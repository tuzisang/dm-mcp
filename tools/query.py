"""
查询工具模块

提供 SQL 查询执行功能
"""

import time
from typing import Dict, Any

from core import (
    DatabaseConnectionError,
    validate_sql_query,
    create_response_metadata,
    mcp_tool_handler,
    mcp_cache,
)
from db import DmClient, DmConfig


def get_database_client() -> DmClient:
    """获取数据库客户端实例"""
    return DmClient(DmConfig.from_config_file())


@mcp_cache()
@mcp_tool_handler("dm_query")
def dm_query(sql: str) -> Dict[str, Any]:
    """
    执行安全的 SELECT 查询！

    ⚠️ 达梦数据库双引号规则:
    - 模式名、表名、字段名需要用双引号包裹才能识别大小写
    - 不用双引号会自动转为大写
    - 示例: SELECT * FROM "aiops"."TASK_HANDLE_WORKORDER"

    Args:
        sql: SQL SELECT 查询语句（仅允许SELECT，禁止其他操作）

    Returns:
        dict: {success, data, sql, metadata} 或 {success, error, sql, metadata}
    """
    start_time = time.time()

    # 验证 SQL 查询的安全性
    validated_sql = validate_sql_query(sql)

    # 使用上下文管理器进行正确的连接管理
    # 注意：__enter__ 已经调用了 connect()，不需要再次调用
    with get_database_client() as client:
        # 检查连接是否成功（__enter__ 中已连接）
        if not client.connection:
            raise DatabaseConnectionError("无法连接到达梦数据库")

        result = client.execute_query(validated_sql)
        execution_time = time.time() - start_time

        return {
            "success": True,
            "data": result,
            "sql": validated_sql,
            "metadata": create_response_metadata(
                operation="dm_query",
                success=True,
                execution_time=execution_time,
                row_count=len(result),
                additional_info={"query_type": "SELECT"}
            )
        }
