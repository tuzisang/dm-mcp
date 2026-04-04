"""
缓存模块基础测试
"""

import time
import pytest
from core.cache import (
    CacheEntry, CacheStore, clear_cache, generate_cache_key,
    get_cache_stats, mcp_cache,
)


class TestCacheEntry:
    """CacheEntry 测试"""
    
    def test_cache_entry_creation(self):
        entry = CacheEntry(value="test", created_at=time.time(), ttl=60.0)
        assert entry.value == "test"
        assert entry.ttl == 60.0
    
    def test_cache_entry_not_expired(self):
        entry = CacheEntry(value="test", created_at=time.time(), ttl=60.0)
        assert not entry.is_expired()
    
    def test_cache_entry_expired(self):
        entry = CacheEntry(value="test", created_at=time.time() - 120, ttl=60.0)
        assert entry.is_expired()


class TestCacheStore:
    """CacheStore 测试"""
    
    def test_set_and_get(self):
        store = CacheStore()
        store.set("key1", "value1", 60.0)
        entry = store.get("key1")
        assert entry is not None
        assert entry.value == "value1"
    
    def test_get_nonexistent(self):
        store = CacheStore()
        assert store.get("nonexistent") is None
    
    def test_delete(self):
        store = CacheStore()
        store.set("key1", "value1", 60.0)
        assert store.delete("key1")
        assert store.get("key1") is None
    
    def test_clear(self):
        store = CacheStore()
        store.set("key1", "value1", 60.0)
        store.set("key2", "value2", 60.0)
        cleared = store.clear()
        assert cleared == 2
        assert store.size() == 0


class TestGenerateCacheKey:
    """缓存键生成测试"""
    
    def test_same_args_same_key(self):
        key1 = generate_cache_key("func", ("a", "b"), {"c": 1})
        key2 = generate_cache_key("func", ("a", "b"), {"c": 1})
        assert key1 == key2
    
    def test_different_args_different_key(self):
        key1 = generate_cache_key("func", ("a",), {})
        key2 = generate_cache_key("func", ("b",), {})
        assert key1 != key2


class TestMcpCacheDecorator:
    """mcp_cache 装饰器测试"""
    
    def setup_method(self):
        clear_cache()
    
    def test_default_ttl(self):
        @mcp_cache()
        def test_func():
            return {"success": True, "metadata": {}}
        assert test_func._cache_ttl == 60.0
    
    def test_cache_hit(self):
        call_count = 0
        
        @mcp_cache()
        def test_func(x):
            nonlocal call_count
            call_count += 1
            return {"success": True, "data": x, "metadata": {"operation": "test"}}
        
        result1 = test_func(1)
        assert call_count == 1
        assert result1["metadata"]["cache_status"] == "miss"
        
        result2 = test_func(1)
        assert call_count == 1  # 没有再次调用
        assert result2["metadata"]["cache_status"] == "hit"
    
    def test_cache_miss_different_args(self):
        call_count = 0
        
        @mcp_cache()
        def test_func(x):
            nonlocal call_count
            call_count += 1
            return {"success": True, "data": x, "metadata": {"operation": "test"}}
        
        test_func(1)
        test_func(2)
        assert call_count == 2
