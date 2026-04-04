## MODIFIED Requirements

### Requirement: 守护进程通信协议
系统 SHALL 使用标准输入/输出与 Java 守护进程进行 JSON 格式通信，支持多种消息类型，并在 SQL 请求中携带由 Python 端共享的 `statement_type`（例如 `SELECT`、`EXPLAIN`、`EXPLAIN_PLAN`）以指导执行路径。

#### Scenario: 发送 SQL 请求
- **WHEN** Python 需要执行数据库操作
- **THEN** 应通过 stdin 发送 JSON 格式的 SQL 请求
- **AND** 请求应包含 SQL 语句、参数以及分类出的 `statement_type`
- **AND** 请求格式应为：`{"sql": "...", "params": ["...", "..."], "statement_type": "SELECT"}`（诊断语句可将 `statement_type` 设置为 `EXPLAIN` 或 `EXPLAIN_PLAN`）

#### Scenario: 接收查询结果
- **WHEN** Java 完成带 ResultSet 的查询执行（含标准 `SELECT` 或返回计划行的 `EXPLAIN`）
- **THEN** 应通过 stdout 返回 JSON 格式的查询结果
- **AND** 结果应至少包含：`success`、`columns`、`columnTypes`（如可得）、`rows`
- **AND** Java 输出不要求包含 MCP 工具层的 `metadata`（该元数据由 Python 工具层统一生成）

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
- **AND** Java 应返回连接池状态（字段名可为实现约定），例如：`{"success": true, "active_connections": 5, "idle_connections": 3, ...}`

#### Scenario: `EXPLAIN_PLAN` 使用与计划来源一致的 SQL 形态
- **WHEN** 收到 `statement_type = EXPLAIN_PLAN`
- **THEN** Java 应确保传入 SQL 与预期的计划来源一致
- **AND** 若后续路径依赖读取 `PLAN_TABLE`，Java MUST 使用能触发计划表写入的 `EXPLAIN PLAN` 兼容形态，而不是执行普通 `EXPLAIN` 后再读取 `PLAN_TABLE`

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
- **THEN** Java 应改用“预清理 -> 生成计划 -> 读取 -> 清理”的兼容路径
- **AND** 返回结果仍应包含标准查询结果字段以及可得的 `plan_table_row_count`

#### Scenario: `EXPLAIN_PLAN` 未产出可读取计划
- **WHEN** `statement_type = EXPLAIN_PLAN` 的诊断语句已成功执行
- **AND** Java 在预期的计划来源中没有读取到任何本次语句的计划行
- **THEN** Java 应返回明确的兼容性错误，说明目标环境未产出可读取的执行计划
- **AND** Python 工具层接收到的错误信息不得只是裸露的空结果或底层 SQL 细节

#### Scenario: 诊断语句路由
- **WHEN** 收到 `statement_type` 为 `EXPLAIN` 或 `EXPLAIN_PLAN`
- **THEN** Java 应根据该类型选择执行策略，但不得假设诊断语句总能用 `executeQuery()` 返回 ResultSet
- **AND** 对于 `EXPLAIN`，Java MUST 使用 `execute()` 并在存在 ResultSet 时返回计划行；若无 ResultSet，应返回清晰错误
- **AND** 对于 `EXPLAIN_PLAN`，Java MUST 在同一连接内完成计划生成与计划读取，并遵循前述能力探测和兼容路径
