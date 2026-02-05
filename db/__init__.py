"""
数据库模块

包含达梦数据库客户端、连接池和配置管理
"""

from .config import (
    DmConfig,
    PoolConfig,
    CacheConfig,
    ConfigManager,
    get_config_manager,
    get_database_config,
    get_cache_ttl,
    # 默认配置常量
    DEFAULT_DB_HOST,
    DEFAULT_DB_PORT,
    DEFAULT_CACHE_TTL,
)
from .client import DmClient

__all__ = [
    # 配置类
    'DmConfig',
    'PoolConfig',
    'CacheConfig',
    'ConfigManager',
    'get_config_manager',
    'get_database_config',
    'get_cache_ttl',
    # 默认配置常量
    'DEFAULT_DB_HOST',
    'DEFAULT_DB_PORT',
    'DEFAULT_CACHE_TTL',
    # 客户端
    'DmClient',
]
