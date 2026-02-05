# 提案：使用 jaydebeapi + HikariCP 重构达梦数据库 MCP 服务器

## Why

当前项目使用 `dmpython` 作为达梦数据库驱动，但该驱动**不支持 macOS ARM64 (Apple Silicon)** 平台，导致在 Mac 环境下无法正常开发和运行。通过使用 **jaydebeapi**（JDBC 桥接）配合 **HikariCP**（高性能连接池），可以跨平台兼容地连接达梦数据库，同时提升连接性能和稳定性。

## What Changes

### 核心改造

- **移除 dmpython 依赖**：完全移除对 dmpython 的依赖，消除平台兼容性问题
- **引入 jaydebeapi**：使用 JDBC 桥接方式调用达梦数据库 JDBC 驱动
- **引入 HikariCP 连接池**：使用业界性能最好的 Java 连接池，提升并发性能
- **创建 Java 守护进程**：Java 桥接服务作为长期守护进程运行，避免重复启动开销
- **重构客户端实现**：`db/client.py` 从 dmpython 实现切换到 jaydebeapi + HikariCP 实现

### 新增组件

- **Java 守护进程** (`DmJdbcBridge.java`)：提供 SQL 执行、连接管理、结果集转换功能；作为长期守护进程运行，通过标准输入/输出与 Python 通信
- **HikariCP 配置**：连接池参数配置（最小/最大连接数、超时设置等）
- **JAR 依赖管理**：从本地 Maven 仓库复制达梦 JDBC 驱动和 HikariCP JAR 包到项目 `lib/` 目录

### 保持兼容

- **MCP 工具接口不变**：7 个 MCP 工具的接口和行为保持完全一致
- **配置文件格式不变**：`dm_config.json` 配置格式保持兼容
- **API 调用方式不变**：上层调用者无需修改代码

## Capabilities

### New Capabilities

- **jdbc-connection**: JDBC 数据库连接能力，使用 jaydebeapi 通过 JDBC 驱动连接达梦数据库
- **connection-pool**: HikariCP 连接池管理，提供高性能、可配置的数据库连接池
- **java-bridge**: Java 守护进程桥接服务，通过 stdin/stdout 进行 JSON 通信，进程长期存活避免启动开销
- **cross-platform**: 跨平台兼容性，支持 macOS ARM64、Linux、Windows

### Modified Capabilities

- **database-client**: 数据库客户端实现从 dmpython 迁移到 jaydebeapi，但对外接口保持不变

## Impact

### 受影响的代码

- `db/client.py`：核心客户端实现，需要完全重写
- `db/config.py`：配置管理，需要增加 HikariCP 相关配置
- `main.py`：MCP 服务器入口，需要初始化 Java 桥接服务
- `pyproject.toml`：依赖项修改（移除 dmpython，添加 jaydebeapi）
- `lib/`：新增 JAR 文件目录（dm-jdbc、HikariCP、slf4j）

### 依赖变更

**移除：**
- `dmpython>=2.5.26`

**新增：**
- `jaydebeapi>=1.2.3`（Python JDBC 桥接）
- `lib/dm-jdbc-1.8.jar`（达梦 JDBC 驱动）
- `lib/HikariCP-5.1.0.jar`（HikariCP 连接池）
- `lib/slf4j-api-2.0.16.jar`（日志门面）

### 系统要求

- **Java 运行时**：需要 JRE 8+（通过 SDKMAN 或系统安装）
- **Python 版本**：保持 >=3.12 要求

### 风险评估

- **低风险**：MCP 工具接口不变，上层调用者无感知
- **低风险**：Java 守护进程模式避免了进程启动开销，性能接近原生实现
- **已验证**：测试用例已验证 Java + JDBC 驱动可以成功连接达梦数据库（发现 504 张表）
