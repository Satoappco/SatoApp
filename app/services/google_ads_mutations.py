"""
Google Ads API mutation helpers - Reusable functions for common operations.
Follows DRY principles and single responsibility pattern.
"""
from typing import Any, Dict, List, Optional
from google.ads.googleads.client import GoogleAdsClient
from google.protobuf import field_mask_pb2
import logging

logger = logging.getLogger(__name__)


# === Client & Service Helpers ===

def get_campaign_service(client: GoogleAdsClient):
    """Get campaign service from client."""
    return client.get_service("CampaignService")


def get_campaign_budget_service(client: GoogleAdsClient):
    """Get campaign budget service from client."""
    return client.get_service("CampaignBudgetService")


def get_asset_service(client: GoogleAdsClient):
    """Get asset service from client."""
    return client.get_service("AssetService")


def get_campaign_asset_service(client: GoogleAdsClient):
    """Get campaign asset service from client."""
    return client.get_service("CampaignAssetService")


def get_ad_group_service(client: GoogleAdsClient):
    """Get ad group service from client."""
    return client.get_service("AdGroupService")


def get_ad_group_ad_service(client: GoogleAdsClient):
    """Get ad group ad service from client."""
    return client.get_service("AdGroupAdService")


def get_bidding_strategy_service(client: GoogleAdsClient):
    """Get bidding strategy service from client."""
    return client.get_service("BiddingStrategyService")


# === Resource Name Helpers ===

def build_campaign_resource_name(customer_id: str, campaign_id: str) -> str:
    """Build campaign resource name."""
    return f"customers/{customer_id}/campaigns/{campaign_id}"


def build_budget_resource_name(customer_id: str, budget_id: str) -> str:
    """Build budget resource name."""
    return f"customers/{customer_id}/campaignBudgets/{budget_id}"


def build_ad_group_resource_name(customer_id: str, ad_group_id: str) -> str:
    """Build ad group resource name."""
    return f"customers/{customer_id}/adGroups/{ad_group_id}"


def build_asset_resource_name(customer_id: str, asset_id: str) -> str:
    """Build asset resource name."""
    return f"customers/{customer_id}/assets/{asset_id}"


def extract_id_from_resource_name(resource_name: str) -> str:
    """Extract ID from resource name (e.g., 'customers/123/campaigns/456' -> '456')."""
    return resource_name.split("/")[-1]


# === Budget Operations ===

def create_budget_operation(
    client: GoogleAdsClient,
    budget_name: str,
    amount_micros: int,
    delivery_method: str = "STANDARD",
    explicitly_shared: bool = False,
):
    """Create a budget operation for mutation."""
    budget_operation = client.get_type("CampaignBudgetOperation")
    budget = budget_operation.create

    budget.name = budget_name
    budget.amount_micros = amount_micros
    budget.delivery_method = getattr(
        client.enums.BudgetDeliveryMethodEnum,
        delivery_method
    )
    budget.explicitly_shared = explicitly_shared

    return budget_operation


def update_budget_operation(
    client: GoogleAdsClient,
    budget_resource_name: str,
    new_amount_micros: int,
):
    """Create a budget update operation."""
    budget_operation = client.get_type("CampaignBudgetOperation")
    budget = budget_operation.update

    budget.resource_name = budget_resource_name
    budget.amount_micros = new_amount_micros

    budget_operation.update_mask.CopyFrom(
        field_mask_pb2.FieldMask(paths=["amount_micros"])
    )

    return budget_operation


# === Campaign Operations ===

def create_campaign_operation(
    client: GoogleAdsClient,
    campaign_name: str,
    budget_resource_name: str,
    channel_type: str,
    status: str = "PAUSED",
):
    """Create a campaign operation for mutation."""
    campaign_operation = client.get_type("CampaignOperation")
    campaign = campaign_operation.create

    campaign.name = campaign_name
    campaign.campaign_budget = budget_resource_name
    campaign.status = getattr(client.enums.CampaignStatusEnum, status)
    campaign.advertising_channel_type = getattr(
        client.enums.AdvertisingChannelTypeEnum,
        channel_type
    )

    return campaign_operation


def apply_network_settings(
    campaign,
    target_google_search: bool = True,
    target_search_network: bool = True,
    target_content_network: bool = False,
):
    """Apply network settings to campaign."""
    campaign.network_settings.target_google_search = target_google_search
    campaign.network_settings.target_search_network = target_search_network
    campaign.network_settings.target_content_network = target_content_network


def apply_bidding_strategy(
    client: GoogleAdsClient,
    campaign,
    strategy_type: str,
    strategy_config: Optional[Dict[str, Any]] = None,
):
    """Apply bidding strategy to campaign."""
    strategy_config = strategy_config or {}

    if strategy_type == "MAXIMIZE_CONVERSIONS":
        campaign.maximize_conversions.CopyFrom(
            client.get_type("MaximizeConversions")
        )
    elif strategy_type == "MAXIMIZE_CONVERSION_VALUE":
        campaign.maximize_conversion_value.CopyFrom(
            client.get_type("MaximizeConversionValue")
        )
    elif strategy_type == "TARGET_CPA":
        target_cpa_micros = strategy_config.get("target_cpa_micros", 0)
        campaign.target_cpa.target_cpa_micros = target_cpa_micros
    elif strategy_type == "TARGET_ROAS":
        target_roas = strategy_config.get("target_roas", 0)
        campaign.target_roas.target_roas = target_roas
    elif strategy_type == "TARGET_SPEND":
        target_spend = client.get_type("TargetSpend")
        if "cpc_bid_ceiling_micros" in strategy_config:
            target_spend.cpc_bid_ceiling_micros = strategy_config["cpc_bid_ceiling_micros"]
        campaign.target_spend.CopyFrom(target_spend)
    elif strategy_type == "MANUAL_CPC":
        manual_cpc = client.get_type("ManualCpc")
        if "enhanced_cpc_enabled" in strategy_config:
            manual_cpc.enhanced_cpc_enabled = strategy_config["enhanced_cpc_enabled"]
        campaign.manual_cpc.CopyFrom(manual_cpc)
    else:
        raise ValueError(f"Unsupported bidding strategy: {strategy_type}")


def update_campaign_field(
    client: GoogleAdsClient,
    campaign_resource_name: str,
    field_updates: Dict[str, Any],
):
    """Create campaign update operation with field mask."""
    campaign_operation = client.get_type("CampaignOperation")
    campaign = campaign_operation.update

    campaign.resource_name = campaign_resource_name

    # Apply field updates
    field_paths = []
    for field_name, value in field_updates.items():
        if field_name == "status":
            campaign.status = getattr(client.enums.CampaignStatusEnum, value)
            field_paths.append("status")
        elif field_name == "name":
            campaign.name = value
            field_paths.append("name")
        elif field_name == "target_cpa_micros":
            campaign.target_cpa.target_cpa_micros = value
            field_paths.append("target_cpa.target_cpa_micros")
        elif field_name == "target_roas":
            campaign.target_roas.target_roas = value
            field_paths.append("target_roas.target_roas")
        elif field_name == "start_date":
            campaign.start_date = value
            field_paths.append("start_date")
        elif field_name == "end_date":
            campaign.end_date = value
            field_paths.append("end_date")

    # Generate field mask
    campaign_operation.update_mask.CopyFrom(
        field_mask_pb2.FieldMask(paths=field_paths)
    )

    return campaign_operation


# === Asset Operations ===

def create_image_asset_operation(
    client: GoogleAdsClient,
    asset_name: str,
    image_data: bytes,
    mime_type: str = "IMAGE_PNG",
):
    """Create an image asset operation."""
    asset_operation = client.get_type("AssetOperation")
    asset = asset_operation.create

    asset.name = asset_name
    asset.type_ = client.enums.AssetTypeEnum.IMAGE
    asset.image_asset.data = image_data
    asset.image_asset.file_size = len(image_data)
    asset.image_asset.mime_type = getattr(client.enums.MimeTypeEnum, mime_type)

    return asset_operation


def create_campaign_asset_link_operation(
    client: GoogleAdsClient,
    asset_resource_name: str,
    campaign_resource_name: str,
    field_type: str = "MARKETING_IMAGE",
):
    """Create campaign asset link operation."""
    campaign_asset_operation = client.get_type("CampaignAssetOperation")
    campaign_asset = campaign_asset_operation.create

    campaign_asset.asset = asset_resource_name
    campaign_asset.campaign = campaign_resource_name
    campaign_asset.field_type = getattr(
        client.enums.AssetFieldTypeEnum,
        field_type
    )

    return campaign_asset_operation


def remove_campaign_asset_link_operation(
    client: GoogleAdsClient,
    campaign_asset_resource_name: str,
):
    """Create operation to remove campaign asset link."""
    campaign_asset_operation = client.get_type("CampaignAssetOperation")
    campaign_asset_operation.remove = campaign_asset_resource_name
    return campaign_asset_operation


# === Ad Operations ===

def create_ad_group_operation(
    client: GoogleAdsClient,
    ad_group_name: str,
    campaign_resource_name: str,
    cpc_bid_micros: Optional[int] = None,
    status: str = "ENABLED",
):
    """Create ad group operation."""
    ad_group_operation = client.get_type("AdGroupOperation")
    ad_group = ad_group_operation.create

    ad_group.name = ad_group_name
    ad_group.campaign = campaign_resource_name
    ad_group.status = getattr(client.enums.AdGroupStatusEnum, status)
    ad_group.type_ = client.enums.AdGroupTypeEnum.SEARCH_STANDARD

    if cpc_bid_micros:
        ad_group.cpc_bid_micros = cpc_bid_micros

    return ad_group_operation


def create_text_asset(client: GoogleAdsClient, text: str):
    """Create a text asset for ads."""
    text_asset = client.get_type("AdTextAsset")
    text_asset.text = text
    return text_asset


def create_responsive_search_ad_operation(
    client: GoogleAdsClient,
    ad_group_resource_name: str,
    headlines: List[str],
    descriptions: List[str],
    final_urls: List[str],
    path1: Optional[str] = None,
    path2: Optional[str] = None,
):
    """Create responsive search ad operation."""
    ad_group_ad_operation = client.get_type("AdGroupAdOperation")
    ad_group_ad = ad_group_ad_operation.create

    ad_group_ad.ad_group = ad_group_resource_name
    ad_group_ad.status = client.enums.AdGroupAdStatusEnum.ENABLED

    # Add final URLs
    ad_group_ad.ad.final_urls.extend(final_urls)

    # Add display paths
    if path1:
        ad_group_ad.ad.display_url_path1 = path1
    if path2:
        ad_group_ad.ad.display_url_path2 = path2

    # Add headlines
    for headline_text in headlines:
        ad_group_ad.ad.responsive_search_ad.headlines.append(
            create_text_asset(client, headline_text)
        )

    # Add descriptions
    for description_text in descriptions:
        ad_group_ad.ad.responsive_search_ad.descriptions.append(
            create_text_asset(client, description_text)
        )

    return ad_group_ad_operation


def update_ad_status_operation(
    client: GoogleAdsClient,
    ad_group_ad_resource_name: str,
    status: str,
):
    """Create operation to update ad status."""
    ad_group_ad_operation = client.get_type("AdGroupAdOperation")
    ad_group_ad = ad_group_ad_operation.update

    ad_group_ad.resource_name = ad_group_ad_resource_name
    ad_group_ad.status = getattr(client.enums.AdGroupAdStatusEnum, status)

    ad_group_ad_operation.update_mask.CopyFrom(
        field_mask_pb2.FieldMask(paths=["status"])
    )

    return ad_group_ad_operation


# === Execution Helpers ===

def execute_mutation(
    service_method,
    customer_id: str,
    operations: List[Any],
    operation_name: str,
) -> Dict[str, Any]:
    """Execute mutation and return standardized response."""
    try:
        logger.info(f"Executing {operation_name} for customer {customer_id}")

        # Call the service method
        response = service_method(customer_id=customer_id, operations=operations)

        # Extract resource names
        resource_names = [result.resource_name for result in response.results]

        logger.info(f"{operation_name} successful: {len(resource_names)} resources created/updated")

        return {
            "success": True,
            "resource_names": resource_names,
            "count": len(resource_names),
        }
    except Exception as e:
        logger.error(f"{operation_name} failed: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
        }


def convert_micros_to_currency(micros: int) -> float:
    """Convert micros to currency amount."""
    return micros / 1_000_000


def convert_currency_to_micros(amount: float) -> int:
    """Convert currency amount to micros."""
    return int(amount * 1_000_000)
