"""
Unit Tests for Connection Failure Tracking

Tests the connection failure tracking utilities to ensure failures and successes
are properly recorded in the database.
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

from app.utils.connection_failure_utils import (
    record_connection_failure,
    record_connection_success,
    get_connection_by_digital_asset_id,
    get_failing_connections,
    should_retry_connection,
)
from app.models.analytics import Connection, AuthType


@pytest.fixture
def mock_connection():
    """Create a mock connection for testing."""
    return Connection(
        id=123,
        digital_asset_id=1,
        customer_id=1,
        campaigner_id=1,
        auth_type=AuthType.OAUTH2,
        revoked=False,
        failure_count=0,
        failure_reason=None,
        last_failure_at=None,
        needs_reauth=False
    )


@pytest.fixture
def failing_connection():
    """Create a connection with existing failures."""
    return Connection(
        id=456,
        digital_asset_id=2,
        customer_id=1,
        campaigner_id=1,
        auth_type=AuthType.OAUTH2,
        revoked=False,
        failure_count=3,
        failure_reason="token_refresh_failed",
        last_failure_at=datetime.now(timezone.utc) - timedelta(hours=1),
        needs_reauth=True
    )


class TestRecordConnectionFailure:
    """Tests for record_connection_failure function."""

    @patch('app.utils.connection_failure_utils.get_session')
    def test_records_first_failure(self, mock_get_session, mock_connection):
        """Test that first failure increments count to 1."""
        # Setup
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__.return_value = mock_session
        mock_session.get.return_value = mock_connection

        # Execute
        result = record_connection_failure(123, "token_refresh_failed")

        # Assert
        assert result is True
        assert mock_connection.failure_count == 1
        assert mock_connection.failure_reason == "token_refresh_failed"
        assert mock_connection.last_failure_at is not None
        mock_session.commit.assert_called_once()

    @patch('app.utils.connection_failure_utils.get_session')
    def test_increments_existing_failure_count(self, mock_get_session, failing_connection):
        """Test that subsequent failures increment the count."""
        # Setup
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__.return_value = mock_session
        mock_session.get.return_value = failing_connection
        original_count = failing_connection.failure_count

        # Execute
        result = record_connection_failure(456, "mcp_validation_failed")

        # Assert
        assert result is True
        assert failing_connection.failure_count == original_count + 1
        assert failing_connection.failure_reason == "mcp_validation_failed"

    @patch('app.utils.connection_failure_utils.get_session')
    def test_sets_needs_reauth_when_requested(self, mock_get_session, mock_connection):
        """Test that needs_reauth flag is set when requested."""
        # Setup
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__.return_value = mock_session
        mock_session.get.return_value = mock_connection

        # Execute
        result = record_connection_failure(
            123,
            "token_refresh_failed",
            also_set_needs_reauth=True
        )

        # Assert
        assert result is True
        assert mock_connection.needs_reauth is True

    @patch('app.utils.connection_failure_utils.get_session')
    def test_handles_missing_connection(self, mock_get_session):
        """Test graceful handling when connection doesn't exist."""
        # Setup
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__.return_value = mock_session
        mock_session.get.return_value = None

        # Execute
        result = record_connection_failure(999, "test_failure")

        # Assert
        assert result is False
        mock_session.commit.assert_not_called()

    @patch('app.utils.connection_failure_utils.get_session')
    def test_handles_database_error(self, mock_get_session, mock_connection):
        """Test graceful handling of database errors."""
        # Setup
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__.return_value = mock_session
        mock_session.get.return_value = mock_connection
        mock_session.commit.side_effect = Exception("Database error")

        # Execute
        result = record_connection_failure(123, "test_failure")

        # Assert
        assert result is False


class TestRecordConnectionSuccess:
    """Tests for record_connection_success function."""

    @patch('app.utils.connection_failure_utils.get_session')
    def test_resets_failure_count(self, mock_get_session, failing_connection):
        """Test that success resets failure count to 0."""
        # Setup
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__.return_value = mock_session
        mock_session.get.return_value = failing_connection

        # Execute
        result = record_connection_success(456, reset_failure_count=True)

        # Assert
        assert result is True
        assert failing_connection.failure_count == 0
        assert failing_connection.failure_reason is None
        assert failing_connection.last_failure_at is None

    @patch('app.utils.connection_failure_utils.get_session')
    def test_clears_needs_reauth(self, mock_get_session, failing_connection):
        """Test that success clears needs_reauth flag."""
        # Setup
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__.return_value = mock_session
        mock_session.get.return_value = failing_connection
        failing_connection.needs_reauth = True

        # Execute
        result = record_connection_success(456)

        # Assert
        assert result is True
        assert failing_connection.needs_reauth is False

    @patch('app.utils.connection_failure_utils.get_session')
    def test_updates_validation_timestamp(self, mock_get_session, mock_connection):
        """Test that success updates last_validated_at timestamp."""
        # Setup
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__.return_value = mock_session
        mock_session.get.return_value = mock_connection
        before = datetime.now(timezone.utc)

        # Execute
        result = record_connection_success(123)

        # Assert
        assert result is True
        assert mock_connection.last_validated_at is not None
        assert mock_connection.last_validated_at >= before

    @patch('app.utils.connection_failure_utils.get_session')
    def test_preserves_failure_count_when_requested(self, mock_get_session, failing_connection):
        """Test that failure count can be preserved if requested."""
        # Setup
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__.return_value = mock_session
        mock_session.get.return_value = failing_connection
        original_count = failing_connection.failure_count

        # Execute
        result = record_connection_success(456, reset_failure_count=False)

        # Assert
        assert result is True
        assert failing_connection.failure_count == original_count


class TestGetConnectionByDigitalAssetId:
    """Tests for get_connection_by_digital_asset_id function."""

    @patch('app.utils.connection_failure_utils.get_session')
    def test_finds_connection_by_asset_id(self, mock_get_session, mock_connection):
        """Test finding connection by digital asset ID."""
        # Setup
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__.return_value = mock_session
        mock_session.exec.return_value.first.return_value = mock_connection

        # Execute
        result = get_connection_by_digital_asset_id(1)

        # Assert
        assert result == mock_connection

    @patch('app.utils.connection_failure_utils.get_session')
    def test_filters_by_campaigner_id(self, mock_get_session, mock_connection):
        """Test filtering by campaigner ID when provided."""
        # Setup
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__.return_value = mock_session
        mock_session.exec.return_value.first.return_value = mock_connection

        # Execute
        result = get_connection_by_digital_asset_id(1, campaigner_id=1)

        # Assert
        assert result == mock_connection

    @patch('app.utils.connection_failure_utils.get_session')
    def test_excludes_revoked_connections(self, mock_get_session):
        """Test that revoked connections are not returned."""
        # Setup
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__.return_value = mock_session
        mock_session.exec.return_value.first.return_value = None

        # Execute
        result = get_connection_by_digital_asset_id(1)

        # Assert
        assert result is None


class TestGetFailingConnections:
    """Tests for get_failing_connections function."""

    @patch('app.utils.connection_failure_utils.get_session')
    def test_returns_connections_with_failures(self, mock_get_session, failing_connection):
        """Test retrieving connections with failures."""
        # Setup
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__.return_value = mock_session
        mock_session.exec.return_value.all.return_value = [failing_connection]

        # Execute
        result = get_failing_connections()

        # Assert
        assert len(result) == 1
        assert result[0] == failing_connection

    @patch('app.utils.connection_failure_utils.get_session')
    def test_filters_by_customer_id(self, mock_get_session, failing_connection):
        """Test filtering by customer ID."""
        # Setup
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__.return_value = mock_session
        mock_session.exec.return_value.all.return_value = [failing_connection]

        # Execute
        result = get_failing_connections(customer_id=1)

        # Assert
        assert len(result) == 1

    @patch('app.utils.connection_failure_utils.get_session')
    def test_respects_min_failure_count(self, mock_get_session):
        """Test minimum failure count threshold."""
        # Setup
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__.return_value = mock_session
        mock_session.exec.return_value.all.return_value = []

        # Execute
        result = get_failing_connections(min_failure_count=5)

        # Assert
        assert len(result) == 0


class TestShouldRetryConnection:
    """Tests for should_retry_connection function."""

    def test_allows_retry_below_threshold(self, failing_connection):
        """Test that retry is allowed when below max failures."""
        failing_connection.failure_count = 2
        assert should_retry_connection(failing_connection, max_failures=3) is True

    def test_prevents_retry_at_threshold(self, failing_connection):
        """Test that retry is prevented when at max failures."""
        failing_connection.failure_count = 3
        assert should_retry_connection(failing_connection, max_failures=3) is False

    def test_prevents_retry_above_threshold(self, failing_connection):
        """Test that retry is prevented when above max failures."""
        failing_connection.failure_count = 5
        assert should_retry_connection(failing_connection, max_failures=3) is False

    def test_allows_retry_with_no_failures(self, mock_connection):
        """Test that retry is allowed with no previous failures."""
        mock_connection.failure_count = 0
        assert should_retry_connection(mock_connection, max_failures=3) is True

    def test_handles_none_failure_count(self, mock_connection):
        """Test handling of None failure count."""
        mock_connection.failure_count = None
        assert should_retry_connection(mock_connection, max_failures=3) is True


class TestFailureReasonFormats:
    """Tests for different failure reason formats."""

    @patch('app.utils.connection_failure_utils.get_session')
    def test_token_refresh_failure_format(self, mock_get_session, mock_connection):
        """Test token refresh failure reason format."""
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__.return_value = mock_session
        mock_session.get.return_value = mock_connection

        record_connection_failure(123, "token_refresh_failed: invalid_grant")

        assert "token_refresh_failed" in mock_connection.failure_reason
        assert "invalid_grant" in mock_connection.failure_reason

    @patch('app.utils.connection_failure_utils.get_session')
    def test_mcp_validation_failure_format(self, mock_get_session, mock_connection):
        """Test MCP validation failure reason format."""
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__.return_value = mock_session
        mock_session.get.return_value = mock_connection

        record_connection_failure(123, "mcp_validation_failed: Invalid credentials")

        assert "mcp_validation_failed" in mock_connection.failure_reason
        assert "Invalid credentials" in mock_connection.failure_reason

    @patch('app.utils.connection_failure_utils.get_session')
    def test_truncates_long_failure_reasons(self, mock_get_session, mock_connection):
        """Test that very long failure reasons are handled."""
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__.return_value = mock_session
        mock_session.get.return_value = mock_connection

        long_reason = "x" * 300
        record_connection_failure(123, long_reason)

        # Reason should be set even if truncated by database
        assert mock_connection.failure_reason is not None
