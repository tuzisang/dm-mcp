## Context

`dm_explain_plan` 当前通过 Java 桥接执行 `EXPLAIN PLAN`，然后读取 `PLAN_TABLE` 返回计划行。现有实现为了避免跨调用 session 不一致，把隔离逻辑写成了“生成唯一 `STATEMENT_ID` -> 调用 `SP_SET_PLAN_TABLE_STMTID(...)` -> `WHERE STATEMENT_ID = ...` 查询 -> 按 `STATEMENT_ID` 删除”。这个思路在支持该列的 DM 版本上可行，但在本次实测环境中，`PLAN_TABLE` 根本没有 `STATEMENT_ID`，导致工具在计划生成之后直接因为“列不存在”失败。

这次修复的难点不在于连接、权限或 SQL 路由，而在于 DM 不同版本 / 模板库之间 `PLAN_TABLE` 结构并不一致。我们既要保留“单次调用、同一 session 内取计划”的要求，又不能为了兼容去读到历史计划或误删共享数据。

## Goals / Non-Goals

**Goals:**
- 让 `dm_explain_plan` 和 `EXPLAIN_PLAN` 在缺少 `STATEMENT_ID` 的 `PLAN_TABLE` 上仍能工作，或至少给出明确的兼容性错误。
- 把计划读取从硬编码列依赖改成基于 `PLAN_TABLE` 实际结构的能力探测。
- 保持现有的单次调用、同一 JDBC 连接内完成“生成计划 + 读取计划 + 清理”的执行模型。
- 为这次兼容性缺口补上回归测试，避免以后再次把 `STATEMENT_ID` 写死。

**Non-Goals:**
- 不引入新的外部依赖或新的数据库对象。
- 不放开新的 SQL 类型，也不改变 `dm_query` / `dm_explain_plan` 的安全边界。
- 不试图支持所有未知的达梦执行计划表变种；无法安全隔离时允许显式失败。

## Decisions

- **先探测 `PLAN_TABLE` 列结构，再决定读取策略**
  - 方案：在 `executeExplainPlan` 内先获取 `PLAN_TABLE` 元数据，判断是否存在 `STATEMENT_ID`。
  - 选择理由：根因就是实现对表结构作了错误假设，能力探测是最低成本且最直接的修复。
  - 备选方案：继续直接查询 `WHERE STATEMENT_ID = ...`，失败后再回退。否决原因是仍会先触发同样的 SQL 异常，而且错误语义不清晰。

- **优先保留 `STATEMENT_ID` 路径**
  - 方案：若探测到 `STATEMENT_ID`，继续沿用当前的按语句隔离读取与清理。
  - 选择理由：这是最精确的隔离方式，能避免读到历史计划或误删其他计划行。
  - 备选方案：统一改成“清空整张 `PLAN_TABLE` 再执行”。否决原因是对支持 `STATEMENT_ID` 的环境反而退化了安全性。

- **缺少 `STATEMENT_ID` 时回退到“同 session 预清理”策略**
  - 方案：在当前连接内先执行 `DELETE FROM PLAN_TABLE`，再确认当前 session 可见行为 0；只有验证成功后才执行 `EXPLAIN PLAN` 并读取 `PLAN_TABLE`。
  - 选择理由：从现有行为和问题现象看，DM 计划表通常与 session 可见性绑定；这一方案能在不依赖额外列的前提下兼容现网环境。
  - 备选方案：按 `ID` 最大值、时间戳或行数差分推断“哪些行是本次生成的”。否决原因是不同 DM 版本并不保证这些字段语义稳定，容易串读。

- **无法证明隔离安全时快速失败**
  - 方案：若预清理后仍读到行，或无法完成清理验证，则返回清晰的兼容性错误，提示当前 `PLAN_TABLE` 结构不支持安全隔离。
  - 选择理由：错误地返回混合计划结果比显式失败更危险，会误导 SQL 调优结论。
  - 备选方案：无条件继续读取所有计划行。否决原因是可能混入历史数据或其他 session 数据。

- **计划读取改为通用结果集提取**
  - 方案：用通用 ResultSet 提取逻辑读取计划查询结果，避免再对计划表列集合做二次硬编码。
  - 选择理由：这次暴露的问题是 `STATEMENT_ID` 缺失，后续很可能还会遇到其他计划表列差异。
  - 备选方案：继续固定选择 `ID, PARENT_ID, OPERATION, ...`。否决原因是兼容性仍脆弱。

## Risks / Trade-offs

- **[Risk] `PLAN_TABLE` 在某些环境不是 session 隔离而是共享表** → 在回退路径中先执行清理并验证当前可见行为 0；验证失败时显式报兼容性错误，而不是继续读取。
- **[Risk] `DELETE FROM PLAN_TABLE` 会被 DBA 限制** → 将清理失败和隔离验证失败统一映射为兼容性错误，并保留支持 `STATEMENT_ID` 的优先路径。
- **[Risk] 读取 `SELECT * FROM PLAN_TABLE` 导致列顺序与旧实现不同** → 工具对外契约本来就是 `columns + rows`，只要列名和数据一致即可；测试应断言结构而非固定列序。
- **[Risk] Java 与 Python 工具层对错误信息表述不一致** → 在 Java 端先生成明确错误消息，再由 Python 端直接包装，避免“列不存在”这种底层异常成为主错误。

## Migration Plan

1. 在 OpenSpec delta specs 中明确 `PLAN_TABLE` 结构探测和无 `STATEMENT_ID` 回退路径。
2. 修改 `db/DmJdbcBridge.java`，实现能力探测、优先 `STATEMENT_ID`、回退清理路径以及明确错误消息。
3. 让 `db/client.py` / `tools/explain_plan.py` 保持返回契约不变，并在失败时透传新的兼容性错误。
4. 增加 Python 回归测试，覆盖成功兼容和清晰报错两种行为。
5. 编译并运行相关测试；若上线后发现某些环境不满足回退前提，可保留 `dm_query(EXPLAIN ...)`，同时让 `dm_explain_plan` 显式提示当前环境不支持安全隔离。

## Open Questions

- 是否需要把探测到的 `PLAN_TABLE` 能力（例如是否支持 `STATEMENT_ID`）附加到调试日志或 metadata 中，便于后续诊断？
- 若后续遇到既无 `STATEMENT_ID` 又无法安全清理的 DM 版本，是否需要新增数据库侧辅助对象或存储过程来做更强隔离？
