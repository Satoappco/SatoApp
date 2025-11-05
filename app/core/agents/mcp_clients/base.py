"""Base MCP client implementation."""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Type
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from contextlib import asynccontextmanager
import asyncio
import os
import logging
import time
from langchain.tools import BaseTool
from pydantic import BaseModel, Field
from app.core.observability import get_current_trace

logger = logging.getLogger(__name__)


class BaseMCPClient(ABC):
    """Base class for MCP client implementations."""

    def __init__(self, server_path: str, server_args: Optional[List[str]] = None):
        """
        Initialize MCP client.

        Args:
            server_path: Path to the MCP server executable
            server_args: Additional arguments for the server
        """
        self.server_path = server_path
        self.server_args = server_args or []
        self.session: Optional[ClientSession] = None
        self._client_context = None
        self._read_stream = None
        self._write_stream = None

    @abstractmethod
    def get_server_command(self) -> List[str]:
        """Get the command to start the MCP server."""
        pass

    @abstractmethod
    def get_tools(self) -> List[Any]:
        """Get the tools provided by this MCP server."""
        pass

    def get_env_vars(self) -> Dict[str, str]:
        """Get environment variables to pass to MCP server.

        Override this method in subclasses to add tokens/credentials.
        """
        return os.environ.copy()

    async def connect(self):
        """Connect to the MCP server."""
        server_params = StdioServerParameters(
            command=self.get_server_command()[0],
            args=self.get_server_command()[1:],
            env=self.get_env_vars()
        )

        # Create stdio client context
        self._client_context = stdio_client(server_params)
        self._read_stream, self._write_stream = await self._client_context.__aenter__()

        # Create session
        self.session = ClientSession(self._read_stream, self._write_stream)
        await self.session.__aenter__()

        # Initialize the session
        await self.session.initialize()

    async def disconnect(self):
        """Disconnect from the MCP server."""
        if self.session:
            await self.session.__aexit__(None, None, None)

        if self._client_context:
            await self._client_context.__aexit__(None, None, None)

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """
        Call a tool on the MCP server.

        Args:
            tool_name: Name of the tool to call
            arguments: Arguments to pass to the tool

        Returns:
            Tool execution result
        """
        if not self.session:
            raise RuntimeError("Not connected to MCP server. Call connect() first.")

        # Get current trace for tracking
        current_trace = get_current_trace()
        tool_span = None

        if current_trace:
            # Sanitize arguments for logging
            sanitized_args = self._sanitize_arguments(arguments)
            tool_span = current_trace.span(
                name=f"mcp_tool_{tool_name}",
                input={"tool": tool_name, "arguments": sanitized_args},
                metadata={"mcp_client": self.__class__.__name__}
            )

        start_time = time.time()
        try:
            result = await self.session.call_tool(tool_name, arguments)
            duration_ms = (time.time() - start_time) * 1000

            logger.debug(f"✅ MCP tool {tool_name} completed in {duration_ms:.2f}ms")

            if tool_span:
                tool_span.end(
                    output={"success": True, "duration_ms": duration_ms},
                    metadata={"duration_ms": duration_ms}
                )

            return result

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(f"❌ MCP tool {tool_name} failed after {duration_ms:.2f}ms: {e}")

            if tool_span:
                tool_span.end(
                    level="ERROR",
                    status_message=str(e),
                    metadata={"duration_ms": duration_ms, "error": str(e)}
                )

            raise

    def _sanitize_arguments(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize arguments for logging (redact sensitive data)."""
        sanitized = {}
        sensitive_keys = {"token", "password", "secret", "key", "api_key", "access_token"}

        for k, v in arguments.items():
            if isinstance(k, str) and any(sens in k.lower() for sens in sensitive_keys):
                sanitized[k] = "***REDACTED***"
            elif isinstance(v, str) and len(v) > 200:
                sanitized[k] = v[:200] + "..."
            else:
                sanitized[k] = v

        return sanitized

    async def list_tools(self) -> List[Dict[str, Any]]:
        """List available tools from the MCP server."""
        if not self.session:
            raise RuntimeError("Not connected to MCP server. Call connect() first.")

        result = await self.session.list_tools()
        return result.tools

    def close(self):
        """Synchronously close the connection."""
        if self.session or self._client_context:
            try:
                asyncio.run(self.disconnect())
            except Exception as e:
                print(f"Error closing MCP client: {e}")


class MCPToolInput(BaseModel):
    """Input schema for MCP tools - accepts any arguments."""
    arguments: Dict[str, Any] = Field(
        default_factory=dict,
        description="Arguments to pass to the MCP tool"
    )


class MCPTool(BaseTool):
    """Wrapper for MCP tools to make them compatible with CrewAI/LangChain."""

    name: str = Field(..., description="Name of the tool")
    description: str = Field(..., description="Description of what the tool does")
    client: Any = Field(..., description="The MCP client instance")
    tool_name: str = Field(..., description="Name of the MCP tool to call")
    args_schema: Type[BaseModel] = MCPToolInput

    class Config:
        arbitrary_types_allowed = True

    def __init__(self, client: BaseMCPClient, tool_name: str, tool_description: str, **kwargs):
        """
        Initialize MCP tool wrapper.

        Args:
            client: The MCP client instance
            tool_name: Name of the tool
            tool_description: Description of what the tool does
        """
        super().__init__(
            name=tool_name,
            description=tool_description,
            client=client,
            tool_name=tool_name,
            **kwargs
        )

    def _run(self, arguments: Dict[str, Any] = None, **kwargs) -> Any:
        """Sync execution of the tool."""
        args = arguments or kwargs
        return asyncio.run(self._arun(args))

    async def _arun(self, arguments: Dict[str, Any] = None, **kwargs) -> Any:
        """Async execution of the tool."""
        args = arguments or kwargs
        return await self.client.call_tool(self.tool_name, args)
