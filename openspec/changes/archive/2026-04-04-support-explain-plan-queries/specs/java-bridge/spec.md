## MODIFIED Requirements

### Requirement: 守护进程通信协议

系统 SHALL 使用标准输入/输出与 Java 守护进程进行 JSON 格式通信，支持多种消息类型，并在 SQL 请求中携带由 Python 端共享的 `statement_type`（例如 `SELECT`、`EXPLAIN`、`EXPLAIN_PLAN`）以指导执行路径。

#### Scenario: 发送 SQL 请求
- **WHEN** Python 需要执行数据库操作
- **THEN** 应通过 stdin 发送 JSON 格式的 SQL 请求
- **AND** 请求应包含 SQL 语句、参数以及分类出的 statement_type
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

#### Scenario: 诊断语句路由
- **WHEN** 收到 `statement_type` 为 `EXPLAIN`/`EXPLAIN_PLAN`
- **THEN** Java 应根据该类型选择执行策略，但不得假设诊断语句总能用 `executeQuery()` 返回 ResultSet
- **AND** 对于 `EXPLAIN`，Java SHOULD 使用 `execute()` 并在存在 ResultSet 时返回计划行；若无 ResultSet，应返回清晰错误（由 Python 工具层进一步映射为可操作的提示）
- **AND** 对于 `EXPLAIN_PLAN`，Java SHOULD 先执行 `EXPLAIN PLAN ...` 触发计划生成，再查询 `PLAN_TABLE` 返回本次语句对应的计划摘要，并在可得时附带 `plan_table_row_count`
