# 动态连接池配置管理规范

## ADDED Requirements

### Requirement: 连接池配置参数

系统 SHALL 支持通过配置文件和代码配置 HikariCP 连接池参数。

#### Scenario: 从配置文件读取连接池参数
- **WHEN** `dm_config.json` 包含连接池配置参数
- **THEN** 系统应读取并应用以下参数：
  - `pool_min_connections`: 最小空闲连接数（默认 2）
  - `pool_max_connections`: 最大连接数（默认 20）
  - `pool_connection_timeout`: 连接获取超时（毫秒，默认 60000）
  - `pool_idle_timeout`: 空闲连接超时（秒，默认 300）
  - `pool_max_lifetime`: 连接最大生命周期（秒，默认 1800）

#### Scenario: 验证连接池参数范围
- **WHEN** 读取连接池配置参数
- **THEN** 系统应验证以下范围：
  - `pool_min_connections`: 1-10
  - `pool_max_connections`: 5-100
  - `pool_connection_timeout`: 5000-300000（毫秒）
  - `pool_idle_timeout`: 60-3600（秒）
  - `pool_max_lifetime`: 300-7200（秒）
- **AND** 无效值应回退到默认值

#### Scenario: 代码中指定连接池参数
- **WHEN** 调用 `JavaBridgeClient` 构造函数时传入连接池配置
- **THEN** 系统应使用该值覆盖配置文件和默认值

### Requirement: Java 端连接池配置

Java 守护进程 SHALL 根据环境变量配置 HikariCP 连接池。

#### Scenario: 读取环境变量
- **WHEN** Java 守护进程初始化 HikariCP
- **THEN** 应从以下环境变量读取配置：
  - `DM_POOL_MIN`: 最小空闲连接数
  - `DM_POOL_MAX`: 最大连接数
  - `DM_POOL_TIMEOUT`: 连接获取超时（毫秒）
  - `DM_POOL_IDLE_TIMEOUT`: 空闲连接超时（毫秒）
  - `DM_POOL_MAX_LIFETIME`: 连接最大生命周期（毫秒）

#### Scenario: 应用 HikariCP 配置
- **WHEN** 构建 `HikariConfig` 对象
- **THEN** 应设置以下参数：
  - `setMinimumIdle(DM_POOL_MIN)`
  - `setMaximumPoolSize(DM_POOL_MAX)`
  - `setConnectionTimeout(DM_POOL_TIMEOUT)`
  - `setIdleTimeout(DM_POOL_IDLE_TIMEOUT)`
  - `setMaximumLifetime(DM_POOL_MAX_LIFETIME)`

#### Scenario: 环境变量未设置
- **WHEN** 某个环境变量未设置
- **THEN** 应使用以下默认值：
  - `DM_POOL_MIN`: 2
  - `DM_POOL_MAX`: 20
  - `DM_POOL_TIMEOUT`: 60000（60 秒）
  - `DM_POOL_IDLE_TIMEOUT`: 300000（5 分钟）
  - `DM_POOL_MAX_LIFETIME`: 1800000（30 分钟）

### Requirement: 连接池状态监控

系统 SHALL 提供查询 HikariCP 连接池状态的接口。

#### Scenario: 查询连接池状态
- **WHEN** 调用 `get_pool_status()` 方法
- **THEN** 系统应返回包含以下信息的字典：
  - `active_connections`: 活跃连接数
  - `idle_connections`: 空闲连接数
  - `total_connections`: 总连接数
  - `waiting_threads`: 等待连接的线程数
  - `max_pool_size`: 最大连接池大小
  - `min_idle`: 最小空闲连接数

#### Scenario: Java 端状态查询
- **WHEN** Python 端请求连接池状态
- **THEN** 应发送特殊请求：`{"type": "pool_status"}`
- **AND** Java 端应返回 HikariCP 的 `HikariPoolMXBean` 数据

### Requirement: 连接池健康检查

系统 SHALL 定期检查连接池健康状态，检测潜在问题。

#### Scenario: 连接泄漏检测
- **WHEN** 活跃连接数连续 5 分钟超过最大连接数的 90%
- **THEN** 系统应记录警告日志
- **AND** 日志应包含可能的连接泄漏提示

#### Scenario: 连接等待时间过长
- **WHEN** `waiting_threads` 大于 0 超过 30 秒
- **THEN** 系统应记录警告日志
- **AND** 建议增加 `pool_max_connections`

#### Scenario: 空闲连接过多
- **WHEN** 空闲连接数超过 `max_pool_size` 的 80%
- **THEN** 系统应记录信息日志
- **AND** 建议减少 `pool_min_connections` 以节省资源

### Requirement: 连接池配置动态更新

系统 SHALL 支持运行时更新连接池配置（需重启 Java 守护进程）。

#### Scenario: 更新连接池配置
- **WHEN** 调用 `update_pool_config()` 方法
- **THEN** 系统应执行以下步骤：
  1. 验证新配置参数范围
  2. 保存到 `dm_config.json`
  3. 关闭现有 Java 守护进程
  4. 重新启动 Java 守护进程（使用新配置）
  5. 验证新配置生效

#### Scenario: 配置更新失败
- **WHEN** 新配置参数无效或 Java 守护进程重启失败
- **THEN** 系统应抛出 `ValueError` 异常
- **AND** 保持旧配置继续运行

#### Scenario: 配置热更新限制
- **WHEN** 尝试在不重启 Java 守护进程的情况下更新配置
- **THEN** 系统应返回不支持错误
- **AND** 说明需要重启 Java 守护进程才能生效

### Requirement: 连接池性能优化建议

系统 SHALL 根据运行时监控数据提供连接池配置优化建议。

#### Scenario: 检测连接池不足
- **WHEN** 监控数据显示频繁的连接等待（>10% 请求需等待）
- **THEN** 系统应记录优化建议日志
- **AND** 建议增加 `pool_max_connections`

#### Scenario: 检测连接池过大
- **WHEN** 监控数据显示连接池利用率 < 20%
- **THEN** 系统应记录优化建议日志
- **AND** 建议减少 `pool_max_connections` 以节省资源

#### Scenario: 检测连接超时
- **WHEN** 监控数据显示连接获取超时率 > 5%
- **THEN** 系统应记录优化建议日志
- **AND** 建议增加 `pool_connection_timeout` 或 `pool_max_connections`
