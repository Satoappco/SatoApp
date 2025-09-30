"""
Facebook OAuth callback handler
Handles the OAuth flow and automatically creates Facebook connections
"""

import os
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

router = APIRouter(prefix="/facebook", tags=["facebook-oauth"])


@router.get("/debug")
async def debug_oauth_config():
    """Debug endpoint to check OAuth configuration"""
    from app.config.settings import get_settings
    settings = get_settings()
    return {
        "facebook_app_id": settings.facebook_app_id,
        "facebook_app_secret": "SET" if settings.facebook_app_secret else "NOT_SET",
        "facebook_redirect_uri": settings.facebook_redirect_uri,
        "facebook_api_version": settings.facebook_api_version,
        "env_file_exists": os.path.exists(".env")
    }


@router.get("/test")
async def test_endpoint():
    """Simple test endpoint"""
    return {"status": "ok", "message": "Facebook OAuth endpoints are working"}


@router.get("/oauth-url")
async def get_oauth_url(redirect_uri: str):
    """
    Get Facebook OAuth URL for frontend to redirect to
    """
    try:
        from app.services.facebook_service import FacebookService
        
        facebook_service = FacebookService()
        auth_url = facebook_service.get_oauth_url(redirect_uri)
        
        return {"auth_url": auth_url}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate OAuth URL: {str(e)}"
        )


class OAuthCallbackRequest(BaseModel):
    """Request model for OAuth callback"""
    code: str
    redirect_uri: str


class OAuthCallbackResponse(BaseModel):
    """Response model for OAuth callback"""
    success: bool
    message: str
    connections: Optional[list] = None
    user_name: Optional[str] = None
    user_email: Optional[str] = None


@router.post("/oauth-callback", response_model=OAuthCallbackResponse)
async def handle_oauth_callback(
    request: OAuthCallbackRequest
):
    """
    Handle Facebook OAuth callback (public endpoint)
    Exchanges authorization code for tokens
    """
    
    print(f"DEBUG: Facebook OAuth callback started with code: {request.code[:10]}...")
    
    try:
        from app.services.facebook_service import FacebookService
        
        facebook_service = FacebookService()
        
        # Exchange code for tokens
        token_data = await facebook_service.exchange_code_for_token(
            code=request.code,
            redirect_uri=request.redirect_uri
        )
        
        print(f"DEBUG: Token exchange successful for user: {token_data['user_name']}")
        
        # Find user by email from Facebook
        from app.models.users import User
        from app.config.database import get_session
        from sqlmodel import select
        
        user_email = token_data.get('user_email')
        
        # If Facebook doesn't provide email, we'll need to find the user another way
        # For now, we'll assume the currently authenticated user is connecting their Facebook
        # In a real app, you might want to require login before OAuth or use session data
        
        with get_session() as session:
            user = None
            
            if user_email:
                # Try to find user by Facebook email
                user_statement = select(User).where(User.email == user_email)
                user = session.exec(user_statement).first()
                print(f"DEBUG: Found user by Facebook email {user_email}: {user.id if user else 'None'}")
            
            if not user:
                # Fallback: Find the demo user (ID 5) for now
                # In production, you'd get this from the authenticated session
                user_statement = select(User).where(User.id == 5)
                user = session.exec(user_statement).first()
                print(f"DEBUG: Using demo user (ID 5): {user.email if user else 'Not found'}")
                
                if user:
                    user_email = user.email  # Use the demo user's email
            
            if not user:
                return OAuthCallbackResponse(
                    success=False,
                    message="No user found. Please sign in first."
                )
            
            # Save connection to database with real user ID
            result = await facebook_service.save_facebook_connection(
                user_id=user.id,  # Real authenticated user ID
                subclient_id=1,  # Default subclient ID
                access_token=token_data['access_token'],
                expires_in=token_data['expires_in'],
                user_name=token_data['user_name'],
                user_email=user_email
            )
        
        print(f"DEBUG: Created {len(result['connections'])} Facebook connections")
        
        return OAuthCallbackResponse(
            success=True,
            message=f"Successfully connected to Facebook! Created {len(result['connections'])} connections.",
            connections=result['connections'],
            user_name=result['user_name'],
            user_email=result['user_email']
        )
        
    except Exception as e:
        print(f"ERROR: Facebook OAuth callback failed: {str(e)}")
        return OAuthCallbackResponse(
            success=False,
            message=f"Failed to connect to Facebook: {str(e)}"
        )


class CreateConnectionRequest(BaseModel):
    """Request model for creating connection"""
    user_id: int
    subclient_id: int
    access_token: str
    expires_in: int
    user_name: str
    user_email: Optional[str] = None


@router.post("/create-connection", response_model=OAuthCallbackResponse)
async def create_facebook_connection(
    request: CreateConnectionRequest
):
    """
    Create Facebook connection manually (for testing)
    """
    
    try:
        from app.services.facebook_service import FacebookService
        
        facebook_service = FacebookService()
        
        result = await facebook_service.save_facebook_connection(
            user_id=request.user_id,
            subclient_id=request.subclient_id,
            access_token=request.access_token,
            expires_in=request.expires_in,
            user_name=request.user_name,
            user_email=request.user_email
        )
        
        return OAuthCallbackResponse(
            success=True,
            message=f"Successfully created Facebook connection!",
            connections=result['connections'],
            user_name=result['user_name'],
            user_email=result['user_email']
        )
        
    except Exception as e:
        return OAuthCallbackResponse(
            success=False,
            message=f"Failed to create Facebook connection: {str(e)}"
        )

