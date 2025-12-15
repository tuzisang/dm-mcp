"""
输入验证器模块

提供数据库标识符和 SQL 查询的验证函数
"""

import re
from typing import Optional

from .exceptions import InvalidParameterError


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


def validate_optional_schema(schema: Optional[str]) -> Optional[str]:
    """
    验证可选的 schema 参数

    Args:
        schema: 可选的模式名称

    Returns:
        Optional[str]: 验证过的模式名称，如果为空则返回 None

    Raises:
        InvalidParameterError: 如果模式名称无效
    """
    if schema is None or not schema.strip():
        return None

    return validate_identifier(schema.strip(), "schema name")
