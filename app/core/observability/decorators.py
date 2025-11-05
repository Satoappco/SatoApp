"""Decorators for Langfuse tracing."""

import functools
import inspect
import logging
from typing import Callable, Any, Optional, Dict
from app.config.langfuse_config import LangfuseConfig
from .context import get_current_trace, trace_context

logger = logging.getLogger(__name__)


def trace_function(
    name: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    capture_input: bool = True,
    capture_output: bool = True,
):
    """Decorator to trace a function with Langfuse.

    Args:
        name: Name of the span (defaults to function name)
        metadata: Additional metadata to attach to span
        capture_input: Whether to capture function arguments
        capture_output: Whether to capture function return value

    Example:
        @trace_function(name="process_data", metadata={"version": "1.0"})
        def process_data(data):
            return transform(data)
    """

    def decorator(func: Callable) -> Callable:
        span_name = name or func.__name__

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            if not LangfuseConfig.is_enabled():
                return await func(*args, **kwargs)

            parent_trace = get_current_trace()
            if parent_trace is None:
                # No parent trace, skip tracing this function
                return await func(*args, **kwargs)

            # Prepare input data
            input_data = None
            if capture_input:
                try:
                    sig = inspect.signature(func)
                    bound_args = sig.bind(*args, **kwargs)
                    bound_args.apply_defaults()
                    input_data = {
                        k: _sanitize_value(v)
                        for k, v in bound_args.arguments.items()
                    }
                except Exception as e:
                    logger.debug(f"Failed to capture input for {span_name}: {e}")

            # Create span
            span = parent_trace.span(
                name=span_name,
                input=input_data,
                metadata=metadata or {}
            )

            try:
                with trace_context(span):
                    result = await func(*args, **kwargs)

                # Capture output
                if capture_output:
                    try:
                        output_data = _sanitize_value(result)
                        span.end(output=output_data)
                    except Exception as e:
                        logger.debug(f"Failed to capture output for {span_name}: {e}")
                        span.end()
                else:
                    span.end()

                return result

            except Exception as e:
                span.end(
                    level="ERROR",
                    status_message=str(e)
                )
                raise

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            if not LangfuseConfig.is_enabled():
                return func(*args, **kwargs)

            parent_trace = get_current_trace()
            if parent_trace is None:
                # No parent trace, skip tracing this function
                return func(*args, **kwargs)

            # Prepare input data
            input_data = None
            if capture_input:
                try:
                    sig = inspect.signature(func)
                    bound_args = sig.bind(*args, **kwargs)
                    bound_args.apply_defaults()
                    input_data = {
                        k: _sanitize_value(v)
                        for k, v in bound_args.arguments.items()
                    }
                except Exception as e:
                    logger.debug(f"Failed to capture input for {span_name}: {e}")

            # Create span
            span = parent_trace.span(
                name=span_name,
                input=input_data,
                metadata=metadata or {}
            )

            try:
                with trace_context(span):
                    result = func(*args, **kwargs)

                # Capture output
                if capture_output:
                    try:
                        output_data = _sanitize_value(result)
                        span.end(output=output_data)
                    except Exception as e:
                        logger.debug(f"Failed to capture output for {span_name}: {e}")
                        span.end()
                else:
                    span.end()

                return result

            except Exception as e:
                span.end(
                    level="ERROR",
                    status_message=str(e)
                )
                raise

        # Return appropriate wrapper based on whether function is async
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def trace_class_methods(
    include: Optional[list[str]] = None,
    exclude: Optional[list[str]] = None,
    metadata: Optional[Dict[str, Any]] = None,
):
    """Decorator to trace all methods of a class.

    Args:
        include: List of method names to include (if None, includes all)
        exclude: List of method names to exclude
        metadata: Additional metadata to attach to spans

    Example:
        @trace_class_methods(exclude=["__init__", "_private"])
        class MyService:
            def process(self, data):
                ...
    """

    def decorator(cls):
        exclude_methods = set(exclude or [])
        exclude_methods.update(["__init__", "__new__", "__del__"])

        for attr_name in dir(cls):
            if attr_name.startswith("_") and attr_name not in (include or []):
                continue

            if attr_name in exclude_methods:
                continue

            attr = getattr(cls, attr_name)
            if callable(attr) and not isinstance(attr, type):
                traced_method = trace_function(
                    name=f"{cls.__name__}.{attr_name}",
                    metadata=metadata
                )(attr)
                setattr(cls, attr_name, traced_method)

        return cls

    return decorator


def _sanitize_value(value: Any, max_str_len: int = 1000) -> Any:
    """Sanitize a value for logging (remove sensitive data, truncate strings).

    Args:
        value: Value to sanitize
        max_str_len: Maximum string length

    Returns:
        Sanitized value safe for logging
    """
    # Handle None
    if value is None:
        return None

    # Handle strings
    if isinstance(value, str):
        if len(value) > max_str_len:
            return value[:max_str_len] + "..."
        return value

    # Handle bytes
    if isinstance(value, bytes):
        return f"<bytes: {len(value)} bytes>"

    # Handle dicts
    if isinstance(value, dict):
        sanitized = {}
        sensitive_keys = {"password", "token", "secret", "key", "api_key", "access_token", "refresh_token"}
        for k, v in value.items():
            if isinstance(k, str) and any(sens in k.lower() for sens in sensitive_keys):
                sanitized[k] = "***REDACTED***"
            else:
                sanitized[k] = _sanitize_value(v, max_str_len)
        return sanitized

    # Handle lists/tuples
    if isinstance(value, (list, tuple)):
        return type(value)(_sanitize_value(item, max_str_len) for item in value)

    # Handle objects with __dict__
    if hasattr(value, "__dict__") and not isinstance(value, type):
        return {
            "type": type(value).__name__,
            "attributes": _sanitize_value(value.__dict__, max_str_len)
        }

    # For primitives and other types, return as-is
    try:
        # Try to convert to string if it's a reasonable size
        str_val = str(value)
        if len(str_val) > max_str_len:
            return f"<{type(value).__name__}>"
        return str_val
    except Exception:
        return f"<{type(value).__name__}>"
