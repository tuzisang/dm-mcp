## Why

上一轮已经把运行时主链路收敛到“共享守护进程 + 共享连接池 + 只读缓存”，但仓库仍保留了过宽的导出面、未消费的 helper API、上下文管理壳层，以及一批已经失真的部署/诊断遗留物。它们不再服务当前闭环，却继续扩大模块耦合、误导调用方式，并让规范与实现再次分叉。

## What Changes

- 收敛 Python 侧公开接口面，只保留当前 MCP 主流程真正使用的入口；删除未被主流程消费的 helper、context-manager 壳层和手工 client 构造路径。
- 收敛 Java/Python 桥接协议，只保留 `ready`、只读 SQL 请求和 `shutdown`，删除未使用的参数透传与历史兼容壳层。
- 删除仓库中的陈旧部署/诊断遗留物，包括编译产物、探针代码和已失真的验证脚本。
- 更新测试、README 与 OpenSpec delta specs，使规范、实现和验证面重新对齐到当前阶段的最小闭环。

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `database-client`: 将客户端能力收敛到共享运行时入口，移除手工构造/上下文管理/参数化查询等当前阶段不再支持的表面。
- `java-bridge`: 将桥接协议收敛到最小只读请求响应闭环，移除 `params`、心跳、池状态和自动恢复相关要求。
- `connection-cleanup`: 将清理语义收敛到共享守护进程关闭和 JDBC 资源释放，移除监控、告警和诊断日志要求。
- `connection-pool-config`: 将连接池能力收敛到实现内固定参数，移除外部配置、状态查询和运行时调优要求。
- `health-check`: 删除基于心跳、自动重启、健康详情查询的能力要求。
- `retry-policy`: 删除可配置重试、退避和重试状态追踪要求。

## Impact

- Affected code: `core/*`, `db/*`, `tools/*`, `main.py`
- Affected tests: `tests/*`
- Affected docs/specs: `README.md`, `openspec/specs/*`
- Deleted repo artifacts: `db/DmJdbcBridge.class`, `scratch/ExplainProbe.*`, `scripts/verify_deployment.sh`
