"""
配置管理模块
处理达梦数据库连接配置的读取、写入和验证
"""

import json
import os
from typing import Dict, Any, Optional
from pathlib import Path


class ConfigManager:
    """配置管理器，负责处理数据库连接配置"""

    def __init__(self, config_file: str = "dm_config.json"):
        """
        初始化配置管理器

        Args:
            config_file: 配置文件路径，默认为当前目录下的dm_config.json
        """
        self.config_file = Path(config_file)
        self.default_config = {
            "database": {
                "host": "192.168.2.38",
                "port": 5236,
                "user": "SYSDBA",
                "password": "SYSDBA001",
                "schema": "aiops",
                "query_timeout": 120,
                "retry_attempts": 3,
                "retry_delay": 5
            }
        }

    def load_config(self) -> Dict[str, Any]:
        """
        从配置文件加载配置

        Returns:
            配置字典，如果文件不存在则返回默认配置
        """
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                return self._validate_config(config)
            else:
                # 如果配置文件不存在，创建默认配置文件
                self.save_config(self.default_config)
                return self.default_config.copy()
        except (json.JSONDecodeError, IOError) as e:
            print(f"读取配置文件失败: {e}")
            return self.default_config.copy()

    def save_config(self, config: Dict[str, Any]) -> bool:
        """
        保存配置到文件

        Args:
            config: 要保存的配置字典

        Returns:
            保存是否成功
        """
        try:
            # 验证配置格式
            validated_config = self._validate_config(config)

            # 确保目录存在
            self.config_file.parent.mkdir(parents=True, exist_ok=True)

            # 保存配置
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(validated_config, f, indent=2, ensure_ascii=False)

            return True
        except (IOError, json.JSONDecodeError) as e:
            print(f"保存配置文件失败: {e}")
            return False

    def _validate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        验证配置格式

        Args:
            config: 原始配置字典

        Returns:
            验证后的配置字典

        Raises:
            ValueError: 配置格式不正确时
        """
        if not isinstance(config, dict):
            raise ValueError("配置必须是一个字典")

        if "database" not in config:
            config["database"] = {}

        db_config = config["database"]

        # 设置默认值
        db_config.setdefault("host", "192.168.2.38")
        db_config.setdefault("port", 5236)
        db_config.setdefault("user", "SYSDBA")
        db_config.setdefault("password", "SYSDBA001")
        db_config.setdefault("schema", "aiops")
        db_config.setdefault("query_timeout", 300)
        db_config.setdefault("retry_attempts", 3)
        db_config.setdefault("retry_delay", 5)

        # 验证端口类型
        if not isinstance(db_config["port"], int):
            try:
                db_config["port"] = int(db_config["port"])
            except (ValueError, TypeError):
                db_config["port"] = 5236

        # 验证端口范围
        if not (1 <= db_config["port"] <= 65535):
            db_config["port"] = 5236

        # 验证超时时间
        if not isinstance(db_config["query_timeout"], int) or db_config["query_timeout"] < 1:
            db_config["query_timeout"] = 300

        # 验证重试次数
        if not isinstance(db_config["retry_attempts"], int) or db_config["retry_attempts"] < 0:
            db_config["retry_attempts"] = 3

        # 验证重试延迟
        if not isinstance(db_config["retry_delay"], int) or db_config["retry_delay"] < 0:
            db_config["retry_delay"] = 5

        return config

    def get_database_config(self) -> Dict[str, Any]:
        """
        获取数据库配置部分

        Returns:
            数据库配置字典
        """
        config = self.load_config()
        return config.get("database", {})

    def update_database_config(self, host: Optional[str] = None,
                             port: Optional[int] = None,
                             user: Optional[str] = None,
                             password: Optional[str] = None,
                             schema: Optional[str] = None,
                             query_timeout: Optional[int] = None,
                             retry_attempts: Optional[int] = None,
                             retry_delay: Optional[int] = None) -> bool:
        """
        更新数据库配置

        Args:
            host: 数据库主机地址
            port: 数据库端口
            user: 用户名
            password: 密码
            schema: 模式名

        Returns:
            更新是否成功
        """
        try:
            config = self.load_config()

            # 更新指定字段
            if host is not None:
                config["database"]["host"] = host
            if port is not None:
                config["database"]["port"] = port
            if user is not None:
                config["database"]["user"] = user
            if password is not None:
                config["database"]["password"] = password
            if schema is not None:
                config["database"]["schema"] = schema
            if query_timeout is not None:
                config["database"]["query_timeout"] = query_timeout
            if retry_attempts is not None:
                config["database"]["retry_attempts"] = retry_attempts
            if retry_delay is not None:
                config["database"]["retry_delay"] = retry_delay

            return self.save_config(config)
        except Exception as e:
            print(f"更新配置失败: {e}")
            return False

    def get_config_file_path(self) -> str:
        """
        获取配置文件的完整路径

        Returns:
            配置文件路径
        """
        return str(self.config_file.absolute())


# 全局配置管理器实例
_config_manager = None


def get_config_manager(config_file: str = "dm_config.json") -> ConfigManager:
    """
    获取全局配置管理器实例

    Args:
        config_file: 配置文件路径

    Returns:
        配置管理器实例
    """
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager(config_file)
    return _config_manager


def get_database_config() -> Dict[str, Any]:
    """
    获取当前数据库配置

    Returns:
        数据库配置字典
    """
    return get_config_manager().get_database_config()