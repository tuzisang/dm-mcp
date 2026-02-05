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

### Requirement: 查询执行

系统 SHALL 支持 SELECT 查询并返回结果集，内部实现改为通过 Java 桥接服务执行。

#### Scenario: 执行 SELECT 查询
- **WHEN** 调用 `execute_query(sql)` 方法
- **THEN** 系统应通过 Java 桥接服务执行 SQL
- **AND** 返回包含结果的列表
- **AND** 保持与原有 dmpython 实现相同的数据格式

#### Scenario: 参数化查询
- **WHEN** 调用 `execute_query(sql, params)` 传入参数
- **THEN** 系统应正确绑定参数防止 SQL 注入
- **AND** 返回正确的查询结果

### Requirement: 表结构查询

系统 SHALL 支持查询数据库表结构信息，内部实现改为通过达梦 JDBC 驱动的 DatabaseMetaData。

#### Scenario: 列出所有表
- **WHEN** 调用 `list_tables(schema)` 方法
- **THEN** 系统应返回指定 schema 中的所有表名
- **AND** 保持与原有实现相同的返回格式

#### Scenario: 描述表结构
- **WHEN** 调用 `describe_table(table_name, schema)` 方法
- **THEN** 系统应返回表的列信息（列名、类型、是否可空等）
- **AND** 保持与原有实现相同的返回格式

### Requirement: 视图查询

系统 SHALL 支持查询数据库视图信息。

#### Scenario: 列出所有视图
- **WHEN** 调用 `list_views(schema)` 方法
- **THEN** 系统应返回指定 schema 中的所有视图名

#### Scenario: 获取视图定义
- **WHEN** 调用 `get_view_definition(view_name, schema)` 方法
- **THEN** 系统应返回创建视图的完整 SQL 语句

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

## REMOVED Requirements

无移除项（只修改内部实现，保持接口不变）
