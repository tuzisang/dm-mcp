  
from mcp.server.fastmcp import FastMCP
from dm_client import DmClient, DmConfig
"""
FastMCP quickstart example with DM Database integration.

cd to the `examples/snippets/clients` directory and run:
    uv run server fastmcp_quickstart stdio
"""


# Create an MCP server
mcp = FastMCP("DM Demo")

# 初始化达梦数据库客户端
dm_config = DmConfig(host="localhost", port=5236, user="SYSDBA", password="SYSDBA")
dm_client = DmClient(dm_config)


# Add an addition tool
@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers"""
    return a + b


# Add DM database query tool
@mcp.tool()
def dm_query(sql: str) -> dict:
    """Execute SQL query on DM Database"""
    try:
        result = dm_client.execute_query(sql)
        return {"success": True, "data": result, "sql": sql}
    except Exception as e:
        return {"success": False, "error": str(e), "sql": sql}


# Add DM connection test tool
@mcp.tool()
def dm_connect() -> dict:
    """Test connection to DM Database"""
    try:
        success = dm_client.connect()
        return {"success": success, "message": "连接成功" if success else "连接失败"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# Add a dynamic greeting resource
@mcp.resource("greeting://{name}")
def get_greeting(name: str) -> str:
    """Get a personalized greeting"""
    return f"Hello, {name}!"


# Add a prompt
@mcp.prompt()
def greet_user(name: str, style: str = "friendly") -> str:
    """Generate a greeting prompt"""
    styles = {
        "friendly": "Please write a warm, friendly greeting",
        "formal": "Please write a formal, professional greeting",
        "casual": "Please write a casual, relaxed greeting",
    }

    return f"{styles.get(style, styles['friendly'])} for someone named {name}."
    
    
if __name__ == "__main__":  
    mcp.run(transport="stdio") # 启动 MCP 服务，使用 stdio 传输