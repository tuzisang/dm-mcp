# 达梦数据库 MCP 服务器 - Java 守护进程版本

## 架构变更

本项目已从 `dmpython` 驱动迁移到 **Java 守护进程 + JDBC 驱动**架构。

### 为什么改变？

- **跨平台兼容性**：`dmpython` 不支持 macOS ARM64 (Apple Silicon)
- **高性能连接池**：使用 HikariCP 提供更好的并发性能
- **零启动开销**：Java 守护进程长期运行，避免重复启动

### 新架构

```
Python MCP Server
    ↓ (JSON over stdin/stdout)
Java Daemon (DmJdbcBridge.class)
    ↓ (JDBC + HikariCP)
达梦数据库
```

## 系统要求

- **Python**: >= 3.12
- **Java**: JRE 8+（通过 SDKMAN 或系统安装）
- **Maven**: 用于获取 JDBC 驱动（已包含在 `lib/` 目录）

## 依赖 JAR 文件

项目包含以下 JAR 文件（位于 `lib/` 目录）：

- `dm-jdbc-1.8.jar` - 达梦数据库 JDBC 驱动
- `HikariCP-4.0.3.jar` - 高性能连接池（Java 8 兼容版本）
- `slf4j-api-2.0.12.jar` - 日志门面

## Java 环境配置

### SDKMAN（推荐）

```bash
sdk install java 8.0.482-zulu
```

### 系统默认 Java

确保 `JAVA_HOME` 设置正确：

```bash
export JAVA_HOME=/path/to/java
export PATH=$JAVA_HOME/bin:$PATH
```

## 使用示例

```python
from db.client import create_client

# 创建客户端
client = create_client()

# 执行查询
result = client.execute_query("SELECT * FROM USER_TABLES")
print(f"找到 {len(result)} 张表")

# 使用上下文管理器
with create_client() as client:
    tables = client.list_tables()
    for table in tables:
        print(table['TABLE_NAME'])
```

## 配置文件

`dm_config.json` 格式：

```json
{
  "database": {
    "host": "192.168.2.38",
    "port": 5236,
    "user": "SYSDBA",
    "password": "your_password",
    "schema": "your_schema",
    "use_pool": true,
    "pool_min_connections": 2,
    "pool_max_connections": 10
  }
}
```

## 故障排查

### Java 找不到

```
找不到 Java 运行时。请确保已安装 Java 8+，
或通过 SDKMAN 安装，或设置 JAVA_HOME 环境变量
```

**解决方案**：
```bash
# 安装 Java（SDKMAN）
sdk install java 8.0.482-zulu

# 或设置 JAVA_HOME
export JAVA_HOME=/Library/Java/JavaVirtualMachines/jdk1.8.0_482.jdk/Contents/Home
```

### 连接超时

```
查询超时（120秒）
```

**解决方案**：
- 检查 VPN 连接
- 检查数据库服务器是否可达
- 在 `dm_config.json` 中调整 `query_timeout`

## 开发

### 重新编译 Java 桥接服务

```bash
cd db
javac -cp ../lib/dm-jdbc-1.8.jar:../lib/HikariCP-4.0.3.jar:../lib/slf4j-api-2.0.12.jar DmJdbcBridge.java
```

### 测试

```bash
python test_step_by_step.py
```

## 性能特性

- **HikariCP 连接池**：最小 2 个连接，最大 10 个连接
- **守护进程持久化**：无进程启动开销
- **JSON 通信**：轻量级序列化
- **AI 友好**：自动分页支持，避免大结果集

## 许可证

MIT License
