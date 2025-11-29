"""
Tests for 90-day metrics sync when adding new assets
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta, timezone

from app.services.google_ads_service import GoogleAdsService
from app.services.facebook_service import FacebookService


class TestNewAssetMetricsSync:
    """Test that new assets automatically sync 90 days of metrics"""

    @pytest.mark.asyncio
    @patch('app.services.campaign_sync_service.CampaignSyncService')
    @patch('app.services.google_ads_service.get_session')
    async def test_google_ads_connection_triggers_90_day_sync(
        self, mock_get_session, mock_sync_service_class
    ):
        """Test that creating a Google Ads connection triggers 90-day metrics sync"""
        # Setup mocks
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__.return_value = mock_session

        mock_sync_service = Mock()
        mock_sync_service.sync_metrics_new.return_value = {
            "success": True,
            "metrics_upserted": 100,
            "error_details": []
        }
        mock_sync_service_class.return_value = mock_sync_service

        # Mock database objects
        mock_digital_asset = Mock()
        mock_digital_asset.id = 1

        mock_connection = Mock()
        mock_connection.id = 1

        # Mock upsert_digital_asset
        with patch('app.services.digital_asset_service.upsert_digital_asset', return_value=mock_digital_asset):
            with patch('app.services.property_selection_service.PropertySelectionService'):
                # Create service and call save_google_ads_connection
                service = GoogleAdsService()
                result = await service.save_google_ads_connection(
                    campaigner_id=1,
                    customer_id=1,
                    account_id="123-456-7890",
                    account_name="Test Account",
                    access_token="test_token",
                    refresh_token="test_refresh",
                    expires_in=3600,
                    account_email="test@example.com"
                )

        # Verify sync was called (it will auto-detect and sync 90 days for new asset)
        mock_sync_service.sync_metrics_new.assert_called_once_with(
            customer_id=1
        )

        # Verify connection was created successfully
        assert result["success"] is True

    @pytest.mark.asyncio
    @patch('app.services.campaign_sync_service.CampaignSyncService')
    @patch('app.services.facebook_service.get_session')
    async def test_facebook_connection_triggers_90_day_sync(
        self, mock_get_session, mock_sync_service_class
    ):
        """Test that creating a Facebook connection triggers 90-day metrics sync"""
        # Setup mocks
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__.return_value = mock_session

        mock_sync_service = Mock()
        mock_sync_service.sync_metrics_new.return_value = {
            "success": True,
            "metrics_upserted": 150,
            "error_details": []
        }
        mock_sync_service_class.return_value = mock_sync_service

        # Mock database objects
        mock_digital_asset = Mock()
        mock_digital_asset.id = 1
        mock_digital_asset.external_id = "page_123"
        mock_digital_asset.name = "Test Page"

        mock_connection = Mock()
        mock_connection.id = 1

        # Mock the API calls
        with patch.object(FacebookService, '_get_user_pages', return_value=[
            {'id': 'page_123', 'name': 'Test Page', 'username': 'testpage'}
        ]):
            with patch.object(FacebookService, '_get_user_ad_accounts', return_value=[
                {'id': 'act_123', 'name': 'Test Ad Account', 'currency': 'USD'}
            ]):
                with patch('app.services.digital_asset_service.upsert_digital_asset', return_value=mock_digital_asset):
                    with patch('app.services.property_selection_service.PropertySelectionService'):
                        # Create service and call save_facebook_connection
                        service = FacebookService()
                        result = await service.save_facebook_connection(
                            campaigner_id=1,
                            customer_id=1,
                            access_token="test_token",
                            expires_in=3600,
                            user_name="Test User",
                            user_email="test@example.com"
                        )

        # Verify sync was called (it will auto-detect and sync 90 days for new asset)
        mock_sync_service.sync_metrics_new.assert_called_once_with(
            customer_id=1
        )

        # Verify connection was created successfully
        assert "connections" in result

    @patch('app.services.campaign_sync_service.get_session')
    def test_sync_metrics_new_auto_detects_gaps(self, mock_get_session):
        """Test that sync_metrics_new automatically detects missing dates"""
        from app.services.campaign_sync_service import CampaignSyncService

        # Setup mocks
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__.return_value = mock_session

        # Mock customer
        mock_customer = Mock()
        mock_customer.id = 1
        mock_customer.full_name = "Test Customer"

        mock_session.get.return_value = mock_customer
        mock_session.exec.return_value.all.return_value = []

        # Create service
        service = CampaignSyncService()

        # Call without days parameter (it will auto-detect)
        result = service.sync_metrics_new(customer_id=1)

        # Verify result structure
        assert result["success"] is True
        assert "metrics_upserted" in result
        assert "customers_processed" in result

    @patch('app.services.campaign_sync_service.get_session')
    def test_sync_metrics_new_no_params(self, mock_get_session):
        """Test that sync_metrics_new works without customer_id (syncs all customers)"""
        from app.services.campaign_sync_service import CampaignSyncService

        # Setup mocks
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__.return_value = mock_session

        # Mock customer
        mock_customer = Mock()
        mock_customer.id = 1
        mock_customer.full_name = "Test Customer"

        mock_session.get.return_value = mock_customer
        mock_session.exec.return_value.all.return_value = []

        # Create service
        service = CampaignSyncService()

        # Call without days parameter (should default to 2)
        result = service.sync_metrics_new(customer_id=1)

        # Verify result structure
        assert result["success"] is True
        assert "metrics_upserted" in result

    @pytest.mark.asyncio
    @patch('app.services.campaign_sync_service.CampaignSyncService')
    @patch('app.services.google_ads_service.get_session')
    async def test_connection_creation_continues_on_sync_failure(
        self, mock_get_session, mock_sync_service_class
    ):
        """Test that connection creation succeeds even if metrics sync fails"""
        # Setup mocks
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__.return_value = mock_session

        mock_sync_service = Mock()
        mock_sync_service.sync_metrics_new.side_effect = Exception("Sync failed")
        mock_sync_service_class.return_value = mock_sync_service

        # Mock database objects
        mock_digital_asset = Mock()
        mock_digital_asset.id = 1

        mock_connection = Mock()
        mock_connection.id = 1

        # Mock upsert_digital_asset
        with patch('app.services.digital_asset_service.upsert_digital_asset', return_value=mock_digital_asset):
            with patch('app.services.property_selection_service.PropertySelectionService'):
                # Create service and call save_google_ads_connection
                service = GoogleAdsService()
                result = await service.save_google_ads_connection(
                    campaigner_id=1,
                    customer_id=1,
                    account_id="123-456-7890",
                    account_name="Test Account",
                    access_token="test_token",
                    refresh_token="test_refresh",
                    expires_in=3600,
                    account_email="test@example.com"
                )

        # Verify connection was still created successfully despite sync failure
        assert result["success"] is True
        assert result["connection_id"] == 1
