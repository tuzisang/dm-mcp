## 1. SQL classification and metadata

- [x] 1.1 Extend `core.validators.validate_sql_query` (and any helper utilities) to identify `statement_type` values for SELECT vs. diagnostic statements and reject DML/DDL, and add regression tests for the new patterns.
- [x] 1.2 Update `tools/query.py` (including metadata creation) to accept the classifier output, populate `metadata.statement_type` and `metadata.query_type`, and surface clear errors for unsupported statements.
- [x] 1.3 Extend classifier to recognize `EXPLAIN PLAN ...` (and optionally `EXPLAIN PLAN FOR ...`) as `EXPLAIN_PLAN` and add regression tests for both dialects.
- [x] 1.4 Add a compatibility strategy for `EXPLAIN_PLAN` dialect differences (e.g., normalize/remove `FOR` when rejected) with clear error messaging when neither form is supported.

## 2. Java bridge execution paths

- [x] 2.1 Modify `db/java_bridge.py` to accept `statement_type`, share it with the Java request payload, and route `EXPLAIN`/`EXPLAIN PLAN` statements to the appropriate JDBC handling path.
- [x] 2.2 Adjust `db/DmJdbcBridge.java` to handle plan statements and surface `plan_table_row_count` while keeping normal ResultSet output for diagnostics that do return rows.
- [x] 2.3 Fix `EXPLAIN` execution compatibility in Java bridge: avoid assuming `executeQuery()` works; use `execute()` + `getResultSet()` and provide a clear error when EXPLAIN cannot return rows in the target DM/JDBC version.
- [x] 2.4 Make `EXPLAIN_PLAN` plan-table reads deterministic (avoid mixing historical/other-session rows), e.g., via a controlled `STATEMENT_ID` marker or equivalent scoping mechanism supported by the target DM dialect.

## 3. Documentation and verification

- [x] 3.1 Update README/tool docs to describe the allowed diagnostic SQL, the fact that `dm_query` still only runs read-only statements, and how the new metadata differentiates statement types.
- [x] 3.2 Add or extend validator/tests (e.g., `tests/test_validators.py`) to cover valid/invalid diagnostic statements and ensure regression coverage for existing SELECT-only paths.
- [x] 3.3 Add regression coverage for the tool wrapper contract: successful `SELECT` must not crash in `dm_query` packaging (no list/dict mismatch), and metadata row_count must be computed from the actual returned shape.
- [x] 3.4 Add end-to-end verification cases for `EXPLAIN` and `EXPLAIN_PLAN` to prevent regressions of “执行未准备SQL语句” and `FOR`-syntax incompatibility in the supported DM environment.

## 4. New MCP tool: explain plan

- [x] 4.1 Add a new MCP tool (e.g., `dm_explain_plan(select_sql)`) that only accepts `SELECT` and returns the execution plan in a single call.
- [x] 4.2 Ensure the tool executes “plan generation + plan read” within the same JDBC connection/session (no reliance on users querying `PLAN_TABLE` in a later call).
- [x] 4.3 Update tool docs/README to recommend `dm_explain_plan` for plans and clarify why `PLAN_TABLE` may appear empty across separate MCP calls (session isolation / connection pooling).
- [x] 4.4 Add regression tests for `dm_explain_plan` validation (reject non-SELECT; block DML/DDL even if wrapped) and response metadata.
