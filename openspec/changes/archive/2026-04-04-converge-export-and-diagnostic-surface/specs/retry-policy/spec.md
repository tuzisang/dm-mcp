## REMOVED Requirements

### Requirement: 可配置的重试次数和延迟
**Reason**: 当前阶段不再支持通过配置或代码调整重试参数。
**Migration**: 无；请求失败后直接返回错误，由调用方决定是否重新发起请求。

### Requirement: 重试策略执行
**Reason**: 查询重试逻辑已从当前最小闭环中移除。
**Migration**: 由外部调用方在需要时显式重试，而不是依赖内部自动策略。

### Requirement: 可重试异常判断
**Reason**: 既然不再执行内部重试，也不再需要异常可重试性分类。
**Migration**: 无。

### Requirement: 指数退避重试（可选）
**Reason**: 退避策略属于未来能力预留，当前没有消费方。
**Migration**: 无。

### Requirement: 重试事件日志记录
**Reason**: 重试事件日志与内部重试实现一起移除。
**Migration**: 无。

### Requirement: 重试状态追踪
**Reason**: 当前响应元数据不再暴露重试状态，因为运行时不再执行内部重试。
**Migration**: 调用方如需追踪重试，应在自身流程中记录。
