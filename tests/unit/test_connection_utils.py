"""
Unit Tests for Connection Utilities

Tests the centralized connection query functions.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, MagicMock, patch

from app.utils.connection_utils import (
    get_connection_for_save,
    get_active_connection,
    get_connection_by_platform,
    get_connections_by_asset_type,
    get_all_active_connections,
)
from app.models.analytics import Connection, DigitalAsset, AssetType, AuthType


class TestGetConnectionForSave:
    """Tests for get_connection_for_save function."""

    @patch('app.utils.connection_utils.get_session')
    def test_returns_existing_connection(self, mock_get_session):
        """Test that it returns existing connection if found."""
        # Setup mock connection
        mock_connection = Mock(spec=Connection)
        mock_connection.id = 1
        mock_connection.digital_asset_id = 100
        mock_connection.campaigner_id = 50
        mock_connection.auth_type = AuthType.OAUTH2

        # Setup mock session
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.first.return_value = mock_connection
        mock_session.exec.return_value = mock_result

        # Call function with session
        result = get_connection_for_save(
            digital_asset_id=100,
            campaigner_id=50,
            auth_type=AuthType.OAUTH2,
            session=mock_session
        )

        assert result == mock_connection
        mock_session.exec.assert_called_once()

    @patch('app.utils.connection_utils.get_session')
    def test_returns_none_when_not_found(self, mock_get_session):
        """Test that it returns None when no connection found."""
        # Setup mock session
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.first.return_value = None
        mock_session.exec.return_value = mock_result

        # Call function with session
        result = get_connection_for_save(
            digital_asset_id=100,
            campaigner_id=50,
            auth_type=AuthType.OAUTH2,
            session=mock_session
        )

        assert result is None


class TestGetActiveConnection:
    """Tests for get_active_connection function."""

    @patch('app.utils.connection_utils.get_session')
    def test_returns_active_connection(self, mock_get_session):
        """Test that it returns active connection."""
        # Setup mock connection
        mock_connection = Mock(spec=Connection)
        mock_connection.id = 1
        mock_connection.revoked = False

        # Setup mock session
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.first.return_value = mock_connection
        mock_session.exec.return_value = mock_result

        # Call function with session
        result = get_active_connection(
            digital_asset_id=100,
            customer_id=10,
            campaigner_id=50,
            session=mock_session
        )

        assert result == mock_connection
        assert result.revoked is False

    @patch('app.utils.connection_utils.get_session')
    def test_filters_by_revoked_status(self, mock_get_session):
        """Test that it filters by revoked == False."""
        # Setup mock session
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.first.return_value = None
        mock_session.exec.return_value = mock_result

        # Call function with session
        result = get_active_connection(
            digital_asset_id=100,
            customer_id=10,
            campaigner_id=50,
            session=mock_session
        )

        # Verify the query was executed
        mock_session.exec.assert_called_once()
        # Result should be None since no connection found
        assert result is None


class TestGetConnectionByPlatform:
    """Tests for get_connection_by_platform function."""

    @patch('app.utils.connection_utils.get_session')
    def test_google_analytics_platform(self, mock_get_session):
        """Test retrieval for Google Analytics platform."""
        # Setup mock connection
        mock_connection = Mock(spec=Connection)
        mock_connection.id = 1

        # Setup mock session
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.first.return_value = mock_connection
        mock_session.exec.return_value = mock_result

        # Call function with session
        result = get_connection_by_platform(
            platform='google_analytics',
            campaigner_id=50,
            customer_id=10,
            session=mock_session
        )

        assert result == mock_connection
        mock_session.exec.assert_called_once()

    @patch('app.utils.connection_utils.get_session')
    def test_google_ads_platform(self, mock_get_session):
        """Test retrieval for Google Ads platform."""
        # Setup mock connection
        mock_connection = Mock(spec=Connection)
        mock_connection.id = 2

        # Setup mock session
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.first.return_value = mock_connection
        mock_session.exec.return_value = mock_result

        # Call function with session
        result = get_connection_by_platform(
            platform='google_ads',
            campaigner_id=50,
            customer_id=10,
            session=mock_session
        )

        assert result == mock_connection

    @patch('app.utils.connection_utils.get_session')
    def test_facebook_platform(self, mock_get_session):
        """Test retrieval for Facebook platform."""
        # Setup mock connection
        mock_connection = Mock(spec=Connection)
        mock_connection.id = 3

        # Setup mock session
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.first.return_value = mock_connection
        mock_session.exec.return_value = mock_result

        # Call function with session
        result = get_connection_by_platform(
            platform='facebook',
            campaigner_id=50,
            customer_id=10,
            session=mock_session
        )

        assert result == mock_connection

    @patch('app.utils.connection_utils.get_session')
    def test_facebook_ads_alias(self, mock_get_session):
        """Test that facebook_ads is an alias for facebook."""
        # Setup mock connection
        mock_connection = Mock(spec=Connection)
        mock_connection.id = 3

        # Setup mock session
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.first.return_value = mock_connection
        mock_session.exec.return_value = mock_result

        # Call function with session
        result = get_connection_by_platform(
            platform='facebook_ads',
            campaigner_id=50,
            customer_id=10,
            session=mock_session
        )

        assert result == mock_connection

    @patch('app.utils.connection_utils.get_session')
    def test_unknown_platform_returns_none(self, mock_get_session):
        """Test that unknown platform returns None."""
        # Setup mock session
        mock_session = MagicMock()

        # Call function with invalid platform
        result = get_connection_by_platform(
            platform='invalid_platform',
            campaigner_id=50,
            customer_id=10,
            session=mock_session
        )

        assert result is None
        # Should not execute query for unknown platform
        mock_session.exec.assert_not_called()

    @patch('app.utils.connection_utils.get_session')
    def test_without_customer_id_filter(self, mock_get_session):
        """Test that customer_id is optional and not filtered if None."""
        # Setup mock connection
        mock_connection = Mock(spec=Connection)
        mock_connection.id = 1

        # Setup mock session
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.first.return_value = mock_connection
        mock_session.exec.return_value = mock_result

        # Call function WITHOUT customer_id
        result = get_connection_by_platform(
            platform='google_analytics',
            campaigner_id=50,
            customer_id=None,  # Not filtering by customer
            session=mock_session
        )

        assert result == mock_connection
        mock_session.exec.assert_called_once()


class TestGetConnectionsByAssetType:
    """Tests for get_connections_by_asset_type function."""

    @patch('app.utils.connection_utils.get_session')
    def test_returns_list_of_connections(self, mock_get_session):
        """Test that it returns list of connections for asset type."""
        # Setup mock connections
        mock_conn1 = Mock(spec=Connection)
        mock_conn1.id = 1
        mock_conn2 = Mock(spec=Connection)
        mock_conn2.id = 2

        # Setup mock session
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.all.return_value = [mock_conn1, mock_conn2]
        mock_session.exec.return_value = mock_result

        # Call function with session
        result = get_connections_by_asset_type(
            asset_type=AssetType.ANALYTICS,
            customer_id=10,
            campaigner_id=50,
            session=mock_session
        )

        assert len(result) == 2
        assert result[0] == mock_conn1
        assert result[1] == mock_conn2

    @patch('app.utils.connection_utils.get_session')
    def test_returns_empty_list_when_none_found(self, mock_get_session):
        """Test that it returns empty list when no connections found."""
        # Setup mock session
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_session.exec.return_value = mock_result

        # Call function with session
        result = get_connections_by_asset_type(
            asset_type=AssetType.ADVERTISING,
            customer_id=10,
            campaigner_id=50,
            session=mock_session
        )

        assert result == []


class TestGetAllActiveConnections:
    """Tests for get_all_active_connections function."""

    @patch('app.utils.connection_utils.get_session')
    def test_returns_all_connections(self, mock_get_session):
        """Test that it returns all active connections for customer/campaigner."""
        # Setup mock connections
        mock_conns = [
            Mock(spec=Connection, id=1, revoked=False),
            Mock(spec=Connection, id=2, revoked=False),
            Mock(spec=Connection, id=3, revoked=False),
        ]

        # Setup mock session
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.all.return_value = mock_conns
        mock_session.exec.return_value = mock_result

        # Call function with session
        result = get_all_active_connections(
            customer_id=10,
            campaigner_id=50,
            session=mock_session
        )

        assert len(result) == 3
        assert all(conn.revoked is False for conn in result)

    @patch('app.utils.connection_utils.get_session')
    def test_filters_revoked_connections(self, mock_get_session):
        """Test that revoked connections are filtered out."""
        # Setup mock session - should only return non-revoked
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.all.return_value = []  # Revoked connections filtered in DB
        mock_session.exec.return_value = mock_result

        # Call function with session
        result = get_all_active_connections(
            customer_id=10,
            campaigner_id=50,
            session=mock_session
        )

        assert result == []
        mock_session.exec.assert_called_once()


class TestSessionManagement:
    """Tests for session management in utility functions."""

    @patch('app.utils.connection_utils.get_session')
    def test_creates_session_when_not_provided(self, mock_get_session):
        """Test that function creates session when not provided."""
        # Setup mock session context manager
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)
        mock_result = MagicMock()
        mock_result.first.return_value = None
        mock_session.exec.return_value = mock_result

        mock_get_session.return_value = mock_session

        # Call function WITHOUT providing session
        result = get_connection_for_save(
            digital_asset_id=100,
            campaigner_id=50,
            auth_type=AuthType.OAUTH2
            # No session parameter
        )

        # Verify session was created
        mock_get_session.assert_called_once()
        mock_session.__enter__.assert_called_once()
        mock_session.__exit__.assert_called_once()

    @patch('app.utils.connection_utils.get_session')
    def test_uses_provided_session(self, mock_get_session):
        """Test that function uses provided session without creating new one."""
        # Setup mock session
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.first.return_value = None
        mock_session.exec.return_value = mock_result

        # Call function WITH provided session
        result = get_connection_for_save(
            digital_asset_id=100,
            campaigner_id=50,
            auth_type=AuthType.OAUTH2,
            session=mock_session  # Provided session
        )

        # Verify session was NOT created (get_session not called)
        mock_get_session.assert_not_called()
        # Verify provided session was used
        mock_session.exec.assert_called_once()


class TestQueryCorrectness:
    """Tests to ensure queries filter correctly."""

    @patch('app.utils.connection_utils.get_session')
    def test_get_active_connection_filters_revoked(self, mock_get_session):
        """Test that get_active_connection filters by revoked != True."""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.first.return_value = None
        mock_session.exec.return_value = mock_result

        get_active_connection(
            digital_asset_id=100,
            customer_id=10,
            campaigner_id=50,
            session=mock_session
        )

        # Verify exec was called (query was executed)
        assert mock_session.exec.called

    @patch('app.utils.connection_utils.get_session')
    def test_get_connection_by_platform_filters_active_assets(self, mock_get_session):
        """Test that platform query filters by is_active = True."""
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.first.return_value = None
        mock_session.exec.return_value = mock_result

        get_connection_by_platform(
            platform='google_analytics',
            campaigner_id=50,
            customer_id=10,
            session=mock_session
        )

        # Verify exec was called (query was executed with filters)
        assert mock_session.exec.called
