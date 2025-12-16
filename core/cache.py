"""
MCP 缓存模块

提供基于装饰器的内存缓存系统，支持 TTL 过期和线程安全操作
"""

import fnmatch
import hashlib
import json
import threading
import time
from dataclasses import dataclass
from functools import wraps
from typing import Any, Callable, Dict, Optional


# 默认缓存 TTL（秒）
DEFAULT_TTL = 120.0


@dataclass
class CacheEntry:
    """
    缓存条目
    
    Attributes:
        value: 缓存的值
        created_at: 创建时间戳
        ttl: 生存时间（秒）
    """
    value: Any
    created_at: float
    ttl: float
    
    def is_expired(self) -> bool:
        """检查缓存是否过期"""
        return time.time() - self.created_at > self.ttl
    
    def age(self) -> float:
        """获取缓存年龄（秒）"""
        return time.time() - self.created_at


class CacheStore:
    """
    缓存存储管理器
    
    线程安全的内存缓存存储，支持 TTL 过期和模式匹配清除
    """
    
    def __init__(self):
        self._cache: Dict[str, CacheEntry] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[CacheEntry]:
        """
        获取缓存条目
        
        Args:
            key: 缓存键
            
        Returns:
            缓存条目，如果不存在或已过期则返回 None
        """
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            if entry.is_expired():
                del self._cache[key]
                return None
            return entry
    
    def set(self, key: str, value: Any, ttl: float) -> None:
        """
        设置缓存条目
        
        Args:
            key: 缓存键
            value: 要缓存的值
            ttl: 生存时间（秒）
        """
        with self._lock:
            self._cache[key] = CacheEntry(
                value=value,
                created_at=time.time(),
                ttl=ttl
            )
    
    def delete(self, key: str) -> bool:
        """
        删除指定缓存条目
        
        Args:
            key: 缓存键
            
        Returns:
            是否成功删除
        """
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False
    
    def clear(self, pattern: Optional[str] = None) -> int:
        """
        清除缓存
        
        Args:
            pattern: 可选的 glob 模式，仅清除匹配的条目
            
        Returns:
            清除的条目数量
        """
        with self._lock:
            if pattern is None:
                count = len(self._cache)
                self._cache.clear()
                return count
            
            keys_to_delete = [
                key for key in self._cache.keys()
                if fnmatch.fnmatch(key, pattern)
            ]
            for key in keys_to_delete:
                del self._cache[key]
            return len(keys_to_delete)
    
    def cleanup_expired(self) -> int:
        """
        清理所有过期条目
        
        Returns:
            清理的条目数量
        """
        with self._lock:
            expired_keys = [
                key for key, entry in self._cache.items()
                if entry.is_expired()
            ]
            for key in expired_keys:
                del self._cache[key]
            return len(expired_keys)
    
    def size(self) -> int:
        """获取缓存条目数量"""
        with self._lock:
            return len(self._cache)
    
    def keys(self) -> list:
        """获取所有缓存键"""
        with self._lock:
            return list(self._cache.keys())


# 全局缓存存储实例
_cache_store = CacheStore()


def generate_cache_key(func_name: str, args: tuple, kwargs: dict) -> str:
    """
    生成缓存键
    
    Args:
        func_name: 函数名
        args: 位置参数
        kwargs: 关键字参数
    
    Returns:
        唯一的缓存键字符串
    """
    # 将参数序列化为可哈希的字符串
    key_parts = [func_name]
    
    # 添加位置参数
    for arg in args:
        key_parts.append(repr(arg))
    
    # 添加排序后的关键字参数
    for k in sorted(kwargs.keys()):
        key_parts.append(f"{k}={repr(kwargs[k])}")
    
    # 生成哈希
    key_str = "|".join(key_parts)
    hash_value = hashlib.md5(key_str.encode()).hexdigest()[:16]
    
    return f"{func_name}:{hash_value}"


def mcp_cache(ttl: float = DEFAULT_TTL):
    """
    MCP 工具缓存装饰器
    
    Args:
        ttl: 缓存生存时间，默认 120 秒（2 分钟）
    
    Usage:
        @mcp_cache()  # 使用默认 2 分钟缓存
        def my_tool(arg1, arg2):
            ...
        
        @mcp_cache(ttl=300)  # 自定义 5 分钟缓存
        def another_tool(arg1):
            ...
    
    Returns:
        装饰器函数
    
    Note:
        只缓存成功的结果（result.get("success") == True）
        失败的结果不会被缓存，避免缓存错误状态
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Dict[str, Any]:
            # 生成缓存键
            cache_key = generate_cache_key(func.__name__, args, kwargs)
            
            # 检查缓存
            entry = _cache_store.get(cache_key)
            if entry is not None:
                # 缓存命中
                result = entry.value
                # 添加缓存元数据
                if isinstance(result, dict) and "metadata" in result:
                    result = result.copy()
                    result["metadata"] = result["metadata"].copy()
                    result["metadata"]["cache_status"] = "hit"
                    result["metadata"]["cache_age"] = entry.age()
                return result
            
            # 缓存未命中，执行原函数
            result = func(*args, **kwargs)
            
            # 只缓存成功的结果，避免缓存错误状态
            should_cache = True
            if isinstance(result, dict):
                # 如果结果包含 success 字段，只缓存成功的结果
                if "success" in result and not result["success"]:
                    should_cache = False
            
            if should_cache:
                # 存储结果到缓存
                _cache_store.set(cache_key, result, ttl)
            
            # 添加缓存元数据
            if isinstance(result, dict) and "metadata" in result:
                result = result.copy()
                result["metadata"] = result["metadata"].copy()
                result["metadata"]["cache_status"] = "miss" if should_cache else "skip"
            
            return result
        
        # 保存 TTL 信息供测试使用
        wrapper._cache_ttl = ttl
        return wrapper
    
    return decorator


def clear_cache(pattern: Optional[str] = None) -> int:
    """
    清除缓存
    
    Args:
        pattern: 可选的 glob 模式，仅清除匹配的条目
        
    Returns:
        清除的条目数量
    """
    return _cache_store.clear(pattern)


def get_cache_stats() -> Dict[str, Any]:
    """
    获取缓存统计信息
    
    Returns:
        包含缓存统计的字典
    """
    return {
        "size": _cache_store.size(),
        "keys": _cache_store.keys()
    }


def get_cache_store() -> CacheStore:
    """获取全局缓存存储实例（主要用于测试）"""
    return _cache_store
