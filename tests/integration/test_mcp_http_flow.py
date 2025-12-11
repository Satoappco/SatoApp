"""
Integration Tests for MCP HTTP Flow

Tests the complete HTTP flow including:
- HTTP server startup and health checks
- Session initialization with real credentials
- Tool calls via HTTP
- Session cleanup

NOTE: These tests require the MCP HTTP server to be running:
  - Start server: docker-compose up -d mcp-ga4
  - Or manually: python app/mcps/google-analytics-oauth/http_server.py

These tests are SKIPPED by default. To run them:
  1. Start the MCP HTTP server
  2. Set SKIP_HTTP_INTEGRATION_TESTS=false
  3. Provide test credentials in environment variables
"""

import pytest
import os
import asyncio
from typing import Dict, Any

# Skip all tests in this file if HTTP server not available
pytestmark = pytest.mark.skipif(
    os.getenv('SKIP_HTTP_INTEGRATION_TESTS', 'true').lower() == 'true',
    reason="HTTP integration tests skipped - require MCP HTTP server running"
)

import httpx


# Test configuration
MCP_GA4_HTTP_URL = os.getenv('MCP_GA4_HTTP_URL', 'http://localhost:8001')
TEST_REFRESH_TOKEN = os.getenv('TEST_GA4_REFRESH_TOKEN')
TEST_PROPERTY_ID = os.getenv('TEST_GA4_PROPERTY_ID')
TEST_CLIENT_ID = os.getenv('TEST_GA4_CLIENT_ID')
TEST_CLIENT_SECRET = os.getenv('TEST_GA4_CLIENT_SECRET')


@pytest.fixture
def test_credentials() -> Dict[str, Any]:
    """Provide test credentials for HTTP server."""
    if not all([TEST_REFRESH_TOKEN, TEST_PROPERTY_ID, TEST_CLIENT_ID, TEST_CLIENT_SECRET]):
        pytest.skip("Test credentials not provided in environment variables")

    return {
        'refresh_token': TEST_REFRESH_TOKEN,
        'property_id': TEST_PROPERTY_ID,
        'client_id': TEST_CLIENT_ID,
        'client_secret': TEST_CLIENT_SECRET
    }


class TestHTTPServerHealth:
    """Test HTTP server health and availability."""

    @pytest.mark.asyncio
    async def test_health_endpoint(self):
        """Test that health endpoint is accessible."""
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{MCP_GA4_HTTP_URL}/health")

            assert response.status_code == 200
            data = response.json()
            assert data['status'] == 'healthy'
            assert data['service'] == 'google-analytics-mcp-http'
            assert 'active_sessions' in data


class TestHTTPSessionLifecycle:
    """Test HTTP session creation, usage, and cleanup."""

    @pytest.mark.asyncio
    async def test_initialize_session(self, test_credentials):
        """Test session initialization with valid credentials."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{MCP_GA4_HTTP_URL}/initialize",
                json=test_credentials
            )

            assert response.status_code == 200
            data = response.json()
            assert data['status'] == 'success'
            assert 'session_id' in data
            assert len(data['session_id']) > 0

            # Cleanup
            session_id = data['session_id']
            await client.delete(f"{MCP_GA4_HTTP_URL}/session/{session_id}")

    @pytest.mark.asyncio
    async def test_initialize_session_invalid_credentials(self):
        """Test session initialization with invalid credentials."""
        invalid_creds = {
            'refresh_token': 'invalid_token',
            'property_id': '123456789',
            'client_id': 'invalid_client',
            'client_secret': 'invalid_secret'
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{MCP_GA4_HTTP_URL}/initialize",
                json=invalid_creds
            )

            # Should return error (401 or 500)
            assert response.status_code in [401, 500]

    @pytest.mark.asyncio
    async def test_get_session_info(self, test_credentials):
        """Test retrieving session information."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Create session
            init_response = await client.post(
                f"{MCP_GA4_HTTP_URL}/initialize",
                json=test_credentials
            )
            session_id = init_response.json()['session_id']

            # Get session info
            info_response = await client.get(
                f"{MCP_GA4_HTTP_URL}/session/{session_id}"
            )

            assert info_response.status_code == 200
            data = info_response.json()
            assert data['session_id'] == session_id
            assert data['property_id'] == test_credentials['property_id']
            assert 'created_at' in data
            assert 'last_accessed' in data
            assert data['is_expired'] is False

            # Cleanup
            await client.delete(f"{MCP_GA4_HTTP_URL}/session/{session_id}")

    @pytest.mark.asyncio
    async def test_delete_session(self, test_credentials):
        """Test session deletion."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Create session
            init_response = await client.post(
                f"{MCP_GA4_HTTP_URL}/initialize",
                json=test_credentials
            )
            session_id = init_response.json()['session_id']

            # Delete session
            delete_response = await client.delete(
                f"{MCP_GA4_HTTP_URL}/session/{session_id}"
            )

            assert delete_response.status_code == 200
            data = delete_response.json()
            assert data['status'] == 'success'

            # Verify session is gone
            info_response = await client.get(
                f"{MCP_GA4_HTTP_URL}/session/{session_id}"
            )
            assert info_response.status_code == 404

    @pytest.mark.asyncio
    async def test_session_not_found(self):
        """Test accessing non-existent session."""
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                f"{MCP_GA4_HTTP_URL}/session/nonexistent-session-id"
            )

            assert response.status_code == 404


class TestHTTPToolCalls:
    """Test MCP tool calls via HTTP."""

    @pytest.mark.asyncio
    async def test_list_tools(self, test_credentials):
        """Test listing available tools."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Create session
            init_response = await client.post(
                f"{MCP_GA4_HTTP_URL}/initialize",
                json=test_credentials
            )
            session_id = init_response.json()['session_id']

            # List tools
            tools_response = await client.get(
                f"{MCP_GA4_HTTP_URL}/tools/{session_id}"
            )

            assert tools_response.status_code == 200
            data = tools_response.json()
            assert 'tools' in data
            assert len(data['tools']) > 0

            # Verify expected tools
            tool_names = [tool['name'] for tool in data['tools']]
            assert 'get_account_summaries' in tool_names
            assert 'get_property_details' in tool_names
            assert 'run_report' in tool_names

            # Cleanup
            await client.delete(f"{MCP_GA4_HTTP_URL}/session/{session_id}")

    @pytest.mark.asyncio
    async def test_call_get_account_summaries(self, test_credentials):
        """Test calling get_account_summaries tool."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Create session
            init_response = await client.post(
                f"{MCP_GA4_HTTP_URL}/initialize",
                json=test_credentials
            )
            session_id = init_response.json()['session_id']

            # Call tool
            tool_request = {
                'tool_name': 'get_account_summaries',
                'arguments': {}
            }

            tool_response = await client.post(
                f"{MCP_GA4_HTTP_URL}/tool/{session_id}/get_account_summaries",
                json=tool_request
            )

            assert tool_response.status_code == 200
            data = tool_response.json()
            assert data['success'] is True
            assert 'result' in data

            # Cleanup
            await client.delete(f"{MCP_GA4_HTTP_URL}/session/{session_id}")

    @pytest.mark.asyncio
    async def test_call_get_property_details(self, test_credentials):
        """Test calling get_property_details tool."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Create session
            init_response = await client.post(
                f"{MCP_GA4_HTTP_URL}/initialize",
                json=test_credentials
            )
            session_id = init_response.json()['session_id']

            # Call tool with property_id argument
            tool_request = {
                'tool_name': 'get_property_details',
                'arguments': {
                    'property_id': test_credentials['property_id']
                }
            }

            tool_response = await client.post(
                f"{MCP_GA4_HTTP_URL}/tool/{session_id}/get_property_details",
                json=tool_request
            )

            assert tool_response.status_code == 200
            data = tool_response.json()
            assert data['success'] is True
            assert 'result' in data

            # Cleanup
            await client.delete(f"{MCP_GA4_HTTP_URL}/session/{session_id}")

    @pytest.mark.asyncio
    async def test_call_run_report(self, test_credentials):
        """Test calling run_report tool."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Create session
            init_response = await client.post(
                f"{MCP_GA4_HTTP_URL}/initialize",
                json=test_credentials
            )
            session_id = init_response.json()['session_id']

            # Call tool with report parameters
            tool_request = {
                'tool_name': 'run_report',
                'arguments': {
                    'property_id': test_credentials['property_id'],
                    'dimensions': ['date'],
                    'metrics': ['activeUsers'],
                    'date_range_start': '7daysAgo',
                    'date_range_end': 'today',
                    'limit': 5
                }
            }

            tool_response = await client.post(
                f"{MCP_GA4_HTTP_URL}/tool/{session_id}/run_report",
                json=tool_request
            )

            assert tool_response.status_code == 200
            data = tool_response.json()
            assert data['success'] is True
            assert 'result' in data

            # Cleanup
            await client.delete(f"{MCP_GA4_HTTP_URL}/session/{session_id}")

    @pytest.mark.asyncio
    async def test_call_nonexistent_tool(self, test_credentials):
        """Test calling a tool that doesn't exist."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Create session
            init_response = await client.post(
                f"{MCP_GA4_HTTP_URL}/initialize",
                json=test_credentials
            )
            session_id = init_response.json()['session_id']

            # Call nonexistent tool
            tool_request = {
                'tool_name': 'nonexistent_tool',
                'arguments': {}
            }

            tool_response = await client.post(
                f"{MCP_GA4_HTTP_URL}/tool/{session_id}/nonexistent_tool",
                json=tool_request
            )

            assert tool_response.status_code == 404

            # Cleanup
            await client.delete(f"{MCP_GA4_HTTP_URL}/session/{session_id}")


class TestHTTPSessionTimeout:
    """Test session timeout and cleanup behavior."""

    @pytest.mark.asyncio
    async def test_session_updates_access_time(self, test_credentials):
        """Test that tool calls update last_accessed time."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Create session
            init_response = await client.post(
                f"{MCP_GA4_HTTP_URL}/initialize",
                json=test_credentials
            )
            session_id = init_response.json()['session_id']

            # Get initial session info
            info1 = await client.get(f"{MCP_GA4_HTTP_URL}/session/{session_id}")
            last_accessed_1 = info1.json()['last_accessed']

            # Wait a bit
            await asyncio.sleep(2)

            # Call a tool
            tool_request = {'tool_name': 'get_account_summaries', 'arguments': {}}
            await client.post(
                f"{MCP_GA4_HTTP_URL}/tool/{session_id}/get_account_summaries",
                json=tool_request
            )

            # Get updated session info
            info2 = await client.get(f"{MCP_GA4_HTTP_URL}/session/{session_id}")
            last_accessed_2 = info2.json()['last_accessed']

            # last_accessed should have been updated
            assert last_accessed_2 > last_accessed_1

            # Cleanup
            await client.delete(f"{MCP_GA4_HTTP_URL}/session/{session_id}")


class TestHTTPSSE:
    """Test Server-Sent Events (SSE) endpoint."""

    @pytest.mark.asyncio
    async def test_sse_connection(self, test_credentials):
        """Test SSE connection for real-time updates."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Create session
            init_response = await client.post(
                f"{MCP_GA4_HTTP_URL}/initialize",
                json=test_credentials
            )
            session_id = init_response.json()['session_id']

            # Connect to SSE endpoint
            async with client.stream('GET', f"{MCP_GA4_HTTP_URL}/sse/{session_id}") as response:
                assert response.status_code == 200
                assert response.headers['content-type'] == 'text/event-stream'

                # Read first few events
                events_received = []
                async for line in response.aiter_lines():
                    if line.startswith('data:'):
                        events_received.append(line)
                    if len(events_received) >= 2:
                        break

                # Should receive at least connected event
                assert len(events_received) > 0
                assert 'connected' in events_received[0]

            # Cleanup
            await client.delete(f"{MCP_GA4_HTTP_URL}/session/{session_id}")
