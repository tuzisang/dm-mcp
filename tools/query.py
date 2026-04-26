"""
查询工具模块

提供 SQL 查询执行功能
"""

import time
import re
from typing import Dict, Any

from core.cache import mcp_cache
from core.decorators import mcp_tool_handler
from core.response import create_response_metadata
from core.validators import (
    STATEMENT_TYPE_EXPLAIN,
    STATEMENT_TYPE_EXPLAIN_PLAN,
    STATEMENT_TYPE_SELECT,
    validate_sql_query,
)
from db.client import get_shared_client


_STATEMENT_TYPE_TO_QUERY_TYPE = {
    STATEMENT_TYPE_SELECT: "SELECT",
    STATEMENT_TYPE_EXPLAIN: "EXPLAIN",
    STATEMENT_TYPE_EXPLAIN_PLAN: "EXPLAIN_PLAN",
}


def _normalize_diagnostic_sql(sql: str, statement_type: str) -> tuple[str, str]:
    """将用户输入的诊断 SQL 规范化到当前环境可执行的路径。"""
    if statement_type != STATEMENT_TYPE_EXPLAIN_PLAN:
        return sql, statement_type

    normalized = re.sub(
        r"^(\s*)EXPLAIN\s+PLAN(?:\s+FOR)?\s+",
        r"\1EXPLAIN ",
        sql,
        flags=re.IGNORECASE,
    )

    if normalized != sql:
        return normalized, STATEMENT_TYPE_EXPLAIN

    return sql, statement_type


@mcp_cache()
@mcp_tool_handler("dm_query")
def dm_query(sql: str) -> Dict[str, Any]:
    """
    执行安全的只读 SQL 查询（包括 SELECT 和诊断语句）

    ⚠️ 达梦数据库双引号规则:
    - 模式名、表名、字段名需要用双引号包裹才能识别大小写
    - 不用双引号会自动转为大写
    - 示例: SELECT * FROM "aiops"."TASK_HANDLE_WORKORDER"

    Args:
        sql: SQL 查询语句，支持：
             - SELECT 查询
             - EXPLAIN SELECT ... (返回执行计划结果集)
             - EXPLAIN PLAN [FOR] SELECT ... (仅生成执行计划，FOR 可选)

    Returns:
        dict: {success, data, sql, metadata} 或 {success, error, sql, metadata}
              metadata.additional_info.statement_type: SELECT | EXPLAIN | EXPLAIN_PLAN
              metadata.additional_info.query_type: 同上
              metadata.additional_info.plan_table_row_count: 仅 EXPLAIN_PLAN 有值
    """
    start_time = time.time()

    # 验证 SQL 并识别语句类型
    validated_sql, statement_type = validate_sql_query(sql)

    normalized_sql, execution_statement_type = _normalize_diagnostic_sql(
        validated_sql, statement_type
    )

    client = get_shared_client()
    result = client.execute_query(
        normalized_sql,
        statement_type=execution_statement_type,
    )
    execution_time = time.time() - start_time

    additional_info = {
        "statement_type": statement_type,
        "query_type": _STATEMENT_TYPE_TO_QUERY_TYPE.get(statement_type, statement_type),
    }

    if execution_statement_type != statement_type:
        additional_info["execution_statement_type"] = execution_statement_type
        additional_info["normalized_sql"] = normalized_sql

    if statement_type == STATEMENT_TYPE_EXPLAIN_PLAN:
        plan_row_count = result.get("plan_table_row_count")
        if plan_row_count is not None:
            additional_info["plan_table_row_count"] = plan_row_count

    return {
        "success": True,
        "data": result,
        "sql": normalized_sql,
        "metadata": create_response_metadata(
            operation="dm_query",
            success=True,
            execution_time=execution_time,
            row_count=len(result.get("rows", [])),
            additional_info=additional_info,
        ),
    }
