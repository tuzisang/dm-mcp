## 1. Java Bridge Compatibility

- [x] 1.1 Add `PLAN_TABLE` capability detection in `db/DmJdbcBridge.java` so `EXPLAIN_PLAN` no longer hard-codes `STATEMENT_ID`.
- [x] 1.2 Keep the existing `STATEMENT_ID` isolation path for environments that support it, and add a same-session cleanup/read fallback for environments that do not.
- [x] 1.3 Return a clear compatibility error when the bridge cannot prove plan-table isolation safely, instead of surfacing a raw “column not found” SQL error.
- [x] 1.4 Reuse generic ResultSet extraction for plan queries so plan output does not depend on a fixed column set.

## 2. Python Integration And Tests

- [x] 2.1 Preserve the existing Python return contract in `db/client.py` and `tools/explain_plan.py` while passing through the new compatibility behavior.
- [x] 2.2 Add regression tests for `dm_explain_plan` and related wrappers covering both successful compatibility fallback and clear compatibility errors.
- [x] 2.3 Update any docs or inline comments that still imply `PLAN_TABLE.STATEMENT_ID` is always available.

## 3. Verification

- [x] 3.1 Run the targeted Python test suite for query/explain-plan behavior.
- [x] 3.2 Compile the Java bridge after the compatibility change and confirm the project remains buildable.
- [x] 3.3 Mark this change complete in OpenSpec artifacts once implementation and verification finish.
