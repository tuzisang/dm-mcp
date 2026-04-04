"""
达梦数据库 MCP 服务器

这是一个基于 FastMCP 的只读达梦数据库 MCP 服务器。
当前实现保留共享 Java 守护进程、共享连接池和短 TTL 查询缓存，其余复杂度已收敛掉。

使用方法:
    python main.py

依赖项:
    - FastMCP: MCP 服务器框架
"""

from mcp.server.fastmcp import FastMCP
from tools import register_tools


# 创建一个带有增强元数据的 MCP 服务器
mcp = FastMCP("DM Database MCP Server")

# 注册所有工具
register_tools(mcp)


if __name__ == "__main__":
    mcp.run()
