# Implementation Plan

- [x] 1. Create cache module with core data structures


  - [x] 1.1 Create `core/cache.py` with CacheEntry dataclass


    - Implement `value`, `created_at`, `ttl` fields
    - Implement `is_expired()` and `age()` methods
    - _Requirements: 2.1, 2.3_
  - [x] 1.2 Write property test for CacheEntry expiration


    - **Property 2: Cache expiration invalidates entries**
    - **Validates: Requirements 2.1, 2.2**
  - [x] 1.3 Implement CacheStore class with thread-safe operations

    - Implement `get()`, `set()`, `delete()`, `clear()`, `cleanup_expired()` methods
    - Use threading.Lock for thread safety
    - _Requirements: 2.1, 2.2, 4.1, 4.2_
  - [x] 1.4 Write property test for cache clear functionality

    - **Property 5: Clear cache removes all entries**
    - **Validates: Requirements 4.1**
  - [x] 1.5 Write property test for pattern-based clear

    - **Property 6: Pattern-based clear removes only matching entries**
    - **Validates: Requirements 4.2**

- [x] 2. Implement cache key generation


  - [x] 2.1 Create `generate_cache_key()` function

    - Handle function name, positional args, and keyword args
    - Use hashlib for consistent hashing
    - _Requirements: 3.1, 3.2, 3.3, 3.4_
  - [x] 2.2 Write property test for cache key determinism and uniqueness


    - **Property 3: Cache key determinism and uniqueness**
    - **Validates: Requirements 3.2, 3.3**
  - [x] 2.3 Write property test for positional/keyword argument equivalence

    - **Property 4: Cache key handles positional and keyword arguments equivalently**
    - **Validates: Requirements 3.4**

- [x] 3. Implement mcp_cache decorator


  - [x] 3.1 Create `mcp_cache(ttl=120)` decorator function

    - Implement cache lookup and storage logic
    - Add cache_status and cache_age to response metadata
    - Default TTL of 120 seconds
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 5.1, 5.2, 5.3_
  - [x] 3.2 Write property test for cache hit behavior


    - **Property 1: Cache hit returns cached value without function execution**
    - **Validates: Requirements 1.2, 1.3**
  - [x] 3.3 Write property test for cache metadata correctness

    - **Property 7: Cache status metadata correctness**
    - **Validates: Requirements 5.1, 5.2, 5.3**
  - [x] 3.4 Write property test for custom TTL

    - **Property 8: Custom TTL is respected**
    - **Validates: Requirements 1.5**

- [x] 4. Integrate cache with existing MCP tools


  - [x] 4.1 Export cache functions from `core/__init__.py`


    - Export `mcp_cache`, `clear_cache`, `get_cache_stats`
    - _Requirements: 1.1_
  - [x] 4.2 Apply `@mcp_cache()` decorator to `dm_query` in `tools/query.py`


    - Stack with existing `@mcp_tool_handler` decorator
    - _Requirements: 1.1, 1.4_
  - [x] 4.3 Write unit tests for integration


    - Test decorator stacking works correctly
    - Test cache behavior with actual tool functions
    - _Requirements: 1.1, 1.2_

- [x] 5. Checkpoint - Ensure all tests pass



  - Ensure all tests pass, ask the user if questions arise.
