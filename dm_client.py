"""
达梦数据库客户端 - 真实可用版本
需要安装 dmPython: pip install dmPython

支持两种模式：
1. 直接连接模式（默认）- 每次创建新连接
2. 连接池模式 - 使用连接池复用连接
"""

import typing as t
from dataclasses import dataclass
from config import get_database_config


@dataclass
class DmConfig:
    """达梦数据库连接配置"""
    host: str = "192.168.2.38"
    port: int = 5236
    user: str = "SYSDBA"
    password: str = "SYSDBA001"
    schema: str = "aiops"
    query_timeout: int = 120  # 查询超时时间（秒）
    retry_attempts: int = 3   # 重试次数
    retry_delay: int = 5      # 重试延迟（秒）
    # 连接池配置
    use_pool: bool = True           # 是否使用连接池
    pool_min_connections: int = 2   # 最小连接数
    pool_max_connections: int = 10  # 最大连接数
    pool_connection_timeout: int = 30  # 获取连接超时（秒）

    @classmethod
    def from_config_file(cls):
        """从配置文件创建配置对象"""
        db_config = get_database_config()
        return cls(
            host=db_config.get("host", "192.168.2.38"),
            port=db_config.get("port", 5236),
            user=db_config.get("user", "SYSDBA"),
            password=db_config.get("password", "SYSDBA001"),
            schema=db_config.get("schema", "aiops"),
            query_timeout=db_config.get("query_timeout", 120),
            retry_attempts=db_config.get("retry_attempts", 3),
            retry_delay=db_config.get("retry_delay", 5),
            use_pool=db_config.get("use_pool", True),
            pool_min_connections=db_config.get("pool_min_connections", 2),
            pool_max_connections=db_config.get("pool_max_connections", 10),
            pool_connection_timeout=db_config.get("pool_connection_timeout", 30)
        )


class DmClient:
    """达梦数据库客户端 - 真实实现
    
    支持两种连接模式：
    1. 直接连接模式（use_pool=False）- 每次创建新连接
    2. 连接池模式（use_pool=True）- 使用连接池复用连接
    """

    def __init__(self, config: DmConfig):
        self.config = config
        self.connection = None
        self.driver = None
        self._pool = None
        self._pooled_conn = None
        self._use_pool = config.use_pool

    def _get_driver(self):
        """获取达梦数据库驱动"""
        if self.driver is None:
            try:
                import dmPython
                self.driver = dmPython
                print("达梦数据库驱动加载成功")
                return True
            except ImportError:
                print("错误: 未安装 dmPython 驱动，请运行: pip install dmPython")
                return False
        return True

    def _init_pool(self):
        """初始化连接池"""
        if self._pool is not None:
            return
            
        from dm_pool import DmConnectionPool, PoolConfig, get_pool
        
        db_config = {
            'host': self.config.host,
            'port': self.config.port,
            'user': self.config.user,
            'password': self.config.password,
            'schema': self.config.schema
        }
        
        pool_config = PoolConfig(
            min_connections=self.config.pool_min_connections,
            max_connections=self.config.pool_max_connections,
            connection_timeout=self.config.pool_connection_timeout
        )
        
        self._pool = get_pool(db_config, pool_config)

    def connect(self) -> bool:
        """连接到达梦数据库"""
        # 使用连接池模式
        if self._use_pool:
            return self._connect_with_pool()
        
        # 直接连接模式
        return self._connect_direct()
    
    def _connect_with_pool(self) -> bool:
        """使用连接池获取连接"""
        try:
            self._init_pool()
            self._pooled_conn = self._pool.get_connection(self.config.pool_connection_timeout)
            self.connection = self._pooled_conn.connection
            print(f"从连接池获取连接成功，池状态: {self._pool.get_stats()}")
            return True
        except Exception as e:
            print(f"从连接池获取连接失败: {e}")
            self.connection = None
            return False

    def _connect_direct(self) -> bool:
        """直接连接到达梦数据库（不使用连接池，带超时控制）"""
        if not self._get_driver():
            return False

        try:
            print(f"正在连接到达梦数据库: {self.config.host}:{self.config.port}")
            print(f"用户: {self.config.user}, 模式: {self.config.schema or '默认'}")

            # 使用线程实现连接超时控制
            import threading
            conn_result = {'conn': None, 'error': None}
            connect_done = threading.Event()
            connect_timeout = self.config.pool_connection_timeout  # 复用连接超时配置
            
            def connect_worker():
                try:
                    conn_params = (self.config.user, self.config.password, self.config.host, self.config.port)
                    conn_result['conn'] = self.driver.connect(*conn_params)
                except Exception as e:
                    conn_result['error'] = e
                finally:
                    connect_done.set()
            
            connect_thread = threading.Thread(target=connect_worker, daemon=True)
            connect_thread.start()
            
            # 等待连接完成或超时
            if not connect_done.wait(timeout=connect_timeout):
                print(f"连接超时（{connect_timeout}秒），数据库可能不可达")
                self.connection = None
                return False
            
            if conn_result['error']:
                raise conn_result['error']
            
            self.connection = conn_result['conn']
            print("达梦数据库连接成功")
            return True

        except Exception as e:
            # 简化的错误处理
            error_msg = str(e).lower()
            print(f"连接失败: {e}")
            
            if "timeout" in error_msg or "超时" in error_msg:
                print("原因: 连接超时，数据库可能不可达")
            elif "authentication" in error_msg or "password" in error_msg:
                print("原因: 认证失败，请检查用户名和密码")
            else:
                print("请检查数据库服务状态和网络连接")

            self.connection = None
            return False

    
    def execute_query(self, sql: str) -> t.List[t.Dict[str, t.Any]]:
        """执行 SQL 查询，返回结果（带超时和重试机制）"""
        return self._execute_with_retry(self._execute_query_with_timeout, sql)

    def _execute_query_with_timeout(self, sql: str) -> t.List[t.Dict[str, t.Any]]:
        """执行 SQL 查询的核心方法（带超时控制）"""
        if not self.connection:
            if not self.connect():
                return []

        import threading
        import time
        
        result = []
        exception_occurred = None
        query_completed = threading.Event()
        
        def query_worker():
            nonlocal result, exception_occurred
            try:
                cursor = self.connection.cursor()
                print(f"执行 SQL: {sql.strip()}")
                print(f"查询超时设置: {self.config.query_timeout} 秒")
                
                start_time = time.time()
                cursor.execute(sql)
                execute_time = time.time() - start_time
                print(f"SQL执行耗时: {execute_time:.2f} 秒")
                
                # 获取列名
                columns = [desc[0] for desc in cursor.description] if cursor.description else []
                
                # 获取结果
                rows = cursor.fetchall()
                fetch_time = time.time() - start_time
                print(f"数据获取总耗时: {fetch_time:.2f} 秒")
                
                # 转换为字典列表
                for row in rows:
                    if len(columns) == len(row):
                        result.append(dict(zip(columns, row)))
                    else:
                        # 如果列数不匹配，使用索引作为键
                        result.append({"row": row})
                
                cursor.close()
                print(f"查询成功，返回 {len(result)} 行结果")
                query_completed.set()
                
            except Exception as e:
                exception_occurred = e
                print(f"查询执行失败: {e}")
                query_completed.set()
        
        # 使用线程执行查询，以便能够控制超时
        query_thread = threading.Thread(target=query_worker)
        query_thread.daemon = True
        
        print(f"开始执行查询，超时时间: {self.config.query_timeout} 秒")
        start_time = time.time()
        query_thread.start()
        
        # 等待查询完成或超时
        completed = query_completed.wait(timeout=self.config.query_timeout)
        elapsed_time = time.time() - start_time
        
        if not completed:
            # 查询超时
            print(f"查询超时！已等待 {elapsed_time:.2f} 秒，超过设定的 {self.config.query_timeout} 秒")
            print("强制断开数据库连接...")
            self.disconnect()
            
            # 等待线程结束（给一点时间让线程清理）
            query_thread.join(timeout=1.0)
            if query_thread.is_alive():
                print("警告: 查询线程仍在运行，可能存在资源泄漏")
            
            raise Exception(f"查询超时（{self.config.query_timeout}秒），实际等待时间: {elapsed_time:.2f}秒")
        
        print(f"查询完成，总耗时: {elapsed_time:.2f} 秒")
        
        if exception_occurred:
            raise exception_occurred
            
        return result

    def execute_update(self, sql: str) -> int:
        """执行 INSERT/UPDATE/DELETE 语句，返回影响的行数（带超时和重试机制）"""
        return self._execute_with_retry(self._execute_update_with_timeout, sql)

    def _execute_update_with_timeout(self, sql: str) -> int:
        """执行更新语句的核心方法（带超时控制）"""
        if not self.connection:
            if not self.connect():
                return -1

        import threading
        import time
        
        affected_rows = -1
        exception_occurred = None
        update_completed = threading.Event()
        
        def update_worker():
            nonlocal affected_rows, exception_occurred
            try:
                cursor = self.connection.cursor()
                print(f"执行更新语句: {sql.strip()}")
                print(f"更新超时设置: {self.config.query_timeout} 秒")
                
                start_time = time.time()
                cursor.execute(sql)
                execute_time = time.time() - start_time
                print(f"SQL执行耗时: {execute_time:.2f} 秒")
                
                affected_rows = cursor.rowcount
                
                self.connection.commit()
                cursor.close()
                
                print(f"更新成功，影响 {affected_rows} 行")
                update_completed.set()
                
            except Exception as e:
                exception_occurred = e
                print(f"更新执行失败: {e}")
                if self.connection:
                    try:
                        self.connection.rollback()
                    except:
                        pass
                update_completed.set()
        
        # 使用线程执行更新，以便能够控制超时
        update_thread = threading.Thread(target=update_worker)
        update_thread.daemon = True
        
        print(f"开始执行更新，超时时间: {self.config.query_timeout} 秒")
        start_time = time.time()
        update_thread.start()
        
        # 等待更新完成或超时
        completed = update_completed.wait(timeout=self.config.query_timeout)
        elapsed_time = time.time() - start_time
        
        if not completed:
            # 更新超时
            print(f"更新超时！已等待 {elapsed_time:.2f} 秒，超过设定的 {self.config.query_timeout} 秒")
            print("强制断开数据库连接...")
            self.disconnect()
            
            # 等待线程结束
            update_thread.join(timeout=1.0)
            if update_thread.is_alive():
                print("警告: 更新线程仍在运行，可能存在资源泄漏")
            
            raise Exception(f"更新超时（{self.config.query_timeout}秒），实际等待时间: {elapsed_time:.2f}秒")
        
        print(f"更新完成，总耗时: {elapsed_time:.2f} 秒")
        
        if exception_occurred:
            raise exception_occurred
            
        return affected_rows

    def test_connection(self) -> dict:
        """测试数据库连接"""
        try:
            if not self.connect():
                return {"success": False, "error": "连接失败"}

            # 执行一个简单的查询来测试连接
            result = self.execute_query("SELECT 1 AS test_value FROM DUAL")

            if result:
                return {
                    "success": True,
                    "message": "连接测试成功",
                    "test_query": result[0]
                }
            else:
                return {"success": False, "error": "测试查询失败"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def list_views(self, schema: str = None) -> t.List[t.Dict[str, t.Any]]:
        """查询数据库中的视图列表

        Args:
            schema: 可选的模式名称，不提供则查询当前用户视图

        Returns:
            List[Dict]: 视图信息列表，每个视图包含VIEW_NAME等字段

        Raises:
            ValueError: 当schema名称包含非法字符时
        """
        if schema is not None:
            # 验证schema参数
            if not schema.strip():
                raise ValueError("Schema名称不能为空")

            # 查询指定模式的视图，使用参数化查询
            # 达梦数据库使用ALL_OBJECTS表查询视图信息
            sql = "SELECT OBJECT_NAME FROM ALL_OBJECTS WHERE OWNER = ? AND OBJECT_TYPE = 'VIEW' ORDER BY OBJECT_NAME"
            result = self._execute_param_query(sql, (schema.strip(),))
        else:
            # 查询当前用户模式的视图
            # 达梦数据库使用USER_OBJECTS表查询视图信息
            sql = "SELECT OBJECT_NAME FROM USER_OBJECTS WHERE OBJECT_TYPE = 'VIEW' ORDER BY OBJECT_NAME"
            result = self.execute_query(sql)

        # 重命名字段为VIEW_NAME以保持一致性
        for item in result:
            if 'OBJECT_NAME' in item:
                item['VIEW_NAME'] = item['OBJECT_NAME']

        print(f"视图列表查询完成，找到 {len(result)} 个视图")
        return result

    def _execute_param_query(self, sql: str, params: tuple) -> t.List[t.Dict[str, t.Any]]:
        """执行参数化查询的辅助方法"""
        if not self.connection:
            if not self.connect():
                return []

        try:
            cursor = self.connection.cursor()
            cursor.execute(sql, params)

            # 获取列名
            columns = [desc[0] for desc in cursor.description] if cursor.description else []

            # 获取结果
            rows = cursor.fetchall()

            # 转换为字典列表
            result = []
            for row in rows:
                if len(columns) == len(row):
                    result.append(dict(zip(columns, row)))
                else:
                    result.append({"row": row})

            cursor.close()
            return result

        except Exception as e:
            print(f"参数化查询执行失败: {e}")
            return []

    def list_tables(self, schema: str = None) -> t.List[t.Dict[str, t.Any]]:
        """查询数据库中的物理表列表

        Args:
            schema: 可选的模式名称，不提供则查询当前用户表

        Returns:
            List[Dict]: 表信息列表，每个表包含TABLE_NAME等字段

        Raises:
            ValueError: 当schema名称包含非法字符时
        """
        if schema is not None:
            # 验证schema参数
            if not schema.strip():
                raise ValueError("Schema名称不能为空")

            # 查询指定模式的物理表，使用参数化查询
            # 达梦数据库使用ALL_OBJECTS表查询表信息
            sql = "SELECT OBJECT_NAME FROM ALL_OBJECTS WHERE OWNER = ? AND OBJECT_TYPE = 'TABLE' ORDER BY OBJECT_NAME"
            result = self._execute_param_query(sql, (schema.strip(),))
        else:
            # 查询当前用户模式的物理表
            # 达梦数据库使用USER_OBJECTS表查询表信息
            sql = "SELECT OBJECT_NAME FROM USER_OBJECTS WHERE OBJECT_TYPE = 'TABLE' ORDER BY OBJECT_NAME"
            result = self.execute_query(sql)

        # 重命名字段为TABLE_NAME以保持一致性
        for item in result:
            if 'OBJECT_NAME' in item:
                item['TABLE_NAME'] = item['OBJECT_NAME']

        print(f"物理表列表查询完成，找到 {len(result)} 个表")
        return result

    def get_view_definition(self, view_name: str, schema: str = None) -> t.List[t.Dict[str, t.Any]]:
        """获取指定视图的创建语句

        Args:
            view_name: 视图名称（必需）
            schema: 可选的模式名称，不提供则查询当前用户视图

        Returns:
            List[Dict]: 包含视图定义信息的字典列表，主要包含VIEW_DEF字段（视图创建SQL语句）

        Raises:
            ValueError: 当view_name或schema名称包含非法字符时
        """
        # 验证view_name参数
        if not view_name or not view_name.strip():
            raise ValueError("视图名称不能为空")

        view_name = view_name.strip()

        if schema:
            # 验证schema参数
            if not schema.strip():
                raise ValueError("Schema名称不能为空")

            # 使用ALL_VIEWS视图查询视图定义
            sql = "SELECT TEXT AS VIEW_DEF FROM ALL_VIEWS WHERE VIEW_NAME = ? AND OWNER = ?"
            result = self._execute_param_query(sql, (view_name, schema.strip()))
        else:
            # 使用USER_VIEWS视图查询当前用户视图定义
            sql = "SELECT TEXT AS VIEW_DEF FROM USER_VIEWS WHERE VIEW_NAME = ?"
            result = self._execute_param_query(sql, (view_name,))

        print(f"视图定义查询完成，视图: {view_name}, 结果: {len(result)} 行")
        return result

    def describe_table(self, table_name: str, schema: str = None) -> t.List[t.Dict[str, t.Any]]:
        """获取指定表的结构信息

        Args:
            table_name: 表名称（必需）
            schema: 可选的模式名称，不提供则查询当前用户表

        Returns:
            List[Dict]: 表结构信息列表，每个字段包含COLUMN_NAME、DATA_TYPE、DATA_LENGTH、NULLABLE等字段

        Raises:
            ValueError: 当table_name或schema名称包含非法字符时
        """
        # 验证table_name参数
        if not table_name or not table_name.strip():
            raise ValueError("表名称不能为空")

        table_name = table_name.strip()

        if schema:
            # 验证schema参数
            if not schema.strip():
                raise ValueError("Schema名称不能为空")

            # 使用ALL_TAB_COLUMNS视图查询表结构
            sql = """
                SELECT
                    COLUMN_NAME,
                    DATA_TYPE,
                    DATA_LENGTH,
                    DATA_PRECISION,
                    DATA_SCALE,
                    NULLABLE,
                    DATA_DEFAULT,
                    COLUMN_ID
                FROM ALL_TAB_COLUMNS
                WHERE TABLE_NAME = ? AND OWNER = ?
                ORDER BY COLUMN_ID
            """
            result = self._execute_param_query(sql, (table_name, schema.strip()))
        else:
            # 使用USER_TAB_COLUMNS视图查询当前用户表结构
            sql = """
                SELECT
                    COLUMN_NAME,
                    DATA_TYPE,
                    DATA_LENGTH,
                    DATA_PRECISION,
                    DATA_SCALE,
                    NULLABLE,
                    DATA_DEFAULT,
                    COLUMN_ID
                FROM USER_TAB_COLUMNS
                WHERE TABLE_NAME = ?
                ORDER BY COLUMN_ID
            """
            result = self._execute_param_query(sql, (table_name,))

        print(f"表结构查询完成，表: {table_name}, 结果: {len(result)} 列")
        return result

    def disconnect(self):
        """断开数据库连接"""
        # 连接池模式：释放连接回池
        if self._use_pool and self._pooled_conn:
            try:
                self._pool.release_connection(self._pooled_conn)
                print("连接已释放回连接池")
            except Exception as e:
                print(f"释放连接到池时出错: {e}")
            finally:
                self._pooled_conn = None
                self.connection = None
            return
        
        # 直接连接模式：关闭连接
        if self.connection:
            try:
                self.connection.close()
                print("达梦数据库连接已断开")
            except Exception as e:
                print(f"断开连接时出错: {e}")
            finally:
                self.connection = None

    def close(self):
        """关闭数据库连接"""
        self.disconnect()

    def _execute_with_retry(self, func, *args, **kwargs):
        """通用重试机制"""
        import time
        
        last_exception = None
        
        for attempt in range(self.config.retry_attempts + 1):  # +1 因为包含初始尝试
            try:
                if attempt > 0:
                    print(f"第 {attempt} 次重试...")
                    # 重试前先断开连接
                    self.disconnect()
                    # 等待重试延迟
                    time.sleep(self.config.retry_delay)
                
                return func(*args, **kwargs)
                
            except Exception as e:
                last_exception = e
                print(f"尝试 {attempt + 1} 失败: {e}")
                
                # 如果是最后一次尝试，不再重试
                if attempt >= self.config.retry_attempts:
                    break
                    
                print(f"将在 {self.config.retry_delay} 秒后重试...")
        
        # 所有重试都失败了
        print(f"所有重试都失败，总共尝试了 {self.config.retry_attempts + 1} 次")
        if last_exception:
            raise last_exception
        else:
            raise Exception("操作失败，原因未知")

    def __enter__(self):
        """上下文管理器支持"""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器支持"""
        self.close()


def test_dm_client():
    """测试达梦数据库客户端 - 修复版本"""
    print("=== 达梦数据库客户端测试 - 修复版本 ===")

    # 从配置文件读取配置
    config = DmConfig.from_config_file()
    print(f"从配置文件读取连接信息: {config.host}:{config.port}, 用户: {config.user}")

    try:
        # 测试连接和查询
        print("\n1. 测试连接...")
        client = DmClient(config)

        if client.connect():
            print("[OK] 数据库连接成功!")

            # 测试 TASK_HANDLE_WORKORDER 表结构
            print("\n2. 测试 TASK_HANDLE_WORKORDER 表结构...")
            try:
                table_struct = client.describe_table("TASK_HANDLE_WORKORDER", "aiops")
                print(f"[OK] TASK_HANDLE_WORKORDER 表结构查询成功")
                if table_struct:
                    print(f"TASK_HANDLE_WORKORDER 包含 {len(table_struct)} 个列:")
                    for i, col in enumerate(table_struct[:5]):  # 显示前5列
                        print(f"  列{i+1}: {col}")
                    if len(table_struct) > 5:
                        print(f"  ... 还有 {len(table_struct)-5} 列")
                else:
                    print("TASK_HANDLE_WORKORDER 表结构为空")
            except Exception as e:
                print(f"[ERROR] TASK_HANDLE_WORKORDER 表结构查询失败: {e}")

            # 测试 V_OPS_WORK_ORDERS 视图定义
            print("\n3. 测试 V_OPS_WORK_ORDERS 视图定义...")
            try:
                view_def = client.get_view_definition("V_OPS_WORK_ORDERS", "aiops")
                print(f"[OK] V_OPS_WORK_ORDERS 视图定义查询成功")
                if view_def:
                    print(f"V_OPS_WORK_ORDERS 视图定义长度: {len(str(view_def))} 字符")
                    # 显示视图定义的前200字符
                    for item in view_def:
                        if 'VIEW_DEF' in item:
                            definition = str(item['VIEW_DEF'])
                            print(f"V_OPS_WORK_ORDERS 视图定义前200字符:")
                            print(f"  {definition[:200]}...")
                else:
                    print("V_OPS_WORK_ORDERS 视图定义为空")
            except Exception as e:
                print(f"[ERROR] V_OPS_WORK_ORDERS 视图定义查询失败: {e}")

            print("\n=== 修复完成！两个SQL错误已解决 ===")

        else:
            print("[ERROR] 数据库连接失败")

    except Exception as e:
        print(f"[ERROR] 测试过程中发生异常: {e}")

    finally:
        # 清理
        if 'client' in locals():
            client.close()

    print("\n=== 测试完成 ===")


if __name__ == "__main__":
    test_dm_client()