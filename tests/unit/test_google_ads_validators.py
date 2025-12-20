"""
Unit tests for Google Ads validation functions.
Tests all validation functions in app/services/google_ads_validators.py
"""

import pytest
from app.services.google_ads_validators import ValidationError


class TestBudgetValidation:
    """Test budget validation functions."""

    def test_validate_budget_amount_valid(self):
        """Test budget validation with valid amounts."""
        from app.services.google_ads_validators import validate_budget_amount

        # Should not raise for valid amounts
        validate_budget_amount(1000000)  # $1
        validate_budget_amount(50000000)  # $50
        validate_budget_amount(1000000000)  # $1000

    def test_validate_budget_amount_zero(self):
        """Test budget validation with zero amount."""
        from app.services.google_ads_validators import validate_budget_amount

        with pytest.raises(ValidationError, match="budget must be greater than 0"):
            validate_budget_amount(0)

    def test_validate_budget_amount_negative(self):
        """Test budget validation with negative amount."""
        from app.services.google_ads_validators import validate_budget_amount

        with pytest.raises(ValidationError, match="budget must be greater than 0"):
            validate_budget_amount(-1000000)

    def test_validate_budget_amount_exceeds_maximum(self):
        """Test budget validation with amount exceeding maximum."""
        from app.services.google_ads_validators import validate_budget_amount

        with pytest.raises(ValidationError, match="exceeds maximum allowed value"):
            validate_budget_amount(2_000_000_000_000)  # $2M (exceeds $1M max)

    def test_validate_budget_amount_custom_field_name(self):
        """Test budget validation with custom field name."""
        from app.services.google_ads_validators import validate_budget_amount

        with pytest.raises(ValidationError, match="target_cpa must be greater than 0"):
            validate_budget_amount(0, field_name="target_cpa")


class TestCampaignValidation:
    """Test campaign validation functions."""

    def test_validate_campaign_name_valid(self):
        """Test campaign name validation with valid names."""
        from app.services.google_ads_validators import validate_campaign_name

        validate_campaign_name("Summer Sale 2024")
        validate_campaign_name("A")  # Single character
        validate_campaign_name("X" * 255)  # Maximum length

    def test_validate_campaign_name_empty(self):
        """Test campaign name validation with empty name."""
        from app.services.google_ads_validators import validate_campaign_name

        with pytest.raises(ValidationError, match="Campaign name cannot be empty"):
            validate_campaign_name("")

    def test_validate_campaign_name_whitespace_only(self):
        """Test campaign name validation with whitespace-only name."""
        from app.services.google_ads_validators import validate_campaign_name

        with pytest.raises(ValidationError, match="Campaign name cannot be empty"):
            validate_campaign_name("   ")

    def test_validate_campaign_name_too_long(self):
        """Test campaign name validation with name exceeding max length."""
        from app.services.google_ads_validators import validate_campaign_name

        with pytest.raises(ValidationError, match="cannot exceed 255 characters"):
            validate_campaign_name("X" * 256)

    def test_validate_campaign_type_valid(self):
        """Test campaign type validation with valid types."""
        from app.services.google_ads_validators import validate_campaign_type

        validate_campaign_type("SEARCH")
        validate_campaign_type("DISPLAY")
        validate_campaign_type("SHOPPING")
        validate_campaign_type("VIDEO")
        validate_campaign_type("PERFORMANCE_MAX")
        validate_campaign_type("MULTI_CHANNEL")
        validate_campaign_type("LOCAL")
        validate_campaign_type("HOTEL")

    def test_validate_campaign_type_invalid(self):
        """Test campaign type validation with invalid type."""
        from app.services.google_ads_validators import validate_campaign_type

        with pytest.raises(ValidationError, match="Invalid campaign type"):
            validate_campaign_type("INVALID_TYPE")

    def test_validate_campaign_status_valid(self):
        """Test campaign status validation with valid statuses."""
        from app.services.google_ads_validators import validate_campaign_status

        validate_campaign_status("ENABLED")
        validate_campaign_status("PAUSED")
        validate_campaign_status("REMOVED")

    def test_validate_campaign_status_invalid(self):
        """Test campaign status validation with invalid status."""
        from app.services.google_ads_validators import validate_campaign_status

        with pytest.raises(ValidationError, match="Invalid status"):
            validate_campaign_status("ACTIVE")

    def test_validate_date_format_valid(self):
        """Test date format validation with valid dates."""
        from app.services.google_ads_validators import validate_date_format

        validate_date_format("2024-01-01")
        validate_date_format("2024-12-31")
        validate_date_format("2024-06-15")

    def test_validate_date_format_invalid(self):
        """Test date format validation with invalid formats."""
        from app.services.google_ads_validators import validate_date_format

        with pytest.raises(ValidationError, match="must be in YYYY-MM-DD format"):
            validate_date_format("01-01-2024")

        with pytest.raises(ValidationError, match="must be in YYYY-MM-DD format"):
            validate_date_format("2024/01/01")

        with pytest.raises(ValidationError, match="must be in YYYY-MM-DD format"):
            validate_date_format("2024-1-1")

    def test_validate_date_format_custom_field_name(self):
        """Test date format validation with custom field name."""
        from app.services.google_ads_validators import validate_date_format

        with pytest.raises(ValidationError, match="start_date must be in YYYY-MM-DD format"):
            validate_date_format("invalid", field_name="start_date")


class TestBiddingValidation:
    """Test bidding strategy validation functions."""

    def test_validate_bidding_strategy_valid(self):
        """Test bidding strategy validation with valid strategies."""
        from app.services.google_ads_validators import validate_bidding_strategy

        validate_bidding_strategy("TARGET_CPA")
        validate_bidding_strategy("TARGET_ROAS")
        validate_bidding_strategy("MAXIMIZE_CONVERSIONS")
        validate_bidding_strategy("MAXIMIZE_CONVERSION_VALUE")
        validate_bidding_strategy("TARGET_SPEND")
        validate_bidding_strategy("TARGET_IMPRESSION_SHARE")
        validate_bidding_strategy("MANUAL_CPC")
        validate_bidding_strategy("MANUAL_CPM")

    def test_validate_bidding_strategy_invalid(self):
        """Test bidding strategy validation with invalid strategy."""
        from app.services.google_ads_validators import validate_bidding_strategy

        with pytest.raises(ValidationError, match="Invalid bidding strategy"):
            validate_bidding_strategy("INVALID_STRATEGY")

    def test_validate_bidding_strategy_target_cpa_valid(self):
        """Test TARGET_CPA bidding strategy with valid config."""
        from app.services.google_ads_validators import validate_bidding_strategy

        validate_bidding_strategy("TARGET_CPA", {"target_cpa_micros": 5000000})

    def test_validate_bidding_strategy_target_cpa_invalid(self):
        """Test TARGET_CPA bidding strategy with invalid config."""
        from app.services.google_ads_validators import validate_bidding_strategy

        with pytest.raises(ValidationError, match="target_cpa_micros must be greater than 0"):
            validate_bidding_strategy("TARGET_CPA", {"target_cpa_micros": 0})

    def test_validate_bidding_strategy_target_roas_valid(self):
        """Test TARGET_ROAS bidding strategy with valid config."""
        from app.services.google_ads_validators import validate_bidding_strategy

        validate_bidding_strategy("TARGET_ROAS", {"target_roas": 4.0})

    def test_validate_bidding_strategy_target_roas_invalid(self):
        """Test TARGET_ROAS bidding strategy with invalid config."""
        from app.services.google_ads_validators import validate_bidding_strategy

        with pytest.raises(ValidationError, match="target_roas must be greater than 0"):
            validate_bidding_strategy("TARGET_ROAS", {"target_roas": 0})

        with pytest.raises(ValidationError, match="target_roas must be greater than 0"):
            validate_bidding_strategy("TARGET_ROAS", {"target_roas": -1.5})


class TestAdValidation:
    """Test ad validation functions."""

    def test_validate_headlines_valid(self):
        """Test headline validation with valid headlines."""
        from app.services.google_ads_validators import validate_headlines

        # Minimum 3 headlines
        validate_headlines(["Buy Now", "Save Today", "Limited Offer"])

        # Maximum 15 headlines
        validate_headlines([f"Headline {i}" for i in range(1, 16)])

    def test_validate_headlines_too_few(self):
        """Test headline validation with too few headlines."""
        from app.services.google_ads_validators import validate_headlines

        with pytest.raises(ValidationError, match="At least 3 headlines are required"):
            validate_headlines(["Buy Now", "Save Today"])

    def test_validate_headlines_too_many(self):
        """Test headline validation with too many headlines."""
        from app.services.google_ads_validators import validate_headlines

        with pytest.raises(ValidationError, match="Maximum 15 headlines allowed"):
            validate_headlines([f"Headline {i}" for i in range(1, 17)])

    def test_validate_headlines_empty_headline(self):
        """Test headline validation with empty headline."""
        from app.services.google_ads_validators import validate_headlines

        with pytest.raises(ValidationError, match="Headline 2 cannot be empty"):
            validate_headlines(["Buy Now", "", "Limited Offer"])

    def test_validate_headlines_whitespace_only(self):
        """Test headline validation with whitespace-only headline."""
        from app.services.google_ads_validators import validate_headlines

        with pytest.raises(ValidationError, match="Headline 3 cannot be empty"):
            validate_headlines(["Buy Now", "Save Today", "   "])

    def test_validate_headlines_too_long(self):
        """Test headline validation with headline exceeding max length."""
        from app.services.google_ads_validators import validate_headlines

        with pytest.raises(ValidationError, match="Headline 1 exceeds maximum length of 30 characters"):
            validate_headlines(["X" * 31, "Save Today", "Limited Offer"])

    def test_validate_descriptions_valid(self):
        """Test description validation with valid descriptions."""
        from app.services.google_ads_validators import validate_descriptions

        # Minimum 2 descriptions
        validate_descriptions(["Get 20% off", "Free shipping"])

        # Maximum 4 descriptions
        validate_descriptions([f"Description {i}" for i in range(1, 5)])

    def test_validate_descriptions_too_few(self):
        """Test description validation with too few descriptions."""
        from app.services.google_ads_validators import validate_descriptions

        with pytest.raises(ValidationError, match="At least 2 descriptions are required"):
            validate_descriptions(["Get 20% off"])

    def test_validate_descriptions_too_many(self):
        """Test description validation with too many descriptions."""
        from app.services.google_ads_validators import validate_descriptions

        with pytest.raises(ValidationError, match="Maximum 4 descriptions allowed"):
            validate_descriptions([f"Description {i}" for i in range(1, 6)])

    def test_validate_descriptions_empty(self):
        """Test description validation with empty description."""
        from app.services.google_ads_validators import validate_descriptions

        with pytest.raises(ValidationError, match="Description 1 cannot be empty"):
            validate_descriptions(["", "Free shipping"])

    def test_validate_descriptions_too_long(self):
        """Test description validation with description exceeding max length."""
        from app.services.google_ads_validators import validate_descriptions

        with pytest.raises(ValidationError, match="Description 2 exceeds maximum length of 90 characters"):
            validate_descriptions(["Get 20% off", "X" * 91])

    def test_validate_final_urls_valid(self):
        """Test final URL validation with valid URLs."""
        from app.services.google_ads_validators import validate_final_urls

        validate_final_urls(["https://www.example.com"])
        validate_final_urls(["http://example.com/sale"])
        validate_final_urls(["https://example.com:8080/path"])
        validate_final_urls(["http://localhost:3000/test"])

    def test_validate_final_urls_empty(self):
        """Test final URL validation with empty list."""
        from app.services.google_ads_validators import validate_final_urls

        with pytest.raises(ValidationError, match="At least one final URL is required"):
            validate_final_urls([])

    def test_validate_final_urls_invalid_format(self):
        """Test final URL validation with invalid URL format."""
        from app.services.google_ads_validators import validate_final_urls

        with pytest.raises(ValidationError, match="Invalid URL format"):
            validate_final_urls(["not-a-url"])

        with pytest.raises(ValidationError, match="Invalid URL format"):
            validate_final_urls(["ftp://example.com"])

    def test_validate_display_path_valid(self):
        """Test display path validation with valid paths."""
        from app.services.google_ads_validators import validate_display_path

        validate_display_path("sale", "path1")
        validate_display_path("products", "path2")
        validate_display_path("", "path1")  # Empty is allowed

    def test_validate_display_path_too_long(self):
        """Test display path validation with path exceeding max length."""
        from app.services.google_ads_validators import validate_display_path

        with pytest.raises(ValidationError, match="path1 cannot exceed 15 characters"):
            validate_display_path("X" * 16, "path1")

    def test_validate_ad_group_name_valid(self):
        """Test ad group name validation with valid names."""
        from app.services.google_ads_validators import validate_ad_group_name

        validate_ad_group_name("Product Ads")
        validate_ad_group_name("A")
        validate_ad_group_name("X" * 255)

    def test_validate_ad_group_name_empty(self):
        """Test ad group name validation with empty name."""
        from app.services.google_ads_validators import validate_ad_group_name

        with pytest.raises(ValidationError, match="Ad group name cannot be empty"):
            validate_ad_group_name("")

    def test_validate_ad_group_name_too_long(self):
        """Test ad group name validation with name exceeding max length."""
        from app.services.google_ads_validators import validate_ad_group_name

        with pytest.raises(ValidationError, match="cannot exceed 255 characters"):
            validate_ad_group_name("X" * 256)


class TestAssetValidation:
    """Test asset validation functions."""

    def test_validate_asset_name_valid(self):
        """Test asset name validation with valid names."""
        from app.services.google_ads_validators import validate_asset_name

        validate_asset_name("Product Image")
        validate_asset_name("A")
        validate_asset_name("X" * 255)

    def test_validate_asset_name_empty(self):
        """Test asset name validation with empty name."""
        from app.services.google_ads_validators import validate_asset_name

        with pytest.raises(ValidationError, match="Asset name cannot be empty"):
            validate_asset_name("")

    def test_validate_asset_name_too_long(self):
        """Test asset name validation with name exceeding max length."""
        from app.services.google_ads_validators import validate_asset_name

        with pytest.raises(ValidationError, match="cannot exceed 255 characters"):
            validate_asset_name("X" * 256)

    def test_validate_image_data_valid(self):
        """Test image data validation with valid data."""
        from app.services.google_ads_validators import validate_image_data

        validate_image_data(b"fake_image_data")
        validate_image_data(b"X" * (5 * 1024 * 1024))  # 5MB exactly

    def test_validate_image_data_empty(self):
        """Test image data validation with empty data."""
        from app.services.google_ads_validators import validate_image_data

        with pytest.raises(ValidationError, match="Image data cannot be empty"):
            validate_image_data(b"")

    def test_validate_image_data_too_large(self):
        """Test image data validation with data exceeding max size."""
        from app.services.google_ads_validators import validate_image_data

        with pytest.raises(ValidationError, match="exceeds maximum allowed size"):
            validate_image_data(b"X" * (6 * 1024 * 1024))  # 6MB

    def test_validate_asset_field_type_valid(self):
        """Test asset field type validation with valid types."""
        from app.services.google_ads_validators import validate_asset_field_type

        validate_asset_field_type("MARKETING_IMAGE")
        validate_asset_field_type("LOGO")
        validate_asset_field_type("LANDSCAPE_LOGO")
        validate_asset_field_type("SQUARE_MARKETING_IMAGE")
        validate_asset_field_type("PORTRAIT_MARKETING_IMAGE")

    def test_validate_asset_field_type_invalid(self):
        """Test asset field type validation with invalid type."""
        from app.services.google_ads_validators import validate_asset_field_type

        with pytest.raises(ValidationError, match="Invalid asset field type"):
            validate_asset_field_type("INVALID_TYPE")


class TestCustomerIdValidation:
    """Test customer ID validation functions."""

    def test_validate_customer_id_valid(self):
        """Test customer ID validation with valid IDs."""
        from app.services.google_ads_validators import validate_customer_id

        validate_customer_id("1234567890")
        validate_customer_id("123-456-7890")  # With dashes

    def test_validate_customer_id_empty(self):
        """Test customer ID validation with empty ID."""
        from app.services.google_ads_validators import validate_customer_id

        with pytest.raises(ValidationError, match="Customer ID cannot be empty"):
            validate_customer_id("")

    def test_validate_customer_id_non_digits(self):
        """Test customer ID validation with non-digit characters."""
        from app.services.google_ads_validators import validate_customer_id

        with pytest.raises(ValidationError, match="must contain only digits"):
            validate_customer_id("ABC1234567")

    def test_validate_customer_id_wrong_length(self):
        """Test customer ID validation with wrong length."""
        from app.services.google_ads_validators import validate_customer_id

        with pytest.raises(ValidationError, match="must be 10 digits"):
            validate_customer_id("123456789")  # 9 digits

        with pytest.raises(ValidationError, match="must be 10 digits"):
            validate_customer_id("12345678901")  # 11 digits

    def test_format_customer_id_basic(self):
        """Test customer ID formatting with basic input."""
        from app.services.google_ads_validators import format_customer_id

        assert format_customer_id("1234567890") == "1234567890"
        assert format_customer_id("123-456-7890") == "1234567890"
        assert format_customer_id("123 456 7890") == "1234567890"

    def test_format_customer_id_short(self):
        """Test customer ID formatting with short input."""
        from app.services.google_ads_validators import format_customer_id

        assert format_customer_id("123") == "0000000123"  # Padded to 10 digits

    def test_format_customer_id_mixed_characters(self):
        """Test customer ID formatting with mixed characters."""
        from app.services.google_ads_validators import format_customer_id

        assert format_customer_id("ABC-123-XYZ-456-7890") == "1234567890"
