"""
API Token Authentication System for External Services

This module provides API token authentication for external services like DialogCX,
Postman, and other webhook/testing endpoints that don't use JWT tokens.
"""

import os
from typing import Optional, Dict, List
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.config import get_settings

settings = get_settings()
security = HTTPBearer()


class APITokenService:
    """Service for managing API token authentication"""
    
    def __init__(self):
        # Load single universal API token from environment variables
        # Check both API_TOKEN (new) and API_KEY (legacy deployment script)
        self.api_token = os.getenv("API_TOKEN") or os.getenv("API_KEY")
        
        # Fallback to old token names for backward compatibility
        if not self.api_token:
            # Try old token names as fallback
            self.api_token = (
                os.getenv("WEBHOOK_API_TOKEN") or 
                os.getenv("CREWAI_API_TOKEN") or 
                os.getenv("POSTMAN_API_TOKEN") or 
                os.getenv("ADMIN_API_TOKEN")
            )
    
    def validate_token(self, token: str) -> Optional[Dict[str, str]]:
        """
        Validate an API token and return token info if valid
        
        Returns:
            Dict with token info if valid, None if invalid
        """
        if not self.api_token:
            return None
            
        if token == self.api_token:
            return {
                "service": "universal",
                "token": token,
                "valid": True
            }
        return None
    
    def get_token_permissions(self, service: str) -> List[str]:
        """Get permissions for a universal token"""
        # Universal token has all permissions
        return [
            "webhooks:write", "dialogcx:access", "crewai:test", 
            "analysis:run", "api:test", "endpoints:access"
        ]


# Global instance
api_token_service = APITokenService()


def verify_api_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, str]:
    """
    Verify API token from Authorization header
    
    Returns:
        Dict with token information if valid
        
    Raises:
        HTTPException: If token is invalid or missing
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token_info = api_token_service.validate_token(credentials.credentials)
    
    if not token_info:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return token_info


# Simplified verification functions - universal token has all permissions

def verify_webhook_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> bool:
    """Verify API token for webhook endpoints - uses universal token"""
    verify_api_token(credentials)  # Universal token has all permissions
    return True


def verify_crewai_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> bool:
    """Verify API token for CrewAI test endpoints - uses universal token"""
    verify_api_token(credentials)  # Universal token has all permissions
    return True


def verify_admin_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> bool:
    """Verify API token for admin endpoints - uses universal token"""
    verify_api_token(credentials)  # Universal token has all permissions
    return True


def get_api_token_info() -> Dict[str, str]:
    """
    Get information about configured API tokens (for debugging/health checks)
    
    Returns:
        Dict with token configuration info (without actual token values)
    """
    return {
        "token_configured": bool(api_token_service.api_token),
        "token_type": "universal",
        "permissions": api_token_service.get_token_permissions("universal"),
        "fallback_used": not os.getenv("API_TOKEN") and bool(api_token_service.api_token)
    }


# Backward compatibility with existing JWT system
def verify_jwt_or_api_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> bool:
    """
    Try API token first, fall back to JWT token
    This allows gradual migration from JWT to API tokens
    
    Returns:
        True if either token type is valid
    """
    try:
        # Try API token first
        verify_api_token(credentials)
        return True
    except HTTPException:
        # Fall back to JWT token
        try:
            from app.core.auth import verify_token
            verify_token(credentials.credentials, "access")
            return True
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API token or JWT token",
                headers={"WWW-Authenticate": "Bearer"},
            )
