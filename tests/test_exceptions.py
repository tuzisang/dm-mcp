"""
异常类测试

**Feature: mcp-refactor, Property: Exception classes inherit from DMMCPError**
**Validates: Requirements 6.1, 6.2**
"""

import pytest
from hypothesis import given, strategies as st

from core.exceptions import (
    DMMCPError,
    DatabaseConnectionError,
    InvalidParameterError,
    SQLExecutionError,
)


class TestExceptionHierarchy:
    """测试异常类继承关系"""

    def test_dmmcp_error_is_base_exception(self):
        """DMMCPError 应该继承自 Exception"""
        assert issubclass(DMMCPError, Exception)

    def test_database_connection_error_inherits_from_dmmcp_error(self):
        """DatabaseConnectionError 应该继承自 DMMCPError"""
        assert issubclass(DatabaseConnectionError, DMMCPError)

    def test_invalid_parameter_error_inherits_from_dmmcp_error(self):
        """InvalidParameterError 应该继承自 DMMCPError"""
        assert issubclass(InvalidParameterError, DMMCPError)

    def test_sql_execution_error_inherits_from_dmmcp_error(self):
        """SQLExecutionError 应该继承自 DMMCPError"""
        assert issubclass(SQLExecutionError, DMMCPError)


class TestExceptionInstantiation:
    """测试异常类实例化"""

    @given(st.text(min_size=1, max_size=100))
    def test_dmmcp_error_with_message(self, message: str):
        """DMMCPError 应该能够携带任意消息"""
        error = DMMCPError(message)
        assert str(error) == message

    @given(st.text(min_size=1, max_size=100))
    def test_database_connection_error_with_message(self, message: str):
        """DatabaseConnectionError 应该能够携带任意消息"""
        error = DatabaseConnectionError(message)
        assert str(error) == message
        assert isinstance(error, DMMCPError)

    @given(st.text(min_size=1, max_size=100))
    def test_invalid_parameter_error_with_message(self, message: str):
        """InvalidParameterError 应该能够携带任意消息"""
        error = InvalidParameterError(message)
        assert str(error) == message
        assert isinstance(error, DMMCPError)

    @given(st.text(min_size=1, max_size=100))
    def test_sql_execution_error_with_message(self, message: str):
        """SQLExecutionError 应该能够携带任意消息"""
        error = SQLExecutionError(message)
        assert str(error) == message
        assert isinstance(error, DMMCPError)


class TestExceptionCatching:
    """测试异常捕获"""

    def test_catch_all_custom_exceptions_with_dmmcp_error(self):
        """所有自定义异常都应该能被 DMMCPError 捕获"""
        exceptions = [
            DatabaseConnectionError("test"),
            InvalidParameterError("test"),
            SQLExecutionError("test"),
        ]

        for exc in exceptions:
            try:
                raise exc
            except DMMCPError as e:
                assert str(e) == "test"
            except Exception:
                pytest.fail(f"{type(exc).__name__} 未被 DMMCPError 捕获")
