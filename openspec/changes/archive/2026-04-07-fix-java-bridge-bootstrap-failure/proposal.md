## Why

当前 DM MCP 在数据库连接真正发生之前，就已经失败在本地 Java 桥接进程启动阶段。`db/java_bridge.py` 直接执行 `java -cp ... DmJdbcBridge`，但仓库运行时只保证存在 `db/DmJdbcBridge.java`，并不保证 `DmJdbcBridge.class` 已经被预编译，因此会触发 `ClassNotFoundException: DmJdbcBridge`。上层 `get_shared_client()` 又把这类启动错误统一包装成“无法建立数据库连接”，导致排障方向被误导成网络或账号问题。

这个问题同时破坏了两层契约：桥接层缺少对 Java 主类可执行性的启动自检，高层数据库客户端也没有保留底层失败的真实原因。如果不先修复这两层，后续任何 `dm_connect()` 结果都不具备诊断价值。

## What Changes

- 为 Java 桥接启动链路增加本地主类可执行性检查，在缺少 `DmJdbcBridge.class` 或编译产物过期时自动尝试编译 `db/DmJdbcBridge.java`。
- 在自动编译不可用或编译失败时返回明确的桥接启动错误，包含 `javac`/`java` 的真实失败信息，而不是泛化成数据库连接失败。
- 调整共享数据库客户端的连接错误传播逻辑，保留 Java 桥接启动失败的根因，避免把 `ClassNotFoundException`、编译失败或守护进程启动错误吞掉。
- 补充针对桥接引导和错误传播的回归测试，覆盖“缺少 class 文件时可自恢复”和“启动失败时向上层暴露真实原因”。

## Capabilities

### New Capabilities
<!-- None -->

### Modified Capabilities
- `java-bridge`: 扩展桥接守护进程启动要求，要求在启动前验证 `DmJdbcBridge` 主类可用，并在必要时自动编译或返回明确的引导失败原因。
- `database-client`: 调整共享 client 的连接失败边界，要求保留桥接启动阶段的真实异常，而不是统一吞成“无法建立数据库连接”。

## Impact

- 受影响代码：
  - `db/java_bridge.py`
  - `db/client.py`
  - `README.md`
  - 相关测试
- 受影响行为：
  - 首次启动不再依赖手工预编译 `DmJdbcBridge.class`
  - `dm_connect()` / `get_shared_client()` 在桥接启动失败时应暴露真实根因
  - 只有在桥接启动成功后，数据库网络或账号问题才会成为下一层排查对象
- 依赖与风险：
  - 依赖本地可用的 `javac`；如果 JRE 存在但 JDK 缺失，应返回明确提示
  - 自动编译需要避免无谓重复执行，并在并发下保持启动路径稳定
