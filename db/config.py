"""
配置管理模块

统一管理所有配置：数据库连接、连接池、缓存等
"""

import json
from typing import Dict, Any, Optional
from pathlib import Path
from dataclasses import dataclass


# ============== 默认配置常量 ==============

# 数据库连接默认配置
DEFAULT_DB_HOST = "192.168.2.38"
DEFAULT_DB_PORT = 5236
DEFAULT_DB_USER = "SYSDBA"
DEFAULT_DB_PASSWORD = "SYSDBA001"
DEFAULT_DB_SCHEMA = "aiops"

# 查询配置
DEFAULT_QUERY_TIMEOUT = 120
DEFAULT_RETRY_ATTEMPTS = 3
DEFAULT_RETRY_DELAY = 5

# 连接池配置
DEFAULT_USE_POOL = True
DEFAULT_POOL_MIN_CONNECTIONS = 2
DEFAULT_POOL_MAX_CONNECTIONS = 10
DEFAULT_POOL_CONNECTION_TIMEOUT = 30
DEFAULT_POOL_IDLE_TIMEOUT = 300
DEFAULT_POOL_HEALTH_CHECK_INTERVAL = 60

# 缓存配置
DEFAULT_CACHE_TTL = 120.0


# ============== 配置数据类 ==============

@dataclass
class DmConfig:
    """达梦数据库连接配置"""
    host: str = DEFAULT_DB_HOST
    port: int = DEFAULT_DB_PORT
    user: str = DEFAULT_DB_USER
    password: str = DEFAULT_DB_PASSWORD
    schema: str = DEFAULT_DB_SCHEMA
    query_timeout: int = DEFAULT_QUERY_TIMEOUT
    retry_attempts: int = DEFAULT_RETRY_ATTEMPTS
    retry_delay: int = DEFAULT_RETRY_DELAY
    use_pool: bool = DEFAULT_USE_POOL
    pool_min_connections: int = DEFAULT_POOL_MIN_CONNECTIONS
    pool_max_connections: int = DEFAULT_POOL_MAX_CONNECTIONS
    pool_connection_timeout: int = DEFAULT_POOL_CONNECTION_TIMEOUT

    @classmethod
    def from_dict(cls, config: Dict[str, Any]) -> 'DmConfig':
        """从字典创建配置对象"""
        return cls(
            host=config.get("host", DEFAULT_DB_HOST),
            port=config.get("port", DEFAULT_DB_PORT),
            user=config.get("user", DEFAULT_DB_USER),
            password=config.get("password", DEFAULT_DB_PASSWORD),
            schema=config.get("schema", DEFAULT_DB_SCHEMA),
            query_timeout=config.get("query_timeout", DEFAULT_QUERY_TIMEOUT),
            retry_attempts=config.get("retry_attempts", DEFAULT_RETRY_ATTEMPTS),
            retry_delay=config.get("retry_delay", DEFAULT_RETRY_DELAY),
            use_pool=config.get("use_pool", DEFAULT_USE_POOL),
            pool_min_connections=config.get("pool_min_connections", DEFAULT_POOL_MIN_CONNECTIONS),
            pool_max_connections=config.get("pool_max_connections", DEFAULT_POOL_MAX_CONNECTIONS),
            pool_connection_timeout=config.get("pool_connection_timeout", DEFAULT_POOL_CONNECTION_TIMEOUT)
        )

    @classmethod
    def from_config_file(cls) -> 'DmConfig':
        """从配置文件创建配置对象"""
        return cls.from_dict(get_database_config())


@dataclass
class PoolConfig:
    """连接池配置"""
    min_connections: int = DEFAULT_POOL_MIN_CONNECTIONS
    max_connections: int = DEFAULT_POOL_MAX_CONNECTIONS
    connection_timeout: int = DEFAULT_POOL_CONNECTION_TIMEOUT
    idle_timeout: int = DEFAULT_POOL_IDLE_TIMEOUT
    health_check_interval: int = DEFAULT_POOL_HEALTH_CHECK_INTERVAL

    @classmethod
    def from_dict(cls, config: Dict[str, Any]) -> 'PoolConfig':
        """从字典创建配置对象"""
        return cls(
            min_connections=config.get("pool_min_connections", DEFAULT_POOL_MIN_CONNECTIONS),
            max_connections=config.get("pool_max_connections", DEFAULT_POOL_MAX_CONNECTIONS),
            connection_timeout=config.get("pool_connection_timeout", DEFAULT_POOL_CONNECTION_TIMEOUT),
            idle_timeout=config.get("pool_idle_timeout", DEFAULT_POOL_IDLE_TIMEOUT),
            health_check_interval=config.get("pool_health_check_interval", DEFAULT_POOL_HEALTH_CHECK_INTERVAL)
        )


@dataclass
class CacheConfig:
    """缓存配置"""
    ttl: float = DEFAULT_CACHE_TTL

    @classmethod
    def from_dict(cls, config: Dict[str, Any]) -> 'CacheConfig':
        """从字典创建配置对象"""
        return cls(ttl=config.get("cache_ttl", DEFAULT_CACHE_TTL))


# ============== 配置管理器 ==============

class ConfigManager:
    """配置管理器，负责处理所有配置的读取、写入和验证"""

    def __init__(self, config_file: str = "dm_config.json"):
        self.config_file = Path(config_file)
        self._config_cache: Optional[Dict[str, Any]] = None

    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return {
            "database": {
                "host": DEFAULT_DB_HOST,
                "port": DEFAULT_DB_PORT,
                "user": DEFAULT_DB_USER,
                "password": DEFAULT_DB_PASSWORD,
                "schema": DEFAULT_DB_SCHEMA,
                "query_timeout": DEFAULT_QUERY_TIMEOUT,
                "retry_attempts": DEFAULT_RETRY_ATTEMPTS,
                "retry_delay": DEFAULT_RETRY_DELAY,
                "use_pool": DEFAULT_USE_POOL,
                "pool_min_connections": DEFAULT_POOL_MIN_CONNECTIONS,
                "pool_max_connections": DEFAULT_POOL_MAX_CONNECTIONS,
                "pool_connection_timeout": DEFAULT_POOL_CONNECTION_TIMEOUT,
                "pool_idle_timeout": DEFAULT_POOL_IDLE_TIMEOUT,
                "pool_health_check_interval": DEFAULT_POOL_HEALTH_CHECK_INTERVAL,
                "cache_ttl": DEFAULT_CACHE_TTL
            }
        }

    def load_config(self, force_reload: bool = False) -> Dict[str, Any]:
        """从配置文件加载配置"""
        if self._config_cache is not None and not force_reload:
            return self._config_cache
        
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                self._config_cache = self._validate_config(config)
            else:
                self._config_cache = self._get_default_config()
                self.save_config(self._config_cache)
            return self._config_cache
        except (json.JSONDecodeError, IOError) as e:
            print(f"读取配置文件失败: {e}")
            self._config_cache = self._get_default_config()
            return self._config_cache

    def save_config(self, config: Dict[str, Any]) -> bool:
        """保存配置到文件"""
        try:
            validated_config = self._validate_config(config)
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(validated_config, f, indent=2, ensure_ascii=False)
            self._config_cache = validated_config
            return True
        except (IOError, json.JSONDecodeError) as e:
            print(f"保存配置文件失败: {e}")
            return False

    def _validate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """验证配置格式，填充缺失的默认值"""
        if not isinstance(config, dict):
            raise ValueError("配置必须是一个字典")

        if "database" not in config:
            config["database"] = {}

        db = config["database"]
        defaults = self._get_default_config()["database"]
        
        for key, default_value in defaults.items():
            db.setdefault(key, default_value)

        # 验证端口号
        if not isinstance(db["port"], int):
            try:
                db["port"] = int(db["port"])
            except (ValueError, TypeError):
                db["port"] = DEFAULT_DB_PORT
        if not (1 <= db["port"] <= 65535):
            db["port"] = DEFAULT_DB_PORT

        return config

    def get_database_config(self) -> Dict[str, Any]:
        """获取数据库配置"""
        return self.load_config().get("database", {})

    def get_dm_config(self) -> DmConfig:
        """获取 DmConfig 对象"""
        return DmConfig.from_dict(self.get_database_config())

    def get_pool_config(self) -> PoolConfig:
        """获取 PoolConfig 对象"""
        return PoolConfig.from_dict(self.get_database_config())

    def get_cache_config(self) -> CacheConfig:
        """获取 CacheConfig 对象"""
        return CacheConfig.from_dict(self.get_database_config())

    def update_database_config(self, **kwargs) -> bool:
        """更新数据库配置"""
        try:
            config = self.load_config()
            for key, value in kwargs.items():
                if value is not None:
                    config["database"][key] = value
            return self.save_config(config)
        except Exception as e:
            print(f"更新配置失败: {e}")
            return False

    def get_config_file_path(self) -> str:
        """获取配置文件的完整路径"""
        return str(self.config_file.absolute())

    def reload(self) -> Dict[str, Any]:
        """重新加载配置"""
        return self.load_config(force_reload=True)


# ============== 全局实例 ==============

_config_manager: Optional[ConfigManager] = None


def get_config_manager(config_file: str = "dm_config.json") -> ConfigManager:
    """获取全局配置管理器实例"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager(config_file)
    return _config_manager


def get_database_config() -> Dict[str, Any]:
    """获取当前数据库配置"""
    return get_config_manager().get_database_config()


def get_cache_ttl() -> float:
    """获取缓存 TTL 配置"""
    return get_config_manager().get_cache_config().ttl
