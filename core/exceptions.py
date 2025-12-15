"""
自定义异常类模块

定义达梦数据库 MCP 操作相关的异常类
"""


class DMMCPError(Exception):
    """达梦数据库 MCP 操作的基础异常类"""
    pass


class DatabaseConnectionError(DMMCPError):
    """数据库连接失败时抛出的异常"""
    pass


class InvalidParameterError(DMMCPError):
    """输入参数无效时抛出的异常"""
    pass


class SQLExecutionError(DMMCPError):
    """SQL 执行失败时抛出的异常"""
    pass
