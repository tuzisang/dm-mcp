# Requirements Document

## Introduction

本功能为 MCP 工具添加缓存机制，通过装饰器方式实现查询结果缓存，默认缓存时间为 2 分钟。缓存可以减少重复查询对数据库的压力，提升响应速度。

## Glossary

- **Cache_Decorator**: 缓存装饰器，用于包装 MCP 工具函数，自动缓存函数返回结果
- **TTL (Time To Live)**: 缓存生存时间，缓存条目在过期前保持有效的时间长度
- **Cache_Key**: 缓存键，由函数名和参数组合生成的唯一标识符
- **Cache_Store**: 缓存存储，内存中保存缓存数据的字典结构

## Requirements

### Requirement 1

**User Story:** As a developer, I want to use a cache decorator on MCP tools, so that I can easily enable caching for database queries without modifying the core logic.

#### Acceptance Criteria

1. WHEN a developer applies the cache decorator to a function THEN the Cache_Decorator SHALL intercept function calls and check the Cache_Store for existing results
2. WHEN a cached result exists and has not expired THEN the Cache_Decorator SHALL return the cached result without executing the original function
3. WHEN no cached result exists or the cache has expired THEN the Cache_Decorator SHALL execute the original function and store the result in Cache_Store
4. WHEN the cache decorator is applied THEN the Cache_Decorator SHALL use a default TTL of 120 seconds (2 minutes)
5. WHEN a developer specifies a custom TTL THEN the Cache_Decorator SHALL use the specified TTL instead of the default

### Requirement 2

**User Story:** As a system operator, I want the cache to automatically expire old entries, so that stale data does not persist indefinitely.

#### Acceptance Criteria

1. WHEN a cached entry exceeds its TTL THEN the Cache_Store SHALL treat the entry as invalid
2. WHEN an expired entry is accessed THEN the Cache_Decorator SHALL remove the expired entry and execute the original function
3. WHEN storing a new cache entry THEN the Cache_Store SHALL record the timestamp of when the entry was created

### Requirement 3

**User Story:** As a developer, I want the cache key to be generated from function arguments, so that different queries produce different cache entries.

#### Acceptance Criteria

1. WHEN a function is called with arguments THEN the Cache_Decorator SHALL generate a Cache_Key from the function name and all arguments
2. WHEN the same function is called with identical arguments THEN the Cache_Decorator SHALL generate the same Cache_Key
3. WHEN the same function is called with different arguments THEN the Cache_Decorator SHALL generate different Cache_Keys
4. WHEN generating a Cache_Key THEN the Cache_Decorator SHALL handle both positional and keyword arguments

### Requirement 4

**User Story:** As a developer, I want to manually clear the cache, so that I can force fresh data retrieval when needed.

#### Acceptance Criteria

1. WHEN a developer calls the cache clear function THEN the Cache_Store SHALL remove all cached entries
2. WHEN a developer calls the cache clear function with a specific key pattern THEN the Cache_Store SHALL remove only matching entries

### Requirement 5

**User Story:** As a developer, I want cache metadata in responses, so that I can know whether a response came from cache.

#### Acceptance Criteria

1. WHEN returning a cached result THEN the Cache_Decorator SHALL add a cache_hit indicator to the response metadata
2. WHEN returning a fresh result THEN the Cache_Decorator SHALL add a cache_miss indicator to the response metadata
3. WHEN returning a cached result THEN the Cache_Decorator SHALL include the cache entry age in the response metadata
