## MODIFIED Requirements

### Requirement: 守护进程通信协议

系统 SHALL 使用标准输入/输出与 Java 守护进程进行 JSON 格式通信，并允许 MCP 进程在多次工具调用之间复用同一守护进程。

#### Scenario: 发送 SQL 请求
- **WHEN** Python 需要执行数据库操作
- **THEN** 应通过 stdin 发送 JSON 格式的 SQL 请求
- **AND** 请求应包含 SQL 语句、参数以及分类出的 `statement_type`
- **AND** 请求格式应为：`{"sql": "...", "params": ["...", "..."], "statement_type": "SELECT"}`（诊断语句可将 `statement_type` 设置为 `EXPLAIN` 或 `EXPLAIN_PLAN`）

#### Scenario: 接收查询结果
- **WHEN** Java 完成带 ResultSet 的查询执行（含标准 `SELECT` 或返回计划行的诊断语句）
- **THEN** 应通过 stdout 返回 JSON 格式的查询结果
- **AND** 结果应至少包含：`success`、`columns`、`columnTypes`（如可得）、`rows`
- **AND** Java 输出不要求包含 MCP 工具层的 `metadata`（该元数据由 Python 工具层统一生成）

#### Scenario: 接收错误信息
- **WHEN** Java 执行过程中发生异常
- **THEN** 应通过 stdout 返回 JSON 格式的错误响应
- **AND** 错误格式应为：`{"error": true, "message": "..."}`
- **AND** stderr 应仅用于 Java 启动阶段的致命错误

#### Scenario: 接收关闭请求
- **WHEN** Python 端发送 `{"type": "shutdown"}`
- **THEN** Java 端应停止读取新请求并关闭当前资源
- **AND** 进程应在当前关闭流程结束后退出

#### Scenario: 跨调用复用守护进程
- **WHEN** MCP 进程在短时间内连续发起多个数据库工具调用
- **THEN** Python 端可以复用同一个 Java 守护进程处理这些请求
- **AND** Java 端不应为每个请求强制重建连接池

### Requirement: 守护进程超时控制

系统 SHALL 为启动和单次请求响应设置有界超时，但 MUST 让超时直接结束当前调用，而不是引入额外恢复状态机。

#### Scenario: 启动超时
- **WHEN** Java 守护进程启动超过 `startup_timeout`（默认 10 秒）未就绪
- **THEN** 系统应放弃启动
- **AND** 抛出 `JavaBridgeError` 异常

#### Scenario: 响应读取超时
- **WHEN** Python 端在单次请求的响应窗口内未收到完整 JSON 响应
- **THEN** 系统应中止当前读取
- **AND** 以超时错误结束当前调用
- **AND** 不得在当前调用内部触发自动重启或隐式重试

#### Scenario: 查询执行超时
- **WHEN** Java 端查询执行时间超过配置的查询超时时间
- **THEN** Java 端应取消查询并返回错误响应
- **AND** Python 端应将该错误直接返回给当前调用方

### Requirement: 守护进程异常处理

系统 SHALL 将 Java 执行异常转换为确定性的 Python 错误，但 MUST 避免在桥接层引入心跳、池状态查询和后台状态追踪。

#### Scenario: Java 异常转换
- **WHEN** Java 代码抛出异常
- **THEN** 系统应捕获异常并转换为对应的 Python 异常类型
- **AND** 保留原始异常信息以便定位问题

#### Scenario: 进程异常退出
- **WHEN** Java 守护进程在当前调用期间意外退出
- **THEN** 系统应检测到进程退出
- **AND** 将该次调用标记为失败
- **AND** 不得在同一次调用内隐式重放当前请求

## REMOVED Requirements

### Requirement: 守护进程健康检查
**Reason**: 守护进程健康语义收敛到专门的 `health-check` 能力，不再在本能力内重复定义。
**Migration**: 请求前活性判断与共享运行时重建改由 `health-check` 规范约束。

### Requirement: 防止连续重启
**Reason**: 自动重启流程已被移除，连续重启计数和窗口控制不再属于当前阶段的必要能力。
**Migration**: 无；问题通过明确失败和下一次新建进程来处理。
