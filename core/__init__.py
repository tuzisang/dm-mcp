"""
核心模块

包含异常类、装饰器、验证器和响应构建器
"""

from .exceptions import (
    DMMCPError,
    DatabaseConnectionError,
    InvalidParameterError,
    SQLExecutionError,
)
from .response import (
    create_response_metadata,
    create_success_response,
    create_error_response,
)
from .validators import (
    validate_identifier,
    validate_sql_query,
    validate_optional_schema,
)
from .decorators import mcp_tool_handler

__all__ = [
    # Exceptions
    "DMMCPError",
    "DatabaseConnectionError",
    "InvalidParameterError",
    "SQLExecutionError",
    # Response
    "create_response_metadata",
    "create_success_response",
    "create_error_response",
    # Validators
    "validate_identifier",
    "validate_sql_query",
    "validate_optional_schema",
    # Decorators
    "mcp_tool_handler",
]
