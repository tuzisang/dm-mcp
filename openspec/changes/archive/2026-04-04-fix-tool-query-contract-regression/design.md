## Context

`DmClient.execute_query()` 已统一返回 `{columns, rows}` 结构，但上层仍残留大量旧契约消费方式。最明显的症状是 `dm_connect()` 在基础查询成功时对结果执行 `test_result[0]`，直接触发 `KeyError(0)`；schema 工具则对顶层结果字典执行 `len(result)`，把 `columns` 和 `rows` 两个键误算成 `row_count=2`。`db/client.py` 自身的 `list_tables()` / `list_views()` 也还在按“逐行 dict”迭代结果做别名映射。

这些问题都属于同一类回归：客户端契约已经迁移，工具和辅助方法只迁移了一半。

## Goals / Non-Goals

**Goals:**
- 统一 `execute_query()` 上游和下游对 `{columns, rows}` 结构的消费方式。
- 让 `dm_connect()` 在真实连接成功时返回成功。
- 让 schema 工具的 `metadata.row_count` 与实际返回行数一致。
- 消除 `list_tables()` / `list_views()` 对旧逐行 dict 结构的依赖。

**Non-Goals:**
- 不改变 `dm_query()` / `dm_explain_plan()` 的对外返回结构。
- 不重构整个 `DmClient` 的类型系统。
- 不在本次变更中处理真实达梦的执行计划方言兼容性问题。

## Decisions

### 决策 1：保留统一 `{columns, rows}` 结构，不回退到 `list[dict]`

客户端返回契约已经在多个路径中统一，继续回退会重新引入多形态返回。修复方向应是让高层包装正确消费当前结构，而不是恢复旧接口。

### 决策 2：通过 SQL 别名修复表/视图名语义

`list_tables()` 和 `list_views()` 不再在 Python 中逐行改写字段名，而是直接在 SQL 中使用 `AS TABLE_NAME` / `AS VIEW_NAME`。这样结果结构仍保持 `{columns, rows}`，且不会再依赖逐行字典转换。

### 决策 3：工具层用 `rows` 计算元数据

所有工具层 `row_count` 统一从 `len(result.get("rows", []))` 计算。连接工具若要返回单行结果，则通过 `columns + 第一行` 构造可读字典。

## Risks / Trade-offs

- [风险] 部分历史调用方可能还依赖 `OBJECT_NAME` 字段名。 → 缓解：先集中修复本仓库内调用点，并用测试锁定新契约。
- [风险] 连接工具把首行重新组装成 dict 后，与其他工具的数据形态不同。 → 缓解：这只是 `test_query_result` 的展示层结构，不改变主查询工具契约。

## Migration Plan

1. 调整 `db/client.py` 的表/视图辅助查询，直接输出明确列别名。
2. 修复 `tools/connection.py` 的测试结果读取逻辑。
3. 修复 `tools/schema.py` 的 `row_count` 计算逻辑。
4. 增加回归测试并用实际 MCP 工具复测。

## Open Questions

- 如果后续还需要逐行 dict 结果，应评估是否增加显式转换辅助函数，而不是让每个工具自行拼装。
