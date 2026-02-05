"""
假死测试 - 验证不会发生死锁或无限循环
"""

import threading
import time
import sys
from unittest.mock import Mock, patch


TEST_TIMEOUT = 10


def run_with_timeout(func, timeout=TEST_TIMEOUT):
    """运行函数并设置超时"""
    result = {'value': None, 'error': None, 'completed': False}
    
    def wrapper():
        try:
            result['value'] = func()
            result['completed'] = True
        except Exception as e:
            result['error'] = e
            result['completed'] = True
    
    thread = threading.Thread(target=wrapper, daemon=True)
    thread.start()
    thread.join(timeout=timeout)
    
    if not result['completed']:
        return False, "DEADLOCK"
    if result['error']:
        return True, f"异常: {result['error']}"
    return True, f"成功: {result['value']}"


def test_connection_timeout():
    """测试连接超时不假死"""
    print("\n=== 测试: 连接超时 ===")
    
    def test_func():
        from db import DmConnectionPool, PoolConfig
        
        with DmConnectionPool._lock:
            DmConnectionPool._instance = None
        
        pool_config = PoolConfig(min_connections=0, max_connections=1, connection_timeout=2)
        
        with patch('db.pool.DmConnectionPool._get_driver') as mock_driver:
            mock_dm = Mock()
            mock_dm.connect = lambda *args: time.sleep(100)
            mock_driver.return_value = mock_dm
            
            pool = DmConnectionPool(
                db_config={'host': 'fake', 'port': 5236, 'user': 'test', 'password': 'test'},
                pool_config=pool_config
            )
            
            try:
                pool.get_connection(timeout=2)
                return "ERROR"
            except (TimeoutError, Exception):
                return "OK"
            finally:
                pool.close()
    
    success, msg = run_with_timeout(test_func)
    print(f"结果: {'✓' if success else '✗'} {msg}")
    return success


def test_health_check_timeout():
    """测试健康检查超时不阻塞"""
    print("\n=== 测试: 健康检查超时 ===")
    
    def test_func():
        from db import PooledConnection
        
        mock_conn = Mock()
        mock_conn.cursor = Mock(return_value=Mock(execute=lambda *args: time.sleep(100)))
        
        pooled = PooledConnection(mock_conn, None)
        start = time.time()
        pooled.is_healthy(timeout=2)
        elapsed = time.time() - start
        
        return "OK" if elapsed < 5 else "ERROR"
    
    success, msg = run_with_timeout(test_func)
    print(f"结果: {'✓' if success else '✗'} {msg}")
    return success


def test_cache_no_deadlock():
    """测试缓存不死锁"""
    print("\n=== 测试: 缓存并发 ===")
    
    def test_func():
        from core.cache import mcp_cache, clear_cache
        
        clear_cache()
        
        @mcp_cache(ttl=60)
        def cached_func(arg):
            return {"success": True, "data": arg, "metadata": {}}
        
        results = []
        def call_cached():
            for _ in range(10):
                results.append(cached_func("test"))
        
        threads = [threading.Thread(target=call_cached, daemon=True) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)
        
        return f"OK: {len(results)} 次调用"
    
    success, msg = run_with_timeout(test_func)
    print(f"结果: {'✓' if success else '✗'} {msg}")
    return success


def run_all_tests():
    """运行所有测试"""
    print("=" * 40)
    print("假死测试")
    print("=" * 40)
    
    tests = [test_connection_timeout, test_health_check_timeout, test_cache_no_deadlock]
    passed = sum(1 for t in tests if t())
    
    print(f"\n结果: {passed}/{len(tests)} 通过")
    return passed == len(tests)


if __name__ == "__main__":
    sys.exit(0 if run_all_tests() else 1)
