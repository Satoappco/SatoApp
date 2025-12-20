"""
Integration tests for Google Ads mutations.
Tests end-to-end workflows using Google Ads service with mocked API.

These tests verify that all the layers work together:
- Service layer (GoogleAdsService)
- Helper functions (google_ads_mutations.py)
- Validators (google_ads_validators.py)
- Data models (google_ads.py)
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta, timezone


@pytest.fixture
def mock_google_ads_client():
    """Create a mock Google Ads client."""
    client = Mock()

    # Mock enums
    client.enums.AdvertisingChannelTypeEnum.SEARCH = "SEARCH"
    client.enums.CampaignStatusEnum.ENABLED = "ENABLED"
    client.enums.CampaignStatusEnum.PAUSED = "PAUSED"
    client.enums.BudgetDeliveryMethodEnum.STANDARD = "STANDARD"
    client.enums.AdGroupStatusEnum.ENABLED = "ENABLED"
    client.enums.AdGroupAdStatusEnum.ENABLED = "ENABLED"
    client.enums.MimeTypeEnum.IMAGE_PNG = "IMAGE_PNG"
    client.enums.AssetFieldTypeEnum.MARKETING_IMAGE = "MARKETING_IMAGE"

    # Mock get_type to return mock operations
    def get_type_side_effect(type_name):
        mock_op = Mock()
        if "Operation" in type_name:
            mock_op.create = Mock()
            mock_op.update = Mock()
            mock_op.remove = None
            mock_op.update_mask = Mock()
        return mock_op

    client.get_type = Mock(side_effect=get_type_side_effect)

    return client


@pytest.fixture
def mock_connection(mock_google_ads_client):
    """Create a mock database connection with encrypted tokens."""
    connection = Mock()
    connection.id = 1
    connection.campaigner_id = 1
    connection.customer_id = 1
    connection.digital_platform_id = 1
    connection.access_token_enc = b"encrypted_access_token"
    connection.refresh_token_enc = b"encrypted_refresh_token"
    connection.expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    connection.revoked = False
    return connection


@pytest.fixture
def mock_session(mock_connection):
    """Create a mock database session."""
    session = Mock()
    session.get.return_value = mock_connection
    session.__enter__ = Mock(return_value=session)
    session.__exit__ = Mock(return_value=None)
    return session


class TestCampaignCreationWorkflow:
    """Test complete campaign creation workflow."""

    @patch("app.services.google_ads_service.get_session")
    @patch("app.services.google_ads_service.GoogleAdsClient")
    @patch("app.services.google_ads_service.get_google_client_id")
    @patch("app.services.google_ads_service.get_google_client_secret")
    async def test_create_campaign_success(
        self,
        mock_get_secret,
        mock_get_id,
        mock_ads_client_class,
        mock_get_session,
        mock_google_ads_client,
        mock_session,
    ):
        """Test successful campaign creation with budget and bidding."""
        from app.services.google_ads_service import GoogleAdsService

        # Setup mocks
        mock_get_id.return_value = "test_client_id"
        mock_get_secret.return_value = "test_client_secret"
        mock_get_session.return_value = mock_session
        mock_ads_client_class.load_from_dict.return_value = mock_google_ads_client

        # Mock budget creation response
        budget_response = Mock()
        budget_result = Mock()
        budget_result.resource_name = "customers/1234567890/campaignBudgets/98765"
        budget_response.results = [budget_result]

        # Mock campaign creation response
        campaign_response = Mock()
        campaign_result = Mock()
        campaign_result.resource_name = "customers/1234567890/campaigns/12345"
        campaign_response.results = [campaign_result]

        # Setup service mock methods
        mock_budget_service = Mock()
        mock_budget_service.mutate_campaign_budgets.return_value = budget_response
        mock_campaign_service = Mock()
        mock_campaign_service.mutate_campaigns.return_value = campaign_response

        mock_google_ads_client.get_service.side_effect = lambda name: (
            mock_budget_service if name == "CampaignBudgetService" else mock_campaign_service
        )

        # Create service and execute
        with patch.dict("os.environ", {"GOOGLE_ADS_DEVELOPER_TOKEN": "test_token"}):
            service = GoogleAdsService()

            result = await service.create_campaign(
                connection_id=1,
                customer_id="1234567890",
                campaign_name="Test Campaign",
                budget_amount_micros=50000000,
                campaign_type="SEARCH",
                bidding_strategy_type="MAXIMIZE_CONVERSIONS",
            )

        # Verify result
        assert result["success"] is True
        assert "12345" in result["resource_names"][0]
        assert result.get("budget_resource_name") is not None

    @patch("app.services.google_ads_service.get_session")
    @patch("app.services.google_ads_service.GoogleAdsClient")
    async def test_create_campaign_invalid_customer_id(
        self, mock_ads_client_class, mock_get_session, mock_session
    ):
        """Test campaign creation with invalid customer ID."""
        from app.services.google_ads_service import GoogleAdsService

        mock_get_session.return_value = mock_session

        service = GoogleAdsService()

        result = await service.create_campaign(
            connection_id=1,
            customer_id="123",  # Invalid: too short
            campaign_name="Test Campaign",
            budget_amount_micros=50000000,
            campaign_type="SEARCH",
            bidding_strategy_type="MAXIMIZE_CONVERSIONS",
        )

        assert result["success"] is False
        assert "Customer ID must be 10 digits" in result["error"]

    @patch("app.services.google_ads_service.get_session")
    async def test_create_campaign_connection_not_found(self, mock_get_session):
        """Test campaign creation with non-existent connection."""
        from app.services.google_ads_service import GoogleAdsService

        mock_session = Mock()
        mock_session.get.return_value = None
        mock_session.__enter__ = Mock(return_value=mock_session)
        mock_session.__exit__ = Mock(return_value=None)
        mock_get_session.return_value = mock_session

        service = GoogleAdsService()

        result = await service.create_campaign(
            connection_id=999,  # Non-existent
            customer_id="1234567890",
            campaign_name="Test Campaign",
            budget_amount_micros=50000000,
            campaign_type="SEARCH",
            bidding_strategy_type="MAXIMIZE_CONVERSIONS",
        )

        assert result["success"] is False
        assert "Connection 999 not found" in result["error"]


class TestCampaignUpdateWorkflow:
    """Test campaign update workflows."""

    @patch("app.services.google_ads_service.get_session")
    @patch("app.services.google_ads_service.GoogleAdsClient")
    @patch("app.services.google_ads_service.get_google_client_id")
    @patch("app.services.google_ads_service.get_google_client_secret")
    async def test_update_campaign_status(
        self,
        mock_get_secret,
        mock_get_id,
        mock_ads_client_class,
        mock_get_session,
        mock_google_ads_client,
        mock_session,
    ):
        """Test updating campaign status."""
        from app.services.google_ads_service import GoogleAdsService

        # Setup mocks
        mock_get_id.return_value = "test_client_id"
        mock_get_secret.return_value = "test_client_secret"
        mock_get_session.return_value = mock_session
        mock_ads_client_class.load_from_dict.return_value = mock_google_ads_client

        # Mock campaign update response
        campaign_response = Mock()
        campaign_result = Mock()
        campaign_result.resource_name = "customers/1234567890/campaigns/12345"
        campaign_response.results = [campaign_result]

        mock_campaign_service = Mock()
        mock_campaign_service.mutate_campaigns.return_value = campaign_response
        mock_google_ads_client.get_service.return_value = mock_campaign_service

        # Create service and execute
        with patch.dict("os.environ", {"GOOGLE_ADS_DEVELOPER_TOKEN": "test_token"}):
            service = GoogleAdsService()

            result = await service.update_campaign_status(
                connection_id=1,
                customer_id="1234567890",
                campaign_id="12345",
                status="PAUSED",
            )

        # Verify result
        assert result["success"] is True
        assert "12345" in result["resource_names"][0]

    @patch("app.services.google_ads_service.get_session")
    async def test_update_campaign_invalid_status(self, mock_get_session, mock_session):
        """Test updating campaign with invalid status."""
        from app.services.google_ads_service import GoogleAdsService

        mock_get_session.return_value = mock_session

        service = GoogleAdsService()

        result = await service.update_campaign_status(
            connection_id=1,
            customer_id="1234567890",
            campaign_id="12345",
            status="INVALID",
        )

        assert result["success"] is False
        assert "Invalid status" in result["error"]


class TestBudgetUpdateWorkflow:
    """Test budget update workflows."""

    @patch("app.services.google_ads_service.get_session")
    @patch("app.services.google_ads_service.GoogleAdsClient")
    @patch("app.services.google_ads_service.get_google_client_id")
    @patch("app.services.google_ads_service.get_google_client_secret")
    async def test_update_campaign_budget(
        self,
        mock_get_secret,
        mock_get_id,
        mock_ads_client_class,
        mock_get_session,
        mock_google_ads_client,
        mock_session,
    ):
        """Test updating campaign budget."""
        from app.services.google_ads_service import GoogleAdsService

        # Setup mocks
        mock_get_id.return_value = "test_client_id"
        mock_get_secret.return_value = "test_client_secret"
        mock_get_session.return_value = mock_session
        mock_ads_client_class.load_from_dict.return_value = mock_google_ads_client

        # Mock budget update response
        budget_response = Mock()
        budget_result = Mock()
        budget_result.resource_name = "customers/1234567890/campaignBudgets/98765"
        budget_response.results = [budget_result]

        mock_budget_service = Mock()
        mock_budget_service.mutate_campaign_budgets.return_value = budget_response
        mock_google_ads_client.get_service.return_value = mock_budget_service

        # Create service and execute
        with patch.dict("os.environ", {"GOOGLE_ADS_DEVELOPER_TOKEN": "test_token"}):
            service = GoogleAdsService()

            result = await service.update_campaign_budget(
                connection_id=1,
                customer_id="1234567890",
                budget_id="98765",
                amount_micros=75000000,
            )

        # Verify result
        assert result["success"] is True
        assert "98765" in result["resource_names"][0]


class TestAdCreationWorkflow:
    """Test ad creation workflows."""

    @patch("app.services.google_ads_service.get_session")
    @patch("app.services.google_ads_service.GoogleAdsClient")
    @patch("app.services.google_ads_service.get_google_client_id")
    @patch("app.services.google_ads_service.get_google_client_secret")
    async def test_create_ad_group_and_ad(
        self,
        mock_get_secret,
        mock_get_id,
        mock_ads_client_class,
        mock_get_session,
        mock_google_ads_client,
        mock_session,
    ):
        """Test creating ad group and responsive search ad."""
        from app.services.google_ads_service import GoogleAdsService

        # Setup mocks
        mock_get_id.return_value = "test_client_id"
        mock_get_secret.return_value = "test_client_secret"
        mock_get_session.return_value = mock_session
        mock_ads_client_class.load_from_dict.return_value = mock_google_ads_client

        # Mock ad group creation response
        ad_group_response = Mock()
        ad_group_result = Mock()
        ad_group_result.resource_name = "customers/1234567890/adGroups/67890"
        ad_group_response.results = [ad_group_result]

        # Mock ad creation response
        ad_response = Mock()
        ad_result = Mock()
        ad_result.resource_name = "customers/1234567890/adGroupAds/67890~11111"
        ad_response.results = [ad_result]

        def get_service_side_effect(name):
            if name == "AdGroupService":
                service = Mock()
                service.mutate_ad_groups.return_value = ad_group_response
                return service
            elif name == "AdGroupAdService":
                service = Mock()
                service.mutate_ad_group_ads.return_value = ad_response
                return service

        mock_google_ads_client.get_service.side_effect = get_service_side_effect

        # Create service and execute
        with patch.dict("os.environ", {"GOOGLE_ADS_DEVELOPER_TOKEN": "test_token"}):
            service = GoogleAdsService()

            # Create ad group
            ad_group_result = await service.create_ad_group(
                connection_id=1,
                customer_id="1234567890",
                campaign_id="12345",
                ad_group_name="Product Ads",
                cpc_bid_micros=2000000,
            )

            assert ad_group_result["success"] is True

            # Create ad
            ad_result = await service.create_responsive_search_ad(
                connection_id=1,
                customer_id="1234567890",
                ad_group_id="67890",
                headlines=["Buy Now", "Save Today", "Limited Offer"],
                descriptions=["Get 20% off", "Free shipping"],
                final_urls=["https://www.example.com/sale"],
            )

            assert ad_result["success"] is True
            assert "67890~11111" in ad_result["resource_names"][0]

    @patch("app.services.google_ads_service.get_session")
    async def test_create_ad_invalid_headlines(self, mock_get_session, mock_session):
        """Test creating ad with invalid headlines."""
        from app.services.google_ads_service import GoogleAdsService

        mock_get_session.return_value = mock_session

        service = GoogleAdsService()

        # Too few headlines
        result = await service.create_responsive_search_ad(
            connection_id=1,
            customer_id="1234567890",
            ad_group_id="67890",
            headlines=["Buy Now", "Save Today"],  # Only 2
            descriptions=["Get 20% off", "Free shipping"],
            final_urls=["https://www.example.com/sale"],
        )

        assert result["success"] is False
        assert "At least 3 headlines are required" in result["error"]

    @patch("app.services.google_ads_service.get_session")
    async def test_create_ad_headline_too_long(self, mock_get_session, mock_session):
        """Test creating ad with headline exceeding max length."""
        from app.services.google_ads_service import GoogleAdsService

        mock_get_session.return_value = mock_session

        service = GoogleAdsService()

        result = await service.create_responsive_search_ad(
            connection_id=1,
            customer_id="1234567890",
            ad_group_id="67890",
            headlines=["X" * 31, "Save Today", "Limited Offer"],  # First headline too long
            descriptions=["Get 20% off", "Free shipping"],
            final_urls=["https://www.example.com/sale"],
        )

        assert result["success"] is False
        assert "exceeds maximum length of 30 characters" in result["error"]


class TestAssetManagementWorkflow:
    """Test asset management workflows."""

    @patch("app.services.google_ads_service.get_session")
    @patch("app.services.google_ads_service.GoogleAdsClient")
    @patch("app.services.google_ads_service.get_google_client_id")
    @patch("app.services.google_ads_service.get_google_client_secret")
    async def test_upload_and_link_asset(
        self,
        mock_get_secret,
        mock_get_id,
        mock_ads_client_class,
        mock_get_session,
        mock_google_ads_client,
        mock_session,
    ):
        """Test uploading and linking an asset to campaign."""
        from app.services.google_ads_service import GoogleAdsService

        # Setup mocks
        mock_get_id.return_value = "test_client_id"
        mock_get_secret.return_value = "test_client_secret"
        mock_get_session.return_value = mock_session
        mock_ads_client_class.load_from_dict.return_value = mock_google_ads_client

        # Mock asset upload response
        asset_response = Mock()
        asset_result = Mock()
        asset_result.resource_name = "customers/1234567890/assets/11111"
        asset_response.results = [asset_result]

        # Mock asset link response
        link_response = Mock()
        link_result = Mock()
        link_result.resource_name = "customers/1234567890/campaignAssets/12345~11111~MARKETING_IMAGE"
        link_response.results = [link_result]

        def get_service_side_effect(name):
            if name == "AssetService":
                service = Mock()
                service.mutate_assets.return_value = asset_response
                return service
            elif name == "CampaignAssetService":
                service = Mock()
                service.mutate_campaign_assets.return_value = link_response
                return service

        mock_google_ads_client.get_service.side_effect = get_service_side_effect

        # Create service and execute
        with patch.dict("os.environ", {"GOOGLE_ADS_DEVELOPER_TOKEN": "test_token"}):
            service = GoogleAdsService()

            # Upload asset
            upload_result = await service.upload_image_asset(
                connection_id=1,
                customer_id="1234567890",
                asset_name="Product Image",
                image_data=b"fake_image_data",
                mime_type="IMAGE_PNG",
            )

            assert upload_result["success"] is True
            assert "11111" in upload_result["resource_names"][0]

            # Link asset
            link_result = await service.link_asset_to_campaign(
                connection_id=1,
                customer_id="1234567890",
                asset_resource_name="customers/1234567890/assets/11111",
                campaign_id="12345",
                field_type="MARKETING_IMAGE",
            )

            assert link_result["success"] is True

    @patch("app.services.google_ads_service.get_session")
    async def test_upload_asset_too_large(self, mock_get_session, mock_session):
        """Test uploading asset with size exceeding maximum."""
        from app.services.google_ads_service import GoogleAdsService

        mock_get_session.return_value = mock_session

        service = GoogleAdsService()

        # 6MB image (exceeds 5MB max)
        large_image = b"X" * (6 * 1024 * 1024)

        result = await service.upload_image_asset(
            connection_id=1,
            customer_id="1234567890",
            asset_name="Large Image",
            image_data=large_image,
            mime_type="IMAGE_PNG",
        )

        assert result["success"] is False
        assert "exceeds maximum allowed size" in result["error"]


class TestBiddingStrategyWorkflow:
    """Test bidding strategy update workflows."""

    @patch("app.services.google_ads_service.get_session")
    @patch("app.services.google_ads_service.GoogleAdsClient")
    @patch("app.services.google_ads_service.get_google_client_id")
    @patch("app.services.google_ads_service.get_google_client_secret")
    async def test_update_bidding_to_target_cpa(
        self,
        mock_get_secret,
        mock_get_id,
        mock_ads_client_class,
        mock_get_session,
        mock_google_ads_client,
        mock_session,
    ):
        """Test updating campaign bidding strategy to TARGET_CPA."""
        from app.services.google_ads_service import GoogleAdsService

        # Setup mocks
        mock_get_id.return_value = "test_client_id"
        mock_get_secret.return_value = "test_client_secret"
        mock_get_session.return_value = mock_session
        mock_ads_client_class.load_from_dict.return_value = mock_google_ads_client

        # Mock campaign update response
        campaign_response = Mock()
        campaign_result = Mock()
        campaign_result.resource_name = "customers/1234567890/campaigns/12345"
        campaign_response.results = [campaign_result]

        mock_campaign_service = Mock()
        mock_campaign_service.mutate_campaigns.return_value = campaign_response
        mock_google_ads_client.get_service.return_value = mock_campaign_service

        # Create service and execute
        with patch.dict("os.environ", {"GOOGLE_ADS_DEVELOPER_TOKEN": "test_token"}):
            service = GoogleAdsService()

            result = await service.update_campaign_bidding_strategy(
                connection_id=1,
                customer_id="1234567890",
                campaign_id="12345",
                bidding_strategy_type="TARGET_CPA",
                bidding_config={"target_cpa_micros": 5000000},
            )

        # Verify result
        assert result["success"] is True
        assert "12345" in result["resource_names"][0]

    @patch("app.services.google_ads_service.get_session")
    async def test_update_bidding_invalid_config(self, mock_get_session, mock_session):
        """Test updating bidding strategy with invalid config."""
        from app.services.google_ads_service import GoogleAdsService

        mock_get_session.return_value = mock_session

        service = GoogleAdsService()

        result = await service.update_campaign_bidding_strategy(
            connection_id=1,
            customer_id="1234567890",
            campaign_id="12345",
            bidding_strategy_type="TARGET_ROAS",
            bidding_config={"target_roas": 0},  # Invalid: must be > 0
        )

        assert result["success"] is False
        assert "target_roas must be greater than 0" in result["error"]


class TestErrorHandling:
    """Test error handling across all workflows."""

    @patch("app.services.google_ads_service.get_session")
    async def test_missing_developer_token(self, mock_get_session, mock_session):
        """Test operations fail gracefully when developer token is missing."""
        from app.services.google_ads_service import GoogleAdsService

        mock_get_session.return_value = mock_session

        service = GoogleAdsService()

        # Ensure GOOGLE_ADS_DEVELOPER_TOKEN is not set
        with patch.dict("os.environ", {}, clear=True):
            result = await service.create_campaign(
                connection_id=1,
                customer_id="1234567890",
                campaign_name="Test Campaign",
                budget_amount_micros=50000000,
                campaign_type="SEARCH",
                bidding_strategy_type="MAXIMIZE_CONVERSIONS",
            )

        assert result["success"] is False
        assert "GOOGLE_ADS_DEVELOPER_TOKEN is required" in result["error"]
