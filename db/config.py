"""
数据库配置管理。

仅保留当前闭环真正需要的数据库连接参数与查询超时。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

DEFAULT_DB_HOST = ""
DEFAULT_DB_PORT = 5236
DEFAULT_DB_USER = ""
DEFAULT_DB_PASSWORD = ""
DEFAULT_DB_SCHEMA = ""
DEFAULT_QUERY_TIMEOUT = 120


@dataclass(frozen=True)
class DmConfig:
    """达梦数据库连接配置。"""

    host: str = DEFAULT_DB_HOST
    port: int = DEFAULT_DB_PORT
    user: str = DEFAULT_DB_USER
    password: str = DEFAULT_DB_PASSWORD
    schema: str = DEFAULT_DB_SCHEMA
    query_timeout: int = DEFAULT_QUERY_TIMEOUT

    @classmethod
    def from_dict(cls, config: Dict[str, Any]) -> "DmConfig":
        return cls(
            host=_coerce_string(config.get("host"), DEFAULT_DB_HOST),
            port=_coerce_int(config.get("port"), DEFAULT_DB_PORT, minimum=1, maximum=65535),
            user=_coerce_string(config.get("user"), DEFAULT_DB_USER),
            password=_coerce_string(config.get("password"), DEFAULT_DB_PASSWORD),
            schema=_coerce_string(config.get("schema"), DEFAULT_DB_SCHEMA),
            query_timeout=_coerce_int(
                config.get("query_timeout"),
                DEFAULT_QUERY_TIMEOUT,
                minimum=1,
                maximum=3600,
            ),
        )

    @classmethod
    def from_config_file(cls, config_file: str = "dm_config.json") -> "DmConfig":
        return cls.from_dict(ConfigManager(config_file).get_database_config())


def _coerce_string(value: Any, default: str) -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _coerce_int(value: Any, default: int, *, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    if minimum <= number <= maximum:
        return number
    return default


class ConfigManager:
    """读取、验证并更新 `dm_config.json`。"""

    def __init__(self, config_file: str = "dm_config.json"):
        self.config_file = Path(config_file)
        self._config_cache: Optional[Dict[str, Any]] = None

    def _default_database_config(self) -> Dict[str, Any]:
        return {
            "host": DEFAULT_DB_HOST,
            "port": DEFAULT_DB_PORT,
            "user": DEFAULT_DB_USER,
            "password": DEFAULT_DB_PASSWORD,
            "schema": DEFAULT_DB_SCHEMA,
            "query_timeout": DEFAULT_QUERY_TIMEOUT,
        }

    def _validate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(config, dict):
            config = {}

        database = config.get("database")
        if not isinstance(database, dict):
            database = {}

        validated = DmConfig.from_dict(database)
        result = dict(config)
        result["database"] = {
            "host": validated.host,
            "port": validated.port,
            "user": validated.user,
            "password": validated.password,
            "schema": validated.schema,
            "query_timeout": validated.query_timeout,
        }
        return result

    def load_config(self, force_reload: bool = False) -> Dict[str, Any]:
        if self._config_cache is not None and not force_reload:
            return self._config_cache

        if self.config_file.exists():
            try:
                with self.config_file.open("r", encoding="utf-8") as file:
                    raw = json.load(file)
            except (OSError, json.JSONDecodeError):
                raw = {}
        else:
            raw = {}

        config = self._validate_config(raw)
        if not self.config_file.exists():
            self.save_config(config)
        self._config_cache = config
        return config

    def save_config(self, config: Dict[str, Any]) -> bool:
        try:
            validated = self._validate_config(config)
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            with self.config_file.open("w", encoding="utf-8") as file:
                json.dump(validated, file, indent=2, ensure_ascii=False)
            self._config_cache = validated
            return True
        except OSError:
            return False

    def get_database_config(self) -> Dict[str, Any]:
        return dict(self.load_config().get("database", self._default_database_config()))

    def get_dm_config(self) -> DmConfig:
        return DmConfig.from_dict(self.get_database_config())

    def update_database_config(self, **kwargs: Any) -> bool:
        config = self.load_config()
        database = dict(config.get("database", {}))
        for key, value in kwargs.items():
            if value is not None:
                database[key] = value
        config["database"] = database
        return self.save_config(config)

    def get_config_file_path(self) -> str:
        return str(self.config_file.absolute())

    def reload(self) -> Dict[str, Any]:
        return self.load_config(force_reload=True)


_config_manager: Optional[ConfigManager] = None


def get_config_manager(config_file: str = "dm_config.json") -> ConfigManager:
    global _config_manager
    if _config_manager is None or _config_manager.config_file != Path(config_file):
        _config_manager = ConfigManager(config_file)
    return _config_manager


def get_database_config() -> Dict[str, Any]:
    return get_config_manager().get_database_config()
