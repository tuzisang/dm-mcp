## REMOVED Requirements

### Requirement: 可配置的重试次数和延迟
**Reason**: 当前阶段没有稳定的可重试语义边界；把重试暴露为配置只会制造额外状态分支和伪保证。
**Migration**: 删除重试配置；请求失败后由调用方决定是否显式重试。

### Requirement: 重试策略执行
**Reason**: 隐式重试会掩盖真实错误来源，并放大请求路径复杂度。
**Migration**: 删除内置重试；单次调用只执行一次数据库请求。

### Requirement: 可重试异常判断
**Reason**: 当前系统不再在客户端内部做异常分类重试，因此不再维护这套判断矩阵。
**Migration**: 无；错误直接返回调用方。

### Requirement: 指数退避重试（可选）
**Reason**: 这属于明显的未来能力预留，不属于当前最小闭环。
**Migration**: 无。

### Requirement: 重试事件日志记录
**Reason**: 随重试机制一起移除，不再需要对应日志承诺。
**Migration**: 无。

### Requirement: 重试状态追踪
**Reason**: 单次请求不再内置重试，因此不存在需要回传的重试状态。
**Migration**: 无。
