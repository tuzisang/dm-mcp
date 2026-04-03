# Proposal: Fix Connection Attribute Error

## Why

在commit `5bcdedc` 中，`DmClient` 已从直接JDBC连接迁移到Java守护进程架构，移除了 `.connection` 属性。然而，工具层代码（`tools/connection.py`、`tools/query.py`、`tools/schema.py`）仍在检查这个不存在的属性，导致 `AttributeError: 'DmClient' object has no attribute 'connection'`，阻塞了所有数据库操作。

## What Changes

### 核心修复

- **db/client.py**: 添加 `is_connected()` 方法，替代直接检查 `.connection` 属性
- **db/client.py**: 更新 `__enter__()` 方法，在进入上下文时验证连接状态
- **tools/connection.py**: 将 `if not client.connection:` 改为 `if not client.is_connected():`
- **tools/query.py**: 将 `if not client.connection:` 改为 `if not client.is_connected():`
- **tools/schema.py**: 更新4个工具函数中的连接检查（dm_list_tables, dm_list_views, dm_describe_table, dm_get_view_definition）

### 错误处理改进

- **db/java_bridge.py**: 增强 `_wait_for_ready()` 的错误消息，提供详细的诊断信息
  - 检测Java桥接版本不匹配
  - 提供CLASSPATH配置检查提示
  - 指导重新编译Java桥接的步骤

## Capabilities

### New Capabilities

无。本次修复不引入新功能，仅修复现有功能的实现缺陷。

### Modified Capabilities

无。规格级别的数据库连接行为没有变化，只是修复实现层面的架构不一致问题。

## Impact

### 受影响的文件

**核心层 (db/)**
- `db/client.py` - 添加 `is_connected()` 方法，更新 `__enter__()` 方法
- `db/java_bridge.py` - 改进启动失败时的错误消息

**工具层 (tools/)**
- `tools/connection.py` - 更新 `dm_connect()` 的连接检查
- `tools/query.py` - 更新 `dm_query()` 的连接检查
- `tools/schema.py` - 更新4个schema工具的连接检查

### 兼容性

- **向后兼容**: ✅ 新的 `is_connected()` 方法对现有代码透明
- **API变更**: ⚠️ 移除了对不存在属性 `.connection` 的依赖
- **测试需求**: 需要回归测试所有7个MCP工具

### 风险评估

- **风险等级**: 低
- **影响范围**: 仅工具层，不影响核心数据库客户端逻辑
- **回滚难度**: 容易（可通过git revert快速回滚）

### 依赖项

无外部依赖变更。仅修改项目内部代码。

---

**下一步**: 完成设计文档（design.md）和任务分解（tasks.md）
