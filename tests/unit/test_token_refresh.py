"""
Unit tests for OAuth token refresh functionality
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch, MagicMock
from app.core.oauth.token_refresh import (
    is_token_expired,
    refresh_google_token,
    refresh_facebook_token,
    OAuthRefreshError,
)
from app.api.v1.routes.connections import (
    refresh_all_tokens,
    BulkRefreshResponse,
    RefreshResult,
)


class TestTokenExpiration:
    """Test token expiration checking."""

    def test_expired_token(self):
        """Test that expired token is detected."""
        expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        assert is_token_expired(expires_at) is True

    def test_valid_token(self):
        """Test that valid token is not expired."""
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        assert is_token_expired(expires_at) is False

    def test_token_within_buffer(self):
        """Test that token within buffer period is considered expired."""
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=3)
        assert is_token_expired(expires_at, buffer_minutes=5) is True

    def test_token_outside_buffer(self):
        """Test that token outside buffer period is not expired."""
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
        assert is_token_expired(expires_at, buffer_minutes=5) is False

    def test_none_expires_at(self):
        """Test that None expires_at is considered expired."""
        assert is_token_expired(None) is True

    def test_naive_datetime_expires_at(self):
        """Test that timezone-naive expires_at is handled correctly."""
        # Create a naive datetime (no timezone info) - assume UTC for this test
        now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
        expires_at_naive = now_utc + timedelta(hours=1)

        # Should not raise TypeError and should work correctly
        assert is_token_expired(expires_at_naive) is False

    def test_naive_datetime_expired(self):
        """Test that timezone-naive expired datetime is detected."""
        # Create a naive datetime in the past - assume UTC for this test
        now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
        expires_at_naive = now_utc - timedelta(hours=1)

        # Should not raise TypeError and should detect expiration
        assert is_token_expired(expires_at_naive) is True


class TestGoogleTokenRefresh:
    """Test Google OAuth token refresh."""

    @patch("requests.post")
    def test_successful_refresh(self, mock_post):
        """Test successful Google token refresh."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "new_access_token",
            "expires_in": 3600,
        }
        mock_post.return_value = mock_response

        result = refresh_google_token("test_refresh_token")

        assert result["access_token"] == "new_access_token"
        assert result["expires_in"] == 3600
        assert "expires_at" in result
        assert isinstance(result["expires_at"], datetime)

        # Verify API call
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[0][0] == "https://oauth2.googleapis.com/token"
        assert call_args[1]["data"]["refresh_token"] == "test_refresh_token"
        assert call_args[1]["data"]["grant_type"] == "refresh_token"

    @patch("requests.post")
    def test_refresh_failure_invalid_grant(self, mock_post):
        """Test Google token refresh failure with invalid_grant error."""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = {
            "error": "invalid_grant",
            "error_description": "Token has been expired or revoked",
        }
        mock_post.return_value = mock_response

        with pytest.raises(OAuthRefreshError) as exc_info:
            refresh_google_token("invalid_refresh_token")

        assert exc_info.value.provider == "google"
        assert exc_info.value.error == "invalid_grant"
        assert "expired or revoked" in exc_info.value.error_description

    @patch("requests.post")
    def test_refresh_network_error(self, mock_post):
        """Test Google token refresh with network error."""
        mock_post.side_effect = Exception("Connection timeout")

        with pytest.raises(OAuthRefreshError) as exc_info:
            refresh_google_token("test_refresh_token")

        assert exc_info.value.provider == "google"
        assert exc_info.value.error == "network_error"


class TestFacebookTokenRefresh:
    """Test Facebook OAuth token refresh."""

    @patch("requests.get")
    def test_successful_refresh(self, mock_get):
        """Test successful Facebook token refresh."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "new_fb_token",
            "expires_in": 5184000,  # 60 days
        }
        mock_get.return_value = mock_response

        result = refresh_facebook_token("old_fb_token")

        assert result["access_token"] == "new_fb_token"
        assert result["expires_in"] == 5184000
        assert "expires_at" in result

        # Verify API call
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        assert "graph.facebook.com" in call_args[0][0]
        assert call_args[1]["params"]["fb_exchange_token"] == "old_fb_token"

    @patch("requests.get")
    def test_refresh_failure(self, mock_get):
        """Test Facebook token refresh failure."""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = {
            "error": {"type": "OAuthException", "message": "Invalid OAuth access token"}
        }
        mock_get.return_value = mock_response

        with pytest.raises(OAuthRefreshError) as exc_info:
            refresh_facebook_token("invalid_token")

        assert exc_info.value.provider == "facebook"
        assert exc_info.value.error == "OAuthException"
        assert "Invalid OAuth access token" in exc_info.value.error_description


class TestBulkTokenRefresh:
    """Test bulk token refresh endpoint functionality."""

    @patch("app.api.v1.routes.connections.get_session")
    @patch("app.api.v1.routes.connections.refresh_tokens_for_platforms")
    @patch("app.api.v1.routes.connections.decrypt_token")
    @patch("app.api.v1.routes.connections.record_connection_failure")
    @patch("app.api.v1.routes.connections.ClickUpService")
    async def test_bulk_refresh_success(
        self,
        mock_clickup,
        mock_record_failure,
        mock_decrypt,
        mock_refresh_platforms,
        mock_get_session,
    ):
        """Test successful bulk token refresh."""
        # Mock database session and connections
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__.return_value = mock_session

        # Mock connection and asset data
        mock_connection = MagicMock()
        mock_connection.id = 1
        mock_connection.refresh_token_enc = b"encrypted_refresh_token"
        mock_connection.access_token_enc = b"encrypted_access_token"
        mock_connection.revoked = False

        mock_asset = MagicMock()
        mock_asset.name = "Test Google Analytics"
        mock_asset.asset_type = MagicMock()
        mock_asset.asset_type.value = "GA4"

        mock_result = MagicMock()
        mock_result.all.return_value = [(mock_connection, mock_asset)]
        mock_session.exec.return_value = mock_result

        # Mock token decryption
        mock_decrypt.return_value = "decrypted_token"

        # Mock successful token refresh
        mock_refresh_platforms.return_value = {"google_analytics": "new_token"}

        # Mock current user
        mock_current_user = MagicMock()
        mock_current_user.id = 123

        # Call the function
        result = await refresh_all_tokens(mock_current_user)

        # Verify result structure
        assert isinstance(result, BulkRefreshResponse)
        assert result.total_connections == 1
        assert result.successful_refreshes == 1
        assert result.failed_refreshes == 0
        assert result.invalidated_connections == 0
        assert result.clickup_tasks_created == 0
        assert len(result.results) == 1

        refresh_result = result.results[0]
        assert isinstance(refresh_result, RefreshResult)
        assert refresh_result.connection_id == 1
        assert refresh_result.success is True
        assert refresh_result.invalidated is False
        assert refresh_result.clickup_task_created is False

    @patch("app.api.v1.routes.connections.get_session")
    @patch("app.api.v1.routes.connections.refresh_tokens_for_platforms")
    @patch("app.api.v1.routes.connections.decrypt_token")
    @patch("app.api.v1.routes.connections.record_connection_failure")
    @patch("app.api.v1.routes.connections.ClickUpService")
    async def test_bulk_refresh_failure_with_invalidation(
        self,
        mock_clickup,
        mock_record_failure,
        mock_decrypt,
        mock_refresh_platforms,
        mock_get_session,
    ):
        """Test bulk token refresh with failure leading to invalidation."""
        # Mock database session and connections
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__.return_value = mock_session

        # Mock connection and asset data
        mock_connection = MagicMock()
        mock_connection.id = 2
        mock_connection.refresh_token_enc = b"encrypted_refresh_token"
        mock_connection.access_token_enc = b"encrypted_access_token"
        mock_connection.revoked = False

        mock_asset = MagicMock()
        mock_asset.name = "Test Facebook Ads"
        mock_asset.asset_type = MagicMock()
        mock_asset.asset_type.value = "FACEBOOK_ADS"

        mock_result = MagicMock()
        mock_result.all.return_value = [(mock_connection, mock_asset)]
        mock_session.exec.return_value = mock_result

        # Mock token decryption
        mock_decrypt.return_value = "decrypted_token"

        # Mock failed token refresh (empty result indicates failure)
        mock_refresh_platforms.return_value = {}

        # Mock ClickUp service
        mock_clickup_instance = MagicMock()
        mock_clickup.return_value = mock_clickup_instance
        mock_clickup_instance.create_task.return_value = {
            "id": "task_123",
            "url": "https://clickup.com/task_123",
        }

        # Mock current user
        mock_current_user = MagicMock()
        mock_current_user.id = 123

        # Call the function
        result = await refresh_all_tokens(mock_current_user)

        # Verify result structure
        assert isinstance(result, BulkRefreshResponse)
        assert result.total_connections == 1
        assert result.successful_refreshes == 0
        assert result.failed_refreshes == 1
        assert result.invalidated_connections == 1
        assert result.clickup_tasks_created == 1
        assert len(result.results) == 1

        refresh_result = result.results[0]
        assert isinstance(refresh_result, RefreshResult)
        assert refresh_result.connection_id == 2
        assert refresh_result.success is False
        assert refresh_result.invalidated is True
        assert refresh_result.clickup_task_created is True

        # Verify connection was marked as revoked
        assert mock_connection.revoked is True
        assert mock_connection.needs_reauth is True

        # Verify ClickUp task was created
        mock_clickup_instance.create_task.assert_called_once()

    @patch("app.api.v1.routes.connections.get_session")
    @patch("app.api.v1.routes.connections.decrypt_token")
    async def test_bulk_refresh_decryption_failure(
        self, mock_decrypt, mock_get_session
    ):
        """Test bulk token refresh with decryption failure."""
        # Mock database session and connections
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__.return_value = mock_session

        # Mock connection and asset data
        mock_connection = MagicMock()
        mock_connection.id = 3
        mock_connection.refresh_token_enc = b"encrypted_refresh_token"
        mock_connection.revoked = False

        mock_asset = MagicMock()
        mock_asset.name = "Test Connection"
        mock_asset.asset_type = MagicMock()
        mock_asset.asset_type.value = "GA4"

        mock_result = MagicMock()
        mock_result.all.return_value = [(mock_connection, mock_asset)]
        mock_session.exec.return_value = mock_result

        # Mock decryption failure
        mock_decrypt.side_effect = Exception("Decryption failed")

        # Mock current user
        mock_current_user = MagicMock()
        mock_current_user.id = 123

        # Call the function
        result = await refresh_all_tokens(mock_current_user)

        # Verify result structure
        assert isinstance(result, BulkRefreshResponse)
        assert result.total_connections == 1
        assert result.successful_refreshes == 0
        assert result.failed_refreshes == 1
        assert result.invalidated_connections == 1
        assert result.clickup_tasks_created == 1
        assert len(result.results) == 1

        refresh_result = result.results[0]
        assert refresh_result.success is False
        assert "Token decryption failed" in refresh_result.message

    @patch("app.api.v1.routes.connections.get_session")
    async def test_bulk_refresh_no_connections(self, mock_get_session):
        """Test bulk token refresh with no connections."""
        # Mock database session with no connections
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__.return_value = mock_session
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_session.exec.return_value = mock_result

        # Mock current user
        mock_current_user = MagicMock()
        mock_current_user.id = 123

        # Call the function
        result = await refresh_all_tokens(mock_current_user)

        # Verify result structure
        assert isinstance(result, BulkRefreshResponse)
        assert result.total_connections == 0
        assert result.successful_refreshes == 0
        assert result.failed_refreshes == 0
        assert result.invalidated_connections == 0
        assert result.clickup_tasks_created == 0
        assert len(result.results) == 0
