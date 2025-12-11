"""
Unit Tests for Google Ads Service refresh token handling

Tests that the Google Ads service properly handles None/empty refresh tokens
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from app.services.google_ads_service import GoogleAdsService


class TestGoogleAdsServiceRefreshTokenHandling:
    """Tests for Google Ads service refresh token handling."""

    def test_encrypt_token_handles_none(self):
        """Test that _encrypt_token returns None for None input."""
        service = GoogleAdsService()
        result = service._encrypt_token(None)
        assert result is None

    def test_encrypt_token_handles_empty_string(self):
        """Test that _encrypt_token returns None for empty string input."""
        service = GoogleAdsService()
        result = service._encrypt_token("")
        assert result is None

    def test_encrypt_token_encrypts_valid_token(self):
        """Test that _encrypt_token encrypts valid tokens."""
        service = GoogleAdsService()
        result = service._encrypt_token("valid_token")
        assert result is not None
        assert isinstance(result, bytes)

    @patch("app.services.digital_asset_service.upsert_digital_asset")
    @patch("app.services.google_ads_service.get_session")
    async def test_save_connection_with_none_refresh_token(
        self, mock_get_session, mock_upsert
    ):
        """Test that save_google_ads_connection handles None refresh_token."""
        # Setup mocks
        mock_session = Mock()
        mock_get_session.return_value.__enter__ = Mock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = Mock(return_value=None)

        mock_digital_asset = Mock()
        mock_digital_asset.id = 123
        mock_upsert.return_value = mock_digital_asset

        # Mock get_connection_for_save to return None (new connection)
        with patch(
            "app.services.google_ads_service.get_connection_for_save", return_value=None
        ):
            service = GoogleAdsService()

            result = await service.save_google_ads_connection(
                campaigner_id=1,
                customer_id=1,
                account_id="123-456-7890",
                account_name="Test Account",
                access_token="access_token_123",
                refresh_token=None,  # None refresh token
                expires_in=3600,
                account_email="test@example.com",
            )

            # Should succeed and return connection info
            assert result is not None
            assert "connection_id" in result
