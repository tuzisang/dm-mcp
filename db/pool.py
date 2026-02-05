"""
达梦数据库连接池模块

支持：连接复用、自动重连、健康检查、最大/最小连接数控制
"""

import threading
import time
import queue
from typing import Optional

from .config import PoolConfig


class PooledConnection:
    """池化连接包装器"""
    
    def __init__(self, connection, pool: 'DmConnectionPool', created_at: float = None):
        self.connection = connection
        self.pool = pool
        self.created_at = created_at or time.time()
        self.last_used_at = time.time()
        self.in_use = False
    
    def is_healthy(self, timeout: int = 5) -> bool:
        """检查连接是否健康"""
        if self.connection is None:
            return False
        
        result = {'healthy': False}
        check_done = threading.Event()
        
        def check_worker():
            try:
                cursor = self.connection.cursor()
                cursor.execute("SELECT 1 FROM DUAL")
                cursor.fetchone()
                cursor.close()
                result['healthy'] = True
            except Exception:
                result['healthy'] = False
            finally:
                check_done.set()
        
        check_thread = threading.Thread(target=check_worker, daemon=True)
        check_thread.start()
        
        if not check_done.wait(timeout=timeout):
            return False
        
        return result['healthy']
    
    def is_expired(self, idle_timeout: int) -> bool:
        """检查连接是否过期"""
        return time.time() - self.last_used_at > idle_timeout
    
    def close(self):
        """关闭底层连接"""
        if self.connection:
            try:
                self.connection.close()
            except Exception:
                pass
            self.connection = None


class DmConnectionPool:
    """达梦数据库连接池（单例模式）"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                instance = super().__new__(cls)
                instance._initialized = False
                cls._instance = instance
        return cls._instance
    
    def __init__(self, db_config: dict = None, pool_config: PoolConfig = None):
        if self._initialized:
            return
            
        self._initialized = True
        self.db_config = db_config or {}
        self.pool_config = pool_config or PoolConfig()
        
        self._pool: queue.Queue = queue.Queue(maxsize=self.pool_config.max_connections)
        self._all_connections: list = []
        self._pool_lock = threading.Lock()
        self._connection_count = 0
        self._driver = None
        self._closed = False
        
        self._health_check_thread = None
        self._stop_health_check = threading.Event()
        
        print(f"连接池初始化: min={self.pool_config.min_connections}, max={self.pool_config.max_connections}")
    
    def _get_driver(self):
        """获取达梦数据库驱动"""
        if self._driver is None:
            try:
                import dmPython
                self._driver = dmPython
            except ImportError:
                raise ImportError("未安装 dmPython 驱动")
        return self._driver
    
    def initialize(self):
        """初始化连接池"""
        if self._closed:
            raise RuntimeError("连接池已关闭")
        self._start_health_check()
    
    def _start_health_check(self):
        """启动健康检查线程"""
        if self._health_check_thread is not None:
            return
        self._stop_health_check.clear()
        self._health_check_thread = threading.Thread(
            target=self._health_check_worker, daemon=True, name="pool-health-check"
        )
        self._health_check_thread.start()
    
    def _health_check_worker(self):
        """健康检查工作线程"""
        self._stop_health_check.wait(self.pool_config.health_check_interval)
        while not self._stop_health_check.is_set():
            try:
                self._check_and_clean_connections()
            except Exception as e:
                print(f"健康检查异常: {e}")
            self._stop_health_check.wait(self.pool_config.health_check_interval)
    
    def _check_and_clean_connections(self):
        """检查并清理无效连接"""
        connections_to_check = []
        max_check = self.pool_config.max_connections
        checked = 0
        
        while checked < max_check:
            try:
                conn = self._pool.get_nowait()
                connections_to_check.append(conn)
                checked += 1
            except queue.Empty:
                break
        
        valid_connections = []
        for conn in connections_to_check:
            if conn.in_use:
                valid_connections.append(conn)
                continue
            if conn.is_expired(self.pool_config.idle_timeout):
                if self._connection_count > self.pool_config.min_connections:
                    self._remove_connection(conn)
                    continue
            if not conn.is_healthy(timeout=3):
                self._remove_connection(conn)
                continue
            valid_connections.append(conn)
        
        for conn in valid_connections:
            try:
                self._pool.put(conn, block=False)
            except queue.Full:
                self._remove_connection(conn)
    
    def _remove_connection(self, conn: PooledConnection):
        """移除连接"""
        conn.close()
        with self._pool_lock:
            if conn in self._all_connections:
                self._all_connections.remove(conn)
            self._connection_count = max(0, self._connection_count - 1)
    
    def get_connection(self, timeout: int = None) -> PooledConnection:
        """从池中获取连接"""
        if self._closed:
            raise RuntimeError("连接池已关闭")
            
        timeout = timeout or self.pool_config.connection_timeout
        start_time = time.time()
        max_attempts = int(timeout / 0.1) + 1
        attempt = 0
        
        while attempt < max_attempts:
            attempt += 1
            if time.time() - start_time >= timeout:
                raise TimeoutError(f"获取连接超时（{timeout}秒）")
            
            try:
                conn = self._pool.get_nowait()
                if conn.connection is not None:
                    conn.in_use = True
                    conn.last_used_at = time.time()
                    return conn
                else:
                    self._remove_connection(conn)
                    continue
            except queue.Empty:
                pass
            
            should_create = False
            with self._pool_lock:
                if self._connection_count < self.pool_config.max_connections:
                    should_create = True
                    self._connection_count += 1
            
            if should_create:
                try:
                    conn = self._create_connection_internal()
                    conn.in_use = True
                    return conn
                except Exception as e:
                    with self._pool_lock:
                        self._connection_count = max(0, self._connection_count - 1)
                    if isinstance(e, TimeoutError):
                        raise e
                    time.sleep(0.1)
                    continue
            
            time.sleep(0.1)
        
        raise TimeoutError(f"获取连接超时")
    
    def _create_connection_internal(self) -> PooledConnection:
        """创建连接"""
        driver = self._get_driver()
        host = self.db_config.get('host', 'localhost')
        port = self.db_config.get('port', 5236)
        user = self.db_config.get('user', 'SYSDBA')
        password = self.db_config.get('password', 'SYSDBA')
        connect_timeout = self.pool_config.connection_timeout
        
        conn_result = {'conn': None, 'error': None}
        connect_done = threading.Event()
        
        def connect_worker():
            try:
                conn_result['conn'] = driver.connect(user, password, host, port)
            except Exception as e:
                conn_result['error'] = e
            finally:
                connect_done.set()
        
        connect_thread = threading.Thread(target=connect_worker, daemon=True)
        connect_thread.start()
        
        if not connect_done.wait(timeout=connect_timeout):
            raise TimeoutError(f"创建数据库连接超时（{connect_timeout}秒）")
        
        if conn_result['error']:
            raise conn_result['error']
        
        if conn_result['conn'] is None:
            raise RuntimeError("创建连接失败")
        
        pooled_conn = PooledConnection(conn_result['conn'], self)
        with self._pool_lock:
            self._all_connections.append(pooled_conn)
        return pooled_conn
    
    def release_connection(self, conn: PooledConnection):
        """释放连接回池"""
        if conn is None:
            return
        conn.in_use = False
        conn.last_used_at = time.time()
        
        if self._closed:
            self._remove_connection(conn)
            return
        
        try:
            self._pool.put(conn, block=False)
        except queue.Full:
            self._remove_connection(conn)
    
    def close(self):
        """关闭连接池"""
        if self._closed:
            return
        self._closed = True
        print("正在关闭连接池...")
        
        self._stop_health_check.set()
        if self._health_check_thread:
            self._health_check_thread.join(timeout=2)
        
        with self._pool_lock:
            for conn in self._all_connections:
                conn.close()
            self._all_connections.clear()
            self._connection_count = 0
        
        while True:
            try:
                self._pool.get_nowait()
            except queue.Empty:
                break
        
        with DmConnectionPool._lock:
            DmConnectionPool._instance = None
        self._initialized = False
        print("连接池已关闭")
    
    def get_stats(self) -> dict:
        """获取连接池统计信息"""
        return {
            "total_connections": self._connection_count,
            "available_connections": self._pool.qsize(),
            "in_use_connections": self._connection_count - self._pool.qsize(),
            "max_connections": self.pool_config.max_connections,
            "min_connections": self.pool_config.min_connections,
            "closed": self._closed
        }


# 全局连接池
_global_pool: Optional[DmConnectionPool] = None
_global_pool_lock = threading.Lock()


def get_pool(db_config: dict = None, pool_config: PoolConfig = None) -> DmConnectionPool:
    """获取全局连接池实例"""
    global _global_pool
    with _global_pool_lock:
        if _global_pool is None or _global_pool._closed:
            if db_config is None:
                raise ValueError("首次获取连接池需要提供数据库配置")
            _global_pool = DmConnectionPool(db_config, pool_config)
            _global_pool.initialize()
        return _global_pool


def close_pool():
    """关闭全局连接池"""
    global _global_pool
    with _global_pool_lock:
        if _global_pool:
            _global_pool.close()
            _global_pool = None
