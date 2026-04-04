## REMOVED Requirements

### Requirement: 守护进程健康检查
**Reason**: 心跳检测、健康详情查询和基于健康状态的自动恢复已被明确移除。
**Migration**: 使用最小活性检查和显式重建共享运行时替代健康检查子系统。

### Requirement: Java 端心跳发送
**Reason**: 心跳协议不再属于当前最小只读闭环。
**Migration**: 无；当前设计不再发送或消费心跳消息。

### Requirement: 自动重启不健康的进程
**Reason**: 自动恢复路径已删除，避免在共享运行时周围继续叠加状态机。
**Migration**: 由显式 `reset_shared_client()` 或进程级重启完成恢复。

### Requirement: 防止连续重启
**Reason**: 自动重启能力已移除，重启限流不再有意义。
**Migration**: 无。

### Requirement: 健康状态查询接口
**Reason**: 当前实现不再暴露 `get_health_status()` 或等价接口。
**Migration**: 无；当前阶段不提供健康详情 API。
