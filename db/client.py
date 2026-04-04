"""
达梦数据库客户端。

对上层暴露统一的只读查询接口，并在 MCP 进程内支持共享 client 复用。
"""

from __future__ import annotations

import atexit
import threading
import typing as t

from core.exceptions import DatabaseConnectionError, SQLExecutionError
from core.validators import validate_identifier, validate_optional_schema

from .config import DmConfig


class DmClientError(SQLExecutionError):
    """数据库客户端错误。"""


class DmClient:
    """达梦数据库客户端。"""

    def __init__(self, config: DmConfig):
        self.config = config
        self._java_bridge = None

    def _bridge_config(self) -> dict[str, t.Any]:
        return {
            "host": self.config.host,
            "port": self.config.port,
            "user": self.config.user,
            "password": self.config.password,
            "schema": self.config.schema,
            "query_timeout": self.config.query_timeout,
        }

    def _get_bridge(self):
        if self._java_bridge is None:
            from .java_bridge import JavaBridgeClient

            self._java_bridge = JavaBridgeClient(self._bridge_config())
        return self._java_bridge

    def connect(self) -> bool:
        try:
            return self._get_bridge().is_alive()
        except Exception:
            return False

    def is_connected(self) -> bool:
        return self._java_bridge is not None and self._java_bridge.is_alive()

    def execute_query(
        self,
        sql: str,
        statement_type: t.Optional[str] = None,
    ) -> dict[str, t.Any]:
        bridge = self._get_bridge()
        if not bridge.is_alive():
            raise DatabaseConnectionError("Java 守护进程未运行")

        try:
            result = bridge.execute_query(sql, statement_type=statement_type)
        except Exception as exc:
            raise SQLExecutionError(f"查询失败: {exc}") from exc

        if not result.get("success", True):
            raise SQLExecutionError(result.get("message", "查询失败"))

        columns = result.get("columns", [])
        rows = result.get("rows", [])
        self._ensure_diagnostic_rows(statement_type, rows)

        unified = {
            "columns": columns,
            "rows": rows,
        }
        if "plan_table_row_count" in result:
            unified["plan_table_row_count"] = result["plan_table_row_count"]
        return unified

    def execute_explain_plan(self, sql: str) -> dict[str, t.Any]:
        return self.execute_query(sql, statement_type="EXPLAIN")

    def _ensure_diagnostic_rows(
        self,
        statement_type: t.Optional[str],
        rows: t.Sequence[t.Any],
    ) -> None:
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

    def list_tables(self, schema: t.Optional[str] = None) -> dict[str, t.Any]:
        validated_schema = validate_optional_schema(schema)
        if validated_schema:
            sql = (
                "SELECT OBJECT_NAME AS TABLE_NAME "
                "FROM ALL_OBJECTS "
                f"WHERE OWNER = '{validated_schema}' AND OBJECT_TYPE = 'TABLE' "
                "ORDER BY OBJECT_NAME"
            )
        else:
            sql = (
                "SELECT OBJECT_NAME AS TABLE_NAME "
                "FROM USER_OBJECTS "
                "WHERE OBJECT_TYPE = 'TABLE' "
                "ORDER BY OBJECT_NAME"
            )
        return self.execute_query(sql)

    def list_views(self, schema: t.Optional[str] = None) -> dict[str, t.Any]:
        validated_schema = validate_optional_schema(schema)
        if validated_schema:
            sql = (
                "SELECT OBJECT_NAME AS VIEW_NAME "
                "FROM ALL_OBJECTS "
                f"WHERE OWNER = '{validated_schema}' AND OBJECT_TYPE = 'VIEW' "
                "ORDER BY OBJECT_NAME"
            )
        else:
            sql = (
                "SELECT OBJECT_NAME AS VIEW_NAME "
                "FROM USER_OBJECTS "
                "WHERE OBJECT_TYPE = 'VIEW' "
                "ORDER BY OBJECT_NAME"
            )
        return self.execute_query(sql)

    def describe_table(
        self,
        table_name: str,
        schema: t.Optional[str] = None,
    ) -> dict[str, t.Any]:
        validated_table = validate_identifier(table_name, "table name")
        validated_schema = validate_optional_schema(schema)

        sql = """
            SELECT COLUMN_NAME, DATA_TYPE, DATA_LENGTH, DATA_PRECISION,
                   DATA_SCALE, NULLABLE, DATA_DEFAULT, COLUMN_ID
            FROM {view} WHERE TABLE_NAME = '{table}'{owner} ORDER BY COLUMN_ID
        """

        if validated_schema:
            owner = f" AND OWNER = '{validated_schema}'"
            view = "ALL_TAB_COLUMNS"
        else:
            owner = ""
            view = "USER_TAB_COLUMNS"

        return self.execute_query(sql.format(view=view, table=validated_table, owner=owner))

    def get_view_definition(
        self,
        view_name: str,
        schema: t.Optional[str] = None,
    ) -> dict[str, t.Any]:
        validated_view = validate_identifier(view_name, "view name")
        validated_schema = validate_optional_schema(schema)

        if validated_schema:
            sql = (
                "SELECT TEXT AS VIEW_DEF "
                "FROM ALL_VIEWS "
                f"WHERE VIEW_NAME = '{validated_view}' AND OWNER = '{validated_schema}'"
            )
        else:
            sql = (
                "SELECT TEXT AS VIEW_DEF "
                "FROM USER_VIEWS "
                f"WHERE VIEW_NAME = '{validated_view}'"
            )

        return self.execute_query(sql)

    def close(self) -> None:
        if self._java_bridge is None:
            return
        try:
            self._java_bridge.shutdown()
        finally:
            self._java_bridge = None

    def __enter__(self) -> "DmClient":
        if not self.connect():
            raise DatabaseConnectionError("无法建立数据库连接")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()


_shared_client: t.Optional[DmClient] = None
_shared_client_lock = threading.Lock()


def create_client(config_file: t.Optional[str] = None) -> DmClient:
    config = DmConfig.from_config_file(config_file or "dm_config.json")
    return DmClient(config)


def get_shared_client() -> DmClient:
    global _shared_client

    with _shared_client_lock:
        if _shared_client is None:
            _shared_client = create_client()

        if not _shared_client.connect():
            _shared_client.close()
            _shared_client = create_client()
            if not _shared_client.connect():
                raise DatabaseConnectionError("无法建立数据库连接")

        return _shared_client


def reset_shared_client() -> None:
    global _shared_client

    with _shared_client_lock:
        if _shared_client is not None:
            _shared_client.close()
            _shared_client = None


atexit.register(reset_shared_client)
