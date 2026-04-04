## MODIFIED Requirements

### Requirement: 单次调用获取执行计划（避免跨 session 依赖）
系统 SHALL 提供一个专用 MCP 工具用于查询 `SELECT` 的执行计划（工具名 `dm_explain_plan(select_sql)`）。该工具 SHALL 在一次调用中完成计划生成与计划读取/返回，且不得要求用户再通过单独的 `dm_query("SELECT ... FROM PLAN_TABLE ...")` 来拼接两次调用的结果。实现 SHALL 优先使用目标环境可直接返回计划的诊断路径，而不是默认依赖 `PLAN_TABLE`。

#### Scenario: `dm_explain_plan` 优先使用直接计划路径
- **WHEN** 用户调用 `dm_explain_plan("SELECT ...")`
- **THEN** 系统对输入做与 `dm_query` 等价的安全校验，并确保输入语句被识别为 `SELECT`
- **AND** 系统在同一数据库 session 内优先执行可直接产出执行计划的诊断语句（例如 `EXPLAIN SELECT ...`）
- **AND** 若驱动可直接返回计划文本或等价结果，响应必须包含执行计划行（列/rows 或等价结构）
- **AND** 响应 `metadata` 必须保留该调用属于执行计划工具的语义标识

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

#### Scenario: 诊断语句必须全部大写/小写枚举
- **WHEN** 用户调用 `dm_query("explain select ...")` 或包含前导注释
- **THEN** 分类器在忽略注释后仍能识别是 `EXPLAIN`
- **AND** 系统按照同样的直接计划逻辑执行
