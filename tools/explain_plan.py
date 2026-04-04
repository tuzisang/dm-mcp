"""
执行计划工具模块

提供专用工具获取 SELECT 语句的执行计划，在单次调用中完成计划生成与读取，
避免跨 JDBC session 导致 PLAN_TABLE 为空的问题。
桥接层优先使用达梦驱动可直接返回计划的路径。
"""

import time
from typing import Dict, Any

from core import create_response_metadata, mcp_tool_handler, mcp_cache
from db import DmClient, DmConfig


def get_database_client() -> DmClient:
    """获取数据库客户端实例"""
    return DmClient(DmConfig.from_config_file())


@mcp_cache()
@mcp_tool_handler("dm_explain_plan")
def dm_explain_plan(select_sql: str) -> Dict[str, Any]:
    """
    获取 SELECT 语句的执行计划（单次调用）

    在同一次 JDBC 连接/session 中完成"计划生成 + 计划读取"，避免跨调用
    session 不一致导致的 PLAN_TABLE 为空问题。

    ⚠️ 达梦数据库限制：
    - 此工具仅接受 SELECT 语句（非 EXPLAIN 前缀语句）
    - 执行计划通过 DM 支持的诊断方式获取

    Args:
        select_sql: SELECT 查询语句（不含 EXPLAIN 前缀）

    Returns:
        dict: {success, data, sql, metadata}
              metadata.statement_type: "EXPLAIN_PLAN"
              metadata.query_type: "EXPLAIN_PLAN"
              data.columns: 执行计划列名
              data.rows: 执行计划行数据
    """
    start_time = time.time()

    # 验证输入是 SELECT 语句（不含 EXPLAIN 前缀）
    from core.validators import _strip_sql_comments, InvalidParameterError
    upper = _strip_sql_comments(select_sql).strip().upper()

    if not upper.startswith("SELECT"):
        raise InvalidParameterError(
            f"dm_explain_plan 仅接受 SELECT 语句，不接受: {select_sql[:50]}..."
        )

    # 检查危险关键字
    dangerous_keywords = [
        "DROP", "DELETE", "UPDATE", "INSERT", "CREATE", "ALTER",
        "EXEC", "EXECUTE", "TRUNCATE", "MERGE", "GRANT", "REVOKE"
    ]
    for keyword in dangerous_keywords:
        if __import__("re").search(rf"\b{keyword}\b", upper):
            raise InvalidParameterError(
                f"检测到危险的 SQL 关键字 '{keyword}'，dm_explain_plan 不允许此操作"
            )

    # 当前真实达梦环境支持 EXPLAIN 直返计划文本，优先走直接路径。
    explain_sql = f"EXPLAIN {select_sql.strip()}"

    # 在同一 session 中执行
    with get_database_client() as client:
        result = client.execute_explain_plan(explain_sql)
        execution_time = time.time() - start_time
        additional_info = {
            "statement_type": "EXPLAIN_PLAN",
            "query_type": "EXPLAIN_PLAN",
            "original_sql": select_sql,
            "execution_statement_type": "EXPLAIN",
            "diagnostic_path": "DIRECT_EXPLAIN",
        }
        plan_row_count = result.get("plan_table_row_count")
        if plan_row_count is not None:
            additional_info["plan_table_row_count"] = plan_row_count

        return {
            "success": True,
            "data": result,
            "sql": explain_sql,
            "metadata": create_response_metadata(
                operation="dm_explain_plan",
                success=True,
                execution_time=execution_time,
                row_count=len(result.get("rows", [])),
                additional_info=additional_info,
            )
        }
