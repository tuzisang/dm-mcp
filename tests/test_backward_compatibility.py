"""
向后兼容性测试

**Feature: mcp-refactor, Property 5: Response format backward compatibility**
**Validates: Requirements 5.1, 5.3**
"""

import pytest
from hypothesis import given, strategies as st, settings

from core import (
    InvalidParameterError,
    DatabaseConnectionError,
    create_response_metadata,
    create_success_response,
    create_error_response,
)
from core.decorators import mcp_tool_handler


class TestResponseFormatBackwardCompatibility:
    """测试响应格式向后兼容性"""

    def test_success_response_has_required_fields(self):
        """
        **Property 5: Response format backward compatibility**
        成功响应应包含所有必需字段
        """
        response = create_success_response(
            operation="dm_query",
            data=[{"id": 1}],
            execution_time=0.1,
            row_count=1
        )

        # 验证顶层字段
        assert "success" in response
        assert response["success"] is True
        assert "data" in response
        assert "metadata" in response

        # 验证元数据字段
        metadata = response["metadata"]
        assert "timestamp" in metadata
        assert "operation" in metadata
        assert "success" in metadata
        assert "execution_time_seconds" in metadata

    def test_error_response_has_required_fields(self):
        """
        **Property 5: Response format backward compatibility**
        错误响应应包含所有必需字段
        """
        response = create_error_response(
            operation="dm_query",
            error="测试错误",
            error_type="validation_error",
            execution_time=0.05
        )

        # 验证顶层字段
        assert "success" in response
        assert response["success"] is False
        assert "error" in response
        assert "metadata" in response

        # 验证元数据字段
        metadata = response["metadata"]
        assert "timestamp" in metadata
        assert "operation" in metadata
        assert "success" in metadata
        assert "execution_time_seconds" in metadata
        assert "error_type" in metadata

    def test_metadata_timestamp_is_float(self):
        """时间戳应为浮点数"""
        metadata = create_response_metadata("test", True, 0.1)
        assert isinstance(metadata["timestamp"], float)

    def test_metadata_execution_time_is_float(self):
        """执行时间应为浮点数"""
        metadata = create_response_metadata("test", True, 0.1234)
        assert isinstance(metadata["execution_time_seconds"], float)

    def test_error_type_values_match_original(self):
        """错误类型值应与原始实现匹配"""
        expected_error_types = [
            "validation_error",
            "connection_error",
            "pool_timeout_error",
            "pool_error",
            "runtime_error",
            "timeout_error",
            "unexpected_error",
        ]

        # 验证所有预期的错误类型都可以在响应中使用
        for error_type in expected_error_types:
            response = create_error_response(
                operation="test",
                error="test error",
                error_type=error_type,
                execution_time=0.1
            )
            assert response["metadata"]["error_type"] == error_type


class TestDecoratorBackwardCompatibility:
    """测试装饰器向后兼容性"""

    def test_validation_error_format(self):
        """验证错误格式应与原始实现匹配"""
        @mcp_tool_handler("dm_query")
        def raise_validation_error():
            raise InvalidParameterError("SQL 查询不能为空")

        result = raise_validation_error()

        assert result["success"] is False
        assert "error" in result
        assert "metadata" in result
        assert result["metadata"]["error_type"] == "validation_error"
        assert result["metadata"]["operation"] == "dm_query"

    def test_connection_error_format(self):
        """连接错误格式应与原始实现匹配"""
        @mcp_tool_handler("dm_connect")
        def raise_connection_error():
            raise DatabaseConnectionError("无法连接到达梦数据库")

        result = raise_connection_error()

        assert result["success"] is False
        assert "无法连接" in result["error"]
        assert result["metadata"]["error_type"] == "connection_error"

    def test_timeout_error_format(self):
        """超时错误格式应与原始实现匹配"""
        @mcp_tool_handler("dm_query")
        def raise_timeout():
            raise TimeoutError("获取连接超时（30秒）")

        result = raise_timeout()

        assert result["success"] is False
        assert "超时" in result["error"]
        assert result["metadata"]["error_type"] == "pool_timeout_error"


class TestResponseStructureProperty:
    """属性测试：响应结构"""

    @given(st.text(min_size=1, max_size=50))
    @settings(max_examples=100)
    def test_error_response_always_has_required_structure(self, error_msg: str):
        """
        **Property 5: Response format backward compatibility**
        所有错误响应都应有相同的结构
        """
        @mcp_tool_handler("test")
        def raise_error():
            raise ValueError(error_msg)

        result = raise_error()

        # 验证结构
        assert isinstance(result, dict)
        assert "success" in result
        assert "error" in result
        assert "metadata" in result

        # 验证元数据结构
        metadata = result["metadata"]
        assert isinstance(metadata, dict)
        assert "timestamp" in metadata
        assert "operation" in metadata
        assert "success" in metadata
        assert "execution_time_seconds" in metadata
        assert "error_type" in metadata

        # 验证类型
        assert isinstance(result["success"], bool)
        assert isinstance(result["error"], str)
        assert isinstance(metadata["timestamp"], float)
        assert isinstance(metadata["execution_time_seconds"], float)
        assert isinstance(metadata["error_type"], str)
