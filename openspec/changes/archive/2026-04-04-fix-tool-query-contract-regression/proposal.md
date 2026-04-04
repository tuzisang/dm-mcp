## Why

在真实环境测试中，`dm_query("SELECT 1 AS test_value FROM DUAL")` 可以正常返回结果，但 `dm_connect()` 却失败并只报出 `0`；同时 `dm_list_tables()`、`dm_list_views()`、`dm_describe_table()`、`dm_get_view_definition()` 虽然返回了 `data.columns/rows`，其 `metadata.row_count` 却始终是 `2`。这表明在 `DmClient.execute_query()` 被统一为 `{columns, rows}` 结构后，多个工具仍按旧的“`list[dict]`”契约消费结果，导致连接探测、别名映射和元数据统计全部失真。

这个问题已经不是单个工具的包装瑕疵，而是数据库客户端返回契约与上层工具消费方式之间的系统性回归。如果不先修复这层契约，后续任何 schema、连接和诊断工具的行为都会继续混杂“数据本身”和“包装层误用”的噪声。

## What Changes

- 修订数据库客户端与工具层之间的结果契约，明确哪些 API 返回 `{columns, rows}` 结构，哪些工具需要在包装层转换为更高层语义，而不能继续按 `list[dict]` 旧接口取值。
- 修复 `dm_connect()` 的成功判定逻辑，使其基于当前结果结构读取测试查询结果，避免再出现 `KeyError(0)` 这类无意义错误。
- 修复 schema 类工具的结果消费逻辑，包括 `dm_list_tables()`、`dm_list_views()`、`dm_describe_table()`、`dm_get_view_definition()` 的 `row_count` 统计、字段别名映射和返回一致性。
- 补充回归测试，覆盖“基础查询成功时 `dm_connect()` 也必须成功”和“schema 工具的 `metadata.row_count` 必须等于实际 `rows` 数量”。

## Capabilities

### New Capabilities
<!-- None -->

### Modified Capabilities
- `database-client`: 调整 `execute_query()` 统一返回契约与调用方约定，确保连接工具和 schema 工具不会再把 `{columns, rows}` 误当成 `list[dict]` 使用。

## Impact

- 受影响代码：
  - `db/client.py`
  - `tools/connection.py`
  - `tools/schema.py`
  - 相关工具测试和回归测试
- 受影响行为：
  - `dm_connect()` 在基础查询成功时应返回连接成功，而不是报 `0`
  - schema 工具的 `metadata.row_count` 必须反映真实行数，而不是固定为顶层字典键数量
  - schema 工具的字段别名映射必须与当前数据结构兼容
- 依赖与风险：
  - 无新增外部依赖
  - 需要明确哪些转换应留在 `DmClient`，哪些应由工具层承担，避免再次出现半迁移状态
