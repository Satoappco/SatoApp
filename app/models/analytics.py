"""
Analytics and performance tracking models - CORRECTED VERSION
Matches real business requirements for digital asset management
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional
from sqlmodel import SQLModel, Field, Column, JSON
from .base import BaseModel


class AssetType(str, Enum):
    """Types of digital assets"""
    SOCIAL_MEDIA = "social_media"  # Facebook Page, Instagram, etc.
    ANALYTICS = "analytics"  # Google Analytics (GA4) - legacy value
    GA4 = "GA4"  # Google Analytics 4 - actual database value
    ADVERTISING = "advertising"  # Generic advertising
    GOOGLE_ADS = "google_ads"  # Google Ads (separate from Analytics)
    GOOGLE_ADS_CAPS = "GOOGLE_ADS"  # Google Ads - actual database value
    FACEBOOK_ADS = "facebook_ads"  # Facebook Ads & Insights (separate from Facebook Page)
    FACEBOOK_ADS_CAPS = "FACEBOOK_ADS"  # Facebook Ads - actual database value
    SEARCH_CONSOLE = "search_console"
    EMAIL_MARKETING = "email_marketing"
    CRM = "crm"
    ECOMMERCE = "ecommerce"


class AuthType(str, Enum):
    """Types of authentication methods"""
    OAUTH2 = "oauth2"
    API_KEY = "api_key"
    BASIC_AUTH = "basic_auth"
    TOKEN = "token"


class DigitalAsset(BaseModel, table=True):
    """Digital assets for sub-clients - נכסים דיגיטליים"""
    __tablename__ = "digital_assets"
    
    # Relationships
    customer_id: int = Field(foreign_key="customers.id")
    
    # Asset identification
    asset_type: AssetType = Field()
    provider: str = Field(max_length=100)  # "Google", "Facebook", "TikTok", "LinkedIn"
    name: str = Field(max_length=255)  # Human-readable name
    handle: Optional[str] = Field(default=None, max_length=100)  # @username, page name
    url: Optional[str] = Field(default=None, max_length=500)  # Asset URL
    external_id: str = Field(max_length=255)  # Platform's unique ID
    
    # Metadata (provider-specific information)
    meta: dict = Field(default_factory=dict, sa_column=Column(JSON))
    # Examples:
    # {"business_id": "123", "pixel_id": "456"} for Facebook
    # {"property_id": "GA_PROPERTY_123", "stream_id": "456"} for GA4
    # {"account_id": "123-456-7890"} for Google Ads
    
    is_active: bool = Field(default=True)


class Connection(BaseModel, table=True):
    """OAuth connections and API credentials for digital assets"""
    __tablename__ = "connections"
    
    # Relationships
    digital_asset_id: int = Field(foreign_key="digital_assets.id")
    customer_id: int = Field(foreign_key="customers.id")  # Direct customer relationship for better queries
    campaigner_id: int = Field(foreign_key="campaigners.id")  # Who created the connection
    
    # Authentication details
    auth_type: AuthType = Field(default=AuthType.OAUTH2)
    account_email: Optional[str] = Field(default=None, max_length=255)  # OAuth account email
    scopes: List[str] = Field(default_factory=list, sa_column=Column(JSON))  # OAuth scopes
    
    # Encrypted tokens
    access_token_enc: Optional[bytes] = Field(default=None)  # Encrypted access token
    refresh_token_enc: Optional[bytes] = Field(default=None)  # Encrypted refresh token
    token_hash: Optional[str] = Field(default=None, max_length=64)  # Hash for validation
    
    # Token management
    expires_at: Optional[datetime] = Field(default=None)
    revoked: bool = Field(default=False)
    rotated_at: Optional[datetime] = Field(default=None)
    last_used_at: Optional[datetime] = Field(default=None)


class KpiCatalog(BaseModel, table=True):
    """Standardized KPI definitions for different sub-customer types"""
    __tablename__ = "kpi_catalog"
    
    id: int = Field(primary_key=True)
    subtype: str = Field(max_length=50, description="Sub-customer type (ecommerce, leadgen, etc.)")
    primary_metric: str = Field(max_length=100, description="Primary KPI metric name")
    primary_submetrics: str = Field(description="JSON array of primary sub-metrics")
    secondary_metric: str = Field(max_length=100, description="Secondary KPI metric name")
    secondary_submetrics: str = Field(description="JSON array of secondary sub-metrics")
    lite_primary_metric: str = Field(max_length=100, description="Lite version primary metric")
    lite_primary_submetrics: str = Field(description="JSON array of lite primary sub-metrics")
    lite_secondary_metric: str = Field(max_length=100, description="Lite version secondary metric")
    lite_secondary_submetrics: str = Field(description="JSON array of lite secondary sub-metrics")


class UserPropertySelection(BaseModel, table=True):
    """User's selected properties/pages for each service"""
    __tablename__ = "user_property_selections"
    
    # Relationships
    campaigner_id: int = Field(foreign_key="campaigners.id")
    customer_id: int = Field(foreign_key="customers.id")
    
    # Service and selected property
    service: str = Field(max_length=50)  # "google_analytics", "google_ads", "facebook_page", "facebook_ads"
    selected_property_id: str = Field(max_length=255)  # The external_id of the selected property/page/ad account
    property_name: str = Field(max_length=255)  # Human-readable name for display
    
    # Additional metadata
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class KpiGoal(BaseModel, table=True):
    """KPI Goals - Target KPIs for each campaign/ad"""
    __tablename__ = "kpi_goals"
    
    # Relationships
    customer_id: int = Field(foreign_key="customers.id")
    
    # Campaign identification
    campaign_id: str = Field(max_length=50)
    campaign_name: str = Field(max_length=255)
    campaign_status: str = Field(max_length=50, default="ACTIVE")  # ACTIVE/PAUSED/INACTIVE
    
    # Ad Group information
    ad_group_id: Optional[int] = Field(default=None)
    ad_group_name: Optional[str] = Field(default=None, max_length=255)
    ad_group_status: Optional[str] = Field(default=None, max_length=50)  # ACTIVE/PAUSED/INACTIVE
    
    # Ad information
    ad_id: Optional[int] = Field(default=None)
    ad_name: Optional[str] = Field(default=None, max_length=255)
    ad_headline: Optional[str] = Field(default=None, max_length=500)
    ad_status: Optional[str] = Field(default=None, max_length=50)  # ACTIVE/PAUSED/INACTIVE
    ad_score: Optional[int] = Field(default=None)  # Numerical score like 99
    
    # Advertising channel and objective
    advertising_channel: str = Field(max_length=100)  # Google AdSense, Google Search Ads, etc.
    campaign_objective: str = Field(max_length=100)  # Sales, Traffic, Awareness, Lead generation
    
    # Budget information
    daily_budget: Optional[float] = Field(default=None)
    
    # Target audience
    target_audience: str = Field(max_length=255)
    
    # KPI Goals (Target values)
    primary_kpi_1: Optional[str] = Field(default=None, max_length=255)  # e.g., "CPA <$15"
    secondary_kpi_1: Optional[str] = Field(default=None, max_length=255)  # e.g., "Clicks > 10"
    secondary_kpi_2: Optional[str] = Field(default=None, max_length=255)  # e.g., "CTR > 6%"
    secondary_kpi_3: Optional[str] = Field(default=None, max_length=255)  # e.g., "Impressions > 160"
    
    # Campaign details
    landing_page: Optional[str] = Field(default=None, max_length=500)
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class KpiValue(BaseModel, table=True):
    """KPI Values - Actual measured KPI values for each campaign/ad"""
    __tablename__ = "kpi_values"
    
    # Relationships
    customer_id: int = Field(foreign_key="customers.id")
    
    # Campaign identification
    campaign_id: str = Field(max_length=50)
    campaign_name: str = Field(max_length=255)
    campaign_status: str = Field(max_length=50, default="ACTIVE")  # ACTIVE/PAUSED/INACTIVE
    
    # Ad Group information
    ad_group_id: Optional[int] = Field(default=None)
    ad_group_name: Optional[str] = Field(default=None, max_length=255)
    ad_group_status: Optional[str] = Field(default=None, max_length=50)  # ACTIVE/PAUSED/INACTIVE
    
    # Ad information
    ad_id: Optional[int] = Field(default=None)
    ad_name: Optional[str] = Field(default=None, max_length=255)
    ad_headline: Optional[str] = Field(default=None, max_length=500)
    ad_status: Optional[str] = Field(default=None, max_length=50)  # ACTIVE/PAUSED/INACTIVE
    ad_score: Optional[int] = Field(default=None)  # Numerical score like 99
    
    # Advertising channel and objective
    advertising_channel: str = Field(max_length=100)  # Google AdSense, Google Search Ads, etc.
    campaign_objective: str = Field(max_length=100)  # Sales, Traffic, Awareness, Lead generation
    
    # Budget information
    daily_budget: Optional[float] = Field(default=None)
    
    # Target audience
    target_audience: str = Field(max_length=255)
    
    # KPI Values (Actual measured values)
    primary_kpi_1: Optional[str] = Field(default=None, max_length=255)  # e.g., "CPA $12.50"
    secondary_kpi_1: Optional[str] = Field(default=None, max_length=255)  # e.g., "Clicks 15"
    secondary_kpi_2: Optional[str] = Field(default=None, max_length=255)  # e.g., "CTR 7.2%"
    secondary_kpi_3: Optional[str] = Field(default=None, max_length=255)  # e.g., "Impressions 180"
    
    # Campaign details
    landing_page: Optional[str] = Field(default=None, max_length=500)
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
