# 非阻塞 I/O 和超时控制规范

## ADDED Requirements

### Requirement: I/O 操作超时控制

系统 SHALL 为所有与 Java 守护进程的 I/O 操作提供超时保障，防止无限阻塞。

#### Scenario: stdout 读取超时
- **WHEN** 从 Java 守护进程 stdout 读取数据
- **AND** 在配置的超时时间内（默认 30 秒）未收到完整行
- **THEN** 系统应终止读取操作
- **AND** 返回 `None` 或抛出 `TimeoutError`
- **AND** 记录超时事件到日志

#### Scenario: stdin 写入超时
- **WHEN** 向 Java 守护进程 stdin 写入数据
- **AND** 写入操作阻塞超过配置的超时时间
- **THEN** 系统应终止写入操作
- **AND** 抛出 `JavaBridgeError` 异常

#### Scenario: 可配置超时时间
- **WHEN** 管理员设置 `io_timeout` 配置参数
- **THEN** 系统应使用该值作为 I/O 超时时间
- **AND** 有效范围为 5-300 秒
- **AND** 无效值应回退到默认值 30 秒

### Requirement: 基于线程的超时包装器

系统 SHALL 使用 `threading.Timer` 和 `queue.Queue` 实现非阻塞 I/O 读取。

#### Scenario: 创建超时读取线程
- **WHEN** 需要从 stdout 读取数据
- **THEN** 系统应在独立线程中执行阻塞式 `readline()`
- **AND** 主线程等待超时时间
- **AND** 线程应标记为 daemon，避免阻止进程退出

#### Scenario: 线程正常完成
- **WHEN** 读取线程在超时前完成
- **THEN** 系统应从队列中获取读取结果
- **AND** 返回读取的数据行

#### Scenario: 线程超时
- **WHEN** 读取线程未在超时时间内完成
- **THEN** 系统应放弃等待线程
- **AND** 返回 `None` 表示超时
- **AND** 线程应在后台继续执行（daemon 线程会随进程清理）

### Requirement: 超时后的自动恢复

系统 SHALL 在 I/O 超时后自动恢复 Java 守护进程并重试查询。

#### Scenario: 检测到 I/O 超时
- **WHEN** I/O 操作超时
- **THEN** 系统应检查 Java 守护进程健康状态
- **AND** 如果进程不健康，应关闭并重启进程
- **AND** 重试当前查询一次

#### Scenario: 恢复成功
- **WHEN** 重试查询成功执行
- **THEN** 系统应返回查询结果
- **AND** 记录恢复事件到日志（INFO 级别）

#### Scenario: 恢复失败
- **WHEN** 重试查询仍然失败
- **THEN** 系统应抛出 `JavaBridgeError` 异常
- **AND** 记录失败详情到日志（ERROR 级别）

### Requirement: 超时事件日志记录

系统 SHALL 记录所有超时事件以便诊断和监控。

#### Scenario: 记录超时事件
- **WHEN** I/O 操作超时
- **THEN** 系统应记录以下信息：
  - 超时类型（stdin/stdout）
  - 超时时间
  - 当前操作（查询/更新）
  - Java 进程状态

#### Scenario: 记录恢复事件
- **WHEN** 系统自动恢复并重试成功
- **THEN** 系统应记录以下信息：
  - 恢复操作类型（重启进程/仅重试）
  - 重试耗时
  - 查询结果（摘要）

### Requirement: 超时配置管理

系统 SHALL 支持通过配置文件和代码配置 I/O 超时参数。

#### Scenario: 从配置文件读取超时配置
- **WHEN** `dm_config.json` 包含 `io_timeout` 参数
- **THEN** 系统应使用该值覆盖默认值
- **AND** 验证参数范围（5-300 秒）

#### Scenario: 代码中指定超时
- **WHEN** 调用 `JavaBridgeClient` 构造函数时传入 `io_timeout` 参数
- **THEN** 系统应使用该值覆盖配置文件和默认值

#### Scenario: 默认超时值
- **WHEN** 未指定 `io_timeout` 参数
- **THEN** 系统应使用默认值 30 秒
