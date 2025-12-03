# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a DM (达梦数据库) MCP (Model Context Protocol) server project that provides database integration tools for Claude. The project uses FastMCP to create a focused MCP server with tools specifically for connecting to and querying DM Database.

## Key Architecture

### Core Components
- **main.py**: Main MCP server entry point using FastMCP framework, defines 7 core database tools
- **dm_client.py**: Comprehensive DM Database client wrapper with connection management, query execution, and database introspection methods
- **config.py**: Configuration management module with ConfigManager class for handling database connection settings
- **pyproject.toml**: Project configuration with dmPython dependency
- **dm_config.json**: Runtime configuration file storing database connection parameters (auto-generated)

### MCP Server Structure
The server provides focused database tools:
- **Connection Tools**: `dm_connect()`, `dm_update_config()`
- **Query Tools**: `dm_query()`, `dm_list_tables()`, `dm_list_views()`, `dm_describe_table()`, `dm_get_view_definition()`

### Configuration Management
The `ConfigManager` class provides comprehensive configuration handling:
- **File Operations**: `load_config()`, `save_config()` for JSON-based configuration files
- **Database Config**: `get_database_config()`, `update_database_config()` for connection parameters
- **Validation**: `_validate_config()` ensures proper format and parameter ranges
- **Auto-creation**: Automatically creates default configuration file if missing
- **Global Instance**: `get_config_manager()` provides singleton access to configuration

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

The project uses a configuration file-based approach for database connection management:

### Configuration File (dm_config.json)
Default connection settings are automatically stored in `dm_config.json`:
- Host: 192.168.2.38
- Port: 5236
- User: SYSDBA
- Password: SYSDBA001
- Schema: aiops

### Configuration Management
- **Auto-creation**: Configuration file is automatically generated with defaults on first run
- **Runtime Updates**: Use `dm_update_config()` tool to modify configuration without server restart
- **Validation**: All parameters are validated for format and range (e.g., port must be 1-65535)
- **Fallback**: If configuration file is corrupted, defaults are restored automatically

### Accessing Configuration in Code
```python
from config import get_database_config, get_config_manager

# Get current database configuration
db_config = get_database_config()

# Get configuration manager instance
config_manager = get_config_manager()

# Update configuration programmatically
config_manager.update_database_config(host="new_host", port=5237)
```

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
from dm_client import DmClient, DmConfig

# Load configuration from config file
config = DmConfig.from_config_file()

# Use client with context manager
with DmClient(config) as client:
    result = client.execute_query("SELECT * FROM table")
```

### Configuration Management Tasks
```python
from config import get_config_manager

# Get configuration manager
config_manager = get_config_manager()

# Load current configuration
config = config_manager.load_config()

# Update specific parameters
config_manager.update_database_config(
    host="new.example.com",
    port=5237,
    user="new_user"
)

# Save updated configuration
success = config_manager.save_config(config)
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

## Important Considerations

### Case Sensitivity
- DM Database is case-sensitive for table names and schema names
- Always use the exact case provided by users
- Do not convert between uppercase and lowercase automatically

### Security
- Only SELECT queries are allowed for security
- All input parameters are validated to prevent SQL injection
- Connection management is handled automatically

## Testing

- Run `python dm_client.py` to verify database connectivity
- Test MCP tools by starting the server and connecting via MCP client
- Verify dmPython driver installation before database operations

## Dependencies

- **dmpython>=2.5.26**: DM Database Python driver
- **mcp.server.fastmcp**: MCP server framework (via FastMCP import)

## Project Structure

### Core Files
- `main.py`: MCP server entry point (defines 7 database tools)
- `dm_client.py`: Database client wrapper with DmClient and DmConfig classes
- `config.py`: Configuration management module with ConfigManager class
- `pyproject.toml`: Project configuration
- `dm_config.json`: Runtime database configuration (auto-generated)

### MCP Tools Overview
The server provides 7 focused database tools:

#### Connection Management Tools
1. **dm_connect()**: Test database connection and health check
2. **dm_update_config(host?, port?, user?, password?, schema?)**: Runtime configuration management with validation and persistence

#### Database Query Tools
3. **dm_query(sql)**: Execute safe SELECT queries with validation
4. **dm_list_tables(schema?)**: List database tables with optional schema filtering
5. **dm_list_views(schema?)**: List database views with optional schema filtering
6. **dm_describe_table(table_name, schema?)**: Get detailed table structure information
7. **dm_get_view_definition(view_name, schema?)**: Get complete CREATE statement for views

#### Configuration Tool Details
**dm_update_config()** Features:
- **Parameter Validation**: Validates host format, port range (1-65535), and required fields
- **Incremental Updates**: Only modifies specified parameters, preserves others
- **Persistence**: Saves changes to dm_config.json for future sessions
- **Error Handling**: Provides detailed error messages for invalid configurations
- **Atomic Operations**: Ensures configuration consistency during updates

## Code Quality

- **Total lines**: 1431 lines (main.py) + 205 lines (config.py)
- **Focused functionality**: Only database-related tools with comprehensive configuration management
- **Comprehensive documentation**: All tools have detailed docstrings with usage examples
- **Error handling**: Robust error handling and user feedback for database and configuration operations
- **Security**: SQL injection protection and input validation
- **Configuration Management**: JSON-based configuration with validation and auto-recovery
- **Modular Design**: Clear separation between database operations, configuration management, and MCP tool definitions