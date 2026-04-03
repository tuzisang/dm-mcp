# Tasks: Fix Connection Attribute Error

## 1. 核心层修复

- [x] 1.1 在 `db/client.py` 中添加 `is_connected()` 方法
  - 实现异常捕获逻辑
  - 调用 `_get_bridge()` 获取Java桥接实例
  - 返回 `bridge.is_alive()` 的结果
  - 异常时返回 `False`

- [x] 1.2 更新 `db/client.py` 中的 `__enter__()` 方法
  - 调用 `is_connected()` 检查连接状态
  - 连接失败时抛出 `DmClientError` 异常
  - 保持返回 `self` 的原有行为

- [x] 1.3 改进 `db/java_bridge.py` 中的 `_wait_for_ready()` 错误消息
  - 在 `json.JSONDecodeError` 异常处理中添加详细诊断信息
  - 说明Java桥接版本不匹配的可能性
  - 提供CLASSPATH配置检查步骤
  - 提供重新编译Java桥接的命令示例

## 2. 工具层修复 - connection.py

- [x] 2.1 更新 `tools/connection.py` 中的 `dm_connect()` 函数
  - 将 `if not client.connection:` 改为 `if not client.is_connected():`
  - 保持其他逻辑不变

## 3. 工具层修复 - query.py

- [x] 3.1 更新 `tools/query.py` 中的 `dm_query()` 函数
  - 将 `if not client.connection:` 改为 `if not client.is_connected():`
  - 保持其他逻辑不变

## 4. 工具层修复 - schema.py

- [x] 4.1 更新 `tools/schema.py` 中的 `dm_list_tables()` 函数
  - 将 `if not client.connection:` 改为 `if not client.is_connected():`

- [x] 4.2 更新 `tools/schema.py` 中的 `dm_list_views()` 函数
  - 将 `if not client.connection:` 改为 `if not client.is_connected():`

- [x] 4.3 更新 `tools/schema.py` 中的 `dm_describe_table()` 函数
  - 将 `if not client.connection:` 改为 `if not client.is_connected():`

- [x] 4.4 更新 `tools/schema.py` 中的 `dm_get_view_definition()` 函数
  - 将 `if not client.connection:` 改为 `if not client.is_connected():`

## 5. 测试和验证

- [x] 5.1 单元测试 - 测试 `is_connected()` 方法
  - 测试正常连接场景
  - 测试Java桥接未启动场景
  - 测试异常场景（如Java进程崩溃）

- [x] 5.2 集成测试 - 测试上下文管理器
  - 测试 `with DmClient() as client:` 的正常流程
  - 测试连接失败时的异常抛出
  - 验证资源清理逻辑

- [x] 5.3 回归测试 - 测试所有7个MCP工具
  - 测试 `dm_connect()` 工具
  - 测试 `dm_query()` 工具
  - 测试 `dm_list_tables()` 工具
  - 测试 `dm_list_views()` 工具
  - 测试 `dm_describe_table()` 工具
  - 测试 `dm_get_view_definition()` 工具
  - 测试 `dm_update_config()` 工具
  - 确认不再出现 `AttributeError: 'DmClient' object has no attribute 'connection'`

- [x] 5.4 错误消息验证
  - 触发Java桥接启动失败
  - 验证错误消息包含详细的诊断信息
  - 确认错误消息中包含重新编译指导

## 6. 代码审查和文档

- [x] 6.1 自我代码审查
  - 检查所有修改的文件
  - 确认没有遗漏的 `client.connection` 引用
  - 验证错误消息的清晰性

- [x] 6.2 更新相关文档（如需要）
  - 检查CLAUDE.md是否需要更新
  - 检查README是否需要更新
  - 确认代码注释的准确性

## 7. 提交和归档

- [x] 7.1 提交代码变更
  - 使用清晰的commit message
  - 引用相关的change: `fix-connection-attribute-error`

- [x] 7.2 推送到远程仓库（如适用）

- [x] 7.3 归档change
  - 运行 `/opsx:archive fix-connection-attribute-error`
  - 将delta specs同步到main specs（如需要）

---

**任务统计**: 18个任务
- 核心层修复: 3个任务
- 工具层修复: 6个任务
- 测试和验证: 4个任务
- 代码审查和文档: 2个任务
- 提交和归档: 3个任务

**预计工作量**: 2-3小时（包含测试）
