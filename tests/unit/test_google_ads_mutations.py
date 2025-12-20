"""
Unit tests for Google Ads mutation helper functions.
Tests all helper functions in app/services/google_ads_mutations.py
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, call
from google.ads.googleads.client import GoogleAdsClient


class TestClientAndServiceHelpers:
    """Test client and service helper functions."""

    def test_get_campaign_service(self):
        """Test getting campaign service from client."""
        from app.services.google_ads_mutations import get_campaign_service

        mock_client = Mock(spec=GoogleAdsClient)
        mock_service = Mock()
        mock_client.get_service.return_value = mock_service

        result = get_campaign_service(mock_client)

        assert result == mock_service
        mock_client.get_service.assert_called_once_with("CampaignService")

    def test_get_campaign_budget_service(self):
        """Test getting campaign budget service from client."""
        from app.services.google_ads_mutations import get_campaign_budget_service

        mock_client = Mock(spec=GoogleAdsClient)
        mock_service = Mock()
        mock_client.get_service.return_value = mock_service

        result = get_campaign_budget_service(mock_client)

        assert result == mock_service
        mock_client.get_service.assert_called_once_with("CampaignBudgetService")

    def test_get_asset_service(self):
        """Test getting asset service from client."""
        from app.services.google_ads_mutations import get_asset_service

        mock_client = Mock(spec=GoogleAdsClient)
        mock_service = Mock()
        mock_client.get_service.return_value = mock_service

        result = get_asset_service(mock_client)

        assert result == mock_service
        mock_client.get_service.assert_called_once_with("AssetService")

    def test_get_campaign_asset_service(self):
        """Test getting campaign asset service from client."""
        from app.services.google_ads_mutations import get_campaign_asset_service

        mock_client = Mock(spec=GoogleAdsClient)
        mock_service = Mock()
        mock_client.get_service.return_value = mock_service

        result = get_campaign_asset_service(mock_client)

        assert result == mock_service
        mock_client.get_service.assert_called_once_with("CampaignAssetService")

    def test_get_ad_group_service(self):
        """Test getting ad group service from client."""
        from app.services.google_ads_mutations import get_ad_group_service

        mock_client = Mock(spec=GoogleAdsClient)
        mock_service = Mock()
        mock_client.get_service.return_value = mock_service

        result = get_ad_group_service(mock_client)

        assert result == mock_service
        mock_client.get_service.assert_called_once_with("AdGroupService")

    def test_get_ad_group_ad_service(self):
        """Test getting ad group ad service from client."""
        from app.services.google_ads_mutations import get_ad_group_ad_service

        mock_client = Mock(spec=GoogleAdsClient)
        mock_service = Mock()
        mock_client.get_service.return_value = mock_service

        result = get_ad_group_ad_service(mock_client)

        assert result == mock_service
        mock_client.get_service.assert_called_once_with("AdGroupAdService")


class TestResourceNameHelpers:
    """Test resource name building and parsing helpers."""

    def test_build_campaign_resource_name(self):
        """Test building campaign resource name."""
        from app.services.google_ads_mutations import build_campaign_resource_name

        result = build_campaign_resource_name("1234567890", "12345")
        assert result == "customers/1234567890/campaigns/12345"

    def test_build_budget_resource_name(self):
        """Test building budget resource name."""
        from app.services.google_ads_mutations import build_budget_resource_name

        result = build_budget_resource_name("1234567890", "98765")
        assert result == "customers/1234567890/campaignBudgets/98765"

    def test_build_ad_group_resource_name(self):
        """Test building ad group resource name."""
        from app.services.google_ads_mutations import build_ad_group_resource_name

        result = build_ad_group_resource_name("1234567890", "67890")
        assert result == "customers/1234567890/adGroups/67890"

    def test_build_asset_resource_name(self):
        """Test building asset resource name."""
        from app.services.google_ads_mutations import build_asset_resource_name

        result = build_asset_resource_name("1234567890", "11111")
        assert result == "customers/1234567890/assets/11111"

    def test_extract_id_from_resource_name(self):
        """Test extracting ID from resource name."""
        from app.services.google_ads_mutations import extract_id_from_resource_name

        # Test campaign resource name
        result = extract_id_from_resource_name("customers/1234567890/campaigns/12345")
        assert result == "12345"

        # Test budget resource name
        result = extract_id_from_resource_name("customers/1234567890/campaignBudgets/98765")
        assert result == "98765"

        # Test ad group ad resource name with compound ID
        result = extract_id_from_resource_name("customers/1234567890/adGroupAds/67890~11111")
        assert result == "67890~11111"


class TestBudgetOperations:
    """Test budget operation helpers."""

    def test_create_budget_operation_basic(self):
        """Test creating budget operation with basic parameters."""
        from app.services.google_ads_mutations import create_budget_operation

        mock_client = Mock(spec=GoogleAdsClient)
        mock_operation = Mock()
        mock_budget = Mock()
        mock_operation.create = mock_budget
        mock_client.get_type.return_value = mock_operation

        # Mock enum
        mock_client.enums = Mock()
        mock_delivery_enum = Mock()
        mock_delivery_enum.STANDARD = "STANDARD"
        mock_client.enums.BudgetDeliveryMethodEnum = mock_delivery_enum

        result = create_budget_operation(
            mock_client,
            "Test Budget",
            50000000,
        )

        assert result == mock_operation
        assert mock_budget.name == "Test Budget"
        assert mock_budget.amount_micros == 50000000
        assert mock_budget.delivery_method == "STANDARD"
        assert mock_budget.explicitly_shared is False

    def test_create_budget_operation_with_options(self):
        """Test creating budget operation with all options."""
        from app.services.google_ads_mutations import create_budget_operation

        mock_client = Mock(spec=GoogleAdsClient)
        mock_operation = Mock()
        mock_budget = Mock()
        mock_operation.create = mock_budget
        mock_client.get_type.return_value = mock_operation

        # Mock enum
        mock_client.enums = Mock()
        mock_delivery_enum = Mock()
        mock_delivery_enum.ACCELERATED = "ACCELERATED"
        mock_client.enums.BudgetDeliveryMethodEnum = mock_delivery_enum

        result = create_budget_operation(
            mock_client,
            "Shared Budget",
            100000000,
            delivery_method="ACCELERATED",
            explicitly_shared=True,
        )

        assert result == mock_operation
        assert mock_budget.name == "Shared Budget"
        assert mock_budget.amount_micros == 100000000
        assert mock_budget.delivery_method == "ACCELERATED"
        assert mock_budget.explicitly_shared is True

    def test_update_budget_operation(self):
        """Test updating budget operation."""
        from app.services.google_ads_mutations import update_budget_operation

        mock_client = Mock(spec=GoogleAdsClient)
        mock_operation = Mock()
        mock_budget = Mock()
        mock_operation.update = mock_budget
        mock_field_mask = Mock()
        mock_operation.update_mask = mock_field_mask
        mock_client.get_type.return_value = mock_operation

        result = update_budget_operation(
            mock_client,
            "customers/1234567890/campaignBudgets/98765",
            75000000,
        )

        assert result == mock_operation
        assert mock_budget.resource_name == "customers/1234567890/campaignBudgets/98765"
        assert mock_budget.amount_micros == 75000000


class TestCampaignOperations:
    """Test campaign operation helpers."""

    def test_create_campaign_operation(self):
        """Test creating campaign operation."""
        from app.services.google_ads_mutations import create_campaign_operation

        mock_client = Mock(spec=GoogleAdsClient)
        mock_operation = Mock()
        mock_campaign = Mock()
        mock_operation.create = mock_campaign
        mock_client.get_type.return_value = mock_operation

        # Mock enums
        mock_client.enums = Mock()
        mock_campaign_type_enum = Mock()
        mock_campaign_type_enum.SEARCH = "SEARCH"
        mock_client.enums.AdvertisingChannelTypeEnum = mock_campaign_type_enum

        mock_status_enum = Mock()
        mock_status_enum.PAUSED = "PAUSED"
        mock_client.enums.CampaignStatusEnum = mock_status_enum

        result = create_campaign_operation(
            mock_client,
            "Summer Sale",
            "customers/1234567890/campaignBudgets/98765",
            "SEARCH",
        )

        assert result == mock_operation
        assert mock_campaign.name == "Summer Sale"
        assert mock_campaign.campaign_budget == "customers/1234567890/campaignBudgets/98765"
        assert mock_campaign.advertising_channel_type == "SEARCH"
        assert mock_campaign.status == "PAUSED"  # Default status

    def test_apply_network_settings(self):
        """Test applying network settings to campaign."""
        from app.services.google_ads_mutations import apply_network_settings

        mock_campaign = Mock()
        mock_network_settings = Mock()
        mock_campaign.network_settings = mock_network_settings

        apply_network_settings(
            mock_campaign,
            target_google_search=True,
            target_search_network=True,
            target_content_network=False
        )

        assert mock_network_settings.target_google_search is True
        assert mock_network_settings.target_search_network is True
        assert mock_network_settings.target_content_network is False

    def test_apply_bidding_strategy_maximize_conversions(self):
        """Test applying MAXIMIZE_CONVERSIONS bidding strategy."""
        from app.services.google_ads_mutations import apply_bidding_strategy

        mock_client = Mock(spec=GoogleAdsClient)
        mock_campaign = Mock()
        mock_maximize_conversions = Mock()
        mock_campaign.maximize_conversions = mock_maximize_conversions

        apply_bidding_strategy(
            mock_client,
            mock_campaign,
            "MAXIMIZE_CONVERSIONS",
        )

        # Verify maximize_conversions was accessed (which creates it)
        assert mock_campaign.maximize_conversions == mock_maximize_conversions

    def test_apply_bidding_strategy_target_cpa(self):
        """Test applying TARGET_CPA bidding strategy with config."""
        from app.services.google_ads_mutations import apply_bidding_strategy

        mock_client = Mock(spec=GoogleAdsClient)
        mock_campaign = Mock()
        mock_target_cpa = Mock()
        mock_campaign.target_cpa = mock_target_cpa

        apply_bidding_strategy(
            mock_client,
            mock_campaign,
            "TARGET_CPA",
            {"target_cpa_micros": 5000000},
        )

        assert mock_target_cpa.target_cpa_micros == 5000000

    def test_apply_bidding_strategy_target_roas(self):
        """Test applying TARGET_ROAS bidding strategy with config."""
        from app.services.google_ads_mutations import apply_bidding_strategy

        mock_client = Mock(spec=GoogleAdsClient)
        mock_campaign = Mock()
        mock_target_roas = Mock()
        mock_campaign.target_roas = mock_target_roas

        apply_bidding_strategy(
            mock_client,
            mock_campaign,
            "TARGET_ROAS",
            {"target_roas": 4.0},
        )

        assert mock_target_roas.target_roas == 4.0


class TestAdOperations:
    """Test ad operation helpers."""

    def test_create_ad_group_operation(self):
        """Test creating ad group operation."""
        from app.services.google_ads_mutations import create_ad_group_operation

        mock_client = Mock(spec=GoogleAdsClient)
        mock_operation = Mock()
        mock_ad_group = Mock()
        mock_operation.create = mock_ad_group
        mock_client.get_type.return_value = mock_operation

        # Mock enum
        mock_client.enums = Mock()
        mock_status_enum = Mock()
        mock_status_enum.ENABLED = "ENABLED"
        mock_client.enums.AdGroupStatusEnum = mock_status_enum

        result = create_ad_group_operation(
            mock_client,
            "Product Ads",
            "customers/1234567890/campaigns/12345",
            2000000,
        )

        assert result == mock_operation
        assert mock_ad_group.name == "Product Ads"
        assert mock_ad_group.campaign == "customers/1234567890/campaigns/12345"
        assert mock_ad_group.cpc_bid_micros == 2000000
        assert mock_ad_group.status == "ENABLED"

    def test_create_text_asset(self):
        """Test creating text asset for ads."""
        from app.services.google_ads_mutations import create_text_asset

        mock_client = Mock(spec=GoogleAdsClient)
        mock_asset = Mock()
        mock_client.get_type.return_value = mock_asset

        result = create_text_asset(mock_client, "Buy Now")

        assert result == mock_asset
        assert mock_asset.text == "Buy Now"

    def test_create_responsive_search_ad_operation(self):
        """Test creating responsive search ad operation."""
        from app.services.google_ads_mutations import create_responsive_search_ad_operation

        mock_client = Mock(spec=GoogleAdsClient)
        mock_operation = Mock()
        mock_ad_group_ad = Mock()
        mock_ad = Mock()
        mock_rsa = Mock()
        mock_operation.create = mock_ad_group_ad
        mock_ad_group_ad.ad = mock_ad
        mock_ad.responsive_search_ad = mock_rsa
        mock_client.get_type.return_value = mock_operation

        # Mock enum
        mock_client.enums = Mock()
        mock_status_enum = Mock()
        mock_status_enum.ENABLED = "ENABLED"
        mock_client.enums.AdGroupAdStatusEnum = mock_status_enum

        headlines = ["Buy Now", "Save Today", "Limited Offer"]
        descriptions = ["Get 20% off", "Free shipping"]
        final_urls = ["https://example.com/sale"]

        result = create_responsive_search_ad_operation(
            mock_client,
            "customers/1234567890/adGroups/67890",
            headlines,
            descriptions,
            final_urls,
            path1="sale",
            path2="products",
        )

        assert result == mock_operation
        assert mock_ad_group_ad.ad_group == "customers/1234567890/adGroups/67890"
        assert mock_ad_group_ad.status == "ENABLED"


class TestExecutionHelpers:
    """Test execution and utility helper functions."""

    def test_execute_mutation_success(self):
        """Test successful mutation execution."""
        from app.services.google_ads_mutations import execute_mutation

        mock_service = Mock()
        mock_response = Mock()
        mock_result1 = Mock()
        mock_result1.resource_name = "customers/123/campaigns/456"
        mock_result2 = Mock()
        mock_result2.resource_name = "customers/123/campaigns/789"
        mock_response.results = [mock_result1, mock_result2]
        mock_service.return_value = mock_response

        operations = [Mock(), Mock()]

        result = execute_mutation(
            mock_service,
            "1234567890",
            operations,
            "Campaign Creation",
        )

        assert result["success"] is True
        assert result["count"] == 2
        assert len(result["resource_names"]) == 2
        assert result["resource_names"][0] == "customers/123/campaigns/456"
        assert result["resource_names"][1] == "customers/123/campaigns/789"
        mock_service.assert_called_once_with(customer_id="1234567890", operations=operations)

    def test_execute_mutation_failure(self):
        """Test failed mutation execution."""
        from app.services.google_ads_mutations import execute_mutation

        mock_service = Mock()
        mock_service.side_effect = Exception("Google Ads API error")

        operations = [Mock()]

        result = execute_mutation(
            mock_service,
            "1234567890",
            operations,
            "Campaign Creation",
        )

        assert result["success"] is False
        assert "Google Ads API error" in result["error"]
        assert result["error_type"] == "Exception"

    def test_convert_micros_to_currency(self):
        """Test converting micros to currency."""
        from app.services.google_ads_mutations import convert_micros_to_currency

        assert convert_micros_to_currency(50000000) == 50.0
        assert convert_micros_to_currency(1000000) == 1.0
        assert convert_micros_to_currency(500000) == 0.5
        assert convert_micros_to_currency(0) == 0.0

    def test_convert_currency_to_micros(self):
        """Test converting currency to micros."""
        from app.services.google_ads_mutations import convert_currency_to_micros

        assert convert_currency_to_micros(50.0) == 50000000
        assert convert_currency_to_micros(1.0) == 1000000
        assert convert_currency_to_micros(0.5) == 500000
        assert convert_currency_to_micros(0.0) == 0


class TestAssetOperations:
    """Test asset operation helpers."""

    def test_create_image_asset_operation(self):
        """Test creating image asset operation."""
        from app.services.google_ads_mutations import create_image_asset_operation

        mock_client = Mock(spec=GoogleAdsClient)
        mock_operation = Mock()
        mock_asset = Mock()
        mock_image_asset = Mock()
        mock_operation.create = mock_asset
        mock_asset.image_asset = mock_image_asset
        mock_client.get_type.return_value = mock_operation

        # Mock enum
        mock_client.enums = Mock()
        mock_mime_enum = Mock()
        mock_mime_enum.IMAGE_PNG = "IMAGE_PNG"
        mock_client.enums.MimeTypeEnum = mock_mime_enum

        image_data = b"fake_image_data"

        result = create_image_asset_operation(
            mock_client,
            "Product Image",
            image_data,
            "IMAGE_PNG",
        )

        assert result == mock_operation
        assert mock_asset.name == "Product Image"
        assert mock_image_asset.data == image_data
        assert mock_image_asset.mime_type == "IMAGE_PNG"

    def test_create_campaign_asset_link_operation(self):
        """Test creating campaign asset link operation."""
        from app.services.google_ads_mutations import create_campaign_asset_link_operation

        mock_client = Mock(spec=GoogleAdsClient)
        mock_operation = Mock()
        mock_campaign_asset = Mock()
        mock_operation.create = mock_campaign_asset
        mock_client.get_type.return_value = mock_operation

        # Mock enum
        mock_client.enums = Mock()
        mock_field_enum = Mock()
        mock_field_enum.MARKETING_IMAGE = "MARKETING_IMAGE"
        mock_client.enums.AssetFieldTypeEnum = mock_field_enum

        result = create_campaign_asset_link_operation(
            mock_client,
            "customers/1234567890/assets/11111",
            "customers/1234567890/campaigns/12345",
            "MARKETING_IMAGE",
        )

        assert result == mock_operation
        assert mock_campaign_asset.asset == "customers/1234567890/assets/11111"
        assert mock_campaign_asset.campaign == "customers/1234567890/campaigns/12345"
        assert mock_campaign_asset.field_type == "MARKETING_IMAGE"

    def test_remove_campaign_asset_link_operation(self):
        """Test removing campaign asset link operation."""
        from app.services.google_ads_mutations import remove_campaign_asset_link_operation

        mock_client = Mock(spec=GoogleAdsClient)
        mock_operation = Mock()
        mock_client.get_type.return_value = mock_operation

        result = remove_campaign_asset_link_operation(
            mock_client,
            "customers/1234567890/campaignAssets/12345~11111~MARKETING_IMAGE",
        )

        assert result == mock_operation
        assert mock_operation.remove == "customers/1234567890/campaignAssets/12345~11111~MARKETING_IMAGE"


class TestUpdateOperations:
    """Test update operation helpers."""

    def test_update_campaign_field_single_field(self):
        """Test updating a single campaign field."""
        from app.services.google_ads_mutations import update_campaign_field

        mock_client = Mock(spec=GoogleAdsClient)
        mock_operation = Mock()
        mock_campaign = Mock()
        mock_field_mask = Mock()
        mock_operation.update = mock_campaign
        mock_operation.update_mask = mock_field_mask
        mock_client.get_type.return_value = mock_operation

        # Mock enum
        mock_client.enums = Mock()
        mock_status_enum = Mock()
        mock_status_enum.PAUSED = "PAUSED"
        mock_client.enums.CampaignStatusEnum = mock_status_enum

        updates = {"status": "PAUSED"}

        result = update_campaign_field(
            mock_client,
            "customers/1234567890/campaigns/12345",
            updates,
        )

        assert result == mock_operation
        assert mock_campaign.resource_name == "customers/1234567890/campaigns/12345"
        assert mock_campaign.status == "PAUSED"

    def test_update_campaign_field_multiple_fields(self):
        """Test updating multiple campaign fields."""
        from app.services.google_ads_mutations import update_campaign_field

        mock_client = Mock(spec=GoogleAdsClient)
        mock_operation = Mock()
        mock_campaign = Mock()
        mock_field_mask = Mock()
        mock_operation.update = mock_campaign
        mock_operation.update_mask = mock_field_mask
        mock_client.get_type.return_value = mock_operation

        updates = {
            "name": "New Campaign Name",
            "start_date": "2024-06-01",
            "end_date": "2024-08-31",
        }

        result = update_campaign_field(
            mock_client,
            "customers/1234567890/campaigns/12345",
            updates,
        )

        assert result == mock_operation
        assert mock_campaign.resource_name == "customers/1234567890/campaigns/12345"
        assert mock_campaign.name == "New Campaign Name"
        assert mock_campaign.start_date == "2024-06-01"
        assert mock_campaign.end_date == "2024-08-31"

    def test_update_ad_status_operation(self):
        """Test updating ad status operation."""
        from app.services.google_ads_mutations import update_ad_status_operation

        mock_client = Mock(spec=GoogleAdsClient)
        mock_operation = Mock()
        mock_ad_group_ad = Mock()
        mock_field_mask = Mock()
        mock_operation.update = mock_ad_group_ad
        mock_operation.update_mask = mock_field_mask
        mock_client.get_type.return_value = mock_operation

        # Mock enum
        mock_client.enums = Mock()
        mock_status_enum = Mock()
        mock_status_enum.PAUSED = "PAUSED"
        mock_client.enums.AdGroupAdStatusEnum = mock_status_enum

        result = update_ad_status_operation(
            mock_client,
            "customers/1234567890/adGroupAds/67890~11111",
            "PAUSED",
        )

        assert result == mock_operation
        assert mock_ad_group_ad.resource_name == "customers/1234567890/adGroupAds/67890~11111"
        assert mock_ad_group_ad.status == "PAUSED"
