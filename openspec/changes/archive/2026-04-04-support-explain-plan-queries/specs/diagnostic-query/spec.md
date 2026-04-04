## ADDED Requirements

### Requirement: 诊断查询执行计划支持
系统 SHALL 定义一个诊断语句分类器，仅允许明确识别为只读诊断 SQL（例如 `EXPLAIN ...`、`EXPLAIN PLAN ...`）进入 MCP 查询流水线，并在响应 `metadata` 中附带对应的 `query_type`/`statement_type` 字段。该分类器 SHALL 拒绝任何 DML/DDL/授权/会话破坏语句，即使这类语句前缀为 `EXPLAIN`。

### Requirement: 单次调用获取执行计划（避免跨 session 依赖）
系统 SHALL 提供一个专用 MCP 工具用于查询 `SELECT` 的执行计划（建议工具名 `dm_explain_plan(select_sql)`）。该工具 SHALL 在一次调用中完成计划生成与计划读取/返回，且不得要求用户再通过单独的 `dm_query("SELECT ... FROM PLAN_TABLE ...")` 来拼接两次调用的结果（因为两次调用可能落在不同数据库 session）。

#### Scenario: `dm_explain_plan` 返回执行计划
- **WHEN** 用户调用 `dm_explain_plan("SELECT ...")`
- **THEN** 系统对输入做与 `dm_query` 等价的安全校验，并确保输入语句被识别为 `SELECT`
- **AND** 系统在同一数据库 session 内执行获取计划所需的诊断语句（例如 `EXPLAIN SELECT ...` 或 `EXPLAIN PLAN ...` + 计划表读取）
- **AND** 响应包含执行计划行（列/rows 或等价结构），并在 `metadata` 中标注该调用属于执行计划工具（例如 `statement_type = EXPLAIN` 或 `EXPLAIN_PLAN`）

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
- **THEN** 分类器检测到非法关键词，抛出 `InvalidParameterError` 并保持原有的“拒绝写操作”行为
