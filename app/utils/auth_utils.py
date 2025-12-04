"""
Authentication utilities
Helper functions for authentication routes to reduce duplication and improve maintainability
"""

from datetime import datetime, timedelta
from typing import Dict, Any, Optional, TYPE_CHECKING
from app.core.auth import create_access_token, create_refresh_token, ACCESS_TOKEN_EXPIRE_MINUTES
from app.models.users import Campaigner

if TYPE_CHECKING:
    from app.api.v1.routes.auth import CampaignerResponse


def build_token_data(user: Campaigner) -> Dict[str, Any]:
    """Build token data dictionary from Campaigner"""
    return {
        "campaigner_id": user.id,
        "email": user.email,
        "role": user.role,
        "agency_id": user.agency_id
    }


def compute_expires_at(expires_in_seconds: Optional[int] = None) -> str:
    """
    Compute expires_at ISO string from expires_in seconds
    Defaults to ACCESS_TOKEN_EXPIRE_MINUTES if expires_in not provided
    """
    if expires_in_seconds is None:
        expires_in_seconds = ACCESS_TOKEN_EXPIRE_MINUTES * 60
    return (datetime.now(timezone.utc) + timedelta(seconds=expires_in_seconds)).isoformat() + 'Z'


def create_token_pair(user: Campaigner, expires_in_seconds: Optional[int] = None) -> Dict[str, Any]:
    """
    Create access and refresh token pair with expires_at metadata
    Returns dict with access_token, refresh_token, expires_in, and expires_at
    """
    token_data = build_token_data(user)
    
    access_token = create_access_token(data=token_data)
    refresh_token = create_refresh_token(data=token_data)
    
    if expires_in_seconds is None:
        expires_in_seconds = ACCESS_TOKEN_EXPIRE_MINUTES * 60
    
    expires_at = compute_expires_at(expires_in_seconds)
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_in": expires_in_seconds,
        "expires_at": expires_at
    }


def create_campaigner_response(user: Campaigner) -> 'CampaignerResponse':
    """Convert Campaigner model to CampaignerResponse"""
    # Import here to avoid circular dependency
    from app.api.v1.routes.auth import CampaignerResponse
    return CampaignerResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        status=user.status,
        agency_id=user.agency_id,
        phone=user.phone,
        google_id=user.google_id,
        email_verified=user.email_verified,
        avatar_url=user.avatar_url,
        locale=user.locale,
        timezone=user.timezone,
        last_login_at=user.last_login_at
    )

