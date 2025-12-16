"""
缓存模块测试

使用 hypothesis 进行属性测试，验证缓存功能的正确性
"""

import time
from unittest.mock import patch

import pytest
from hypothesis import given, settings, strategies as st

from core.cache import (
    CacheEntry,
    CacheStore,
    DEFAULT_TTL,
    clear_cache,
    generate_cache_key,
    get_cache_stats,
    get_cache_store,
    mcp_cache,
)


class TestCacheEntry:
    """CacheEntry 测试"""
    
    def test_cache_entry_creation(self):
        """测试缓存条目创建"""
        entry = CacheEntry(value="test", created_at=time.time(), ttl=60.0)
        assert entry.value == "test"
        assert entry.ttl == 60.0
    
    def test_cache_entry_not_expired(self):
        """测试未过期的缓存条目"""
        entry = CacheEntry(value="test", created_at=time.time(), ttl=60.0)
        assert not entry.is_expired()
    
    def test_cache_entry_expired(self):
        """测试已过期的缓存条目"""
        entry = CacheEntry(value="test", created_at=time.time() - 120, ttl=60.0)
        assert entry.is_expired()
    
    def test_cache_entry_age(self):
        """测试缓存条目年龄"""
        created_at = time.time() - 30
        entry = CacheEntry(value="test", created_at=created_at, ttl=60.0)
        assert 29 <= entry.age() <= 31  # 允许小误差
    
    # **Feature: mcp-cache, Property 2: Cache expiration invalidates entries**
    @given(
        ttl=st.floats(min_value=0.1, max_value=10.0),
        elapsed_ratio=st.floats(min_value=0.0, max_value=0.9).filter(lambda x: x < 0.9) | 
                      st.floats(min_value=1.1, max_value=3.0)
    )
    @settings(max_examples=100)
    def test_property_cache_expiration(self, ttl: float, elapsed_ratio: float):
        """
        属性测试：缓存过期使条目失效
        
        对于任何 TTL 值 t，在创建后经过 t 时间后，条目应被视为无效
        
        **Validates: Requirements 2.1, 2.2**
        """
        elapsed_time = ttl * elapsed_ratio
        created_at = time.time() - elapsed_time
        entry = CacheEntry(value="test", created_at=created_at, ttl=ttl)
        
        # 如果经过的时间超过 TTL，条目应该过期（避免边界条件 elapsed_time == ttl）
        if elapsed_time > ttl:
            assert entry.is_expired(), f"Entry should be expired: elapsed={elapsed_time}, ttl={ttl}"
        elif elapsed_time < ttl:
            assert not entry.is_expired(), f"Entry should not be expired: elapsed={elapsed_time}, ttl={ttl}"


class TestCacheStore:
    """CacheStore 测试"""
    
    def setup_method(self):
        """每个测试前清空缓存"""
        self.store = CacheStore()
    
    def test_set_and_get(self):
        """测试设置和获取缓存"""
        self.store.set("key1", "value1", 60.0)
        entry = self.store.get("key1")
        assert entry is not None
        assert entry.value == "value1"
    
    def test_get_nonexistent(self):
        """测试获取不存在的键"""
        entry = self.store.get("nonexistent")
        assert entry is None
    
    def test_get_expired(self):
        """测试获取已过期的条目"""
        self.store.set("key1", "value1", 0.001)
        time.sleep(0.01)
        entry = self.store.get("key1")
        assert entry is None
    
    def test_delete(self):
        """测试删除缓存条目"""
        self.store.set("key1", "value1", 60.0)
        assert self.store.delete("key1")
        assert self.store.get("key1") is None
    
    def test_delete_nonexistent(self):
        """测试删除不存在的键"""
        assert not self.store.delete("nonexistent")
    
    # **Feature: mcp-cache, Property 5: Clear cache removes all entries**
    @given(
        keys=st.lists(st.text(min_size=1, max_size=20), min_size=0, max_size=10, unique=True)
    )
    @settings(max_examples=100)
    def test_property_clear_removes_all(self, keys: list):
        """
        属性测试：清除缓存移除所有条目
        
        对于任何缓存状态（n 个条目），调用 clear() 后缓存应包含 0 个条目
        
        **Validates: Requirements 4.1**
        """
        store = CacheStore()
        
        # 添加条目
        for key in keys:
            store.set(key, f"value_{key}", 60.0)
        
        # 清除所有
        cleared = store.clear()
        
        # 验证
        assert cleared == len(keys)
        assert store.size() == 0
    
    # **Feature: mcp-cache, Property 6: Pattern-based clear removes only matching entries**
    @given(
        prefix=st.text(alphabet="abc", min_size=1, max_size=3),
        matching_suffixes=st.lists(st.text(alphabet="123", min_size=1, max_size=3), min_size=0, max_size=5, unique=True),
        non_matching_keys=st.lists(st.text(alphabet="xyz", min_size=1, max_size=5), min_size=0, max_size=5, unique=True)
    )
    @settings(max_examples=100)
    def test_property_pattern_clear(self, prefix: str, matching_suffixes: list, non_matching_keys: list):
        """
        属性测试：按模式清除只移除匹配的条目
        
        对于任何缓存状态和模式 p，调用 clear(pattern=p) 后，
        只有键匹配模式 p 的条目被移除，其他条目保留
        
        **Validates: Requirements 4.2**
        """
        store = CacheStore()
        
        # 添加匹配模式的条目
        matching_keys = [f"{prefix}_{suffix}" for suffix in matching_suffixes]
        for key in matching_keys:
            store.set(key, f"value_{key}", 60.0)
        
        # 添加不匹配的条目
        for key in non_matching_keys:
            store.set(key, f"value_{key}", 60.0)
        
        initial_size = store.size()
        
        # 按模式清除
        pattern = f"{prefix}_*"
        cleared = store.clear(pattern=pattern)
        
        # 验证：匹配的被清除
        assert cleared == len(matching_keys)
        
        # 验证：不匹配的保留
        for key in non_matching_keys:
            entry = store.get(key)
            assert entry is not None, f"Non-matching key '{key}' should remain"



class TestGenerateCacheKey:
    """缓存键生成测试"""
    
    def test_basic_key_generation(self):
        """测试基本键生成"""
        key = generate_cache_key("test_func", ("arg1",), {"kwarg1": "value1"})
        assert key.startswith("test_func:")
        assert len(key) > len("test_func:")
    
    def test_same_args_same_key(self):
        """测试相同参数生成相同键"""
        key1 = generate_cache_key("func", ("a", "b"), {"c": 1})
        key2 = generate_cache_key("func", ("a", "b"), {"c": 1})
        assert key1 == key2
    
    def test_different_args_different_key(self):
        """测试不同参数生成不同键"""
        key1 = generate_cache_key("func", ("a",), {})
        key2 = generate_cache_key("func", ("b",), {})
        assert key1 != key2
    
    # **Feature: mcp-cache, Property 3: Cache key determinism and uniqueness**
    @given(
        func_name=st.text(min_size=1, max_size=20, alphabet="abcdefghijklmnopqrstuvwxyz_"),
        args=st.tuples(st.integers(), st.integers()),
        kwargs_values=st.tuples(st.integers(), st.integers())
    )
    @settings(max_examples=100)
    def test_property_key_determinism(self, func_name: str, args: tuple, kwargs_values: tuple):
        """
        属性测试：缓存键确定性
        
        对于任何函数 f 和参数 (args, kwargs)，多次调用 generate_cache_key 应产生相同的键
        
        **Validates: Requirements 3.2, 3.3**
        """
        kwargs = {"a": kwargs_values[0], "b": kwargs_values[1]}
        
        # 多次生成应该得到相同结果
        key1 = generate_cache_key(func_name, args, kwargs)
        key2 = generate_cache_key(func_name, args, kwargs)
        key3 = generate_cache_key(func_name, args, kwargs)
        
        assert key1 == key2 == key3, "Same inputs should produce same key"
    
    @given(
        func_name=st.text(min_size=1, max_size=10, alphabet="abcdefghijklmnopqrstuvwxyz"),
        arg1=st.integers(min_value=0, max_value=1000),
        arg2=st.integers(min_value=0, max_value=1000)
    )
    @settings(max_examples=100)
    def test_property_key_uniqueness(self, func_name: str, arg1: int, arg2: int):
        """
        属性测试：缓存键唯一性
        
        对于不同的参数，应产生不同的键
        
        **Validates: Requirements 3.2, 3.3**
        """
        # 只有当参数不同时才测试唯一性
        if arg1 != arg2:
            key1 = generate_cache_key(func_name, (arg1,), {})
            key2 = generate_cache_key(func_name, (arg2,), {})
            assert key1 != key2, f"Different args should produce different keys: {arg1} vs {arg2}"
    
    # **Feature: mcp-cache, Property 4: Cache key handles positional and keyword arguments equivalently**
    @given(
        a=st.integers(),
        b=st.integers()
    )
    @settings(max_examples=100)
    def test_property_kwargs_order_independence(self, a: int, b: int):
        """
        属性测试：关键字参数顺序无关性
        
        关键字参数的顺序不应影响生成的键
        
        **Validates: Requirements 3.4**
        """
        # 不同顺序的 kwargs 应该生成相同的键
        key1 = generate_cache_key("func", (), {"a": a, "b": b})
        key2 = generate_cache_key("func", (), {"b": b, "a": a})
        
        assert key1 == key2, "Kwargs order should not affect cache key"



class TestMcpCacheDecorator:
    """mcp_cache 装饰器测试"""
    
    def setup_method(self):
        """每个测试前清空缓存"""
        clear_cache()
    
    def test_default_ttl(self):
        """测试默认 TTL 为 120 秒"""
        @mcp_cache()
        def test_func():
            return {"success": True, "metadata": {}}
        
        assert test_func._cache_ttl == 120.0
    
    def test_custom_ttl(self):
        """测试自定义 TTL"""
        @mcp_cache(ttl=300)
        def test_func():
            return {"success": True, "metadata": {}}
        
        assert test_func._cache_ttl == 300.0
    
    def test_cache_hit(self):
        """测试缓存命中"""
        call_count = 0
        
        @mcp_cache()
        def test_func(x):
            nonlocal call_count
            call_count += 1
            return {"success": True, "data": x, "metadata": {"operation": "test"}}
        
        # 第一次调用
        result1 = test_func(1)
        assert call_count == 1
        assert result1["metadata"]["cache_status"] == "miss"
        
        # 第二次调用（应该命中缓存）
        result2 = test_func(1)
        assert call_count == 1  # 函数没有被再次调用
        assert result2["metadata"]["cache_status"] == "hit"
        assert "cache_age" in result2["metadata"]
    
    def test_cache_miss_different_args(self):
        """测试不同参数导致缓存未命中"""
        call_count = 0
        
        @mcp_cache()
        def test_func(x):
            nonlocal call_count
            call_count += 1
            return {"success": True, "data": x, "metadata": {"operation": "test"}}
        
        test_func(1)
        test_func(2)
        assert call_count == 2
    
    # **Feature: mcp-cache, Property 1: Cache hit returns cached value without function execution**
    @given(
        arg=st.integers(min_value=0, max_value=100)
    )
    @settings(max_examples=100)
    def test_property_cache_hit_no_execution(self, arg: int):
        """
        属性测试：缓存命中返回缓存值且不执行原函数
        
        对于任何装饰函数和有效参数，如果在 TTL 期间内用相同参数调用两次，
        第二次调用应返回缓存结果，原函数只执行一次
        
        **Validates: Requirements 1.2, 1.3**
        """
        clear_cache()
        call_count = 0
        
        @mcp_cache(ttl=60)
        def cached_func(x):
            nonlocal call_count
            call_count += 1
            return {"success": True, "data": x * 2, "metadata": {"operation": "test"}}
        
        # 第一次调用
        result1 = cached_func(arg)
        assert call_count == 1
        
        # 第二次调用
        result2 = cached_func(arg)
        assert call_count == 1, "Function should not be called again on cache hit"
        
        # 结果应该相同
        assert result1["data"] == result2["data"]
        assert result2["metadata"]["cache_status"] == "hit"
    
    # **Feature: mcp-cache, Property 7: Cache status metadata correctness**
    @given(
        arg=st.integers()
    )
    @settings(max_examples=100)
    def test_property_cache_metadata(self, arg: int):
        """
        属性测试：缓存状态元数据正确性
        
        对于任何装饰函数调用，响应元数据应包含 cache_status，
        值为 "hit"（来自缓存）或 "miss"（执行函数）。
        缓存命中还应包含非负的 cache_age 值
        
        **Validates: Requirements 5.1, 5.2, 5.3**
        """
        clear_cache()
        
        @mcp_cache(ttl=60)
        def cached_func(x):
            return {"success": True, "data": x, "metadata": {"operation": "test"}}
        
        # 第一次调用 - miss
        result1 = cached_func(arg)
        assert "cache_status" in result1["metadata"]
        assert result1["metadata"]["cache_status"] == "miss"
        
        # 第二次调用 - hit
        result2 = cached_func(arg)
        assert "cache_status" in result2["metadata"]
        assert result2["metadata"]["cache_status"] == "hit"
        assert "cache_age" in result2["metadata"]
        assert result2["metadata"]["cache_age"] >= 0
    
    # **Feature: mcp-cache, Property 8: Custom TTL is respected**
    @given(
        ttl=st.floats(min_value=0.05, max_value=0.2)
    )
    @settings(max_examples=20, deadline=None)
    def test_property_custom_ttl_respected(self, ttl: float):
        """
        属性测试：自定义 TTL 被正确使用
        
        对于任何自定义 TTL 值 t，缓存条目应在 t 秒后过期，而不是默认的 120 秒
        
        **Validates: Requirements 1.5**
        """
        clear_cache()
        call_count = 0
        
        @mcp_cache(ttl=ttl)
        def cached_func(x):
            nonlocal call_count
            call_count += 1
            return {"success": True, "data": x, "metadata": {"operation": "test"}}
        
        # 验证 TTL 被正确设置
        assert cached_func._cache_ttl == ttl
        
        # 第一次调用
        cached_func(42)
        assert call_count == 1
        
        # 等待 TTL 过期
        time.sleep(ttl + 0.02)
        
        # 再次调用，应该重新执行函数
        cached_func(42)
        assert call_count == 2, f"Function should be called again after TTL ({ttl}s) expires"



class TestCacheIntegration:
    """缓存集成测试"""
    
    def setup_method(self):
        """每个测试前清空缓存"""
        clear_cache()
    
    def test_decorator_stacking(self):
        """测试装饰器堆叠正常工作"""
        from core import mcp_tool_handler
        
        call_count = 0
        
        @mcp_cache(ttl=60)
        @mcp_tool_handler("test_op")
        def stacked_func(x: int):
            nonlocal call_count
            call_count += 1
            return {"success": True, "data": x, "metadata": {"operation": "test_op"}}
        
        # 第一次调用
        result1 = stacked_func(10)
        assert result1["success"] is True
        assert result1["data"] == 10
        assert call_count == 1
        
        # 第二次调用（缓存命中）
        result2 = stacked_func(10)
        assert result2["success"] is True
        assert call_count == 1  # 没有再次调用
        assert result2["metadata"]["cache_status"] == "hit"
    
    def test_cache_with_error_handling(self):
        """测试缓存与错误处理的交互"""
        from core import mcp_tool_handler, InvalidParameterError
        
        @mcp_cache(ttl=60)
        @mcp_tool_handler("test_op")
        def error_func(x: int):
            if x < 0:
                raise InvalidParameterError("x must be non-negative")
            return {"success": True, "data": x, "metadata": {"operation": "test_op"}}
        
        # 正常调用
        result1 = error_func(5)
        assert result1["success"] is True
        
        # 错误调用（不应被缓存）
        result2 = error_func(-1)
        assert result2["success"] is False
        
        # 再次正常调用（应该命中缓存）
        result3 = error_func(5)
        assert result3["metadata"]["cache_status"] == "hit"
    
    def test_clear_cache_function(self):
        """测试清除缓存功能"""
        @mcp_cache(ttl=60)
        def cached_func(x):
            return {"success": True, "data": x, "metadata": {"operation": "test"}}
        
        # 填充缓存
        cached_func(1)
        cached_func(2)
        cached_func(3)
        
        stats = get_cache_stats()
        assert stats["size"] == 3
        
        # 清除缓存
        cleared = clear_cache()
        assert cleared == 3
        
        stats = get_cache_stats()
        assert stats["size"] == 0
    
    def test_cache_stats(self):
        """测试缓存统计功能"""
        @mcp_cache(ttl=60)
        def cached_func(x):
            return {"success": True, "data": x, "metadata": {"operation": "test"}}
        
        cached_func(1)
        cached_func(2)
        
        stats = get_cache_stats()
        assert stats["size"] == 2
        assert len(stats["keys"]) == 2
