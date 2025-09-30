"""
Security utilities for authentication and authorization
"""

from typing import Optional
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.config import get_settings

settings = get_settings()
security = HTTPBearer()


def verify_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)) -> bool:
    """Verify API key from Authorization header"""
    
    if not settings.api_key:
        # If no API key is configured, allow all requests
        return True
    
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header required"
        )
    
    if credentials.credentials != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key"
        )
    
    return True


def get_current_user_id(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Optional[int]:
    """Extract user ID from token (placeholder for future implementation)"""
    # For now, return a default user ID
    # In the future, this would decode a JWT token
    return 7001  # Default user ID from the implementation plan


def get_secret_key() -> str:
    """Get secret key for encryption"""
    return settings.secret_key or "default-secret-key-for-encryption"
