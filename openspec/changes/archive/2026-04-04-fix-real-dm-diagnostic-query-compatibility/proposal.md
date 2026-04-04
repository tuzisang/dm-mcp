## Why

在 2026-04-04 的真实达梦联调中，诊断 SQL 路径与当前实现假设明显不一致：`dm_query("EXPLAIN SELECT 1 AS test_value FROM DUAL")` 返回 `success=true` 但 `rows=[]`，`dm_query("EXPLAIN PLAN SELECT 1 AS test_value FROM DUAL")` 与 `dm_query("EXPLAIN PLAN FOR SELECT 1 AS test_value FROM DUAL")` 都报“第 1 行, 第 13 列[SELECT]附近出现错误”，而 `dm_explain_plan("SELECT 1 AS test_value FROM DUAL")` 则返回“`PLAN_TABLE` 未返回任何计划行”的兼容性错误。说明当前 DM-MCP 对真实目标库支持哪种 `EXPLAIN` 语法、何时返回 ResultSet、何时写入 `PLAN_TABLE` 的判断都不可靠。

这已经超出单一报错修补的范围。现有实现同时硬编码了“去掉 `FOR` 更兼容”“`EXPLAIN PLAN` 可写入 `PLAN_TABLE`”“普通 `EXPLAIN` 拿不到结果时可视为空结果”三类假设，而真实环境至少否定了其中两项。需要新增一条提案，重新定义诊断 SQL 的能力探测、方言选择和失败语义。

## What Changes

- 修订诊断查询能力要求：`dm_query("EXPLAIN ...")` 与 `dm_explain_plan(...)` 必须根据真实达梦环境支持的语法和返回方式选择路径，而不是固定依赖某一种 `EXPLAIN` / `EXPLAIN PLAN` 变体。
- 重新评估并约束 `EXPLAIN PLAN FOR` 的规范化逻辑，避免再无条件移除 `FOR` 导致本来可能兼容的语句被改坏。
- 明确普通 `EXPLAIN` 的失败语义：如果 JDBC 未返回 ResultSet，系统必须给出清晰诊断错误，而不是返回 `success=true` 且 `rows=[]`。
- 明确 `dm_explain_plan()` 的目标语义：当目标库既不返回直接结果、也不向 `PLAN_TABLE` 写入可读计划时，工具必须给出明确兼容性结论，并暴露本次尝试过的诊断路径。
- 补充真实环境导向的回归测试，覆盖 `EXPLAIN`、`EXPLAIN PLAN`、`EXPLAIN PLAN FOR` 三种输入在不同 JDBC / DM 组合下的行为。

## Capabilities

### New Capabilities
<!-- None -->

### Modified Capabilities
- `diagnostic-query`: 调整 `EXPLAIN` / `EXPLAIN PLAN` / `dm_explain_plan` 的成功条件、方言兼容策略和错误语义，使其匹配真实达梦环境而不是硬编码假设。
- `java-bridge`: 调整诊断语句路由、ResultSet 检测和计划来源选择逻辑，确保桥接层能够对“语法不支持”“无 ResultSet”“无 `PLAN_TABLE` 数据”给出不同的明确结论。

## Impact

- 受影响代码：
  - `tools/query.py`
  - `tools/explain_plan.py`
  - `core/validators.py`
  - `db/client.py`
  - `db/DmJdbcBridge.java`
  - 与诊断 SQL 相关的测试和文档
- 受影响行为：
  - `dm_query("EXPLAIN SELECT ...")` 不应再把“无 ResultSet”伪装成空成功
  - `dm_query("EXPLAIN PLAN [FOR] SELECT ...")` 需要按真实 DM 方言选择可执行路径
  - `dm_explain_plan(select_sql)` 需要给出可操作的兼容性结论，而不只是单一路径失败
- 依赖与风险：
  - 无新增外部依赖
  - 需要在不破坏现有 SQL 安全校验的前提下，引入更细的诊断路径探测
  - 不同 DM/JDBC 版本的行为可能不一致，需把“环境能力探测”定义为一等行为而不是隐式假设
