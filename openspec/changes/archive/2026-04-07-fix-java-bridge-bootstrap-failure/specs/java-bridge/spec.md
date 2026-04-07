## ADDED Requirements

### Requirement: 守护进程启动准备

系统 SHALL 在启动 Java 守护进程前验证 `DmJdbcBridge` 主类可执行，并在本地编译产物缺失或过期时自动完成构建准备。

#### Scenario: 缺少主类编译产物时自动编译
- **WHEN** Python 端准备启动 `DmJdbcBridge`
- **AND** 本地不存在 `db/DmJdbcBridge.class`
- **THEN** 系统 MUST 在启动 `java` 进程前尝试执行 `javac` 编译 `db/DmJdbcBridge.java`
- **AND** 编译成功后再继续启动守护进程

#### Scenario: Java 源文件更新后自动重编译
- **WHEN** `db/DmJdbcBridge.java` 的修改时间晚于现有 `db/DmJdbcBridge.class`
- **THEN** 系统 MUST 在下一次启动前重新编译主类
- **AND** 不得继续使用过期的 class 产物

#### Scenario: 缺少编译器时返回明确错误
- **WHEN** 系统需要编译 `DmJdbcBridge.java`
- **AND** 本地不可用 `javac`
- **THEN** 系统 MUST 终止本次启动
- **AND** 返回明确的桥接启动错误，说明需要可用的 JDK/`javac`

#### Scenario: 编译失败时保留真实输出
- **WHEN** `javac` 编译 `DmJdbcBridge.java` 失败
- **THEN** 系统 MUST 终止本次启动
- **AND** 返回的桥接启动错误 MUST 包含 `javac` 的 stderr 或 stdout 细节，便于定位缺失依赖或语法错误

## MODIFIED Requirements

### Requirement: 守护进程超时控制

系统 SHALL 为启动、读取和查询执行设置有界超时，并在启动阶段保留可诊断的失败原因，而不是把启动错误降级为无上下文的超时或空错误。

#### Scenario: I/O 读取超时
- **WHEN** 从 Java 守护进程 stdout 读取数据
- **AND** 在固定 I/O 超时内未收到完整响应
- **THEN** 系统应终止当前读取
- **AND** 返回明确的桥接超时错误

#### Scenario: 查询执行超时
- **WHEN** Java 端查询执行时间超过 `query_timeout`
- **THEN** Java 端应取消查询
- **AND** 返回错误响应：`{"error": true, "message": "Query timeout"}`

#### Scenario: 启动超时
- **WHEN** Java 守护进程启动超过 `startup_timeout` 未就绪
- **THEN** 系统应放弃启动
- **AND** 抛出 `JavaBridgeError` 异常

#### Scenario: 启动阶段进程直接失败
- **WHEN** Java 守护进程在发出 ready 消息前异常退出
- **THEN** 系统 MUST 读取并返回启动阶段的真实失败信息
- **AND** 错误内容不得退化成仅有“启动失败”或“无法建立数据库连接”的泛化描述
