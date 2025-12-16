# Design Document

## Overview

本设计为 MCP 工具实现一个基于装饰器的内存缓存系统。缓存装饰器 `@mcp_cache` 可以应用于任何 MCP 工具函数，自动缓存函数返回结果，默认缓存时间为 2 分钟（120 秒）。

## Architecture

```mermaid
graph TD
    A[MCP Tool Function] --> B{@mcp_cache decorator}
    B --> C{Check Cache}
    C -->|Cache Hit & Valid| D[Return Cached Result]
    C -->|Cache Miss or Expired| E[Execute Original Function]
    E --> F[Store Result in Cache]
    F --> G[Return Fresh Result]
    D --> H[Add cache_hit metadata]
    G --> I[Add cache_miss metadata]
```

### 缓存流程

1. 函数调用时，装饰器拦截请求
2. 根据函数名和参数生成缓存键
3. 检查缓存是否存在且未过期
4. 命中则返回缓存结果，未命中则执行原函数并缓存结果
5. 在响应元数据中标记缓存状态

## Components and Interfaces

### 1. CacheEntry 数据类

```python
@dataclass
class CacheEntry:
    """缓存条目"""
    value: Any           # 缓存的值
    created_at: float    # 创建时间戳
    ttl: float           # 生存时间（秒）
    
    def is_expired(self) -> bool:
        """检查缓存是否过期"""
        return time.time() - self.created_at > self.ttl
    
    def age(self) -> float:
        """获取缓存年龄（秒）"""
        return time.time() - self.created_at
```

### 2. CacheStore 类

```python
class CacheStore:
    """缓存存储管理器"""
    
    def __init__(self):
        self._cache: Dict[str, CacheEntry] = {}
        self._lock = threading.Lock()
    
    def get(self, key: str) -> Optional[CacheEntry]:
        """获取缓存条目"""
        
    def set(self, key: str, value: Any, ttl: float) -> None:
        """设置缓存条目"""
        
    def delete(self, key: str) -> bool:
        """删除指定缓存条目"""
        
    def clear(self, pattern: Optional[str] = None) -> int:
        """清除缓存，可选按模式匹配"""
        
    def cleanup_expired(self) -> int:
        """清理所有过期条目"""
```

### 3. mcp_cache 装饰器

```python
def mcp_cache(ttl: float = 120.0):
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
    """
```

### 4. 缓存键生成函数

```python
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
```

### 5. 缓存管理函数

```python
def clear_cache(pattern: Optional[str] = None) -> int:
    """清除缓存"""

def get_cache_stats() -> Dict[str, Any]:
    """获取缓存统计信息"""
```

## Data Models

### CacheEntry

| 字段 | 类型 | 描述 |
|------|------|------|
| value | Any | 缓存的返回值 |
| created_at | float | Unix 时间戳 |
| ttl | float | 生存时间（秒） |

### Cache Store 内部结构

```python
{
    "dm_query:hash(args)": CacheEntry(value={...}, created_at=1234567890.0, ttl=120.0),
    "another_tool:hash(args)": CacheEntry(value={...}, created_at=1234567891.0, ttl=300.0),
}
```

### 响应元数据扩展

```python
{
    "success": True,
    "data": [...],
    "metadata": {
        "operation": "dm_query",
        "execution_time": 0.001,  # 缓存命中时接近 0
        "cache_status": "hit",    # "hit" 或 "miss"
        "cache_age": 45.2,        # 仅在 hit 时存在，单位秒
        ...
    }
}
```



## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Cache hit returns cached value without function execution

*For any* decorated function and any valid arguments, if the function is called twice with identical arguments within the TTL period, the second call SHALL return the cached result and the original function SHALL be executed exactly once.

**Validates: Requirements 1.2, 1.3**

### Property 2: Cache expiration invalidates entries

*For any* cache entry with TTL t, after time t has elapsed since creation, the entry SHALL be treated as invalid and accessing it SHALL trigger re-execution of the original function.

**Validates: Requirements 2.1, 2.2**

### Property 3: Cache key determinism and uniqueness

*For any* function f and arguments (args, kwargs), calling `generate_cache_key(f, args, kwargs)` multiple times SHALL produce the same key, AND calling with different arguments SHALL produce different keys.

**Validates: Requirements 3.2, 3.3**

### Property 4: Cache key handles positional and keyword arguments equivalently

*For any* function f with parameters, calling f(a, b) and f(a=a, b=b) with equivalent values SHALL produce the same cache key.

**Validates: Requirements 3.4**

### Property 5: Clear cache removes all entries

*For any* cache state with n entries (n >= 0), after calling `clear_cache()`, the cache SHALL contain 0 entries.

**Validates: Requirements 4.1**

### Property 6: Pattern-based clear removes only matching entries

*For any* cache state and pattern p, after calling `clear_cache(pattern=p)`, only entries whose keys match pattern p SHALL be removed, and all non-matching entries SHALL remain.

**Validates: Requirements 4.2**

### Property 7: Cache status metadata correctness

*For any* decorated function call, the response metadata SHALL contain `cache_status` equal to "hit" if the result came from cache, or "miss" if the function was executed. Additionally, cache hits SHALL include a non-negative `cache_age` value.

**Validates: Requirements 5.1, 5.2, 5.3**

### Property 8: Custom TTL is respected

*For any* custom TTL value t specified in the decorator, cached entries SHALL expire after exactly t seconds, not the default 120 seconds.

**Validates: Requirements 1.5**

## Error Handling

| 场景 | 处理方式 |
|------|----------|
| 缓存键生成失败（不可哈希参数） | 跳过缓存，直接执行函数，记录警告日志 |
| 缓存存储失败 | 返回函数结果，不影响正常执行 |
| 并发访问冲突 | 使用线程锁保护缓存操作 |

## Testing Strategy

### Property-Based Testing

使用 `hypothesis` 库进行属性测试：

- 测试缓存键生成的确定性和唯一性
- 测试缓存过期行为
- 测试缓存命中/未命中的正确性
- 测试清除功能的完整性

每个属性测试配置运行至少 100 次迭代。

### Unit Testing

使用 `pytest` 进行单元测试：

- 测试默认 TTL 值为 120 秒
- 测试装饰器基本功能
- 测试边界条件（空参数、特殊字符等）

### 测试标注格式

每个属性测试必须使用以下格式标注：
```python
# **Feature: mcp-cache, Property {number}: {property_text}**
```
