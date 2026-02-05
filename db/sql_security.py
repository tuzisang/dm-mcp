"""
SQL 安全工具

提供输入验证和 SQL 注入防护功能
"""

import re
from typing import Optional


class SqlValidationError(Exception):
    """SQL 验证错误"""
    pass


def validate_identifier(name: str, name_type: str = "标识符") -> str:
    """
    验证 SQL 标识符（表名、列名、schema名等）

    只允许：字母、数字、下划线，且必须以字母或下划线开头

    Args:
        name: 要验证的名称
        name_type: 名称类型（用于错误消息）

    Returns:
        验证后的名称（已去除前后空格）

    Raises:
        SqlValidationError: 如果名称不符合规范
    """
    if name is None:
        raise SqlValidationError(f"{name_type}不能为空")

    # 去除前后空格
    name = name.strip()

    if not name:
        raise SqlValidationError(f"{name_type}不能为空")

    # 验证格式：只允许字母、数字、下划线，且必须以字母或下划线开头
    if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', name):
        raise SqlValidationError(
            f"无效的{name_type}: '{name}'。"
            f"{name_type}只能包含字母、数字、下划线，且必须以字母或下划线开头"
        )

    # 检查长度限制（大多数数据库对标识符有长度限制）
    if len(name) > 128:
        raise SqlValidationError(f"{name_type}过长（超过128个字符）")

    return name


def validate_table_name(table_name: str) -> str:
    """验证表名"""
    return validate_identifier(table_name, "表名")


def validate_schema_name(schema: str) -> str:
    """验证 schema 名称"""
    return validate_identifier(schema, "Schema名称")


def validate_view_name(view_name: str) -> str:
    """验证视图名称"""
    return validate_identifier(view_name, "视图名")


def is_safe_sql(sql: str) -> bool:
    """
    简单检查 SQL 是否包含危险模式

    这是一个基础检查，不能替代参数化查询

    Args:
        sql: SQL 语句

    Returns:
        True 如果看起来安全，False 如果包含明显危险模式
    """
    if not sql:
        return False

    sql_upper = sql.upper().strip()

    # 危险模式检查
    dangerous_patterns = [
        r'\bDROP\s+TABLE\b',      # DROP TABLE
        r'\bTRUNCATE\b',            # TRUNCATE
        r'\bALTER\s+TABLE\b',       # ALTER TABLE
        r'\bEXEC\b',                # EXEC/EXECUTE
        r'\bEXECUTE\b',             # EXECUTE
        r'\bGRANT\b',               # GRANT 权限
        r'\bREVOKE\b',              # REVOKE 权限
        r';\s*DROP\b',             # 多语句注入
        r';\s*DELETE\b',           # 多语句注入
    ]

    for pattern in dangerous_patterns:
        if re.search(pattern, sql_upper):
            return False

    return True
