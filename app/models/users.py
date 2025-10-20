"""
User-related database models - CORRECTED VERSION
Matches real business requirements for agency multi-tenant system
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional
from sqlmodel import SQLModel, Field, Column, JSON, String
from .base import BaseModel


class UserRole(str, Enum):
    """User roles in the agency system"""
    OWNER = "OWNER"
    ADMIN = "ADMIN"
    CAMPAIGNER = "CAMPAIGNER"  # Regular team member (default)
    VIEWER = "VIEWER"


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


class Campaigner(BaseModel, table=True):
    """Agency campaigners - משתמשים של הagency (e.g., Everest employees)"""
    __tablename__ = "campaigners"
    
    # Core identity - matches client requirements
    email: str = Field(max_length=255, unique=True, index=True)
    full_name: str = Field(max_length=255)
    phone: Optional[str] = Field(default=None, max_length=20)
    google_id: Optional[str] = Field(default=None, max_length=255, unique=True, index=True)
    email_verified: bool = Field(default=False)
    avatar_url: Optional[str] = Field(default=None, max_length=500)
    
    # User preferences
    locale: str = Field(default="he-IL", max_length=10)
    timezone: str = Field(default="Asia/Jerusalem", max_length=50)
    last_login_at: Optional[datetime] = Field(default=None)
    
    # Permissions & Status
    role: UserRole = Field(default=UserRole.VIEWER)
    status: UserStatus = Field(default=UserStatus.INVITED)
    
    # Agency relationship
    agency_id: int = Field(foreign_key="agencies.id")  # References agencies table


class Agency(BaseModel, table=True):
    """Marketing agencies - סוכנויות פרסום (e.g., Everest Agency Ltd)"""
    __tablename__ = "agencies"
    
    # Core info - matches client requirements
    name: str = Field(max_length=255)
    email: Optional[str] = Field(default=None, max_length=255)
    phone: Optional[str] = Field(default=None, max_length=50)
    status: CustomerStatus = Field(default=CustomerStatus.ACTIVE)


class Customer(BaseModel, table=True):
    """Agency clients/projects - לקוחות של הסוכנות (e.g., Brand X Store #12)"""
    __tablename__ = "customers"
    
    # Relationships
    agency_id: int = Field(foreign_key="agencies.id")  # Points to parent agency
    assigned_campaigner_id: Optional[int] = Field(default=None, foreign_key="campaigners.id", description="Campaigner assigned to this customer")
    
    # Core info - matches Info Table requirements from image
    full_name: str = Field(max_length=255, description="Full name or business name")
    status: CustomerStatus = Field(default=CustomerStatus.ACTIVE)
    
    # Client information - all fields from Info Table image
    contact_email: Optional[str] = Field(default=None, max_length=255, description="Primary business contact email address")
    phone: Optional[str] = Field(default=None, max_length=50, description="Phone number")
    address: Optional[str] = Field(default=None, max_length=500, description="Physical address")
    opening_hours: Optional[str] = Field(default=None, sa_column=Column(String), description="Business opening hours")
    narrative_report: Optional[str] = Field(default=None, sa_column=Column(String), description="Narrative report text")
    website_url: Optional[str] = Field(default=None, max_length=500, description="Website URL")
    facebook_page_url: Optional[str] = Field(default=None, max_length=500, description="Facebook page URL")
    instagram_page_url: Optional[str] = Field(default=None, max_length=500, description="Instagram page URL")
    llm_engine_preference: Optional[str] = Field(default=None, max_length=50, description="Preferred LLM engine: gemini, openai, claude")
    
    # Active status
    is_active: bool = Field(default=True, description="Whether this customer record is active")


class CampaignerSession(BaseModel, table=True):
    """Campaigner authentication sessions for JWT token management"""
    __tablename__ = "campaigner_sessions"
    
    # Relationships
    campaigner_id: int = Field(foreign_key="campaigners.id")  # Points to campaigners table
    
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


class InviteToken(BaseModel, table=True):
    """Secure invitation tokens for team member invites"""
    __tablename__ = "invite_tokens"
    
    token: str = Field(unique=True, max_length=255, index=True)  # UUID
    agency_id: int = Field(foreign_key="agencies.id")
    invited_by_campaigner_id: int = Field(foreign_key="campaigners.id")
    
    # Invite details
    invited_email: Optional[str] = Field(default=None, max_length=255)
    role: UserRole = Field(default=UserRole.CAMPAIGNER)
    
    # Status tracking
    is_used: bool = Field(default=False)
    used_at: Optional[datetime] = Field(default=None)
    used_by_campaigner_id: Optional[int] = Field(default=None, foreign_key="campaigners.id")
    
    # Security
    expires_at: datetime = Field()  # 7 days expiry
    max_uses: int = Field(default=1)  # Single-use tokens
    use_count: int = Field(default=0)
