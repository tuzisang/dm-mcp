# Specs: Fix Connection Attribute Error

## 说明

本次修复**不涉及规格级别的变更**，因此不需要创建或修改任何规格文件。

## 理由

根据 proposal.md 的 "Capabilities" 部分：

- **New Capabilities**: 无。本次修复不引入新功能。
- **Modified Capabilities**: 无。规格级别的数据库连接行为没有变化，仅修复实现层面的架构不一致。

## 修复范围

本次修复仅限于**实现层面**：

1. **API适配**: 适配新架构的连接检查接口（`is_connected()` 替代 `.connection`）
2. **错误处理**: 改进Java桥接启动失败的诊断信息
3. **代码一致性**: 统一所有工具函数的连接检查模式

## 不变的内容

以下规格级别的行为**保持不变**：

- ✅ 数据库连接的生命周期管理
- ✅ 上下文管理器的语义（`with`语句）
- ✅ MCP工具的外部API签名
- ✅ 错误处理的契约（抛出 `DatabaseConnectionError`）
- ✅ 重试机制和超时控制

## 参考文档

如果需要了解数据库连接的规格定义，请参考：

- `openspec/specs/database-client/spec.md` - 数据库客户端核心规格
- `openspec/specs/java-bridge/spec.md` - Java桥接服务规格
- `openspec/specs/connection-pool/spec.md` - 连接池管理规格

---

**结论**: 这是一个纯实现修复，规格文档保持不变。
