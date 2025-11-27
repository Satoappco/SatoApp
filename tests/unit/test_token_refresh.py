"""
Unit tests for OAuth token refresh functionality
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from app.core.oauth.token_refresh import (
    is_token_expired,
    refresh_google_token,
    refresh_facebook_token,
    OAuthRefreshError
)


class TestTokenExpiration:
    """Test token expiration checking."""

    def test_expired_token(self):
        """Test that expired token is detected."""
        expires_at = datetime.utcnow() - timedelta(hours=1)
        assert is_token_expired(expires_at) is True

    def test_valid_token(self):
        """Test that valid token is not expired."""
        expires_at = datetime.utcnow() + timedelta(hours=1)
        assert is_token_expired(expires_at) is False

    def test_token_within_buffer(self):
        """Test that token within buffer period is considered expired."""
        expires_at = datetime.utcnow() + timedelta(minutes=3)
        assert is_token_expired(expires_at, buffer_minutes=5) is True

    def test_token_outside_buffer(self):
        """Test that token outside buffer period is not expired."""
        expires_at = datetime.utcnow() + timedelta(minutes=10)
        assert is_token_expired(expires_at, buffer_minutes=5) is False

    def test_none_expires_at(self):
        """Test that None expires_at is considered expired."""
        assert is_token_expired(None) is True


class TestGoogleTokenRefresh:
    """Test Google OAuth token refresh."""

    @patch('requests.post')
    def test_successful_refresh(self, mock_post):
        """Test successful Google token refresh."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'access_token': 'new_access_token',
            'expires_in': 3600
        }
        mock_post.return_value = mock_response

        result = refresh_google_token('test_refresh_token')

        assert result['access_token'] == 'new_access_token'
        assert result['expires_in'] == 3600
        assert 'expires_at' in result
        assert isinstance(result['expires_at'], datetime)

        # Verify API call
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[0][0] == 'https://oauth2.googleapis.com/token'
        assert call_args[1]['data']['refresh_token'] == 'test_refresh_token'
        assert call_args[1]['data']['grant_type'] == 'refresh_token'

    @patch('requests.post')
    def test_refresh_failure_invalid_grant(self, mock_post):
        """Test Google token refresh failure with invalid_grant error."""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = {
            'error': 'invalid_grant',
            'error_description': 'Token has been expired or revoked'
        }
        mock_post.return_value = mock_response

        with pytest.raises(OAuthRefreshError) as exc_info:
            refresh_google_token('invalid_refresh_token')

        assert exc_info.value.provider == 'google'
        assert exc_info.value.error == 'invalid_grant'
        assert 'expired or revoked' in exc_info.value.error_description

    @patch('requests.post')
    def test_refresh_network_error(self, mock_post):
        """Test Google token refresh with network error."""
        mock_post.side_effect = Exception("Connection timeout")

        with pytest.raises(OAuthRefreshError) as exc_info:
            refresh_google_token('test_refresh_token')

        assert exc_info.value.provider == 'google'
        assert exc_info.value.error == 'network_error'


class TestFacebookTokenRefresh:
    """Test Facebook OAuth token refresh."""

    @patch('requests.get')
    def test_successful_refresh(self, mock_get):
        """Test successful Facebook token refresh."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'access_token': 'new_fb_token',
            'expires_in': 5184000  # 60 days
        }
        mock_get.return_value = mock_response

        result = refresh_facebook_token('old_fb_token')

        assert result['access_token'] == 'new_fb_token'
        assert result['expires_in'] == 5184000
        assert 'expires_at' in result

        # Verify API call
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        assert 'graph.facebook.com' in call_args[0][0]
        assert call_args[1]['params']['fb_exchange_token'] == 'old_fb_token'

    @patch('requests.get')
    def test_refresh_failure(self, mock_get):
        """Test Facebook token refresh failure."""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = {
            'error': {
                'type': 'OAuthException',
                'message': 'Invalid OAuth access token'
            }
        }
        mock_get.return_value = mock_response

        with pytest.raises(OAuthRefreshError) as exc_info:
            refresh_facebook_token('invalid_token')

        assert exc_info.value.provider == 'facebook'
        assert exc_info.value.error == 'OAuthException'
        assert 'Invalid OAuth access token' in exc_info.value.error_description
