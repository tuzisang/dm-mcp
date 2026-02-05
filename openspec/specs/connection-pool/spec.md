# 连接池规范

## ADDED Requirements

### Requirement: 使用 HikariCP 管理数据库连接池

系统 SHALL 使用 HikariCP 作为数据库连接池实现，提供高性能的连接复用。

#### Scenario: 连接池初始化
- **WHEN** 系统启动时
- **THEN** 应创建 HikariCP 数据源
- **AND** 根据配置初始化最小和最大连接数

#### Scenario: 连接复用
- **WHEN** 多个查询并发执行
- **THEN** 系统应从连接池获取可用连接
- **AND** 查询完成后将连接返回池中
- **AND** 不为每次查询创建新连接

### Requirement: 连接池参数配置

系统 SHALL 支持通过配置文件自定义 HikariCP 连接池参数。

#### Scenario: 最小/最大连接数配置
- **WHEN** 配置文件定义了 `pool_min_connections` 和 `pool_max_connections`
- **THEN** 系统应使用这些值配置连接池大小
- **AND** 验证 min <= max

#### Scenario: 连接超时配置
- **WHEN** 配置文件定义了 `pool_connection_timeout`
- **THEN** 系统应在获取连接超时时抛出异常

#### Scenario: 空闲连接超时
- **WHEN** 连接空闲时间超过 `pool_idle_timeout`
- **THEN** 系统应关闭并移除该连接

### Requirement: 连接健康检查

系统 SHALL 定期检查连接池中连接的健康状态，移除无效连接。

#### Scenario: 健康检查间隔
- **WHEN** 配置文件定义了 `pool_health_check_interval`
- **THEN** 系统应按此间隔执行连接健康检查

#### Scenario: 无效连接移除
- **WHEN** 健康检查发现连接已失效
- **THEN** 系统应从池中移除该连接
- **AND** 创建新连接维持池大小

### Requirement: 连接池统计信息

系统 SHALL 提供连接池运行状态统计，便于监控和调优。

#### Scenario: 获取池状态
- **WHEN** 调用连接池状态查询方法
- **THEN** 系统应返回当前活跃连接数、空闲连接数、等待线程数等信息
