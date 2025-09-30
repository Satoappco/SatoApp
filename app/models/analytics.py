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
    SOCIAL_MEDIA = "social_media"
    ANALYTICS = "analytics" 
    ADVERTISING = "advertising"
    GOOGLE_ADS = "google_ads"
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
    subclient_id: int = Field(foreign_key="sub_customers.id")
    
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
    user_id: int = Field(foreign_key="users.id")  # Who created the connection
    
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


class PerformanceMetric(BaseModel, table=True):
    """Performance metrics for monitoring"""
    __tablename__ = "performance_metrics"
    
    metric_name: str = Field(max_length=100)
    metric_value: float = Field()
    metric_unit: str = Field(max_length=50)
    agent_type: Optional[str] = Field(default=None, max_length=50)
    session_id: Optional[str] = Field(default=None, max_length=255)
    user_id: Optional[int] = Field(default=None)
    metric_metadata: Optional[str] = Field(default=None)  # JSON additional data


class AnalyticsCache(BaseModel, table=True):
    """Cache for analytics data"""
    __tablename__ = "analytics_cache"
    
    cache_key: str = Field(max_length=255, unique=True)
    cache_data: str = Field()  # JSON cached data
    expires_at: datetime = Field()
    user_id: Optional[int] = Field(default=None)
    asset_id: Optional[int] = Field(default=None)


class KpiCatalog(BaseModel, table=True):
    """KPI catalog for standardized metrics"""
    __tablename__ = "kpi_catalog"
    
    kpi_name: str = Field(max_length=100)
    kpi_description: str = Field()
    calculation_method: str = Field()
    data_sources: str = Field()  # JSON array of data sources
    category: str = Field(max_length=100)
    is_active: bool = Field(default=True)


class CampaignKPI(BaseModel, table=True):
    """Campaign KPI data for tracking performance metrics"""
    __tablename__ = "campaign_kpis"
    
    # Relationships
    subcustomer_id: int = Field(foreign_key="sub_customers.id")
    
    # Campaign identification
    date: datetime = Field()
    campaign_num: int = Field()
    campaign_id: str = Field(max_length=50)
    advertising_channel: str = Field(max_length=100)
    campaign_name: str = Field(max_length=255)
    campaign_objective: str = Field(max_length=100)
    
    # Budget information
    daily_budget: Optional[float] = Field(default=None)
    weekly_budget: Optional[float] = Field(default=None)
    
    # Target audience
    target_audience: str = Field(max_length=255)
    
    # KPI metrics
    primary_kpi_1: Optional[str] = Field(default=None, max_length=255)
    secondary_kpi_1: Optional[str] = Field(default=None, max_length=255)
    secondary_kpi_2: Optional[str] = Field(default=None, max_length=255)
    secondary_kpi_3: Optional[str] = Field(default=None, max_length=255)
    
    # Campaign details
    landing_page: Optional[str] = Field(default=None, max_length=500)
    summary_text: Optional[str] = Field(default=None)
    
    # Note: secondary_kpi_* fields will store actual performance data from cron job
    
    # Additional metadata
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
