## 1. 修正客户端与工具契约

- [x] 1.1 调整 `db/client.py` 的表/视图辅助查询，移除对旧 `list[dict]` 结构的依赖
- [x] 1.2 修改 `tools/connection.py`，让 `dm_connect()` 正确读取统一查询结果并返回成功响应
- [x] 1.3 修改 `tools/schema.py`，让 schema 工具的 `metadata.row_count` 基于实际 `rows` 数量计算

## 2. 回归验证

- [x] 2.1 增加工具契约回归测试，覆盖 `dm_connect()` 成功路径和 schema 工具的 `row_count`
- [x] 2.2 运行本地静态校验并用 dm-mcp 工具实际复测连接与 schema 路径
