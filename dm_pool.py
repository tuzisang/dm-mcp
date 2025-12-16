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
    
    def is_healthy(self, timeout: int = 5) -> bool:
        """检查连接是否健康（带超时控制）"""
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
        
        # 等待检查完成或超时
        if not check_done.wait(timeout=timeout):
            return False  # 超时视为不健康
        
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
    """达梦数据库连接池"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls, *args, **kwargs):
        """单例模式"""
        with cls._lock:
            if cls._instance is None:
                instance = super().__new__(cls)
                instance._initialized = False
                cls._instance = instance
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
        """创建新的数据库连接（带超时控制，会增加连接计数）
        
        注意：此方法会增加连接计数，调用者不应再次增加计数
        """
        should_increment = False
        with self._pool_lock:
            # 只有在未达到最大连接数时才增加计数
            if self._connection_count < self.pool_config.max_connections:
                self._connection_count += 1
                should_increment = True
            else:
                raise RuntimeError(f"已达最大连接数 {self.pool_config.max_connections}")
        
        try:
            conn = self._create_connection_internal()
            print(f"创建新连接，当前连接数: {self._connection_count}")
            return conn
        except Exception as e:
            if should_increment:
                with self._pool_lock:
                    self._connection_count = max(0, self._connection_count - 1)
            raise e
    
    def initialize(self):
        """初始化连接池（懒加载模式，不阻塞）"""
        if self._closed:
            raise RuntimeError("连接池已关闭")
            
        print(f"连接池初始化: min={self.pool_config.min_connections}, max={self.pool_config.max_connections}")
        print("使用懒加载模式，连接将在首次使用时创建")
        
        # 不在初始化时创建连接，改为懒加载
        # 这样可以避免数据库不可达时阻塞
        
        # 启动健康检查线程
        self._start_health_check()
        
        print(f"连接池初始化完成")
    
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
        """检查并清理无效连接（带超时保护）"""
        connections_to_check = []
        
        # 从池中取出所有连接进行检查，限制最大数量防止阻塞
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
                
            # 检查是否过期
            if conn.is_expired(self.pool_config.idle_timeout):
                # 保持最小连接数
                if self._connection_count > self.pool_config.min_connections:
                    print(f"关闭过期连接，空闲时间: {time.time() - conn.last_used_at:.0f}秒")
                    self._remove_connection(conn)
                    continue
            
            # 检查连接健康（使用较短的超时时间避免阻塞）
            if not conn.is_healthy(timeout=3):
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
        
        # 补充连接到最小数量（限制尝试次数防止无限循环）
        attempts = 0
        max_attempts = self.pool_config.min_connections
        while self._connection_count < self.pool_config.min_connections and attempts < max_attempts:
            attempts += 1
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
        max_attempts = int(timeout / 0.1) + 1  # 防止无限循环的安全措施
        attempt = 0
        
        while attempt < max_attempts:
            attempt += 1
            elapsed = time.time() - start_time
            if elapsed >= timeout:
                raise TimeoutError(f"获取连接超时（{timeout}秒），已尝试 {attempt} 次")
            
            # 先尝试从池中获取
            try:
                conn = self._pool.get_nowait()
                if conn.connection is not None:
                    conn.in_use = True
                    conn.last_used_at = time.time()
                    return conn
                else:
                    self._remove_connection(conn)
                    continue  # 继续尝试获取下一个
            except queue.Empty:
                pass
            
            # 池为空，检查是否可以创建新连接
            should_create = False
            with self._pool_lock:
                if self._connection_count < self.pool_config.max_connections:
                    should_create = True
                    self._connection_count += 1  # 预占位
            
            if should_create:
                try:
                    conn = self._create_connection_internal()
                    conn.in_use = True
                    return conn
                except Exception as e:
                    # 创建失败，释放预占位
                    with self._pool_lock:
                        self._connection_count = max(0, self._connection_count - 1)
                    # 如果是超时错误，直接抛出
                    if isinstance(e, TimeoutError):
                        raise e
                    # 其他错误，记录并继续尝试
                    print(f"创建连接失败: {e}，继续尝试...")
                    time.sleep(0.1)
                    continue
            
            # 已达最大连接数，等待一下再试
            time.sleep(0.1)
        
        # 超过最大尝试次数
        raise TimeoutError(f"获取连接超时，已达最大尝试次数 {max_attempts}")
    
    def _create_connection_internal(self) -> PooledConnection:
        """创建连接的内部方法（不增加计数，由调用者管理）"""
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
        """释放连接回池（不做健康检查，避免阻塞）
        
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
        
        # 不在释放时检查健康状态，避免阻塞
        # 健康检查由后台线程定期执行
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
        
        # 重置单例和初始化标志
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
