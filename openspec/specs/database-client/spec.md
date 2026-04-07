# 数据库客户端规范

## Purpose

描述 MCP 进程内共享数据库客户端在当前只读阶段应保留的最小能力，包括共享运行时、稳定返回契约、诊断查询支持和明确的错误边界。

## Requirements

### Requirement: 数据库连接

系统 SHALL 提供统一的数据库连接接口，并将当前阶段的公开入口收敛到 MCP 进程内共享运行时。

#### Scenario: 共享运行时入口
- **WHEN** MCP 工具需要执行数据库操作
- **THEN** 系统 MUST 通过共享 client 入口获取数据库客户端
- **AND** 该 client 复用同一 Java 守护进程和 HikariCP 连接池

#### Scenario: 连接复用
- **WHEN** 多次调用查询方法
- **THEN** 系统应复用连接池中的连接
- **AND** 不重复建立新的进程级运行时

#### Scenario: 连接测试读取统一查询结果
- **WHEN** `dm_connect()` 执行测试查询 `SELECT 1 AS test_value FROM DUAL`
- **THEN** 工具 MUST 从统一的 `{columns, rows}` 结果中读取首行
- **AND** 在测试查询成功时返回明确的连接成功结果，而不是因为结果包装方式报错

### Requirement: 查询执行

系统 SHALL 支持 SELECT 查询和受控的诊断 SQL，并将这两类语句都通过 Java 桥接执行。系统仍需对所有 DML、DDL、多语句注入和授权类语句返回错误。

#### Scenario: 执行 SELECT 查询
- **WHEN** 调用 `execute_query(sql)` 方法并传入标准的 `SELECT` 语句
- **THEN** 系统应通过 Java 桥接服务执行 SQL
- **AND** 返回统一的 `{columns, rows}` 结构
- **AND** 保持与工具层约定一致，不得要求上层再猜测是否为 `list[dict]`

#### Scenario: 执行诊断语句
- **WHEN** 调用 `execute_query(sql)` 并传入被识别为 `EXPLAIN` 或 `EXPLAIN PLAN` 的语句
- **THEN** 系统应将请求分类为诊断类型，并把分类结果发送到 Java 桥接
- **AND** 若语句返回 ResultSet，则读取并返回执行计划行
- **AND** 若语句仅触发计划生成，则应在触发后查询计划表返回计划摘要，并在可得时把计划表行数暴露给上层
- **AND** 除了以上诊断和标准 `SELECT`，任何 DML、DDL 或授权类语句都应被拒绝，抛出 `InvalidParameterError`

#### Scenario: 返回值契约稳定
- **WHEN** `execute_query(sql)` 执行任意被允许的语句
- **THEN** 返回值的数据形态 MUST 保持稳定
- **AND** 任何额外的诊断信息应通过稳定的扩展字段提供，避免上层工具因类型漂移发生运行时错误

#### Scenario: 高层工具消费统一查询结果
- **WHEN** 连接工具、schema 工具或其他高层包装调用 `execute_query()`、`list_tables()`、`list_views()`、`describe_table()`、`get_view_definition()`
- **THEN** 它们 MUST 按统一的 `{columns, rows}` 契约读取结果
- **AND** 不得继续把结果当成 `list[dict]` 使用

### Requirement: 表结构查询

系统 SHALL 支持查询数据库表结构信息。

#### Scenario: 列出所有表
- **WHEN** 调用 `list_tables(schema)` 方法
- **THEN** 系统应返回统一的 `{columns, rows}` 结构
- **AND** 列名应明确表示表名语义

#### Scenario: 描述表结构
- **WHEN** 调用 `describe_table(table_name, schema)` 方法
- **THEN** 系统应返回表的列信息
- **AND** 结果中的 `metadata.row_count` MUST 等于实际 `rows` 数量

### Requirement: 视图查询

系统 SHALL 支持查询数据库视图信息。

#### Scenario: 列出所有视图
- **WHEN** 调用 `list_views(schema)` 方法
- **THEN** 系统应返回统一的 `{columns, rows}` 结构
- **AND** 列名应明确表示视图名语义

#### Scenario: 获取视图定义
- **WHEN** 调用 `get_view_definition(view_name, schema)` 方法
- **THEN** 系统应返回创建视图的完整 SQL 语句
- **AND** 结果中的 `metadata.row_count` MUST 等于实际 `rows` 数量

### Requirement: 错误处理

系统 SHALL 统一错误处理，将桥接层异常转换为 Python 侧稳定的连接错误或 SQL 执行错误，并在桥接启动阶段保留足够的根因上下文。

#### Scenario: 连接失败
- **WHEN** 数据库连接失败
- **THEN** 系统应抛出数据库连接错误

#### Scenario: 桥接启动失败透传根因
- **WHEN** 共享 `DmClient` 在创建或重建时失败于 Java 桥接启动阶段
- **THEN** 系统 MUST 抛出 `DatabaseConnectionError` 或等价连接错误
- **AND** 错误消息 MUST 包含桥接启动阶段的真实根因，例如 `ClassNotFoundException`、`javac` 编译失败或 Java 启动 stderr
- **AND** 不得只返回泛化的“无法建立数据库连接”

#### Scenario: SQL 语法错误
- **WHEN** 执行的 SQL 存在语法错误
- **THEN** 系统应抛出 SQL 执行错误
- **AND** 异常信息应包含数据库返回的错误详情

#### Scenario: 查询超时
- **WHEN** 查询执行时间超过配置的超时时间
- **THEN** 系统应抛出 `TimeoutError` 或等价超时错误
