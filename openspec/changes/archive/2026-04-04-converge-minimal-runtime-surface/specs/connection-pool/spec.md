## MODIFIED Requirements

### Requirement: 使用 HikariCP 管理数据库连接池

系统 SHALL 继续使用 HikariCP 作为 Java 桥接内部的连接复用实现，并在 MCP 进程生命周期内复用同一连接池以服务短时间频繁调用。

#### Scenario: 首次调用时创建连接池
- **WHEN** MCP 进程首次初始化共享 Java 桥接
- **THEN** 系统应初始化 HikariCP 数据源
- **AND** 后续短时间内的数据库工具调用应复用该数据源

#### Scenario: 进程退出或显式重置时释放连接池
- **WHEN** Python 端关闭共享 Java 桥接（例如进程退出或配置变更）
- **THEN** Java 端应关闭 HikariCP 数据源
- **AND** 释放所有连接池资源

### Requirement: 连接池参数配置

系统 SHALL 将连接池参数收敛为实现内固定默认值，而不是对外暴露运行时调优表面。

#### Scenario: 使用固定连接池默认值
- **WHEN** Java 桥接初始化 HikariCP
- **THEN** 系统应应用仓库内定义的最小必要默认值
- **AND** 调用方不需要通过配置文件或工具显式传入连接池调优参数

## REMOVED Requirements

### Requirement: 连接健康检查
**Reason**: 连接池复用仍然保留，但单独的池级健康检查承诺不是当前最小闭环所必需。
**Migration**: 无；依赖 HikariCP 默认连接管理和共享桥接重建。

### Requirement: 连接池统计信息
**Reason**: 当前阶段不暴露连接池观测接口，避免引入无消费方的扩展点和协议分支。
**Migration**: 无；如未来确有监控需求，再单独设计观测能力。
