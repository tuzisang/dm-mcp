## REMOVED Requirements

### Requirement: 连接池配置参数
**Reason**: 当前阶段不需要对外暴露连接池调优参数；这些参数增加了配置面，但没有形成被主流程消费的稳定能力。
**Migration**: 连接池参数改为内部固定默认值；调用方仅维护数据库连接参数与查询超时。

### Requirement: Java 端连接池配置
**Reason**: Java 端不再通过一组可调环境变量承诺连接池调优能力。
**Migration**: Java 桥接直接使用实现内默认值初始化 HikariCP。

### Requirement: 连接池状态监控
**Reason**: 当前系统没有基于连接池状态做调度或运维决策，该接口属于伪扩展点。
**Migration**: 无；如未来需要观测，再单独设计监控接口。

### Requirement: 连接池健康检查
**Reason**: 共享连接池仍然保留，但额外的池级监控、建议和告警链路不属于当前最小闭环。
**Migration**: 无；依赖 HikariCP 默认行为与共享桥接重建。

### Requirement: 连接池配置动态更新
**Reason**: 运行时更新连接池配置会引入额外状态切换与重启路径，不属于当前最小闭环。
**Migration**: 删除该能力；如未来确需调优，应通过代码变更重新引入并配套验证。

### Requirement: 连接池性能优化建议
**Reason**: 当前阶段没有稳定的观测输入和消费方，自动建议属于未来能力预留。
**Migration**: 无。
