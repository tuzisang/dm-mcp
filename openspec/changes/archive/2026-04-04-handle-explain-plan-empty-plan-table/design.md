## Context

当前 `dm_explain_plan` 的 Python 工具层接收裸 `SELECT`，随后拼接成 `EXPLAIN SELECT ...` 并交给 `DmClient.execute_explain_plan()`。但 Java 桥接在 `statement_type = EXPLAIN_PLAN` 时走的是“执行语句后读取 `PLAN_TABLE`”分支，这要求前置 SQL 必须是能向计划表写入计划的形态。结果是：工具层与桥接层的语义不一致，某些达梦环境中语句能成功执行，却不会向 `PLAN_TABLE` 写数据，最终表现为无报错但计划为空。

这次变更不是要重做所有诊断语句路由，而是要收紧 `dm_explain_plan` 与 `EXPLAIN_PLAN` 的契约，让“计划来源”与“执行语句形态”保持一致，并把“未产出计划”从静默空结果升级为明确的兼容性错误。

## Goals / Non-Goals

**Goals:**
- 让 `dm_explain_plan` 生成与桥接 `EXPLAIN_PLAN` 路径一致的 SQL 形态。
- 让 `EXPLAIN_PLAN` 路径在 `PLAN_TABLE` 为空时返回明确错误，而不是成功空结果。
- 保持 `dm_query("EXPLAIN SELECT ...")` 的现有语义不变，继续作为“直接 ResultSet”诊断路径。
- 增加覆盖该回归的单元测试，防止未来再次出现“普通 EXPLAIN + PLAN_TABLE 读取”的错配。

**Non-Goals:**
- 不在本次变更中引入新的数据库依赖或系统存储过程探测逻辑。
- 不改变通用 `SELECT` / DML 安全校验行为。
- 不尝试为所有 DM/JDBC 版本实现完整的多路径自动探测框架；本次优先修正当前明确失配的路径。

## Decisions

### 决策 1：`dm_explain_plan` 统一生成 `EXPLAIN PLAN` SQL

`dm_explain_plan` 是专用“生成并读取计划表”的工具，因此它输出给客户端的 SQL 必须匹配桥接 `EXPLAIN_PLAN` 分支的预期。实现上将把当前 `EXPLAIN {select}` 改为 `EXPLAIN PLAN {select}`。

备选方案：
- 保持 `EXPLAIN SELECT`，只在 Java 侧做隐式改写。
  - 未采纳原因：工具层继续暴露错误语义，且 `sql` 返回值会与真实执行语句不一致。

### 决策 2：桥接层把“0 条计划行”视为兼容性错误

对于 `statement_type = EXPLAIN_PLAN`，Java 桥接当前会把空结果也序列化成成功响应。这会让上层工具把“目标库没有产出计划”误判成“执行计划为空”。实现上将统一在桥接计划读取后检查行数，若为 0，则抛出兼容性错误。

备选方案：
- 仅在 Python 工具层检查 `rows=[]`。
  - 未采纳原因：`dm_query("EXPLAIN PLAN ...")` 与 `dm_explain_plan()` 会产生分叉语义，错误边界仍留在下游。

### 决策 3：保留 `dm_query("EXPLAIN SELECT ...")` 作为独立诊断路径

标准 `EXPLAIN` 与 `EXPLAIN_PLAN` 在现有规范里已经是两条不同的执行路径。本次只修复 `EXPLAIN_PLAN` 契约，不改变 `dm_query("EXPLAIN SELECT ...")` 的直返 ResultSet 语义。

备选方案：
- 将所有 `EXPLAIN` 自动改写成 `EXPLAIN PLAN`。
  - 未采纳原因：这会改变已有 API 语义，也会掩盖目标环境是否支持直接 `EXPLAIN` 结果集。

## Risks / Trade-offs

- [风险] 某些环境下 `EXPLAIN PLAN` 语法本身需要额外兼容变体。 → 缓解：沿用现有 `EXPLAIN PLAN FOR` 规范化逻辑，并把兼容性错误暴露清楚。
- [风险] 把空计划改为错误后，依赖“空数组也算成功”的调用方可能需要适配。 → 缓解：该行为本质上是错误成功化，优先保证诊断结果可信。
- [风险] 当前单元测试主要覆盖 Python 工具层，对 Java 侧真实 JDBC 行为覆盖有限。 → 缓解：补充工具层和客户端契约测试，并在实现后编译桥接类做静态校验。

## Migration Plan

1. 更新 OpenSpec delta specs 与 tasks，锁定行为变更。
2. 修改 `tools/explain_plan.py`，让专用工具生成 `EXPLAIN PLAN` SQL。
3. 修改 `db/DmJdbcBridge.java`，在 `EXPLAIN_PLAN` 路径对空计划结果抛出兼容性错误。
4. 如有必要，调整 `db/client.py` 的错误透传文案。
5. 补充并运行回归测试，确认 `dm_explain_plan` 与 `dm_query("EXPLAIN PLAN ...")` 的行为一致。

## Open Questions

- 当前不引入新的计划来源探测字段（例如 `plan_source`）。如果后续需要更细粒度的观测信息，可在下一轮 change 中补充。
