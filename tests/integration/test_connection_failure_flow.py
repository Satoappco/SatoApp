"""
Integration Tests for Connection Failure Flow

Tests the complete flow of connection failure tracking from token refresh
through MCP validation to database updates.
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, AsyncMock, MagicMock

from app.core.oauth.token_refresh import (
    refresh_tokens_for_platforms,
    mark_needs_reauth,
    OAuthRefreshError
)
from app.core.agents.mcp_clients.mcp_validator import MCPValidator, ValidationStatus
from app.core.agents.mcp_clients.mcp_client_manager import MCPClientManager
from app.core.agents.mcp_clients.mcp_registry import MCPServer
from app.models.analytics import Connection, AssetType, DigitalAsset, AuthType
from app.config.database import get_session


@pytest.fixture
def test_connection(db_session):
    """Create a test connection in database."""
    session = db_session
    with session:
        # Create digital asset
        asset = DigitalAsset(
            customer_id=1,
            external_id="test-ga4-property",
            asset_type=AssetType.GA4,
            provider="Google",
            name="Test GA4 Property",
            is_active=True,
            meta={"property_id": "123456789"}
        )
        session.add(asset)
        session.commit()
        session.refresh(asset)

        # Create connection
        connection = Connection(
            digital_asset_id=asset.id,
            customer_id=1,
            campaigner_id=1,
            auth_type=AuthType.OAUTH2,
            account_email="test@example.com",
            scopes=["https://www.googleapis.com/auth/analytics.readonly"],
            expires_at=datetime.now(timezone.utc) + timedelta(days=1),
            revoked=False,
            failure_count=0,
            needs_reauth=False
        )
        session.add(connection)
        session.commit()
        session.refresh(connection)

        yield connection

        # Cleanup
        session.delete(connection)
        session.delete(asset)
        session.commit()


class TestTokenRefreshFailureFlow:
    """Test token refresh failure logging."""

    @patch('app.core.oauth.token_refresh.refresh_google_token')
    def test_token_refresh_failure_logged_to_database(self, mock_refresh, test_connection):
        """Test that token refresh failure is logged to database."""
        # Setup - make token refresh fail
        mock_refresh.side_effect = OAuthRefreshError(
            provider="Google",
            error="invalid_grant",
            error_description="Token has been expired or revoked"
        )

        # Make token appear expired
        with get_session() as session:
            conn = session.get(Connection, test_connection.id)
            conn.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
            session.commit()

        # Execute
        user_tokens = {'google_analytics': 'fake_refresh_token'}
        platforms = [MCPServer.GOOGLE_ANALYTICS_OFFICIAL]

        result = refresh_tokens_for_platforms(1, platforms, user_tokens)

        # Assert
        with get_session() as session:
            conn = session.get(Connection, test_connection.id)
            assert conn.failure_count > 0, "Failure count should be incremented"
            assert conn.failure_reason == "token_refresh_failed", "Failure reason should be set"
            assert conn.needs_reauth is True, "needs_reauth should be set"
            assert conn.last_failure_at is not None, "last_failure_at should be set"

        # Token should be removed from result
        assert 'google_analytics' not in result

    def test_mark_needs_reauth_records_failure(self, test_connection):
        """Test that mark_needs_reauth records connection failure."""
        # Execute
        mark_needs_reauth(campaigner_id=1, asset_type=AssetType.GA4)

        # Assert
        with get_session() as session:
            conn = session.get(Connection, test_connection.id)
            assert conn.needs_reauth is True
            assert conn.failure_count == 1
            assert conn.failure_reason == "token_refresh_failed"

    @patch('app.core.oauth.token_refresh.refresh_google_token')
    def test_successful_refresh_clears_failures(self, mock_refresh, test_connection):
        """Test that successful token refresh clears previous failures."""
        # Setup - add existing failures
        with get_session() as session:
            conn = session.get(Connection, test_connection.id)
            conn.failure_count = 3
            conn.failure_reason = "token_refresh_failed"
            conn.last_failure_at = datetime.now(timezone.utc) - timedelta(hours=1)
            conn.needs_reauth = True
            conn.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
            session.commit()

        # Setup - make token refresh succeed
        mock_refresh.return_value = {
            'access_token': 'new_access_token',
            'expires_at': datetime.now(timezone.utc) + timedelta(hours=1)
        }

        # Execute
        user_tokens = {'google_analytics': 'fake_refresh_token'}
        platforms = [MCPServer.GOOGLE_ANALYTICS_OFFICIAL]

        result = refresh_tokens_for_platforms(1, platforms, user_tokens)

        # Assert
        with get_session() as session:
            conn = session.get(Connection, test_connection.id)
            assert conn.failure_count == 0, "Failure count should be reset"
            assert conn.failure_reason is None, "Failure reason should be cleared"
            assert conn.needs_reauth is False, "needs_reauth should be cleared"


class TestMCPValidationFailureFlow:
    """Test MCP validation failure logging."""

    @pytest.mark.asyncio
    async def test_mcp_validation_failure_logged(self, test_connection):
        """Test that MCP validation failure is logged to database."""
        # Setup - create mock MCP client that fails validation
        mock_client = AsyncMock()
        mock_client.get_tools.return_value = []  # No tools = validation failure

        connection_ids = {'google_analytics': test_connection.id}
        clients_dict = {'google_analytics': mock_client}

        # Execute
        validator = MCPValidator(clients_dict, connection_ids)
        results = await validator.validate_all()

        # Assert
        assert len(results) == 1
        assert results[0].status == ValidationStatus.FAILED

        # Check database
        with get_session() as session:
            conn = session.get(Connection, test_connection.id)
            assert conn.failure_count == 1, "Failure count should be incremented"
            assert "mcp_validation_failed" in conn.failure_reason, "Failure reason should contain mcp_validation_failed"
            assert conn.last_failure_at is not None

    @pytest.mark.asyncio
    async def test_mcp_validation_success_clears_failures(self, test_connection):
        """Test that successful MCP validation clears previous failures."""
        # Setup - add existing failures
        with get_session() as session:
            conn = session.get(Connection, test_connection.id)
            conn.failure_count = 2
            conn.failure_reason = "mcp_validation_failed: No tools"
            conn.last_failure_at = datetime.now(timezone.utc) - timedelta(hours=1)
            session.commit()

        # Setup - create mock MCP client that succeeds
        mock_client = AsyncMock()
        mock_client.get_tools.return_value = ['run_report', 'get_metadata']
        mock_client.call_tool.return_value = MagicMock(isError=False, content=[])

        connection_ids = {'google_analytics': test_connection.id}
        clients_dict = {'google_analytics': mock_client}

        # Execute
        validator = MCPValidator(clients_dict, connection_ids)
        results = await validator.validate_all()

        # Assert
        assert len(results) == 1
        assert results[0].status == ValidationStatus.SUCCESS

        # Check database
        with get_session() as session:
            conn = session.get(Connection, test_connection.id)
            assert conn.failure_count == 0, "Failure count should be reset"
            assert conn.failure_reason is None, "Failure reason should be cleared"
            assert conn.last_validated_at is not None


class TestMCPClientManagerFailureFlow:
    """Test complete MCP client manager failure flow."""

    @pytest.mark.asyncio
    async def test_manager_fetches_connection_ids(self, test_connection):
        """Test that manager fetches connection IDs for failure logging."""
        # Setup
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
            credentials=credentials
        )

        # Execute
        await manager._fetch_connection_ids()

        # Assert
        assert 'google_analytics' in manager.connection_ids
        assert manager.connection_ids['google_analytics'] == test_connection.id

    @pytest.mark.asyncio
    @patch('app.core.agents.mcp_clients.mcp_client_manager.MCPSelector')
    @patch('app.core.oauth.token_refresh.refresh_google_token')
    async def test_manager_passes_connection_ids_to_validator(
        self,
        mock_refresh,
        mock_selector,
        test_connection
    ):
        """Test that manager passes connection IDs to validator."""
        # Setup
        mock_refresh.return_value = {
            'access_token': 'new_token',
            'expires_at': datetime.now(timezone.utc) + timedelta(hours=1)
        }

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
            credentials=credentials
        )

        # Mock MCP client initialization
        mock_client = AsyncMock()
        mock_client.get_tools.return_value = []
        mock_selector.build_all_server_params.return_value = []

        with patch('app.core.agents.mcp_clients.mcp_client_manager.MCPValidator') as mock_validator_class:
            mock_validator = AsyncMock()
            mock_validator.validate_all.return_value = []
            mock_validator.get_summary.return_value = {'success': 0, 'failed': 0, 'error': 0}
            mock_validator_class.return_value = mock_validator

            # Execute
            manager.clients = mock_client
            await manager._validate_clients()

            # Assert - validator was called with connection_ids
            mock_validator_class.assert_called_once()
            call_args = mock_validator_class.call_args
            assert 'google_analytics' in call_args[0][1]  # connection_ids is second argument


class TestFailureRecoveryFlow:
    """Test failure recovery scenarios."""

    @patch('app.core.oauth.token_refresh.refresh_google_token')
    def test_connection_recovers_after_multiple_failures(self, mock_refresh, test_connection):
        """Test that connection can recover after multiple failures."""
        # Fail 3 times
        for i in range(3):
            mark_needs_reauth(campaigner_id=1, asset_type=AssetType.GA4)

        with get_session() as session:
            conn = session.get(Connection, test_connection.id)
            assert conn.failure_count == 3

        # Now succeed
        with get_session() as session:
            conn = session.get(Connection, test_connection.id)
            conn.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
            session.commit()

        mock_refresh.return_value = {
            'access_token': 'new_token',
            'expires_at': datetime.now(timezone.utc) + timedelta(hours=1)
        }

        user_tokens = {'google_analytics': 'fake_refresh_token'}
        platforms = [MCPServer.GOOGLE_ANALYTICS_OFFICIAL]
        refresh_tokens_for_platforms(1, platforms, user_tokens)

        # Check recovery
        with get_session() as session:
            conn = session.get(Connection, test_connection.id)
            assert conn.failure_count == 0
            assert conn.failure_reason is None
            assert conn.needs_reauth is False

    def test_should_retry_logic_with_database(self, test_connection):
        """Test retry logic integration with database."""
        from app.utils.connection_failure_utils import should_retry_connection

        # Initially should retry
        with get_session() as session:
            conn = session.get(Connection, test_connection.id)
            assert should_retry_connection(conn, max_failures=3) is True

        # After 3 failures, should not retry
        for i in range(3):
            mark_needs_reauth(campaigner_id=1, asset_type=AssetType.GA4)

        with get_session() as session:
            conn = session.get(Connection, test_connection.id)
            assert should_retry_connection(conn, max_failures=3) is False


class TestFailureReasonPersistence:
    """Test that failure reasons are properly persisted."""

    def test_different_failure_types_recorded(self, test_connection):
        """Test that different failure types are recorded correctly."""
        from app.utils.connection_failure_utils import record_connection_failure

        # Token refresh failure
        record_connection_failure(test_connection.id, "token_refresh_failed: invalid_grant")

        with get_session() as session:
            conn = session.get(Connection, test_connection.id)
            assert "token_refresh_failed" in conn.failure_reason
            assert "invalid_grant" in conn.failure_reason

        # MCP validation failure
        record_connection_failure(test_connection.id, "mcp_validation_failed: Invalid credentials")

        with get_session() as session:
            conn = session.get(Connection, test_connection.id)
            assert conn.failure_count == 2
            assert "mcp_validation_failed" in conn.failure_reason

    def test_failure_timestamps_updated(self, test_connection):
        """Test that failure timestamps are properly updated."""
        from app.utils.connection_failure_utils import record_connection_failure

        before = datetime.now(timezone.utc)
        record_connection_failure(test_connection.id, "test_failure")
        after = datetime.now(timezone.utc)

        with get_session() as session:
            conn = session.get(Connection, test_connection.id)
            assert conn.last_failure_at is not None
            assert before <= conn.last_failure_at <= after
