"""
验证器测试

**Feature: mcp-refactor, Property 3: Validator rejects invalid identifiers**
**Feature: mcp-refactor, Property 4: Validator rejects non-SELECT queries**
**Validates: Requirements 3.1, 3.2, 3.3**
"""

import pytest
from hypothesis import given, strategies as st, settings

from core.validators import (
    validate_identifier,
    validate_sql_query,
    validate_optional_schema,
)
from core.exceptions import InvalidParameterError


class TestValidateIdentifier:
    """测试 validate_identifier 函数"""

    def test_valid_identifier(self):
        """有效标识符应通过验证"""
        assert validate_identifier("users") == "users"
        assert validate_identifier("User_Table") == "User_Table"
        assert validate_identifier("_private") == "_private"
        assert validate_identifier("table123") == "table123"

    def test_empty_identifier_rejected(self):
        """空标识符应被拒绝"""
        with pytest.raises(InvalidParameterError, match="不能为空"):
            validate_identifier("")

        with pytest.raises(InvalidParameterError, match="不能为空"):
            validate_identifier("   ")

    def test_identifier_with_spaces_trimmed(self):
        """标识符两端的空格应被去除"""
        assert validate_identifier("  users  ") == "users"

    def test_sql_injection_characters_rejected(self):
        """SQL 注入字符应被拒绝"""
        dangerous_chars = [";", "'", '"']
        for char in dangerous_chars:
            with pytest.raises(InvalidParameterError, match="无效字符"):
                validate_identifier(f"table{char}name")

    def test_sql_keywords_rejected(self):
        """SQL 关键字应被拒绝"""
        keywords = ["DROP", "DELETE", "INSERT", "UPDATE", "CREATE", "ALTER", "EXEC"]
        for keyword in keywords:
            with pytest.raises(InvalidParameterError, match="无效字符或 SQL 关键字"):
                validate_identifier(keyword)

    def test_sql_comments_rejected(self):
        """SQL 注释应被拒绝"""
        with pytest.raises(InvalidParameterError, match="无效字符"):
            validate_identifier("table--comment")

        with pytest.raises(InvalidParameterError, match="无效字符"):
            validate_identifier("table/*comment*/name")

    def test_too_long_identifier_rejected(self):
        """过长的标识符应被拒绝"""
        long_name = "a" * 129
        with pytest.raises(InvalidParameterError, match="过长"):
            validate_identifier(long_name)

    def test_max_length_identifier_accepted(self):
        """最大长度的标识符应被接受"""
        max_name = "a" * 128
        assert validate_identifier(max_name) == max_name

    def test_invalid_start_character_rejected(self):
        """以数字开头的标识符应被拒绝"""
        with pytest.raises(InvalidParameterError, match="必须以字母或下划线开头"):
            validate_identifier("123table")

    def test_invalid_characters_rejected(self):
        """包含无效字符的标识符应被拒绝"""
        with pytest.raises(InvalidParameterError, match="必须以字母或下划线开头"):
            validate_identifier("table-name")

        with pytest.raises(InvalidParameterError, match="必须以字母或下划线开头"):
            validate_identifier("table.name")


class TestValidateIdentifierProperty:
    """属性测试：验证器拒绝无效标识符"""

    @given(st.text(alphabet=";'\"", min_size=1, max_size=10))
    @settings(max_examples=100)
    def test_sql_injection_chars_always_rejected(self, dangerous_part: str):
        """
        **Property 3: Validator rejects invalid identifiers**
        任何包含 SQL 注入字符的字符串都应被拒绝
        """
        test_input = f"valid{dangerous_part}name"
        with pytest.raises(InvalidParameterError):
            validate_identifier(test_input)

    @given(st.sampled_from(["DROP", "DELETE", "INSERT", "UPDATE", "CREATE", "ALTER", "EXEC"]))
    @settings(max_examples=100)
    def test_sql_keywords_always_rejected(self, keyword: str):
        """
        **Property 3: Validator rejects invalid identifiers**
        任何 SQL 关键字都应被拒绝
        """
        with pytest.raises(InvalidParameterError):
            validate_identifier(keyword)


class TestValidateSqlQuery:
    """测试 validate_sql_query 函数"""

    def test_valid_select_query(self):
        """有效的 SELECT 查询应通过验证"""
        sql = "SELECT * FROM users"
        assert validate_sql_query(sql) == sql

    def test_select_with_where(self):
        """带 WHERE 子句的 SELECT 应通过验证"""
        sql = "SELECT id, name FROM users WHERE id = 1"
        assert validate_sql_query(sql) == sql

    def test_empty_query_rejected(self):
        """空查询应被拒绝"""
        with pytest.raises(InvalidParameterError, match="不能为空"):
            validate_sql_query("")

    def test_non_select_rejected(self):
        """非 SELECT 查询应被拒绝"""
        with pytest.raises(InvalidParameterError, match="只允许 SELECT"):
            validate_sql_query("UPDATE users SET name = 'test'")

    def test_dangerous_keywords_rejected(self):
        """危险关键字应被拒绝"""
        dangerous_queries = [
            "SELECT * FROM users; DROP TABLE users",
            "SELECT * FROM users WHERE 1=1 DELETE FROM users",
            "SELECT * FROM users UNION INSERT INTO users VALUES (1)",
        ]
        for query in dangerous_queries:
            with pytest.raises(InvalidParameterError, match="危险的 SQL 关键字"):
                validate_sql_query(query)


class TestValidateSqlQueryProperty:
    """属性测试：验证器拒绝非 SELECT 查询"""

    @given(st.sampled_from([
        "DROP TABLE users",
        "DELETE FROM users",
        "UPDATE users SET x=1",
        "INSERT INTO users VALUES (1)",
        "CREATE TABLE test (id INT)",
        "ALTER TABLE users ADD col INT",
        "TRUNCATE TABLE users",
        "GRANT ALL ON users TO public",
        "REVOKE ALL ON users FROM public",
    ]))
    @settings(max_examples=100)
    def test_non_select_always_rejected(self, query: str):
        """
        **Property 4: Validator rejects non-SELECT queries**
        任何非 SELECT 查询都应被拒绝
        """
        with pytest.raises(InvalidParameterError):
            validate_sql_query(query)

    @given(st.sampled_from(["DROP", "DELETE", "UPDATE", "INSERT", "CREATE", "ALTER", "TRUNCATE", "MERGE", "GRANT", "REVOKE"]))
    @settings(max_examples=100)
    def test_dangerous_keywords_in_select_rejected(self, keyword: str):
        """
        **Property 4: Validator rejects non-SELECT queries**
        SELECT 中包含危险关键字也应被拒绝
        """
        query = f"SELECT * FROM users; {keyword} TABLE test"
        with pytest.raises(InvalidParameterError):
            validate_sql_query(query)


class TestValidateOptionalSchema:
    """测试 validate_optional_schema 函数"""

    def test_none_returns_none(self):
        """None 应返回 None"""
        assert validate_optional_schema(None) is None

    def test_empty_string_returns_none(self):
        """空字符串应返回 None"""
        assert validate_optional_schema("") is None
        assert validate_optional_schema("   ") is None

    def test_valid_schema_validated(self):
        """有效的 schema 应通过验证"""
        assert validate_optional_schema("public") == "public"
        assert validate_optional_schema("  aiops  ") == "aiops"

    def test_invalid_schema_rejected(self):
        """无效的 schema 应被拒绝"""
        with pytest.raises(InvalidParameterError):
            validate_optional_schema("invalid;schema")
