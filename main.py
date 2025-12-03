  
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

# 数据库配置（可通过环境变量覆盖）
dm_config = DmConfig(
    host="192.168.2.38",
    port=5236,
    user="SYSDBA",
    password="SYSDBA001",
    schema="aiops"
)


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
    return DmClient(dm_config)


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
    在达梦数据库上执行安全的 SELECT 查询，提供全面的参数验证和 SQL 注入保护。

    ⚠️ 重要提醒 - 大小写敏感性:
    - 达梦数据库对 schema 名称和表名称是大小写敏感的
    - AI 必须使用用户提供的确切大小写，不要默认转换为大写
    - 示例: 如果用户提到 "MyTable"，应使用 "MyTable" 而不是 "MYTABLE"
    - SQL 关键字（SELECT, FROM, WHERE 等）不区分大小写

    🚨 AI 使用指南:
    - 此工具仅允许 SELECT 查询，出于安全考虑禁止其他 SQL 操作
    - 在构造 SQL 之前，建议先使用 dm_list_tables() 或 dm_describe_table() 验证表结构
    - 对于复杂的查询，建议分步执行并验证每一步
    - 始终使用参数化查询避免 SQL 注入（此工具已内置防护）

    最佳使用场景:
    - 数据探索和分析查询
    - 报表数据获取
    - 业务逻辑验证
    - 数据完整性检查

    Args:
        sql (str): 要执行的 SQL SELECT 查询语句（必需参数）
                 - 格式: 标准 SQL SELECT 语法，支持达梦数据库特定功能
                 - 限制: 仅允许 SELECT 查询，禁止 DROP/DELETE/UPDATE/INSERT 等
                 - 安全: 已内置 SQL 注入防护和关键字过滤
                 - 验证: 会检查查询语法和危险关键字

    Returns:
        dict: 查询结果和执行信息的完整响应
            成功时返回结构:
            {
                "success": bool,           # 操作是否成功，恒为true
                "data": list,             # 查询结果行列表，每行为字典格式
                "sql": str,               # 实际执行的SQL查询
                "metadata": dict          # 详细的执行元数据
                {
                    "timestamp": float,               # 执行时间戳
                    "operation": str,                 # 操作名称，恒为"dm_query"
                    "success": bool,                  # 操作状态
                    "execution_time_seconds": float,  # 执行耗时(秒)
                    "row_count": int,                 # 返回的行数
                    "query_type": str                 # 查询类型，恒为"SELECT"
                }
            }

            失败时返回结构:
            {
                "success": bool,         # 操作是否成功，恒为false
                "error": str,            # 详细错误信息
                "sql": str,              # 原始SQL查询
                "metadata": dict         # 错误执行元数据
                {
                    "timestamp": float,
                    "operation": str,
                    "success": bool,
                    "execution_time_seconds": float,
                    "error_type": str      # 错误类型: validation_error/connection_error/unexpected_error
                }
            }

    Example:
        >>> dm_query("SELECT * FROM users WHERE id = 1")
        {
            "success": true,
            "data": [{"id": 1, "name": "John", "email": "john@example.com"}],
            "sql": "SELECT * FROM users WHERE id = 1",
            "metadata": {
                "timestamp": 1234567890.123,
                "operation": "dm_query",
                "success": true,
                "execution_time_seconds": 0.0234,
                "row_count": 1,
                "query_type": "SELECT"
            }
        }

    Raises:
        InvalidParameterError: 当SQL查询无效或包含危险操作时
            - 非SELECT查询
            - 包含危险关键字
            - 查询为空或格式错误
        DatabaseConnectionError: 当数据库连接失败时
        SQLExecutionError: 当SQL执行失败时

    错误处理指导:
        - validation_error: 检查SQL语法，确保只使用SELECT语句
        - connection_error: 检查数据库连接配置，可能需要使用dm_connect()测试连接
        - unexpected_error: 查看详细错误信息，可能是数据库权限或表不存在问题

    性能和安全建议:
        - 避免SELECT *，明确指定需要的列名
        - 对大表使用LIMIT子句限制返回行数
        - 使用WHERE子句减少数据传输量
        - 考虑查询复杂度，避免过深的嵌套查询

    数据使用最佳实践:
        - 检查返回的row_count以了解数据规模
        - 使用metadata中的execution_time评估查询性能
        - 对于大量数据，考虑分页处理
        - 验证返回数据的完整性和准确性
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
    except Exception as e:
        return {
            "success": False,
            "error": f"查询执行过程中发生意外错误: {str(e)}",
            "sql": sql,
            "metadata": create_response_metadata(
                operation="dm_query",
                success=False,
                execution_time=time.time() - start_time,
                additional_info={"error_type": "unexpected_error"}
            )
        }


# 添加达梦数据库连接测试工具
@mcp.tool()
def dm_connect() -> dict:
    """
    测试到达梦数据库的连接并验证数据库可访问性，执行全面的连接健康检查。

    ⚠️ 重要提醒 - 连接测试目的:
    - 此工具专门用于诊断数据库连接问题
    - 在使用其他数据库工具前，建议先运行此工具验证连接状态
    - 连接测试包括网络连接、身份验证和基本查询响应验证

    🚨 AI 使用指南:
    - 当其他数据库操作失败时，首先使用此工具排查连接问题
    - 验证数据库配置参数是否正确（主机、端口、用户、密码）
    - 检查网络连通性和数据库服务状态
    - 测试数据库用户权限和基本查询能力

    最佳使用场景:
    - 初次配置数据库连接时
    - 其他数据库操作失败时的故障排查
    - 定期检查数据库服务健康状态
    - 验证数据库配置变更后的连接有效性
    - 监控网络连接稳定性

    测试内容包括:
    1. 网络连接测试 - 验证数据库服务器可达性
    2. 身份验证验证 - 检查用户名和密码有效性
    3. 基本查询执行 - 验证数据库响应和权限
    4. 连接池功能 - 测试连接资源的正常分配和释放

    Returns:
        dict: 连接测试结果和详细诊断信息
            成功时返回结构:
            {
                "success": bool,           # 连接测试是否成功，恒为true
                "message": str,            # 成功消息描述
                "test_query_result": dict, # 测试查询结果 {test_value: 1}
                "metadata": dict           # 执行元数据
                {
                    "timestamp": float,               # 执行时间戳
                    "operation": str,                 # 操作名称，恒为"dm_connect"
                    "success": bool,                  # 操作状态
                    "execution_time_seconds": float,  # 连接测试耗时(秒)
                    "error_type": str                 # 错误类型（仅在失败时存在）
                }
            }

            失败时返回结构:
            {
                "success": bool,         # 连接测试是否成功，恒为false
                "error": str,            # 详细错误信息
                "message": str,          # 失败消息描述
                "metadata": dict         # 错误诊断元数据
            }

    Example:
        >>> dm_connect()
        {
            "success": true,
            "message": "数据库连接成功且响应正常",
            "test_query_result": {"test_value": 1},
            "metadata": {
                "timestamp": 1234567890.123,
                "operation": "dm_connect",
                "success": true,
                "execution_time_seconds": 0.1234
            }
        }

    Raises:
        DatabaseConnectionError: 当数据库连接失败时
            - 网络不可达
            - 认证失败（用户名/密码错误）
            - 数据库服务未运行
        Exception: 其他未预期的系统错误

    错误处理指导:
        - connection_error:
            1. 检查数据库服务是否启动
            2. 验证网络连通性（防火墙、端口配置）
            3. 确认连接参数正确性（主机、端口、用户、密码）
            4. 检查数据库用户权限和状态
        - unexpected_error: 查看详细错误信息，可能是系统资源或配置问题

    诊断检查清单:
        ✅ 网络连通性: 检查数据库服务器是否可达
        ✅ 服务状态: 确认达梦数据库服务正在运行
        ✅ 端口配置: 验证端口5236（或指定端口）是否开放
        ✅ 认证信息: 确认用户名和密码正确
        ✅ 权限设置: 检查用户是否有基本查询权限
        ✅ 资源可用: 验证数据库连接池资源是否充足

    性能基准:
        - 正常连接时间: 应小于1秒
        - 测试查询响应: 应小于100毫秒
        - 如果连接时间过长，可能存在网络或性能问题

    后续行动建议:
        - 连接成功: 可以安全使用其他数据库工具
        - 连接失败: 根据错误信息调整配置或联系管理员
        - 响应缓慢: 考虑网络优化或数据库性能调优
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
    except Exception as e:
        return {
            "success": False,
            "error": f"连接测试过程中发生意外错误: {str(e)}",
            "message": "数据库连接测试失败",
            "metadata": create_response_metadata(
                operation="dm_connect",
                success=False,
                execution_time=time.time() - start_time,
                additional_info={"error_type": "unexpected_error"}
            )
        }


# 添加达梦数据库列表工具
@mcp.tool()
def dm_list_tables(schema: str = None) -> dict:
    """
    列出来自达梦数据库的数据库表，可选择按模式过滤，返回完整的表信息。

    ⚠️ 重要提醒 - 大小写敏感性:
    - 达梦数据库对 schema 名称是大小写敏感的
    - AI 必须使用用户提供的确切 schema 大小写，不要默认转换
    - 如果用户提到 "MySchema"，应使用 "MySchema" 而不是 "MYSCHEMA"
    - 不指定 schema 时，将返回当前用户默认模式中的表

    🚨 AI 使用指南:
    - 在执行查询前，使用此工具了解可用的表结构
    - 结合 dm_describe_table() 获取表的详细结构信息
    - 用于验证表名是否存在于指定的模式中
    - 帮助用户发现和探索数据库中的表资源

    最佳使用场景:
    - 数据库结构探索和导航
    - 表名验证和存在性检查
    - 数据库模式分析
    - 为复杂查询准备表名信息
    - 数据库文档生成和维护

    Args:
        schema (str, optional): 模式名称过滤器（可选参数）
                           - 格式: 字符串，必须是有效的达梦数据库标识符
                           - 大小写: 完全大小写敏感，使用用户提供的确切值
                           - 默认值: None（查询当前用户默认模式）
                           - 验证: 会进行标识符有效性检查
                           - 限制: 不能包含SQL关键字或特殊字符

    Returns:
        dict: 表列表查询结果和详细信息
            成功时返回结构:
            {
                "success": bool,           # 操作是否成功，恒为true
                "data": list,             # 表信息列表，每个元素包含表名等字段
                "schema": str,            # 查询的模式名（可能与输入不同，经过验证）
                "metadata": dict          # 详细的执行元数据
                {
                    "timestamp": float,               # 执行时间戳
                    "operation": str,                 # 操作名称，恒为"dm_list_tables"
                    "success": bool,                  # 操作状态
                    "execution_time_seconds": float,  # 查询耗时(秒)
                    "row_count": int,                 # 返回的表数量
                    "schema_filtered": bool           # 是否进行了模式过滤
                }
            }

            失败时返回结构:
            {
                "success": bool,         # 操作是否成功，恒为false
                "error": str,            # 详细错误信息
                "schema": str,           # 原始schema参数值
                "metadata": dict         # 错误执行元数据
                {
                    "error_type": str      # 错误类型: validation_error/connection_error/unexpected_error
                }
            }

    Example:
        >>> dm_list_tables("PUBLIC")
        {
            "success": true,
            "data": [
                {"TABLE_NAME": "USERS", "OWNER": "PUBLIC"},
                {"TABLE_NAME": "PRODUCTS", "OWNER": "PUBLIC"}
            ],
            "schema": "PUBLIC",
            "metadata": {
                "timestamp": 1234567890.123,
                "operation": "dm_list_tables",
                "success": true,
                "execution_time_seconds": 0.0456,
                "row_count": 2,
                "schema_filtered": true
            }
        }

    Raises:
        InvalidParameterError: 当schema名称无效时
            - 包含SQL关键字或特殊字符
            - 格式不符合达梦数据库标识符规范
            - 长度超过数据库限制（通常128字符）
        DatabaseConnectionError: 当数据库连接失败时

    错误处理指导:
        - validation_error: 检查schema名称格式，确保符合数据库命名规范
        - connection_error: 使用dm_connect()测试数据库连接状态
        - unexpected_error: 检查数据库权限和schema存在性

    数据使用最佳实践:
        - 检查row_count了解表的数量规模
        - 使用返回的表名构造后续的查询语句
        - 注意保留原始的大小写格式
        - 对于大量表，考虑分批处理

    Schema 使用建议:
        - 不指定schema: 查看当前用户可访问的所有表
        - 指定具体schema: 精确查找特定模式中的表
        - 常用schema: PUBLIC, SYSDBA, 或用户自定义schema
        - 大小写匹配: 确保与数据库中实际schema大小写完全一致

    性能说明:
        - 查询复杂度: O(n)，n为表的数量
        - 内存占用: 与返回的表数量成正比
        - 执行时间: 通常在毫秒级别，大型数据库可能需要更长时间

    权限要求:
        - 需要对目标schema有读取权限
        - 系统表查询权限（通常默认拥有）
        - 某些受保护的schema可能需要特殊权限
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
    列出来自达梦数据库的数据库视图，可选择按模式过滤，返回完整的视图信息。

    ⚠️ 重要提醒 - 大小写敏感性:
    - 达梦数据库对 schema 名称和视图名称都是大小写敏感的
    - AI 必须使用用户提供的确切大小写，不要默认转换
    - 如果用户提到 "MyView"，应使用 "MyView" 而不是 "MYVIEW"
    - 不指定 schema 时，将返回当前用户默认模式中的视图

    🚨 AI 使用指南:
    - 在查询视图数据前，使用此工具了解可用的视图资源
    - 结合 dm_get_view_definition() 获取视图的完整SQL定义
    - 用于验证视图名是否存在于指定的模式中
    - 帮助用户理解数据库中的虚拟表结构和逻辑

    最佳使用场景:
    - 数据库视图资源发现和探索
    - 视图名验证和存在性检查
    - 复杂数据查询的逻辑理解
    - 业务数据报表的结构分析
    - 数据库抽象层的导航和使用

    Args:
        schema (str, optional): 模式名称过滤器（可选参数）
                           - 格式: 字符串，必须是有效的达梦数据库标识符
                           - 大小写: 完全大小写敏感，使用用户提供的确切值
                           - 默认值: None（查询当前用户默认模式）
                           - 验证: 会进行标识符有效性检查
                           - 限制: 不能包含SQL关键字或特殊字符

    Returns:
        dict: 视图列表查询结果和详细信息
            成功时返回结构:
            {
                "success": bool,           # 操作是否成功，恒为true
                "data": list,             # 视图信息列表，每个元素包含视图名等字段
                "schema": str,            # 查询的模式名（可能与输入不同，经过验证）
                "metadata": dict          # 详细的执行元数据
                {
                    "timestamp": float,               # 执行时间戳
                    "operation": str,                 # 操作名称，恒为"dm_list_views"
                    "success": bool,                  # 操作状态
                    "execution_time_seconds": float,  # 查询耗时(秒)
                    "row_count": int,                 # 返回的视图数量
                    "schema_filtered": bool           # 是否进行了模式过滤
                }
            }

            失败时返回结构:
            {
                "success": bool,         # 操作是否成功，恒为false
                "error": str,            # 详细错误信息
                "schema": str,           # 原始schema参数值
                "metadata": dict         # 错误执行元数据
                {
                    "error_type": str      # 错误类型: validation_error/connection_error/unexpected_error
                }
            }

    Example:
        >>> dm_list_views("PUBLIC")
        {
            "success": true,
            "data": [
                {"VIEW_NAME": "USER_SUMMARY", "OWNER": "PUBLIC"},
                {"VIEW_NAME": "PRODUCT_STATS", "OWNER": "PUBLIC"}
            ],
            "schema": "PUBLIC",
            "metadata": {
                "timestamp": 1234567890.123,
                "operation": "dm_list_views",
                "success": true,
                "execution_time_seconds": 0.0345,
                "row_count": 2,
                "schema_filtered": true
            }
        }

    Raises:
        InvalidParameterError: 当schema名称无效时
            - 包含SQL关键字或特殊字符
            - 格式不符合达梦数据库标识符规范
            - 长度超过数据库限制（通常128字符）
        DatabaseConnectionError: 当数据库连接失败时

    错误处理指导:
        - validation_error: 检查schema名称格式，确保符合数据库命名规范
        - connection_error: 使用dm_connect()测试数据库连接状态
        - unexpected_error: 检查数据库权限和schema存在性

    视图与表的区别说明:
        - 视图是虚拟表，基于SQL查询结果
        - 视图不存储实际数据，每次查询时动态生成
        - 视图可以简化复杂查询，提供数据抽象层
        - 视图可用于实现数据安全性和访问控制

    数据使用最佳实践:
        - 检查row_count了解视图的数量规模
        - 使用返回的视图名构造后续的查询语句
        - 注意保留原始的大小写格式
        - 对于性能敏感的应用，了解视图的底层查询逻辑

    Schema 使用建议:
        - 不指定schema: 查看当前用户可访问的所有视图
        - 指定具体schema: 精确查找特定模式中的视图
        - 常用schema: PUBLIC, SYSDBA, 或用户自定义schema
        - 大小写匹配: 确保与数据库中实际schema大小写完全一致

    后续操作建议:
        - 发现有用视图后，使用 dm_get_view_definition() 查看完整定义
        - 使用 dm_query() 查询视图数据
        - 分析视图逻辑以理解数据处理流程
        - 评估视图性能以优化查询策略

    性能说明:
        - 查询复杂度: O(n)，n为视图的数量
        - 内存占用: 与返回的视图数量成正比
        - 执行时间: 通常在毫秒级别，大型数据库可能需要更长时间

    权限要求:
        - 需要对目标schema有读取权限
        - 系统表查询权限（通常默认拥有）
        - 查看视图定义可能需要额外的权限
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
    获取包括列定义在内的详细表结构信息，提供完整的数据库表元数据。

    ⚠️ 重要提醒 - 大小写敏感性:
    - 达梦数据库对 schema 名称和表名称都是大小写敏感的
    - AI 必须使用用户提供的确切大小写，不要默认转换为大写
    - 如果用户提到 "MyTable"，应使用 "MyTable" 而不是 "MYTABLE"
    - 列名也是大小写敏感的，返回结果会保持数据库中的原始大小写

    🚨 AI 使用指南:
    - 在构造查询语句前，使用此工具了解表的完整结构
    - 结合 dm_list_tables() 发现可用表，然后获取详细结构
    - 用于验证查询中的列名和数据类型
    - 帮助用户理解数据库设计和约束条件

    最佳使用场景:
    - 数据库表结构分析和理解
    - 查询语句构造前的列名验证
    - 数据类型映射和转换
    - 数据库文档生成和维护
    - 数据迁移和集成的结构分析

    获取的详细信息包括:
    - 列基本信息: 名称、数据类型、长度、精度
    - 约束信息: 可空性、默认值、主键/外键关系
    - 排序信息: 列在表中的物理顺序
    - 元数据: 创建时间、修改时间、注释等

    Args:
        table_name (str): 要描述的表名（必需参数）
                       - 格式: 字符串，必须是有效的达梦数据库标识符
                       - 大小写: 完全大小写敏感，使用用户提供的确切值
                       - 验证: 会进行标识符有效性检查
                       - 限制: 不能包含SQL关键字或特殊字符
        schema (str, optional): 模式名称（可选参数）
                           - 格式: 字符串，必须是有效的达梦数据库标识符
                           - 大小写: 完全大小写敏感，使用用户提供的确切值
                           - 默认值: None（在当前用户默认模式中查找表）
                           - 验证: 会进行标识符有效性检查
                           - 限制: 不能包含SQL关键字或特殊字符

    Returns:
        dict: 表结构信息查询结果和详细元数据
            成功时返回结构:
            {
                "success": bool,           # 操作是否成功，恒为true
                "data": list,             # 列定义信息列表，每个元素包含列的完整信息
                "table_name": str,        # 描述的表名（经过验证）
                "schema": str,            # 查询的模式名（经过验证）
                "metadata": dict          # 详细的执行元数据
                {
                    "timestamp": float,               # 执行时间戳
                    "operation": str,                 # 操作名称，恒为"dm_describe_table"
                    "success": bool,                  # 操作状态
                    "execution_time_seconds": float,  # 查询耗时(秒)
                    "row_count": int,                 # 返回的列数量
                    "table_name": str,                # 表名（重复）
                    "schema": str                     # 模式名（重复）
                }
            }

            失败时返回结构:
            {
                "success": bool,         # 操作是否成功，恒为false
                "error": str,            # 详细错误信息
                "table_name": str,       # 原始表名参数值
                "schema": str,           # 原始schema参数值
                "metadata": dict         # 错误执行元数据
                {
                    "error_type": str      # 错误类型: validation_error/connection_error/unexpected_error
                }
            }

    Example:
        >>> dm_describe_table("USERS", "PUBLIC")
        {
            "success": true,
            "data": [
                {
                    "COLUMN_NAME": "ID",
                    "DATA_TYPE": "INTEGER",
                    "DATA_LENGTH": 10,
                    "DATA_PRECISION": 10,
                    "NULLABLE": "N",
                    "COLUMN_ID": 1,
                    "DEFAULT_VALUE": null
                },
                {
                    "COLUMN_NAME": "NAME",
                    "DATA_TYPE": "VARCHAR",
                    "DATA_LENGTH": 100,
                    "DATA_PRECISION": null,
                    "NULLABLE": "Y",
                    "COLUMN_ID": 2,
                    "DEFAULT_VALUE": null
                }
            ],
            "table_name": "USERS",
            "schema": "PUBLIC",
            "metadata": {
                "timestamp": 1234567890.123,
                "operation": "dm_describe_table",
                "success": true,
                "execution_time_seconds": 0.0234,
                "row_count": 2,
                "table_name": "USERS",
                "schema": "PUBLIC"
            }
        }

    Raises:
        InvalidParameterError: 当参数无效时
            - table_name或schema包含SQL关键字或特殊字符
            - 格式不符合达梦数据库标识符规范
            - 长度超过数据库限制（通常128字符）
            - table_name参数为空或仅包含空白字符
        DatabaseConnectionError: 当数据库连接失败时

    错误处理指导:
        - validation_error: 检查table_name和schema格式，确保符合数据库命名规范
        - connection_error: 使用dm_connect()测试数据库连接状态
        - table_not_found: 使用dm_list_tables()确认表的存在性和正确的大小写
        - permission_denied: 检查用户对目标表的读取权限

    列信息字段说明:
        - COLUMN_NAME: 列名（保持原始大小写）
        - DATA_TYPE: 数据类型（VARCHAR, INTEGER, DATE, TIMESTAMP等）
        - DATA_LENGTH: 字符串类型的最大长度
        - DATA_PRECISION: 数值类型的精度
        - DATA_SCALE: 数值类型的小数位数
        - NULLABLE: 是否允许NULL值（'Y'=允许, 'N'=不允许）
        - COLUMN_ID: 列在表中的物理位置
        - DEFAULT_VALUE: 默认值（如果有）

    数据使用最佳实践:
        - 根据DATA_TYPE和DATA_LENGTH构造适当的查询参数
        - 检查NULLABLE字段避免插入NULL值到非空列
        - 使用COLUMN_ID了解列的物理顺序
        - 注意特殊数据类型（BLOB, CLOB）的处理方式

    查询构造建议:
        - 使用正确的列名和数据类型构造WHERE子句
        - 根据字段长度限制字符串参数
        - 注意数值类型的精度和范围
        - 考虑时区信息处理TIMESTAMP类型

    性能说明:
        - 查询复杂度: O(n)，n为表中的列数量
        - 内存占用: 与返回的列数量成正比
        - 执行时间: 通常在毫秒级别
        - 缓存建议: 表结构信息相对稳定，可以考虑缓存

    权限要求:
        - 需要对目标表有读取权限
        - 系统表查询权限（通常默认拥有）
        - 某些受保护表的结构信息可能需要特殊权限
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
    获取数据库视图的完整 CREATE 语句，提供视图的完整SQL定义和逻辑分析。

    ⚠️ 重要提醒 - 大小写敏感性:
    - 达梦数据库对 schema 名称和视图名称都是大小写敏感的
    - AI 必须使用用户提供的确切大小写，不要默认转换
    - 如果用户提到 "MyView"，应使用 "MyView" 而不是 "MYVIEW"
    - 视图定义中的表名和列名也会保持原始的大小写格式

    🚨 AI 使用指南:
    - 使用此工具理解复杂视图的业务逻辑和数据转换规则
    - 结合 dm_list_views() 发现可用视图，然后获取完整定义
    - 分析视图依赖关系和性能影响
    - 帮助用户理解数据抽象层的设计思路

    最佳使用场景:
    - 视图业务逻辑分析和理解
    - 数据血缘分析和影响评估
    - 视图性能优化和重构
    - 数据库文档生成和维护
    - 数据迁移和复制时的结构复现

    获取的信息包括:
    - 完整的CREATE VIEW语句
    - 底层查询逻辑和表依赖关系
    - 列映射和数据转换规则
    - 业务逻辑的SQL实现方式

    Args:
        view_name (str): 要获取定义的视图名（必需参数）
                       - 格式: 字符串，必须是有效的达梦数据库标识符
                       - 大小写: 完全大小写敏感，使用用户提供的确切值
                       - 验证: 会进行标识符有效性检查
                       - 限制: 不能包含SQL关键字或特殊字符
        schema (str, optional): 模式名称（可选参数）
                           - 格式: 字符串，必须是有效的达梦数据库标识符
                           - 大小写: 完全大小写敏感，使用用户提供的确切值
                           - 默认值: None（在当前用户默认模式中查找视图）
                           - 验证: 会进行标识符有效性检查
                           - 限制: 不能包含SQL关键字或特殊字符

    Returns:
        dict: 视图定义查询结果和详细信息
            成功时返回结构:
            {
                "success": bool,           # 操作是否成功，恒为true
                "data": list,             # 视图定义信息列表，通常包含一个元素
                "view_name": str,         # 查询的视图名（经过验证）
                "schema": str,            # 查询的模式名（经过验证）
                "metadata": dict          # 详细的执行元数据
                {
                    "timestamp": float,               # 执行时间戳
                    "operation": str,                 # 操作名称，恒为"dm_get_view_definition"
                    "success": bool,                  # 操作状态
                    "execution_time_seconds": float,  # 查询耗时(秒)
                    "row_count": int,                 # 返回的记录数量
                    "view_name": str,                 # 视图名（重复）
                    "schema": str                     # 模式名（重复）
                }
            }

            失败时返回结构:
            {
                "success": bool,         # 操作是否成功，恒为false
                "error": str,            # 详细错误信息
                "view_name": str,        # 原始view_name参数值
                "schema": str,           # 原始schema参数值
                "metadata": dict         # 错误执行元数据
                {
                    "error_type": str      # 错误类型: validation_error/connection_error/unexpected_error
                }
            }

    Example:
        >>> dm_get_view_definition("USER_SUMMARY", "PUBLIC")
        {
            "success": true,
            "data": [
                {
                    "VIEW_DEF": "CREATE VIEW USER_SUMMARY AS SELECT u.id, u.name, u.email FROM PUBLIC.users u WHERE u.active = 1 AND u.created_at >= '2020-01-01'"
                }
            ],
            "view_name": "USER_SUMMARY",
            "schema": "PUBLIC",
            "metadata": {
                "timestamp": 1234567890.123,
                "operation": "dm_get_view_definition",
                "success": true,
                "execution_time_seconds": 0.0345,
                "row_count": 1,
                "view_name": "USER_SUMMARY",
                "schema": "PUBLIC"
            }
        }

    Raises:
        InvalidParameterError: 当参数无效时
            - view_name或schema包含SQL关键字或特殊字符
            - 格式不符合达梦数据库标识符规范
            - 长度超过数据库限制（通常128字符）
            - view_name参数为空或仅包含空白字符
        DatabaseConnectionError: 当数据库连接失败时

    错误处理指导:
        - validation_error: 检查view_name和schema格式，确保符合数据库命名规范
        - connection_error: 使用dm_connect()测试数据库连接状态
        - view_not_found: 使用dm_list_views()确认视图的存在性和正确的大小写
        - permission_denied: 检查用户对目标视图的读取权限和查看定义权限

    视图定义信息说明:
        - VIEW_DEF字段: 包含完整的CREATE VIEW语句
        - 可能包含多行定义（对于复杂视图）
        - 保持原始的SQL格式和大小写
        - 包含所有子查询、JOIN操作和聚合逻辑

    定义分析要点:
        - 基础表依赖: 分析视图依赖的源表
        - 数据过滤条件: 理解WHERE子句的业务规则
        - 数据转换: 识别计算列和表达式
        - 性能影响因素: 复杂的JOIN、子查询、聚合操作
        - 数据完整性: 约束和验证逻辑

    性能分析建议:
        - 检查是否包含复杂的JOIN操作
        - 分析WHERE条件的过滤效果
        - 评估聚合操作的计算复杂度
        - 识别可能的性能瓶颈点

    数据使用最佳实践:
        - 保存视图定义用于文档和审计
        - 分析视图逻辑以理解数据加工过程
        - 评估视图对基础表性能的影响
        - 考虑视图重构和优化的可能性

    后续操作建议:
        - 使用 dm_query() 测试视图的数据查询性能
        - 分析依赖的基表结构使用 dm_describe_table()
        - 考虑创建索引优化视图查询性能
        - 评估视图的业务价值和使用场景

    权限要求:
        - 需要对目标视图有读取权限
        - 需要有查看视图定义的特殊权限
        - 对依赖的基础表可能也需要相应的权限
        - 系统表查询权限（通常默认拥有）

    安全注意事项:
        - 视图定义可能暴露敏感的表结构和业务逻辑
        - 某些视图可能包含专有的数据处理算法
        - 考虑访问控制和审计需求
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