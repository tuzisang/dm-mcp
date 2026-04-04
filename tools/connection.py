"""
连接工具模块

提供数据库连接测试功能
"""

import time
from typing import Dict, Any

from core.decorators import mcp_tool_handler
from core.exceptions import DatabaseConnectionError
from core.response import create_response_metadata
from db.client import get_shared_client


def _first_row_as_dict(result: Dict[str, Any]) -> Dict[str, Any]:
    """将统一查询结果中的首行转换为便于阅读的字典。"""
    columns = result.get("columns", [])
    rows = result.get("rows", [])
    if not rows:
        return {}

    return dict(zip(columns, rows[0]))


@mcp_tool_handler("dm_connect")
def dm_connect() -> Dict[str, Any]:
    """
    测试达梦数据库连接，验证网络、身份验证和基本查询响应。

    用途: 诊断连接问题、验证配置、检查数据库服务状态。

    Returns:
        dict: {success, message, test_query_result, metadata} 或 {success, error, message, metadata}
              error_type: connection_error | timeout_error | unexpected_error
    """
    start_time = time.time()

    client = get_shared_client()
    test_result = client.execute_query("SELECT 1 AS test_value FROM DUAL")
    execution_time = time.time() - start_time

    if test_result.get("rows"):
        return {
            "success": True,
            "message": "数据库连接成功且响应正常",
            "test_query_result": _first_row_as_dict(test_result),
            "metadata": create_response_metadata(
                operation="dm_connect",
                success=True,
                execution_time=execution_time
            )
        }

    raise DatabaseConnectionError("连接已建立但测试查询失败")
