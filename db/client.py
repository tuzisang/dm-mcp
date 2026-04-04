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

        # 构建数据库配置字典（包含新的配置参数）
        self._db_config = {
            'host': config.host,
            'port': config.port,
            'user': config.user,
            'password': config.password,
            'schema': config.schema,
            'query_timeout': config.query_timeout,
            'pool_min_connections': config.pool_min_connections,
            'pool_max_connections': config.pool_max_connections,
            'pool_connection_timeout': config.pool_connection_timeout,
            'io_timeout': config.io_timeout,
            'health_check_interval': config.health_check_interval,
            'max_retries': config.max_retries
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

    def execute_query(self, sql: str, statement_type: str = None) -> t.Dict[str, t.Any]:
        """
        执行 SQL 查询

        Args:
            sql: SQL 查询语句
            statement_type: 语句类型（SELECT, EXPLAIN, EXPLAIN_PLAN），用于桥接层路由

        Returns:
            统一查询结果结构：{"columns": [...], "rows": [[...], ...]}
        """
        return self._execute_with_retry(
            self._execute_query_internal, sql, statement_type=statement_type
        )

    def _execute_query_internal(self, sql: str, statement_type: str = None) -> t.Dict[str, t.Any]:
        """
        执行查询的内部方法

        统一返回 Dict 结构: {"columns": [...], "rows": [[...], ...], "plan_table_row_count"?: int}
        禁止返回混合形态（有时 List 有时 Dict）。
        """
        # SQL 安全检查（基础检查，不能替代参数化查询）
        if not is_safe_sql(sql):
            raise DmClientError(f"SQL 包含危险模式或未被允许的操作: {sql[:100]}...")

        bridge = self._get_bridge()

        if not bridge.is_alive():
            raise DmClientError("Java 守护进程未运行")

        try:
            result = bridge.execute_query(sql, statement_type=statement_type)

            # 转换 Java 返回的格式为统一 Python 字典结构
            # Java 返回: {"success": true, "columns": ["COL1", "COL2"], "rows": [[val1, val2], ...]}
            if not result.get('success'):
                raise DmClientError(result.get('message', '查询失败'))

            columns = result.get('columns', [])
            rows = result.get('rows', [])
            plan_row_count = result.get('plan_table_row_count')
            self._ensure_diagnostic_rows(statement_type, rows)

            # 统一返回 Dict 结构（始终包含 columns 和 rows）
            unified = {
                "columns": columns,
                "rows": rows,
            }
            if plan_row_count is not None:
                unified["plan_table_row_count"] = plan_row_count

            return unified

        except Exception as e:
            raise DmClientError(f"查询失败: {e}")

    def execute_explain_plan(self, sql: str) -> t.Dict[str, t.Any]:
        """
        执行执行计划语句并返回统一结构

        Args:
            sql: EXPLAIN 语句

        Returns:
            统一 Dict 结构: {"columns": [...], "rows": [[...], ...]}
        """
        return self._execute_with_retry(
            self._execute_explain_plan_internal, sql
        )

    def _execute_explain_plan_internal(self, sql: str) -> t.Dict[str, t.Any]:
        """执行执行计划查询的内部方法。"""
        bridge = self._get_bridge()

        if not bridge.is_alive():
            raise DmClientError("Java 守护进程未运行")

        try:
            # 使用 EXPLAIN 直返路径，优先从达梦驱动直接提取计划文本
            result = bridge.execute_query(sql, statement_type="EXPLAIN")

            if not result.get('success'):
                raise DmClientError(result.get('message', '获取执行计划失败'))

            columns = result.get('columns', [])
            rows = result.get('rows', [])
            plan_row_count = result.get('plan_table_row_count')
            self._ensure_diagnostic_rows("EXPLAIN", rows)

            unified = {"columns": columns, "rows": rows}
            if plan_row_count is not None:
                unified["plan_table_row_count"] = plan_row_count

            return unified

        except Exception as e:
            raise DmClientError(f"获取执行计划失败: {e}")

    def _ensure_diagnostic_rows(self, statement_type: t.Optional[str], rows: t.Sequence[t.Any]) -> None:
        """诊断 SQL 不能为空结果，避免把兼容性问题误判成成功。"""
        if rows:
            return

        if statement_type == "EXPLAIN":
            raise DmClientError(
                "目标环境未直接返回执行计划: EXPLAIN 已执行，但未返回任何计划文本或结果集"
            )

        if statement_type == "EXPLAIN_PLAN":
            raise DmClientError(
                "目标环境未产出可读取的执行计划: EXPLAIN PLAN 已执行，但未返回任何计划行"
            )

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

    def list_tables(self, schema: str = None) -> t.Dict[str, t.Any]:
        """
        查询表列表

        Args:
            schema: schema 名称，如果为 None 则查询当前用户的表

        Returns:
            表列表查询结果：{"columns": [...], "rows": [[...], ...]}
        """
        if schema:
            # 验证 schema 名称以防止 SQL 注入
            schema = validate_schema_name(schema)
            sql = f"SELECT OBJECT_NAME AS TABLE_NAME FROM ALL_OBJECTS WHERE OWNER = '{schema}' AND OBJECT_TYPE = 'TABLE' ORDER BY OBJECT_NAME"
        else:
            sql = "SELECT OBJECT_NAME AS TABLE_NAME FROM USER_OBJECTS WHERE OBJECT_TYPE = 'TABLE' ORDER BY OBJECT_NAME"

        return self.execute_query(sql)

    def list_views(self, schema: str = None) -> t.Dict[str, t.Any]:
        """
        查询视图列表

        Args:
            schema: schema 名称，如果为 None 则查询当前用户的视图

        Returns:
            视图列表查询结果：{"columns": [...], "rows": [[...], ...]}
        """
        if schema:
            # 验证 schema 名称以防止 SQL 注入
            schema = validate_schema_name(schema)
            sql = f"SELECT OBJECT_NAME AS VIEW_NAME FROM ALL_OBJECTS WHERE OWNER = '{schema}' AND OBJECT_TYPE = 'VIEW' ORDER BY OBJECT_NAME"
        else:
            sql = "SELECT OBJECT_NAME AS VIEW_NAME FROM USER_OBJECTS WHERE OBJECT_TYPE = 'VIEW' ORDER BY OBJECT_NAME"

        return self.execute_query(sql)

    def describe_table(self, table_name: str, schema: str = None) -> t.Dict[str, t.Any]:
        """
        获取表结构

        Args:
            table_name: 表名
            schema: schema 名称，如果为 None 则查询当前用户的表

        Returns:
            列信息查询结果：{"columns": [...], "rows": [[...], ...]}
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

    def get_view_definition(self, view_name: str, schema: str = None) -> t.Dict[str, t.Any]:
        """
        获取视图定义

        Args:
            view_name: 视图名
            schema: schema 名称，如果为 None 则查询当前用户的视图

        Returns:
            视图定义查询结果（包含 VIEW_DEF 字段）
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
        通用重试机制（优化版）

        - 使用 max_retries 而非 retry_attempts（默认 1 次而非 3 次）
        - 重试延迟从 5 秒降至 1 秒
        - 智能判断异常是否可重试

        Args:
            func: 要执行的函数
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            函数执行结果

        Raises:
            最后一次执行的异常
        """
        import logging
        logger = logging.getLogger(__name__)

        last_exception = None
        start_time = time.time()

        # 使用 max_retries 而非 retry_attempts（默认 1 次而非 3 次）
        max_retries = self.config.max_retries
        retry_delay = 1  # 固定 1 秒延迟（而非 5 秒）

        for attempt in range(max_retries + 1):
            try:
                if attempt > 0:
                    # 重试前等待（1 秒而非 5 秒）
                    logger.info(f"Retry attempt {attempt}/{max_retries} after {retry_delay}s delay")
                    time.sleep(retry_delay)
                return func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                error_msg = str(e).lower()

                # 判断是否为可重试异常
                is_retryable = self._is_retryable_error(e, error_msg)

                if attempt >= max_retries or not is_retryable:
                    # 不可重试或已达到最大重试次数
                    break

                # 记录重试事件
                total_time = time.time() - start_time
                logger.warning(
                    f"Retryable error on attempt {attempt + 1}/{max_retries + 1}: {e}. "
                    f"Will retry in {retry_delay}s..."
                )

        # 所有重试都失败
        total_time = time.time() - start_time
        error_msg = f"Operation failed after {max_retries} retries in {total_time:.1f}s: {last_exception}"
        logger.error(error_msg)

        if last_exception:
            raise last_exception

        raise DmClientError("操作失败")

    def _is_retryable_error(self, error: Exception, error_msg: str) -> bool:
        """
        判断异常是否可重试

        可重试异常：
        - 超时相关（timeout, timed out）
        - 连接相关（connection, bridge）
        - 临时性错误（temporary, try again）

        不可重试异常：
        - SQL 语法错误（syntax, invalid）
        - 权限错误（permission, denied）
        - 表/列不存在（not found, does not exist）

        Args:
            error: 异常对象
            error_msg: 异常消息（小写）

        Returns:
            True 如果可重试，False 否则
        """
        # 可重试的关键词
        retryable_keywords = [
            'timeout',
            'timed out',
            'connection',
            'bridge',
            'temporary',
            'try again',
            'unavailable',
            'deadlock',
            'lock wait'
        ]

        # 不可重试的关键词
        non_retryable_keywords = [
            'syntax',
            'invalid sql',
            'permission',
            'denied',
            'does not exist',
            'not found',
            'duplicate',
            'constraint',
            'foreign key',
            'unique constraint',
            '未产出可读取的执行计划',
            'plan_table 未返回任何计划行',
        ]

        # 首先检查不可重试关键词（优先级更高）
        for keyword in non_retryable_keywords:
            if keyword in error_msg:
                return False

        # 然后检查可重试关键词
        for keyword in retryable_keywords:
            if keyword in error_msg:
                return True

        # 默认：未知异常可重试（保守策略）
        return True

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

    # 转换为 DmConfig 对象（使用新的默认值）
    from .config import DmConfig

    # 向后兼容：处理 pool_connection_timeout（可能是秒或毫秒）
    pool_timeout = db_config.get('pool_connection_timeout', 60000)
    if pool_timeout < 1000:
        pool_timeout = pool_timeout * 1000  # 秒转毫秒

    config = DmConfig(
        host=db_config.get('host', 'localhost'),
        port=db_config.get('port', 5236),
        user=db_config.get('user', ''),
        password=db_config.get('password', ''),
        schema=db_config.get('schema', ''),
        use_pool=db_config.get('use_pool', True),
        query_timeout=db_config.get('query_timeout', 120),
        retry_attempts=db_config.get('retry_attempts', 3),  # 向后兼容
        retry_delay=db_config.get('retry_delay', 5),  # 向后兼容
        pool_min_connections=db_config.get('pool_min_connections', 2),
        pool_max_connections=db_config.get('pool_max_connections', 20),  # 新默认值
        pool_connection_timeout=pool_timeout,  # 新默认值（毫秒），已处理向后兼容
        io_timeout=db_config.get('io_timeout', 30),  # 新参数
        health_check_interval=db_config.get('health_check_interval', 15),  # 新参数
        max_retries=db_config.get('max_retries', 1)  # 新参数（默认 1 次而非 3 次）
    )

    return DmClient(config)
