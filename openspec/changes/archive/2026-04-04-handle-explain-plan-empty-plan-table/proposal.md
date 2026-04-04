## Why

`dm_explain_plan` 目前已经解决了 `PLAN_TABLE.STATEMENT_ID` 缺失导致的报错，但在真实达梦环境中仍存在残留兼容性问题：`EXPLAIN SELECT ...` 可以成功执行，却没有把本次执行计划写入 `PLAN_TABLE`，最终返回空计划行。当前实现把“计划一定会落到 `PLAN_TABLE`”当作默认前提，导致工具虽然不再报错，却仍无法稳定交付执行计划结果。

现有 OpenSpec 已覆盖“跨 session 读取计划表会丢结果”和“计划表列结构可能不一致”，但还没有定义“目标库可能根本不向 `PLAN_TABLE` 写入计划”的行为边界。需要补一条提案，把执行计划获取能力从“依赖某张表有数据”收敛为“按目标库可用机制返回计划，或给出明确兼容性结论”。

## What Changes

- 修订 `dm_explain_plan` / `EXPLAIN_PLAN` 的能力要求：实现不得将“`PLAN_TABLE` 中出现计划行”视为唯一成功路径，必须处理 `EXPLAIN` 成功但计划表为空的场景。
- 为 Java 桥接补充执行计划来源策略，要求先识别目标 JDBC / 达梦环境支持的返回方式，例如直接 ResultSet、计划表读取或其他受支持的诊断路径，而不是固定执行后查询 `PLAN_TABLE`。
- 明确空计划结果的失败语义：当目标环境既不返回直接结果、也不向 `PLAN_TABLE` 写入本次计划时，工具必须返回清晰的兼容性错误，说明“目标库未产出可读取的执行计划”，而不是返回成功但 `rows=[]`。
- 补充回归测试与文档，覆盖“`EXPLAIN` 直接返回结果集”“`PLAN_TABLE` 可读”“`EXPLAIN` 成功但 `PLAN_TABLE` 为空”三类行为，确保工具对不同达梦环境给出稳定、一致的结果。

## Capabilities

### New Capabilities
<!-- None -->

### Modified Capabilities
- `diagnostic-query`: 调整 `dm_explain_plan` / `EXPLAIN_PLAN` 的成功与失败判定，要求工具在 `PLAN_TABLE` 为空时仍能尝试其他受支持路径，或返回明确兼容性错误。
- `java-bridge`: 调整执行计划诊断语句的执行策略，要求桥接层探测并选择可用的计划结果来源，而不是默认依赖执行后读取 `PLAN_TABLE`。

## Impact

- 受影响代码：
  - `db/DmJdbcBridge.java`
  - `db/client.py`
  - `tools/explain_plan.py`
  - 与执行计划相关的测试、夹具和 README / 工具文档
- 受影响行为：
  - `dm_explain_plan(select_sql)` 不能再把空 `PLAN_TABLE` 结果当作成功执行
  - `dm_query("EXPLAIN ...")` / `dm_query("EXPLAIN PLAN ...")` 的底层桥接路径需要重新定义“何时视为拿到计划”
- 依赖与风险：
  - 无新增外部依赖
  - 需要明确不同 DM 版本 / JDBC 驱动下执行计划结果来源的优先级和回退边界
  - 若目标环境确实不产出可读取计划，需要保证错误信息足够明确，避免用户误判为“查询无执行计划节点”
