# 诊断查询执行计划支持

## Purpose

TBD

## ADDED Requirements

### Requirement: 诊断查询执行计划支持
系统 SHALL 定义一个诊断语句分类器，仅允许明确识别为只读诊断 SQL（例如 `EXPLAIN ...`、`EXPLAIN PLAN ...`）进入 MCP 查询流水线，并在响应 `metadata` 中附带对应的 `query_type`/`statement_type` 字段。该分类器 SHALL 拒绝任何 DML/DDL/授权/会话破坏语句，即使这类语句前缀为 `EXPLAIN`。

### Requirement: 单次调用获取执行计划（避免跨 session 依赖）
系统 SHALL 提供一个专用 MCP 工具用于查询 `SELECT` 的执行计划（工具名 `dm_explain_plan(select_sql)`）。该工具 SHALL 在一次调用中完成计划生成与计划读取/返回，且不得要求用户再通过单独的 `dm_query("SELECT ... FROM PLAN_TABLE ...")` 来拼接两次调用的结果。实现 SHALL 优先使用目标环境可直接返回计划的诊断路径，而不是默认依赖 `PLAN_TABLE`。实现不得假设标准 `EXPLAIN`、`EXPLAIN PLAN` 与 `PLAN_TABLE` 的行为在所有达梦环境中一致，而必须根据目标环境支持的计划来源选择兼容路径。

#### Scenario: `dm_explain_plan` 优先使用直接计划路径
- **WHEN** 用户调用 `dm_explain_plan("SELECT ...")`
- **THEN** 系统对输入做与 `dm_query` 等价的安全校验，并确保输入语句被识别为 `SELECT`
- **AND** 系统在同一数据库 session 内优先执行可直接产出执行计划的诊断语句（例如 `EXPLAIN SELECT ...`）
- **AND** 若驱动可直接返回计划文本或等价结果，响应必须包含执行计划行（列/rows 或等价结构）
- **AND** 响应 `metadata` 必须保留该调用属于执行计划工具的语义标识

#### Scenario: `dm_explain_plan` 读取 `PLAN_TABLE` 时使用兼容语句形态
- **WHEN** `dm_explain_plan` 选择通过 `PLAN_TABLE` 获取执行计划
- **THEN** 系统 MUST 先执行能触发计划表写入的兼容语句形态（例如 `EXPLAIN PLAN SELECT ...` 或 `EXPLAIN PLAN FOR SELECT ...` 的目标库兼容变体）
- **AND** 系统不得执行 `EXPLAIN SELECT ...` 后再假设本次计划一定会出现在 `PLAN_TABLE`

#### Scenario: `EXPLAIN_PLAN` 执行成功但 `PLAN_TABLE` 为空
- **WHEN** 系统执行了 `EXPLAIN PLAN ...`
- **AND** 后续读取 `PLAN_TABLE` 时没有获得任何可归属到本次语句的计划行
- **THEN** 系统应返回清晰的兼容性错误，明确说明目标环境没有产出可读取的执行计划
- **AND** 系统不得返回 `success = true` 且 `rows = []` 来伪装为成功

#### Scenario: `PLAN_TABLE` 包含 `STATEMENT_ID`
- **WHEN** `dm_explain_plan` 在目标环境发现 `PLAN_TABLE` 包含 `STATEMENT_ID`
- **THEN** 系统应优先使用 `STATEMENT_ID` 或等价隔离机制定位本次执行计划生成的行
- **AND** 计划读取与清理仅作用于本次语句对应的计划数据

#### Scenario: `PLAN_TABLE` 不包含 `STATEMENT_ID` 但 session 可安全清理
- **WHEN** `dm_explain_plan` 在目标环境发现 `PLAN_TABLE` 不包含 `STATEMENT_ID`
- **AND** 系统可在当前 JDBC session 内成功清理并验证当前 session 可见计划行为 0
- **THEN** 系统应改用"同 session 预清理 -> 生成计划 -> 读取当前 session 可见计划 -> 清理"的兼容路径
- **AND** 工具不得因为缺少 `STATEMENT_ID` 直接失败

#### Scenario: `PLAN_TABLE` 不包含 `STATEMENT_ID` 且无法安全隔离
- **WHEN** `dm_explain_plan` 在目标环境发现 `PLAN_TABLE` 不包含 `STATEMENT_ID`
- **AND** 系统无法证明当前 session 的计划表读取不会混入历史数据或其他 session 数据
- **THEN** 系统应返回清晰的兼容性错误，明确说明当前 `PLAN_TABLE` 结构不支持安全隔离本次执行计划
- **AND** 系统不得将底层"列不存在"或原始 SQL 异常直接暴露为用户主要错误信息

#### Scenario: 标准 `EXPLAIN` 通过驱动直接返回计划
- **WHEN** 用户调用 `dm_query("EXPLAIN SELECT ...")`
- **THEN** 分类器将语句标记为 `statement_type = EXPLAIN`
- **AND** 校验链路允许语句通过
- **AND** 若 JDBC `execute()` 未返回 `ResultSet`，执行层仍必须尝试从达梦驱动暴露的直接计划接口中读取计划文本
- **AND** 响应 `metadata.statement_type` = `EXPLAIN`

#### Scenario: `EXPLAIN PLAN` 输入改写到受支持路径
- **WHEN** 用户调用 `dm_query("EXPLAIN PLAN SELECT ...")` 或 `dm_query("EXPLAIN PLAN FOR SELECT ...")`
- **THEN** 分类器仍将输入识别为执行计划查询
- **AND** 工具层必须将输入规范化到当前环境可执行的诊断路径，而不是无条件要求底层支持原始文本形态
- **AND** 响应 `metadata` 必须保留用户输入的诊断语义，并可附带实际执行路径

#### Scenario: 目标环境未直接返回计划
- **WHEN** 用户调用 `dm_query("EXPLAIN SELECT ...")` 或 `dm_explain_plan("SELECT ...")`
- **AND** 底层既未返回 `ResultSet`，也未返回可读取的直接计划文本
- **THEN** 系统必须返回清晰的诊断兼容性错误
- **AND** 系统不得将该情况伪装为 `success = true` 且 `rows = []`

#### Scenario: `EXPLAIN` 在目标 JDBC 版本不返回 ResultSet
- **WHEN** 用户调用 `dm_query("EXPLAIN SELECT ...")` 且底层 JDBC 无法返回 ResultSet（例如报"执行未准备SQL语句"或返回 updateCount）
- **THEN** 系统应将底层错误映射为清晰的诊断错误，提示用户改用 `EXPLAIN PLAN ...`（或给出当前支持的诊断语句形态）
- **AND** 系统不得将该错误伪装为"写操作被拒绝"

#### Scenario: `EXPLAIN PLAN` 返回计划摘要
- **WHEN** 用户调用 `dm_query("EXPLAIN PLAN SELECT ...")`
- **THEN** 分类器将语句标记为 `statement_type = EXPLAIN_PLAN`
- **AND** Java 桥接执行语句以触发计划生成，并查询计划表获取本次语句对应的计划摘要
- **AND** 响应 `metadata.statement_type` = `EXPLAIN_PLAN`
- **AND** 若可获取计划表行数，响应 `metadata.plan_table_row_count` 应包含该值

#### Scenario: `EXPLAIN PLAN FOR` 兼容形态
- **WHEN** 用户调用 `dm_query("EXPLAIN PLAN FOR SELECT ...")`
- **THEN** 分类器仍将语句标记为 `statement_type = EXPLAIN_PLAN`
- **AND** 若目标数据库不支持 `FOR` 关键字，执行层可对该语句进行兼容性规范化（例如去除 `FOR`）或给出清晰错误提示

#### Scenario: 诊断语句必须全部大写/小写枚举
- **WHEN** 用户调用 `dm_query("explain select ...")` 或包含前导注释
- **THEN** 分类器在忽略注释后仍能识别是 `EXPLAIN`，并按照同样的逻辑执行

#### Scenario: 非诊断语句或危险语句被拒绝
- **WHEN** 用户尝试 `dm_query("EXPLAIN INSERT ...")` 或 `dm_query("EXPLAIN /*; DROP TABLE */ SELECT ...")`
- **THEN** 分类器检测到非法关键词，抛出 `InvalidParameterError` 并保持原有的"拒绝写操作"行为
