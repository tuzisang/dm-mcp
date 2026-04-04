"""
MCP 工具模块

包含所有数据库操作工具
"""

from .query import dm_query
from .explain_plan import dm_explain_plan
from .connection import dm_connect
from .schema import dm_list_tables, dm_list_views, dm_describe_table, dm_get_view_definition
from .config import dm_update_config


def register_tools(mcp):
    """
    注册所有工具到 MCP 服务器

    Args:
        mcp: FastMCP 服务器实例
    """
    mcp.tool()(dm_query)
    mcp.tool()(dm_explain_plan)
    mcp.tool()(dm_connect)
    mcp.tool()(dm_list_tables)
    mcp.tool()(dm_list_views)
    mcp.tool()(dm_describe_table)
    mcp.tool()(dm_get_view_definition)
    mcp.tool()(dm_update_config)


__all__ = [
    "dm_query",
    "dm_explain_plan",
    "dm_connect",
    "dm_list_tables",
    "dm_list_views",
    "dm_describe_table",
    "dm_get_view_definition",
    "dm_update_config",
    "register_tools",
]
