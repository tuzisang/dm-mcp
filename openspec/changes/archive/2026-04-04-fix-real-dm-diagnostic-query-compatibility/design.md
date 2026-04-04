## Context

2026-04-04 的真实联调已经证明，当前环境不能把“执行计划 = `EXPLAIN PLAN` 写入 `PLAN_TABLE`”当成默认真相：

- `EXPLAIN PLAN SELECT ...` 与 `EXPLAIN PLAN FOR SELECT ...` 在目标库上直接报语法错误。
- `EXPLAIN SELECT ...` 可以成功执行，但 JDBC `execute()` 返回的是 `updateCount=0`，不是 `ResultSet`。
- 真实驱动 `dm.jdbc.driver.DmdbStatement` 在 `EXPLAIN SELECT ...` 之后可通过 `getExplain()` 直接拿到完整计划文本。

这说明问题不在“达梦一定要落表”，而在我们当前桥接层只认 `ResultSet` / `PLAN_TABLE` 两种来源，漏掉了驱动原生的直接计划接口。

## Goals / Non-Goals

**Goals:**
- 让 `dm_explain_plan(select_sql)` 在当前真实环境下稳定返回执行计划。
- 让 `dm_query("EXPLAIN SELECT ...")` 不再出现“成功但空结果”。
- 保留 `EXPLAIN PLAN [FOR]` 这类用户输入的兼容入口，但内部改走当前环境可用的直接计划路径。
- 在桥接层明确区分“无结果集但有驱动计划文本”和“完全无可读计划”。

**Non-Goals:**
- 不在本次变更里重做 `PLAN_TABLE` 路径的全部兼容逻辑。
- 不尝试复刻所有达梦图形客户端的展示格式。
- 不引入新的外部依赖或重构整个 Java/Python 通信协议。

## Decisions

### 1. `dm_explain_plan()` 改为执行 `EXPLAIN SELECT ...`
原因：真实驱动已验证这条路径可执行，并能从 `DmdbStatement.getExplain()` 拿到计划；而 `EXPLAIN PLAN` 在当前环境语法不通。

备选方案：
- 继续使用 `EXPLAIN PLAN` + `PLAN_TABLE`：已被真实环境否定。
- 改走 `DBMS_XPLAN` / `SYSPLANHIST`：存在可用性，但需要额外匹配历史 SQL，复杂度更高，作为后续兼容增强更合适。

### 2. Java 桥接在 `statement_type = EXPLAIN` 且无 `ResultSet` 时读取 `DmdbStatement.getExplain()`
原因：这是当前最贴近达梦客户端行为的原生能力，且只需在桥接层加一条分支，不破坏现有协议。

备选方案：
- 在 Python 侧通过额外 SQL 读取计划：需要依赖库对象或历史表，不如驱动直接接口稳定。
- 在 Java 侧继续返回空结果，再由 Python 补救：会把驱动能力藏掉，错误语义仍然模糊。

### 3. `EXPLAIN PLAN [FOR]` 输入在工具层规范化为 `EXPLAIN SELECT ...`
原因：用户可能已经习惯输入 `EXPLAIN PLAN`，但底层实际可执行的是 `EXPLAIN`。工具层应该把“用户输入语义”和“底层执行路径”分开。

备选方案：
- 保持原样并直接报错：对用户不够友好，也无法达成“执行计划能查”的目标。

## Risks / Trade-offs

- [返回格式从结构化计划表变成文本行] → 通过统一 `columns/rows` 结构承载，每行一条计划文本，避免破坏工具契约。
- [驱动版本差异可能导致 `getExplain()` 缺失或返回空串] → 在桥接层保留明确兼容性错误，不再伪装成空成功。
- [`EXPLAIN PLAN` 输入被改写后，响应中的 `sql` 与用户原始输入不同] → 在元数据中增加原始语义/实际执行路径，降低排障歧义。

## Migration Plan

1. 更新 OpenSpec delta spec 和 tasks，固定新的执行计划语义。
2. 修改 Java 桥接，使 `EXPLAIN` 能从 `DmdbStatement.getExplain()` 取计划文本。
3. 修改 Python 工具层，把 `dm_explain_plan()` 与 `EXPLAIN PLAN [FOR]` 输入统一到 `EXPLAIN SELECT` 路径。
4. 补充回归测试，覆盖 SQL 规范化、空结果报错和直接计划文本返回。
5. 用真实库再次执行 `dm_explain_plan()` / `dm_query("EXPLAIN ...")` 验证结果。

## Open Questions

- 是否需要在后续 change 中保留 `DBMS_XPLAN` / `SYSPLANHIST` 作为驱动直接计划接口不可用时的二级回退。
- 是否要把计划文本进一步解析成树形结构列，而不是当前的一行一行文本。
