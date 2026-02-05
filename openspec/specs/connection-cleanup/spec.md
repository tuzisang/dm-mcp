# 连接资源清理规范

## ADDED Requirements

### Requirement: Java 端查询超时连接释放

Java 守护进程 SHALL 在查询超时或异常时确保数据库连接被正确关闭。

#### Scenario: 正常查询完成
- **WHEN** 查询成功执行完成
- **THEN** 系统应使用 try-with-resources 自动关闭 `ResultSet`、`PreparedStatement` 和 `Connection`
- **AND** 连接应返回 HikariCP 连接池

#### Scenario: 查询执行异常
- **WHEN** 查询执行过程中抛出异常
- **THEN** try-with-resources 应确保 `PreparedStatement` 和 `Connection` 被关闭
- **AND** 连接应返回 HikariCP 连接池
- **AND** 异常应传递给 Python 端

#### Scenario: JDBC 查询超时
- **WHEN** 查询执行时间超过 `statement_timeout`（默认 120 秒）
- **THEN** JDBC 驱动应自动取消查询
- **AND** 自动关闭 `Statement` 和 `Connection`
- **AND** 返回超时错误响应：`{"error": true, "message": "Query timeout"}`

### Requirement: Python 端进程重启前连接池关闭

Python 端 SHALL 在重启 Java 守护进程前确保 HikariCP 连接池已完全关闭。

#### Scenario: 优雅关闭 Java 进程
- **WHEN** Python 端需要重启 Java 守护进程
- **THEN** 应先向 Java 进程发送关闭消息：`{"type": "shutdown"}`
- **AND** 等待 Java 进程优雅退出（最多 5 秒）
- **AND** Java 进程应关闭 HikariCP 连接池（释放所有连接）
- **AND** Python 日志应记录 "Java bridge shutdown gracefully"

#### Scenario: 强制终止 Java 进程
- **WHEN** Java 进程在 5 秒内未退出
- **THEN** Python 端应使用 `kill()` 强制终止进程
- **AND** 记录警告日志："Java bridge force killed"
- **AND** 操作系统会回收所有资源（包括连接）

#### Scenario: 验证进程已退出
- **WHEN** 调用 `shutdown()` 方法
- **THEN** 应检查 `process.poll()` 确认进程已退出
- **AND** 如进程仍在运行，应抛出 `JavaBridgeError` 异常

### Requirement: Java 端关闭钩子

Java 守护进程 SHALL 注册 JVM 关闭钩子，确保进程退出时连接池被正确关闭。

#### Scenario: 正常退出时触发关闭钩子
- **WHEN** Java 守护进程接收到关闭信号（如 SIGTERM）
- **THEN** 关闭钩子应执行 `shutdown()` 方法
- **AND** 关闭 HikariCP 连接池：`dataSource.close()`
- **AND** 关闭心跳线程池：`executor.shutdownNow()`
- **AND** 记录日志："HikariCP pool is shutting down"

#### Scenario: 异常崩溃时触发关闭钩子
- **WHEN** Java 守护进程因未捕获异常崩溃
- **THEN** JVM 应在退出前触发关闭钩子
- **AND** 尝试关闭 HikariCP 连接池
- **AND** 记录错误日志

#### Scenario: Python 端发送 shutdown 消息
- **WHEN** Python 端发送 `{"type": "shutdown"}` 消息
- **THEN** Java 端应识别关闭消息类型
- **AND** 调用 `shutdown()` 方法
- **AND** 退出主循环（结束进程）

### Requirement: 连接泄漏检测和告警

系统 SHALL 监控连接池状态，检测连接泄漏并发出告警。

#### Scenario: 检测连接池接近满载
- **WHEN** 活跃连接数连续 5 分钟超过最大连接数的 90%
- **THEN** 系统应记录警告日志
- **AND** 日志应包含："Possible connection leak detected"
- **AND** 日志应包含当前活跃连接数和最大连接数

#### Scenario: 检测连接等待时间过长
- **WHEN** HikariCP 的 `waiting_threads` 大于 0 超过 30 秒
- **THEN** 系统应记录警告日志
- **AND** 日志应包含："Connection wait timeout"
- **AND** 建议增加 `pool_max_connections`

#### Scenario: 检测空闲连接过多
- **WHEN** 空闲连接数超过 `max_pool_size` 的 80%
- **THEN** 系统应记录信息日志
- **AND** 日志应包含："High idle connection count"
- **AND** 建议减少 `pool_min_connections`

### Requirement: 连接资源验证测试

系统 SHALL 提供测试验证连接资源正确释放。

#### Scenario: 超时后连接数验证
- **WHEN** 执行查询并手动触发超时（如杀掉 Java 进程）
- **THEN** 重启后 HikariCP 的 `active_connections` 应为 0
- **AND** 新查询应能正常获取连接

#### Scenario: 并发查询后连接数验证
- **WHEN** 并发执行 20 个查询
- **AND** 所有查询完成或超时
- **THEN** HikariCP 的 `active_connections` 应降至 `pool_min_connections` 以下
- **AND** 不应超过 `pool_max_connections`

#### Scenario: 长时间运行后连接数验证
- **WHEN** 系统运行 1 小时并处理 100 个查询
- **THEN** HikariCP 的 `total_connections` 应不超过 `pool_max_connections`
- **AND** 不应出现 "Connection pool exhausted" 错误

### Requirement: 连接清理日志记录

系统 SHALL 详细记录连接清理操作以便诊断。

#### Scenario: 记录连接获取
- **WHEN** Java 端从连接池获取连接
- **AND** 日志级别为 DEBUG
- **THEN** 应记录："Got connection from pool, active=X, idle=Y"

#### Scenario: 记录连接释放
- **WHEN** Java 端将连接返回连接池
- **AND** 日志级别为 DEBUG
- **THEN** 应记录："Returned connection to pool, active=X, idle=Y"

#### Scenario: 记录连接池关闭
- **WHEN** Java 端关闭 HikariCP 连接池
- **THEN** 应记录 INFO 日志："HikariCP pool shutting down, active=X connections closed"

### Requirement: HikariCP 配置强制资源回收

系统 SHALL 配置 HikariCP 参数确保即使个别连接泄漏也会被强制回收。

#### Scenario: 配置连接最大生命周期
- **WHEN** HikariCP 初始化
- **THEN** 应设置 `setMaxLifetime(1800000)`（30 分钟）
- **AND** 超过 30 分钟的连接将被强制关闭并重建

#### Scenario: 配置空闲连接超时
- **WHEN** HikariCP 初始化
- **THEN** 应设置 `setIdleTimeout(300000)`（5 分钟）
- **AND** 空闲超过 5 分钟的连接将被关闭

#### Scenario: 配置连接泄漏检测
- **WHEN** HikariCP 初始化
- **THEN** 应设置 `setLeakDetectionThreshold(60000)`（60 秒）
- **AND** 连接借用超过 60 秒未归还应记录警告日志
