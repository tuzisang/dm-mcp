# 可配置的重试策略规范

## ADDED Requirements

### Requirement: 可配置的重试次数和延迟

系统 SHALL 支持通过配置文件和代码配置重试次数和延迟时间。

#### Scenario: 从配置文件读取重试参数
- **WHEN** `dm_config.json` 包含 `max_retries` 和 `retry_delay` 参数
- **THEN** 系统应使用这些值覆盖默认值
- **AND** 验证 `max_retries` 范围（0-5 次）
- **AND** 验证 `retry_delay` 范围（0-60 秒）

#### Scenario: 代码中指定重试参数
- **WHEN** 调用 `DmClient` 构造函数时传入 `retry_attempts` 和 `retry_delay` 参数
- **THEN** 系统应使用该值覆盖配置文件和默认值

#### Scenario: 默认重试参数
- **WHEN** 未指定重试参数
- **THEN** 系统应使用默认值：
  - `max_retries`: 1 次
  - `retry_delay`: 1 秒

### Requirement: 重试策略执行

系统 SHALL 在查询失败时按照配置的重试策略执行重试。

#### Scenario: 首次执行失败
- **WHEN** 查询执行失败（抛出异常）
- **AND** 剩余重试次数 > 0
- **THEN** 系统应等待 `retry_delay` 秒
- **AND** 减少剩余重试次数
- **AND** 重新执行查询

#### Scenario: 重试成功
- **WHEN** 重试查询成功执行
- **THEN** 系统应返回查询结果
- **AND** 记录重试成功事件到日志（INFO 级别）
- **AND** 日志应包含重试次数和总耗时

#### Scenario: 重试耗尽
- **WHEN** 所有重试次数用尽仍失败
- **THEN** 系统应抛出最后一次的异常
- **AND** 记录重试耗尽事件到日志（WARN 级别）
- **AND** 日志应包含总重试次数和总耗时

#### Scenario: 禁用重试
- **WHEN** `max_retries` 配置为 0
- **THEN** 系统应在首次失败时直接抛出异常
- **AND** 不进行任何重试

### Requirement: 可重试异常判断

系统 SHALL 只对特定类型的异常执行重试，避免无意义的重试。

#### Scenario: 可重试异常
- **WHEN** 抛出以下异常类型：
  - `JavaBridgeError`（Java 进程通信错误）
  - `TimeoutError`（I/O 或查询超时）
  - `ConnectionError`（网络连接错误）
- **THEN** 系统应执行重试策略

#### Scenario: 不可重试异常
- **WHEN** 抛出以下异常类型：
  - `ValueError`（参数错误）
  - `PermissionError`（权限错误）
  - `SQLSecurityError`（SQL 安全错误）
- **THEN** 系统应直接抛出异常
- **AND** 不执行重试

#### Scenario: 未知异常类型
- **WHEN** 抛出未知的异常类型
- **THEN** 系统应记录警告日志
- **AND** 按可重试异常处理（保守策略）

### Requirement: 指数退避重试（可选）

系统 SHALL 支持指数退避算法，避免频繁重试对服务器造成压力。

#### Scenario: 启用指数退避
- **WHEN** 配置 `retry_backoff="exponential"`
- **THEN** 每次重试延迟应按公式计算：`retry_delay * (2 ** retry_count)`
- **AND** 最大延迟不超过 30 秒

#### Scenario: 指数退避延迟计算
- **WHEN** `retry_delay=1` 秒，第 1 次重试
- **THEN** 延迟应为 1 秒（`1 * 2^0`）
- **WHEN** 第 2 次重试
- **THEN** 延迟应为 2 秒（`1 * 2^1`）
- **WHEN** 第 3 次重试
- **THEN** 延迟应为 4 秒（`1 * 2^2`）

#### Scenario: 线性退避（默认）
- **WHEN** 未配置退避策略或配置为 `retry_backoff="linear"`
- **THEN** 每次重试延迟应固定为 `retry_delay`

### Requirement: 重试事件日志记录

系统 SHALL 详细记录所有重试事件以便诊断。

#### Scenario: 记录重试开始
- **WHEN** 开始重试查询
- **THEN** 系统应记录以下信息：
  - 当前重试次数（如 "Retry 1/3"）
  - 失败原因（异常类型和消息）
  - 即将等待的延迟时间

#### Scenario: 记录重试成功
- **WHEN** 重试成功
- **THEN** 系统应记录以下信息：
  - 总重试次数
  - 总耗时（包括延迟时间）
  - 最终查询耗时

#### Scenario: 记录重试失败
- **WHEN** 所有重试失败
- **THEN** 系统应记录以下信息：
  - 总重试次数
  - 总耗时
  - 所有失败的异常堆栈（仅最后一次完整堆栈）

### Requirement: 重试状态追踪

系统 SHALL 追踪查询的重试状态，便于监控和调试。

#### Scenario: 查询结果包含重试信息
- **WHEN** 查询成功执行（可能经过重试）
- **THEN** 返回结果的 `metadata` 中应包含：
  - `retry_count`: 实际重试次数
  - `total_time`: 总耗时（秒）

#### Scenario: 查询失败不包含重试信息
- **WHEN** 查询失败并抛出异常
- **THEN** 异常对象应包含 `retry_count` 属性
- **AND** 可通过日志获取总重试次数
