"""
LLM Response Validation and Retry Logic

This module provides utilities for validating LLM responses and retrying
failed calls with exponential backoff.
"""

import logging
from typing import Any, Optional, Callable
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
    after_log
)

logger = logging.getLogger(__name__)


class LLMResponseError(Exception):
    """Raised when LLM returns invalid or empty response."""
    pass


def validate_llm_response(response: Any) -> bool:
    """
    Validate that an LLM response is not None or empty.

    Args:
        response: The LLM response to validate

    Returns:
        True if response is valid

    Raises:
        LLMResponseError: If response is None or empty
    """
    if response is None:
        logger.error("❌ LLM returned None response")
        raise LLMResponseError("LLM returned None response")

    # Check for content attribute (LangChain/CrewAI messages)
    if hasattr(response, 'content'):
        if not response.content or not str(response.content).strip():
            logger.error("❌ LLM returned empty content")
            raise LLMResponseError("LLM returned empty content")
        return True

    # Check for string response
    if isinstance(response, str):
        if not response.strip():
            logger.error("❌ LLM returned empty string")
            raise LLMResponseError("LLM returned empty string")
        return True

    # For other types, check if it's truthy
    if not response:
        logger.error("❌ LLM returned falsy response")
        raise LLMResponseError("LLM returned falsy response")

    return True


def create_llm_retry_decorator(
    max_attempts: int = 3,
    min_wait: int = 2,
    max_wait: int = 10,
    multiplier: int = 2
):
    """
    Create a retry decorator for LLM calls.

    Args:
        max_attempts: Maximum number of retry attempts
        min_wait: Minimum wait time between retries (seconds)
        max_wait: Maximum wait time between retries (seconds)
        multiplier: Exponential backoff multiplier

    Returns:
        Retry decorator configured for LLM calls
    """
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=multiplier, min=min_wait, max=max_wait),
        retry=retry_if_exception_type((LLMResponseError, Exception)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        after=after_log(logger, logging.DEBUG),
        reraise=True
    )


# Default retry decorator for LLM calls
llm_retry = create_llm_retry_decorator()


@llm_retry
def call_llm_with_validation(llm_callable: Callable, *args, **kwargs) -> Any:
    """
    Call an LLM with automatic validation and retry.

    Args:
        llm_callable: The LLM function to call
        *args: Positional arguments for the LLM call
        **kwargs: Keyword arguments for the LLM call

    Returns:
        Validated LLM response

    Raises:
        LLMResponseError: If response is invalid after all retries

    Example:
        >>> from langchain_google_genai import ChatGoogleGenerativeAI
        >>> llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash")
        >>> response = call_llm_with_validation(llm.invoke, "Hello, how are you?")
    """
    try:
        logger.debug(f"🔄 Calling LLM: {llm_callable.__name__ if hasattr(llm_callable, '__name__') else 'unknown'}")
        response = llm_callable(*args, **kwargs)
        validate_llm_response(response)
        logger.debug(f"✅ LLM response validated successfully")
        return response
    except Exception as e:
        logger.error(f"❌ LLM call failed: {str(e)}")
        raise


async def call_llm_with_validation_async(llm_callable: Callable, *args, **kwargs) -> Any:
    """
    Async version of call_llm_with_validation.

    Args:
        llm_callable: The async LLM function to call
        *args: Positional arguments for the LLM call
        **kwargs: Keyword arguments for the LLM call

    Returns:
        Validated LLM response

    Raises:
        LLMResponseError: If response is invalid after all retries
    """
    try:
        logger.debug(f"🔄 Calling LLM (async): {llm_callable.__name__ if hasattr(llm_callable, '__name__') else 'unknown'}")
        response = await llm_callable(*args, **kwargs)
        validate_llm_response(response)
        logger.debug(f"✅ LLM response validated successfully")
        return response
    except Exception as e:
        logger.error(f"❌ LLM call failed (async): {str(e)}")
        raise


def wrap_llm_call(llm_callable: Callable) -> Callable:
    """
    Wrap an LLM callable with validation and retry logic.

    Args:
        llm_callable: The LLM function to wrap

    Returns:
        Wrapped function with validation and retry

    Example:
        >>> llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash")
        >>> safe_invoke = wrap_llm_call(llm.invoke)
        >>> response = safe_invoke("Hello!")
    """
    @llm_retry
    def wrapper(*args, **kwargs):
        response = llm_callable(*args, **kwargs)
        validate_llm_response(response)
        return response

    return wrapper


class SafeLLMWrapper:
    """
    Wrapper class for LLM instances that adds validation and retry logic.

    Example:
        >>> from langchain_google_genai import ChatGoogleGenerativeAI
        >>> base_llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash")
        >>> safe_llm = SafeLLMWrapper(base_llm)
        >>> response = safe_llm.invoke("Hello!")
    """

    def __init__(self, llm: Any, max_attempts: int = 3):
        """
        Initialize the safe LLM wrapper.

        Args:
            llm: The base LLM instance to wrap
            max_attempts: Maximum retry attempts
        """
        self._llm = llm
        self._retry_decorator = create_llm_retry_decorator(max_attempts=max_attempts)
        logger.info(f"🛡️  SafeLLMWrapper initialized with {max_attempts} max attempts")

    def invoke(self, *args, **kwargs):
        """Invoke LLM with validation and retry."""
        @self._retry_decorator
        def _invoke():
            response = self._llm.invoke(*args, **kwargs)
            validate_llm_response(response)
            return response

        return _invoke()

    async def ainvoke(self, *args, **kwargs):
        """Async invoke LLM with validation and retry."""
        @self._retry_decorator
        async def _ainvoke():
            response = await self._llm.ainvoke(*args, **kwargs)
            validate_llm_response(response)
            return response

        return await _ainvoke()

    def __getattr__(self, name):
        """Delegate other attributes to the wrapped LLM."""
        return getattr(self._llm, name)
