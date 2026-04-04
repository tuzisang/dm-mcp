"""
输入验证器模块

提供数据库标识符和 SQL 查询的验证函数
"""

import re
from typing import Optional, Tuple

from .exceptions import InvalidParameterError

# 支持的语句类型
StatementType = str
STATEMENT_TYPE_SELECT = "SELECT"
STATEMENT_TYPE_EXPLAIN = "EXPLAIN"
STATEMENT_TYPE_EXPLAIN_PLAN = "EXPLAIN_PLAN"


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


def _strip_sql_comments(sql: str) -> str:
    """
    移除 SQL 开头的注释，用于验证实际的 SQL 语句类型

    支持的注释格式：
    - 单行注释: -- 注释内容
    - 块注释: /* 注释内容 */

    Args:
        sql: 原始 SQL 字符串

    Returns:
        str: 移除开头注释后的 SQL 字符串
    """
    result = sql.strip()

    while True:
        original = result

        # 移除开头的单行注释 (-- 注释)
        # 匹配 -- 开头直到换行符的内容
        result = re.sub(r'^--[^\n]*\n?', '', result, flags=re.MULTILINE).strip()

        # 移除开头的块注释 (/* 注释 */)
        result = re.sub(r'^/\*.*?\*/', '', result, flags=re.DOTALL).strip()

        # 如果没有变化，说明没有更多注释了
        if result == original:
            break

    return result


def classify_statement(sql_without_comments: str) -> StatementType:
    """
    根据去除注释后的 SQL 语句开头识别语句类型

    Args:
        sql_without_comments: 去除注释后的 SQL 语句（已 strip）

    Returns:
        StatementType: 语句类型 (SELECT, EXPLAIN, EXPLAIN_PLAN)

    Raises:
        ValueError: 如果无法识别语句类型
    """
    upper = sql_without_comments.upper()

    # 优先级：EXPLAIN PLAN FOR > EXPLAIN PLAN > EXPLAIN
    # 目标 DM 环境不支持 FOR 语法，所以 EXPLAIN PLAN 也归为 EXPLAIN_PLAN
    if upper.startswith("EXPLAIN PLAN FOR"):
        return STATEMENT_TYPE_EXPLAIN_PLAN

    if upper.startswith("EXPLAIN PLAN"):
        return STATEMENT_TYPE_EXPLAIN_PLAN

    if upper.startswith("EXPLAIN"):
        return STATEMENT_TYPE_EXPLAIN

    if upper.startswith("SELECT"):
        return STATEMENT_TYPE_SELECT

    # 理论上不会到达这里，因为调用方已做危险关键字检查
    raise ValueError(f"无法识别的语句类型: {sql_without_comments[:20]}")


def validate_sql_query(sql: str) -> Tuple[str, StatementType]:
    """
    验证 SQL 查询的安全性并识别语句类型

    Args:
        sql: SQL 查询字符串

    Returns:
        Tuple[str, StatementType]: (验证过的 SQL 查询, 语句类型)

    Raises:
        InvalidParameterError: 如果 SQL 查询无效或存在潜在危险

    Note:
        支持开头带有注释的 SELECT/EXPLAIN 语句，例如：
        -- 这是注释
        SELECT * FROM table

        允许的语句类型：
        - SELECT：标准查询
        - EXPLAIN：诊断语句（返回结果集）
        - EXPLAIN_PLAN：执行计划语句（仅生成计划，无结果集）
    """
    if not sql or not sql.strip():
        raise InvalidParameterError("SQL 查询不能为空")

    sql = sql.strip()

    # 移除开头的注释，用于检查实际的 SQL 语句类型
    sql_without_leading_comments = _strip_sql_comments(sql)

    # 检查潜在的危险操作（在去除注释后的 SQL 中检查）
    dangerous_keywords = [
        "DROP", "DELETE", "UPDATE", "INSERT", "CREATE", "ALTER",
        "EXEC", "EXECUTE", "TRUNCATE", "MERGE", "GRANT", "REVOKE"
    ]

    for keyword in dangerous_keywords:
        if re.search(rf"\b{keyword}\b", sql_without_leading_comments, re.IGNORECASE):
            raise InvalidParameterError(f"检测到危险的 SQL 关键字 '{keyword}'")

    # 识别语句类型
    statement_type = classify_statement(sql_without_leading_comments)

    # 返回原始 SQL（保留注释）和语句类型
    return sql, statement_type


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
