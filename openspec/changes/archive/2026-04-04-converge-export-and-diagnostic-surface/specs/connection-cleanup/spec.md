## MODIFIED Requirements

### Requirement: Java 端查询超时连接释放

Java 守护进程 SHALL 在查询超时或异常时确保数据库连接被正确关闭。

#### Scenario: 正常查询完成
- **WHEN** 查询成功执行完成
- **THEN** 系统应使用 try-with-resources 自动关闭 `ResultSet`、`Statement` 和 `Connection`
- **AND** 连接应返回 HikariCP 连接池

#### Scenario: 查询执行异常
- **WHEN** 查询执行过程中抛出异常
- **THEN** try-with-resources 应确保 `Statement` 和 `Connection` 被关闭
- **AND** 连接应返回 HikariCP 连接池
- **AND** 异常应传递给 Python 端

#### Scenario: JDBC 查询超时
- **WHEN** 查询执行时间超过 `statement_timeout`
- **THEN** JDBC 驱动应自动取消查询
- **AND** 自动关闭 `Statement` 和 `Connection`
- **AND** 返回超时错误响应：`{"error": true, "message": "Query timeout"}`

### Requirement: Python 端共享运行时关闭

Python 端 SHALL 在重建共享运行时或进程退出前关闭现有 Java 守护进程。

#### Scenario: 优雅关闭 Java 进程
- **WHEN** Python 端需要重建或关闭共享运行时
- **THEN** 应先向 Java 进程发送关闭消息：`{"type": "shutdown"}`
- **AND** 等待 Java 进程优雅退出（最多 5 秒）
- **AND** Java 进程应关闭 HikariCP 连接池（释放所有连接）

#### Scenario: 强制终止 Java 进程
- **WHEN** Java 进程在 5 秒内未退出
- **THEN** Python 端应使用 `kill()` 强制终止进程
- **AND** 操作系统回收剩余资源

### Requirement: Java 端关闭钩子

Java 守护进程 SHALL 注册 JVM 关闭钩子，确保进程退出时连接池被正确关闭。

#### Scenario: 正常退出时触发关闭钩子
- **WHEN** Java 守护进程接收到关闭信号
- **THEN** 关闭钩子应执行 `shutdown()` 方法
- **AND** 关闭 HikariCP 连接池：`dataSource.close()`

#### Scenario: Python 端发送 shutdown 消息
- **WHEN** Python 端发送 `{"type": "shutdown"}` 消息
- **THEN** Java 端应识别关闭消息类型
- **AND** 调用 `shutdown()` 方法
- **AND** 退出主循环

## REMOVED Requirements

### Requirement: 连接泄漏检测和告警
**Reason**: 当前阶段不再在 MCP 进程内承载监控/告警职责。
**Migration**: 如需观测连接池，应使用数据库或运行环境外部监控，而不是内置逻辑。

### Requirement: 连接资源验证测试
**Reason**: 当前验证面只保留可重复的单元测试、编译检查和 MCP 冒烟测试。
**Migration**: 使用自动化测试和显式冒烟测试替代环境敏感的资源验证脚本。

### Requirement: 连接清理日志记录
**Reason**: 详细连接清理日志不属于当前最小闭环的必要能力。
**Migration**: 依赖异常返回和必要的运行时错误信息进行诊断。
