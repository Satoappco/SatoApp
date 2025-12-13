"""
Unit tests for Facebook duplicate connection handling
Tests that the system properly handles duplicate digital assets
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone, timedelta
from app.api.v1.routes.facebook_oauth import (
    create_facebook_ads_connection,
    create_facebook_connection,
    CreateFacebookAdsConnectionRequest,
    CreateConnectionRequest,
)
from app.models.analytics import DigitalAsset, Connection, AssetType, AuthType


class TestFacebookDuplicateConnectionHandling:
    """Tests for handling duplicate Facebook connections"""

    @pytest.mark.asyncio
    @patch("app.api.v1.routes.facebook_oauth.CampaignSyncService")
    @patch("app.api.v1.routes.facebook_oauth.get_session")
    @patch("app.api.v1.routes.facebook_oauth.FacebookService")
    async def test_create_ads_connection_duplicate_asset(
        self, mock_facebook_service, mock_get_session, mock_sync_service
    ):
        """Test creating an ads connection when digital asset already exists"""

        # Mock CampaignSyncService
        mock_sync_instance = MagicMock()
        mock_sync_instance.sync_metrics_new.return_value = {
            "success": True,
            "metrics_upserted": 0,
        }
        mock_sync_service.return_value = mock_sync_instance

        # Create request
        request = CreateFacebookAdsConnectionRequest(
            campaigner_id=1,
            customer_id=10,
            access_token="test_token_123",
            expires_in=3600,
            user_name="Test User",
            user_email="test@example.com",
            ad_account_id="act_81369432",
            ad_account_name="AEF",
            currency="ILS",
            timezone="Asia/Jerusalem",
        )

        # Mock existing digital asset
        mock_existing_asset = Mock(spec=DigitalAsset)
        mock_existing_asset.id = 100
        mock_existing_asset.customer_id = 10
        mock_existing_asset.external_id = "act_81369432"
        mock_existing_asset.asset_type = AssetType.FACEBOOK_ADS
        mock_existing_asset.name = "Old Name"
        mock_existing_asset.meta = {}
        mock_existing_asset.is_active = False

        # Mock session
        mock_session = MagicMock()

        # First exec call finds existing asset
        mock_exec_result = MagicMock()
        mock_exec_result.first.return_value = mock_existing_asset

        # Second exec call checks for existing connection (none found)
        mock_exec_result_connection = MagicMock()
        mock_exec_result_connection.first.return_value = None

        mock_session.exec.side_effect = [mock_exec_result, mock_exec_result_connection]

        mock_get_session.return_value.__enter__.return_value = mock_session

        # Mock FacebookService
        mock_fb_service_instance = MagicMock()
        mock_fb_service_instance._encrypt_token.return_value = b"encrypted_token"
        mock_fb_service_instance._generate_token_hash.return_value = "token_hash_123"
        mock_fb_service_instance.FACEBOOK_SCOPES = ["ads_read", "ads_management"]
        mock_facebook_service.return_value = mock_fb_service_instance

        # Mock the new connection
        mock_new_connection = Mock(spec=Connection)
        mock_new_connection.id = 200

        # Call the function
        result = await create_facebook_ads_connection(request)

        # Assertions
        assert result.success is True
        assert "Successfully connected Facebook Ads account" in result.message
        assert len(result.connections) == 1
        assert result.connections[0]["digital_asset_id"] == 100

        # Verify that existing asset was updated, not recreated
        mock_session.add.assert_called()  # Called to update existing asset and add connection
        mock_session.commit.assert_called()

        # Verify the asset was updated with new metadata
        assert mock_existing_asset.name == "AEF"
        assert mock_existing_asset.meta["ad_account_name"] == "AEF"
        assert mock_existing_asset.meta["currency"] == "ILS"
        assert mock_existing_asset.is_active is True

    @pytest.mark.asyncio
    @patch("app.api.v1.routes.facebook_oauth.CampaignSyncService")
    @patch("app.api.v1.routes.facebook_oauth.get_session")
    @patch("app.api.v1.routes.facebook_oauth.FacebookService")
    async def test_create_ads_connection_new_asset(
        self, mock_facebook_service, mock_get_session, mock_sync_service
    ):
        """Test creating an ads connection when digital asset doesn't exist"""

        # Mock CampaignSyncService
        mock_sync_instance = MagicMock()
        mock_sync_instance.sync_metrics_new.return_value = {
            "success": True,
            "metrics_upserted": 0,
        }
        mock_sync_service.return_value = mock_sync_instance

        # Create request
        request = CreateFacebookAdsConnectionRequest(
            campaigner_id=1,
            customer_id=10,
            access_token="test_token_123",
            expires_in=3600,
            user_name="Test User",
            user_email="test@example.com",
            ad_account_id="act_99999999",
            ad_account_name="New Account",
            currency="USD",
            timezone="America/New_York",
        )

        # Mock session
        mock_session = MagicMock()

        # First exec call finds no existing asset
        mock_exec_result = MagicMock()
        mock_exec_result.first.return_value = None

        # Second exec call checks for existing connection (none found)
        mock_exec_result_connection = MagicMock()
        mock_exec_result_connection.first.return_value = None

        mock_session.exec.side_effect = [mock_exec_result, mock_exec_result_connection]

        mock_get_session.return_value.__enter__.return_value = mock_session

        # Mock FacebookService
        mock_fb_service_instance = MagicMock()
        mock_fb_service_instance._encrypt_token.return_value = b"encrypted_token"
        mock_fb_service_instance._generate_token_hash.return_value = "token_hash_123"
        mock_fb_service_instance.FACEBOOK_SCOPES = ["ads_read", "ads_management"]
        mock_facebook_service.return_value = mock_fb_service_instance

        # Call the function
        result = await create_facebook_ads_connection(request)

        # Assertions
        assert result.success is True
        assert "Successfully connected Facebook Ads account" in result.message

        # Verify that a new asset was created
        # session.add should be called twice: once for new asset, once for new connection
        assert mock_session.add.call_count >= 2
        mock_session.commit.assert_called()

    @pytest.mark.asyncio
    @patch("app.api.v1.routes.facebook_oauth.get_session")
    @patch("app.api.v1.routes.facebook_oauth.FacebookService")
    async def test_create_page_connection_duplicate_asset(
        self, mock_facebook_service, mock_get_session
    ):
        """Test creating a page connection when digital asset already exists"""

        # Create request
        request = CreateConnectionRequest(
            campaigner_id=1,
            customer_id=10,
            access_token="test_token_123",
            expires_in=3600,
            user_name="Test User",
            user_email="test@example.com",
            page_id="123456789",
            page_name="Test Page",
            page_username="testpage",
            page_category="Business",
        )

        # Mock existing digital asset
        mock_existing_asset = Mock(spec=DigitalAsset)
        mock_existing_asset.id = 100
        mock_existing_asset.customer_id = 10
        mock_existing_asset.external_id = "123456789"
        mock_existing_asset.asset_type = AssetType.SOCIAL_MEDIA
        mock_existing_asset.name = "Old Page Name"
        mock_existing_asset.handle = "oldhandle"
        mock_existing_asset.meta = {}
        mock_existing_asset.is_active = False

        # Mock session
        mock_session = MagicMock()

        # First exec call finds existing asset
        mock_exec_result = MagicMock()
        mock_exec_result.first.return_value = mock_existing_asset

        # Second exec call checks for existing connection (none found)
        mock_exec_result_connection = MagicMock()
        mock_exec_result_connection.first.return_value = None

        mock_session.exec.side_effect = [mock_exec_result, mock_exec_result_connection]

        mock_get_session.return_value.__enter__.return_value = mock_session

        # Mock FacebookService
        mock_fb_service_instance = MagicMock()
        mock_fb_service_instance._encrypt_token.return_value = b"encrypted_token"
        mock_fb_service_instance._generate_token_hash.return_value = "token_hash_123"
        mock_fb_service_instance.FACEBOOK_SCOPES = ["pages_read_engagement", "pages_manage_metadata"]
        mock_facebook_service.return_value = mock_fb_service_instance

        # Call the function
        result = await create_facebook_connection(request)

        # Assertions
        assert result.success is True
        assert "Successfully connected Facebook page" in result.message
        assert len(result.connections) == 1
        assert result.connections[0]["digital_asset_id"] == 100

        # Verify that existing asset was updated, not recreated
        mock_session.add.assert_called()
        mock_session.commit.assert_called()

        # Verify the asset was updated with new metadata
        assert mock_existing_asset.name == "Test Page"
        assert mock_existing_asset.handle == "testpage"
        assert mock_existing_asset.meta["page_name"] == "Test Page"
        assert mock_existing_asset.meta["page_category"] == "Business"
        assert mock_existing_asset.is_active is True

    @pytest.mark.asyncio
    @patch("app.api.v1.routes.facebook_oauth.CampaignSyncService")
    @patch("app.api.v1.routes.facebook_oauth.get_session")
    @patch("app.api.v1.routes.facebook_oauth.FacebookService")
    async def test_create_ads_connection_updates_inactive_asset(
        self, mock_facebook_service, mock_get_session, mock_sync_service
    ):
        """Test that creating a connection reactivates an inactive asset"""

        # Mock CampaignSyncService
        mock_sync_instance = MagicMock()
        mock_sync_instance.sync_metrics_new.return_value = {
            "success": True,
            "metrics_upserted": 0,
        }
        mock_sync_service.return_value = mock_sync_instance

        # Create request
        request = CreateFacebookAdsConnectionRequest(
            campaigner_id=1,
            customer_id=10,
            access_token="test_token_123",
            expires_in=3600,
            user_name="Test User",
            user_email="test@example.com",
            ad_account_id="act_inactive",
            ad_account_name="Reactivated Account",
            currency="EUR",
            timezone="Europe/London",
        )

        # Mock existing inactive digital asset
        mock_existing_asset = Mock(spec=DigitalAsset)
        mock_existing_asset.id = 100
        mock_existing_asset.customer_id = 10
        mock_existing_asset.external_id = "act_inactive"
        mock_existing_asset.asset_type = AssetType.FACEBOOK_ADS
        mock_existing_asset.name = "Old Inactive"
        mock_existing_asset.meta = {"status": "inactive"}
        mock_existing_asset.is_active = False  # Asset was inactive

        # Mock session
        mock_session = MagicMock()

        mock_exec_result = MagicMock()
        mock_exec_result.first.return_value = mock_existing_asset

        mock_exec_result_connection = MagicMock()
        mock_exec_result_connection.first.return_value = None

        mock_session.exec.side_effect = [mock_exec_result, mock_exec_result_connection]

        mock_get_session.return_value.__enter__.return_value = mock_session

        # Mock FacebookService
        mock_fb_service_instance = MagicMock()
        mock_fb_service_instance._encrypt_token.return_value = b"encrypted_token"
        mock_fb_service_instance._generate_token_hash.return_value = "token_hash_123"
        mock_fb_service_instance.FACEBOOK_SCOPES = ["ads_read", "ads_management"]
        mock_facebook_service.return_value = mock_fb_service_instance

        # Call the function
        result = await create_facebook_ads_connection(request)

        # Assertions
        assert result.success is True

        # Verify that the asset was reactivated
        assert mock_existing_asset.is_active is True
        assert mock_existing_asset.name == "Reactivated Account"
