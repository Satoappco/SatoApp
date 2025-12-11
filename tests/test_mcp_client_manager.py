"""
Test MCP Client Manager and UnifiedMCPClient

This test validates:
1. UnifiedMCPClient correctly handles both HTTP and STDIO transports
2. get_tools() method works for both transport modes
3. MCPClientManager.get_clients() returns a UnifiedMCPClient
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.core.agents.mcp_clients.mcp_client_manager import (
    UnifiedMCPClient,
    MCPClientManager,
    MCPTransportMode
)
from app.core.agents.mcp_clients.http_client import HTTPMCPClient


class TestUnifiedMCPClient:
    """Test the UnifiedMCPClient wrapper."""

    @pytest.mark.asyncio
    async def test_http_transport_get_tools(self):
        """Test get_tools() with HTTP transport."""
        from langchain_core.tools import BaseTool
        from app.core.agents.mcp_clients.http_client import HTTPToolWrapper

        # Create mock HTTP clients
        mock_ga_client = AsyncMock(spec=HTTPMCPClient)
        mock_ga_client.list_tools.return_value = [
            {'name': 'run_report', 'description': 'Run GA4 report'},
            {'name': 'get_metadata', 'description': 'Get GA4 metadata'}
        ]

        mock_gads_client = AsyncMock(spec=HTTPMCPClient)
        mock_gads_client.list_tools.return_value = [
            {'name': 'list_accessible_accounts', 'description': 'List Google Ads accounts'},
            {'name': 'execute_gaql', 'description': 'Execute GAQL query'}
        ]

        # Create HTTP clients dict
        http_clients_dict = {
            'type': 'http',
            'clients': {
                'google_analytics': mock_ga_client,
                'google_ads': mock_gads_client
            }
        }

        # Create UnifiedMCPClient
        unified_client = UnifiedMCPClient(http_clients_dict)

        # Test get_tools()
        tools = await unified_client.get_tools()

        # Verify
        assert len(tools) == 4
        assert unified_client.transport_mode == 'http'
        mock_ga_client.list_tools.assert_called_once()
        mock_gads_client.list_tools.assert_called_once()

        # Verify all tools are proper LangChain BaseTool instances
        for tool in tools:
            assert isinstance(tool, BaseTool)
            assert isinstance(tool, HTTPToolWrapper)
            assert hasattr(tool, 'name')
            assert hasattr(tool, 'description')
            assert hasattr(tool, '_run')
            assert hasattr(tool, '_arun')

    @pytest.mark.asyncio
    async def test_stdio_transport_get_tools(self):
        """Test get_tools() with STDIO transport."""
        # Create mock STDIO client (MultiServerMCPClient)
        mock_stdio_client = AsyncMock()
        mock_stdio_client.get_tools.return_value = [
            MagicMock(name='run_report'),
            MagicMock(name='get_metadata'),
            MagicMock(name='list_accessible_accounts'),
            MagicMock(name='execute_gaql')
        ]

        # Create UnifiedMCPClient with STDIO client
        unified_client = UnifiedMCPClient(mock_stdio_client)

        # Test get_tools()
        tools = await unified_client.get_tools()

        # Verify
        assert len(tools) == 4
        assert unified_client.transport_mode == 'stdio'
        mock_stdio_client.get_tools.assert_called_once()

    @pytest.mark.asyncio
    async def test_http_transport_handles_errors(self):
        """Test that HTTP transport handles client errors gracefully."""
        # Create mock client that raises error
        mock_client = AsyncMock(spec=HTTPMCPClient)
        mock_client.list_tools.side_effect = Exception("Connection failed")

        http_clients_dict = {
            'type': 'http',
            'clients': {
                'google_analytics': mock_client
            }
        }

        unified_client = UnifiedMCPClient(http_clients_dict)

        # Should not raise, just return empty list
        tools = await unified_client.get_tools()
        assert tools == []

    @pytest.mark.asyncio
    async def test_http_tool_wrapper_unwraps_kwargs(self):
        """Test that HTTPToolWrapper properly unwraps 'kwargs' argument."""
        from app.core.agents.mcp_clients.http_client import HTTPToolWrapper

        # Create mock HTTP client
        mock_client = AsyncMock(spec=HTTPMCPClient)
        mock_client.call_tool.return_value = {
            'success': True,
            'content': [{'text': 'Success'}]
        }

        # Create tool wrapper
        tool = HTTPToolWrapper(
            name='execute_gaql',
            description='Execute GAQL query',
            http_client=mock_client,
            tool_name='execute_gaql'
        )

        # Test Case 1: LangChain wraps arguments in 'kwargs'
        result1 = await tool._arun(kwargs={'customer_id': '123', 'query': 'SELECT...'})

        # Verify the client received unwrapped arguments
        mock_client.call_tool.assert_called_with('execute_gaql', {'customer_id': '123', 'query': 'SELECT...'})
        assert result1 == 'Success'

        # Reset mock
        mock_client.reset_mock()

        # Test Case 2: Arguments passed directly (not wrapped)
        result2 = await tool._arun(customer_id='456', query='SELECT...')

        # Verify the client received the arguments correctly
        mock_client.call_tool.assert_called_with('execute_gaql', {'customer_id': '456', 'query': 'SELECT...'})
        assert result2 == 'Success'

    @pytest.mark.asyncio
    async def test_http_tool_wrapper_coroutine_property(self):
        """Test that HTTPToolWrapper has a coroutine property for agent compatibility."""
        from app.core.agents.mcp_clients.http_client import HTTPToolWrapper

        # Create mock HTTP client
        mock_client = AsyncMock(spec=HTTPMCPClient)
        mock_client.call_tool.return_value = {
            'success': True,
            'content': [{'text': 'Success'}]
        }

        # Create tool wrapper
        tool = HTTPToolWrapper(
            name='test_tool',
            description='Test tool',
            http_client=mock_client,
            tool_name='test_tool'
        )

        # Test that coroutine property exists and returns _arun
        assert hasattr(tool, 'coroutine')
        assert tool.coroutine == tool._arun

        # Test that coroutine can be wrapped (setter works)
        async def wrapped_coroutine(*args, **kwargs):
            return "wrapped"

        tool.coroutine = wrapped_coroutine
        assert tool.coroutine == wrapped_coroutine
        assert tool.coroutine != tool._arun


class TestMCPClientManager:
    """Test MCPClientManager.get_clients() returns UnifiedMCPClient."""

    def test_get_clients_returns_unified_wrapper(self):
        """Test that get_clients() returns UnifiedMCPClient instance."""
        # Create manager (no initialization needed for this test)
        manager = MCPClientManager(
            campaigner_id=1,
            platforms=['google_analytics'],
            credentials={'google_analytics': {}},
            transport_mode=MCPTransportMode.HTTP
        )

        # Manually set clients to simulate initialization
        manager.clients = {
            'type': 'http',
            'clients': {}
        }

        # Get clients
        client = manager.get_clients()

        # Verify it's a UnifiedMCPClient
        assert isinstance(client, UnifiedMCPClient)
        assert client.transport_mode == 'http'

    def test_get_clients_returns_none_when_not_initialized(self):
        """Test that get_clients() returns None when not initialized."""
        manager = MCPClientManager(
            campaigner_id=1,
            platforms=['google_analytics'],
            credentials={'google_analytics': {}}
        )

        # Don't initialize, clients should be None
        client = manager.get_clients()
        assert client is None


class TestGoogleAdsValidation:
    """Test that Google Ads validation accepts correct tool names."""

    @pytest.mark.asyncio
    async def test_google_ads_validator_accepts_new_tool_names(self):
        """Test that validator accepts list_accessible_accounts and execute_gaql."""
        from app.core.agents.mcp_clients.mcp_validator import MCPValidator
        from app.core.agents.mcp_clients.http_client import HTTPMCPClient

        # Create mock HTTP client with new tool names
        mock_client = AsyncMock(spec=HTTPMCPClient)
        mock_client.list_tools.return_value = [
            {'name': 'list_accessible_accounts'},
            {'name': 'execute_gaql'}
        ]
        mock_client.call_tool = AsyncMock(return_value=MagicMock(isError=False, content=[]))

        # Create validator
        validator = MCPValidator({'google_ads': mock_client})

        # Validate
        results = await validator.validate_all()

        # Should succeed (not fail with "Missing expected tools")
        assert len(results) == 1
        result = results[0]
        # Should be success, not failed
        assert result.status.value in ['success', 'error']  # error is ok if call_tool fails, but not "failed" due to missing tools
        if result.status.value == 'failed':
            assert 'Missing expected tools' not in result.message


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
