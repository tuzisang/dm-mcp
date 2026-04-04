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
    STATEMENT_TYPE_SELECT,
    STATEMENT_TYPE_EXPLAIN,
    STATEMENT_TYPE_EXPLAIN_PLAN,
)
from .decorators import mcp_tool_handler
from .cache import (
    mcp_cache,
    clear_cache,
    get_cache_stats,
    CacheEntry,
    CacheStore,
    generate_cache_key,
)

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
    "STATEMENT_TYPE_SELECT",
    "STATEMENT_TYPE_EXPLAIN",
    "STATEMENT_TYPE_EXPLAIN_PLAN",
    # Decorators
    "mcp_tool_handler",
    # Cache
    "mcp_cache",
    "clear_cache",
    "get_cache_stats",
    "CacheEntry",
    "CacheStore",
    "generate_cache_key",
]
