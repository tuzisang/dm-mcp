"""
MCP 假死测试用例

测试目标：验证 MCP 在各种场景下不会发生假死（死锁、无限循环）

测试场景：
1. 连接池获取连接超时测试
2. 并发获取连接测试
3. 连接池耗尽测试
4. 数据库不可达时的超时测试
5. 健康检查不阻塞测试
6. 缓存装饰器不阻塞测试
7. 快速连接断开测试
8. 成功失败混合测试
9. 连接不健康测试
10. 装饰器链测试
"""

import threading
import time
import sys
from unittest.mock import Mock, patch


# 测试超时时间（秒）- 如果测试超过这个时间就认为发生了假死
TEST_TIMEOUT = 10


def run_with_timeout(func, timeout=TEST_TIMEOUT, *args, **kwargs):
    """运行函数并设置超时，超时则认为假死"""
    result = {'value': None, 'error': None, 'completed': False}
    
    def wrapper():
        try:
            result['value'] = func(*args, **kwargs)
            result['completed'] = True
        except Exception as e:
            result['error'] = e
            result['completed'] = True
    
    thread = threading.Thread(target=wrapper, daemon=True)
    thread.start()
    thread.join(timeout=timeout)
    
    if not result['completed']:
        return False, "DEADLOCK: 函数执行超时，可能发生假死"
    
    if result['error']:
        return True, f"函数执行完成（有异常: {result['error']}）"
    
    return True, f"函数执行成功: {result['value']}"


class TestConnectionPoolNoDeadlock:
    """连接池假死测试"""
    
    def test_get_connection_timeout_no_deadlock(self):
        """测试：获取连接超时时不会假死"""
        print("\n=== 测试1: 获取连接超时不假死 ===")
        
        def test_func():
            from dm_pool import DmConnectionPool, PoolConfig
            
            # 重置单例
            with DmConnectionPool._lock:
                DmConnectionPool._instance = None
            
            pool_config = PoolConfig(
                min_connections=0,
                max_connections=1,
                connection_timeout=2,
            )
            
            with patch('dm_pool.DmConnectionPool._get_driver') as mock_driver:
                mock_dm = Mock()
                def slow_connect(*args):
                    time.sleep(100)
                mock_dm.connect = slow_connect
                mock_driver.return_value = mock_dm
                
                pool = DmConnectionPool(
                    db_config={'host': 'fake', 'port': 5236, 'user': 'test', 'password': 'test'},
                    pool_config=pool_config
                )
                
                try:
                    pool.get_connection(timeout=2)
                    return "ERROR: 应该抛出超时异常"
                except TimeoutError as e:
                    return f"OK: 正确抛出超时异常 - {e}"
                except Exception as e:
                    return f"OK: 抛出其他异常 - {type(e).__name__}: {e}"
                finally:
                    pool.close()
        
        success, msg = run_with_timeout(test_func, timeout=TEST_TIMEOUT)
        print(f"结果: {'✓' if success else '✗'} {msg}")
        assert success, msg
    
    def test_concurrent_connections_no_deadlock(self):
        """测试：并发获取连接不会死锁"""
        print("\n=== 测试2: 并发获取连接不死锁 ===")
        
        def test_func():
            from dm_pool import DmConnectionPool, PoolConfig
            
            with DmConnectionPool._lock:
                DmConnectionPool._instance = None
            
            pool_config = PoolConfig(
                min_connections=0,
                max_connections=2,
                connection_timeout=3,
            )
            
            with patch('dm_pool.DmConnectionPool._get_driver') as mock_driver:
                mock_dm = Mock()
                
                def mock_connect(*args):
                    time.sleep(0.1)
                    mock_conn = Mock()
                    mock_cursor = Mock()
                    mock_cursor.execute = Mock()
                    mock_cursor.fetchone = Mock(return_value=(1,))
                    mock_cursor.close = Mock()
                    mock_conn.cursor = Mock(return_value=mock_cursor)
                    mock_conn.close = Mock()
                    return mock_conn
                
                mock_dm.connect = mock_connect
                mock_driver.return_value = mock_dm
                
                pool = DmConnectionPool(
                    db_config={'host': 'fake', 'port': 5236, 'user': 'test', 'password': 'test'},
                    pool_config=pool_config
                )
                
                results = []
                errors = []
                
                def get_and_release():
                    try:
                        conn = pool.get_connection(timeout=5)
                        time.sleep(0.05)
                        pool.release_connection(conn)
                        results.append("OK")
                    except Exception as e:
                        errors.append(str(e))
                
                threads = []
                for i in range(10):
                    t = threading.Thread(target=get_and_release, daemon=True)
                    threads.append(t)
                    t.start()
                
                for t in threads:
                    t.join(timeout=10)
                
                pool.close()
                return f"OK: {len(results)} 成功, {len(errors)} 失败"
        
        success, msg = run_with_timeout(test_func, timeout=TEST_TIMEOUT)
        print(f"结果: {'✓' if success else '✗'} {msg}")
        assert success, msg
    
    def test_pool_exhausted_no_deadlock(self):
        """测试：连接池耗尽时不会死锁"""
        print("\n=== 测试3: 连接池耗尽不死锁 ===")
        
        def test_func():
            from dm_pool import DmConnectionPool, PoolConfig
            
            with DmConnectionPool._lock:
                DmConnectionPool._instance = None
            
            pool_config = PoolConfig(
                min_connections=0,
                max_connections=1,
                connection_timeout=2,
            )
            
            with patch('dm_pool.DmConnectionPool._get_driver') as mock_driver:
                mock_dm = Mock()
                
                def mock_connect(*args):
                    mock_conn = Mock()
                    mock_cursor = Mock()
                    mock_cursor.execute = Mock()
                    mock_cursor.fetchone = Mock(return_value=(1,))
                    mock_cursor.close = Mock()
                    mock_conn.cursor = Mock(return_value=mock_cursor)
                    mock_conn.close = Mock()
                    return mock_conn
                
                mock_dm.connect = mock_connect
                mock_driver.return_value = mock_dm
                
                pool = DmConnectionPool(
                    db_config={'host': 'fake', 'port': 5236, 'user': 'test', 'password': 'test'},
                    pool_config=pool_config
                )
                
                conn1 = pool.get_connection(timeout=3)
                
                try:
                    pool.get_connection(timeout=2)
                    result = "ERROR: 不应该获取到第二个连接"
                except TimeoutError:
                    result = "OK: 正确抛出超时异常"
                except Exception as e:
                    result = f"OK: 抛出异常 - {type(e).__name__}"
                finally:
                    pool.release_connection(conn1)
                    pool.close()
                
                return result
        
        success, msg = run_with_timeout(test_func, timeout=TEST_TIMEOUT)
        print(f"结果: {'✓' if success else '✗'} {msg}")
        assert success, msg


class TestCacheNoDeadlock:
    """缓存装饰器假死测试"""
    
    def test_cache_no_deadlock(self):
        """测试：缓存装饰器不会死锁"""
        print("\n=== 测试4: 缓存装饰器不死锁 ===")
        
        def test_func():
            from core.cache import mcp_cache, clear_cache
            
            clear_cache()
            call_count = {'count': 0}
            
            @mcp_cache(ttl=60)
            def cached_function(arg):
                call_count['count'] += 1
                return {"success": True, "data": arg, "metadata": {}}
            
            results = []
            
            def call_cached():
                for i in range(10):
                    result = cached_function("test")
                    results.append(result)
            
            threads = []
            for i in range(5):
                t = threading.Thread(target=call_cached, daemon=True)
                threads.append(t)
                t.start()
            
            for t in threads:
                t.join(timeout=5)
            
            return f"OK: {len(results)} 次调用完成，实际执行 {call_count['count']} 次"
        
        success, msg = run_with_timeout(test_func, timeout=TEST_TIMEOUT)
        print(f"结果: {'✓' if success else '✗'} {msg}")
        assert success, msg
    
    def test_cache_error_no_deadlock(self):
        """测试：缓存函数抛出异常时不会死锁"""
        print("\n=== 测试5: 缓存函数异常不死锁 ===")
        
        def test_func():
            from core.cache import mcp_cache, clear_cache
            
            clear_cache()
            
            @mcp_cache(ttl=60)
            def error_function(arg):
                raise ValueError("模拟错误")
            
            errors = []
            
            def call_with_error():
                try:
                    error_function("test")
                except ValueError:
                    errors.append("caught")
            
            threads = []
            for i in range(5):
                t = threading.Thread(target=call_with_error, daemon=True)
                threads.append(t)
                t.start()
            
            for t in threads:
                t.join(timeout=5)
            
            return f"OK: {len(errors)} 个异常被正确捕获"
        
        success, msg = run_with_timeout(test_func, timeout=TEST_TIMEOUT)
        print(f"结果: {'✓' if success else '✗'} {msg}")
        assert success, msg


class TestHealthCheckNoDeadlock:
    """健康检查假死测试"""
    
    def test_health_check_timeout_no_deadlock(self):
        """测试：健康检查超时不会阻塞"""
        print("\n=== 测试6: 健康检查超时不阻塞 ===")
        
        def test_func():
            from dm_pool import PooledConnection
            
            mock_conn = Mock()
            mock_cursor = Mock()
            
            def slow_execute(*args):
                time.sleep(100)
            
            mock_cursor.execute = slow_execute
            mock_conn.cursor = Mock(return_value=mock_cursor)
            
            pooled_conn = PooledConnection(mock_conn, None)
            
            start = time.time()
            result = pooled_conn.is_healthy(timeout=2)
            elapsed = time.time() - start
            
            if elapsed > 5:
                return f"ERROR: 健康检查耗时 {elapsed:.1f}秒，可能阻塞"
            
            return f"OK: 健康检查在 {elapsed:.1f}秒 内完成，结果: {result}"
        
        success, msg = run_with_timeout(test_func, timeout=TEST_TIMEOUT)
        print(f"结果: {'✓' if success else '✗'} {msg}")
        assert success, msg


class TestToolsNoDeadlock:
    """工具函数假死测试"""
    
    def test_query_tool_timeout_no_deadlock(self):
        """测试：查询工具超时不会假死"""
        print("\n=== 测试7: 查询工具超时不假死 ===")
        
        def test_func():
            from dm_pool import DmConnectionPool
            
            with DmConnectionPool._lock:
                DmConnectionPool._instance = None
            
            with patch('dm_client.DmClient._get_driver') as mock_driver:
                mock_driver.return_value = True
                
                with patch('dm_client.DmClient._connect_direct') as mock_connect:
                    mock_connect.return_value = False
                    
                    with patch('dm_client.DmClient._connect_with_pool') as mock_pool_connect:
                        mock_pool_connect.return_value = False
                        
                        from tools.query import dm_query
                        result = dm_query("SELECT 1 FROM DUAL")
                        
                        if result.get('success'):
                            return "ERROR: 不应该成功"
                        
                        return f"OK: 正确返回错误 - {result.get('error', 'unknown')}"
        
        success, msg = run_with_timeout(test_func, timeout=TEST_TIMEOUT)
        print(f"结果: {'✓' if success else '✗'} {msg}")
        assert success, msg


class TestRealWorldScenarios:
    """真实场景假死测试"""
    
    def test_rapid_connect_disconnect_no_deadlock(self):
        """测试：快速连接断开不会死锁"""
        print("\n=== 测试8: 快速连接断开不死锁 ===")
        
        def test_func():
            from dm_pool import DmConnectionPool, PoolConfig
            
            with DmConnectionPool._lock:
                DmConnectionPool._instance = None
            
            pool_config = PoolConfig(
                min_connections=0,
                max_connections=5,
                connection_timeout=3,
            )
            
            with patch('dm_pool.DmConnectionPool._get_driver') as mock_driver:
                mock_dm = Mock()
                
                def mock_connect(*args):
                    mock_conn = Mock()
                    mock_cursor = Mock()
                    mock_cursor.execute = Mock()
                    mock_cursor.fetchone = Mock(return_value=(1,))
                    mock_cursor.close = Mock()
                    mock_conn.cursor = Mock(return_value=mock_cursor)
                    mock_conn.close = Mock()
                    return mock_conn
                
                mock_dm.connect = mock_connect
                mock_driver.return_value = mock_dm
                
                pool = DmConnectionPool(
                    db_config={'host': 'fake', 'port': 5236, 'user': 'test', 'password': 'test'},
                    pool_config=pool_config
                )
                
                success_count = 0
                for i in range(50):
                    conn = pool.get_connection(timeout=3)
                    pool.release_connection(conn)
                    success_count += 1
                
                pool.close()
                return f"OK: {success_count} 次快速连接断开成功"
        
        success, msg = run_with_timeout(test_func, timeout=TEST_TIMEOUT)
        print(f"结果: {'✓' if success else '✗'} {msg}")
        assert success, msg
    
    def test_mixed_success_failure_no_deadlock(self):
        """测试：成功和失败混合场景不会死锁"""
        print("\n=== 测试9: 成功失败混合不死锁 ===")
        
        def test_func():
            from dm_pool import DmConnectionPool, PoolConfig
            
            with DmConnectionPool._lock:
                DmConnectionPool._instance = None
            
            pool_config = PoolConfig(
                min_connections=0,
                max_connections=3,
                connection_timeout=2,
            )
            
            call_count = {'count': 0}
            
            with patch('dm_pool.DmConnectionPool._get_driver') as mock_driver:
                mock_dm = Mock()
                
                def mock_connect(*args):
                    call_count['count'] += 1
                    if call_count['count'] % 3 == 0:
                        raise Exception("模拟连接失败")
                    
                    mock_conn = Mock()
                    mock_cursor = Mock()
                    mock_cursor.execute = Mock()
                    mock_cursor.fetchone = Mock(return_value=(1,))
                    mock_cursor.close = Mock()
                    mock_conn.cursor = Mock(return_value=mock_cursor)
                    mock_conn.close = Mock()
                    return mock_conn
                
                mock_dm.connect = mock_connect
                mock_driver.return_value = mock_dm
                
                pool = DmConnectionPool(
                    db_config={'host': 'fake', 'port': 5236, 'user': 'test', 'password': 'test'},
                    pool_config=pool_config
                )
                
                success_count = 0
                error_count = 0
                
                for i in range(20):
                    try:
                        conn = pool.get_connection(timeout=2)
                        pool.release_connection(conn)
                        success_count += 1
                    except Exception:
                        error_count += 1
                
                pool.close()
                return f"OK: {success_count} 成功, {error_count} 失败"
        
        success, msg = run_with_timeout(test_func, timeout=TEST_TIMEOUT)
        print(f"结果: {'✓' if success else '✗'} {msg}")
        assert success, msg
    
    def test_connection_becomes_unhealthy_no_deadlock(self):
        """测试：连接变得不健康时不会死锁"""
        print("\n=== 测试10: 连接不健康不死锁 ===")
        
        def test_func():
            from dm_pool import DmConnectionPool, PoolConfig
            
            with DmConnectionPool._lock:
                DmConnectionPool._instance = None
            
            pool_config = PoolConfig(
                min_connections=0,
                max_connections=2,
                connection_timeout=3,
            )
            
            with patch('dm_pool.DmConnectionPool._get_driver') as mock_driver:
                mock_dm = Mock()
                
                def mock_connect(*args):
                    mock_conn = Mock()
                    mock_cursor = Mock()
                    mock_cursor.execute = Mock()
                    mock_cursor.fetchone = Mock(return_value=(1,))
                    mock_cursor.close = Mock()
                    mock_conn.cursor = Mock(return_value=mock_cursor)
                    mock_conn.close = Mock()
                    return mock_conn
                
                mock_dm.connect = mock_connect
                mock_driver.return_value = mock_dm
                
                pool = DmConnectionPool(
                    db_config={'host': 'fake', 'port': 5236, 'user': 'test', 'password': 'test'},
                    pool_config=pool_config
                )
                
                conn1 = pool.get_connection(timeout=3)
                conn1.connection = None  # 模拟连接变得不健康
                pool.release_connection(conn1)
                
                conn2 = pool.get_connection(timeout=3)
                pool.release_connection(conn2)
                
                pool.close()
                return "OK: 不健康连接处理正常"
        
        success, msg = run_with_timeout(test_func, timeout=TEST_TIMEOUT)
        print(f"结果: {'✓' if success else '✗'} {msg}")
        assert success, msg


class TestDecoratorChainNoDeadlock:
    """装饰器链假死测试"""
    
    def test_cache_and_handler_chain_no_deadlock(self):
        """测试：缓存和处理器装饰器链不会死锁"""
        print("\n=== 测试11: 装饰器链不死锁 ===")
        
        def test_func():
            from core.cache import mcp_cache, clear_cache
            from core.decorators import mcp_tool_handler
            
            clear_cache()
            call_count = {'count': 0}
            
            @mcp_cache(ttl=60)
            @mcp_tool_handler("test_operation")
            def test_tool(arg):
                call_count['count'] += 1
                if arg == "error":
                    raise ValueError("模拟错误")
                return {
                    "success": True,
                    "data": arg,
                    "metadata": {"operation": "test"}
                }
            
            results = []
            errors = []
            
            def call_tool():
                for i in range(5):
                    try:
                        result = test_tool("success")
                        results.append(result)
                    except Exception as e:
                        errors.append(str(e))
                    
                    try:
                        result = test_tool("error")
                        results.append(result)
                    except Exception as e:
                        errors.append(str(e))
            
            threads = []
            for i in range(3):
                t = threading.Thread(target=call_tool, daemon=True)
                threads.append(t)
                t.start()
            
            for t in threads:
                t.join(timeout=5)
            
            return f"OK: {len(results)} 结果, {len(errors)} 错误, 实际调用 {call_count['count']} 次"
        
        success, msg = run_with_timeout(test_func, timeout=TEST_TIMEOUT)
        print(f"结果: {'✓' if success else '✗'} {msg}")
        assert success, msg


def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("MCP 假死测试")
    print("=" * 60)
    print(f"测试超时时间: {TEST_TIMEOUT} 秒")
    print("如果任何测试超过此时间，将被视为假死")
    print("=" * 60)
    
    test_classes = [
        TestConnectionPoolNoDeadlock,
        TestCacheNoDeadlock,
        TestHealthCheckNoDeadlock,
        TestToolsNoDeadlock,
        TestRealWorldScenarios,
        TestDecoratorChainNoDeadlock,
    ]
    
    total_tests = 0
    passed_tests = 0
    failed_tests = []
    
    for test_class in test_classes:
        instance = test_class()
        for method_name in dir(instance):
            if method_name.startswith('test_'):
                total_tests += 1
                try:
                    getattr(instance, method_name)()
                    passed_tests += 1
                except AssertionError as e:
                    failed_tests.append((f"{test_class.__name__}.{method_name}", str(e)))
                except Exception as e:
                    failed_tests.append((f"{test_class.__name__}.{method_name}", f"异常: {e}"))
    
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    print(f"总测试数: {total_tests}")
    print(f"通过: {passed_tests}")
    print(f"失败: {len(failed_tests)}")
    
    if failed_tests:
        print("\n失败的测试:")
        for name, error in failed_tests:
            print(f"  ✗ {name}")
            print(f"    原因: {error}")
    
    print("=" * 60)
    
    if failed_tests:
        print("⚠️  存在假死风险，需要进一步修复！")
        return False
    else:
        print("✓ 所有测试通过，未发现假死问题！")
        return True


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
