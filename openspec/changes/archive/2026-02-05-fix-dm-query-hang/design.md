## Context

### 当前状态

DM MCP 服务器使用 Java 守护进程（`DmJdbcBridge`）桥接达梦数据库，通过 stdin/stdout 进行 JSON 通信。当前架构存在以下问题：

1. **阻塞式 I/O**: `db/java_bridge.py:_read_response()` 使用阻塞式 `stdout.readline()`，在 Java 进程存活但无响应时永久挂起
2. **无健康检查**: 无法区分 Java 进程假死与正常执行长查询
3. **重试延迟过长**: 默认重试 3 次，每次间隔 5 秒，配合 120 秒查询超时，最长可达 6 分钟
4. **连接池配置保守**: HikariCP 最大连接数 10，连接超时 30 秒，高并发时容易耗尽

### 技术约束

- **通信协议**: stdin/stdout JSON 协议，保持兼容性
- **依赖**: 仅使用 Python 标准库（`threading`, `queue`），无外部依赖
- **向后兼容**: 配置文件格式向后兼容，新参数使用默认值
- **Java 环境**: Java 8+，使用 HikariCP 连接池

## Goals / Non-Goals

**Goals:**
- 在 30-60 秒内检测并恢复假死状态（而非 6 分钟）
- 自动重启假死的 Java 守护进程并重试查询
- 提供可配置的超时和重试策略
- 添加监控指标便于诊断
- 保持向后兼容性

**Non-Goals:**
- 更换通信协议（如使用 Unix socket 或 HTTP）
- 引入新的外部依赖（如 `asyncio`）
- 修改 MCP 工具接口（`dm_query` 等）
- 实现分布式追踪或完整的监控系统

## Decisions

### 1. 超时控制机制：使用 `threading.Timer` + `queue.Queue`

**决策**: 使用 `threading.Timer` 在独立线程中执行阻塞式 `readline()`，通过 `queue.Queue` 传递结果，主线程等待超时。

**理由**:
- ✅ 仅依赖标准库，无新增依赖
- ✅ 不改变现有 I/O 模型，保持兼容性
- ✅ 实现简单，代码改动小

**替代方案**:
- ❌ 使用 `select`/`poll`: 不适用于普通文件的 stdout（管道）
- ❌ 使用 `asyncio`: 需要大幅重构现有同步代码
- ❌ 使用 `signal.alarm()`: 在多线程环境下不可靠

**实现**:
```python
def _read_line_with_timeout(timeout: int) -> Optional[str]:
    """从 stdout 读取一行，支持超时"""
    result_queue = queue.Queue()

    def reader():
        try:
            line = self.process.stdout.readline()
            result_queue.put(("success", line))
        except Exception as e:
            result_queue.put(("error", e))

    thread = threading.Thread(target=reader, daemon=True)
    thread.start()
    thread.join(timeout=timeout)

    if thread.is_alive():
        # 超时：线程仍在运行
        return None
    else:
        # 线程结束，获取结果
        if not result_queue.empty():
            status, value = result_queue.get()
            return value if status == "success" else None
    return None
```

### 2. 心跳检测：Java 端定期发送心跳，Python 端监控

**决策**: Java 守护进程每 15 秒发送一次心跳消息，Python 端通过 `last_heartbeat` 时间戳判断进程健康状态。

**理由**:
- ✅ 轻量级，仅增加一条 JSON 消息
- ✅ 不干扰正常查询流程
- ✅ 可配置心跳间隔

**实现**:
- **Java 端** (`DmJdbcBridge.java`):
  - 新增 `ScheduledExecutorService` 定时发送心跳
  - 心跳消息: `{"type": "heartbeat", "timestamp": <ms>}`
  - 在主循环外独立执行，不阻塞查询处理

- **Python 端** (`java_bridge.py`):
  - 新增 `last_heartbeat: float` 时间戳
  - `_read_response()` 中识别心跳消息，更新时间戳
  - 新增 `is_healthy()` 方法检查心跳

### 3. 自动恢复策略：超时后重启 Java 进程

**决策**: 检测到超时或心跳缺失时，标记 Java 进程为不健康，自动重启并重试当前查询一次。

**理由**:
- ✅ 无缝恢复，用户无感知
- ✅ 清理可能的资源泄漏（内存、连接）
- ✅ 避免手动干预

**流程**:
```
1. 查询超时或心跳缺失
2. shutdown() 关闭 Java 进程
3. _start_daemon() 重新启动
4. 重试当前查询一次
5. 如仍失败，抛出异常
```

**风险控制**:
- 限制连续重启次数（如最多 3 次），防止无限重启
- 记录重启事件到日志，便于诊断

### 4. 重试机制优化：减少重试次数和延迟

**决策**: 将 `retry_attempts` 从 3 降至 1，`retry_delay` 从 5 秒降至 1 秒。

**理由**:
- ✅ 超时机制已保证单次查询不会永久阻塞
- ✅ 自动恢复机制处理进程假死，无需多次重试
- ✅ 缩短总体响应时间（6 分钟 → 30-60 秒）

**影响**:
- 临时性网络故障恢复能力略降（但可接受）
- 长查询假死场景恢复时间大幅缩短

### 5. 连接池配置调整：增加最大连接数和超时时间

**决策**:
- `pool_max_connections`: 10 → 20
- `pool_connection_timeout`: 30000ms → 60000ms

**理由**:
- ✅ 降低连接获取失败概率
- ✅ 适应可能的并发查询场景
- ✅ 内存开销可接受（约 10MB）

**配置方式**:
- 环境变量传递给 Java 进程（现有机制）
- `dm_config.json` 中新增配置项
- HikariCP 启动时读取环境变量

### 6. 🔴 连接资源管理：确保异常场景下连接被正确释放

**决策**: 在假死、超时、主动断开等异常场景下，必须确保数据库连接被正确关闭，防止连接池耗尽。

**关键问题**:
- 当前 Java 端查询超时后，`Connection` 和 `Statement` 可能未关闭
- Python 端超时重启 Java 进程时，HikariCP 连接池可能未完全关闭
- 连接泄漏会累积，最终导致新请求无法获取连接

**实现方案**:

1. **Java 端查询超时时强制释放资源**:
   ```java
   // 使用 try-with-resources 确保自动关闭
   try (Connection conn = dataSource.getConnection()) {
       try (PreparedStatement stmt = conn.prepareStatement(sql)) {
           ResultSet rs = stmt.executeQuery();
           // 处理结果
       }  // stmt 自动关闭
   }  // conn 自动关闭
   ```

2. **Java 端添加超时中断机制**:
   - 使用 `Statement.setQueryTimeout()` 设置 JDBC 查询超时
   - 超时后 JDBC 驱动会自动取消查询并释放资源
   - 新增配置：`statement_timeout`（默认 120 秒）

3. **Python 端重启进程前确保 HikariCP 关闭**:
   ```python
   def shutdown(self):
       if self.process:
           try:
               # 1. 发送关闭信号
               self.process.stdin.write('{"type": "shutdown"}\n')
               self.process.stdin.flush()

               # 2. 等待进程优雅退出（最多 5 秒）
               self.process.wait(timeout=5)
           except:
               # 3. 强制终止
               self.process.kill()

           # 4. 确认进程已退出
           if self.process.poll() is None:
               raise JavaBridgeError("Failed to shutdown Java process")
   ```

4. **Java 端关闭钩子确保连接池关闭**:
   ```java
   private void shutdown() {
       if (dataSource != null) {
           dataSource.close();  // HikariCP 会关闭所有连接
       }
       if (executor != null) {
           executor.shutdownNow();  // 关闭心跳线程
       }
   }

   // 添加关闭钩子
   Runtime.getRuntime().addShutdownHook(new Thread(() -> {
       shutdown();
   }));
   ```

5. **连接泄漏检测和告警**:
   - 监控 `active_connections` 指标
   - 如果活跃连接数连续 5 分钟超过最大连接数的 90%，记录警告
   - 建议管理员检查是否存在查询超时未释放的场景

**验证方法**:
- 压力测试：并发执行 20 个查询，手动触发超时，验证连接池不会耗尽
- 监控 HikariCP 的 `active_connections` 指标，确认超时后连接数下降
- 检查日志，确认 Java 进程关闭时看到 "HikariCP pool is shutting down"

**风险缓解**:
- 即使个别连接泄漏，HikariCP 的 `maxLifetime`（30 分钟）会强制回收旧连接
- 连接池配置 `idleTimeout`（5 分钟）会清理空闲连接
- 定期重启 Java 守护进程（如每天一次）清理长期累积的资源

### 7. 配置管理：新增配置参数（向后兼容）

**决策**: 在 `db/config.py` 中新增配置参数，使用默认值保证向后兼容。

**新增配置**:
```python
DEFAULT_IO_TIMEOUT = 30  # I/O 操作超时（秒）
DEFAULT_HEALTH_CHECK_INTERVAL = 15  # 心跳间隔（秒）
DEFAULT_MAX_RETRIES = 1  # 最大重试次数
DEFAULT_RETRY_DELAY = 1  # 重试延迟（秒）
DEFAULT_POOL_MAX_CONNECTIONS = 20  # 最大连接数
DEFAULT_POOL_CONNECTION_TIMEOUT = 60000  # 连接超时（毫秒）
```

**兼容性**:
- 旧配置文件自动使用默认值
- 新配置文件可选覆盖

## Risks / Trade-offs

### 🔴 风险 1: 连接泄漏导致连接池耗尽

**风险**: 在假死、超时、主动断开等异常场景下，数据库连接可能未被正确关闭，导致连接池逐渐耗尽，新请求无法获取连接。

**严重性**: 🔴 **Critical** - 会导致系统完全无法处理查询请求

**缓解**:
- Java 端使用 try-with-resources 确保 Connection 和 Statement 自动关闭
- 配置 `Statement.setQueryTimeout()` 强制中断长时间运行的查询
- Python 端重启前先发送 `shutdown` 消息，确保 HikariCP 优雅关闭
- 注册 JVM 关闭钩子，即使进程崩溃也尝试关闭连接池
- 配置 HikariCP 连接泄漏检测（`setLeakDetectionThreshold(60000)`）
- 配置 `maxLifetime`（30 分钟）和 `idleTimeout`（5 分钟）强制回收旧连接
- 添加连接池监控，活跃连接数超过 90% 时发出告警

**验证**:
- 压力测试：并发 20 个查询，手动触发超时，验证连接池不耗尽
- 检查日志确认 Java 进程关闭时有 "HikariCP pool is shutting down" 消息
- 长时间运行测试（1 小时），监控 `active_connections` 不超过 `pool_max_connections`

### 风险 2: 多线程开销

**风险**: 为每次 I/O 创建新线程可能增加 CPU 开销。

**缓解**:
- 使用 daemon 线程，进程退出时自动清理
- 实测开销 < 1% CPU（待验证）
- 可选：使用线程池复用线程（优化阶段）

### 风险 2: 心跳消息丢失

**风险**: 管道缓冲区满时，心跳消息可能被延迟或丢失。

**缓解**:
- 心跳消息极小（~50 bytes），丢失概率低
- Python 端使用 `readline()` 阻塞读取，不会漏消息
- 配置合理的心跳间隔（15 秒），避免管道压力

### 风险 3: Java 进程重启导致连接池丢失

**风险**: 重启 Java 进程会清空 HikariCP 连接池，影响后续查询性能。

**缓解**:
- 仅在检测到假死时重启（低频事件）
- HikariCP 会自动重新建立连接
- 可选：保留上次查询结果缓存（优化阶段）

### 风险 4: 误判 Java 进程假死

**风险**: 长查询（如大数据量导出）可能被误判为假死。

**缓解**:
- I/O 超时与查询超时分离：
  - `io_timeout` (30s): 仅针对通信读取
  - `query_timeout` (120s): 针对 Java 端查询执行
- Java 端查询超时由 JDBC 控制，不受 Python 端影响
- 日志中明确区分超时类型

## Migration Plan

### 部署步骤

1. **代码部署**:
   - 更新 `db/java_bridge.py`（核心修复）
   - 更新 `db/DmJdbcBridge.java`（心跳支持）
   - 更新 `db/client.py` 和 `db/config.py`（配置优化）
   - 重新编译 Java 桥接：
     ```bash
     javac -cp 'lib/*' db/DmJdbcBridge.java
     ```

2. **配置更新**（可选）:
   - 复制 `dm_config.json.default` 到 `dm_config.json`
   - 根据需要调整新参数（或使用默认值）

3. **服务重启**:
   ```bash
   # 停止现有 MCP 服务器
   pkill -f "python main.py"

   # 启动新版本
   python main.py
   ```

4. **验证**:
   - 执行测试查询：`dm_query "SELECT 1 FROM DUAL"`
   - 检查日志：确认心跳消息和超时控制生效
   - 压力测试：并发查询验证连接池配置

### 回滚策略

- **配置回滚**: 恢复旧 `dm_config.json`
- **代码回滚**: Git checkout 到上一个版本
- **Java 回滚**: 保留旧版本 `DmJdbcBridge.class` 备份

### 监控指标

部署后关注以下指标：
- 查询超时率（应 < 1%）
- Java 进程重启次数（应 < 1次/小时）
- 平均查询耗时（应 < 5 秒）

## Open Questions

1. **心跳间隔是否需要可配置？**
   - 当前方案：固定 15 秒
   - 待讨论：是否需要 `dm_config.json` 中配置 `health_check_interval`

2. **是否需要实现查询取消机制？**
   - 当前方案：超时后重启 Java 进程，强制取消所有查询
   - 待讨论：是否需要精细化控制单个查询取消（如 JDBC `Statement.cancel()`）

3. **连接池大小是否需要动态调整？**
   - 当前方案：静态配置 20
   - 待讨论：是否需要根据负载动态调整（如 10-50）

4. **是否需要实现查询队列？**
   - 当前方案：并发查询受连接池限制，超出时等待
   - 待讨论：是否需要 Python 端查询队列（如 `queue.PriorityQueue`）
