"""
模式工具模块

提供数据库模式相关操作（表、视图等）
"""

import time
from typing import Dict, Any, Optional

from core import (
    DatabaseConnectionError,
    validate_identifier,
    validate_optional_schema,
    create_response_metadata,
    mcp_tool_handler,
)
from db import DmClient, DmConfig


def get_database_client() -> DmClient:
    """获取数据库客户端实例"""
    return DmClient(DmConfig.from_config_file())


@mcp_tool_handler("dm_list_tables")
def dm_list_tables(schema: Optional[str] = None) -> Dict[str, Any]:
    """
    列出数据库表，可按模式过滤。

    ⚠️ 达梦数据库大小写敏感: schema名称必须使用用户提供的确切大小写，不要转换。

    Args:
        schema: 模式名称过滤器（可选，大小写敏感）

    Returns:
        dict: {success, data, schema, metadata} 或 {success, error, schema, metadata}
              error_type: validation_error | connection_error | unexpected_error
    """
    start_time = time.time()

    # 验证可选的 schema 参数
    validated_schema = validate_optional_schema(schema)

    # 使用上下文管理器进行正确的连接管理
    # 注意：__enter__ 已经调用了 is_connected()，不需要再次调用
    with get_database_client() as client:
        result = client.list_tables(validated_schema)
        execution_time = time.time() - start_time

        return {
            "success": True,
            "data": result,
            "schema": validated_schema,
            "metadata": create_response_metadata(
                operation="dm_list_tables",
                success=True,
                execution_time=execution_time,
                row_count=len(result),
                additional_info={"schema_filtered": validated_schema is not None}
            )
        }


@mcp_tool_handler("dm_list_views")
def dm_list_views(schema: Optional[str] = None) -> Dict[str, Any]:
    """
    列出数据库视图，可按模式过滤。

    ⚠️ 达梦数据库大小写敏感: schema名称必须使用用户提供的确切大小写，不要转换。

    Args:
        schema: 模式名称过滤器（可选，大小写敏感）

    Returns:
        dict: {success, data, schema, metadata} 或 {success, error, schema, metadata}
              error_type: validation_error | connection_error | unexpected_error
    """
    start_time = time.time()

    # 验证可选的 schema 参数
    validated_schema = validate_optional_schema(schema)

    # 使用上下文管理器进行正确的连接管理
    # 注意：__enter__ 已经调用了 is_connected()，不需要再次调用
    with get_database_client() as client:
        result = client.list_views(validated_schema)
        execution_time = time.time() - start_time

        return {
            "success": True,
            "data": result,
            "schema": validated_schema,
            "metadata": create_response_metadata(
                operation="dm_list_views",
                success=True,
                execution_time=execution_time,
                row_count=len(result),
                additional_info={"schema_filtered": validated_schema is not None}
            )
        }


@mcp_tool_handler("dm_describe_table")
def dm_describe_table(table_name: str, schema: Optional[str] = None) -> Dict[str, Any]:
    """
    获取表的详细结构信息，包括列定义、数据类型、约束等。

    ⚠️ 达梦数据库大小写敏感: table_name和schema必须使用用户提供的确切大小写，不要转换。

    Args:
        table_name: 表名（必需，大小写敏感）
        schema: 模式名称（可选，大小写敏感）

    Returns:
        dict: {success, data, table_name, schema, metadata} 或 {success, error, ...}
              data包含: COLUMN_NAME, DATA_TYPE, DATA_LENGTH, NULLABLE, COLUMN_ID等
              error_type: validation_error | connection_error | unexpected_error
    """
    start_time = time.time()

    # 验证必需的 table_name 参数
    validated_table_name = validate_identifier(table_name, "table name")

    # 验证可选的 schema 参数
    validated_schema = validate_optional_schema(schema)

    # 使用上下文管理器进行正确的连接管理
    # 注意：__enter__ 已经调用了 is_connected()，不需要再次调用
    with get_database_client() as client:
        result = client.describe_table(validated_table_name, validated_schema)
        execution_time = time.time() - start_time

        return {
            "success": True,
            "data": result,
            "table_name": validated_table_name,
            "schema": validated_schema,
            "metadata": create_response_metadata(
                operation="dm_describe_table",
                success=True,
                execution_time=execution_time,
                row_count=len(result),
                additional_info={
                    "table_name": validated_table_name,
                    "schema": validated_schema
                }
            )
        }


@mcp_tool_handler("dm_get_view_definition")
def dm_get_view_definition(view_name: str, schema: Optional[str] = None) -> Dict[str, Any]:
    """
    获取视图的完整 CREATE VIEW 语句和SQL定义。

    ⚠️ 达梦数据库大小写敏感: view_name和schema必须使用用户提供的确切大小写，不要转换。

    Args:
        view_name: 视图名（必需，大小写敏感）
        schema: 模式名称（可选，大小写敏感）

    Returns:
        dict: {success, data, view_name, schema, metadata} 或 {success, error, ...}
              data包含: VIEW_DEF (完整的CREATE VIEW语句)
              error_type: validation_error | connection_error | unexpected_error
    """
    start_time = time.time()

    # 验证必需的 view_name 参数
    validated_view_name = validate_identifier(view_name, "view name")

    # 验证可选的 schema 参数
    validated_schema = validate_optional_schema(schema)

    # 使用上下文管理器进行正确的连接管理
    # 注意：__enter__ 已经调用了 is_connected()，不需要再次调用
    with get_database_client() as client:
        result = client.get_view_definition(validated_view_name, validated_schema)
        execution_time = time.time() - start_time

        return {
            "success": True,
            "data": result,
            "view_name": validated_view_name,
            "schema": validated_schema,
            "metadata": create_response_metadata(
                operation="dm_get_view_definition",
                success=True,
                execution_time=execution_time,
                row_count=len(result),
                additional_info={
                    "view_name": validated_view_name,
                    "schema": validated_schema
                }
            )
        }
