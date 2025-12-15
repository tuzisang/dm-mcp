"""
达梦数据库 MCP 服务器

这是一个基于 FastMCP 框架构建的达梦数据库 MCP 服务器，提供数据库连接和查询工具。
该服务器提供全面的数据库操作功能，包括表管理、视图检查和带有参数验证的安全 SQL 执行。

使用方法:
    python main.py

依赖项:
    - dmPython: 达梦数据库 Python 驱动
    - FastMCP: MCP 服务器框架

数据库配置:
    - 主机: localhost
    - 端口: 5236
    - 用户: SYSDBA
    - 密码: SYSDBA
    (请根据您的环境修改配置)
"""

from mcp.server.fastmcp import FastMCP
from tools import register_tools


# 创建一个带有增强元数据的 MCP 服务器
mcp = FastMCP("DM Database MCP Server")

# 注册所有工具
register_tools(mcp)


if __name__ == "__main__":
    mcp.run()
