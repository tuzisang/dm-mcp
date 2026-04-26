# 达梦数据库 MCP 服务器

只读达梦数据库 MCP 服务，使用 Java 桥接实现跨平台兼容。

**架构**: Python (MCP) → Java 守护进程 (JDBC) → 达梦数据库

Python 驱动 (`dmPython`) 依赖原生扩展，在 Apple Silicon Mac、跨平台切换等场景下兼容性差。本项目通过 Java 桥接解决这个问题 —— 只要有 JRE，JDBC 驱动就能跑，无需编译任何原生扩展。

## 前提

- Python `>= 3.12`
- Java 8+ (`javac` 用于首次编译)
- `lib/` 下的 JDBC 与 HikariCP JAR

## 快速上手

```bash
git clone https://github.com/tuzisang/dm-mcp.git
cd dm-mcp

# 配置数据库
cp dm_config.json.example dm_config.json
# 编辑 dm_config.json 填入你的数据库信息

# 安装依赖并启动
uv run pip install fastmcp
uv run python main.py
```

或通过环境变量配置：

```bash
export DM_HOST=your_host
export DM_PORT=5236
export DM_USER=your_user
export DM_PASSWORD=your_password
export DM_SCHEMA=your_schema
uv run python main.py
```

## 部署为 Claude Code MCP

```bash
nano ~/.claude/settings.json
```

```json
{
  "mcpServers": {
    "dm-mcp": {
      "command": "uv",
      "args": [
        "--directory",
        "/项目路径/dm-mcp",
        "run",
        "main.py"
      ],
      "env": {},
      "type": "stdio"
    }
  }
}
```

重启 Claude Code 即可使用。

## 工具

| 工具 | 说明 |
|------|------|
| `dm_connect` | 测试数据库连接 |
| `dm_query(sql)` | 只读 SQL 查询（SELECT / EXPLAIN / EXPLAIN PLAN） |
| `dm_explain_plan(sql)` | 专用执行计划分析，只接受 SELECT |
| `dm_list_tables(schema?)` | 列出数据库表 |
| `dm_list_views(schema?)` | 列出数据库视图 |
| `dm_describe_table(table, schema?)` | 查看表结构 |
| `dm_get_view_definition(view, schema?)` | 查看视图定义 |
| `dm_update_config(...)` | 运行时更新数据库配置 |

## 说明

- 只读约束：所有 DML / DDL 在 Python 侧校验阶段拒绝，Java 侧也会拦截
- 查询缓存：`dm_query` 和 `dm_explain_plan` 结果缓存约 60 秒
- 自动编译：启动时自动检测 `DmJdbcBridge.class` 是否需要重新编译
