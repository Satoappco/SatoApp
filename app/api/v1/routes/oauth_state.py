"""
OAuth state signing endpoint
Handles JWT signing of OAuth state parameters for secure user context preservation
"""

import jwt
from datetime import datetime, timedelta, timezone
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel
from app.api.dependencies import get_current_campaigner

router = APIRouter(prefix="/oauth", tags=["oauth-state"])


class SignStateRequest(BaseModel):
    """Request model for signing OAuth state"""
    campaigner_id: int
    customer_id: int
    service_type: str  # Required field, no default
    timestamp: int
    nonce: str


class SignStateResponse(BaseModel):
    """Response model for signed OAuth state"""
    signed_state: str


@router.post("/sign-state", response_model=SignStateResponse)
async def sign_oauth_state(
    request: SignStateRequest,
    current_campaigner = Depends(get_current_campaigner)
):
    """
    Sign OAuth state parameter with JWT to preserve user context securely
    """
    try:
        # Verify the campaigner_id matches the authenticated user
        if request.campaigner_id != current_campaigner.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Campaigner ID does not match authenticated user"
            )
        
        # Verify customer belongs to campaigner's agency
        from app.config.database import get_session
        from app.models.users import Customer
        from sqlmodel import select
        
        with get_session() as session:
            customer = session.exec(
                select(Customer).where(Customer.id == request.customer_id)
            ).first()
            
            if not customer:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Customer with ID {request.campaigner_id} not found"
                )
            
            if customer.agency_id != current_campaigner.agency_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Customer does not belong to campaigner's agency"
                )
        
        # Get JWT secret from settings
        from app.config.settings import get_settings
        settings = get_settings()
        
        # Create JWT payload
        # Use timezone-aware datetime to avoid timestamp conversion issues
        current_time = datetime.now(timezone.utc)
        expiration_time = current_time + timedelta(minutes=10)

        payload = {
            "campaigner_id": request.campaigner_id,
            "customer_id": request.customer_id,
            "service_type": request.service_type,
            "timestamp": request.timestamp,
            "nonce": request.nonce,
            "exp": int(expiration_time.timestamp())  # 10 minute expiration
        }
        
        # Sign the JWT
        signed_state = jwt.encode(
            payload,
            settings.oauth_state_secret,
            algorithm="HS256"
        )
        
        return SignStateResponse(signed_state=signed_state)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sign OAuth state: {str(e)}"
        )


@router.post("/verify-state")
async def verify_oauth_state(state: str) -> Dict[str, Any]:
    """
    Verify and decode OAuth state parameter
    """
    try:
        from app.config.settings import get_settings
        settings = get_settings()
        
        # Decode and verify the JWT
        payload = jwt.decode(
            state,
            settings.oauth_state_secret,
            algorithms=["HS256"]
        )
        
        # Check expiration (using timezone-aware datetime)
        current_timestamp = datetime.now(timezone.utc).timestamp()
        if current_timestamp > payload.get('exp', 0):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="OAuth state has expired"
            )
        
        return {
            "valid": True,
            "campaigner_id": payload.get('campaigner_id'),
            "customer_id": payload.get('customer_id'),
            "service_type": payload.get('service_type'),  # No default, return what's in JWT
            "timestamp": payload.get('timestamp'),
            "nonce": payload.get('nonce')
        }
        
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid OAuth state: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to verify OAuth state: {str(e)}"
        )
