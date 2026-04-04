## Why

`dm_explain_plan` 在真实达梦环境中失败，根因不是连接、权限或 SQL 安全校验，而是当前实现把 `PLAN_TABLE.STATEMENT_ID` 当成必备列来做计划隔离和清理。目标数据库的 `PLAN_TABLE` 不包含该列，导致 `dm_explain_plan` 在执行计划生成后、读取计划表时直接报错，现有“单次调用获取执行计划”的能力因此在部分 DM 版本上不可用。

现有 OpenSpec 已要求在同一 session 内完成计划生成与读取，但没有明确约束“计划表结构在不同 DM 版本间可能不同”。需要补一条兼容性提案，把执行计划读取从“硬编码依赖某列”收敛为“按目标库实际 PLAN_TABLE 结构选择可用策略”，并在无法安全兼容时返回明确错误。

## What Changes

- 修订 `dm_explain_plan` / `EXPLAIN_PLAN` 的兼容性要求：实现不得假设 `PLAN_TABLE` 一定存在 `STATEMENT_ID`，必须支持目标库缺少该列的场景。
- 为 Java 桥接补充计划表能力探测与回退策略，例如先读取 `PLAN_TABLE` 元数据，再决定是否使用 `STATEMENT_ID`、其他可用隔离字段，或退化为“同 session 内受控清理 + 本次结果读取”的兼容路径。
- 明确 `dm_explain_plan` 的失败语义：当目标库的计划表结构不足以安全隔离本次计划时，工具必须返回清晰的兼容性错误，而不是暴露底层“列不存在”异常。
- 补充文档与回归测试，覆盖“`PLAN_TABLE` 有 `STATEMENT_ID`”和“`PLAN_TABLE` 无 `STATEMENT_ID`”两类达梦环境，确保 `dm_explain_plan` 在已支持环境中稳定工作。

## Capabilities

### New Capabilities
<!-- None -->

### Modified Capabilities
- `diagnostic-query`: 调整 `dm_explain_plan` / `EXPLAIN_PLAN` 的行为要求，使其基于目标库实际 `PLAN_TABLE` 结构获取执行计划，而不是硬编码依赖 `STATEMENT_ID`。
- `java-bridge`: 调整执行计划读取与清理约定，要求桥接层先探测计划表能力，再选择兼容的隔离、查询和清理策略，并输出明确的兼容性错误。

## Impact

- 受影响代码：
  - `db/DmJdbcBridge.java`
  - `db/java_bridge.py`
  - `db/client.py`
  - `tools/explain_plan.py`
  - 与执行计划相关的测试与 README / 工具文档
- 受影响行为：
  - `dm_explain_plan(select_sql)` 需要兼容不含 `STATEMENT_ID` 的 `PLAN_TABLE`
  - `dm_query(...EXPLAIN PLAN...)` 的底层桥接路径需要避免暴露“列不存在”这一实现细节
- 依赖与风险：
  - 无新增外部依赖
  - 需要重新定义“如何识别本次计划结果”的兼容边界，避免读取历史计划或误删共享计划数据
