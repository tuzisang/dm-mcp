  
"""
达梦数据库 MCP 服务器

这是一个基于 FastMCP 框架构建的达梦数据库 MCP 服务器，提供数据库连接和查询工具。
该服务器提供全面的数据库操作功能，包括表管理、视图检查和带有参数验证的安全 SQL 执行。

使用方法:
    python main.py

依赖项:
    - dmPython: 达梦数据库 Python 驱动
    - FastMCP: MCP 服务器框架

数据库配置:
    - 主机: localhost
    - 端口: 5236
    - 用户: SYSDBA
    - 密码: SYSDBA
    (请根据您的环境修改配置)
"""

import re
import time
from typing import Dict, Any, Optional, List
from mcp.server.fastmcp import FastMCP
from dm_client import DmClient, DmConfig
from config import get_database_config, get_config_manager


# 自定义异常类，用于更好的错误处理
class DMMCPError(Exception):
    """达梦数据库 MCP 操作的基础异常类"""
    pass


class DatabaseConnectionError(DMMCPError):
    """数据库连接失败时抛出的异常"""
    pass


class InvalidParameterError(DMMCPError):
    """输入参数无效时抛出的异常"""
    pass


class SQLExecutionError(DMMCPError):
    """SQL 执行失败时抛出的异常"""
    pass


# 创建一个带有增强元数据的 MCP 服务器
mcp = FastMCP("DM Database MCP Server")


def get_dm_config() -> DmConfig:
    """从配置文件获取达梦数据库配置"""
    return DmConfig.from_config_file()


def validate_identifier(identifier: str, identifier_type: str = "identifier") -> str:
    """
    验证数据库标识符（表名、模式名等）

    Args:
        identifier: 要验证的标识符
        identifier_type: 标识符类型，用于错误消息

    Returns:
        str: 清理并验证过的标识符

    Raises:
        InvalidParameterError: 如果标识符包含无效字符
    """
    if not identifier or not identifier.strip():
        raise InvalidParameterError(f"{identifier_type} 不能为空")

    identifier = identifier.strip()

    # 检查 SQL 注入模式
    dangerous_patterns = [
        r"[;'\"]",  # SQL 注入字符
        r"\b(DROP|DELETE|INSERT|UPDATE|CREATE|ALTER|EXEC)\b",  # SQL 关键字
        r"--",  # SQL 注释
        r"/\*.*?\*/",  # SQL 块注释
    ]

    for pattern in dangerous_patterns:
        if re.search(pattern, identifier, re.IGNORECASE):
            raise InvalidParameterError(f"{identifier_type} 包含无效字符或 SQL 关键字")

    # 检查长度限制（典型数据库限制）
    if len(identifier) > 128:
        raise InvalidParameterError(f"{identifier_type} 过长（最多 128 个字符）")

    # 检查有效的标识符模式（字母、数字、下划线）
    if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", identifier):
        raise InvalidParameterError(f"{identifier_type} 必须以字母或下划线开头，且只能包含字母、数字和下划线")

    return identifier


def validate_sql_query(sql: str) -> str:
    """
    验证 SQL 查询的安全性

    Args:
        sql: SQL 查询字符串

    Returns:
        str: 验证过的 SQL 查询

    Raises:
        InvalidParameterError: 如果 SQL 查询无效或存在潜在危险
    """
    if not sql or not sql.strip():
        raise InvalidParameterError("SQL 查询不能为空")

    sql = sql.strip()

    # 查询的基本 SQL 注入保护
    # 为安全起见，只允许 SELECT 查询
    if not re.match(r"^\s*SELECT\s", sql, re.IGNORECASE):
        raise InvalidParameterError("出于安全考虑，只允许 SELECT 查询")

    # 检查潜在的危险操作
    dangerous_keywords = [
        "DROP", "DELETE", "UPDATE", "INSERT", "CREATE", "ALTER",
        "EXEC", "EXECUTE", "TRUNCATE", "MERGE", "GRANT", "REVOKE"
    ]

    for keyword in dangerous_keywords:
        if re.search(rf"\b{keyword}\b", sql, re.IGNORECASE):
            raise InvalidParameterError(f"检测到危险的 SQL 关键字 '{keyword}'")

    return sql


def get_database_client() -> DmClient:
    """
    获取数据库客户端实例（应使用上下文管理器以确保正确清理）

    Returns:
        DmClient: 数据库客户端实例
    """
    config = get_dm_config()
    return DmClient(config)


def create_response_metadata(
    operation: str,
    success: bool,
    execution_time: float = 0.0,
    row_count: int = None,
    additional_info: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    创建标准化的响应元数据

    Args:
        operation: 执行的操作名称
        success: 操作是否成功
        execution_time: 操作执行时间（秒）
        row_count: 受影响/返回的行数（如适用）
        additional_info: 要包含的其他元数据

    Returns:
        Dict[str, Any]: 标准化的元数据字典
    """
    metadata = {
        "timestamp": time.time(),
        "operation": operation,
        "success": success,
        "execution_time_seconds": round(execution_time, 4)
    }

    if row_count is not None:
        metadata["row_count"] = row_count

    if additional_info:
        metadata.update(additional_info)

    return metadata




# 添加达梦数据库查询工具
@mcp.tool()
def dm_query(sql: str) -> dict:
    """
    执行安全的 SELECT 查询。

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

    try:
        # 验证 SQL 查询的安全性
        validated_sql = validate_sql_query(sql)

        # 使用上下文管理器进行正确的连接管理
        with get_database_client() as client:
            if not client.connect():
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

    except InvalidParameterError as e:
        return {
            "success": False,
            "error": f"无效的 SQL 查询: {str(e)}",
            "sql": sql,
            "metadata": create_response_metadata(
                operation="dm_query",
                success=False,
                execution_time=time.time() - start_time,
                additional_info={"error_type": "validation_error"}
            )
        }
    except (DatabaseConnectionError, SQLExecutionError) as e:
        return {
            "success": False,
            "error": str(e),
            "sql": sql,
            "metadata": create_response_metadata(
                operation="dm_query",
                success=False,
                execution_time=time.time() - start_time,
                additional_info={"error_type": type(e).__name__}
            )
        }
    except TimeoutError as e:
        # 连接池获取连接超时
        return {
            "success": False,
            "error": f"获取数据库连接超时: {str(e)}",
            "sql": sql,
            "metadata": create_response_metadata(
                operation="dm_query",
                success=False,
                execution_time=time.time() - start_time,
                additional_info={"error_type": "pool_timeout_error"}
            )
        }
    except RuntimeError as e:
        # 连接池已关闭等运行时错误
        error_msg = str(e)
        if "连接池" in error_msg or "pool" in error_msg.lower():
            error_type = "pool_error"
        else:
            error_type = "runtime_error"
        return {
            "success": False,
            "error": f"运行时错误: {error_msg}",
            "sql": sql,
            "metadata": create_response_metadata(
                operation="dm_query",
                success=False,
                execution_time=time.time() - start_time,
                additional_info={"error_type": error_type}
            )
        }
    except Exception as e:
        # 检查是否是超时错误
        error_msg = str(e)
        if "超时" in error_msg or "timeout" in error_msg.lower():
            error_type = "timeout_error"
            error_description = f"查询超时: {error_msg}"
        elif "连接池" in error_msg or "pool" in error_msg.lower():
            error_type = "pool_error"
            error_description = f"连接池错误: {error_msg}"
        else:
            error_type = "unexpected_error"
            error_description = f"查询执行过程中发生意外错误: {error_msg}"
        
        return {
            "success": False,
            "error": error_description,
            "sql": sql,
            "metadata": create_response_metadata(
                operation="dm_query",
                success=False,
                execution_time=time.time() - start_time,
                additional_info={"error_type": error_type}
            )
        }


# 添加达梦数据库连接测试工具
@mcp.tool()
def dm_connect() -> dict:
    """
    测试达梦数据库连接，验证网络、身份验证和基本查询响应。

    用途: 诊断连接问题、验证配置、检查数据库服务状态。

    Returns:
        dict: {success, message, test_query_result, metadata} 或 {success, error, message, metadata}
              error_type: connection_error | timeout_error | unexpected_error
    """
    start_time = time.time()

    try:
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

    except DatabaseConnectionError as e:
        return {
            "success": False,
            "error": str(e),
            "message": "数据库连接测试失败",
            "metadata": create_response_metadata(
                operation="dm_connect",
                success=False,
                execution_time=time.time() - start_time,
                additional_info={"error_type": "connection_error"}
            )
        }
    except TimeoutError as e:
        return {
            "success": False,
            "error": f"获取数据库连接超时: {str(e)}",
            "message": "数据库连接测试失败（连接池超时）",
            "metadata": create_response_metadata(
                operation="dm_connect",
                success=False,
                execution_time=time.time() - start_time,
                additional_info={"error_type": "pool_timeout_error"}
            )
        }
    except Exception as e:
        # 检查是否是超时错误或连接池错误
        error_msg = str(e)
        if "超时" in error_msg or "timeout" in error_msg.lower():
            error_type = "timeout_error"
            error_description = f"连接测试超时: {error_msg}"
        elif "连接池" in error_msg or "pool" in error_msg.lower():
            error_type = "pool_error"
            error_description = f"连接池错误: {error_msg}"
        else:
            error_type = "unexpected_error"
            error_description = f"连接测试过程中发生意外错误: {error_msg}"
        
        return {
            "success": False,
            "error": error_description,
            "message": "数据库连接测试失败",
            "metadata": create_response_metadata(
                operation="dm_connect",
                success=False,
                execution_time=time.time() - start_time,
                additional_info={"error_type": error_type}
            )
        }


# 添加达梦数据库列表工具
@mcp.tool()
def dm_list_tables(schema: str = None) -> dict:
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

    try:
        # 如果提供了模式参数，则验证它
        validated_schema = None
        if schema is not None and schema.strip():
            validated_schema = validate_identifier(schema.strip(), "schema name")

        # 使用上下文管理器进行正确的连接管理
        with get_database_client() as client:
            if not client.connect():
                raise DatabaseConnectionError("无法连接到达梦数据库")

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

    except InvalidParameterError as e:
        return {
            "success": False,
            "error": str(e),
            "schema": schema,
            "metadata": create_response_metadata(
                operation="dm_list_tables",
                success=False,
                execution_time=time.time() - start_time,
                additional_info={"error_type": "validation_error"}
            )
        }
    except DatabaseConnectionError as e:
        return {
            "success": False,
            "error": str(e),
            "schema": schema,
            "metadata": create_response_metadata(
                operation="dm_list_tables",
                success=False,
                execution_time=time.time() - start_time,
                additional_info={"error_type": "connection_error"}
            )
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"列表表时发生意外错误: {str(e)}",
            "schema": schema,
            "metadata": create_response_metadata(
                operation="dm_list_tables",
                success=False,
                execution_time=time.time() - start_time,
                additional_info={"error_type": "unexpected_error"}
            )
        }


# 添加达梦数据库视图列表工具
@mcp.tool()
def dm_list_views(schema: str = None) -> dict:
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

    try:
        # 如果提供了模式参数，则验证它
        validated_schema = None
        if schema is not None and schema.strip():
            validated_schema = validate_identifier(schema.strip(), "schema name")

        # 使用上下文管理器进行正确的连接管理
        with get_database_client() as client:
            if not client.connect():
                raise DatabaseConnectionError("无法连接到达梦数据库")

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

    except InvalidParameterError as e:
        return {
            "success": False,
            "error": str(e),
            "schema": schema,
            "metadata": create_response_metadata(
                operation="dm_list_views",
                success=False,
                execution_time=time.time() - start_time,
                additional_info={"error_type": "validation_error"}
            )
        }
    except DatabaseConnectionError as e:
        return {
            "success": False,
            "error": str(e),
            "schema": schema,
            "metadata": create_response_metadata(
                operation="dm_list_views",
                success=False,
                execution_time=time.time() - start_time,
                additional_info={"error_type": "connection_error"}
            )
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"列视图时发生意外错误: {str(e)}",
            "schema": schema,
            "metadata": create_response_metadata(
                operation="dm_list_views",
                success=False,
                execution_time=time.time() - start_time,
                additional_info={"error_type": "unexpected_error"}
            )
        }


# 添加达梦数据库表描述工具
@mcp.tool()
def dm_describe_table(table_name: str, schema: str = None) -> dict:
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

    try:
        # 验证必需的 table_name 参数
        validated_table_name = validate_identifier(table_name, "table name")

        # 如果提供了可选的模式参数，则验证它
        validated_schema = None
        if schema is not None and schema.strip():
            validated_schema = validate_identifier(schema.strip(), "schema name")

        # 使用上下文管理器进行正确的连接管理
        with get_database_client() as client:
            if not client.connect():
                raise DatabaseConnectionError("无法连接到达梦数据库")

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

    except InvalidParameterError as e:
        return {
            "success": False,
            "error": str(e),
            "table_name": table_name,
            "schema": schema,
            "metadata": create_response_metadata(
                operation="dm_describe_table",
                success=False,
                execution_time=time.time() - start_time,
                additional_info={"error_type": "validation_error"}
            )
        }
    except DatabaseConnectionError as e:
        return {
            "success": False,
            "error": str(e),
            "table_name": table_name,
            "schema": schema,
            "metadata": create_response_metadata(
                operation="dm_describe_table",
                success=False,
                execution_time=time.time() - start_time,
                additional_info={"error_type": "connection_error"}
            )
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"描述表时发生意外错误: {str(e)}",
            "table_name": table_name,
            "schema": schema,
            "metadata": create_response_metadata(
                operation="dm_describe_table",
                success=False,
                execution_time=time.time() - start_time,
                additional_info={"error_type": "unexpected_error"}
            )
        }


# 添加达梦数据库获取视图定义工具
@mcp.tool()
def dm_get_view_definition(view_name: str, schema: str = None) -> dict:
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

    try:
        # 验证必需的 view_name 参数
        validated_view_name = validate_identifier(view_name, "view name")

        # 如果提供了可选的模式参数，则验证它
        validated_schema = None
        if schema is not None and schema.strip():
            validated_schema = validate_identifier(schema.strip(), "schema name")

        # 使用上下文管理器进行正确的连接管理
        with get_database_client() as client:
            if not client.connect():
                raise DatabaseConnectionError("无法连接到达梦数据库")

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

    except InvalidParameterError as e:
        return {
            "success": False,
            "error": str(e),
            "view_name": view_name,
            "schema": schema,
            "metadata": create_response_metadata(
                operation="dm_get_view_definition",
                success=False,
                execution_time=time.time() - start_time,
                additional_info={"error_type": "validation_error"}
            )
        }
    except DatabaseConnectionError as e:
        return {
            "success": False,
            "error": str(e),
            "view_name": view_name,
            "schema": schema,
            "metadata": create_response_metadata(
                operation="dm_get_view_definition",
                success=False,
                execution_time=time.time() - start_time,
                additional_info={"error_type": "connection_error"}
            )
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"获取视图定义时发生意外错误: {str(e)}",
            "view_name": view_name,
            "schema": schema,
            "metadata": create_response_metadata(
                operation="dm_get_view_definition",
                success=False,
                execution_time=time.time() - start_time,
                additional_info={"error_type": "unexpected_error"}
            )
        }




# 添加达梦数据库配置更新工具
@mcp.tool()
def dm_update_config(host: str = None, port: int = None, user: str = None,
                    password: str = None, schema: str = None,
                    query_timeout: int = None, retry_attempts: int = None,
                    retry_delay: int = None) -> dict:
    """
    修改数据库连接参数并保存到 dm_config.json 配置文件。

    ⚠️ 配置持久化: 修改后需重启服务器生效，只修改提供的参数，其他保持不变。

    Args:
        host: 数据库主机地址（IP或主机名）
        port: 端口号（1-65535）
        user: 用户名
        password: 密码
        schema: 默认模式名称
        query_timeout: 查询超时秒数（1-3600）
        retry_attempts: 重试次数（0-10）
        retry_delay: 重试延迟秒数（0-60）

    Returns:
        dict: {success, message, updated_fields, current_config, config_file, metadata}
              error_type: validation_error | file_error | update_error | unexpected_error
    """
    start_time = time.time()

    try:
        # 获取配置管理器
        config_manager = get_config_manager()

        # 记录要更新的字段
        updated_fields = []
        validation_errors = []

        # 验证并处理主机地址
        if host is not None:
            if not host or not host.strip():
                validation_errors.append("主机地址不能为空")
            else:
                host = host.strip()
                # 简单的主机名/IP验证
                if len(host) > 255:
                    validation_errors.append("主机地址过长（最多255个字符）")
                else:
                    updated_fields.append("host")

        # 验证并处理端口号
        if port is not None:
            if not isinstance(port, int):
                try:
                    port = int(port)
                except (ValueError, TypeError):
                    validation_errors.append("端口号必须是整数")
            else:
                if not (1 <= port <= 65535):
                    validation_errors.append("端口号必须在1-65535范围内")
                else:
                    updated_fields.append("port")

        # 验证并处理用户名
        if user is not None:
            if not user or not user.strip():
                validation_errors.append("用户名不能为空")
            else:
                user = user.strip()
                if len(user) > 128:
                    validation_errors.append("用户名过长（最多128个字符）")
                elif not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", user):
                    validation_errors.append("用户名必须以字母或下划线开头，且只能包含字母、数字和下划线")
                else:
                    updated_fields.append("user")

        # 验证并处理密码
        if password is not None:
            if password is None or password == "":
                validation_errors.append("密码不能为空")
            else:
                if len(str(password)) > 256:
                    validation_errors.append("密码过长（最多256个字符）")
                else:
                    updated_fields.append("password")

        # 验证并处理模式名
        if schema is not None:
            if schema is not None and schema.strip():
                schema = schema.strip()
                if len(schema) > 128:
                    validation_errors.append("模式名过长（最多128个字符）")
                elif not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", schema):
                    validation_errors.append("模式名必须以字母或下划线开头，且只能包含字母、数字和下划线")
                else:
                    updated_fields.append("schema")
            elif schema == "":
                # 允许设置为空字符串
                updated_fields.append("schema")

        # 验证并处理查询超时时间
        if query_timeout is not None:
            if not isinstance(query_timeout, int):
                try:
                    query_timeout = int(query_timeout)
                except (ValueError, TypeError):
                    validation_errors.append("查询超时时间必须是整数")
            else:
                if not (1 <= query_timeout <= 3600):
                    validation_errors.append("查询超时时间必须在1-3600秒范围内")
                else:
                    updated_fields.append("query_timeout")

        # 验证并处理重试次数
        if retry_attempts is not None:
            if not isinstance(retry_attempts, int):
                try:
                    retry_attempts = int(retry_attempts)
                except (ValueError, TypeError):
                    validation_errors.append("重试次数必须是整数")
            else:
                if not (0 <= retry_attempts <= 10):
                    validation_errors.append("重试次数必须在0-10次范围内")
                else:
                    updated_fields.append("retry_attempts")

        # 验证并处理重试延迟时间
        if retry_delay is not None:
            if not isinstance(retry_delay, int):
                try:
                    retry_delay = int(retry_delay)
                except (ValueError, TypeError):
                    validation_errors.append("重试延迟时间必须是整数")
            else:
                if not (0 <= retry_delay <= 60):
                    validation_errors.append("重试延迟时间必须在0-60秒范围内")
                else:
                    updated_fields.append("retry_delay")

        # 如果有验证错误，返回失败结果
        if validation_errors:
            return {
                "success": False,
                "error": f"参数验证失败: {'; '.join(validation_errors)}",
                "updated_fields": [],
                "config_file": config_manager.get_config_file_path(),
                "metadata": create_response_metadata(
                    operation="dm_update_config",
                    success=False,
                    execution_time=time.time() - start_time,
                    additional_info={"error_type": "validation_error"}
                )
            }

        # 如果没有提供任何参数，返回提示信息
        if not updated_fields:
            return {
                "success": True,
                "message": "未提供任何更新参数，配置保持不变",
                "updated_fields": [],
                "current_config": config_manager.get_database_config(),
                "config_file": config_manager.get_config_file_path(),
                "metadata": create_response_metadata(
                    operation="dm_update_config",
                    success=True,
                    execution_time=time.time() - start_time,
                    row_count=0,
                    additional_info={"fields_updated": 0, "config_file": config_manager.get_config_file_path()}
                )
            }

        # 执行配置更新
        update_success = config_manager.update_database_config(
            host=host,
            port=port,
            user=user,
            password=password,
            schema=schema,
            query_timeout=query_timeout,
            retry_attempts=retry_attempts,
            retry_delay=retry_delay
        )

        execution_time = time.time() - start_time

        if update_success:
            # 获取更新后的配置
            current_config = config_manager.get_database_config()

            return {
                "success": True,
                "message": f"配置更新成功，已保存到配置文件。更新的字段: {', '.join(updated_fields)}",
                "updated_fields": updated_fields,
                "current_config": current_config,
                "config_file": config_manager.get_config_file_path(),
                "metadata": create_response_metadata(
                    operation="dm_update_config",
                    success=True,
                    execution_time=execution_time,
                    row_count=len(updated_fields),
                    additional_info={
                        "fields_updated": len(updated_fields),
                        "config_file": config_manager.get_config_file_path()
                    }
                )
            }
        else:
            return {
                "success": False,
                "error": "配置文件更新失败，请检查文件权限和磁盘空间",
                "updated_fields": updated_fields,
                "config_file": config_manager.get_config_file_path(),
                "metadata": create_response_metadata(
                    operation="dm_update_config",
                    success=False,
                    execution_time=execution_time,
                    additional_info={"error_type": "update_error"}
                )
            }

    except Exception as e:
        return {
            "success": False,
            "error": f"配置更新过程中发生意外错误: {str(e)}",
            "updated_fields": [],
            "config_file": config_manager.get_config_file_path() if 'config_manager' in locals() else "未知",
            "metadata": create_response_metadata(
                operation="dm_update_config",
                success=False,
                execution_time=time.time() - start_time,
                additional_info={"error_type": "unexpected_error"}
            )
        }


# 添加连接池状态查询工具
@mcp.tool()
def dm_pool_status() -> dict:
    """
    获取数据库连接池状态信息。

    用途: 诊断连接池问题、监控连接使用情况、排查连接泄漏。

    Returns:
        dict: {success, pool_stats, pool_enabled, metadata}
              pool_stats包含: total_connections, available_connections, in_use_connections等
    """
    start_time = time.time()

    try:
        config = get_dm_config()
        
        if not config.use_pool:
            return {
                "success": True,
                "pool_enabled": False,
                "message": "连接池未启用，当前使用直接连接模式",
                "metadata": create_response_metadata(
                    operation="dm_pool_status",
                    success=True,
                    execution_time=time.time() - start_time
                )
            }
        
        # 尝试获取连接池状态
        try:
            from dm_pool import get_pool, PoolConfig
            
            db_config = {
                'host': config.host,
                'port': config.port,
                'user': config.user,
                'password': config.password,
                'schema': config.schema
            }
            
            pool_config = PoolConfig(
                min_connections=config.pool_min_connections,
                max_connections=config.pool_max_connections,
                connection_timeout=config.pool_connection_timeout
            )
            
            pool = get_pool(db_config, pool_config)
            stats = pool.get_stats()
            
            return {
                "success": True,
                "pool_enabled": True,
                "pool_stats": stats,
                "config": {
                    "min_connections": config.pool_min_connections,
                    "max_connections": config.pool_max_connections,
                    "connection_timeout": config.pool_connection_timeout
                },
                "metadata": create_response_metadata(
                    operation="dm_pool_status",
                    success=True,
                    execution_time=time.time() - start_time,
                    additional_info={"pool_enabled": True}
                )
            }
        except Exception as e:
            return {
                "success": True,
                "pool_enabled": True,
                "pool_stats": None,
                "message": f"连接池已启用但尚未初始化: {str(e)}",
                "metadata": create_response_metadata(
                    operation="dm_pool_status",
                    success=True,
                    execution_time=time.time() - start_time,
                    additional_info={"pool_initialized": False}
                )
            }

    except Exception as e:
        return {
            "success": False,
            "error": f"获取连接池状态失败: {str(e)}",
            "metadata": create_response_metadata(
                operation="dm_pool_status",
                success=False,
                execution_time=time.time() - start_time,
                additional_info={"error_type": "unexpected_error"}
            )
        }


def main():
    """
    达梦数据库 MCP 服务器的主入口点。

    此函数使用 stdio 传输启动 MCP 服务器。
    包含错误处理和优雅关闭功能。

    使用方法:
        python main.py

    环境变量:
        - DM_HOST: 数据库主机（默认：localhost）
        - DM_PORT: 数据库端口（默认：5236）
        - DM_USER: 数据库用户（默认：SYSDBA）
        - DM_PASSWORD: 数据库密码（默认：SYSDBA）
        - DM_SCHEMA: 数据库模式（默认：空）
    """
    import os
    import sys

    try:
        # 获取当前配置
        dm_config = get_dm_config()

        # 如果提供了环境变量，则覆盖配置
        env_host = os.getenv('DM_HOST')
        env_port = os.getenv('DM_PORT')
        env_user = os.getenv('DM_USER')
        env_password = os.getenv('DM_PASSWORD')
        env_schema = os.getenv('DM_SCHEMA')

        # 应用环境变量覆盖
        if env_host:
            dm_config.host = env_host
            print(f"使用环境变量 DM_HOST: {env_host}")

        if env_port:
            try:
                dm_config.port = int(env_port)
                print(f"使用环境变量 DM_PORT: {env_port}")
            except ValueError:
                print(f"警告: 环境变量 DM_PORT '{env_port}' 不是有效的端口号，使用默认值 {dm_config.port}")

        if env_user:
            dm_config.user = env_user
            print(f"使用环境变量 DM_USER: {env_user}")

        if env_password:
            dm_config.password = env_password
            print(f"使用环境变量 DM_PASSWORD: {'*' * len(env_password)}")

        if env_schema:
            dm_config.schema = env_schema
            print(f"使用环境变量 DM_SCHEMA: {env_schema}")

        print(f"\n正在启动达梦数据库 MCP 服务器...")
        print(f"最终数据库配置:")
        print(f"  - 主机: {dm_config.host}")
        print(f"  - 端口: {dm_config.port}")
        print(f"  - 用户: {dm_config.user}")
        print(f"  - 模式: {dm_config.schema or '无'}")
        print(f"  - 密码: {'*' * len(dm_config.password) if dm_config.password else '无'}")

        # 启动 MCP 服务器
        mcp.run(transport="stdio")

    except KeyboardInterrupt:
        print("\n用户请求关闭服务器")
        sys.exit(0)
    except Exception as e:
        print(f"服务器启动错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()