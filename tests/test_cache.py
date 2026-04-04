"""缓存公共行为测试。"""

from core.cache import clear_cache, mcp_cache


def setup_function():
    clear_cache()


def test_default_ttl():
    @mcp_cache()
    def test_func():
        return {"success": True, "metadata": {}}

    assert test_func._cache_ttl == 60.0


def test_cache_hit():
    call_count = 0

    @mcp_cache()
    def test_func(x):
        nonlocal call_count
        call_count += 1
        return {"success": True, "data": x, "metadata": {"operation": "test"}}

    first = test_func(1)
    second = test_func(1)

    assert call_count == 1
    assert first["metadata"]["cache_status"] == "miss"
    assert second["metadata"]["cache_status"] == "hit"


def test_failed_result_is_not_cached():
    call_count = 0

    @mcp_cache()
    def test_func():
        nonlocal call_count
        call_count += 1
        return {"success": False, "metadata": {"operation": "test"}}

    first = test_func()
    second = test_func()

    assert call_count == 2
    assert first["metadata"]["cache_status"] == "skip"
    assert second["metadata"]["cache_status"] == "skip"


def test_clear_cache_forces_recompute():
    call_count = 0

    @mcp_cache()
    def test_func():
        nonlocal call_count
        call_count += 1
        return {"success": True, "metadata": {"operation": "test"}}

    test_func()
    clear_cache()
    test_func()

    assert call_count == 2
