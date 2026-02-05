"""
装饰器基础测试
"""

import pytest
import time
from core.decorators import mcp_tool_handler
from core.exceptions import InvalidParameterError, DatabaseConnectionError


class TestMcpToolHandler:
    """测试 mcp_tool_handler 装饰器"""

    def test_successful_execution(self):
        @mcp_tool_handler("test_op")
        def success_func():
            return {"success": True, "data": [1, 2, 3], "metadata": {"operation": "test_op"}}

        result = success_func()
        assert result["success"] is True
        assert result["data"] == [1, 2, 3]

    def test_invalid_parameter_error(self):
        @mcp_tool_handler("test_op")
        def raise_invalid_param():
            raise InvalidParameterError("参数无效")

        result = raise_invalid_param()
        assert result["success"] is False
        assert "参数无效" in result["error"]
        assert result["metadata"]["error_type"] == "validation_error"

    def test_database_connection_error(self):
        @mcp_tool_handler("test_op")
        def raise_connection_error():
            raise DatabaseConnectionError("无法连接")

        result = raise_connection_error()
        assert result["success"] is False
        assert result["metadata"]["error_type"] == "connection_error"

    def test_timeout_error(self):
        @mcp_tool_handler("test_op")
        def raise_timeout():
            raise TimeoutError("连接超时")

        result = raise_timeout()
        assert result["success"] is False
        assert result["metadata"]["error_type"] == "pool_timeout_error"

    def test_generic_exception(self):
        @mcp_tool_handler("test_op")
        def raise_generic():
            raise ValueError("未知错误")

        result = raise_generic()
        assert result["success"] is False
        assert result["metadata"]["error_type"] == "unexpected_error"

    def test_metadata_contains_operation(self):
        @mcp_tool_handler("dm_query")
        def raise_error():
            raise InvalidParameterError("test")

        result = raise_error()
        assert result["metadata"]["operation"] == "dm_query"
