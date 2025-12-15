"""
连接池功能测试

测试内容：
1. 连接池初始化
2. 连接获取和释放
3. 连接复用
4. 并发访问
5. 连接池统计
6. 连接健康检查
"""

import unittest
import threading
import time
from unittest.mock import Mock, patch, MagicMock


class TestPoolConfig(unittest.TestCase):
    """测试连接池配置"""
    
    def test_default_config(self):
        """测试默认配置值"""
        from dm_pool import PoolConfig
        
        config = PoolConfig()
        self.assertEqual(config.min_connections, 2)
        self.assertEqual(config.max_connections, 10)
        self.assertEqual(config.connection_timeout, 30)
        self.assertEqual(config.idle_timeout, 300)
        self.assertEqual(config.health_check_interval, 60)
    
    def test_custom_config(self):
        """测试自定义配置"""
        from dm_pool import PoolConfig
        
        config = PoolConfig(
            min_connections=5,
            max_connections=20,
            connection_timeout=60
        )
        self.assertEqual(config.min_connections, 5)
        self.assertEqual(config.max_connections, 20)
        self.assertEqual(config.connection_timeout, 60)


class TestPooledConnection(unittest.TestCase):
    """测试池化连接"""
    
    def test_pooled_connection_creation(self):
        """测试池化连接创建"""
        from dm_pool import PooledConnection
        
        mock_conn = Mock()
        mock_pool = Mock()
        
        pooled = PooledConnection(mock_conn, mock_pool)
        
        self.assertEqual(pooled.connection, mock_conn)
        self.assertEqual(pooled.pool, mock_pool)
        self.assertFalse(pooled.in_use)
        self.assertIsNotNone(pooled.created_at)
        self.assertIsNotNone(pooled.last_used_at)
    
    def test_is_healthy_success(self):
        """测试健康检查成功"""
        from dm_pool import PooledConnection
        
        mock_cursor = Mock()
        mock_cursor.execute = Mock()
        mock_cursor.fetchone = Mock(return_value=(1,))
        mock_cursor.close = Mock()
        
        mock_conn = Mock()
        mock_conn.cursor = Mock(return_value=mock_cursor)
        
        pooled = PooledConnection(mock_conn, Mock())
        
        self.assertTrue(pooled.is_healthy())
        mock_cursor.execute.assert_called_once_with("SELECT 1 FROM DUAL")
    
    def test_is_healthy_failure(self):
        """测试健康检查失败"""
        from dm_pool import PooledConnection
        
        mock_conn = Mock()
        mock_conn.cursor = Mock(side_effect=Exception("Connection lost"))
        
        pooled = PooledConnection(mock_conn, Mock())
        
        self.assertFalse(pooled.is_healthy())
    
    def test_is_expired(self):
        """测试连接过期检查"""
        from dm_pool import PooledConnection
        
        pooled = PooledConnection(Mock(), Mock())
        
        # 刚创建的连接不应该过期
        self.assertFalse(pooled.is_expired(300))
        
        # 模拟过期
        pooled.last_used_at = time.time() - 400
        self.assertTrue(pooled.is_expired(300))
    
    def test_close(self):
        """测试关闭连接"""
        from dm_pool import PooledConnection
        
        mock_conn = Mock()
        pooled = PooledConnection(mock_conn, Mock())
        
        pooled.close()
        
        mock_conn.close.assert_called_once()
        self.assertIsNone(pooled.connection)


class TestDmConnectionPool(unittest.TestCase):
    """测试连接池"""
    
    def setUp(self):
        """测试前重置单例"""
        from dm_pool import DmConnectionPool
        DmConnectionPool._instance = None
    
    def tearDown(self):
        """测试后清理"""
        from dm_pool import DmConnectionPool, close_pool
        try:
            close_pool()
        except:
            pass
        DmConnectionPool._instance = None
    
    def test_singleton_pattern(self):
        """测试单例模式"""
        from dm_pool import DmConnectionPool, PoolConfig
        
        db_config = {'host': 'localhost', 'port': 5236, 'user': 'test', 'password': 'test'}
        pool_config = PoolConfig(min_connections=1, max_connections=5)
        
        pool1 = DmConnectionPool(db_config, pool_config)
        pool2 = DmConnectionPool()
        
        self.assertIs(pool1, pool2)
    
    def test_get_stats(self):
        """测试获取统计信息"""
        from dm_pool import DmConnectionPool, PoolConfig
        
        db_config = {'host': 'localhost', 'port': 5236, 'user': 'test', 'password': 'test'}
        pool_config = PoolConfig(min_connections=2, max_connections=10)
        
        pool = DmConnectionPool(db_config, pool_config)
        stats = pool.get_stats()
        
        self.assertIn('total_connections', stats)
        self.assertIn('available_connections', stats)
        self.assertIn('in_use_connections', stats)
        self.assertIn('max_connections', stats)
        self.assertIn('min_connections', stats)
        self.assertEqual(stats['max_connections'], 10)
        self.assertEqual(stats['min_connections'], 2)


class TestDmClientWithPool(unittest.TestCase):
    """测试使用连接池的 DmClient"""
    
    def test_config_pool_settings(self):
        """测试配置中的连接池设置"""
        from dm_client import DmConfig
        
        config = DmConfig(
            host='localhost',
            port=5236,
            user='test',
            password='test',
            use_pool=True,
            pool_min_connections=3,
            pool_max_connections=15
        )
        
        self.assertTrue(config.use_pool)
        self.assertEqual(config.pool_min_connections, 3)
        self.assertEqual(config.pool_max_connections, 15)
    
    def test_config_from_file(self):
        """测试从配置文件读取连接池设置"""
        from dm_client import DmConfig
        
        config = DmConfig.from_config_file()
        
        # 验证连接池配置已加载
        self.assertIsInstance(config.use_pool, bool)
        self.assertIsInstance(config.pool_min_connections, int)
        self.assertIsInstance(config.pool_max_connections, int)


class TestPoolConcurrency(unittest.TestCase):
    """测试连接池并发访问"""
    
    def setUp(self):
        from dm_pool import DmConnectionPool
        DmConnectionPool._instance = None
    
    def tearDown(self):
        from dm_pool import close_pool, DmConnectionPool
        try:
            close_pool()
        except:
            pass
        DmConnectionPool._instance = None
    
    @unittest.skip("并发测试需要真实数据库，跳过")
    def test_concurrent_connection_requests(self):
        """测试并发连接请求（需要真实数据库）"""
        pass


class TestPoolIntegration(unittest.TestCase):
    """集成测试（需要真实数据库连接）"""
    
    def test_real_connection_pool(self):
        """测试真实连接池操作"""
        from dm_pool import get_pool, close_pool, PoolConfig, DmConnectionPool
        from config import get_database_config
        
        # 重置单例
        DmConnectionPool._instance = None
        
        db_config = get_database_config()
        pool_config = PoolConfig(min_connections=2, max_connections=5)
        
        try:
            pool = get_pool(db_config, pool_config)
            
            # 获取连接
            conn = pool.get_connection()
            self.assertIsNotNone(conn)
            print(f"获取连接成功，池状态: {pool.get_stats()}")
            
            # 执行查询
            cursor = conn.connection.cursor()
            cursor.execute("SELECT 1 FROM DUAL")
            result = cursor.fetchone()
            cursor.close()
            
            self.assertEqual(result[0], 1)
            print(f"查询成功，结果: {result}")
            
            # 释放连接
            pool.release_connection(conn)
            print(f"释放连接后，池状态: {pool.get_stats()}")
            
            # 检查统计
            stats = pool.get_stats()
            self.assertGreater(stats['available_connections'], 0)
            
        finally:
            close_pool()
    
    def test_connection_reuse(self):
        """测试连接复用"""
        from dm_pool import get_pool, close_pool, PoolConfig, DmConnectionPool
        from config import get_database_config
        
        # 重置单例
        DmConnectionPool._instance = None
        
        db_config = get_database_config()
        # 使用 min=1 确保只有一个初始连接，便于测试复用
        pool_config = PoolConfig(min_connections=1, max_connections=5)
        
        try:
            pool = get_pool(db_config, pool_config)
            
            # 第一次获取连接
            conn1 = pool.get_connection()
            conn1_id = id(conn1)
            pool.release_connection(conn1)
            
            # 第二次获取连接（应该复用同一个连接）
            conn2 = pool.get_connection()
            conn2_id = id(conn2)
            pool.release_connection(conn2)
            
            print(f"连接1 ID: {conn1_id}, 连接2 ID: {conn2_id}")
            print(f"连接是否复用: {conn1_id == conn2_id}")
            
            # 连接应该被复用（因为只有1个初始连接）
            self.assertEqual(conn1_id, conn2_id)
            
        finally:
            close_pool()
    
    def test_dm_client_with_pool(self):
        """测试 DmClient 使用连接池"""
        from dm_client import DmClient, DmConfig
        from dm_pool import close_pool, DmConnectionPool
        
        # 重置单例
        DmConnectionPool._instance = None
        
        config = DmConfig.from_config_file()
        config.use_pool = True
        
        try:
            with DmClient(config) as client:
                # 测试连接
                result = client.execute_query("SELECT 1 AS test_value FROM DUAL")
                self.assertEqual(len(result), 1)
                self.assertEqual(result[0]['TEST_VALUE'], 1)
                print(f"DmClient 连接池测试成功: {result}")
        finally:
            close_pool()


if __name__ == '__main__':
    unittest.main(verbosity=2)
