# 达梦数据库 MCP 服务器

基于 FastMCP 框架构建的达梦数据库 MCP 服务器，提供完整的数据库操作工具。

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install dmPython
```

### 2. 数据库配置

项目使用配置文件管理系统，所有数据库连接信息都存储在 `dm_config.json` 文件中。

#### 配置文件管理（推荐）

首次启动服务器时，系统会自动创建 `dm_config.json` 配置文件，包含默认配置：

```json
{
  "database": {
    "host": "192.168.2.38",
    "port": 5236,
    "user": "SYSDBA",
    "password": "SYSDBA001",
    "schema": "aiops"
  }
}
```

#### 修改配置方式

**方式一：直接编辑配置文件**
1. 编辑 `dm_config.json` 文件
2. 修改数据库连接参数
3. 重启服务器使配置生效

**方式二：使用 MCP 工具动态配置**
使用 `dm_update_config()` 工具可以在运行时修改配置：
```python
# 修改主机地址
dm_update_config(host="192.168.1.100")

# 修改端口和用户
dm_update_config(port=5237, user="NEW_USER")

# 修改完整配置
dm_update_config(
    host="192.168.1.100",
    port=5237,
    user="NEW_USER",
    password="NEW_PASSWORD",
    schema="new_schema"
)
```

### 3. 启动服务器

```bash
python main.py
```

### 4. 测试连接

```bash
python dm_client.py
```

## 📋 默认配置

| 环境变量 | 默认值 | 说明 |
|---------|--------|------|
| DM_HOST | 192.168.2.38 | 数据库主机地址 |
| DM_PORT | 5236 | 数据库端口 |
| DM_USER | SYSDBA | 数据库用户名 |
| DM_PASSWORD | SYSDBA001 | 数据库密码 |
| DM_SCHEMA | aiops | 默认数据库模式 |

## 🔧 故障排除

### 连接问题排查步骤：

1. **检查配置文件**：
   ```bash
   # 查看当前配置
   cat dm_config.json

   # 验证配置格式
   python -c "import json; print(json.load(open('dm_config.json')))"
   ```

2. **检查网络连通性**：
   ```bash
   # 使用配置文件中的主机地址
   ping $(python -c "import json; print(json.load(open('dm_config.json'))['database']['host'])")
   ```

3. **检查端口可用性**：
   ```bash
   # 使用配置中的主机和端口
   telnet $(python -c "import json; print(json.load(open('dm_config.json'))['database']['host'])") \
          $(python -c "import json; print(json.load(open('dm_config.json'))['database']['port'])")
   ```

4. **验证用户权限**：
   - 确认配置文件中的用户名和密码正确
   - 确认用户有访问指定模式的权限
   - 使用 `dm_connect()` 工具测试连接

5. **配置文件问题**：
   - 如果配置文件损坏，删除 `dm_config.json` 并重启服务器
   - 检查文件权限：确保可读写
   - 使用 `dm_update_config()` 工具重新配置

6. **检查防火墙设置**：
   - 确认数据库端口开放（默认 5236）
   - 检查网络防火墙规则
   - 验证主机之间的网络连通性

## 🛠️ MCP 工具

服务器提供以下 8 个核心数据库工具：

### 数据库连接工具
- `dm_connect()`: 测试数据库连接和健康检查
- `dm_update_config(host?, port?, user?, password?, schema?)`: 动态修改数据库连接配置并保存到配置文件

### 数据库查询工具
- `dm_query(sql)`: 执行安全 SQL 查询（支持 SELECT、EXPLAIN、EXPLAIN PLAN）
- `dm_list_tables(schema?)`: 列出数据库表
- `dm_list_views(schema?)`: 列出数据库视图
- `dm_describe_table(table_name, schema?)`: 获取表结构
- `dm_get_view_definition(view_name, schema?)`: 获取视图定义

### 执行计划工具
- `dm_explain_plan(select_sql)`: 在单次调用中获取 SELECT 语句的执行计划（推荐）
  - 在同一 JDBC session 内完成计划生成与读取，优先使用达梦驱动直接返回的计划文本
  - 仅接受 SELECT 语句，自动拒绝 DML/DDL

## ⚠️ 重要说明

- **安全限制**：`dm_query` 仅允许执行只读语句（SELECT、EXPLAIN、EXPLAIN PLAN），所有 DML、DDL、授权语句都会被拒绝
- **执行计划推荐使用 `dm_explain_plan`**：建议使用专用工具获取 SELECT 的执行计划。当前实现优先走 `EXPLAIN SELECT ...` + 达梦 JDBC 驱动直接计划接口，不再默认依赖 `PLAN_TABLE`。
- **大小写敏感**：达梦数据库对表名和模式名大小写敏感，请使用用户提供的确切大小写
- **参数验证**：所有输入参数都会进行严格验证，防止 SQL 注入
- **连接管理**：自动管理数据库连接，确保资源正确释放

### 语句类型元数据

`dm_query` 返回的 `metadata.additional_info` 包含以下字段用于标识语句类型：

| 字段 | 说明 | 示例值 |
|------|------|--------|
| `statement_type` | 语句类型 | `SELECT`, `EXPLAIN`, `EXPLAIN_PLAN` |
| `query_type` | 查询类型（人类可读） | `SELECT`, `EXPLAIN`, `EXPLAIN_PLAN` |
| `execution_statement_type` | 实际执行路径对应的语句类型 | `EXPLAIN` |
| `normalized_sql` | 规范化后实际执行的 SQL（如适用） | `EXPLAIN SELECT * FROM users` |

**示例：执行 EXPLAIN**
```json
{
  "success": true,
  "metadata": {
    "additional_info": {
      "statement_type": "EXPLAIN",
      "query_type": "EXPLAIN"
    }
  }
}
```

**示例：执行 EXPLAIN PLAN**
```json
{
  "success": true,
  "sql": "EXPLAIN SELECT * FROM users WHERE id = 1",
  "metadata": {
    "additional_info": {
      "statement_type": "EXPLAIN_PLAN",
      "query_type": "EXPLAIN_PLAN",
      "execution_statement_type": "EXPLAIN",
      "normalized_sql": "EXPLAIN SELECT * FROM users WHERE id = 1"
    }
  }
}
```

**示例：使用 dm_explain_plan 获取执行计划（推荐）**
```json
{
  "success": true,
  "sql": "EXPLAIN SELECT * FROM users WHERE id = 1",
  "data": {
    "columns": ["PLAN_LINE"],
    "rows": [
      ["1   #NSET2: [1, 1, 1]"],
      ["2     #PRJT2: [1, 1, 1]; exp_num(1), is_atom(FALSE)"]
    ]
  },
  "metadata": {
    "statement_type": "EXPLAIN_PLAN",
    "query_type": "EXPLAIN_PLAN",
    "execution_statement_type": "EXPLAIN",
    "diagnostic_path": "DIRECT_EXPLAIN",
    "original_sql": "SELECT * FROM users WHERE id = 1",
    "row_count": 2
  }
}
```

> ⚠️ **为什么用 `dm_explain_plan` 而不是 `dm_query("EXPLAIN SELECT ...")`:**
> `dm_explain_plan` 会固定走仓库当前验证通过的执行计划路径，并把“用户语义”与“实际执行路径”一起写入元数据。
> 这样即使目标库只支持 `EXPLAIN SELECT ...` 而不支持 `EXPLAIN PLAN ...`，工具仍然能稳定返回计划。

## 🐛 常见问题

### 连接失败

1. **"无法安装 dmPython 包"**
   ```bash
   pip install dmPython
   ```

2. **"连接被拒绝"**
   - 检查数据库服务是否运行
   - 验证连接配置
   - 检查防火墙设置

3. **"认证失败"**
   - 验证用户名和密码
   - 检查用户权限设置

4. **"超时错误"**
   - 检查网络延迟
   - 增加连接超时时间

## 📁 项目结构

### 核心文件

- `main.py`: MCP 服务器主入口（定义7个数据库工具）
- `dm_client.py`: 数据库客户端封装（DmClient 类和 DmConfig 配置类）
- `config.py`: 配置管理模块（ConfigManager 类，处理配置文件读写）
- `pyproject.toml`: 项目配置
- `dm_config.json`: 数据库连接配置文件（自动生成）

### 配置文件管理

- **配置文件位置**: `dm_config.json`（项目根目录）
- **自动创建**: 首次运行时自动生成默认配置
- **动态更新**: 支持 `dm_update_config()` 工具运行时修改
- **格式验证**: 自动验证配置格式和参数有效性

### 添加自定义工具

在 `main.py` 中使用 `@mcp.tool()` 装饰器添加新工具：

```python
@mcp.tool()
def your_tool(param: str) -> dict:
    """工具说明"""
    # 实现逻辑
    return {"result": "value"}
```

## 📄 许可证

[请添加许可证信息]

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📞 支持

如有问题，请提交 GitHub Issue。
