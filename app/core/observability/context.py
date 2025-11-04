"""Context management for Langfuse traces across async boundaries."""

from contextvars import ContextVar
from typing import Optional, Any
from contextlib import contextmanager

# Context variable to store current trace/span
_current_trace: ContextVar[Optional[Any]] = ContextVar("current_trace", default=None)


def get_current_trace() -> Optional[Any]:
    """Get the current Langfuse trace from context.

    Returns:
        Current trace/span or None if no trace is active
    """
    return _current_trace.get()


def set_current_trace(trace: Optional[Any]):
    """Set the current Langfuse trace in context.

    Args:
        trace: Langfuse trace or span to set as current
    """
    _current_trace.set(trace)


@contextmanager
def trace_context(trace: Any):
    """Context manager for setting trace context.

    Args:
        trace: Langfuse trace or span

    Example:
        with trace_context(trace):
            # Operations here will have access to the trace
            span = get_current_trace().span(name="operation")
    """
    token = _current_trace.set(trace)
    try:
        yield trace
    finally:
        _current_trace.reset(token)
