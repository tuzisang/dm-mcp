## 1. 修正执行计划路径

- [x] 1.1 调整 `tools/explain_plan.py`，让 `dm_explain_plan` 生成与桥接分支一致的 `EXPLAIN PLAN` SQL
- [x] 1.2 修改 `db/DmJdbcBridge.java`，让 `EXPLAIN_PLAN` 路径在未读取到任何计划行时返回明确兼容性错误
- [x] 1.3 视需要更新 `db/client.py` 或相关文档注释，确保 `EXPLAIN_PLAN` 的错误语义与返回契约一致

## 2. 补充回归验证

- [x] 2.1 为 `dm_explain_plan` 增加单元测试，覆盖 SQL 形态和元数据透传
- [x] 2.2 增加 `EXPLAIN_PLAN` 空结果场景的回归测试，确保工具不会把 `rows=[]` 误判为成功
- [x] 2.3 运行相关测试并编译 Java 桥接，确认实现与规范一致（当前环境无 `pytest`，已改用 `py_compile`、最小 smoke test 和 `javac`）
