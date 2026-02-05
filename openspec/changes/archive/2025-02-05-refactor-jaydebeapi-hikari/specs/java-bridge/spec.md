# Java 守护进程桥接服务规范

## ADDED Requirements

### Requirement: Java 守护进程启动和管理

系统 SHALL 在 MCP 服务器启动时创建 Java 守护进程，在服务器退出时终止进程。

#### Scenario: 启动守护进程
- **WHEN** MCP 服务器初始化时
- **THEN** 系统应启动 Java 守护进程
- **AND** 包含正确的 classpath（JAR 文件）
- **AND** 初始化 HikariCP 连接池

#### Scenario: 终止守护进程
- **WHEN** MCP 服务器关闭时
- **THEN** 系统应优雅地终止 Java 守护进程
- **AND** 关闭所有数据库连接
- **AND** 释放所有相关资源

### Requirement: 守护进程通信协议

系统 SHALL 使用标准输入/输出与 Java 守护进程进行 JSON 格式通信。

#### Scenario: 发送 SQL 请求
- **WHEN** Python 需要执行数据库操作
- **THEN** 应通过 stdin 发送 JSON 格式的 SQL 请求
- **AND** 请求应包含 SQL 语句和参数

#### Scenario: 接收查询结果
- **WHEN** Java 完成查询执行
- **THEN** 应通过 stdout 返回 JSON 格式的查询结果
- **AND** 结果应包含行数据和元数据

#### Scenario: 接收错误信息
- **WHEN** Java 执行过程中发生异常
- **THEN** 应通过 stderr 输出错误信息
- **AND** 通过 stdout 返回 JSON 格式的错误响应

### Requirement: 守护进程健康检查

系统 SHALL 定期检查 Java 守护进程的健康状态。

#### Scenario: 进程存活检查
- **WHEN** 执行数据库操作前
- **THEN** 系统应检查 Java 进程是否仍在运行
- **AND** 如果进程已崩溃，应自动重启

#### Scenario: Ping 心跳检测
- **WHEN** 配置了健康检查间隔
- **THEN** 系统应定期发送 ping 消息
- **AND** 验证 Java 进程响应正常

### Requirement: 守护进程异常处理

系统 SHALL 捕获并转换 Java 异常为 Python 异常。

#### Scenario: Java 异常转换
- **WHEN** Java 代码抛出异常
- **THEN** 系统应捕获异常并转换为对应的 Python 异常类型
- **AND** 保留原始异常信息和堆栈跟踪

#### Scenario: 进程崩溃处理
- **WHEN** Java 守护进程意外崩溃
- **THEN** 系统应检测到进程退出
- **AND** 抛出 `RuntimeError` 异常
- **AND** 尝试自动重启守护进程

### Requirement: 类路径管理

系统 SHALL 正确构建 Java classpath，包含所有必需的 JAR 文件。

#### Scenario: 构建classpath
- **WHEN** 启动 Java 守护进程
- **THEN** classpath 应包含 dm-jdbc-1.8.jar、HikariCP-5.1.0.jar、slf4j-api-2.0.16.jar
- **AND** 所有 JAR 文件应存在于 lib/ 目录

#### Scenario: 缺少 JAR 文件
- **WHEN** 必需的 JAR 文件不存在
- **THEN** 系统应在启动前报错
- **AND** 提示用户缺少哪个文件

### Requirement: 守护进程超时控制

系统 SHALL 为每个操作设置超时时间，防止无限等待。

#### Scenario: 查询超时
- **WHEN** 查询执行时间超过配置的超时时间
- **THEN** 系统应终止当前操作
- **AND** 抛出 `TimeoutError` 异常
- **AND** 守护进程继续运行（不影响后续查询）

#### Scenario: 启动超时
- **WHEN** Java 守护进程启动超时
- **THEN** 系统应放弃启动
- **AND** 抛出 `RuntimeError` 异常
