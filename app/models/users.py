"""
User-related database models - CORRECTED VERSION
Matches real business requirements for agency multi-tenant system
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional
from sqlmodel import SQLModel, Field, Column, JSON
from .base import BaseModel


class UserRole(str, Enum):
    """User roles in the agency system"""
    OWNER = "owner"
    ADMIN = "admin"
    MANAGER = "manager"
    ANALYST = "analyst"
    VIEWER = "viewer"


class UserStatus(str, Enum):
    """User account status"""
    ACTIVE = "active"
    INVITED = "invited"
    SUSPENDED = "suspended"
    DELETED = "deleted"


class CustomerType(str, Enum):
    """Type of customer/client"""
    AGENCY = "agency"
    BRAND = "brand"
    MERCHANT = "merchant"
    FREELANCER = "freelancer"
    IN_HOUSE = "in-house"


class CustomerStatus(str, Enum):
    """Customer subscription status"""
    ACTIVE = "active"
    TRIAL = "trial"
    PAUSED = "paused"
    CHURNED = "churned"


class SubCustomerType(str, Enum):
    """Type of sub-customer property"""
    ECOMMERCE = "ecommerce"
    LEADS = "leads"
    BLOG = "blog"
    CATALOG = "catalog"
    LANDING_PAGE = "landing_page"


class User(BaseModel, table=True):
    """Agency users - משתמשים של הclient (e.g., Everest employees)"""
    __tablename__ = "users"
    
    # Core identity
    email: str = Field(max_length=255, unique=True, index=True)
    full_name: str = Field(max_length=255)
    phone: Optional[str] = Field(default=None, max_length=20)
    
    # Permissions & Status
    role: UserRole = Field(default=UserRole.VIEWER)
    status: UserStatus = Field(default=UserStatus.INVITED)
    
    # Client relationships
    primary_customer_id: int = Field(foreign_key="customers.id")
    additional_customer_ids: List[int] = Field(default_factory=list, sa_column=Column(JSON))
    
    # Localization
    locale: str = Field(default="he-IL", max_length=10)
    timezone: str = Field(default="Asia/Jerusalem", max_length=50)
    
    # OAuth fields for Google authentication
    google_id: Optional[str] = Field(default=None, unique=True, max_length=255)
    avatar_url: Optional[str] = Field(default=None, max_length=500)
    email_verified: bool = Field(default=False)
    provider: str = Field(default="google", max_length=20)
    
    # Activity tracking
    last_login_at: Optional[datetime] = Field(default=None)


class Customer(BaseModel, table=True):
    """Clients - לקוחות (Agency clients like Adi Media Ltd)"""
    __tablename__ = "customers"
    
    # Core info
    name: str = Field(max_length=255)
    type: CustomerType = Field(default=CustomerType.BRAND)
    status: CustomerStatus = Field(default=CustomerStatus.TRIAL)
    
    # Business info
    plan: str = Field(max_length=100)  # Pro, Enterprise, etc.
    billing_currency: str = Field(default="ILS", max_length=3)
    vat_id: Optional[str] = Field(default=None, max_length=50)
    address: Optional[str] = Field(default=None, max_length=500)
    
    # Relationships
    primary_contact_user_id: Optional[int] = Field(default=None, foreign_key="users.id")
    
    # Metadata
    domains: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    tags: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    notes: Optional[str] = Field(default=None)


class SubCustomer(BaseModel, table=True):
    """Sub-clients - תת-לקוחות (Brand's stores/projects like 'Brand X – Store #12')"""
    __tablename__ = "sub_customers"
    
    # Relationships
    customer_id: int = Field(foreign_key="customers.id")
    
    # Core info
    name: str = Field(max_length=255)  # "Brand X – Store #12"
    subtype: SubCustomerType = Field()
    status: CustomerStatus = Field(default=CustomerStatus.ACTIVE)
    
    # Integration with external platforms
    external_ids: dict = Field(default_factory=dict, sa_column=Column(JSON))
    # Example: {"ga4":"properties/123","fb_page":"12345","google_ads":"123-456-7890"}
    
    # Business info
    timezone: Optional[str] = Field(default=None, max_length=50)
    markets: List[str] = Field(default_factory=list, sa_column=Column(JSON))  # ["IL","EU"]
    budget_monthly: Optional[float] = Field(default=None)
    tags: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    notes: Optional[str] = Field(default=None)


class UserSession(BaseModel, table=True):
    """User authentication sessions for JWT token management"""
    __tablename__ = "user_sessions"
    
    # Relationships
    user_id: int = Field(foreign_key="users.id")
    
    # Session identification
    session_token: str = Field(unique=True, max_length=255)
    
    # JWT tokens
    access_token: str = Field()  # Short-lived JWT (15 minutes)
    refresh_token: str = Field()  # Long-lived token (7 days)
    
    # Session metadata
    expires_at: datetime = Field()
    ip_address: Optional[str] = Field(default=None, max_length=45)  # IPv4/IPv6
    user_agent: Optional[str] = Field(default=None, max_length=500)
    
    # Session status
    is_active: bool = Field(default=True)
    revoked_at: Optional[datetime] = Field(default=None)
