"""
Tests for observability context management
"""

import pytest
from unittest.mock import MagicMock
from app.core.observability.context import (
    get_current_trace,
    set_current_trace,
    trace_context,
)


class TestContextManagement:
    """Test context management functions"""

    def test_get_current_trace_no_context(self):
        """Test getting current trace when no context is set"""
        result = get_current_trace()
        assert result is None

    def test_set_and_get_current_trace(self):
        """Test setting and getting current trace"""
        mock_trace = MagicMock()
        set_current_trace(mock_trace)

        result = get_current_trace()
        assert result == mock_trace

    def test_set_current_trace_to_none(self):
        """Test setting current trace to None"""
        # First set a trace
        mock_trace = MagicMock()
        set_current_trace(mock_trace)
        assert get_current_trace() == mock_trace

        # Then set to None
        set_current_trace(None)
        assert get_current_trace() is None

    def test_trace_context_manager(self):
        """Test trace_context context manager"""
        mock_trace = MagicMock()

        # Before context
        assert get_current_trace() is None

        # Inside context
        with trace_context(mock_trace) as yielded_trace:
            assert yielded_trace == mock_trace
            assert get_current_trace() == mock_trace

        # After context
        assert get_current_trace() is None

    def test_trace_context_exception_handling(self):
        """Test that trace context is properly reset even when exception occurs"""
        mock_trace = MagicMock()

        with pytest.raises(ValueError):
            with trace_context(mock_trace):
                assert get_current_trace() == mock_trace
                raise ValueError("Test exception")

        # Context should be reset even after exception
        assert get_current_trace() is None

    def test_nested_trace_contexts(self):
        """Test nested trace contexts"""
        outer_trace = MagicMock()
        inner_trace = MagicMock()

        with trace_context(outer_trace):
            assert get_current_trace() == outer_trace

            with trace_context(inner_trace):
                assert get_current_trace() == inner_trace

            # Should be back to outer trace
            assert get_current_trace() == outer_trace

        # Should be None after all contexts
        assert get_current_trace() is None

    def test_trace_context_returns_trace(self):
        """Test that trace_context returns the trace object"""
        mock_trace = MagicMock()

        with trace_context(mock_trace) as result:
            assert result == mock_trace

    def test_context_isolation(self):
        """Test that different context variables don't interfere"""
        # This test ensures that the context variable is properly isolated
        # by checking that we can set and reset values correctly
        trace1 = MagicMock()
        trace2 = MagicMock()

        # Set first trace
        set_current_trace(trace1)
        assert get_current_trace() == trace1

        # Set second trace
        set_current_trace(trace2)
        assert get_current_trace() == trace2

        # Reset to None
        set_current_trace(None)
        assert get_current_trace() is None
