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
    from app.config.settings import get_settings, clear_settings_cache
    clear_settings_cache()  # Clear cache to get fresh settings
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
async def get_oauth_url(redirect_uri: str, state: str = None):
    """
    Get Facebook OAuth URL for frontend to redirect to
    """
    try:
        from app.services.facebook_service import FacebookService
        
        facebook_service = FacebookService()
        auth_url = facebook_service.get_oauth_url(redirect_uri, state=state)
        
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
    state: Optional[str] = None


class OAuthCallbackResponse(BaseModel):
    """Response model for OAuth callback"""
    success: bool
    message: str
    connections: Optional[list] = None
    pages: Optional[list] = None
    ad_accounts: Optional[list] = None
    access_token: Optional[str] = None
    expires_in: Optional[int] = None
    user_name: Optional[str] = None
    user_email: Optional[str] = None
    state: Optional[str] = None
    user_id: Optional[int] = None


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

                    message="No user found. Please sign in first."
                )
            
            # Get available Facebook pages instead of auto-creating connections
            pages = await facebook_service._get_user_pages(token_data['access_token'])
            ad_accounts = await facebook_service._get_user_ad_accounts(token_data['access_token'])
            
            print(f"DEBUG: Found {len(pages)} Facebook pages and {len(ad_accounts)} ad accounts")
        
        return OAuthCallbackResponse(
            success=True,
            message=f"Found {len(pages)} Facebook pages available for connection.",
            pages=pages,  # Return pages for selection
            ad_accounts=ad_accounts,  # Return ad accounts for selection
            access_token=token_data['access_token'],
            expires_in=token_data['expires_in'],
            user_name=token_data['user_name'],
            user_email=user_email,
            state=request.state,  # Pass through the state parameter
            user_id=user.id if user else None
        )
        
    except Exception as e:
        print(f"ERROR: Facebook OAuth callback failed: {str(e)}")
        return OAuthCallbackResponse(
            success=False,
            message=f"Failed to connect to Facebook: {str(e)}"
        )


class CreateConnectionRequest(BaseModel):
    """Request model for creating Facebook Page connection"""
    user_id: int
    subclient_id: int
    access_token: str
    expires_in: int
    user_name: str
    user_email: Optional[str] = None
    page_id: Optional[str] = None
    page_name: Optional[str] = None
    page_username: Optional[str] = None
    page_category: Optional[str] = None


class CreateFacebookAdsConnectionRequest(BaseModel):
    """Request model for creating Facebook Ads connection"""
    user_id: int
    subclient_id: int
    access_token: str
    expires_in: int
    user_name: str
    user_email: Optional[str] = None
    ad_account_id: str  # Format: act_123456789
    ad_account_name: str
    currency: Optional[str] = None
    timezone: Optional[str] = None


@router.post("/create-connection", response_model=OAuthCallbackResponse)
async def create_facebook_connection(
    request: CreateConnectionRequest
):
    """
    Create Facebook connection for a specific page
    """
    
    try:
        from app.services.facebook_service import FacebookService
        from app.config.database import get_session
        from app.models.analytics import DigitalAsset, Connection, AssetType, AuthType
        from datetime import datetime, timedelta
        
        facebook_service = FacebookService()
        
        # If page_id is provided, create connection for specific page
        if request.page_id:
            with get_session() as session:
                # Create digital asset for the specific page
                digital_asset = DigitalAsset(
                    subclient_id=request.subclient_id,
                    asset_type=AssetType.SOCIAL_MEDIA,
                    provider="Facebook",
                    name=request.page_name or f"Facebook Page {request.page_id}",
                    handle=request.page_username,
                    external_id=request.page_id,
                    meta={
                        "page_id": request.page_id,
                        "page_name": request.page_name,
                        "page_username": request.page_username,
                        "page_category": request.page_category,
                        "user_name": request.user_name,
                        "user_email": request.user_email,
                        "access_token": request.access_token,
                        "created_via": "page_selection"
                    },
                    is_active=True
                )
                session.add(digital_asset)
                session.commit()
                session.refresh(digital_asset)
                
                # Encrypt access token
                access_token_enc = facebook_service._encrypt_token(request.access_token)
                
                # Calculate expiry time
                expires_at = datetime.utcnow() + timedelta(seconds=request.expires_in)
                
                # Create connection
                connection = Connection(
                    user_id=request.user_id,
                    digital_asset_id=digital_asset.id,
                    auth_type=AuthType.OAUTH2,
                    access_token_enc=access_token_enc,
                    expires_at=expires_at,
                    is_active=True,
                    revoked=False,
                    last_used_at=datetime.utcnow()
                )
                session.add(connection)
                session.commit()
                session.refresh(connection)
                
                return OAuthCallbackResponse(
                    success=True,
                    message=f"Successfully connected Facebook page: {request.page_name}",
                    connections=[{
                        "connection_id": connection.id,
                        "digital_asset_id": digital_asset.id,
                        "asset_name": digital_asset.name,
                        "asset_type": digital_asset.asset_type,
                        "external_id": digital_asset.external_id
                    }],
                    user_name=request.user_name,
                    user_email=request.user_email
                )
        else:
            # Fallback to original behavior for backward compatibility
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


@router.post("/create-ads-connection", response_model=OAuthCallbackResponse)
async def create_facebook_ads_connection(
    request: CreateFacebookAdsConnectionRequest
):
    """
    Create Facebook Ads connection for a specific ad account
    This is separate from Facebook Page connections
    """
    
    try:
        from app.services.facebook_service import FacebookService
        from app.config.database import get_session
        from app.models.analytics import DigitalAsset, Connection, AssetType, AuthType
        from datetime import datetime, timedelta
        
        facebook_service = FacebookService()
        
        with get_session() as session:
            # Create digital asset for the ad account
            digital_asset = DigitalAsset(
                subclient_id=request.subclient_id,
                asset_type=AssetType.FACEBOOK_ADS,  # Use new FACEBOOK_ADS type
                provider="Facebook",
                name=request.ad_account_name,
                external_id=request.ad_account_id,
                meta={
                    "ad_account_id": request.ad_account_id,
                    "ad_account_name": request.ad_account_name,
                    "currency": request.currency,
                    "timezone": request.timezone,
                    "user_name": request.user_name,
                    "user_email": request.user_email,
                    "created_via": "ads_account_selection"
                },
                is_active=True
            )
            session.add(digital_asset)
            session.commit()
            session.refresh(digital_asset)
            
            # Encrypt access token
            access_token_enc = facebook_service._encrypt_token(request.access_token)
            
            # Calculate expiry time
            expires_at = datetime.utcnow() + timedelta(seconds=request.expires_in)
            
            # Create connection
            connection = Connection(
                user_id=request.user_id,
                digital_asset_id=digital_asset.id,
                auth_type=AuthType.OAUTH2,
                access_token_enc=access_token_enc,
                expires_at=expires_at,
                account_email=request.user_email,
                is_active=True,
                revoked=False,
                last_used_at=datetime.utcnow()
            )
            session.add(connection)
            session.commit()
            session.refresh(connection)
            
            return OAuthCallbackResponse(
                success=True,
                message=f"Successfully connected Facebook Ads account: {request.ad_account_name}",
                connections=[{
                    "connection_id": connection.id,
                    "digital_asset_id": digital_asset.id,
                    "asset_name": digital_asset.name,
                    "asset_type": digital_asset.asset_type,
                    "external_id": digital_asset.external_id
                }],
                user_name=request.user_name,
                user_email=request.user_email
            )
    
    except Exception as e:
        return OAuthCallbackResponse(
            success=False,
            message=f"Failed to create Facebook Ads connection: {str(e)}"
        )

