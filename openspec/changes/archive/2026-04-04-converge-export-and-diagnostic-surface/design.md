## Context

当前运行时真实闭环已经很短：

`main.py` -> `tools/*` -> `db/client.py` -> `db/java_bridge.py` -> `db/DmJdbcBridge.java`

但仓库外层还残留几类非必要复杂度：

- 冗余/重复代码
  - `core/response.py` 中的 `create_success_response` / `create_error_response` 已无人消费。
  - `core/__init__.py`、`db/__init__.py` 仍暴露大量未被主流程使用的对象，形成宽而隐式的导出面。
- 过度抽象 / 无效层级
  - `DmClient`、`JavaBridgeClient` 仍保留 `with` 上下文语义，但主流程已统一走共享运行时，不再存在“临时构造再自动关闭”的正常调用模式。
  - `db/client.py` 仍保留 `create_client()` 手工构造入口，而当前 MCP 只需要 `get_shared_client()` / `reset_shared_client()`。
- 状态分叉 / 隐式行为
  - 包级 re-export 让调用方无需显式指向真实模块，隐藏了依赖边界。
  - `core/cache.py` 暴露了内部实现类型与测试辅助入口，使测试和外部代码容易依赖缓存实现细节，而不是缓存行为契约。
- 伪扩展点 / 未来能力预留
  - Python 桥接仍保留 `params` 透传签名，但 Java 最小协议已经不消费该字段。
  - 仓库中仍存在 `db/DmJdbcBridge.class`、`scratch/ExplainProbe.*`、`scripts/verify_deployment.sh` 等历史遗留物，它们描述的路径、配置和行为已不再真实。
- 规范与实现分叉
  - main specs 仍声明心跳、自动重启、重试、池状态查询、上下文管理器等能力，而当前实现已明确收敛掉这些表面。

约束：

- 连接池、共享 Java 守护进程和约 60 秒只读缓存继续保留。
- 不改变当前 MCP 工具集合与只读主流程能力。
- 任何代码删改都必须在本设计声明的范围内。

## Goals / Non-Goals

**Goals:**

- 继续从第一性原理收敛到当前阶段真正必要的公开接口面和仓库结构。
- 删除未被主流程使用的 helper、导出、遗留脚本和诊断产物。
- 让调用方只能看到当前真实支持的最小运行时入口，减少误用路径。
- 让 OpenSpec main specs 回到与实现一致的最小闭环。

**Non-Goals:**

- 不改变只读 SQL、执行计划、共享连接池或缓存的行为能力。
- 不新增任何新工具、新配置项或新的抽象层。
- 不把诊断脚本替换为新的框架化工具。
- 不处理与本轮收敛无关的打包、发布或外部集成问题。

## Decisions

### Decision: 导出面收敛到显式模块入口

工具和运行时代码改为从具体模块导入依赖，而不是继续依赖宽泛的包级 re-export。

保留：

- `tools/__init__.py` 作为工具注册入口
- 必要的模块级实现文件

删除或收紧：

- `core/__init__.py` 的宽导出
- `db/__init__.py` 的宽导出
- 未被主流程消费的 response/cache/client helper 导出

理由：

- 包级“全量转发”扩大了隐式依赖面。
- 真实闭环只需要少量稳定入口，其他导出继续存在只会制造错误调用路径。

备选方案：

- 保留现状，只靠约定不去使用多余导出：被拒绝，因为这不会降低错误面。

### Decision: 删除未消费的手工生命周期 API

删除以下不再属于主流程的表面：

- `DmClient.__enter__()` / `__exit__()`
- `JavaBridgeClient.__enter__()` / `__exit__()`
- `db.client.create_client()`
- Python 桥接 `execute_query(..., params=...)` 中未消费的参数透传

保留：

- `get_shared_client()`
- `reset_shared_client()`
- `DmClient.close()` 与 `JavaBridgeClient.shutdown()` 作为显式生命周期动作

理由：

- 当前运行时唯一有效的生命周期是“进程级共享 + 显式重建/关闭”。
- 保留 `with` 或手工工厂只会鼓励错误调用方式。

备选方案：

- 继续保留这些 API 作为“手工调试入口”：被拒绝，因为仓库已经不应围绕临时调试入口设计。

### Decision: 仓库内诊断/部署遗留物直接删除

删除以下不再属于产品闭环的文件：

- `db/DmJdbcBridge.class`
- `scratch/ExplainProbe.java`
- `scratch/ExplainProbe.class`
- `scripts/verify_deployment.sh`

理由：

- 这些文件要么是编译产物，要么是一次性探针，要么已经验证过时。
- 它们保留在仓库中会误导维护者把它们视为正式支持路径。

备选方案：

- 保留这些文件并仅在 README 中说明“仅供参考”：被拒绝，因为这仍然保留了伪能力面。

### Decision: 缓存与响应模块只保留行为契约，不暴露内部实现

`core/cache.py` 仅保留主流程真正需要的公共行为：

- `mcp_cache`
- `clear_cache`

内部缓存结构和测试辅助函数改为内部实现细节，不再通过包导出，也不再由测试直接消费。

`core/response.py` 仅保留 `create_response_metadata`，删除未使用的成功/失败响应 helper。

理由：

- 当前测试对缓存内部结构的直接依赖不属于主流程契约。
- 响应 helper 未被消费，继续保留只会扩大维护面。

备选方案：

- 保留内部 helper，等待未来复用：被拒绝，因为这正是本轮要移除的未来预留。

### Decision: main specs 同步收敛到当前最小闭环

更新现有 capability，使其只反映当前支持的能力：

- `database-client`: 共享运行时、只读执行、稳定结果契约
- `java-bridge`: 最小 JSON 协议、超时、显式关闭
- `connection-cleanup`: 显式关闭与资源释放
- `connection-pool-config`: 固定实现内连接池参数

删除或移除的规范能力：

- `health-check`
- `retry-policy`
- 连接池状态查询、动态配置、性能建议、自动恢复、上下文管理器、参数化查询

理由：

- 规范继续声明已删除能力，会在下一轮演化时重新引入错误假设。

## Risks / Trade-offs

- [风险] 外部手工脚本可能仍依赖被删除的 helper 或诊断文件
  -> Mitigation: 当前产品闭环不依赖这些路径；README 与测试改为只描述正式支持路径。

- [风险] 删除缓存内部导出后，现有测试需要重写
  -> Mitigation: 将测试收敛到公开行为契约，避免再次绑定实现细节。

- [风险] main specs 收敛后，历史能力只能在 archive 中查看
  -> Mitigation: OpenSpec archive 保留完整历史；当前 main specs 只描述现状。

## Migration Plan

1. 先更新 proposal / design / delta specs / tasks，锁定删减边界。
2. 收敛代码导入与公开接口，删除未消费的 helper 和上下文管理器。
3. 删除仓库内的陈旧探针、编译产物和失真脚本。
4. 更新 README 与测试，使其只覆盖当前支持的最小闭环。
5. 运行 Python 测试、Java 编译和 MCP 冒烟测试。

## Open Questions

None.
