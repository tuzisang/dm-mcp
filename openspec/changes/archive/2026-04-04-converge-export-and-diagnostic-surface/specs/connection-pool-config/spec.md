## MODIFIED Requirements

### Requirement: Java 端连接池配置

Java 守护进程 SHALL 根据固定的实现内默认值配置 HikariCP 连接池，而不是继续暴露外部配置面。

#### Scenario: 使用固定默认值
- **WHEN** Java 守护进程初始化 HikariCP
- **THEN** 应使用实现内约定的默认值：
  - 最小空闲连接数：2
  - 最大连接数：20
  - 连接获取超时：60000 毫秒
- **AND** 这些默认值由运行时内部设置，不通过 `dm_config.json` 暴露

#### Scenario: 应用 HikariCP 配置
- **WHEN** 构建 `HikariConfig` 对象
- **THEN** 应设置以下参数：
  - `setMinimumIdle(2)` 或等价固定值
  - `setMaximumPoolSize(20)` 或等价固定值
  - `setConnectionTimeout(60000)` 或等价固定值

## REMOVED Requirements

### Requirement: 连接池配置参数
**Reason**: 当前阶段不再对外暴露连接池配置项，避免保留无消费方的配置面。
**Migration**: 使用实现内固定默认值；如未来确有需要，再以独立变更重新引入。

### Requirement: 连接池状态监控
**Reason**: 连接池状态查询协议与监控接口已移除。
**Migration**: 使用外部监控或数据库侧观测，而不是内置 `pool_status` 路径。

### Requirement: 连接池健康检查
**Reason**: 当前 MCP 不再承载连接池健康分析、告警与建议。
**Migration**: 无；现阶段不提供等价内置替代。

### Requirement: 连接池配置动态更新
**Reason**: 当前阶段仅支持数据库连接参数更新，不支持动态调优连接池。
**Migration**: 使用固定连接池默认值；配置更新后只重建共享运行时，不调整池参数。

### Requirement: 连接池性能优化建议
**Reason**: 运行时优化建议属于未来能力，不属于当前最小闭环。
**Migration**: 无；如后续需要，应作为独立能力重新设计。
