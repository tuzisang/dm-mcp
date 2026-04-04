## 1. Diagnostic Path

- [x] 1.1 将 `dm_explain_plan()` 的底层执行语句改为 `EXPLAIN SELECT ...`，并保留执行计划工具语义元数据
- [x] 1.2 调整 `dm_query()` 对 `EXPLAIN PLAN [FOR]` 的规范化逻辑，使其落到当前环境可执行的直接计划路径

## 2. Bridge And Client

- [x] 2.1 修改 `db/DmJdbcBridge.java`，在 `statement_type = EXPLAIN` 且无 `ResultSet` 时读取 `DmdbStatement.getExplain()`
- [x] 2.2 修改 `db/client.py`，把“诊断 SQL 空结果”映射为明确错误，避免返回成功空结果

## 3. Verification

- [x] 3.1 更新/新增单元测试，覆盖 `EXPLAIN` 直接计划、`EXPLAIN PLAN [FOR]` 规范化和错误语义
- [x] 3.2 使用真实达梦库执行 `dm_query("EXPLAIN ...")` 与 `dm_explain_plan(...)` 自测并记录结论
