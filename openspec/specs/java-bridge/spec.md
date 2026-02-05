# Java 桥接服务增强规范

## MODIFIED Requirements

### Requirement: 守护进程通信协议

系统 SHALL 使用标准输入/输出与 Java 守护进程进行 JSON 格式通信，支持多种消息类型。

#### Scenario: 发送 SQL 请求
- **WHEN** Python 需要执行数据库操作
- **THEN** 应通过 stdin 发送 JSON 格式的 SQL 请求
- **AND** 请求应包含 SQL 语句和参数
- **AND** 请求格式应为：`{"sql": "...", "params": ["...", "..."]}`

#### Scenario: 接收查询结果
- **WHEN** Java 完成查询执行
- **THEN** 应通过 stdout 返回 JSON 格式的查询结果
- **AND** 结果应包含行数据和元数据

#### Scenario: 接收错误信息
- **WHEN** Java 执行过程中发生异常
- **THEN** 应通过 stdout 返回 JSON 格式的错误响应（不再使用 stderr）
- **AND** 错误格式应为：`{"error": true, "message": "..."}`
- **AND** stderr 应仅用于 Java 启动阶段的致命错误

#### Scenario: 接收心跳消息
- **WHEN** Java 守护进程定期发送心跳
- **THEN** 应通过 stdout 返回心跳消息
- **AND** 心跳格式应为：`{"type": "heartbeat", "timestamp": <ms>}`
- **AND** Python 端应更新 `last_heartbeat` 时间戳

#### Scenario: 查询连接池状态
- **WHEN** Python 需要查询连接池状态
- **THEN** 应通过 stdin 发送请求：`{"type": "pool_status"}`
- **AND** Java 应返回连接池状态：`{"type": "pool_status", "active": 5, "idle": 3, ...}`

### Requirement: 守护进程超时控制

系统 SHALL 为每个操作设置超时时间，防止无限等待，并区分 I/O 超时和查询超时。

#### Scenario: I/O 读取超时
- **WHEN** 从 Java 守护进程 stdout 读取数据
- **AND** 在 `io_timeout`（默认 30 秒）内未收到完整行
- **THEN** 系统应终止读取操作
- **AND** 检查 Java 进程健康状态
- **AND** 如不健康，重启进程并重试查询一次

#### Scenario: 查询执行超时
- **WHEN** Java 端查询执行时间超过 `query_timeout`（默认 120 秒）
- **THEN** Java 端应取消查询
- **AND** 返回错误响应：`{"error": true, "message": "Query timeout"}`
- **AND** Python 端应根据重试策略决定是否重试

#### Scenario: 启动超时
- **WHEN** Java 守护进程启动超过 `startup_timeout`（默认 10 秒）未就绪
- **THEN** 系统应放弃启动
- **AND** 抛出 `JavaBridgeError` 异常
- **AND** 记录详细的诊断信息（Java 版本、classpath、环境变量）

### Requirement: 守护进程异常处理

系统 SHALL 捕获并转换 Java 异常为 Python 异常，并支持自动恢复。

#### Scenario: Java 异常转换
- **WHEN** Java 代码抛出异常
- **THEN** 系统应捕获异常并转换为对应的 Python 异常类型
- **AND** 保留原始异常信息和堆栈跟踪

#### Scenario: 进程崩溃处理
- **WHEN** Java 守护进程意外崩溃
- **THEN** 系统应检测到进程退出（`poll()` 返回非 None）
- **AND** 自动重启守护进程
- **AND** 记录崩溃事件到日志（ERROR 级别）

#### Scenario: 自动恢复成功
- **WHEN** 系统检测到 Java 进程不健康并成功重启
- **THEN** 应重试当前查询一次
- **AND** 如重试成功，返回查询结果
- **AND** 记录恢复成功事件到日志（INFO 级别）

#### Scenario: 自动恢复失败
- **WHEN** 系统尝试重启 Java 进程失败
- **THEN** 应抛出 `JavaBridgeError` 异常
- **AND** 异常消息应包含 "Failed to recover Java bridge process"
- **AND** 记录失败详情到日志（ERROR 级别）

### Requirement: 守护进程健康检查

系统 SHALL 综合使用进程存活检查和心跳检测来判断 Java 守护进程健康状态。

#### Scenario: 进程存活检查
- **WHEN** 执行数据库操作前
- **THEN** 系统应使用 `poll()` 检查 Java 进程是否仍在运行
- **AND** 如果进程已退出，应自动重启

#### Scenario: 心跳健康检查
- **WHEN** 调用 `is_healthy()` 方法
- **THEN** 系统应检查当前时间与 `last_heartbeat` 的时间差
- **AND** 如果时间差超过 `health_check_interval * 2`，返回 `False`
- **AND** 如果进程退出或心跳缺失，应触发自动恢复流程

#### Scenario: 获取健康状态详情
- **WHEN** 调用 `get_health_status()` 方法
- **THEN** 应返回包含以下信息的字典：
  - `is_healthy`: 布尔值
  - `process_alive`: 布尔值
  - `last_heartbeat`: 时间戳
  - `uptime`: 数字
  - `restart_count`: 数字

### Requirement: 防止连续重启

系统 SHALL 限制连续重启次数，防止无限重启循环。

#### Scenario: 记录重启历史
- **WHEN** Java 守护进程重启
- **THEN** 系统应记录重启时间戳
- **AND** 维护最近 5 分钟内的重启次数

#### Scenario: 达到重启限制
- **WHEN** 5 分钟内重启次数达到 3 次
- **THEN** 系统应停止自动重启
- **AND** 抛出 `JavaBridgeError` 异常
- **AND** 错误消息应包含 "too many restarts in 5 minutes"

#### Scenario: 重置重启计数
- **WHEN** Java 守护进程稳定运行超过 5 分钟
- **THEN** 系统应重置重启计数器
