## MODIFIED Requirements

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
