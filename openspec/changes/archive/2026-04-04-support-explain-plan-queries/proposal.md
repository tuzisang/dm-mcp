## Why

当前 `dm_query` 在工具说明、README 和现有规格中都被限定为“仅支持 SELECT”，但数据库诊断和 SQL 调优经常需要执行 `EXPLAIN`、`EXPLAIN PLAN` 等执行计划语句。现有实现还把 Java 桥接层的语句分发写死为“`SELECT` 走查询，其余走更新”，导致这类只读诊断语句无法稳定执行或返回预期结果。

此外，Python 校验层、Java 桥接层和文档对“哪些 SQL 被允许”并不一致。为了在不放开写操作的前提下支持执行计划语句，需要先用 OpenSpec 明确允许范围、分类规则和响应约定。

## 实施反馈（当前报错根因）

按本提案思路实现后，`dm_query` 在真实环境中仍出现以下报错，暴露出“SQL 形态兼容 + JDBC 执行路径 + 跨层返回值契约”三类问题：

1) `EXPLAIN SELECT ...` → `执行未准备SQL语句`  
   说明对 `EXPLAIN` 语句不能简单复用 `PreparedStatement.executeQuery()` 的路径（至少在目标 DM/JDBC 版本中不兼容）。提案需要把“诊断语句的 JDBC 执行方式”明确为：优先 `Statement.execute()` 并根据 `getResultSet()`/`getUpdateCount()` 判定返回形态，而不是假设一定能走 `executeQuery()`。

2) `EXPLAIN PLAN FOR SELECT ...` → `FOR` 附近语法错误  
   说明目标环境的语法更接近 `EXPLAIN PLAN <stmt>`（不包含 `FOR`）。提案需要把允许/分类规则从写死的 `EXPLAIN PLAN FOR` 调整为支持 `EXPLAIN PLAN`（必要时兼容可选 `FOR`），并同步更新文档示例。

3) 任意成功 `SELECT ...`（如 `SELECT * FROM PLAN_TABLE ...`）→ `'list' object has no attribute 'get'`  
   说明 `tools/query.py` 对底层返回值结构的假设与 `DmClient.execute_query()` 的实际返回不一致，导致“SQL 执行成功但在工具包装阶段崩溃”。提案需要补齐并统一跨层契约：要么 `dm_query` 直接返回 Java 桥接的 `{columns, columnTypes, rows}` 结构，要么工具层对“行字典列表”按 `len(result)` 计算行数，并在 `EXPLAIN_PLAN` 场景单独携带 `plan_table_row_count`。

4) `EXPLAIN ...` 已可执行，但随后查询 `PLAN_TABLE` 始终为空（0 rows）  
   说明不能依赖“跨 MCP 调用共享同一数据库 session”来读取执行计划：单次工具调用通常会获取新的 JDBC 连接（新的 session），导致“计划写入 session A、读取发生在 session B”。即使数据库确实把计划写入 `PLAN_TABLE`，也可能只在生成该计划的 session 可见。提案需要把“生成 + 读取计划”收敛到一次 MCP 调用内完成，避免把 `PLAN_TABLE` 当作跨调用的中转层。

## What Changes

- 将 `dm_query(sql)` 的支持范围从“仅支持 SELECT”扩展为“只读结果集查询 + 受控执行计划语句”，覆盖 `EXPLAIN ...` 与 `EXPLAIN PLAN ...`（以 DM 兼容形态为准，不强依赖 `FOR`）。
- 为查询工具增加统一的 SQL 语句分类规则（校验层与桥接层共享），并将 `EXPLAIN PLAN`（可选兼容 `EXPLAIN PLAN FOR`）识别为 `EXPLAIN_PLAN`。
- 调整 Java 桥接执行约定：诊断语句不再假设可走 `PreparedStatement.executeQuery()`；统一以 `Statement.execute()` 作为入口，并根据是否产生 ResultSet 来决定“直接返回 rows”或“查询 PLAN_TABLE 返回摘要”。
- 明确并统一 `dm_query` 的数据返回契约与元数据：稳定标识语句类型（`SELECT`/`EXPLAIN`/`EXPLAIN_PLAN`），并保证成功查询不会因返回结构差异在工具层崩溃；对计划类语句补充 `plan_table_row_count`。
- 新增一个专用工具（例如 `dm_explain_plan(select_sql)`），用于“单次调用”获取 `SELECT` 的执行计划：工具内部在同一 session 内完成计划生成与读取/返回，不要求用户再手动查询 `PLAN_TABLE`，从而规避跨调用 session 不一致导致的空结果问题。
- 同步更新 MCP 工具文档、README 和测试用例，明确允许的诊断语句边界，并继续拒绝 DDL、DML、授权、会话破坏类语句和多语句注入。

## Capabilities

### New Capabilities
- `diagnostic-query`: 定义只读诊断 SQL 的允许范围、分类规则和响应约定，覆盖 `EXPLAIN` / 执行计划语句，并新增专用工具（例如 `dm_explain_plan(select_sql)`）用于单次调用获取执行计划，避免跨调用依赖 `PLAN_TABLE` 与 session 一致性。

### Modified Capabilities
- `database-client`: 查询执行 requirement 从“支持 SELECT 查询”扩展为“支持结果集查询和受控执行计划语句”，并要求返回一致的语句类型元数据与错误反馈。
- `java-bridge`: SQL 请求分发 requirement 从仅按 `SELECT` 前缀判断，调整为按语句类别和是否返回结果集决定执行路径，以兼容执行计划语句。

## Impact

- 受影响的代码模块：
  - `core/validators.py`
  - `db/sql_security.py`
  - `tools/query.py`
  - `tools`（新增 `dm_explain_plan` 工具实现与注册）
  - `db/client.py`
  - `db/java_bridge.py`
  - `db/DmJdbcBridge.java`
  - `README.md`
  - `tests/test_validators.py`
  - 与查询安全、桥接执行相关的回归测试
- API / 工具行为变更：
  - `dm_query(sql)` 的文档与校验逻辑将不再表述为“仅支持 SELECT”
  - 返回元数据中的 `query_type` 需要覆盖执行计划语句类别
  - 继续保持“仅允许只读/诊断型 SQL”的安全边界，不引入通用写操作能力
- 依赖与系统影响：
  - 无新增外部依赖
  - 需要补充针对执行计划语句路由、返回格式和拦截规则的自动化测试
