## Context

目前 `dm_query`、`README` 和 `core.validators.validate_sql_query` 形成了一套路由：只要语句以 `SELECT` 开头就走查询，否则就被认为是更新/写操作并被拒绝。Java 桥接是同样的分发方式，因此 `EXPLAIN`/`EXPLAIN PLAN` 这类只读执行计划语句在 MCP 工具中无法访问，尽管它们不会写数据。为了在不放开 DML/DDL 的前提下支持这些诊断语句，需要先确定统一的语句分类、安全白名单和桥接层处理契约。

在集成验证中还暴露了三个关键兼容性问题（需要在规格/设计中显式约束）：

- **SQL 方言差异**：目标环境对 `EXPLAIN PLAN FOR ...` 不兼容，语法更接近 `EXPLAIN PLAN <stmt>`（不包含 `FOR`）。
- **JDBC 执行路径差异**：`EXPLAIN SELECT ...` 在目标 DM/JDBC 版本下不能简单复用 `PreparedStatement.executeQuery()`，会报“执行未准备SQL语句”，需要改为更通用的 `Statement/PreparedStatement.execute()` 并根据是否产生 ResultSet 决定读取方式。
- **跨层返回值契约漂移**：`DmClient.execute_query()` 与 `tools/query.py` 对结果结构的假设不一致，导致成功查询在工具包装阶段因把 `list` 当成 `dict` 而崩溃（`'list' object has no attribute 'get'`）。必须定义并落实统一的返回契约。
- **Session 不一致导致计划不可见**：执行计划常依赖会话级对象（例如 `PLAN_TABLE` 可能为会话可见或按会话写入/隔离）。如果用户在一次 MCP 调用中生成计划、在下一次 MCP 调用中查询 `PLAN_TABLE`，则很可能因为连接池/新连接导致 session 不同而读不到计划数据（表现为 `PLAN_TABLE` 为空）。

## Goals / Non-Goals

**Goals:**
- Allow MCP to execute read-only diagnostic statements such as `EXPLAIN ...` and `EXPLAIN PLAN ...`（可选兼容 `EXPLAIN PLAN FOR ...`）without requiring schema changes or introducing write operations.
- Share a deterministic statement classifier across validators, `dm_query`, and the Java bridge so that allowed statements and their expected response shapes are consistent.
- Enumerate the expected metadata (`query_type`, `statement_type`) and error handling so callers and tooling builders know whether a statement produced a result set or only a plan description.
- Document the architecture and boundaries so future engineers can extend to other read-only diagnostics safely.
- Provide a stable, single-call “get plan” API that does not require callers to query `PLAN_TABLE` in a subsequent request (no cross-call session coupling).

**Non-Goals:**
- Opening the door to arbitrary DML/DDL/privilege statements or multi-statement batches.
- Replacing the existing Java bridge architecture; we only adjust routing and metadata around the current stdin/stdout contract.

## Decisions

- **Statement classification shared via validator**: Extend `validate_sql_query` to return `(sql, statement_type)` and recognize `EXPLAIN PLAN ...`（可选兼容 `EXPLAIN PLAN FOR ...`）为 `EXPLAIN_PLAN`，且该判断必须优先于通用 `EXPLAIN` 前缀匹配，避免误分类。
- **Dialect compatibility for EXPLAIN PLAN**: Treat `EXPLAIN PLAN ...` and `EXPLAIN PLAN FOR ...` as the same `statement_type = EXPLAIN_PLAN` in the validator. Execution layer SHOULD be allowed to normalize/rewrite the SQL to the DB-accepted dialect (e.g., prefer `EXPLAIN PLAN <stmt>` when `FOR` is rejected) while keeping a clear error if neither dialect is supported.
- **Metadata for diagnostics**: `dm_query` 响应的 `metadata` SHALL 包含 `statement_type` / `query_type` 字段（不依赖调用方猜测语句类型），并在 `EXPLAIN_PLAN` 场景附带 `plan_table_row_count`（如果可得）。
- **Java bridge routing by statement type**: Java 桥接按 `statement_type` 选择执行策略，但诊断语句不再假设可走 `executeQuery()`：统一以 `execute()` 为入口，并用 `getResultSet()` 判断是否存在结果集；`EXPLAIN_PLAN` 还需要在触发计划生成后查询 `PLAN_TABLE` 返回计划摘要（并确保不会混入历史/其他会话的计划行）。
- **Cross-layer result contract**: 明确并统一跨层返回值：`DmClient.execute_query()` 在所有语句类型下都返回同一种数据形态（推荐 `List[Dict[str, Any]]`），`dm_query` 仅负责包装与元数据生成；禁止出现“同一接口在不同语句类型下返回 list 或 dict 混用”的契约漂移。
- **Add a dedicated plan tool**: 新增专用工具（建议命名 `dm_explain_plan(select_sql)`），只接受 `SELECT ...`（不含 `EXPLAIN` 前缀），工具内部在同一 JDBC 连接/同一 session 内完成“计划生成 + 计划读取/返回”。该工具用于替代“先 EXPLAIN 再查 PLAN_TABLE”的双调用模式，避免 session 不一致导致的空结果。
- **Safe-listing diagnostics**: Continue rejecting dangerous keywords (DDL/DML) even if the statement begins with `EXPLAIN`, unless the classifier explicitly recognizes the pattern as a supported diagnostic. This preserves security while allowing the limited new statements.
- **Documentation and tests**: Add README updates and validator tests to capture the new statement patterns and ensure existing multi-statement or destructive SQL remain blocked.

## Risks / Trade-offs

- **[Risk] Misclassifying statements (false positives)** → Keep the classifier conservative (only allow explicit `EXPLAIN`/`EXPLAIN PLAN` patterns) and add regression tests. The mitigation is to reject anything ambiguous and ask users to wrap their request differently.
- **[Risk] Bridge behavior drift (JDBC path assumptions)** → 对 `EXPLAIN`/`EXPLAIN_PLAN` 明确采用 `execute()` + `getResultSet()` 的通用模式，并添加回归用例覆盖“无 ResultSet 的诊断语句”分支，避免再次回退到错误的 `executeQuery()` 假设。
- **[Risk] PLAN_TABLE 污染/串读** → `EXPLAIN_PLAN` 读取计划表必须可定位到当前语句生成的计划（例如通过受控 `STATEMENT_ID` 标记或会话隔离字段），否则会读到历史计划或其他会话计划，造成信息泄露/误导。
- **[Risk] Monitoring/caching expecting row counts** → 统一结果形态与 `row_count` 计算规则（对 list 取 `len()`），并通过 `metadata.statement_type` 让下游按语句类型解释行数语义。

## Migration Plan

1. First fix the cross-layer result contract (eliminate list/dict mismatch) so successful queries cannot crash in the tool wrapper.
2. Update the classifier to recognize `EXPLAIN PLAN` (w/ optional `FOR`) and adjust documentation/examples accordingly.
3. Update Java bridge execution for diagnostics to use `execute()` + `getResultSet()` (avoid `executeQuery()` assumptions), and implement deterministic `PLAN_TABLE` read strategy.
4. Deploy with regression coverage ensuring DML/DDL remain rejected and diagnostic statements behave consistently.
5. If rollback is required, revert validator allow-list changes first so diagnostics are blocked again while leaving bridge code untouched.

## Open Questions

- Should we expose the `statement_type` in MCP logs and metrics as well as the response metadata?
- Do we need to support additional read-only diagnostics (`DESCRIBE`, `SHOW PLAN`) later, and if so when does that become a separate capability?
