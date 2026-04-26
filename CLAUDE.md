# CLAUDE.md

## Project Overview

达梦数据库 MCP 服务器，使用 FastMCP，通过 Java 守护进程桥接达梦数据库。只读场景。

## Architecture

```
main.py → tools/* → db/client.py → db/java_bridge.py → db/DmJdbcBridge.java
```

- `main.py`: FastMCP 入口，注册 8 个工具
- `db/java_bridge.py`: Python 端，spawn Java 进程，stdin/stdout JSON 通信
- `db/DmJdbcBridge.java`: Java 端，HikariCP 连接池，JDBC 查询
- `db/client.py`: DmClient，封装 Java 桥接调用
- `db/config.py`: ConfigManager + DmConfig，配置文件读写和验证
- `core/`: 公共模块（cache / decorators / exceptions / response / validators）
- `tools/`: MCP 工具实现（config / connection / explain_plan / query / schema）

## Tools (8)

| Tool | File | Description |
|------|------|-------------|
| `dm_connect` | tools/connection.py | 测试连接 |
| `dm_update_config` | tools/config.py | 运行时更新配置 |
| `dm_query` | tools/query.py | 只读 SQL（SELECT / EXPLAIN / EXPLAIN PLAN） |
| `dm_explain_plan` | tools/explain_plan.py | 专用执行计划分析 |
| `dm_list_tables` | tools/schema.py | 列出表 |
| `dm_list_views` | tools/schema.py | 列出视图 |
| `dm_describe_table` | tools/schema.py | 表结构 |
| `dm_get_view_definition` | tools/schema.py | 视图定义 |

## Adding a Tool

```python
from core.decorators import mcp_tool_handler
from core.response import create_response_metadata

@mcp_tool_handler()
def dm_your_tool(param: str) -> dict:
    return create_response_metadata(success=True, data={...})
```

注册在 `tools/__init__.py` 中。

## Configuration

配置通过 `dm_config.json`（自动创建）或环境变量读取：

```bash
DM_HOST DM_PORT DM_USER DM_PASSWORD DM_SCHEMA
```

```bash
# 运行时
cp dm_config.json.example dm_config.json
# 编辑填入数据库信息
```

## Java Bridge

启动时自动检测 `.class` 是否过期，必要时调用 `javac -cp 'lib/*' db/DmJdbcBridge.java` 编译。

手动编译：
```bash
javac -cp 'lib/*' db/DmJdbcBridge.java
```

## Testing

```bash
uv run pytest tests -q
```

## Key Constraints

- **只读**: 所有 DML / DDL 在 Python 侧拒绝，Java 侧也会拦截
- **大小写敏感**: 表名、schema 名必须精确匹配
- **缓存**: `dm_query` 和 `dm_explain_plan` 结果缓存约 60 秒，`dm_update_config` 后清空
