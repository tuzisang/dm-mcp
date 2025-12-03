# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a DM (达梦数据库) MCP (Model Context Protocol) server project that provides database integration tools for Claude. The project uses FastMCP to create an MCP server with tools for connecting to and querying DM Database.

## Key Architecture

### Core Components
- **main.py**: Main MCP server entry point using FastMCP framework, defines MCP tools and resources
- **dm_client.py**: Comprehensive DM Database client wrapper with connection management, query execution, and database introspection methods
- **pyproject.toml**: Project configuration with dmPython dependency

### MCP Server Structure
The server provides:
- **Tools**: `add()`, `dm_query()`, `dm_connect()` for database operations
- **Resources**: Dynamic greeting resource with URI pattern `greeting://{name}`
- **Prompts**: Customizable greeting prompt generator with style options

### Database Client Features
The `DmClient` class provides comprehensive database operations:
- **Connection Management**: Automatic connection handling with configuration validation
- **Query Operations**: `execute_query()` for SELECT statements, `execute_update()` for INSERT/UPDATE/DELETE
- **Database Introspection**: `list_tables()`, `list_views()`, `describe_table()`, `get_view_definition()`
- **Parameterized Queries**: Safe SQL execution with parameter binding via `_execute_param_query()`
- **Context Manager Support**: Automatic resource cleanup with `with DmClient(config) as client:`
- **Error Handling**: Comprehensive exception handling with meaningful error messages

## Development Commands

### Environment Setup
```bash
# Install dependencies
pip install dmPython

# or using uv (if available)
uv run pip install dmPython
```

### Running the Server
```bash
# Start MCP server with stdio transport
python main.py

# or using uv
uv run python main.py
```

### Testing the Database Client
```bash
# Test DM database connection and basic operations
python dm_client.py
```

## Database Configuration

Default connection settings (modify in main.py:16):
- Host: localhost
- Port: 5236
- User: SYSDBA
- Password: SYSDBA

For production use, update these values or use environment variables.

## Common Development Tasks

### Adding New MCP Tools
Use the `@mcp.tool()` decorator pattern in main.py:
```python
@mcp.tool()
def your_tool(param: str) -> dict:
    """Tool description"""
    # implementation
    return {"result": "value"}
```

### Database Operations
- Use `DmClient` for all database interactions
- The client handles connection management automatically
- Use context managers for proper resource cleanup:
```python
with DmClient(config) as client:
    result = client.execute_query("SELECT * FROM table")
```

### Database Schema Operations
```python
# List tables and views
tables = client.list_tables("schema_name")
views = client.list_views("schema_name")

# Get table structure
columns = client.describe_table("table_name", "schema_name")

# Get view definition
view_def = client.get_view_definition("view_name", "schema_name")
```

### Error Handling
- Database operations return empty lists on failure
- Connection errors are caught and logged
- Update operations return -1 on failure, affected row count on success
- Schema operations raise `ValueError` for invalid parameters

## Testing

- Run `python dm_client.py` to verify database connectivity
- Test MCP tools by starting the server and connecting via MCP client
- Verify dmPython driver installation before database operations

## Dependencies

- **dmpython>=2.5.26**: DM Database Python driver
- **mcp.server.fastmcp**: MCP server framework (via FastMCP import)