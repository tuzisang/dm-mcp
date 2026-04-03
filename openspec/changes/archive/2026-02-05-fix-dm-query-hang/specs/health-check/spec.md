# Java 桥接进程健康检查规范

## MODIFIED Requirements

### Requirement: 守护进程健康检查

系统 SHALL 定期检查 Java 守护进程的健康状态，包括心跳检测和进程存活检查。

#### Scenario: 进程存活检查
- **WHEN** 执行数据库操作前
- **THEN** 系统应检查 Java 进程是否仍在运行（使用 `poll()`）
- **AND** 如果进程已退出，应抛出 `JavaBridgeError` 异常
- **AND** 尝试自动重启守护进程

#### Scenario: 心跳消息接收
- **WHEN** Java 守护进程发送心跳消息
- **THEN** 系统应更新 `last_heartbeat` 时间戳
- **AND** 心跳消息格式应为 `{"type": "heartbeat", "timestamp": <ms>}`

#### Scenario: 心跳健康检查
- **WHEN** 调用 `is_healthy()` 方法
- **THEN** 系统应检查当前时间与 `last_heartbeat` 的时间差
- **AND** 如果时间差超过 `health_check_interval * 2`，返回 `False`
- **AND** 否则返回 `True`

#### Scenario: 检测到心跳缺失
- **WHEN** 心跳缺失超过阈值（默认 30 秒）
- **THEN** 系统应标记 Java 进程为不健康
- **AND** 关闭并重启 Java 守护进程
- **AND** 记录心跳缺失事件到日志

#### Scenario: 配置心跳间隔
- **WHEN** 管理员设置 `health_check_interval` 配置参数
- **THEN** 系统应使用该值作为心跳检查间隔
- **AND** 有效范围为 5-60 秒
- **AND** 无效值应回退到默认值 15 秒

### Requirement: Java 端心跳发送

Java 守护进程 SHALL 定期发送心跳消息以证明其存活状态。

#### Scenario: 启动心跳定时器
- **WHEN** Java 守护进程启动完成
- **THEN** 应创建 `ScheduledExecutorService`
- **AND** 以固定间隔（默认 15 秒）发送心跳消息

#### Scenario: 发送心跳消息
- **WHEN** 心跳定时器触发
- **THEN** 应通过 stdout 发送心跳消息
- **AND** 消息格式为 `{"type": "heartbeat", "timestamp": 1234567890}`
- **AND** 消息后应刷新输出缓冲区（flush）

#### Scenario: 心跳线程独立运行
- **WHEN** 主线程正在处理查询请求
- **THEN** 心跳线程应继续独立发送心跳
- **AND** 不受查询执行时间影响

#### Scenario: 心跳线程异常处理
- **WHEN** 心跳发送失败（如 stdout 关闭）
- **THEN** 应记录错误日志
- **AND** 不影响主线程运行
- **AND** 心跳线程继续尝试发送

### Requirement: 自动重启不健康的进程

系统 SHALL 在检测到 Java 守护进程不健康时自动重启。

#### Scenario: 触发重启条件
- **WHEN** 满足以下任一条件
  - 进程已退出（`poll()` 返回非 None）
  - 心跳缺失超过阈值
  - I/O 操作超时
- **THEN** 系统应判定 Java 进程不健康

#### Scenario: 重启流程
- **WHEN** 系统决定重启 Java 守护进程
- **THEN** 应按以下顺序执行：
  1. 调用 `shutdown()` 关闭现有进程
  2. 等待进程完全退出（最多 5 秒）
  3. 调用 `_start_daemon()` 启动新进程
  4. 等待新进程就绪（`_wait_for_ready()`）
  5. 重试当前查询一次

#### Scenario: 重启成功
- **WHEN** Java 守护进程重启成功
- **THEN** 系统应记录重启事件到日志（INFO 级别）
- **AND** 继续处理查询请求

#### Scenario: 重启失败
- **WHEN** Java 守护进程重启失败（如启动超时）
- **THEN** 系统应抛出 `JavaBridgeError` 异常
- **AND** 记录失败详情到日志（ERROR 级别）
- **AND** 不再尝试重启

### Requirement: 防止连续重启

系统 SHALL 限制连续重启次数，防止无限重启循环。

#### Scenario: 记录重启历史
- **WHEN** Java 守护进程重启
- **THEN** 系统应记录重启时间戳
- **AND** 维护最近 5 分钟内的重启次数

#### Scenario: 达到重启限制
- **WHEN** 5 分钟内重启次数达到 3 次
- **THEN** 系统应停止自动重启
- **AND** 抛出 `JavaBridgeError` 异常
- **AND** 错误消息应包含 "too many restarts"

#### Scenario: 重置重启计数
- **WHEN** Java 守护进程稳定运行超过 5 分钟
- **THEN** 系统应重置重启计数器

### Requirement: 健康状态查询接口

系统 SHALL 提供查询 Java 守护进程健康状态的接口。

#### Scenario: 查询健康状态
- **WHEN** 调用 `get_health_status()` 方法
- **THEN** 系统应返回包含以下信息的字典：
  - `is_healthy`: 布尔值，表示进程是否健康
  - `last_heartbeat`: 时间戳，最后一次心跳时间
  - `uptime`: 数字，进程运行时长（秒）
  - `restart_count`: 数字，5 分钟内重启次数

#### Scenario: 进程未启动时查询
- **WHEN** Java 守护进程尚未启动
- **THEN** `get_health_status()` 应返回 `is_healthy=False`
- **AND** `last_heartbeat=None`
