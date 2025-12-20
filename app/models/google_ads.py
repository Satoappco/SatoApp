"""
Google Ads data models for API requests and responses.
"""
from pydantic import BaseModel, Field, field_validator
from typing import List, Dict, Any, Optional
from enum import Enum


class CampaignType(str, Enum):
    """Google Ads campaign types."""
    SEARCH = "SEARCH"
    DISPLAY = "DISPLAY"
    PERFORMANCE_MAX = "PERFORMANCE_MAX"
    SHOPPING = "SHOPPING"
    VIDEO = "VIDEO"
    MULTI_CHANNEL = "MULTI_CHANNEL"
    LOCAL = "LOCAL"
    HOTEL = "HOTEL"


class CampaignStatus(str, Enum):
    """Campaign status values."""
    ENABLED = "ENABLED"
    PAUSED = "PAUSED"
    REMOVED = "REMOVED"


class AdGroupStatus(str, Enum):
    """Ad group status values."""
    ENABLED = "ENABLED"
    PAUSED = "PAUSED"
    REMOVED = "REMOVED"


class AdStatus(str, Enum):
    """Ad status values."""
    ENABLED = "ENABLED"
    PAUSED = "PAUSED"
    REMOVED = "REMOVED"


class BiddingStrategyType(str, Enum):
    """Bidding strategy types."""
    TARGET_CPA = "TARGET_CPA"
    TARGET_ROAS = "TARGET_ROAS"
    MAXIMIZE_CONVERSIONS = "MAXIMIZE_CONVERSIONS"
    MAXIMIZE_CONVERSION_VALUE = "MAXIMIZE_CONVERSION_VALUE"
    TARGET_SPEND = "TARGET_SPEND"
    TARGET_IMPRESSION_SHARE = "TARGET_IMPRESSION_SHARE"
    MANUAL_CPC = "MANUAL_CPC"
    MANUAL_CPM = "MANUAL_CPM"


class BudgetDeliveryMethod(str, Enum):
    """Budget delivery methods."""
    STANDARD = "STANDARD"
    ACCELERATED = "ACCELERATED"


class AssetFieldType(str, Enum):
    """Asset field types for linking to campaigns."""
    MARKETING_IMAGE = "MARKETING_IMAGE"
    LOGO = "LOGO"
    LANDSCAPE_LOGO = "LANDSCAPE_LOGO"
    SQUARE_MARKETING_IMAGE = "SQUARE_MARKETING_IMAGE"
    PORTRAIT_MARKETING_IMAGE = "PORTRAIT_MARKETING_IMAGE"


# === Request Models ===

class CreateCampaignRequest(BaseModel):
    """Request to create a new campaign."""
    connection_id: int = Field(..., description="Connection ID for authentication")
    customer_id: str = Field(..., description="Google Ads customer ID (10 digits)")
    campaign_name: str = Field(..., min_length=1, max_length=255, description="Campaign name")
    daily_budget_micros: int = Field(..., gt=0, description="Daily budget in micros (e.g., 50000000 = $50)")
    campaign_type: CampaignType = Field(..., description="Campaign type")
    bidding_strategy: BiddingStrategyType = Field(..., description="Bidding strategy type")
    bidding_config: Optional[Dict[str, Any]] = Field(None, description="Bidding strategy configuration")
    network_settings: Optional[Dict[str, bool]] = Field(None, description="Network settings")
    start_date: Optional[str] = Field(None, pattern=r'^\d{4}-\d{2}-\d{2}$', description="Start date (YYYY-MM-DD)")
    end_date: Optional[str] = Field(None, pattern=r'^\d{4}-\d{2}-\d{2}$', description="End date (YYYY-MM-DD)")

    @field_validator('customer_id')
    @classmethod
    def validate_customer_id(cls, v):
        """Validate customer ID format."""
        clean_id = ''.join(c for c in v if c.isdigit())
        if len(clean_id) != 10:
            raise ValueError('Customer ID must be 10 digits')
        return clean_id


class UpdateCampaignRequest(BaseModel):
    """Request to update campaign settings."""
    connection_id: int = Field(..., description="Connection ID for authentication")
    customer_id: str = Field(..., description="Google Ads customer ID")
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    status: Optional[CampaignStatus] = None
    start_date: Optional[str] = Field(None, pattern=r'^\d{4}-\d{2}-\d{2}$')
    end_date: Optional[str] = Field(None, pattern=r'^\d{4}-\d{2}-\d{2}$')

    @field_validator('customer_id')
    @classmethod
    def validate_customer_id(cls, v):
        clean_id = ''.join(c for c in v if c.isdigit())
        if len(clean_id) != 10:
            raise ValueError('Customer ID must be 10 digits')
        return clean_id


class UpdateBudgetRequest(BaseModel):
    """Request to update campaign budget."""
    connection_id: int = Field(..., description="Connection ID for authentication")
    customer_id: str = Field(..., description="Google Ads customer ID")
    new_daily_budget_micros: int = Field(..., gt=0, description="New daily budget in micros")

    @field_validator('customer_id')
    @classmethod
    def validate_customer_id(cls, v):
        clean_id = ''.join(c for c in v if c.isdigit())
        if len(clean_id) != 10:
            raise ValueError('Customer ID must be 10 digits')
        return clean_id


class UpdateBiddingRequest(BaseModel):
    """Request to update bidding strategy."""
    connection_id: int = Field(..., description="Connection ID for authentication")
    customer_id: str = Field(..., description="Google Ads customer ID")
    bidding_strategy: BiddingStrategyType
    target_cpa_micros: Optional[int] = Field(None, gt=0, description="Target CPA in micros (for TARGET_CPA)")
    target_roas: Optional[float] = Field(None, gt=0, description="Target ROAS (for TARGET_ROAS)")
    target_spend_cpc_bid_ceiling_micros: Optional[int] = Field(None, gt=0, description="CPC ceiling (for TARGET_SPEND)")

    @field_validator('customer_id')
    @classmethod
    def validate_customer_id(cls, v):
        clean_id = ''.join(c for c in v if c.isdigit())
        if len(clean_id) != 10:
            raise ValueError('Customer ID must be 10 digits')
        return clean_id


class CreateBudgetRequest(BaseModel):
    """Request to create a campaign budget."""
    connection_id: int = Field(..., description="Connection ID for authentication")
    customer_id: str = Field(..., description="Google Ads customer ID")
    budget_name: str = Field(..., min_length=1, max_length=255)
    amount_micros: int = Field(..., gt=0)
    delivery_method: BudgetDeliveryMethod = Field(BudgetDeliveryMethod.STANDARD)
    explicitly_shared: bool = Field(False, description="Whether budget is shared across campaigns")

    @field_validator('customer_id')
    @classmethod
    def validate_customer_id(cls, v):
        clean_id = ''.join(c for c in v if c.isdigit())
        if len(clean_id) != 10:
            raise ValueError('Customer ID must be 10 digits')
        return clean_id


class CreateAdGroupRequest(BaseModel):
    """Request to create an ad group."""
    connection_id: int = Field(..., description="Connection ID for authentication")
    customer_id: str = Field(..., description="Google Ads customer ID")
    campaign_id: str = Field(..., description="Campaign ID")
    ad_group_name: str = Field(..., min_length=1, max_length=255)
    cpc_bid_micros: Optional[int] = Field(None, gt=0, description="CPC bid in micros")

    @field_validator('customer_id')
    @classmethod
    def validate_customer_id(cls, v):
        clean_id = ''.join(c for c in v if c.isdigit())
        if len(clean_id) != 10:
            raise ValueError('Customer ID must be 10 digits')
        return clean_id


class CreateAdRequest(BaseModel):
    """Request to create a responsive search ad."""
    connection_id: int = Field(..., description="Connection ID for authentication")
    customer_id: str = Field(..., description="Google Ads customer ID")
    ad_group_id: str = Field(..., description="Ad group ID")
    headlines: List[str] = Field(..., min_length=3, max_length=15, description="Ad headlines")
    descriptions: List[str] = Field(..., min_length=2, max_length=4, description="Ad descriptions")
    final_urls: List[str] = Field(..., min_length=1, description="Landing page URLs")
    path1: Optional[str] = Field(None, max_length=15, description="Display path 1")
    path2: Optional[str] = Field(None, max_length=15, description="Display path 2")

    @field_validator('customer_id')
    @classmethod
    def validate_customer_id(cls, v):
        clean_id = ''.join(c for c in v if c.isdigit())
        if len(clean_id) != 10:
            raise ValueError('Customer ID must be 10 digits')
        return clean_id

    @field_validator('headlines')
    @classmethod
    def validate_headlines(cls, v):
        for i, headline in enumerate(v):
            if not headline or not headline.strip():
                raise ValueError(f'Headline {i+1} cannot be empty')
            if len(headline) > 30:
                raise ValueError(f'Headline {i+1} exceeds 30 characters')
        return v

    @field_validator('descriptions')
    @classmethod
    def validate_descriptions(cls, v):
        for i, desc in enumerate(v):
            if not desc or not desc.strip():
                raise ValueError(f'Description {i+1} cannot be empty')
            if len(desc) > 90:
                raise ValueError(f'Description {i+1} exceeds 90 characters')
        return v


class UploadAssetRequest(BaseModel):
    """Request to upload an asset."""
    connection_id: int = Field(..., description="Connection ID for authentication")
    customer_id: str = Field(..., description="Google Ads customer ID")
    asset_name: str = Field(..., min_length=1, max_length=255)
    # Note: image_data will be handled separately as file upload

    @field_validator('customer_id')
    @classmethod
    def validate_customer_id(cls, v):
        clean_id = ''.join(c for c in v if c.isdigit())
        if len(clean_id) != 10:
            raise ValueError('Customer ID must be 10 digits')
        return clean_id


class LinkAssetRequest(BaseModel):
    """Request to link asset to campaign."""
    connection_id: int = Field(..., description="Connection ID for authentication")
    customer_id: str = Field(..., description="Google Ads customer ID")
    campaign_id: str = Field(..., description="Campaign ID")
    asset_resource_name: str = Field(..., description="Asset resource name")
    field_type: AssetFieldType = Field(AssetFieldType.MARKETING_IMAGE)

    @field_validator('customer_id')
    @classmethod
    def validate_customer_id(cls, v):
        clean_id = ''.join(c for c in v if c.isdigit())
        if len(clean_id) != 10:
            raise ValueError('Customer ID must be 10 digits')
        return clean_id


class UpdateStatusRequest(BaseModel):
    """Request to update campaign/ad status."""
    connection_id: int = Field(..., description="Connection ID for authentication")
    customer_id: str = Field(..., description="Google Ads customer ID")
    status: CampaignStatus = Field(..., description="New status")

    @field_validator('customer_id')
    @classmethod
    def validate_customer_id(cls, v):
        clean_id = ''.join(c for c in v if c.isdigit())
        if len(clean_id) != 10:
            raise ValueError('Customer ID must be 10 digits')
        return clean_id


# === Response Models ===

class MutationResponse(BaseModel):
    """Standard response for mutation operations."""
    success: bool
    resource_names: Optional[List[str]] = None
    count: Optional[int] = None
    error: Optional[str] = None
    error_type: Optional[str] = None


class CampaignCreationResponse(MutationResponse):
    """Response for campaign creation."""
    budget_resource_name: Optional[str] = None
    campaign_id: Optional[str] = None

    def model_post_init(self, __context):
        """Extract campaign ID from resource name."""
        if self.success and self.resource_names:
            self.campaign_id = self.resource_names[0].split('/')[-1]


class BudgetCreationResponse(MutationResponse):
    """Response for budget creation."""
    budget_id: Optional[str] = None

    def model_post_init(self, __context):
        """Extract budget ID from resource name."""
        if self.success and self.resource_names:
            self.budget_id = self.resource_names[0].split('/')[-1]


class AdGroupCreationResponse(MutationResponse):
    """Response for ad group creation."""
    ad_group_id: Optional[str] = None

    def model_post_init(self, __context):
        """Extract ad group ID from resource name."""
        if self.success and self.resource_names:
            self.ad_group_id = self.resource_names[0].split('/')[-1]


class AdCreationResponse(MutationResponse):
    """Response for ad creation."""
    ad_id: Optional[str] = None

    def model_post_init(self, __context):
        """Extract ad ID from resource name."""
        if self.success and self.resource_names:
            # Ad resource name format: customers/123/adGroupAds/456~789
            self.ad_id = self.resource_names[0].split('/')[-1]


class AssetUploadResponse(MutationResponse):
    """Response for asset upload."""
    asset_id: Optional[str] = None
    asset_resource_name: Optional[str] = None

    def model_post_init(self, __context):
        """Extract asset ID and set resource name."""
        if self.success and self.resource_names:
            self.asset_resource_name = self.resource_names[0]
            self.asset_id = self.resource_names[0].split('/')[-1]
