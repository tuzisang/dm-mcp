# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a DM (达梦数据库) MCP (Model Context Protocol) server project that provides database integration tools for Claude. The project uses FastMCP to create an MCP server with tools for connecting to and querying DM Database.

## Key Architecture

### Core Components
- **main.py**: Main MCP server entry point using FastMCP framework
- **dm_client.py**: DM Database client wrapper with connection management and query execution
- **pyproject.toml**: Project configuration with dmPython dependency

### MCP Server Structure
The server provides:
- **Tools**: `add()`, `dm_query()`, `dm_connect()` for database operations
- **Resources**: Dynamic greeting resource
- **Prompts**: Customizable greeting prompt generator

### Database Integration
- Uses dmPython driver for DM Database connectivity
- Supports connection pooling and transaction management
- Implements both query execution and update operations
- Context manager support for proper resource cleanup

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

### Error Handling
- Database operations return empty lists on failure
- Connection errors are caught and logged
- Update operations return -1 on failure, affected row count on success

## Testing

- Run `python dm_client.py` to verify database connectivity
- Test MCP tools by starting the server and connecting via MCP client
- Verify dmPython driver installation before database operations

## Dependencies

- **dmpython>=2.5.26**: DM Database Python driver
- **mcp.server.fastmcp**: MCP server framework (via FastMCP import)