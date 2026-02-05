"""
配置工具模块

提供数据库配置管理功能
"""

import re
import time
from typing import Dict, Any, Optional

from core import create_response_metadata, mcp_tool_handler
from db import get_config_manager


@mcp_tool_handler("dm_update_config")
def dm_update_config(
    host: Optional[str] = None,
    port: Optional[int] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    schema: Optional[str] = None,
    query_timeout: Optional[int] = None,
    retry_attempts: Optional[int] = None,
    retry_delay: Optional[int] = None
) -> Dict[str, Any]:
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
        if isinstance(port, int) and not (1 <= port <= 65535):
            validation_errors.append("端口号必须在1-65535范围内")
        elif isinstance(port, int):
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
        if password == "":
            validation_errors.append("密码不能为空")
        elif len(str(password)) > 256:
            validation_errors.append("密码过长（最多256个字符）")
        else:
            updated_fields.append("password")

    # 验证并处理模式名
    if schema is not None:
        if schema.strip():
            schema = schema.strip()
            if len(schema) > 128:
                validation_errors.append("模式名过长（最多128个字符）")
            elif not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", schema):
                validation_errors.append("模式名必须以字母或下划线开头，且只能包含字母、数字和下划线")
            else:
                updated_fields.append("schema")
        elif schema == "":
            updated_fields.append("schema")

    # 验证并处理查询超时时间
    if query_timeout is not None:
        if not isinstance(query_timeout, int):
            try:
                query_timeout = int(query_timeout)
            except (ValueError, TypeError):
                validation_errors.append("查询超时时间必须是整数")
        if isinstance(query_timeout, int) and not (1 <= query_timeout <= 3600):
            validation_errors.append("查询超时时间必须在1-3600秒范围内")
        elif isinstance(query_timeout, int):
            updated_fields.append("query_timeout")

    # 验证并处理重试次数
    if retry_attempts is not None:
        if not isinstance(retry_attempts, int):
            try:
                retry_attempts = int(retry_attempts)
            except (ValueError, TypeError):
                validation_errors.append("重试次数必须是整数")
        if isinstance(retry_attempts, int) and not (0 <= retry_attempts <= 10):
            validation_errors.append("重试次数必须在0-10次范围内")
        elif isinstance(retry_attempts, int):
            updated_fields.append("retry_attempts")

    # 验证并处理重试延迟时间
    if retry_delay is not None:
        if not isinstance(retry_delay, int):
            try:
                retry_delay = int(retry_delay)
            except (ValueError, TypeError):
                validation_errors.append("重试延迟时间必须是整数")
        if isinstance(retry_delay, int) and not (0 <= retry_delay <= 60):
            validation_errors.append("重试延迟时间必须在0-60秒范围内")
        elif isinstance(retry_delay, int):
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
            "error": "配置更新失败，请检查配置文件权限",
            "updated_fields": [],
            "config_file": config_manager.get_config_file_path(),
            "metadata": create_response_metadata(
                operation="dm_update_config",
                success=False,
                execution_time=execution_time,
                additional_info={"error_type": "update_error"}
            )
        }
