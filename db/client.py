"""
达梦数据库客户端 - Java 守护进程版本

通过 Java 守护进程（DmJdbcBridge）连接达梦数据库，使用 HikariCP 连接池。
"""

import typing as t
import time
from pathlib import Path

from .config import DmConfig, get_config_manager
from .sql_security import validate_schema_name, validate_table_name, validate_view_name, is_safe_sql


class DmClientError(Exception):
    """数据库客户端错误"""
    pass


class DmClient:
    """达梦数据库客户端 - 使用 Java 守护进程"""

    def __init__(self, config: DmConfig):
        """
        初始化数据库客户端

        Args:
            config: 数据库配置对象
        """
        self.config = config
        self._java_bridge = None

        # 构建数据库配置字典
        self._db_config = {
            'host': config.host,
            'port': config.port,
            'user': config.user,
            'password': config.password,
            'schema': config.schema,
            'query_timeout': config.query_timeout,
            'pool_min_connections': config.pool_min_connections,
            'pool_max_connections': config.pool_max_connections,
            'pool_connection_timeout': config.pool_connection_timeout
        }

    def _get_bridge(self):
        """获取 Java 桥接服务实例（懒加载）"""
        if self._java_bridge is None:
            from .java_bridge import JavaBridgeClient
            self._java_bridge = JavaBridgeClient(self._db_config)
        return self._java_bridge

    def connect(self) -> bool:
        """连接到达梦数据库（Java 守护进程自动连接）"""
        try:
            bridge = self._get_bridge()
            return bridge.is_alive()
        except Exception as e:
            print(f"连接失败: {e}")
            return False

    def is_connected(self) -> bool:
        """
        检查数据库连接是否活跃

        Returns:
            bool: 如果Java桥接进程存活且运行正常返回True，否则返回False
        """
        try:
            bridge = self._get_bridge()
            return bridge is not None and bridge.is_alive()
        except Exception:
            return False

    def execute_query(self, sql: str) -> t.List[t.Dict[str, t.Any]]:
        """
        执行 SQL 查询

        Args:
            sql: SQL 查询语句

        Returns:
            查询结果列表，每行是一个字典
        """
        return self._execute_with_retry(self._execute_query_internal, sql)

    def _execute_query_internal(self, sql: str) -> t.List[t.Dict[str, t.Any]]:
        """执行查询的内部方法"""
        # SQL 安全检查（基础检查，不能替代参数化查询）
        if not is_safe_sql(sql):
            raise DmClientError(f"SQL 包含危险模式或未被允许的操作: {sql[:100]}...")

        bridge = self._get_bridge()

        if not bridge.is_alive():
            raise DmClientError("Java 守护进程未运行")

        try:
            result = bridge.execute_query(sql)

            # 转换 Java 返回的格式为 Python 字典列表
            # Java 返回: {"success": true, "columns": ["COL1", "COL2"], "rows": [[val1, val2], ...]}
            if not result.get('success'):
                raise DmClientError(result.get('message', '查询失败'))

            columns = result.get('columns', [])
            rows = result.get('rows', [])

            return [dict(zip(columns, row)) for row in rows]

        except Exception as e:
            raise DmClientError(f"查询失败: {e}")

    def execute_update(self, sql: str) -> int:
        """
        执行更新语句（INSERT/UPDATE/DELETE）

        Args:
            sql: SQL 更新语句

        Returns:
            影响的行数
        """
        return self._execute_with_retry(self._execute_update_internal, sql)

    def _execute_update_internal(self, sql: str) -> int:
        """执行更新的内部方法"""
        bridge = self._get_bridge()

        if not bridge.is_alive():
            raise DmClientError("Java 守护进程未运行")

        try:
            result = bridge.execute_update(sql)

            if not result.get('success'):
                raise DmClientError(result.get('message', '更新失败'))

            return result.get('affectedRows', -1)

        except Exception as e:
            raise DmClientError(f"更新失败: {e}")

    def list_tables(self, schema: str = None) -> t.List[t.Dict[str, t.Any]]:
        """
        查询表列表

        Args:
            schema: schema 名称，如果为 None 则查询当前用户的表

        Returns:
            表列表
        """
        if schema:
            # 验证 schema 名称以防止 SQL 注入
            schema = validate_schema_name(schema)
            sql = f"SELECT OBJECT_NAME FROM ALL_OBJECTS WHERE OWNER = '{schema}' AND OBJECT_TYPE = 'TABLE' ORDER BY OBJECT_NAME"
        else:
            sql = "SELECT OBJECT_NAME FROM USER_OBJECTS WHERE OBJECT_TYPE = 'TABLE' ORDER BY OBJECT_NAME"

        result = self.execute_query(sql)

        # 转换字段名
        for item in result:
            if 'OBJECT_NAME' in item:
                item['TABLE_NAME'] = item['OBJECT_NAME']

        return result

    def list_views(self, schema: str = None) -> t.List[t.Dict[str, t.Any]]:
        """
        查询视图列表

        Args:
            schema: schema 名称，如果为 None 则查询当前用户的视图

        Returns:
            视图列表
        """
        if schema:
            # 验证 schema 名称以防止 SQL 注入
            schema = validate_schema_name(schema)
            sql = f"SELECT OBJECT_NAME FROM ALL_OBJECTS WHERE OWNER = '{schema}' AND OBJECT_TYPE = 'VIEW' ORDER BY OBJECT_NAME"
        else:
            sql = "SELECT OBJECT_NAME FROM USER_OBJECTS WHERE OBJECT_TYPE = 'VIEW' ORDER BY OBJECT_NAME"

        result = self.execute_query(sql)

        # 转换字段名
        for item in result:
            if 'OBJECT_NAME' in item:
                item['VIEW_NAME'] = item['OBJECT_NAME']

        return result

    def describe_table(self, table_name: str, schema: str = None) -> t.List[t.Dict[str, t.Any]]:
        """
        获取表结构

        Args:
            table_name: 表名
            schema: schema 名称，如果为 None 则查询当前用户的表

        Returns:
            列信息列表
        """
        # 验证表名以防止 SQL 注入
        table_name = validate_table_name(table_name)

        sql_base = """
            SELECT COLUMN_NAME, DATA_TYPE, DATA_LENGTH, DATA_PRECISION,
                   DATA_SCALE, NULLABLE, DATA_DEFAULT, COLUMN_ID
            FROM {view} WHERE TABLE_NAME = '{table}'{owner} ORDER BY COLUMN_ID
        """

        if schema:
            schema = validate_schema_name(schema)
            owner = f" AND OWNER = '{schema}'"
            view = "ALL_TAB_COLUMNS"
        else:
            owner = ""
            view = "USER_TAB_COLUMNS"

        sql = sql_base.format(view=view, table=table_name, owner=owner)
        return self.execute_query(sql)

    def get_view_definition(self, view_name: str, schema: str = None) -> t.List[t.Dict[str, t.Any]]:
        """
        获取视图定义

        Args:
            view_name: 视图名
            schema: schema 名称，如果为 None 则查询当前用户的视图

        Returns:
            视图定义列表（包含 VIEW_DEF 字段）
        """
        # 验证视图名以防止 SQL 注入
        view_name = validate_view_name(view_name)

        if schema:
            schema = validate_schema_name(schema)
            sql = f"SELECT TEXT AS VIEW_DEF FROM ALL_VIEWS WHERE VIEW_NAME = '{view_name}' AND OWNER = '{schema}'"
        else:
            sql = f"SELECT TEXT AS VIEW_DEF FROM USER_VIEWS WHERE VIEW_NAME = '{view_name}'"

        return self.execute_query(sql)

    def disconnect(self):
        """断开连接（Java 守护进程持续运行，不主动断开）"""
        # Java 守护进程持续运行，只在显式关闭时才终止
        pass

    def close(self):
        """关闭客户端并终止 Java 守护进程"""
        if self._java_bridge:
            try:
                self._java_bridge.shutdown()
            except Exception:
                pass
            finally:
                self._java_bridge = None

    def _execute_with_retry(self, func, *args, **kwargs):
        """
        通用重试机制

        Args:
            func: 要执行的函数
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            函数执行结果

        Raises:
            最后一次执行的异常
        """
        last_exception = None
        for attempt in range(self.config.retry_attempts + 1):
            try:
                if attempt > 0:
                    # 重试前等待
                    time.sleep(self.config.retry_delay)
                return func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                if attempt >= self.config.retry_attempts:
                    break

        if last_exception:
            raise last_exception

        raise DmClientError("操作失败")

    def __enter__(self):
        """
        上下文管理器入口 - 确保连接建立

        Returns:
            DmClient: 客户端实例

        Raises:
            DmClientError: 如果无法建立数据库连接
        """
        if not self.is_connected():
            raise DmClientError("无法建立数据库连接")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器退出"""
        self.close()


# 便捷函数
def create_client(config_file: str = None) -> DmClient:
    """
    创建数据库客户端

    Args:
        config_file: 配置文件路径，默认为 dm_config.json

    Returns:
        DmClient 实例
    """
    manager = get_config_manager()
    db_config = manager.get_database_config()

    if config_file:
        import json
        with open(config_file) as f:
            db_config.update(json.load(f).get('database', {}))

    # 转换为 DmConfig 对象
    from .config import DmConfig
    config = DmConfig(
        host=db_config.get('host', 'localhost'),
        port=db_config.get('port', 5236),
        user=db_config.get('user', ''),
        password=db_config.get('password', ''),
        schema=db_config.get('schema', ''),
        use_pool=db_config.get('use_pool', True),
        query_timeout=db_config.get('query_timeout', 120),
        retry_attempts=db_config.get('retry_attempts', 3),
        retry_delay=db_config.get('retry_delay', 5),
        pool_min_connections=db_config.get('pool_min_connections', 2),
        pool_max_connections=db_config.get('pool_max_connections', 10),
        pool_connection_timeout=db_config.get('pool_connection_timeout', 30)
    )

    return DmClient(config)
