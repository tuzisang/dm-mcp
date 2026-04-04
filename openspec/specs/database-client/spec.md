# 数据库客户端规范

## MODIFIED Requirements

### Requirement: 数据库连接

系统 SHALL 提供统一的数据库连接接口，内部实现从 dmpython 切换到 jaydebeapi + HikariCP。

#### Scenario: 建立连接
- **WHEN** 调用 `DmClient.__init__()` 传入配置
- **THEN** 系统应初始化 Java 桥接服务
- **AND** 通过 HikariCP 创建连接池

#### Scenario: 连接复用
- **WHEN** 多次调用查询方法
- **THEN** 系统应复用连接池中的连接
- **AND** 不重复建立连接

#### Scenario: 连接测试读取统一查询结果
- **WHEN** `dm_connect()` 执行测试查询 `SELECT 1 AS test_value FROM DUAL`
- **THEN** 工具 MUST 从统一的 `{columns, rows}` 结果中读取首行
- **AND** 在测试查询成功时返回明确的连接成功结果，而不是因为结果包装方式报错

### Requirement: 查询执行

系统 SHALL 支持 SELECT 查询和受控的诊断 SQL（如 `EXPLAIN`/`EXPLAIN PLAN`），并将这两类语句都通过 Java 桥接执行。系统仍需对所有 DML、DDL、多语句注入和授权类语句返回错误。

#### Scenario: 执行 SELECT 查询
- **WHEN** 调用 `execute_query(sql)` 方法并传入标准的 `SELECT` 语句
- **THEN** 系统应通过 Java 桥接服务执行 SQL
- **AND** 返回统一的 `{columns, rows}` 结构
- **AND** 保持与工具层约定一致，不得要求上层再猜测是否为 `list[dict]`

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

#### Scenario: 高层工具消费统一查询结果
- **WHEN** 连接工具、schema 工具或其他高层包装调用 `execute_query()`、`list_tables()`、`list_views()`、`describe_table()`、`get_view_definition()`
- **THEN** 它们 MUST 按统一的 `{columns, rows}` 契约读取结果
- **AND** 不得继续把结果当成 `list[dict]` 使用

#### Scenario: 参数化查询
- **WHEN** 调用 `execute_query(sql, params)` 传入参数
- **THEN** 系统应正确绑定参数防止 SQL 注入
- **AND** 返回正确的查询结果

### Requirement: 表结构查询

系统 SHALL 支持查询数据库表结构信息，内部实现改为通过达梦 JDBC 驱动的 DatabaseMetaData。

#### Scenario: 列出所有表
- **WHEN** 调用 `list_tables(schema)` 方法
- **THEN** 系统应返回统一的 `{columns, rows}` 结构
- **AND** 列名应明确表示表名语义（例如 `TABLE_NAME`），避免上层再做旧式逐行别名转换

#### Scenario: 描述表结构
- **WHEN** 调用 `describe_table(table_name, schema)` 方法
- **THEN** 系统应返回表的列信息（列名、类型、是否可空等）
- **AND** 结果中的 `metadata.row_count` MUST 等于实际 `rows` 数量

### Requirement: 视图查询

系统 SHALL 支持查询数据库视图信息。

#### Scenario: 列出所有视图
- **WHEN** 调用 `list_views(schema)` 方法
- **THEN** 系统应返回统一的 `{columns, rows}` 结构
- **AND** 列名应明确表示视图名语义（例如 `VIEW_NAME`）

#### Scenario: 获取视图定义
- **WHEN** 调用 `get_view_definition(view_name, schema)` 方法
- **THEN** 系统应返回创建视图的完整 SQL 语句
- **AND** 结果中的 `metadata.row_count` MUST 等于实际 `rows` 数量

### Requirement: 上下文管理器支持

系统 SHALL 支持使用 `with` 语句自动管理连接资源。

#### Scenario: 使用 with 语句
- **WHEN** 使用 `with DmClient(config) as client:` 语法
- **THEN** 进入 with 块时应建立连接
- **AND** 退出 with 块时应自动关闭连接并释放资源
- **AND** 即使发生异常也应正确清理资源

### Requirement: 错误处理

系统 SHALL 统一错误处理，将 Java 异常转换为 Python 标准异常。

#### Scenario: 连接失败
- **WHEN** 数据库连接失败
- **THEN** 系统应抛出 `ConnectionError` 异常

#### Scenario: SQL 语法错误
- **WHEN** 执行的 SQL 存在语法错误
- **THEN** 系统应抛出 `DatabaseError` 异常
- **AND** 异常信息应包含数据库返回的错误详情

#### Scenario: 查询超时
- **WHEN** 查询执行时间超过配置的超时时间
- **THEN** 系统应抛出 `TimeoutError` 异常
