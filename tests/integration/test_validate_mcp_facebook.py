"""Test validate_mcp.py script with Facebook/Meta Ads support."""

import pytest
from unittest.mock import Mock, patch
from app.core.agents.graph.agents import AnalyticsCrewPlaceholder


def test_fetch_meta_ads_token():
    """Test fetching Meta Ads credentials from database."""
    # Mock database connection and data
    with patch('app.core.agents.graph.agents.get_session') as mock_session:
        # Setup mock
        mock_context = Mock()
        mock_session.return_value.__enter__ = Mock(return_value=mock_context)
        mock_session.return_value.__exit__ = Mock(return_value=False)

        # Mock digital asset
        mock_fb_asset = Mock()
        mock_fb_asset.id = 1
        mock_fb_asset.asset_type = "FACEBOOK_ADS"
        mock_fb_asset.meta = {"ad_account_id": "act_123456789"}

        # Mock connection
        mock_connection = Mock()
        mock_connection.access_token_enc = b"encrypted_access_token"

        # Mock database queries
        mock_context.exec = Mock()
        mock_context.exec.return_value.first = Mock(side_effect=[
            mock_fb_asset,  # First call returns FB asset
            mock_connection  # Second call returns connection
        ])

        # Mock decryption
        with patch('app.core.agents.graph.agents.google_ads_service._decrypt_token') as mock_decrypt:
            mock_decrypt.return_value = "decrypted_access_token"

            # Test
            analytics_crew = AnalyticsCrewPlaceholder(llm=None)
            result = analytics_crew._fetch_meta_ads_token(customer_id=1, campaigner_id=1)

            # Verify
            assert result is not None
            assert result["access_token"] == "decrypted_access_token"
            assert result["ad_account_id"] == "act_123456789"


def test_fetch_google_ads_token():
    """Test fetching Google Ads credentials from database."""
    # Mock database connection and data
    with patch('app.core.agents.graph.agents.get_session') as mock_session:
        # Setup mock
        mock_context = Mock()
        mock_session.return_value.__enter__ = Mock(return_value=mock_context)
        mock_session.return_value.__exit__ = Mock(return_value=False)

        # Mock digital asset
        mock_gads_asset = Mock()
        mock_gads_asset.id = 1
        mock_gads_asset.asset_type = "GOOGLE_ADS"
        mock_gads_asset.meta = {"customer_id": "1234567890"}

        # Mock connection
        mock_connection = Mock()
        mock_connection.refresh_token_enc = b"encrypted_refresh_token"

        # Mock database queries
        mock_context.exec = Mock()
        mock_context.exec.return_value.first = Mock(side_effect=[
            mock_gads_asset,  # First call returns Google Ads asset
            mock_connection  # Second call returns connection
        ])

        # Mock decryption and environment variables
        with patch('app.core.agents.graph.agents.google_ads_service._decrypt_token') as mock_decrypt, \
             patch('os.getenv') as mock_getenv:
            mock_decrypt.return_value = "decrypted_refresh_token"

            def getenv_side_effect(key, default=None):
                return {
                    "GOOGLE_CLIENT_ID": "test_client_id",
                    "GOOGLE_CLIENT_SECRET": "test_client_secret",
                    "GOOGLE_ADS_DEVELOPER_TOKEN": "test_developer_token",
                    "GEMINI_API_KEY": "test_gemini_key",
                    "DATABASE_URL": "sqlite:///:memory:",
                }.get(key, default)

            mock_getenv.side_effect = getenv_side_effect

            # Test - don't create AnalyticsCrewPlaceholder (it initializes CrewAI)
            # Just call the method directly after mocking
            with patch('app.core.agents.graph.agents.AnalyticsCrew'):
                analytics_crew = AnalyticsCrewPlaceholder(llm=None)
                result = analytics_crew._fetch_google_ads_token(customer_id=1, campaigner_id=1)

            # Verify
            assert result is not None
            assert result["refresh_token"] == "decrypted_refresh_token"
            assert result["customer_id"] == "1234567890"
            assert result["client_id"] == "test_client_id"
            assert result["developer_token"] == "test_developer_token"


def test_fetch_all_credentials():
    """Test fetching all platform credentials."""
    with patch('app.core.agents.graph.agents.get_session') as mock_session:
        # Setup mock
        mock_context = Mock()
        mock_session.return_value.__enter__ = Mock(return_value=mock_context)
        mock_session.return_value.__exit__ = Mock(return_value=False)

        # Test that all three fetch methods can be called
        analytics_crew = AnalyticsCrewPlaceholder(llm=None)

        # Mock database to return None for all (no credentials)
        mock_context.exec = Mock()
        mock_context.exec.return_value.first = Mock(return_value=None)

        ga_result = analytics_crew._fetch_google_analytics_token(customer_id=1, campaigner_id=1)
        gads_result = analytics_crew._fetch_google_ads_token(customer_id=1, campaigner_id=1)
        meta_result = analytics_crew._fetch_meta_ads_token(customer_id=1, campaigner_id=1)

        # Verify methods handle missing credentials gracefully
        assert ga_result is None
        assert gads_result is None
        assert meta_result is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
