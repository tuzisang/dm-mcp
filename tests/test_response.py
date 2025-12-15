"""
响应构建器测试

**Validates: Requirements 2.3, 2.4**
"""

import pytest
import time

from core.response import (
    create_response_metadata,
    create_success_response,
    create_error_response,
)


class TestCreateResponseMetadata:
    """测试 create_response_metadata 函数"""

    def test_basic_metadata_fields(self):
        """元数据应包含所有必需字段"""
        metadata = create_response_metadata(
            operation="test_op",
            success=True,
            execution_time=0.5
        )

        assert "timestamp" in metadata
        assert metadata["operation"] == "test_op"
        assert metadata["success"] is True
        assert metadata["execution_time_seconds"] == 0.5

    def test_timestamp_is_recent(self):
        """时间戳应该是当前时间"""
        before = time.time()
        metadata = create_response_metadata("test", True)
        after = time.time()

        assert before <= metadata["timestamp"] <= after

    def test_row_count_included_when_provided(self):
        """提供 row_count 时应包含在元数据中"""
        metadata = create_response_metadata(
            operation="test",
            success=True,
            row_count=10
        )

        assert metadata["row_count"] == 10

    def test_row_count_excluded_when_none(self):
        """row_count 为 None 时不应包含在元数据中"""
        metadata = create_response_metadata(
            operation="test",
            success=True,
            row_count=None
        )

        assert "row_count" not in metadata

    def test_additional_info_merged(self):
        """additional_info 应合并到元数据中"""
        metadata = create_response_metadata(
            operation="test",
            success=True,
            additional_info={"custom_field": "value", "error_type": "test_error"}
        )

        assert metadata["custom_field"] == "value"
        assert metadata["error_type"] == "test_error"

    def test_execution_time_rounded(self):
        """执行时间应四舍五入到 4 位小数"""
        metadata = create_response_metadata(
            operation="test",
            success=True,
            execution_time=0.123456789
        )

        assert metadata["execution_time_seconds"] == 0.1235


class TestCreateSuccessResponse:
    """测试 create_success_response 函数"""

    def test_success_response_structure(self):
        """成功响应应有正确的结构"""
        response = create_success_response(
            operation="dm_query",
            data=[{"id": 1}],
            execution_time=0.1,
            row_count=1
        )

        assert response["success"] is True
        assert response["data"] == [{"id": 1}]
        assert "metadata" in response
        assert response["metadata"]["success"] is True
        assert response["metadata"]["operation"] == "dm_query"
        assert response["metadata"]["row_count"] == 1

    def test_extra_fields_included(self):
        """额外字段应包含在响应中"""
        response = create_success_response(
            operation="dm_query",
            data=[],
            execution_time=0.1,
            sql="SELECT 1"
        )

        assert response["sql"] == "SELECT 1"

    def test_additional_info_in_metadata(self):
        """additional_info 应包含在元数据中"""
        response = create_success_response(
            operation="dm_query",
            data=[],
            execution_time=0.1,
            additional_info={"query_type": "SELECT"}
        )

        assert response["metadata"]["query_type"] == "SELECT"


class TestCreateErrorResponse:
    """测试 create_error_response 函数"""

    def test_error_response_structure(self):
        """错误响应应有正确的结构"""
        response = create_error_response(
            operation="dm_query",
            error="测试错误",
            error_type="validation_error",
            execution_time=0.05
        )

        assert response["success"] is False
        assert response["error"] == "测试错误"
        assert "metadata" in response
        assert response["metadata"]["success"] is False
        assert response["metadata"]["error_type"] == "validation_error"

    def test_extra_fields_included(self):
        """额外字段应包含在响应中"""
        response = create_error_response(
            operation="dm_query",
            error="错误",
            error_type="validation_error",
            execution_time=0.1,
            sql="SELECT * FROM invalid"
        )

        assert response["sql"] == "SELECT * FROM invalid"

    def test_additional_info_merged_with_error_type(self):
        """additional_info 应与 error_type 合并"""
        response = create_error_response(
            operation="dm_query",
            error="错误",
            error_type="validation_error",
            execution_time=0.1,
            additional_info={"custom": "value"}
        )

        assert response["metadata"]["error_type"] == "validation_error"
        assert response["metadata"]["custom"] == "value"
