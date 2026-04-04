## 1. Public Surface

- [x] 1.1 收敛 `core`、`db` 的公开导出和调用路径，移除未被主流程消费的 re-export、response helper 与多余 helper 入口。
- [x] 1.2 精简 `db/client.py`、`db/java_bridge.py`，删除上下文管理器、手工 client 工厂和未使用的 `params` 透传。
- [x] 1.3 调整 `tools/*`、`main.py`、测试代码使用显式模块入口，而不是依赖宽泛的包级导出。

## 2. Repo Convergence

- [x] 2.1 删除仓库中的陈旧诊断/部署遗留物，包括 `db/DmJdbcBridge.class`、`scratch/ExplainProbe.*`、`scripts/verify_deployment.sh`。
- [x] 2.2 收敛 `core/cache.py` 的公共表面，只保留缓存行为契约，并把测试从内部实现断言改为公共行为断言。
- [x] 2.3 更新 `README.md`，明确当前正式支持的入口、验证方式和不再支持的旧路径。

## 3. Spec And Verification

- [x] 3.1 更新本次 change 的 delta specs，使 `database-client`、`java-bridge`、`connection-cleanup`、`connection-pool-config`、`health-check`、`retry-policy` 与最小闭环一致。
- [x] 3.2 运行必要验证，包括 Python 测试、Java 编译和 MCP 冒烟测试，并修复发现的问题。
