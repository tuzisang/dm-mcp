## 1. Shared Runtime

- [x] 1.1 精简 `db/config.py` 的配置模型，只保留数据库连接参数与查询超时，同时明确只读缓存 TTL 约 60 秒的默认行为。
- [x] 1.2 在 `db` 层实现共享 client/bridge 入口与统一清理逻辑，使 MCP 进程内的频繁调用复用同一守护进程和连接池。
- [x] 1.3 调整 `tools/connection.py`、`tools/query.py`、`tools/explain_plan.py`、`tools/schema.py`、`tools/config.py` 使用共享运行时，并在配置更新后重建共享运行时且清空缓存。

## 2. Complexity Reduction

- [x] 2.1 删除 `db/sql_security.py` 并将相关调用收敛到 `core.validators`。
- [x] 2.2 精简 `db/client.py`，删除重复校验、更新路径和历史兼容分支，收敛为共享只读执行器。
- [x] 2.3 精简 `db/java_bridge.py`，删除心跳、池状态协议、重启计数和多余恢复分支，保留最小活性判断、超时和优雅关闭。
- [x] 2.4 精简 `db/DmJdbcBridge.java`，删除心跳线程、`pool_status` 分支和非只读更新路径，保留只读查询与执行计划兼容逻辑。
- [x] 2.5 删除未使用的重复资产，包括根目录 `DmJdbcBridge.java` 和 `db/dm_config.json`。

## 3. Verification Surface

- [x] 3.1 更新 `README.md` 与 `dm_config.json.example`，说明共享守护进程、最小配置面和约 60 秒只读缓存。
- [x] 3.2 删除脚本式/环境敏感测试，保留并修正 mock/单元测试以覆盖共享运行时、缓存和配置更新行为。
- [x] 3.3 运行必要验证，包括 Python 测试与 Java 编译检查，并修复发现的问题。
