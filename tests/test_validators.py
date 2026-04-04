"""
验证器基础测试
"""

import pytest
from core.validators import (
    validate_identifier,
    validate_sql_query,
    validate_optional_schema,
    classify_statement,
    STATEMENT_TYPE_SELECT,
    STATEMENT_TYPE_EXPLAIN,
    STATEMENT_TYPE_EXPLAIN_PLAN,
)
from core.exceptions import InvalidParameterError


class TestValidateIdentifier:
    """测试 validate_identifier"""

    def test_valid_identifier(self):
        assert validate_identifier("users") == "users"
        assert validate_identifier("User_Table") == "User_Table"
        assert validate_identifier("_private") == "_private"

    def test_empty_identifier_rejected(self):
        with pytest.raises(InvalidParameterError, match="不能为空"):
            validate_identifier("")

    def test_sql_injection_rejected(self):
        with pytest.raises(InvalidParameterError):
            validate_identifier("table;name")

    def test_sql_keywords_rejected(self):
        with pytest.raises(InvalidParameterError):
            validate_identifier("DROP")

    def test_too_long_rejected(self):
        with pytest.raises(InvalidParameterError, match="过长"):
            validate_identifier("a" * 129)


class TestValidateSqlQuery:
    """测试 validate_sql_query（返回 Tuple[sql, statement_type]）"""

    # === SELECT 语句 ===
    def test_valid_select(self):
        sql = "SELECT * FROM users"
        result_sql, stmt_type = validate_sql_query(sql)
        assert result_sql == sql
        assert stmt_type == STATEMENT_TYPE_SELECT

    def test_select_with_comment(self):
        sql = "-- 注释\nSELECT * FROM users"
        result_sql, stmt_type = validate_sql_query(sql)
        assert "SELECT" in result_sql
        assert stmt_type == STATEMENT_TYPE_SELECT

    def test_select_lowercase(self):
        sql = "select * from users"
        result_sql, stmt_type = validate_sql_query(sql)
        assert stmt_type == STATEMENT_TYPE_SELECT

    def test_select_with_leading_block_comment(self):
        sql = "/* block comment */ SELECT * FROM users"
        result_sql, stmt_type = validate_sql_query(sql)
        assert stmt_type == STATEMENT_TYPE_SELECT

    # === EXPLAIN 语句 ===
    def test_explain_select(self):
        sql = "EXPLAIN SELECT * FROM users"
        result_sql, stmt_type = validate_sql_query(sql)
        assert stmt_type == STATEMENT_TYPE_EXPLAIN

    def test_explain_select_lowercase(self):
        sql = "explain select * from users"
        result_sql, stmt_type = validate_sql_query(sql)
        assert stmt_type == STATEMENT_TYPE_EXPLAIN

    def test_explain_with_comment(self):
        sql = "-- plan comment\nEXPLAIN SELECT * FROM users"
        result_sql, stmt_type = validate_sql_query(sql)
        assert stmt_type == STATEMENT_TYPE_EXPLAIN

    # === EXPLAIN PLAN FOR 语句 ===
    def test_explain_plan_for(self):
        sql = "EXPLAIN PLAN FOR SELECT * FROM users"
        result_sql, stmt_type = validate_sql_query(sql)
        assert stmt_type == STATEMENT_TYPE_EXPLAIN_PLAN

    def test_explain_plan_for_lowercase(self):
        sql = "explain plan for select * from users"
        result_sql, stmt_type = validate_sql_query(sql)
        assert stmt_type == STATEMENT_TYPE_EXPLAIN_PLAN

    # === EXPLAIN PLAN (without FOR) 语句 ===
    def test_explain_plan_without_for(self):
        """EXPLAIN PLAN（不含 FOR）归为 EXPLAIN_PLAN"""
        sql = "EXPLAIN PLAN SELECT * FROM users"
        result_sql, stmt_type = validate_sql_query(sql)
        assert stmt_type == STATEMENT_TYPE_EXPLAIN_PLAN

    def test_explain_plan_without_for_lowercase(self):
        """小写 EXPLAIN PLAN（不含 FOR）归为 EXPLAIN_PLAN"""
        sql = "explain plan select * from users"
        result_sql, stmt_type = validate_sql_query(sql)
        assert stmt_type == STATEMENT_TYPE_EXPLAIN_PLAN

    # === 危险语句拒绝 ===
    def test_empty_rejected(self):
        with pytest.raises(InvalidParameterError, match="不能为空"):
            validate_sql_query("")

    def test_whitespace_only_rejected(self):
        with pytest.raises(InvalidParameterError, match="不能为空"):
            validate_sql_query("   \n\t  ")

    def test_dangerous_keywords_rejected(self):
        with pytest.raises(InvalidParameterError, match="危险的 SQL 关键字"):
            validate_sql_query("SELECT * FROM users; DROP TABLE users")

    def test_insert_rejected(self):
        with pytest.raises(InvalidParameterError, match="危险的 SQL 关键字"):
            validate_sql_query("INSERT INTO users VALUES (1, 'test')")

    def test_update_rejected(self):
        with pytest.raises(InvalidParameterError, match="危险的 SQL 关键字"):
            validate_sql_query("UPDATE users SET name = 'test'")

    def test_delete_rejected(self):
        with pytest.raises(InvalidParameterError, match="危险的 SQL 关键字"):
            validate_sql_query("DELETE FROM users WHERE id = 1")

    def test_drop_rejected(self):
        with pytest.raises(InvalidParameterError, match="危险的 SQL 关键字"):
            validate_sql_query("DROP TABLE users")

    def test_explain_insert_rejected(self):
        """EXPLAIN 前缀不能豁免 DML 关键字检测"""
        with pytest.raises(InvalidParameterError, match="危险的 SQL 关键字"):
            validate_sql_query("EXPLAIN INSERT INTO users VALUES (1)")

    def test_explain_delete_rejected(self):
        """EXPLAIN 前缀不能豁免 DML 关键字检测"""
        with pytest.raises(InvalidParameterError, match="危险的 SQL 关键字"):
            validate_sql_query("EXPLAIN DELETE FROM users")

    def test_explain_drop_rejected(self):
        """EXPLAIN DROP 也要被拒绝"""
        with pytest.raises(InvalidParameterError, match="危险的 SQL 关键字"):
            validate_sql_query("EXPLAIN DROP TABLE users")


class TestClassifyStatement:
    """测试 classify_statement 函数"""

    def test_select(self):
        assert classify_statement("SELECT * FROM users") == STATEMENT_TYPE_SELECT
        assert classify_statement("select * from users") == STATEMENT_TYPE_SELECT

    def test_explain(self):
        assert classify_statement("EXPLAIN SELECT * FROM users") == STATEMENT_TYPE_EXPLAIN
        assert classify_statement("explain select * from users") == STATEMENT_TYPE_EXPLAIN

    def test_explain_plan_for(self):
        assert classify_statement("EXPLAIN PLAN FOR SELECT * FROM users") == STATEMENT_TYPE_EXPLAIN_PLAN
        assert classify_statement("explain plan for select * from users") == STATEMENT_TYPE_EXPLAIN_PLAN
        # 验证 EXPLAIN PLAN FOR 优先级高于 EXPLAIN
        assert classify_statement("EXPLAIN PLAN FOR DELETE FROM users") == STATEMENT_TYPE_EXPLAIN_PLAN

    def test_explain_plan_without_for(self):
        """EXPLAIN PLAN（不含 FOR）也归为 EXPLAIN_PLAN"""
        assert classify_statement("EXPLAIN PLAN SELECT * FROM users") == STATEMENT_TYPE_EXPLAIN_PLAN
        assert classify_statement("explain plan select * from users") == STATEMENT_TYPE_EXPLAIN_PLAN

    def test_unrecognized_raises(self):
        with pytest.raises(ValueError):
            classify_statement("SHOW TABLES")


class TestValidateOptionalSchema:
    """测试 validate_optional_schema"""

    def test_none_returns_none(self):
        assert validate_optional_schema(None) is None

    def test_empty_returns_none(self):
        assert validate_optional_schema("") is None

    def test_valid_schema(self):
        assert validate_optional_schema("public") == "public"
