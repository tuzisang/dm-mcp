## MODIFIED Requirements

### Requirement: 查询执行

系统 SHALL 支持 SELECT 查询和受控的诊断 SQL（如 `EXPLAIN`/`EXPLAIN PLAN`），并将这两类语句都通过 Java 桥接执行。系统仍需对所有 DML、DDL、多语句注入和授权类语句返回错误。

#### Scenario: 执行 SELECT 查询
- **WHEN** 调用 `execute_query(sql)` 方法并传入标准的 `SELECT` 语句
- **THEN** 系统应通过 Java 桥接服务执行 SQL
- **AND** 返回包含结果的列表
- **AND** 保持与原有 dmpython 实现相同的数据格式

#### Scenario: 执行诊断语句
- **WHEN** 调用 `execute_query(sql)` 并传入被识别为 `EXPLAIN`/`EXPLAIN PLAN` 的语句（例如 `EXPLAIN SELECT ...`、`EXPLAIN PLAN SELECT ...`，可选兼容 `EXPLAIN PLAN FOR SELECT ...`）
- **THEN** 系统应将请求分类为诊断类型，并把分类结果发送到 Java 桥接
- **AND** 若语句返回 ResultSet（如部分环境支持的 `EXPLAIN SELECT ...`），则读取并返回执行计划行
- **AND** 若语句仅触发计划生成（如 `EXPLAIN PLAN ...`），则应在触发后查询计划表返回计划摘要，并在可得时把计划表行数暴露给上层（用于工具层填充 `metadata.plan_table_row_count`）
- **AND** 除了以上诊断和标准 `SELECT`，任何 DML/DDL 语句都应被拒绝，抛出 `InvalidParameterError`

#### Scenario: 返回值契约稳定
- **WHEN** `execute_query(sql)` 执行任意被允许的语句（SELECT/诊断）
- **THEN** 返回值的数据形态 MUST 保持稳定（不得在不同语句类型下在 `list`/`dict` 之间切换）
- **AND** 任何额外的诊断信息（如 `plan_table_row_count`）应通过稳定的扩展机制提供（例如独立字段/结构），避免上层工具因类型漂移发生运行时错误

#### Scenario: 参数化查询
- **WHEN** 调用 `execute_query(sql, params)` 传入参数
- **THEN** 系统应正确绑定参数防止 SQL 注入
- **AND** 返回正确的查询结果
