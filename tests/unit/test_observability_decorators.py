"""
Tests for observability decorators
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from app.core.observability.decorators import (
    trace_function,
    trace_class_methods,
    _sanitize_value,
)


class TestTraceFunction:
    """Test trace_function decorator"""

    @patch("app.core.observability.decorators.LangfuseConfig.is_enabled")
    def test_trace_function_disabled_langfuse(self, mock_is_enabled):
        """Test that decorator returns original function when Langfuse is disabled"""
        mock_is_enabled.return_value = False

        @trace_function()
        def test_func(x, y=10):
            return x + y

        result = test_func(5, 15)
        assert result == 20

    @patch("app.core.observability.decorators.LangfuseConfig.is_enabled")
    @patch("app.core.observability.decorators.get_current_trace")
    def test_trace_function_no_parent_trace(self, mock_get_trace, mock_is_enabled):
        """Test that decorator returns original function when no parent trace"""
        mock_is_enabled.return_value = True
        mock_get_trace.return_value = None

        @trace_function()
        def test_func(x, y=10):
            return x + y

        result = test_func(5, 15)
        assert result == 20

    @patch("app.core.observability.decorators.LangfuseConfig.is_enabled")
    @patch("app.core.observability.decorators.get_current_trace")
    @patch("app.core.observability.decorators.trace_context")
    def test_trace_function_success_sync(
        self, mock_trace_context, mock_get_trace, mock_is_enabled
    ):
        """Test successful tracing of sync function"""
        mock_is_enabled.return_value = True

        # Mock parent trace and span
        mock_parent_trace = MagicMock()
        mock_span = MagicMock()
        mock_parent_trace.span.return_value = mock_span
        mock_get_trace.return_value = mock_parent_trace

        @trace_function(name="test_span", metadata={"version": "1.0"})
        def test_func(x, y=10):
            return x + y

        result = test_func(5, 15)

        assert result == 20
        mock_parent_trace.span.assert_called_once()
        mock_span.end.assert_called_once()
        mock_trace_context.assert_called_once_with(mock_span)

    @pytest.mark.asyncio
    @patch("app.core.observability.decorators.LangfuseConfig.is_enabled")
    @patch("app.core.observability.decorators.get_current_trace")
    @patch("app.core.observability.decorators.trace_context")
    async def test_trace_function_success_async(
        self, mock_trace_context, mock_get_trace, mock_is_enabled
    ):
        """Test successful tracing of async function"""
        mock_is_enabled.return_value = True

        # Mock parent trace and span
        mock_parent_trace = MagicMock()
        mock_span = MagicMock()
        mock_parent_trace.span.return_value = mock_span
        mock_get_trace.return_value = mock_parent_trace

        @trace_function(name="test_span", metadata={"version": "1.0"})
        async def test_func(x, y=10):
            return x + y

        result = await test_func(5, 15)

        assert result == 20
        mock_parent_trace.span.assert_called_once()
        mock_span.end.assert_called_once()
        mock_trace_context.assert_called_once_with(mock_span)

    @patch("app.core.observability.decorators.LangfuseConfig.is_enabled")
    @patch("app.core.observability.decorators.get_current_trace")
    @patch("app.core.observability.decorators.trace_context")
    def test_trace_function_exception_handling(
        self, mock_trace_context, mock_get_trace, mock_is_enabled
    ):
        """Test exception handling in traced function"""
        mock_is_enabled.return_value = True

        # Mock parent trace and span
        mock_parent_trace = MagicMock()
        mock_span = MagicMock()
        mock_parent_trace.span.return_value = mock_span
        mock_get_trace.return_value = mock_parent_trace

        @trace_function()
        def test_func():
            raise ValueError("Test error")

        with pytest.raises(ValueError, match="Test error"):
            test_func()

        mock_span.end.assert_called_once_with(
            level="ERROR", status_message="Test error"
        )

    @patch("app.core.observability.decorators.LangfuseConfig.is_enabled")
    @patch("app.core.observability.decorators.get_current_trace")
    @patch("app.core.observability.decorators.trace_context")
    def test_trace_function_no_capture_input(
        self, mock_trace_context, mock_get_trace, mock_is_enabled
    ):
        """Test tracing without input capture"""
        mock_is_enabled.return_value = True

        # Mock parent trace and span
        mock_parent_trace = MagicMock()
        mock_span = MagicMock()
        mock_parent_trace.span.return_value = mock_span
        mock_get_trace.return_value = mock_parent_trace

        @trace_function(capture_input=False)
        def test_func(x, y=10):
            return x + y

        result = test_func(5, 15)

        assert result == 20
        # Check that span was called with input=None
        call_args = mock_parent_trace.span.call_args
        assert call_args[1]["input"] is None

    @patch("app.core.observability.decorators.LangfuseConfig.is_enabled")
    @patch("app.core.observability.decorators.get_current_trace")
    @patch("app.core.observability.decorators.trace_context")
    def test_trace_function_no_capture_output(
        self, mock_trace_context, mock_get_trace, mock_is_enabled
    ):
        """Test tracing without output capture"""
        mock_is_enabled.return_value = True

        # Mock parent trace and span
        mock_parent_trace = MagicMock()
        mock_span = MagicMock()
        mock_parent_trace.span.return_value = mock_span
        mock_get_trace.return_value = mock_parent_trace

        @trace_function(capture_output=False)
        def test_func(x, y=10):
            return x + y

        result = test_func(5, 15)

        assert result == 20
        # Check that span.end was called without output parameter
        mock_span.end.assert_called_once_with()


class TestTraceClassMethods:
    """Test trace_class_methods decorator"""

    @patch("app.core.observability.decorators.LangfuseConfig.is_enabled")
    @patch("app.core.observability.decorators.get_current_trace")
    @patch("app.core.observability.decorators.trace_context")
    def test_trace_class_methods_basic(
        self, mock_trace_context, mock_get_trace, mock_is_enabled
    ):
        """Test basic class method tracing"""
        mock_is_enabled.return_value = True

        # Mock parent trace and span
        mock_parent_trace = MagicMock()
        mock_span = MagicMock()
        mock_parent_trace.span.return_value = mock_span
        mock_get_trace.return_value = mock_parent_trace

        @trace_class_methods(exclude=["__init__"])
        class TestClass:
            def __init__(self, value):
                self.value = value

            def method1(self, x):
                return self.value + x

            def method2(self, y):
                return self.value * y

            def _private_method(self):
                return "private"

        instance = TestClass(10)
        result1 = instance.method1(5)
        result2 = instance.method2(3)

        assert result1 == 15
        assert result2 == 30

        # Should have created spans for method1 and method2, but not _private_method
        assert mock_parent_trace.span.call_count == 2

    @patch("app.core.observability.decorators.LangfuseConfig.is_enabled")
    @patch("app.core.observability.decorators.get_current_trace")
    @patch("app.core.observability.decorators.trace_context")
    def test_trace_class_methods_include_private(
        self, mock_trace_context, mock_get_trace, mock_is_enabled
    ):
        """Test including private methods in tracing"""
        mock_is_enabled.return_value = True

        # Mock parent trace and span
        mock_parent_trace = MagicMock()
        mock_span = MagicMock()
        mock_parent_trace.span.return_value = mock_span
        mock_get_trace.return_value = mock_parent_trace

        @trace_class_methods(include=["_private_method"])
        class TestClass:
            def __init__(self, value):
                self.value = value

            def method1(self, x):
                return self.value + x

            def _private_method(self):
                return "private"

        instance = TestClass(10)
        result1 = instance.method1(5)
        result2 = instance._private_method()

        assert result1 == 15
        assert result2 == "private"

        # Should have created spans for method1 and _private_method
        assert mock_parent_trace.span.call_count == 2


class TestSanitizeValue:
    """Test _sanitize_value function"""

    def test_sanitize_none(self):
        """Test sanitizing None value"""
        result = _sanitize_value(None)
        assert result is None

    def test_sanitize_string(self):
        """Test sanitizing string values"""
        # Short string
        result = _sanitize_value("hello")
        assert result == "hello"

        # Long string gets truncated
        long_string = "a" * 2000
        result = _sanitize_value(long_string)
        assert len(result) == 1003  # 1000 + "..."
        assert result.endswith("...")

    def test_sanitize_bytes(self):
        """Test sanitizing bytes"""
        result = _sanitize_value(b"hello world")
        assert result == "<bytes: 11 bytes>"

    def test_sanitize_dict(self):
        """Test sanitizing dictionaries"""
        data = {
            "normal_value": "some_value",
            "password": "secret123",
            "api_key": "key456",
            "nested": {"token": "nested_secret"},
        }

        result = _sanitize_value(data)

        # The function checks if any sensitive keyword is contained in the key name
        # "password" contains "pass", "api_key" contains "key", "token" contains "token"
        assert result["normal_value"] == "some_value"
        assert result["password"] == "***REDACTED***"
        assert result["api_key"] == "***REDACTED***"
        assert result["nested"]["token"] == "***REDACTED***"

    def test_sanitize_list(self):
        """Test sanitizing lists and tuples"""
        data = ["item1", "item2", {"password": "secret"}]
        result = _sanitize_value(data)

        assert result[0] == "item1"
        assert result[1] == "item2"
        assert result[2]["password"] == "***REDACTED***"

        # Test tuple
        tuple_data = ("a", "b")
        result = _sanitize_value(tuple_data)
        assert result == ("a", "b")
        assert isinstance(result, tuple)

    def test_sanitize_object(self):
        """Test sanitizing custom objects"""

        class TestObj:
            def __init__(self):
                self.attr1 = "value1"
                self.password = "secret"

        obj = TestObj()
        result = _sanitize_value(obj)

        assert result["type"] == "TestObj"
        assert result["attributes"]["attr1"] == "value1"
        assert result["attributes"]["password"] == "***REDACTED***"

    def test_sanitize_primitives(self):
        """Test sanitizing primitive values"""
        assert _sanitize_value(42) == "42"
        assert _sanitize_value(3.14) == "3.14"
        assert _sanitize_value(True) == "True"

    def test_sanitize_large_object(self):
        """Test sanitizing objects that can't be stringified nicely"""

        class LargeObj:
            def __init__(self):
                self.data = "x" * 2000

        obj = LargeObj()
        result = _sanitize_value(obj)
        # Objects with __dict__ get sanitized as {"type": "...", "attributes": {...}}
        assert result["type"] == "LargeObj"
        assert "data" in result["attributes"]

    def test_sanitize_max_str_len(self):
        """Test custom max string length"""
        long_string = "a" * 500
        result = _sanitize_value(long_string, max_str_len=100)
        assert len(result) == 103  # 100 + "..."
