# 实施任务清单

## 1. 依赖准备

- [x] 1.1 从本地 Maven 仓库复制 HikariCP JAR 到 lib/ 目录
- [x] 1.2 从本地 Maven 仓库复制 SLF4J JAR 到 lib/ 目录
- [x] 1.3 验证 lib/ 目录包含所有必需的 JAR 文件（dm-jdbc、HikariCP、slf4j-api）
- [x] 1.4 更新 pyproject.toml 移除 dmpython 依赖

## 2. Java 桥接服务实现

- [x] 2.1 创建 DmJdbcBridge.java 基础框架
- [x] 2.2 实现 HikariCP 数据源配置
- [x] 2.3 实现 SQL 执行功能（SELECT 查询）
- [x] 2.4 实现 JSON 通信协议（输入请求、输出结果）
- [x] 2.5 添加异常处理和错误码映射
- [x] 2.6 编译并测试 Java 桥接服务（504 张表）

## 3. Python 桥接层实现

- [x] 3.1 创建 db/java_bridge.py 模块
- [x] 3.2 实现 Java 进程启动和管理
- [x] 3.3 实现 JSON 请求/响应序列化
- [x] 3.4 实现超时控制和进程清理
- [x] 3.5 添加 Java 异常到 Python 异常的转换

## 4. 配置管理更新

- [x] 4.1 更新 db/config.py 添加 HikariCP 配置字段
- [x] 4.2 创建 db/pool.py 连接池配置模块
- [x] 4.3 添加 Java 环境检测逻辑（SDKMAN、JAVA_HOME）
- [x] 4.4 更新配置验证逻辑

## 5. 数据库客户端重写

- [x] 5.1 重写 db/client.py 的 DmClient.__init__ 方法
- [x] 5.2 重写 execute_query 方法（改用 Java 桥接）
- [x] 5.3 重写 execute_update 方法（改用 Java 桥接）
- [x] 5.4 重写 list_tables 方法
- [x] 5.5 重写 list_views 方法
- [x] 5.6 重写 describe_table 方法
- [x] 5.7 重写 get_view_definition 方法
- [x] 5.8 实现上下文管理器（__enter__、__exit__）

## 6. MCP 工具适配

- [x] 6.1 更新 tools/connection.py 适配新客户端实现
- [x] 6.2 更新 tools/query.py 适配新客户端实现
- [x] 6.3 更新 tools/schema.py 适配新客户端实现
- [x] 6.4 更新 main.py 的 MCP 服务器初始化逻辑

## 7. 测试验证

- [x] 7.1 运行 test_jaydebeapi.py 验证基础连接
- [x] 7.2 测试所有 7 个 MCP 工具功能（通过 Java 桥接）
- [x] 7.3 测试连接池参数配置（HikariCP 2-10 连接）
- [x] 7.4 测试异常处理（连接失败、超时、SQL 错误）
- [x] 7.5 测试跨平台兼容性（macOS ARM64 ✅）
- [x] 7.6 运行现有测试用例确保回归

## 8. 文档更新

- [x] 8.1 创建 MIGRATION.md 添加 Java 环境要求说明
- [x] 8.2 更新 pyproject.toml 添加 JAR 依赖说明
- [x] 8.3 更新 JAR 依赖管理说明
- [x] 8.4 添加故障排查指南（Java 环境问题）

## 9. 清理和收尾

- [x] 9.1 删除旧的 dmpython 相关代码（从 pyproject.toml 移除）
- [x] 9.2 清理未使用的导入和变量
- [x] 9.3 更新 git 忽略文件（编译后的 .class 文件）
- [x] 9.4 提交代码并创建 PR

---

## 完成总结

**提交**: `5bcdedc` - refactor: 迁移到 Java 守护进程架构

**关键成果**:
- ✅ 移除 dmpython 依赖
- ✅ 实现 Java 守护进程 + HikariCP 连接池
- ✅ 支持 macOS ARM64 (Apple Silicon)
- ✅ 所有接口保持兼容
- ✅ 测试通过（504 张表）

**新增文件**:
- `db/DmJdbcBridge.java` - Java 守护进程
- `db/java_bridge.py` - Python 桥接客户端
- `db/client.py` - 重写的数据库客户端
- `lib/` - JAR 依赖目录
- `MIGRATION.md` - 迁移文档

**性能特性**:
- HikariCP 连接池（最小 2，最大 10）
- 守护进程持久运行（零启动开销）
- JSON 通信（轻量级序列化）
