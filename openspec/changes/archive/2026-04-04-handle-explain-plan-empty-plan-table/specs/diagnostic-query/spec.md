## MODIFIED Requirements

### Requirement: 单次调用获取执行计划（避免跨 session 依赖）
系统 SHALL 提供一个专用 MCP 工具用于查询 `SELECT` 的执行计划（建议工具名 `dm_explain_plan(select_sql)`）。该工具 SHALL 在一次调用中完成计划生成与计划读取/返回，且不得要求用户再通过单独的 `dm_query("SELECT ... FROM PLAN_TABLE ...")` 来拼接两次调用的结果（因为两次调用可能落在不同数据库 session）。实现不得假设标准 `EXPLAIN`、`EXPLAIN PLAN` 与 `PLAN_TABLE` 的行为在所有达梦环境中一致，而必须根据目标环境支持的计划来源选择兼容路径。

#### Scenario: `dm_explain_plan` 返回执行计划
- **WHEN** 用户调用 `dm_explain_plan("SELECT ...")`
- **THEN** 系统对输入做与 `dm_query` 等价的安全校验，并确保输入语句被识别为 `SELECT`
- **AND** 系统在同一数据库 session 内执行获取计划所需的诊断语句
- **AND** 响应包含执行计划行（列/rows 或等价结构），并在 `metadata` 中标注该调用属于执行计划工具（例如 `statement_type = EXPLAIN_PLAN`）

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
- **THEN** 系统应改用“同 session 预清理 -> 生成计划 -> 读取当前 session 可见计划 -> 清理”的兼容路径
- **AND** 工具不得因为缺少 `STATEMENT_ID` 直接失败

#### Scenario: `PLAN_TABLE` 不包含 `STATEMENT_ID` 且无法安全隔离
- **WHEN** `dm_explain_plan` 在目标环境发现 `PLAN_TABLE` 不包含 `STATEMENT_ID`
- **AND** 系统无法证明当前 session 的计划表读取不会混入历史数据或其他 session 数据
- **THEN** 系统应返回清晰的兼容性错误，明确说明当前 `PLAN_TABLE` 结构不支持安全隔离本次执行计划
- **AND** 系统不得将底层“列不存在”或原始 SQL 异常直接暴露为用户主要错误信息

#### Scenario: 标准 `EXPLAIN` 返回结果集
- **WHEN** 用户调用 `dm_query("EXPLAIN SELECT ...")`
- **THEN** 分类器将语句标记为 `statement_type = EXPLAIN`
- **AND** 校验链路允许语句通过，Java 桥接使用通用的 JDBC `execute()` 路径并在存在 ResultSet 时返回执行计划行
- **AND** 响应 `metadata.statement_type` = `EXPLAIN`

#### Scenario: `EXPLAIN` 在目标 JDBC 版本不返回 ResultSet
- **WHEN** 用户调用 `dm_query("EXPLAIN SELECT ...")` 且底层 JDBC 无法返回 ResultSet（例如报“执行未准备SQL语句”或返回 updateCount）
- **THEN** 系统应将底层错误映射为清晰的诊断错误，提示用户改用 `EXPLAIN PLAN ...`（或给出当前支持的诊断语句形态）
- **AND** 系统不得将该错误伪装为“写操作被拒绝”

#### Scenario: `EXPLAIN PLAN` 返回计划摘要
- **WHEN** 用户调用 `dm_query("EXPLAIN PLAN SELECT ...")`
- **THEN** 分类器将语句标记为 `statement_type = EXPLAIN_PLAN`
- **AND** Java 桥接执行语句以触发计划生成，并根据目标环境可用的计划表结构获取本次语句对应的计划摘要
- **AND** 响应 `metadata.statement_type` = `EXPLAIN_PLAN`
- **AND** 若可获取计划表行数，响应 `metadata.plan_table_row_count` 应包含该值

#### Scenario: `EXPLAIN PLAN FOR` 兼容形态
- **WHEN** 用户调用 `dm_query("EXPLAIN PLAN FOR SELECT ...")`
- **THEN** 分类器仍将语句标记为 `statement_type = EXPLAIN_PLAN`
- **AND** 若目标数据库不支持 `FOR` 关键字，执行层可对该语句进行兼容性规范化（例如去除 `FOR`）或给出清晰错误提示

#### Scenario: 诊断语句必须全部大写或小写枚举
- **WHEN** 用户调用 `dm_query("explain select ...")` 或包含前导注释
- **THEN** 分类器在忽略注释后仍能识别是 `EXPLAIN`
- **AND** 系统按同样的兼容逻辑执行

#### Scenario: 非诊断语句或危险语句被拒绝
- **WHEN** 用户尝试 `dm_query("EXPLAIN INSERT ...")` 或 `dm_query("EXPLAIN /*; DROP TABLE */ SELECT ...")`
- **THEN** 分类器检测到非法关键词，抛出 `InvalidParameterError`
- **AND** 保持原有的“拒绝写操作”行为
