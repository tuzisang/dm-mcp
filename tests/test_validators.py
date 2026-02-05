"""
验证器基础测试
"""

import pytest
from core.validators import validate_identifier, validate_sql_query, validate_optional_schema
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
    """测试 validate_sql_query"""

    def test_valid_select(self):
        sql = "SELECT * FROM users"
        assert validate_sql_query(sql) == sql

    def test_select_with_comment(self):
        sql = "-- 注释\nSELECT * FROM users"
        assert "SELECT" in validate_sql_query(sql)

    def test_empty_rejected(self):
        with pytest.raises(InvalidParameterError, match="不能为空"):
            validate_sql_query("")

    def test_non_select_rejected(self):
        with pytest.raises(InvalidParameterError, match="只允许 SELECT"):
            validate_sql_query("UPDATE users SET name = 'test'")

    def test_dangerous_keywords_rejected(self):
        with pytest.raises(InvalidParameterError, match="危险的 SQL 关键字"):
            validate_sql_query("SELECT * FROM users; DROP TABLE users")


class TestValidateOptionalSchema:
    """测试 validate_optional_schema"""

    def test_none_returns_none(self):
        assert validate_optional_schema(None) is None

    def test_empty_returns_none(self):
        assert validate_optional_schema("") is None

    def test_valid_schema(self):
        assert validate_optional_schema("public") == "public"
