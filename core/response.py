"""
响应构建器模块

提供标准化的响应格式构建函数
"""

import time
from typing import Dict, Any, Optional


def create_response_metadata(
    operation: str,
    success: bool,
    execution_time: float = 0.0,
    row_count: Optional[int] = None,
    additional_info: Optional[Dict[str, Any]] = None
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


def create_success_response(
    operation: str,
    data: Any,
    execution_time: float,
    row_count: Optional[int] = None,
    additional_info: Optional[Dict[str, Any]] = None,
    **extra_fields
) -> Dict[str, Any]:
    """
    创建成功响应

    Args:
        operation: 操作名称
        data: 返回的数据
        execution_time: 执行时间（秒）
        row_count: 行数（如适用）
        additional_info: 元数据中的附加信息
        **extra_fields: 响应中的额外字段

    Returns:
        Dict[str, Any]: 标准化的成功响应
    """
    response = {
        "success": True,
        "data": data,
        "metadata": create_response_metadata(
            operation=operation,
            success=True,
            execution_time=execution_time,
            row_count=row_count,
            additional_info=additional_info
        )
    }

    # 添加额外字段
    response.update(extra_fields)

    return response


def create_error_response(
    operation: str,
    error: str,
    error_type: str,
    execution_time: float,
    additional_info: Optional[Dict[str, Any]] = None,
    **extra_fields
) -> Dict[str, Any]:
    """
    创建错误响应

    Args:
        operation: 操作名称
        error: 错误消息
        error_type: 错误类型
        execution_time: 执行时间（秒）
        additional_info: 元数据中的附加信息
        **extra_fields: 响应中的额外字段

    Returns:
        Dict[str, Any]: 标准化的错误响应
    """
    # 合并 error_type 到 additional_info
    meta_info = {"error_type": error_type}
    if additional_info:
        meta_info.update(additional_info)

    response = {
        "success": False,
        "error": error,
        "metadata": create_response_metadata(
            operation=operation,
            success=False,
            execution_time=execution_time,
            additional_info=meta_info
        )
    }

    # 添加额外字段
    response.update(extra_fields)

    return response
