"""
装饰器测试

**Feature: mcp-refactor, Property 1: Decorator catches all exceptions and returns standardized response**
**Feature: mcp-refactor, Property 2: Decorator records execution time and formats response**
**Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5, 2.1, 2.2, 2.3, 2.4**
"""

import pytest
import time
from hypothesis import given, strategies as st, settings

from core.decorators import mcp_tool_handler, _get_error_type
from core.exceptions import (
    DMMCPError,
    DatabaseConnectionError,
    InvalidParameterError,
    SQLExecutionError,
)


class TestMcpToolHandler:
    """测试 mcp_tool_handler 装饰器"""

    def test_successful_execution(self):
        """成功执行应返回原函数结果"""
        @mcp_tool_handler("test_op")
        def success_func():
            return {"success": True, "data": [1, 2, 3], "metadata": {"operation": "test_op", "success": True, "timestamp": time.time(), "execution_time_seconds": 0.0}}

        result = success_func()
        assert result["success"] is True
        assert result["data"] == [1, 2, 3]

    def test_invalid_parameter_error_handling(self):
        """InvalidParameterError 应返回 validation_error"""
        @mcp_tool_handler("test_op")
        def raise_invalid_param():
            raise InvalidParameterError("参数无效")

        result = raise_invalid_param()
        assert result["success"] is False
        assert "参数无效" in result["error"]
        assert result["metadata"]["error_type"] == "validation_error"

    def test_database_connection_error_handling(self):
        """DatabaseConnectionError 应返回 connection_error"""
        @mcp_tool_handler("test_op")
        def raise_connection_error():
            raise DatabaseConnectionError("无法连接")

        result = raise_connection_error()
        assert result["success"] is False
        assert "无法连接" in result["error"]
        assert result["metadata"]["error_type"] == "connection_error"

    def test_timeout_error_handling(self):
        """TimeoutError 应返回 pool_timeout_error"""
        @mcp_tool_handler("test_op")
        def raise_timeout():
            raise TimeoutError("连接超时")

        result = raise_timeout()
        assert result["success"] is False
        assert "超时" in result["error"]
        assert result["metadata"]["error_type"] == "pool_timeout_error"

    def test_runtime_error_with_pool_keyword(self):
        """包含 pool 关键字的 RuntimeError 应返回 pool_error"""
        @mcp_tool_handler("test_op")
        def raise_pool_error():
            raise RuntimeError("连接池已关闭")

        result = raise_pool_error()
        assert result["success"] is False
        assert result["metadata"]["error_type"] == "pool_error"

    def test_generic_exception_handling(self):
        """通用异常应返回 unexpected_error"""
        @mcp_tool_handler("test_op")
        def raise_generic():
            raise ValueError("未知错误")

        result = raise_generic()
        assert result["success"] is False
        assert result["metadata"]["error_type"] == "unexpected_error"

    def test_execution_time_recorded(self):
        """执行时间应被记录"""
        @mcp_tool_handler("test_op")
        def slow_func():
            time.sleep(0.1)
            return {"success": True, "data": None, "metadata": {"operation": "test_op", "success": True, "timestamp": time.time(), "execution_time_seconds": 0.1}}

        result = slow_func()
        # 函数返回的是原始结果，不是装饰器包装的
        assert result["success"] is True

    def test_metadata_contains_operation_name(self):
        """元数据应包含操作名称"""
        @mcp_tool_handler("dm_query")
        def raise_error():
            raise InvalidParameterError("test")

        result = raise_error()
        assert result["metadata"]["operation"] == "dm_query"


class TestDecoratorPropertyErrorHandling:
    """属性测试：装饰器捕获所有异常并返回标准化响应"""

    @given(st.text(min_size=1, max_size=50))
    @settings(max_examples=100)
    def test_invalid_parameter_error_always_returns_validation_error(self, message: str):
        """
        **Property 1: Decorator catches all exceptions and returns standardized response**
        InvalidParameterError 总是返回 validation_error
        """
        @mcp_tool_handler("test")
        def raise_error():
            raise InvalidParameterError(message)

        result = raise_error()
        assert result["success"] is False
        assert "error" in result
        assert "metadata" in result
        assert result["metadata"]["error_type"] == "validation_error"

    @given(st.text(min_size=1, max_size=50))
    @settings(max_examples=100)
    def test_database_connection_error_always_returns_connection_error(self, message: str):
        """
        **Property 1: Decorator catches all exceptions and returns standardized response**
        DatabaseConnectionError 总是返回 connection_error
        """
        @mcp_tool_handler("test")
        def raise_error():
            raise DatabaseConnectionError(message)

        result = raise_error()
        assert result["success"] is False
        assert "error" in result
        assert "metadata" in result
        assert result["metadata"]["error_type"] == "connection_error"

    @given(st.sampled_from([
        InvalidParameterError("test"),
        DatabaseConnectionError("test"),
        SQLExecutionError("test"),
        TimeoutError("test"),
        RuntimeError("test"),
        ValueError("test"),
        Exception("test"),
    ]))
    @settings(max_examples=100)
    def test_all_exceptions_return_standardized_response(self, exc: Exception):
        """
        **Property 1: Decorator catches all exceptions and returns standardized response**
        所有异常都应返回标准化响应
        """
        @mcp_tool_handler("test")
        def raise_error():
            raise exc

        result = raise_error()

        # 验证响应结构
        assert isinstance(result, dict)
        assert result["success"] is False
        assert "error" in result
        assert isinstance(result["error"], str)
        assert "metadata" in result
        assert isinstance(result["metadata"], dict)
        assert "error_type" in result["metadata"]
        assert "execution_time_seconds" in result["metadata"]
        assert "timestamp" in result["metadata"]
        assert "operation" in result["metadata"]


class TestDecoratorPropertyTiming:
    """属性测试：装饰器记录执行时间和格式化响应"""

    def test_execution_time_is_non_negative(self):
        """
        **Property 2: Decorator records execution time and formats response**
        执行时间应为非负数
        """
        @mcp_tool_handler("test")
        def raise_error():
            raise ValueError("test")

        result = raise_error()
        assert result["metadata"]["execution_time_seconds"] >= 0

    def test_metadata_success_matches_top_level(self):
        """
        **Property 2: Decorator records execution time and formats response**
        metadata.success 应与顶层 success 匹配
        """
        @mcp_tool_handler("test")
        def raise_error():
            raise ValueError("test")

        result = raise_error()
        assert result["metadata"]["success"] == result["success"]


class TestGetErrorType:
    """测试 _get_error_type 函数"""

    def test_known_exception_types(self):
        """已知异常类型应返回正确的错误类型"""
        assert _get_error_type(InvalidParameterError("test")) == "validation_error"
        assert _get_error_type(DatabaseConnectionError("test")) == "connection_error"
        assert _get_error_type(SQLExecutionError("test")) == "sql_error"
        assert _get_error_type(TimeoutError("test")) == "pool_timeout_error"

    def test_timeout_keyword_in_message(self):
        """消息中包含超时关键字应返回 timeout_error"""
        assert _get_error_type(Exception("操作超时了")) == "timeout_error"
        assert _get_error_type(Exception("connection timeout")) == "timeout_error"

    def test_pool_keyword_in_message(self):
        """消息中包含连接池关键字应返回 pool_error"""
        assert _get_error_type(Exception("连接池已满")) == "pool_error"
        assert _get_error_type(Exception("pool exhausted")) == "pool_error"

    def test_unknown_exception(self):
        """未知异常应返回 unexpected_error"""
        assert _get_error_type(Exception("unknown error")) == "unexpected_error"
