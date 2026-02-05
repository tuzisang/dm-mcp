"""
连接池基础测试
"""

import unittest
import time
from unittest.mock import Mock


class TestPoolConfig(unittest.TestCase):
    """测试连接池配置"""
    
    def test_default_config(self):
        from db import PoolConfig
        config = PoolConfig()
        self.assertEqual(config.min_connections, 2)
        self.assertEqual(config.max_connections, 10)
        self.assertEqual(config.connection_timeout, 30)


class TestPooledConnection(unittest.TestCase):
    """测试池化连接"""
    
    def test_pooled_connection_creation(self):
        from db import PooledConnection
        mock_conn = Mock()
        pooled = PooledConnection(mock_conn, None)
        self.assertEqual(pooled.connection, mock_conn)
        self.assertFalse(pooled.in_use)
    
    def test_is_expired(self):
        from db import PooledConnection
        pooled = PooledConnection(Mock(), None)
        self.assertFalse(pooled.is_expired(300))
        pooled.last_used_at = time.time() - 400
        self.assertTrue(pooled.is_expired(300))


class TestDmConnectionPool(unittest.TestCase):
    """测试连接池"""
    
    def setUp(self):
        from db import DmConnectionPool
        DmConnectionPool._instance = None
    
    def tearDown(self):
        from db import close_pool, DmConnectionPool
        try:
            close_pool()
        except:
            pass
        DmConnectionPool._instance = None
    
    def test_singleton_pattern(self):
        from db import DmConnectionPool, PoolConfig
        db_config = {'host': 'localhost', 'port': 5236, 'user': 'test', 'password': 'test'}
        pool_config = PoolConfig(min_connections=1, max_connections=5)
        pool1 = DmConnectionPool(db_config, pool_config)
        pool2 = DmConnectionPool()
        self.assertIs(pool1, pool2)
    
    def test_get_stats(self):
        from db import DmConnectionPool, PoolConfig
        db_config = {'host': 'localhost', 'port': 5236, 'user': 'test', 'password': 'test'}
        pool_config = PoolConfig(min_connections=2, max_connections=10)
        pool = DmConnectionPool(db_config, pool_config)
        stats = pool.get_stats()
        self.assertIn('total_connections', stats)
        self.assertEqual(stats['max_connections'], 10)


if __name__ == '__main__':
    unittest.main(verbosity=2)
