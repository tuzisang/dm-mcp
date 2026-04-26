# 达梦数据库 MCP 服务器

这是一个只读场景下的达梦数据库 MCP 服务。当前实现刻意收敛为最小闭环：

- Python 进程内只维护一个共享 `DmClient`
- `DmClient` 只维护一个共享 Java 守护进程和 HikariCP 连接池
- `dm_query` 与 `dm_explain_plan` 使用约 60 秒的内存缓存
- 配置更新后立即重建共享运行时并清空缓存

## 为什么选择 Java 桥接

达梦官方 Python 驱动 (`dmPython`) 依赖原生扩展，在以下场景会遇到兼容性问题：

- **Apple Silicon Mac**（M系列芯片）：Python 原生扩展需要重新编译，部分场景下难以找到适配版本
- **跨平台开发**：Windows / macOS / Linux 需要各自编译或寻找对应版本的 Python 原生驱动
- **环境切换**：开发者换电脑或 CI/CD 迁移时，驱动环境需要重新搭建

本项目采用 **Python + Java 桥接** 的架构解决这个问题：

```
Python (MCP Server) <--stdin/stdout--> Java (守护进程) <--JDBC--> 达梦数据库
```

- Python 只负责任务调度和协议处理，不直接接触数据库
- Java 进程通过标准 JDBC 驱动连接达梦，天然跨平台（只要有 JRE 就能跑）
- JDBC 驱动由达梦官方维护，兼容性和稳定性有保障
- Python 端无需安装任何数据库相关的原生依赖

作者从 Windows 切换到 macOS 的 Apple Silicon 机器后，原有的 Python 达梦驱动无法直接使用，正是这个原因促使了 Java 桥接方案的实现。

## 运行模型

主流程只有一条：

`main.py` -> `tools/*` -> `db/client.py` -> `db/java_bridge.py` -> `db/DmJdbcBridge.java`

保留的状态只有三类：

- 共享 Java 守护进程
- 守护进程内部的共享连接池
- 只读查询缓存

没有保留的能力：

- 心跳协议
- 连接池状态查询协议
- 自动重启与重试策略
- 写入 SQL 路径
- 可配置的连接池/缓存/守护参数
- 手工 `create_client()` / `with DmClient(...)` 生命周期路径
- 探针脚本与部署验证脚本路径

## 配置

配置文件是项目根目录下的 `dm_config.json`。首次加载时会自动生成。

当前只支持以下字段：

```json
{
  "database": {
    "host": "your_host",
    "port": 5236,
    "user": "your_user",
    "password": "your_password_here",
    "schema": "your_schema",
    "query_timeout": 120
  }
}
```

说明：

- `query_timeout` 是 SQL 语句执行超时，单位秒
- 连接池参数固定在实现内，不对外暴露
- 缓存 TTL 固定约 60 秒，不在配置文件中暴露
- 配置文件中遗留的旧字段会被忽略，不再生效

## 启动

前提：

- Python `>= 3.12`
- Java 8+（首次启动或 `db/DmJdbcBridge.java` 更新后需要可用的 `javac`，推荐直接使用 JDK）
- `lib/` 下的 JDBC 与 HikariCP JAR 已就位

安装 Python 依赖：

```bash
python -m pip install fastmcp
```

启动 MCP：

```bash
python main.py
```

说明：

- 启动前，Python 桥接会检查 `db/DmJdbcBridge.class` 是否存在且是否晚于 `db/DmJdbcBridge.java`
- 如果 class 缺失或已过期，会自动执行 `javac -cp 'lib/*' db/DmJdbcBridge.java`
- 如果本地没有 `javac`，或编译/启动失败，错误信息会直接保留 `javac`/`java` 的真实输出，便于定位问题

## 正式支持的入口

- 运行服务：`python main.py`
- 工具注册：`tools.register_tools`
- 共享运行时：`db.client.get_shared_client()`、`db.client.reset_shared_client()`
- 开发验证：`python -m pytest tests -q`、可选手工预编译 `javac -cp 'lib/*' db/DmJdbcBridge.java`

以下旧路径已经删除，不再支持：

- `db/__init__.py`、`core/__init__.py` 这类包级宽导出
- `create_client()` 和 `with DmClient(...)`
- `scratch/ExplainProbe.*`
- `scripts/verify_deployment.sh`

## 工具

当前保留 8 个工具：

- `dm_connect()`: 验证连接与基本查询响应
- `dm_query(sql)`: 只读 SQL 查询，支持 `SELECT`、`EXPLAIN`、`EXPLAIN PLAN`
- `dm_explain_plan(select_sql)`: 专用执行计划工具，只接受 `SELECT`
- `dm_list_tables(schema?)`
- `dm_list_views(schema?)`
- `dm_describe_table(table_name, schema?)`
- `dm_get_view_definition(view_name, schema?)`
- `dm_update_config(host?, port?, user?, password?, schema?, query_timeout?)`

### 缓存规则

- 只缓存 `dm_query` 和 `dm_explain_plan`
- 只缓存成功结果
- 默认 TTL 为 60 秒
- `dm_update_config` 成功后会清空缓存

### 配置更新行为

`dm_update_config(...)` 成功后会立即：

1. 更新 `dm_config.json`
2. 关闭旧的共享 Java 守护进程与连接池
3. 清空查询缓存
4. 让下一次工具调用按新配置惰性重建运行时

## 只读约束

当前实现只支持只读路径：

- `SELECT`
- `EXPLAIN`
- `EXPLAIN PLAN`

所有 DML、DDL、授权语句都会在 Python 侧校验阶段被拒绝。即使绕过 Python 校验，Java 桥接也不会执行非只读请求。

## 开发验证

运行 Python 测试：

```bash
python -m pytest tests -q
```

编译 Java 桥接：

```bash
javac -cp 'lib/*' db/DmJdbcBridge.java
```

这一步对开发验证和排查仍然有用，但正常启动路径会在需要时自动编译。

## 快速上手

### 1. 克隆项目

```bash
git clone https://github.com/tuzisang/dm-mcp.git
cd dm-mcp
```

### 2. 配置数据库连接

复制配置示例文件并修改：

```bash
cp dm_config.json.example dm_config.json
# 编辑 dm_config.json，填入你的数据库信息
```

或通过环境变量配置：

```bash
export DM_HOST=your_host
export DM_PORT=5236
export DM_USER=your_user
export DM_PASSWORD=your_password
export DM_SCHEMA=your_schema
```

### 3. 启动

```bash
# 安装依赖
python -m pip install fastmcp

# 启动 MCP 服务（stdio 模式，供 Claude Code 使用）
python main.py
```

启动后可以通过 MCP 协议直接使用 `dm_query`、`dm_list_tables` 等工具查询达梦数据库。

### 4. 验证连接

在 Claude Code 中连接成功后，可运行：

```
dm_connect
```

返回成功信息即表示数据库连接正常。

## 部署为 Claude Code MCP 服务

Claude Code 支持通过 `settings.json` 注册本地 MCP 服务器。

### 步骤一：编辑 Claude Code 设置

打开 Claude Code 设置文件：

```bash
# macOS
nano ~/.claude/settings.json
```

添加 MCP 服务器配置：

```json
{
  "mcpServers": {
    "dm-mcp": {
      "command": "uv",
      "args": [
        "--directory",
        "/Users/yourname/projects/dm-mcp",
        "run",
        "main.py"
      ],
      "env": {},
      "type": "stdio"
    }
  }
}
```

> **注意**：将 `/Users/yourname/projects/dm-mcp` 替换为你的实际项目路径。

### 步骤二：重启 Claude Code

保存设置后，重启 Claude Code。MCP 服务器会自动启动并注册所有工具。

### 可用工具一览

| 工具 | 说明 |
|------|------|
| `dm_connect` | 测试数据库连接 |
| `dm_query` | 执行只读 SQL 查询 |
| `dm_explain_plan` | 分析 SELECT 执行计划 |
| `dm_list_tables` | 列出数据库表 |
| `dm_list_views` | 列出数据库视图 |
| `dm_describe_table` | 查看表结构 |
| `dm_get_view_definition` | 查看视图定义 |
| `dm_update_config` | 运行时更新数据库配置 |
