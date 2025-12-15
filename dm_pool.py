"""
达梦数据库连接池模块

基于线程安全的连接池实现，支持：
- 连接复用
- 自动重连
- 连接健康检查
- 最大/最小连接数控制
"""

import threading
import time
import queue
from typing import Optional, Any
from dataclasses import dataclass


@dataclass
class PoolConfig:
    """连接池配置"""
    min_connections: int = 2      # 最小连接数
    max_connections: int = 10     # 最大连接数
    connection_timeout: int = 30  # 获取连接超时（秒）
    idle_timeout: int = 300       # 空闲连接超时（秒）
    health_check_interval: int = 60  # 健康检查间隔（秒）


class PooledConnection:
    """池化连接包装器"""
    
    def __init__(self, connection, pool: 'DmConnectionPool', created_at: float = None):
        self.connection = connection
        self.pool = pool
        self.created_at = created_at or time.time()
        self.last_used_at = time.time()
        self.in_use = False
    
    def is_healthy(self) -> bool:
        """检查连接是否健康"""
        if self.connection is None:
            return False
        try:
            cursor = self.connection.cursor()
            cursor.execute("SELECT 1 FROM DUAL")
            cursor.fetchone()
            cursor.close()
            return True
        except Exception:
            return False
    
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
    """达梦数据库连接池"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls, *args, **kwargs):
        """单例模式"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, db_config: dict = None, pool_config: PoolConfig = None):
        """初始化连接池
        
        Args:
            db_config: 数据库配置 {host, port, user, password, schema}
            pool_config: 连接池配置
        """
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
        
        # 健康检查线程
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
                raise ImportError("未安装 dmPython 驱动，请运行: pip install dmPython")
        return self._driver
    
    def _create_connection(self) -> PooledConnection:
        """创建新的数据库连接"""
        driver = self._get_driver()
        
        host = self.db_config.get('host', 'localhost')
        port = self.db_config.get('port', 5236)
        user = self.db_config.get('user', 'SYSDBA')
        password = self.db_config.get('password', 'SYSDBA')
        
        conn = driver.connect(user, password, host, port)
        pooled_conn = PooledConnection(conn, self)
        
        with self._pool_lock:
            self._connection_count += 1
            self._all_connections.append(pooled_conn)
        
        print(f"创建新连接，当前连接数: {self._connection_count}")
        return pooled_conn
    
    def initialize(self):
        """初始化连接池，创建最小连接数"""
        if self._closed:
            raise RuntimeError("连接池已关闭")
            
        print(f"初始化连接池，创建 {self.pool_config.min_connections} 个初始连接...")
        
        for _ in range(self.pool_config.min_connections):
            try:
                conn = self._create_connection()
                self._pool.put(conn, block=False)
            except Exception as e:
                print(f"创建初始连接失败: {e}")
        
        # 启动健康检查线程
        self._start_health_check()
        
        print(f"连接池初始化完成，当前可用连接: {self._pool.qsize()}")
    
    def _start_health_check(self):
        """启动健康检查线程"""
        if self._health_check_thread is not None:
            return
            
        self._stop_health_check.clear()
        self._health_check_thread = threading.Thread(
            target=self._health_check_worker,
            daemon=True,
            name="pool-health-check"
        )
        self._health_check_thread.start()
    
    def _health_check_worker(self):
        """健康检查工作线程"""
        # 首次启动时先等待，避免立即检查刚创建的连接
        self._stop_health_check.wait(self.pool_config.health_check_interval)
        
        while not self._stop_health_check.is_set():
            try:
                self._check_and_clean_connections()
            except Exception as e:
                print(f"健康检查异常: {e}")
            
            # 等待下次检查
            self._stop_health_check.wait(self.pool_config.health_check_interval)
    
    def _check_and_clean_connections(self):
        """检查并清理无效连接"""
        connections_to_check = []
        
        # 从池中取出所有连接进行检查
        while True:
            try:
                conn = self._pool.get_nowait()
                connections_to_check.append(conn)
            except queue.Empty:
                break
        
        valid_connections = []
        for conn in connections_to_check:
            if conn.in_use:
                valid_connections.append(conn)
                continue
                
            # 检查是否过期
            if conn.is_expired(self.pool_config.idle_timeout):
                # 保持最小连接数
                if self._connection_count > self.pool_config.min_connections:
                    print(f"关闭过期连接，空闲时间: {time.time() - conn.last_used_at:.0f}秒")
                    self._remove_connection(conn)
                    continue
            
            # 检查连接健康
            if not conn.is_healthy():
                print("关闭不健康的连接")
                self._remove_connection(conn)
                continue
            
            valid_connections.append(conn)
        
        # 将有效连接放回池中
        for conn in valid_connections:
            try:
                self._pool.put(conn, block=False)
            except queue.Full:
                self._remove_connection(conn)
        
        # 补充连接到最小数量
        while self._connection_count < self.pool_config.min_connections:
            try:
                new_conn = self._create_connection()
                self._pool.put(new_conn, block=False)
            except Exception as e:
                print(f"补充连接失败: {e}")
                break
    
    def _remove_connection(self, conn: PooledConnection):
        """移除连接"""
        conn.close()
        with self._pool_lock:
            if conn in self._all_connections:
                self._all_connections.remove(conn)
            self._connection_count = max(0, self._connection_count - 1)
    
    def get_connection(self, timeout: int = None) -> PooledConnection:
        """从池中获取连接
        
        Args:
            timeout: 获取超时时间（秒），None 使用默认配置
            
        Returns:
            PooledConnection: 池化连接
            
        Raises:
            TimeoutError: 获取连接超时
            RuntimeError: 连接池已关闭
        """
        if self._closed:
            raise RuntimeError("连接池已关闭")
            
        timeout = timeout or self.pool_config.connection_timeout
        start_time = time.time()
        
        while True:
            elapsed = time.time() - start_time
            if elapsed >= timeout:
                raise TimeoutError(f"获取连接超时（{timeout}秒）")
            
            try:
                # 尝试从池中获取
                remaining = max(0.1, timeout - elapsed)
                conn = self._pool.get(timeout=min(1, remaining))
                
                # 检查连接是否有效
                if conn.is_healthy():
                    conn.in_use = True
                    conn.last_used_at = time.time()
                    return conn
                else:
                    # 连接无效，移除并继续
                    self._remove_connection(conn)
                    continue
                    
            except queue.Empty:
                # 池为空，尝试创建新连接
                with self._pool_lock:
                    if self._connection_count < self.pool_config.max_connections:
                        try:
                            conn = self._create_connection()
                            conn.in_use = True
                            return conn
                        except Exception as e:
                            print(f"创建连接失败: {e}")
                            continue
                
                # 已达最大连接数，等待
                time.sleep(0.1)
    
    def release_connection(self, conn: PooledConnection):
        """释放连接回池
        
        Args:
            conn: 要释放的连接
        """
        if conn is None:
            return
            
        conn.in_use = False
        conn.last_used_at = time.time()
        
        if self._closed:
            self._remove_connection(conn)
            return
        
        # 检查连接是否健康
        if not conn.is_healthy():
            self._remove_connection(conn)
            return
        
        try:
            self._pool.put(conn, block=False)
        except queue.Full:
            # 池已满，关闭连接
            self._remove_connection(conn)
    
    def close(self):
        """关闭连接池"""
        if self._closed:
            return
            
        self._closed = True
        print("正在关闭连接池...")
        
        # 停止健康检查
        self._stop_health_check.set()
        if self._health_check_thread:
            self._health_check_thread.join(timeout=2)
        
        # 关闭所有连接
        with self._pool_lock:
            for conn in self._all_connections:
                conn.close()
            self._all_connections.clear()
            self._connection_count = 0
        
        # 清空队列
        while True:
            try:
                self._pool.get_nowait()
            except queue.Empty:
                break
        
        # 重置单例
        DmConnectionPool._instance = None
        
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
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class PooledDmClient:
    """使用连接池的达梦数据库客户端"""
    
    def __init__(self, pool: DmConnectionPool):
        self.pool = pool
        self._conn: Optional[PooledConnection] = None
    
    def __enter__(self):
        self._conn = self.pool.get_connection()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._conn:
            self.pool.release_connection(self._conn)
            self._conn = None
    
    @property
    def connection(self):
        """获取底层连接"""
        if self._conn is None:
            raise RuntimeError("未获取连接，请使用 with 语句")
        return self._conn.connection
    
    def execute_query(self, sql: str) -> list:
        """执行查询"""
        cursor = self.connection.cursor()
        try:
            cursor.execute(sql)
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            rows = cursor.fetchall()
            return [dict(zip(columns, row)) for row in rows]
        finally:
            cursor.close()
    
    def execute_update(self, sql: str) -> int:
        """执行更新"""
        cursor = self.connection.cursor()
        try:
            cursor.execute(sql)
            affected = cursor.rowcount
            self.connection.commit()
            return affected
        except Exception:
            self.connection.rollback()
            raise
        finally:
            cursor.close()


# 全局连接池实例
_global_pool: Optional[DmConnectionPool] = None
_global_pool_lock = threading.Lock()


def get_pool(db_config: dict = None, pool_config: PoolConfig = None) -> DmConnectionPool:
    """获取全局连接池实例
    
    Args:
        db_config: 数据库配置（首次调用时必需）
        pool_config: 连接池配置（可选）
        
    Returns:
        DmConnectionPool: 连接池实例
    """
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
