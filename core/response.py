"""响应元数据构建函数。"""

import time
from typing import Dict, Any, Optional


def create_response_metadata(
    operation: str,
    success: bool,
    execution_time: float = 0.0,
    row_count: Optional[int] = None,
    additional_info: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """创建标准化的响应元数据。"""
    metadata = {
        "timestamp": time.time(),
        "operation": operation,
        "success": success,
        "execution_time_seconds": round(execution_time, 4),
    }

    if row_count is not None:
        metadata["row_count"] = row_count

    if additional_info:
        metadata.update(additional_info)

    return metadata
