## Context

当前启动链路假设 `db/DmJdbcBridge.class` 已经存在，因此 `db/java_bridge.py` 直接执行 `java -cp ... DmJdbcBridge`。仓库中却只跟踪 `db/DmJdbcBridge.java`，README 也把 `javac -cp 'lib/*' db/DmJdbcBridge.java` 作为人工前提。这使得一个纯本地引导问题被伪装成数据库连接失败：当 class 文件缺失时，Java 会在守护进程尚未 ready 前就报 `ClassNotFoundException` 退出，而 `db/client.py` 又在共享 client 初始化失败后统一抛出“无法建立数据库连接”。

这次变更横跨桥接启动层、共享 client 错误边界和开发文档，属于典型的跨模块修复，适合先明确技术决策再编码。

## Goals / Non-Goals

**Goals:**
- 让 Java 桥接在缺少或过期 class 文件时可以自检并自动编译。
- 让桥接启动失败的真实根因能够稳定到达 `get_shared_client()` 和 `dm_connect()` 调用方。
- 用单元测试锁定“触发自动编译”和“错误不再被吞掉”的行为。
- 更新 README，使启动前提与真实运行模型一致。

**Non-Goals:**
- 不修改 `DmJdbcBridge.java` 的 SQL 执行协议和计划查询逻辑。
- 不在本次变更中引入后台重试、自动重启或更复杂的健康检查状态机。
- 不处理桥接启动成功之后的真实数据库网络、账号或 SQL 问题。

## Decisions

### 决策 1：由 Python 桥接层负责主类自检和惰性编译

在真正启动 `java` 之前，由 `db/java_bridge.py` 比较 `DmJdbcBridge.java` 与 `DmJdbcBridge.class` 的存在性和修改时间。只有在 class 缺失或源文件更新时，才尝试调用 `javac`。这样可以保持仓库不提交编译产物，同时消除“必须先手工编译”的隐藏前提。

备选方案：
- 始终要求手工执行 `javac`。否决原因：问题正是因为这个隐式前提没有在运行时被验证。
- 把 `.class` 文件提交进仓库。否决原因：二进制产物容易过期，也会增加跨版本 Java 兼容和审查噪声。

### 决策 2：编译器发现顺序优先复用 `JAVA_HOME`，再回退到 PATH

启动链路已经会定位 `java` 可执行文件，因此编译时优先检查同一 `JAVA_HOME/bin/javac`，保证 `java`/`javac` 来自同一安装。若该路径不存在，再回退到 PATH 中的 `javac`。两者都不存在时，直接返回明确错误，提示当前环境缺少 JDK 能力。

### 决策 3：保留 `connect()` 的布尔接口，但新增显式的连接保证路径

现有 `connect()` 已被单元测试和可能的调用点视为布尔探针，不适合直接改成抛异常。修复方式是在 `DmClient` 内增加一个显式的“确保桥接可用”路径，供 `get_shared_client()` 使用；`connect()` 仍可基于该路径降级为 `True/False`，以保留兼容性。这样既能透传根因，也不会破坏现有布尔语义。

### 决策 4：共享 client 重建后直接传播第二次失败

`get_shared_client()` 仍可保留“若现有共享 client 失效则关闭并重建一次”的语义，但第二次失败不得再包装成通用文案，而应直接把 `DatabaseConnectionError` 抛出。这样既保留恢复路径，也不会吞掉真实根因。

## Risks / Trade-offs

- [风险] 本地只有 JRE 没有 JDK，自动编译会失败。 -> 缓解：错误文案明确指出缺少 `javac`，README 同步更新为首次启动需要可用 JDK。
- [风险] 多线程下可能重复触发编译。 -> 缓解：在桥接模块内使用进程内锁保护编译段，并在进入锁后再次检查产物状态。
- [风险] 启动错误文案变长，部分调用方日志更冗长。 -> 缓解：保留错误前缀语义，只扩展根因内容，不改变异常类型。

## Migration Plan

1. 在 `db/java_bridge.py` 增加主类产物路径、编译器发现和按需编译逻辑。
2. 调整 Java 启动命令与错误读取逻辑，保留启动前和启动时的真实失败输出。
3. 在 `db/client.py` 增加显式连接保证路径，并修改共享 client 初始化/重建逻辑。
4. 增加单元测试并更新 README 中的启动说明。

## Open Questions

- 当前不考虑把自动编译结果缓存到其他目录；若后续引入多主类或打包流程，再评估是否迁移到专门 build 目录。
