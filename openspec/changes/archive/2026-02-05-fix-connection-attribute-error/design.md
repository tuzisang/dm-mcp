# Design: Fix Connection Attribute Error

## Context

### 当前状态

项目已从直接JDBC连接架构迁移到Java守护进程架构（commit `5bcdedc`），但存在架构不一致问题：

**旧架构（已废弃）**
```
DmClient.connection → JDBC Connection对象
工具检查: if not client.connection
```

**新架构（当前）**
```
DmClient._java_bridge → JavaBridgeClient
Java守护进程 + stdin/stdout通信
工具仍检查: if not client.connection  ❌ 属性不存在
```

**架构分层**
```
MCP工具层 (tools/)
  ├─ connection.py
  ├─ query.py
  └─ schema.py

核心层 (db/)
  ├─ client.py (DmClient)
  └─ java_bridge.py (JavaBridgeClient)

Java层 (JVM)
  └─ DmJdbcBridge.class
```

### 约束条件

1. **最小化改动**: 仅修复连接检查逻辑，不改变核心架构
2. **向后兼容**: 保持工具API签名不变
3. **错误诊断**: 提供清晰的错误消息，帮助用户快速定位问题
4. **测试覆盖**: 确保7个MCP工具都能正常工作

## Goals / Non-Goals

**Goals:**
1. 统一连接检查接口：使用 `is_connected()` 方法替代直接属性访问
2. 改进错误消息：提供Java桥接启动失败的详细诊断信息
3. 代码一致性：所有工具函数使用相同的连接检查模式
4. 快速恢复功能：最小化改动，快速修复阻塞问题

**Non-Goals:**
1. 不修改Java桥接的实现（那是阶段2的工作）
2. 不改变MCP工具的外部API
3. 不重构核心架构（仅修复实现缺陷）
4. 不添加新的连接管理功能

## Decisions

### 决策1: 添加 `is_connected()` 方法而非 `.connection` 属性

**选择**: 在 `DmClient` 中添加 `is_connected()` 方法

**理由**:
- ✅ 语义更清晰：方法调用表达"检查连接状态"的意图
- ✅ 支持错误处理：方法内部可以捕获异常并返回False
- ✅ 符合新架构：`_java_bridge` 是私有属性，不应直接暴露
- ✅ 便于测试：可以模拟连接状态

**替代方案及驳回原因**:
- **方案A**: 添加 `@property def connection(self)` - 驳回：会误导用户以为存在真实的连接对象
- **方案B**: 直接暴露 `_java_bridge` - 驳回：破坏封装性

### 决策2: 在 `__enter__()` 中预检查连接

**选择**: 在上下文管理器入口调用 `is_connected()`，失败时抛出异常

**理由**:
- ✅ 快速失败（Fail Fast）：在执行SQL前就知道连接有问题
- ✅ 资源清理：如果连接失败，`__exit__()` 仍会调用 `close()` 清理资源
- ✅ 符合Python惯用法：上下文管理器应该确保资源可用

**替代方案及驳回原因**:
- **方案A**: 延迟到第一次查询时检查 - 驳回：延迟错误发现，难以调试
- **方案B**: 在每个工具函数中检查 - 驳回：重复代码，易遗漏

### 决策3: 改进Java桥接启动错误的诊断信息

**选择**: 在 `JavaBridgeClient._wait_for_ready()` 中捕获JSON解析失败，提供详细诊断

**理由**:
- ✅ 快速定位问题：用户可以立即知道是版本不匹配
- ✅ 减少支持成本：避免"连接失败"这类模糊的错误消息
- ✅ 指导修复：提供具体的检查和重新编译步骤

**诊断信息包括**:
- Java桥接版本不匹配的提示
- CLASSPATH配置检查步骤
- 重新编译命令示例

### 决策4: 修改模式（渐进式修复）

**选择**: 先修复 `db/client.py`，然后批量修改工具文件

**理由**:
- ✅ 依赖关系：工具依赖核心，先修复核心
- ✅ 测试友好：可以单独测试 `is_connected()` 方法
- ✅ 减少冲突：原子性修改，避免中间状态

**修改顺序**:
1. `db/client.py` - 添加 `is_connected()`，更新 `__enter__()`
2. `db/java_bridge.py` - 改进错误消息
3. `tools/connection.py` - 更新 `dm_connect()`
4. `tools/query.py` - 更新 `dm_query()`
5. `tools/schema.py` - 更新4个schema工具

## Risks / Trade-offs

### 风险1: Java桥接版本不匹配可能导致修复后仍有问题

**风险描述**: 即使修复了连接检查，如果Java桥接本身无法启动，数据库操作仍会失败。

**缓解措施**:
- ✅ 改进错误消息，明确指出Java桥接版本问题
- ✅ 提供诊断步骤和重新编译指导
- ✅ 在阶段2中重写Java桥接以解决根本问题

**影响**: 中等 - 用户可能看到更清晰的错误消息，但仍需等待阶段2彻底修复

### 风险2: 上下文管理器的异常处理逻辑

**风险描述**: 如果 `__enter__()` 抛出异常，`__exit__()` 不会被调用，可能导致资源泄漏。

**缓解措施**:
- ✅ `is_connected()` 只是检查状态，不会获取需要释放的资源
- ✅ `_java_bridge` 采用懒加载，此时可能尚未创建
- ✅ 即使创建，Java进程也会在Python进程退出时自动终止

**影响**: 低 - 实际资源泄漏风险很小

### 风险3: 多线程并发访问连接状态

**风险描述**: 多个MCP工具并发调用时，`is_connected()` 的状态可能不一致。

**缓解措施**:
- ✅ 当前MCP服务器是单线程的（FastMCP顺序处理请求）
- ✅ `_java_bridge` 内部已有线程锁保护
- ✅ `is_connected()` 是幂等的，多次调用无副作用

**影响**: 低 - 当前架构下不存在并发问题

## Implementation Plan

### 阶段1: 核心修复（本次实施）

**修改 db/client.py**
```python
def is_connected(self) -> bool:
    """检查数据库连接是否活跃"""
    try:
        bridge = self._get_bridge()
        return bridge is not None and bridge.is_alive()
    except Exception:
        return False

def __enter__(self):
    """上下文管理器入口 - 确保连接建立"""
    if not self.is_connected():
        raise DmClientError("无法建立数据库连接")
    return self
```

**修改 db/java_bridge.py**
```python
def _wait_for_ready(self):
    """等待守护进程就绪"""
    # ...
    except json.JSONDecodeError:
        raise JavaBridgeError(
            f"Java守护进程响应格式错误。\n"
            f"可能原因：\n"
            f"1. Java桥接版本过旧（期望JSON协议）\n"
            # ... 详细的诊断信息
        )
```

**批量修改工具文件（5个文件）**
```python
# 将所有:
if not client.connection:
# 改为:
if not client.is_connected():
```

### 验证计划

1. **单元测试**: 测试 `is_connected()` 在各种情况下的返回值
2. **集成测试**: 测试上下文管理器的连接检查
3. **回归测试**: 运行所有7个MCP工具，确保无AttributeError

### 回滚策略

- 如果引入新问题，可通过 `git revert <commit>` 快速回滚
- 修改集中在工具层，不影响核心架构，回滚风险低

## Open Questions

**Q1**: 是否需要添加Java桥接版本检测？
- **状态**: 延迟到阶段2
- **理由**: 阶段1专注于快速修复，版本检测需要修改Java桥接代码

**Q2**: 是否需要在 `is_connected()` 中实现健康检查（如测试查询）？
- **状态**: 否
- **理由**: 当前仅检查进程存活状态，健康检查会增加延迟和复杂性

**Q3**: 是否需要添加连接重试机制？
- **状态**: 否
- **理由**: 已有 `retry_attempts` 配置，在查询失败时重试。连接检查应该快速失败。

---

**下一步**: 创建任务分解（tasks.md）
