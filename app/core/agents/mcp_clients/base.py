"""Base MCP client implementation."""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from contextlib import asynccontextmanager
import asyncio
import os


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

    async def connect(self):
        """Connect to the MCP server."""
        server_params = StdioServerParameters(
            command=self.get_server_command()[0],
            args=self.get_server_command()[1:],
            env=os.environ.copy()
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

        result = await self.session.call_tool(tool_name, arguments)
        return result

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


class MCPTool:
    """Wrapper for MCP tools to make them compatible with CrewAI/LangChain."""

    def __init__(self, client: BaseMCPClient, tool_name: str, tool_description: str):
        """
        Initialize MCP tool wrapper.

        Args:
            client: The MCP client instance
            tool_name: Name of the tool
            tool_description: Description of what the tool does
        """
        self.client = client
        self.tool_name = tool_name
        self.tool_description = tool_description
        self.name = tool_name
        self.description = tool_description

    async def _arun(self, **kwargs) -> Any:
        """Async execution of the tool."""
        return await self.client.call_tool(self.tool_name, kwargs)

    def _run(self, **kwargs) -> Any:
        """Sync execution of the tool."""
        return asyncio.run(self._arun(**kwargs))

    def __call__(self, **kwargs) -> Any:
        """Make the tool callable."""
        return self._run(**kwargs)
