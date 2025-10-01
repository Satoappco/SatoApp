"""
Utility functions for handling async operations in tools
"""

import asyncio
import concurrent.futures
from typing import Any, Coroutine


def run_async_in_thread(coro: Coroutine[Any, Any, Any]) -> Any:
    """
    Run async coroutine in a separate thread to avoid event loop conflicts.
    This is needed when calling async functions from within tools that are
    executed in an already running event loop context.
    
    Args:
        coro: The async coroutine to run
        
    Returns:
        The result of the coroutine
    """
    def run_in_thread():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()
    
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future = executor.submit(run_in_thread)
        return future.result()
