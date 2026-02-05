# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a DM (达梦数据库) MCP (Model Context Protocol) server project that provides database integration tools for Claude. The project uses FastMCP to create a focused MCP server with tools specifically for connecting to and querying DM Database.

## Key Architecture

### Core Components
- **main.py**: Main MCP server entry point using FastMCP framework, defines 7 core database tools
- **db/java_bridge.py**: Java 守护进程桥接服务（Python 端），包含心跳检测、超时恢复、自动重启等机制
- **db/DmJdbcBridge.java**: Java 守护进程（Java 端），使用 HikariCP 连接池，支持心跳发送和优雅关闭
- **db/client.py**: DmClient 数据库客户端，封装了 Java 桥接和重试逻辑
- **db/config.py**: Configuration management module with ConfigManager class for handling database connection settings
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
- **Parameterized Queries**: Safe SQL execution with parameter binding via Java bridge
- **Context Manager Support**: Automatic resource cleanup with `with DmClient(config) as client:`
- **Error Handling**: Comprehensive exception handling with meaningful error messages
- **Smart Retry Logic**: 区分可重试和不可重试异常，默认重试 1 次（而非 3 次），重试延迟 1 秒（而非 5 秒）

### Java Bridge Architecture (假死修复)
项目使用 Java 守护进程桥接达梦数据库，通过 stdin/stdout 进行 JSON 通信。已实现以下关键修复：

**Python 端 (db/java_bridge.py)**:
- **非阻塞 I/O**: 使用 `threading.Thread` + `queue.Queue` 实现超时读取（默认 30 秒）
- **心跳检测**: 监控 Java 进程健康状态，心跳间隔 15 秒
- **自动恢复**: 检测到假死后自动重启 Java 进程并重试查询
- **重启限制**: 5 分钟内最多重启 3 次，防止无限重启循环
- **优雅关闭**: 先发送 `shutdown` 消息，再验证进程退出

**Java 端 (db/DmJdbcBridge.java)**:
- **心跳定时器**: 每 15 秒发送心跳消息 `{"type": "heartbeat", "timestamp": <ms>}`
- **HikariCP 连接池**: 最大连接数 20，连接超时 60 秒
- **连接泄漏检测**: 60 秒阈值，自动检测未关闭的连接
- **查询超时**: Statement 查询超时 120 秒，防止长时间占用连接
- **优雅关闭**: JVM 关闭钩子确保连接池完全关闭
- **智能类型转换**: BLOB→Base64, CLOB→String, TIMESTAMP→ISO 8601
- **大对象保护**: BLOB 限制 10MB, CLOB 限制 1MB，防止 OOM
- **类型转换降级**: 转换失败时返回错误字符串而非崩溃

**关键改进**:
- 假死检测时间从最长 6 分钟降至 30-60 秒
- 连接资源正确释放，防止连接池耗尽
- 向后兼容旧配置文件
- 支持 BLOB/CLOB/LONG/TIMESTAMP 等所有达梦数据库类型

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

**新增配置参数** (向后兼容):
```json
{
  "database": {
    "io_timeout": 30,
    "health_check_interval": 15,
    "max_retries": 1,
    "pool_max_connections": 20,
    "pool_connection_timeout": 60000
  }
}
```

**配置参数说明**:
- `io_timeout`: I/O 操作超时时间（秒），范围 5-300，默认 30
- `health_check_interval`: 心跳检测间隔（秒），范围 5-60，默认 15
- `max_retries`: 最大重试次数，范围 0-10，默认 1（原为 3）
- `pool_max_connections`: 连接池最大连接数，默认 20（原为 10）
- `pool_connection_timeout`: 连接获取超时（毫秒），默认 60000（原为 30000）

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

### JDBC Type Conversion

The Java bridge automatically handles DM Database JDBC type conversion to ensure JSON serialization:

#### Supported Types
| JDBC Type | Java Type | JSON Format | Example |
|-----------|-----------|-------------|---------|
| BLOB | byte[] → Base64 | String | `"SGVsbG8gV29ybGQ="` |
| CLOB/LONG/TEXT | String | String | `"long text..."` |
| TIMESTAMP/DATE | String (ISO 8601) | String | `"2026-02-05 18:01:09"` |
| DECIMAL/NUMERIC | BigDecimal | Number | `123.456789` |
| VARCHAR/CHAR | String | String | `"text"` |
| INTEGER/SMALLINT | Integer | Number | `42` |
| BIGINT | Long | Number | `1234567890` |

#### Size Limits
- **BLOB**: 10MB limit, larger values truncated with warning suffix `(truncated from XX.XXMB)`
- **CLOB/LONG/TEXT**: 1MB limit, larger values truncated with warning suffix `(truncated)`

#### Error Handling
- Type conversion failures return error string: `"<类型转换失败: <error message>>"`
- Errors are logged to stderr but don't crash the query
- NULL values handled correctly (return `null` in JSON)

#### Column Type Metadata
Query responses include `columnTypes` array with JDBC type names:
```json
{
  "success": true,
  "columns": ["ID", "NAME", "DATA"],
  "columnTypes": ["INTEGER", "VARCHAR2", "BLOB"],
  "rows": [[1, "test", "base64data..."]]
}
```

#### Important Notes
- BLOB fields are Base64 encoded and may be large
- CLOB fields over 1MB are truncated to prevent OOM
- TIMESTAMP fields are returned as strings in database's default format
- For large objects, consider using dedicated export tools rather than SQL queries

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