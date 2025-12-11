"""
Unit Tests for MCP HTTP Transport

Tests the HTTP transport mode in MCPClientManager including:
- Transport mode selection
- HTTP client initialization
- Fallback from HTTP to STDIO
- Session management
"""

import pytest
import os
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import datetime, timezone

from app.core.agents.mcp_clients.mcp_client_manager import (
    MCPClientManager,
    MCPTransportMode,
)


class TestTransportModeSelection:
    """Tests for transport mode selection logic."""

    def test_default_transport_mode_is_auto(self):
        """Test that default transport mode is AUTO."""
        manager = MCPClientManager(
            campaigner_id=1,
            platforms=['google_analytics'],
            credentials={'google_analytics': {}}
        )
        assert manager.transport_mode == MCPTransportMode.AUTO

    def test_explicit_http_transport_mode(self):
        """Test setting HTTP transport mode explicitly."""
        manager = MCPClientManager(
            campaigner_id=1,
            platforms=['google_analytics'],
            credentials={'google_analytics': {}},
            transport_mode=MCPTransportMode.HTTP
        )
        assert manager.transport_mode == MCPTransportMode.HTTP

    def test_explicit_stdio_transport_mode(self):
        """Test setting STDIO transport mode explicitly."""
        manager = MCPClientManager(
            campaigner_id=1,
            platforms=['google_analytics'],
            credentials={'google_analytics': {}},
            transport_mode=MCPTransportMode.STDIO
        )
        assert manager.transport_mode == MCPTransportMode.STDIO

    def test_transport_mode_from_env_http(self):
        """Test reading HTTP transport mode from environment."""
        with patch.dict(os.environ, {'MCP_TRANSPORT_MODE': 'http'}):
            manager = MCPClientManager(
                campaigner_id=1,
                platforms=['google_analytics'],
                credentials={'google_analytics': {}}
            )
            assert manager.transport_mode == MCPTransportMode.HTTP

    def test_transport_mode_from_env_stdio(self):
        """Test reading STDIO transport mode from environment."""
        with patch.dict(os.environ, {'MCP_TRANSPORT_MODE': 'stdio'}):
            manager = MCPClientManager(
                campaigner_id=1,
                platforms=['google_analytics'],
                credentials={'google_analytics': {}}
            )
            assert manager.transport_mode == MCPTransportMode.STDIO

    def test_transport_mode_from_env_auto(self):
        """Test reading AUTO transport mode from environment."""
        with patch.dict(os.environ, {'MCP_TRANSPORT_MODE': 'auto'}):
            manager = MCPClientManager(
                campaigner_id=1,
                platforms=['google_analytics'],
                credentials={'google_analytics': {}}
            )
            assert manager.transport_mode == MCPTransportMode.AUTO

    def test_explicit_mode_overrides_env(self):
        """Test that explicit transport mode overrides environment variable."""
        with patch.dict(os.environ, {'MCP_TRANSPORT_MODE': 'stdio'}):
            manager = MCPClientManager(
                campaigner_id=1,
                platforms=['google_analytics'],
                credentials={'google_analytics': {}},
                transport_mode=MCPTransportMode.HTTP
            )
            assert manager.transport_mode == MCPTransportMode.HTTP


class TestHTTPServiceURLs:
    """Tests for HTTP service URL configuration."""

    def test_default_http_service_urls(self):
        """Test default HTTP service URLs."""
        manager = MCPClientManager(
            campaigner_id=1,
            platforms=['google_analytics'],
            credentials={'google_analytics': {}}
        )
        assert manager.http_service_urls['google_analytics'] == 'http://localhost:8001'
        assert manager.http_service_urls['google_ads'] == 'http://localhost:8002'
        assert manager.http_service_urls['facebook_ads'] == 'http://localhost:8003'

    def test_custom_http_service_url_from_env(self):
        """Test custom HTTP service URL from environment."""
        custom_url = 'http://mcp-ga4:8001'
        with patch.dict(os.environ, {'MCP_GA4_HTTP_URL': custom_url}):
            manager = MCPClientManager(
                campaigner_id=1,
                platforms=['google_analytics'],
                credentials={'google_analytics': {}}
            )
            assert manager.http_service_urls['google_analytics'] == custom_url


class TestHTTPInitialization:
    """Tests for HTTP client initialization."""

    @pytest.mark.asyncio
    async def test_http_initialization_google_analytics(self):
        """Test HTTP initialization for Google Analytics."""
        credentials = {
            'google_analytics': {
                'refresh_token': 'test_token',
                'property_id': '123456789',
                'client_id': 'test_client',
                'client_secret': 'test_secret'
            }
        }

        manager = MCPClientManager(
            campaigner_id=1,
            platforms=['google_analytics'],
            credentials=credentials,
            transport_mode=MCPTransportMode.HTTP
        )

        # Mock HTTP response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'session_id': 'test-session-123',
            'status': 'success'
        }

        with patch('httpx.AsyncClient') as mock_client:
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
            mock_client.return_value = mock_context

            # Disable token refresh and validation for this test
            manager.enable_token_refresh = False
            manager.enable_validation = False

            success = await manager.initialize()

            assert success is True
            assert 'google_analytics' in manager.http_sessions
            assert manager.http_sessions['google_analytics'] == 'test-session-123'

    @pytest.mark.asyncio
    async def test_http_initialization_failure(self):
        """Test HTTP initialization handles failures correctly."""
        credentials = {
            'google_analytics': {
                'refresh_token': 'test_token',
                'property_id': '123456789',
                'client_id': 'test_client',
                'client_secret': 'test_secret'
            }
        }

        manager = MCPClientManager(
            campaigner_id=1,
            platforms=['google_analytics'],
            credentials=credentials,
            transport_mode=MCPTransportMode.HTTP
        )

        # Mock HTTP error response
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = 'Invalid credentials'

        with patch('httpx.AsyncClient') as mock_client:
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
            mock_client.return_value = mock_context

            manager.enable_token_refresh = False
            manager.enable_validation = False

            success = await manager.initialize()

            # Should fail since HTTP mode only, no fallback
            assert success is False


class TestAutoModeFallback:
    """Tests for AUTO mode fallback from HTTP to STDIO."""

    @pytest.mark.asyncio
    async def test_auto_mode_falls_back_to_stdio(self):
        """Test that AUTO mode falls back to STDIO when HTTP fails."""
        credentials = {
            'google_analytics': {
                'refresh_token': 'test_token',
                'property_id': '123456789',
                'client_id': 'test_client',
                'client_secret': 'test_secret'
            }
        }

        manager = MCPClientManager(
            campaigner_id=1,
            platforms=['google_analytics'],
            credentials=credentials,
            transport_mode=MCPTransportMode.AUTO
        )

        # Mock HTTP failure
        with patch('httpx.AsyncClient') as mock_http:
            mock_http.side_effect = Exception("Connection refused")

            # Mock successful STDIO initialization
            with patch('app.core.agents.mcp_clients.mcp_client_manager.MCPSelector.build_all_server_params') as mock_selector:
                mock_selector.return_value = [MagicMock()]

                # Patch at the import location within the function
                with patch('langchain_mcp_adapters.client.MultiServerMCPClient') as mock_client:
                    mock_client.return_value = MagicMock()

                    manager.enable_token_refresh = False
                    manager.enable_validation = False

                    success = await manager.initialize()

                    # Should succeed with STDIO fallback
                    assert success is True
                    # Should have STDIO client, not HTTP
                    assert not isinstance(manager.clients, dict) or manager.clients.get('type') != 'http'

    @pytest.mark.asyncio
    async def test_auto_mode_prefers_http_when_available(self):
        """Test that AUTO mode uses HTTP when available."""
        credentials = {
            'google_analytics': {
                'refresh_token': 'test_token',
                'property_id': '123456789',
                'client_id': 'test_client',
                'client_secret': 'test_secret'
            }
        }

        manager = MCPClientManager(
            campaigner_id=1,
            platforms=['google_analytics'],
            credentials=credentials,
            transport_mode=MCPTransportMode.AUTO
        )

        # Mock successful HTTP response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'session_id': 'test-session-456',
            'status': 'success'
        }

        with patch('httpx.AsyncClient') as mock_client:
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
            mock_client.return_value = mock_context

            manager.enable_token_refresh = False
            manager.enable_validation = False

            success = await manager.initialize()

            # Should succeed with HTTP
            assert success is True
            assert 'google_analytics' in manager.http_sessions
            assert manager.http_sessions['google_analytics'] == 'test-session-456'


class TestHTTPSessionCleanup:
    """Tests for HTTP session cleanup."""

    @pytest.mark.asyncio
    async def test_cleanup_deletes_http_sessions(self):
        """Test that cleanup properly deletes HTTP sessions."""
        manager = MCPClientManager(
            campaigner_id=1,
            platforms=['google_analytics'],
            credentials={'google_analytics': {}}
        )

        # Setup fake sessions
        manager.http_sessions = {
            'google_analytics': 'session-123'
        }
        manager.clients = {
            'type': 'http',
            'clients': {'google_analytics': {}}
        }

        # Mock HTTP delete request
        with patch('httpx.AsyncClient') as mock_client:
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value.delete = AsyncMock()
            mock_client.return_value = mock_context

            await manager.cleanup()

            # Sessions should be cleared
            assert len(manager.http_sessions) == 0
            assert manager.clients is None

    @pytest.mark.asyncio
    async def test_cleanup_handles_errors_gracefully(self):
        """Test that cleanup handles HTTP errors gracefully."""
        manager = MCPClientManager(
            campaigner_id=1,
            platforms=['google_analytics'],
            credentials={'google_analytics': {}}
        )

        manager.http_sessions = {'google_analytics': 'session-123'}
        manager.clients = {'type': 'http', 'clients': {}}

        # Mock HTTP error
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.side_effect = Exception("Network error")

            # Should not raise exception
            await manager.cleanup()

            # Should still clear sessions and clients
            assert len(manager.http_sessions) == 0
            assert manager.clients is None


class TestHTTPConnectionData:
    """Tests for HTTP connection data formatting."""

    @pytest.mark.asyncio
    async def test_google_analytics_init_data_format(self):
        """Test that Google Analytics initialization data is formatted correctly."""
        credentials = {
            'google_analytics': {
                'refresh_token': 'test_refresh',
                'property_id': '987654321',
                'client_id': 'test_client_id',
                'client_secret': 'test_client_secret'
            }
        }

        manager = MCPClientManager(
            campaigner_id=1,
            platforms=['google_analytics'],
            credentials=credentials,
            transport_mode=MCPTransportMode.HTTP
        )

        # Mock to capture the request data
        captured_data = {}

        async def capture_post(url, **kwargs):
            if 'json' in kwargs:
                captured_data['json'] = kwargs['json']
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {'session_id': 'test-123', 'status': 'success'}
            return mock_resp

        with patch('httpx.AsyncClient') as mock_client:
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value.post = capture_post
            mock_client.return_value = mock_context

            manager.enable_token_refresh = False
            manager.enable_validation = False

            await manager.initialize()

            # Verify the data sent
            assert captured_data['json']['refresh_token'] == 'test_refresh'
            assert captured_data['json']['property_id'] == '987654321'
            assert captured_data['json']['client_id'] == 'test_client_id'
            assert captured_data['json']['client_secret'] == 'test_client_secret'
