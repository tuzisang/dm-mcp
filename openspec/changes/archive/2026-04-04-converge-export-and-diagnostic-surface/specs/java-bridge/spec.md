## MODIFIED Requirements

### Requirement: 守护进程通信协议

系统 SHALL 使用标准输入/输出与 Java 守护进程进行 JSON 格式通信，并将协议收敛到最小只读请求响应闭环。

#### Scenario: 发送 SQL 请求
- **WHEN** Python 需要执行数据库操作
- **THEN** 应通过 stdin 发送 JSON 格式的 SQL 请求
- **AND** 请求只包含 SQL 语句和分类出的 `statement_type`
- **AND** 请求格式应为：`{"sql": "...", "statement_type": "SELECT"}`（诊断语句可将 `statement_type` 设置为 `EXPLAIN` 或 `EXPLAIN_PLAN`）

#### Scenario: 接收查询结果
- **WHEN** Java 完成带 ResultSet 的查询执行（含标准 `SELECT` 或返回计划行的 `EXPLAIN`）
- **THEN** 应通过 stdout 返回 JSON 格式的查询结果
- **AND** 结果应至少包含：`success`、`columns`、`columnTypes`（如可得）、`rows`
- **AND** Java 输出不要求包含 MCP 工具层的 `metadata`（该元数据由 Python 工具层统一生成）

#### Scenario: 接收错误信息
- **WHEN** Java 执行过程中发生异常
- **THEN** 应通过 stdout 返回 JSON 格式的错误响应
- **AND** 错误格式应为：`{"error": true, "message": "..."}`
- **AND** stderr 应仅用于 Java 启动阶段的致命错误

#### Scenario: 守护进程就绪
- **WHEN** Java 守护进程启动完成
- **THEN** 应通过 stdout 输出唯一的就绪消息
- **AND** 就绪消息格式应为：`{"status": "ready", "message": "..."}`

#### Scenario: 显式关闭守护进程
- **WHEN** Python 端发送 `{"type": "shutdown"}`
- **THEN** Java 端应退出主循环
- **AND** 返回 `{"status": "shutting_down"}` 或等价确认响应

#### Scenario: `EXPLAIN` 从驱动直接提取计划文本
- **WHEN** 收到 `statement_type = EXPLAIN`
- **THEN** Java 必须使用 `Statement.execute()`
- **AND** 若存在 `ResultSet`，Java 直接读取并返回结果集
- **AND** 若不存在 `ResultSet`，Java 必须尝试从达梦 JDBC 驱动公开的直接计划接口读取计划文本
- **AND** 若读取到计划文本，Java 必须将其转换为标准 `columns/rows` 结构返回

#### Scenario: `EXPLAIN` 未返回任何可读计划
- **WHEN** 收到 `statement_type = EXPLAIN`
- **AND** JDBC 既未返回 `ResultSet`，也未返回可读取的直接计划文本
- **THEN** Java 必须返回清晰的诊断错误
- **AND** Java 不得返回 `success = true` 且 `rows = []`

#### Scenario: `EXPLAIN_PLAN` 使用计划表能力探测
- **WHEN** 收到 `statement_type = EXPLAIN_PLAN`
- **THEN** Java 应先探测 `PLAN_TABLE` 的实际列结构，再选择执行计划隔离、读取和清理策略
- **AND** Java 不得硬编码假设 `PLAN_TABLE.STATEMENT_ID` 一定存在

#### Scenario: `EXPLAIN_PLAN` 使用 `STATEMENT_ID` 隔离
- **WHEN** `PLAN_TABLE` 包含 `STATEMENT_ID`
- **THEN** Java 应优先使用 `STATEMENT_ID` 或等价机制隔离本次语句生成的计划数据
- **AND** 读取和清理操作仅针对本次语句对应的数据

#### Scenario: `EXPLAIN_PLAN` 回退到同 session 清理路径
- **WHEN** `PLAN_TABLE` 不包含 `STATEMENT_ID`
- **AND** Java 能在当前连接中成功清理并验证当前 session 可见计划行为 0
- **THEN** Java 应改用"预清理 -> 生成计划 -> 读取 -> 清理"的兼容路径
- **AND** 返回结果仍应包含标准查询结果字段以及可得的 `plan_table_row_count`

#### Scenario: `EXPLAIN_PLAN` 未产出可读取计划
- **WHEN** `statement_type = EXPLAIN_PLAN` 的诊断语句已成功执行
- **AND** Java 在预期的计划来源中没有读取到任何本次语句的计划行
- **THEN** Java 应返回明确的兼容性错误，说明目标环境未产出可读取的执行计划
- **AND** Python 工具层接收到的错误信息不得只是裸露的空结果或底层 SQL 细节

### Requirement: 守护进程超时控制

系统 SHALL 为启动、读取和查询执行设置有界超时，但不再包含自动恢复和重试路径。

#### Scenario: I/O 读取超时
- **WHEN** 从 Java 守护进程 stdout 读取数据
- **AND** 在固定 I/O 超时内未收到完整响应
- **THEN** 系统应终止当前读取
- **AND** 返回明确的桥接超时错误

#### Scenario: 查询执行超时
- **WHEN** Java 端查询执行时间超过 `query_timeout`
- **THEN** Java 端应取消查询
- **AND** 返回错误响应：`{"error": true, "message": "Query timeout"}`

#### Scenario: 启动超时
- **WHEN** Java 守护进程启动超过 `startup_timeout` 未就绪
- **THEN** 系统应放弃启动
- **AND** 抛出 `JavaBridgeError` 异常

## REMOVED Requirements

### Requirement: 守护进程异常处理
**Reason**: 当前最小闭环不再提供自动重启、自动恢复和进程崩溃后重试。
**Migration**: 通过共享运行时重建路径显式关闭并重建守护进程，而不是依赖桥接内部自动恢复。

### Requirement: 守护进程健康检查
**Reason**: 心跳与健康详情查询已被移除，当前只保留最小活性判断和显式失败。
**Migration**: 使用请求前的进程存活检查与失败后的显式重建替代健康检查接口。

### Requirement: 防止连续重启
**Reason**: 自动重启能力已移除，连续重启限制不再有消费方。
**Migration**: 无；当前设计不再提供内部自动重启流程。
