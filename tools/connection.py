"""
连接工具模块

提供数据库连接测试功能
"""

import time
from typing import Dict, Any

from core import (
    DatabaseConnectionError,
    create_response_metadata,
    mcp_tool_handler,
)
from dm_client import DmClient, DmConfig


def get_dm_config() -> DmConfig:
    """从配置文件获取达梦数据库配置"""
    return DmConfig.from_config_file()


def get_database_client() -> DmClient:
    """获取数据库客户端实例"""
    config = get_dm_config()
    return DmClient(config)


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

    # 使用上下文管理器进行正确的连接管理
    with get_database_client() as client:
        if not client.connect():
            raise DatabaseConnectionError("无法建立数据库连接")

        # 执行简单的测试查询以验证连接是否正常工作
        test_result = client.execute_query("SELECT 1 AS test_value FROM DUAL")
        execution_time = time.time() - start_time

        if test_result and len(test_result) > 0:
            return {
                "success": True,
                "message": "数据库连接成功且响应正常",
                "test_query_result": test_result[0],
                "metadata": create_response_metadata(
                    operation="dm_connect",
                    success=True,
                    execution_time=execution_time
                )
            }
        else:
            raise DatabaseConnectionError("连接已建立但测试查询失败")
