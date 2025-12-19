"""
Google Ads input validation helpers.
Validates parameters before sending to Google Ads API.
"""
from typing import List, Optional
import re


class ValidationError(Exception):
    """Custom exception for validation errors."""
    pass


# === Budget Validation ===

def validate_budget_amount(amount_micros: int, field_name: str = "budget") -> None:
    """Validate budget amount in micros."""
    if amount_micros <= 0:
        raise ValidationError(f"{field_name} must be greater than 0")

    # Maximum daily budget is $1,000,000 (1 trillion micros)
    if amount_micros > 1_000_000_000_000:
        raise ValidationError(f"{field_name} exceeds maximum allowed value")


# === Campaign Validation ===

def validate_campaign_name(name: str) -> None:
    """Validate campaign name."""
    if not name or not name.strip():
        raise ValidationError("Campaign name cannot be empty")

    if len(name) > 255:
        raise ValidationError("Campaign name cannot exceed 255 characters")


def validate_campaign_type(campaign_type: str) -> None:
    """Validate campaign type."""
    valid_types = [
        "SEARCH", "DISPLAY", "SHOPPING", "VIDEO",
        "MULTI_CHANNEL", "PERFORMANCE_MAX", "LOCAL", "HOTEL"
    ]

    if campaign_type not in valid_types:
        raise ValidationError(
            f"Invalid campaign type: {campaign_type}. Must be one of {valid_types}"
        )


def validate_bidding_strategy(strategy_type: str, strategy_config: Optional[dict] = None) -> None:
    """Validate bidding strategy and configuration."""
    valid_strategies = [
        "TARGET_CPA", "TARGET_ROAS", "MAXIMIZE_CONVERSIONS",
        "MAXIMIZE_CONVERSION_VALUE", "TARGET_SPEND",
        "TARGET_IMPRESSION_SHARE", "MANUAL_CPC", "MANUAL_CPM"
    ]

    if strategy_type not in valid_strategies:
        raise ValidationError(
            f"Invalid bidding strategy: {strategy_type}. Must be one of {valid_strategies}"
        )

    # Validate strategy-specific config
    if strategy_config:
        if strategy_type == "TARGET_CPA":
            if "target_cpa_micros" in strategy_config:
                validate_budget_amount(strategy_config["target_cpa_micros"], "target_cpa_micros")

        elif strategy_type == "TARGET_ROAS":
            if "target_roas" in strategy_config:
                if strategy_config["target_roas"] <= 0:
                    raise ValidationError("target_roas must be greater than 0")


def validate_campaign_status(status: str) -> None:
    """Validate campaign status."""
    valid_statuses = ["ENABLED", "PAUSED", "REMOVED"]

    if status not in valid_statuses:
        raise ValidationError(
            f"Invalid status: {status}. Must be one of {valid_statuses}"
        )


def validate_date_format(date_str: str, field_name: str = "date") -> None:
    """Validate date format (YYYY-MM-DD)."""
    if not re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
        raise ValidationError(
            f"{field_name} must be in YYYY-MM-DD format"
        )


# === Ad Validation ===

def validate_headlines(headlines: List[str]) -> None:
    """Validate responsive search ad headlines."""
    if len(headlines) < 3:
        raise ValidationError("At least 3 headlines are required")

    if len(headlines) > 15:
        raise ValidationError("Maximum 15 headlines allowed")

    for i, headline in enumerate(headlines):
        if not headline or not headline.strip():
            raise ValidationError(f"Headline {i+1} cannot be empty")

        if len(headline) > 30:
            raise ValidationError(
                f"Headline {i+1} exceeds maximum length of 30 characters: '{headline}'"
            )


def validate_descriptions(descriptions: List[str]) -> None:
    """Validate responsive search ad descriptions."""
    if len(descriptions) < 2:
        raise ValidationError("At least 2 descriptions are required")

    if len(descriptions) > 4:
        raise ValidationError("Maximum 4 descriptions allowed")

    for i, description in enumerate(descriptions):
        if not description or not description.strip():
            raise ValidationError(f"Description {i+1} cannot be empty")

        if len(description) > 90:
            raise ValidationError(
                f"Description {i+1} exceeds maximum length of 90 characters: '{description}'"
            )


def validate_final_urls(final_urls: List[str]) -> None:
    """Validate final URLs for ads."""
    if not final_urls or len(final_urls) == 0:
        raise ValidationError("At least one final URL is required")

    url_pattern = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE
    )

    for i, url in enumerate(final_urls):
        if not url_pattern.match(url):
            raise ValidationError(f"Invalid URL format for final_urls[{i}]: '{url}'")


def validate_display_path(path: str, field_name: str) -> None:
    """Validate display path (path1 or path2)."""
    if path and len(path) > 15:
        raise ValidationError(f"{field_name} cannot exceed 15 characters")


def validate_ad_group_name(name: str) -> None:
    """Validate ad group name."""
    if not name or not name.strip():
        raise ValidationError("Ad group name cannot be empty")

    if len(name) > 255:
        raise ValidationError("Ad group name cannot exceed 255 characters")


# === Asset Validation ===

def validate_asset_name(name: str) -> None:
    """Validate asset name."""
    if not name or not name.strip():
        raise ValidationError("Asset name cannot be empty")

    if len(name) > 255:
        raise ValidationError("Asset name cannot exceed 255 characters")


def validate_image_data(image_data: bytes) -> None:
    """Validate image asset data."""
    if not image_data:
        raise ValidationError("Image data cannot be empty")

    # Maximum file size is 5MB
    max_size = 5 * 1024 * 1024  # 5MB in bytes
    if len(image_data) > max_size:
        raise ValidationError(
            f"Image file size ({len(image_data)} bytes) exceeds maximum allowed size ({max_size} bytes)"
        )


def validate_asset_field_type(field_type: str) -> None:
    """Validate asset field type."""
    valid_types = [
        "MARKETING_IMAGE", "LOGO", "LANDSCAPE_LOGO",
        "SQUARE_MARKETING_IMAGE", "PORTRAIT_MARKETING_IMAGE"
    ]

    if field_type not in valid_types:
        raise ValidationError(
            f"Invalid asset field type: {field_type}. Must be one of {valid_types}"
        )


# === Customer ID Validation ===

def validate_customer_id(customer_id: str) -> None:
    """Validate Google Ads customer ID format."""
    if not customer_id:
        raise ValidationError("Customer ID cannot be empty")

    # Remove dashes for validation
    clean_id = customer_id.replace("-", "")

    if not clean_id.isdigit():
        raise ValidationError("Customer ID must contain only digits (and optional dashes)")

    if len(clean_id) != 10:
        raise ValidationError(f"Customer ID must be 10 digits, got {len(clean_id)}")


def format_customer_id(customer_id: str) -> str:
    """Format customer ID to 10 digits without dashes."""
    # Remove any non-digit characters
    clean_id = ''.join(char for char in str(customer_id) if char.isdigit())

    # Ensure it's 10 digits
    return clean_id.zfill(10)
