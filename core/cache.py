"""MCP 工具缓存。"""

import fnmatch
import hashlib
import threading
import time
from dataclasses import dataclass
from functools import wraps
from typing import Any, Callable, Dict, Optional

DEFAULT_CACHE_TTL = 60.0


@dataclass
class _CacheEntry:
    """内部缓存条目。"""

    value: Any
    created_at: float
    ttl: float

    def is_expired(self) -> bool:
        """检查缓存是否过期"""
        return time.time() - self.created_at > self.ttl

    def age(self) -> float:
        """获取缓存年龄（秒）"""
        return time.time() - self.created_at


class _CacheStore:
    """线程安全的内部缓存存储。"""

    def __init__(self):
        self._cache: Dict[str, _CacheEntry] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[_CacheEntry]:
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            if entry.is_expired():
                del self._cache[key]
                return None
            return entry

    def set(self, key: str, value: Any, ttl: float) -> None:
        with self._lock:
            self._cache[key] = _CacheEntry(value=value, created_at=time.time(), ttl=ttl)

    def clear(self, pattern: Optional[str] = None) -> int:
        with self._lock:
            if pattern is None:
                count = len(self._cache)
                self._cache.clear()
                return count

            keys_to_delete = [
                key for key in self._cache.keys() if fnmatch.fnmatch(key, pattern)
            ]
            for key in keys_to_delete:
                del self._cache[key]
            return len(keys_to_delete)


_cache_store = _CacheStore()


def _build_cache_key(func_name: str, args: tuple, kwargs: dict) -> str:
    key_parts = [func_name]
    for arg in args:
        key_parts.append(repr(arg))
    for k in sorted(kwargs.keys()):
        key_parts.append(f"{k}={repr(kwargs[k])}")

    key_str = "|".join(key_parts)
    hash_value = hashlib.md5(key_str.encode()).hexdigest()[:16]
    return f"{func_name}:{hash_value}"


def mcp_cache(ttl: float = DEFAULT_CACHE_TTL):
    """只缓存成功的工具结果。"""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Dict[str, Any]:
            cache_key = _build_cache_key(func.__name__, args, kwargs)
            entry = _cache_store.get(cache_key)
            if entry is not None:
                result = entry.value
                if isinstance(result, dict) and "metadata" in result:
                    result = result.copy()
                    result["metadata"] = result["metadata"].copy()
                    result["metadata"]["cache_status"] = "hit"
                    result["metadata"]["cache_age"] = entry.age()
                return result

            result = func(*args, **kwargs)
            should_cache = True
            if isinstance(result, dict):
                if "success" in result and not result["success"]:
                    should_cache = False

            if should_cache:
                _cache_store.set(cache_key, result, ttl)

            if isinstance(result, dict) and "metadata" in result:
                result = result.copy()
                result["metadata"] = result["metadata"].copy()
                result["metadata"]["cache_status"] = "miss" if should_cache else "skip"
            return result

        wrapper._cache_ttl = ttl
        return wrapper

    return decorator


def clear_cache(pattern: Optional[str] = None) -> int:
    """清除缓存。"""
    return _cache_store.clear(pattern)
