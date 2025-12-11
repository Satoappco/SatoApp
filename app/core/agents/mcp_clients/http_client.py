"""HTTP MCP Client Wrapper.

This module provides a wrapper around HTTP-based MCP servers
to make them compatible with the MCP client interface.
"""

import httpx
import asyncio
from typing import List, Dict, Any, Optional, Type
from pydantic import BaseModel, Field, PrivateAttr, create_model
from langchain_core.tools import BaseTool
import logging

logger = logging.getLogger(__name__)


class HTTPToolWrapper(BaseTool):
    """Wrapper to convert HTTP MCP tool to LangChain BaseTool."""

    name: str
    description: str
    http_client: Any = Field(exclude=True)  # HTTPMCPClient instance
    tool_name: str
    _coroutine: Any = PrivateAttr(default=None)  # Store wrapped coroutine

    class Config:
        arbitrary_types_allowed = True

    def _run(self, **kwargs) -> str:
        """Synchronous execution (not used, but required by BaseTool)."""
        # Run async version in sync context
        loop = asyncio.get_event_loop()
        if loop.is_running():
            raise RuntimeError("Cannot call sync _run from async context")
        return loop.run_until_complete(self._arun(**kwargs))

    async def _arun(self, **kwargs) -> str:
        """Asynchronous execution of the tool."""
        try:
            # Unwrap 'kwargs' if LangChain wrapped the arguments
            # Sometimes LangChain passes {'kwargs': {'arg1': 'val1', ...}}
            # instead of {'arg1': 'val1', ...}
            if 'kwargs' in kwargs and len(kwargs) == 1:
                arguments = kwargs['kwargs']
            else:
                arguments = kwargs

            result = await self.http_client.call_tool(self.tool_name, arguments)

            # Handle different response formats
            if isinstance(result, dict):
                if result.get('success') is False:
                    return f"Error: {result.get('error', 'Unknown error')}"

                # Extract content from MCP response format
                if 'content' in result:
                    content = result['content']
                    if isinstance(content, list) and len(content) > 0:
                        # Get text from first content item
                        first_item = content[0]
                        if isinstance(first_item, dict) and 'text' in first_item:
                            return first_item['text']
                        elif hasattr(first_item, 'text'):
                            return first_item.text
                    return str(content)

                # Return the whole result as string
                return str(result)

            return str(result)

        except Exception as e:
            logger.error(f"Error calling HTTP tool {self.tool_name}: {e}")
            return f"Error: {str(e)}"

    @property
    def coroutine(self):
        """Return the async execution method for compatibility with LangChain's agent wrappers."""
        # If a wrapped coroutine was set, use it; otherwise use _arun
        return self._coroutine if self._coroutine is not None else self._arun

    @coroutine.setter
    def coroutine(self, value):
        """Allow setting a wrapped coroutine (used by agent's type coercion wrapper)."""
        self._coroutine = value


class HTTPMCPClient:
    """HTTP-based MCP client wrapper."""

    def __init__(self, platform: str, base_url: str, session_id: str):
        """Initialize HTTP MCP client.

        Args:
            platform: Platform name (e.g., 'google_analytics', 'google_ads')
            base_url: Base URL of the HTTP MCP server
            session_id: Session ID from initialization
        """
        self.platform = platform
        self.base_url = base_url
        self.session_id = session_id
        self._tools_cache: Optional[List[Dict[str, Any]]] = None

    async def list_tools(self) -> List[Dict[str, Any]]:
        """List available tools from the HTTP MCP server."""
        if self._tools_cache is not None:
            return self._tools_cache

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.base_url}/tools/{self.session_id}"
                )

                if response.status_code == 200:
                    result = response.json()
                    self._tools_cache = result.get('tools', [])
                    return self._tools_cache
                else:
                    logger.error(f"❌ Failed to list tools for {self.platform}: {response.status_code}")
                    return []

        except Exception as e:
            logger.error(f"❌ Error listing tools for {self.platform}: {e}")
            return []


    async def call_tool(self, tool_name: str, arguments: Dict[str, Any] = None) -> Dict[str, Any]:
        """Call a tool on the HTTP MCP server.

        Args:
            tool_name: Name of the tool to call
            arguments: Tool arguments

        Returns:
            Tool call result
        """
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.base_url}/tool/{self.session_id}/{tool_name}",
                    json={"tool_name": tool_name, "arguments": arguments or {}}
                )

                if response.status_code == 200:
                    return response.json()
                else:
                    error_msg = f"HTTP {response.status_code}: {response.text}"
                    logger.error(f"❌ Tool call failed for {tool_name}: {error_msg}")
                    return {
                        "success": False,
                        "error": error_msg
                    }

        except Exception as e:
            logger.error(f"❌ Error calling tool {tool_name}: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def close(self):
        """Close the HTTP session."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.delete(
                    f"{self.base_url}/session/{self.session_id}"
                )
                logger.info(f"✅ Closed HTTP session for {self.platform}")
        except Exception as e:
            logger.warning(f"⚠️  Failed to close HTTP session for {self.platform}: {e}")
