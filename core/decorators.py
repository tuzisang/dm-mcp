"""
MCP 工具处理装饰器模块

提供统一的错误处理、计时和响应格式化
"""

import time
from functools import wraps
from typing import Callable, Any, Dict

from .exceptions import (
    DatabaseConnectionError,
    InvalidParameterError,
    SQLExecutionError,
)
from .response import create_response_metadata


# 错误类型映射
ERROR_TYPE_MAP = {
    InvalidParameterError: "validation_error",
    DatabaseConnectionError: "connection_error",
    SQLExecutionError: "sql_error",
    TimeoutError: "pool_timeout_error",
}


def _get_error_type(error: Exception) -> str:
    """
    根据异常类型获取错误类型字符串

    Args:
        error: 异常实例

    Returns:
        str: 错误类型字符串
    """
    # 检查已知异常类型
    for exc_type, error_type in ERROR_TYPE_MAP.items():
        if isinstance(error, exc_type):
            return error_type

    # 检查错误消息中的关键字
    error_msg = str(error).lower()

    if "超时" in error_msg or "timeout" in error_msg:
        return "timeout_error"

    if "连接池" in error_msg or "pool" in error_msg:
        return "pool_error"

    if isinstance(error, RuntimeError):
        if "连接池" in str(error) or "pool" in str(error).lower():
            return "pool_error"
        return "runtime_error"

    return "unexpected_error"


def _format_error_message(error: Exception, error_type: str, operation: str) -> str:
    """
    格式化错误消息

    Args:
        error: 异常实例
        error_type: 错误类型
        operation: 操作名称

    Returns:
        str: 格式化的错误消息
    """
    error_msg = str(error)

    if error_type == "validation_error":
        return f"无效的参数: {error_msg}"

    if error_type == "timeout_error":
        return f"操作超时: {error_msg}"

    if error_type == "pool_timeout_error":
        return f"获取数据库连接超时: {error_msg}"

    if error_type == "pool_error":
        return f"连接池错误: {error_msg}"

    if error_type == "connection_error":
        return error_msg

    if error_type == "runtime_error":
        return f"运行时错误: {error_msg}"

    return f"操作过程中发生意外错误: {error_msg}"


def mcp_tool_handler(operation_name: str):
    """
    MCP 工具处理装饰器

    功能：
    - 自动计时
    - 统一错误处理
    - 标准化响应格式

    Args:
        operation_name: 操作名称，用于元数据

    Returns:
        装饰器函数
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Dict[str, Any]:
            start_time = time.time()

            try:
                # 执行原函数
                result = func(*args, **kwargs)
                return result

            except InvalidParameterError as e:
                execution_time = time.time() - start_time
                error_type = "validation_error"
                return {
                    "success": False,
                    "error": _format_error_message(e, error_type, operation_name),
                    "metadata": create_response_metadata(
                        operation=operation_name,
                        success=False,
                        execution_time=execution_time,
                        additional_info={"error_type": error_type}
                    )
                }

            except (DatabaseConnectionError, SQLExecutionError) as e:
                execution_time = time.time() - start_time
                error_type = _get_error_type(e)
                return {
                    "success": False,
                    "error": str(e),
                    "metadata": create_response_metadata(
                        operation=operation_name,
                        success=False,
                        execution_time=execution_time,
                        additional_info={"error_type": error_type}
                    )
                }

            except TimeoutError as e:
                execution_time = time.time() - start_time
                return {
                    "success": False,
                    "error": f"获取数据库连接超时: {str(e)}",
                    "metadata": create_response_metadata(
                        operation=operation_name,
                        success=False,
                        execution_time=execution_time,
                        additional_info={"error_type": "pool_timeout_error"}
                    )
                }

            except RuntimeError as e:
                execution_time = time.time() - start_time
                error_msg = str(e)
                if "连接池" in error_msg or "pool" in error_msg.lower():
                    error_type = "pool_error"
                else:
                    error_type = "runtime_error"
                return {
                    "success": False,
                    "error": f"运行时错误: {error_msg}",
                    "metadata": create_response_metadata(
                        operation=operation_name,
                        success=False,
                        execution_time=execution_time,
                        additional_info={"error_type": error_type}
                    )
                }

            except Exception as e:
                execution_time = time.time() - start_time
                error_type = _get_error_type(e)
                error_msg = _format_error_message(e, error_type, operation_name)

                return {
                    "success": False,
                    "error": error_msg,
                    "metadata": create_response_metadata(
                        operation=operation_name,
                        success=False,
                        execution_time=execution_time,
                        additional_info={"error_type": error_type}
                    )
                }

        return wrapper
    return decorator
