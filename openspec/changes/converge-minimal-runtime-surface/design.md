## Context

当前项目的真实主流程很短：

`main.py` -> `tools/*` -> `DmClient` -> `JavaBridgeClient` -> `db/DmJdbcBridge.java` -> 达梦 JDBC

但实现已经叠加出多层非必要复杂度：

- 冗余/重复代码
  - `core.validators` 与 `db.sql_security` 同时维护校验规则。
  - 各个工具文件重复定义 `get_database_client()`。
  - 根目录 `DmJdbcBridge.java` 与 `db/DmJdbcBridge.java` 并存，但只有后者在运行路径中使用。
- 过度抽象 / 无效层级
  - `db.config` 同时维护 `DmConfig`、`PoolConfig`、`CacheConfig`，但当前闭环只真正依赖数据库连接参数。
- `core.cache` 当前已经被真实读路径使用，但它的 TTL、失效时机和适用范围没有被明确收敛。
- 状态分叉 / 隐式行为
  - 查询缓存导致同一工具调用结果可能由数据库返回，也可能由内存返回。
  - Python 端桥接包含心跳、健康检查、自动重启、重试、重启限流等多套恢复路径。
- 伪扩展点 / 未来能力预留
  - 连接池状态查询、动态连接池调优、指数退避重试、详细超时遥测等能力当前没有稳定消费方。
  - 多个脚本式测试依赖本地数据库/JDK/目录布局，不属于可重复验证闭环。

约束：

- 不改变当前阶段必要的 MCP 工具集合。
- 不改变只读查询与诊断查询的主流程能力。
- 所有代码删改必须落在本设计声明的范围内。

## Goals / Non-Goals

**Goals:**

- 删除当前阶段非必要复杂度，优先删减而不是新增。
- 收敛为 MCP 进程内共享的最小执行闭环，只保留短时高频调用真正需要的跨调用复用状态。
- 减少文件数、配置项、协议分支、恢复分支和测试噪音。
- 保留 `dm_connect`、`dm_query`、`dm_explain_plan`、schema 查询、`dm_update_config` 的主流程可用性。
- 保留只读场景下约 1 分钟的查询缓存。
- 保留达梦 JDBC 执行计划相关兼容逻辑。

**Non-Goals:**

- 不新增任何新工具、新依赖或新扩展点。
- 不回到“每次工具调用都销毁桥接与连接池”的低效模型。
- 不处理本轮设计之外的协议扩展、监控、性能优化建议或未来运维能力。
- 不改动用户工作区中与本轮无关的现有修改。

## Decisions

### Decision: 定义当前阶段的最小闭环

保留的最小闭环定义为：

1. MCP 进程首次收到数据库工具调用时，惰性创建一个共享 `DmClient`。
2. 共享 `DmClient` 只维护一个共享 `JavaBridgeClient` 和其内部 HikariCP 数据源。
3. 后续短时间内的工具调用复用同一守护进程、同一连接池。
4. `dm_query` / `dm_explain_plan` 在共享运行时之上使用约 60 秒 TTL 的只读缓存。
5. 进程退出或配置变更时，显式关闭共享运行时并清空缓存。

理由：

- 用户已明确该 MCP 存在短时间频繁调用，连接池与守护进程复用是必要收益，不应误删。
- 需要收敛的是“围绕共享运行时长出来的外围复杂度”，不是共享运行时本身。

备选方案：

- 每次工具调用都重建 client/bridge：被拒绝，因为会直接放弃频繁调用场景下最真实的性能收益。

### Decision: 校验逻辑收敛到 `core.validators`

删除 `db/sql_security.py`，所有标识符与 SQL 分类/校验都收敛到 `core.validators`。

理由：

- 当前双实现已经形成规则漂移风险。
- 对外只需要一套“允许什么 SQL、拒绝什么 SQL”的规则。

备选方案：

- 同时保留两套校验并补同步测试：被拒绝，因为这是维护重复性而不是消除重复性。

### Decision: 保留缓存，但把缓存收敛为显式规则

保留 `core/cache.py`，并把缓存收敛到以下明确规则：

- 仅用于 `dm_query` / `dm_explain_plan` 这类只读查询工具
- TTL 固定为约 60 秒
- `dm_update_config` 成功后清空缓存
- 不把缓存能力继续扩散到其他工具或额外层级

理由：

- 用户已明确该 MCP 仅用于只读场景，短 TTL 缓存是实际需要的性能能力。
- 需要删除的是“隐式缓存语义”，而不是缓存本身。
- 把缓存边界写死，能保留收益同时减少歧义。

备选方案：

- 完全删除缓存：被拒绝，因为与当前真实使用场景不符。
- 继续维持当前散落的缓存策略：被拒绝，因为语义不够显式。

### Decision: 配置面收敛到最小必要参数

`dm_config.json` 的托管配置只保留：

- `host`
- `port`
- `user`
- `password`
- `schema`
- `query_timeout`

实现内固定：

- Python 端桥接 I/O 超时
- HikariCP 最小/最大连接数与连接超时

理由：

- 当前阶段真正需要外部配置的是“连到哪”和“查询执行上限”。
- `retry_*`、`health_check_interval`、`pool_*`、`cache_ttl` 等配置项不是当前闭环必需能力。

备选方案：

- 保留全部旧配置并标记“暂未使用”：被拒绝，因为这会继续保留伪能力面。

### Decision: Python 桥接客户端退化为薄执行层

`db/java_bridge.py` 删除以下能力：

- 心跳接收与后台健康线程
- 连续重启限制
- 连接池状态查询协议
- 重试配置与额外恢复策略

保留：

- 共享桥接实例的生命周期管理
- Java 启动
- JSON 请求发送
- 单次有界响应读取
- 按请求触发的最小活性判断
- 优雅关闭

理由：

- 共享守护进程本身需要保留，但不需要心跳、池状态查询、重启计数等额外协议层。
- 当前阶段更需要最小化共享状态，而不是在共享状态周围继续叠加运维能力。

备选方案：

- 继续保留完整守护增强逻辑：被拒绝，因为它仍然保留了大量当前无消费方的状态和分支。

### Decision: Java 桥接只保留只读执行路径

`db/DmJdbcBridge.java` 删除：

- 心跳线程
- `pool_status` 消息分支
- 非只读更新执行路径

保留：

- `SELECT`
- `EXPLAIN`
- `EXPLAIN_PLAN`
- 统一结果集转换
- 关闭消息与资源释放
- 执行计划兼容逻辑

理由：

- 当前 MCP 工具只暴露只读能力，写路径属于未消费的扩展点。
- 执行计划兼容逻辑是当前阶段真实能力，不能误删。

备选方案：

- 同时保留更新分支作为“未来可能需要”：被拒绝，因为这正是本轮要清理的未来能力预留。

### Decision: 统一客户端创建路径

工具层不再各自实现 `get_database_client()`；统一改为调用共享运行时入口（例如 `db.get_shared_client()`）。

理由：

- 删除低价值重复代码。
- 把“如何构造、复用和关闭共享 client”收敛到一个地方。

### Decision: 测试集收敛到可重复的单元回归

保留 mock/纯单元测试，删除依赖真实数据库、本地 Java 环境、人工输出检查的脚本式测试。

理由：

- 当前 repo 的测试噪音很大，真正稳定执行的回归面太小。
- 本轮目标是收敛错误面，而不是继续维护大量环境敏感脚本。

## Risks / Trade-offs

- [风险] 短 TTL 缓存会在极短时间窗口内返回缓存结果
  -> Mitigation: 这是用户明确接受的只读场景约束；同时将 TTL 固定在约 60 秒并在配置更新后清空缓存。

- [风险] 共享守护进程一旦失活，后续调用会受到影响
  -> Mitigation: 在请求入口做最小活性判断；配置变更和显式关闭都统一走共享运行时清理。

- [风险] 删除配置项后，旧配置文件可能仍包含遗留字段
  -> Mitigation: 配置加载逻辑应容忍额外字段，但不再导出、验证或文档化这些字段。

- [风险] 删除脚本式测试会减少“本地手工探针”
  -> Mitigation: 保留与主流程强相关的 mock/unit 回归，并在需要时使用 `scratch/` 作为临时诊断区，而不是正式测试面。

## Migration Plan

1. 更新 OpenSpec proposal/specs/design/tasks，明确删除边界。
2. 先删运行时死代码和重复资产：
   - `db/sql_security.py`
   - 根目录 `DmJdbcBridge.java`
   - 重复/脚本式测试文件
3. 收敛 Python 侧结构：
   - 精简 `db/config.py`
   - 精简 `db/client.py`
   - 精简 `db/java_bridge.py`
   - 工具层改用统一共享 client 入口
4. 收敛 Java 侧结构：
   - 删除心跳、pool status、更新路径
   - 保留只读查询和执行计划逻辑
5. 更新 README、示例配置和测试。
6. 运行最小必要验证：
   - Python 单元测试
   - Java 编译检查

回滚策略：

- 本轮改动集中在共享运行时收敛、重复代码删除和外围扩展点裁剪；若发现主流程回归，可按文件粒度回退本 change 的提交范围，不需要数据迁移。

## Open Questions

- 无阻塞问题。本轮按“最小闭环优先”直接实施，不为未来监控/调优预留接口。

## 删除 / 合并 / 收敛清单

**将删除的文件/模块**

- `db/sql_security.py`
- `DmJdbcBridge.java`
- `db/dm_config.json`
- `tests/test_bridge_simple.py`
- `tests/test_integration.py`
- `tests/test_jaydebeapi.py`
- `tests/test_new_client.py`
- `tests/test_regression.py`
- `tests/test_security.py`
- `tests/test_step_by_step.py`

**将合并/收敛的文件**

- `db/config.py`: 删除 `PoolConfig` / `CacheConfig` / 额外配置验证
- `db/client.py`: 删除重复校验、更新路径和历史兼容分支，收敛到共享 client 管理
- `db/java_bridge.py`: 删除心跳、重启计数和池状态协议，保留共享守护运行时
- `tools/connection.py`
- `tools/query.py`
- `tools/schema.py`
- `tools/explain_plan.py`
  - 统一改为使用共享 client 入口
- `tools/config.py`: 只保留最小必要配置项更新
- `core/__init__.py`
- `db/__init__.py`
- `tests/test_config.py`
- `tests/test_query_tool.py`
- `tests/test_server.py`

## Target Structure

修改后的目标结构：

```text
main.py
core/
  __init__.py
  cache.py
  decorators.py
  exceptions.py
  response.py
  validators.py
db/
  __init__.py
  config.py
  client.py
  java_bridge.py
  DmJdbcBridge.java
tools/
  __init__.py
  connection.py
  config.py
  explain_plan.py
  query.py
  schema.py
tests/
  __init__.py
  test_cache.py
  test_client_explain_plan.py
  test_config.py
  test_connection_schema_contract.py
  test_decorators.py
  test_is_connected.py
  test_query_tool.py
  test_server.py
  test_validators.py
```
