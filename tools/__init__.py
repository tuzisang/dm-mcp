"""MCP 工具注册入口。"""


def register_tools(mcp):
    """注册当前正式支持的工具集合。"""
    from .config import dm_update_config
    from .connection import dm_connect
    from .explain_plan import dm_explain_plan
    from .query import dm_query
    from .schema import (
        dm_describe_table,
        dm_get_view_definition,
        dm_list_tables,
        dm_list_views,
    )

    mcp.tool()(dm_query)
    mcp.tool()(dm_explain_plan)
    mcp.tool()(dm_connect)
    mcp.tool()(dm_list_tables)
    mcp.tool()(dm_list_views)
    mcp.tool()(dm_describe_table)
    mcp.tool()(dm_get_view_definition)
    mcp.tool()(dm_update_config)


__all__ = ["register_tools"]
