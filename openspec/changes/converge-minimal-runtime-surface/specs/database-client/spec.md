## MODIFIED Requirements

### Requirement: 数据库连接

系统 SHALL 提供统一的数据库连接接口，并在 MCP 进程内复用共享的 Java 桥接与 HikariCP 连接池，以支撑短时间频繁调用。

#### Scenario: 首次调用建立共享客户端
- **WHEN** MCP 进程首次需要执行数据库工具调用
- **THEN** 系统应创建共享 `DmClient`
- **AND** 共享 `DmClient` 应初始化 Java 桥接服务
- **AND** 通过 HikariCP 创建连接池

#### Scenario: 后续调用复用共享客户端
- **WHEN** 后续工具调用发生在同一 MCP 进程内
- **THEN** 系统应复用已存在的共享 `DmClient`
- **AND** 不重复建立新的 Java 桥接和连接池

#### Scenario: 配置变更后重建共享客户端
- **WHEN** `dm_update_config()` 成功更新数据库配置
- **THEN** 系统应关闭当前共享 `DmClient`
- **AND** 清空依赖旧配置的运行时状态
- **AND** 后续调用应基于新配置重新创建共享客户端

#### Scenario: 连接测试读取统一查询结果
- **WHEN** `dm_connect()` 执行测试查询 `SELECT 1 AS test_value FROM DUAL`
- **THEN** 工具 MUST 从统一的 `{columns, rows}` 结果中读取首行
- **AND** 在测试查询成功时返回明确的连接成功结果，而不是因为结果包装方式报错
