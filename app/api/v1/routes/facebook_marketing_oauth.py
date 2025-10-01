"""
Facebook Marketing OAuth routes
Handles OAuth flow specifically for Facebook Ads/Marketing (not pages)
"""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import os

router = APIRouter(prefix="/facebook-marketing-oauth", tags=["facebook-marketing-oauth"])


class OAuthCallbackResponse(BaseModel):
    """Response model for OAuth callback"""
    success: bool
    message: str
    ad_accounts: Optional[List[Dict[str, Any]]] = None
    access_token: Optional[str] = None
    expires_in: Optional[int] = None
    user_name: Optional[str] = None
    user_email: Optional[str] = None
    state: Optional[str] = None
    user_id: Optional[int] = None


class OAuthCallbackRequest(BaseModel):
    """Request model for OAuth callback"""
    code: str
    redirect_uri: str
    state: Optional[str] = None


@router.get("/test")
async def test_endpoint():
    """Test endpoint to verify Facebook Marketing OAuth routes are working"""
    return {"status": "ok", "message": "Facebook Marketing OAuth endpoints are working"}


@router.get("/oauth-url")
async def get_oauth_url(redirect_uri: str, state: str = None):
    """
    Get Facebook Marketing OAuth URL for frontend to redirect to
    Note: Only requests Facebook Ads scopes. For Facebook Pages, use the separate Facebook Page OAuth flow.
    """
    try:
        from app.config.settings import get_settings
        settings = get_settings()
        
        # Facebook Marketing specific scopes - only for ads and business management
        marketing_scopes = [
            'email',                     # Basic user email
            'public_profile',            # Basic user profile
            'ads_read',                  # Read ads data
            'ads_management',            # Manage ads
            'business_management',       # Manage business assets
            'read_insights'             # Read insights data
        ]
        
        params = {
            'client_id': settings.facebook_app_id,
            'redirect_uri': redirect_uri,
            'scope': ','.join(marketing_scopes),
            'response_type': 'code',
            'state': state or 'facebook_marketing_oauth'
        }
        
        auth_url = f"https://www.facebook.com/v18.0/dialog/oauth?" + "&".join([f"{k}={v}" for k, v in params.items()])
        
        return {"auth_url": auth_url}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate Facebook Marketing OAuth URL: {str(e)}"
        )


@router.options("/oauth-callback")
async def handle_oauth_callback_options():
    """Handle CORS preflight request for OAuth callback"""
    return {"message": "OK"}


@router.post("/oauth-callback", response_model=OAuthCallbackResponse)
async def handle_oauth_callback(
    request: OAuthCallbackRequest
):
    """
    Handle Facebook Marketing OAuth callback (public endpoint)
    Exchanges authorization code for tokens and returns available ad accounts
    Note: Only handles Facebook Ads scopes. For Facebook Pages, use the separate Facebook Page OAuth flow.
    """
    
    print(f"DEBUG: Facebook Marketing OAuth callback started with code: {request.code[:10]}...")
    
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
        
        with get_session() as session:
            user = None
            
            if user_email:
                # Try to find user by Facebook email
                user_statement = select(User).where(User.email == user_email)
                user = session.exec(user_statement).first()
                print(f"DEBUG: Found user by Facebook email {user_email}: {user.id if user else 'None'}")
            
            if not user:
                # Fallback: Find the demo user (ID 5) for now
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
            
            # Get available Facebook ad accounts (only ad accounts, not pages)
            ad_accounts = await facebook_service._get_user_ad_accounts(token_data['access_token'])
            
            print(f"DEBUG: Found {len(ad_accounts)} Facebook ad accounts for Marketing connection")
        
        return OAuthCallbackResponse(
            success=True,
            message=f"Found {len(ad_accounts)} Facebook ad accounts available for connection.",
            ad_accounts=ad_accounts,  # Return ad accounts for selection
            access_token=token_data['access_token'],
            expires_in=token_data['expires_in'],
            user_name=token_data['user_name'],
            user_email=user_email,
            state=request.state,  # Pass through the state parameter
            user_id=user.id if user else None
        )
        
    except Exception as e:
        print(f"ERROR: Facebook Marketing OAuth callback failed: {str(e)}")
        return OAuthCallbackResponse(
            success=False,
            message=f"Failed to connect to Facebook Marketing: {str(e)}"
        )


class CreateMarketingConnectionRequest(BaseModel):
    """Request model for creating Facebook Marketing connection"""
    user_id: int
    subclient_id: int
    ad_account_id: str
    ad_account_name: str
    currency: Optional[str] = None
    timezone: Optional[str] = None
    user_name: str
    user_email: str
    access_token: str


@router.post("/create-connection", response_model=OAuthCallbackResponse)
async def create_facebook_marketing_connection(
    request: CreateMarketingConnectionRequest
):
    """
    Create Facebook Marketing connection for a specific ad account
    """
    
    try:
        from app.services.facebook_service import FacebookService
        from app.config.database import get_session
        from app.models.analytics import DigitalAsset, Connection, AssetType, AuthType
        from datetime import datetime, timedelta
        
        facebook_service = FacebookService()
        
        with get_session() as session:
            # First, deactivate all other FACEBOOK_ADS assets for this user/subclient
            print(f"DEBUG: Deactivating other FACEBOOK_ADS assets for user {request.user_id}, subclient {request.subclient_id}")
            from sqlmodel import select, and_
            deactivate_statement = select(DigitalAsset).where(
                and_(
                    DigitalAsset.subclient_id == request.subclient_id,
                    DigitalAsset.asset_type == AssetType.FACEBOOK_ADS,
                    DigitalAsset.provider == "Facebook",
                    DigitalAsset.is_active == True
                )
            )
            other_assets = session.exec(deactivate_statement).all()
            for asset in other_assets:
                asset.is_active = False
                print(f"DEBUG: Deactivated asset {asset.id}: {asset.name}")
            session.commit()
            
            # Create digital asset for the specific ad account
            digital_asset = DigitalAsset(
                subclient_id=request.subclient_id,
                asset_type=AssetType.FACEBOOK_ADS,
                provider="Facebook",
                name=request.ad_account_name or f"Facebook Ad Account {request.ad_account_id}",
                handle=None,  # Ad accounts don't have handles
                external_id=request.ad_account_id,
                meta={
                    "ad_account_id": request.ad_account_id,
                    "ad_account_name": request.ad_account_name,
                    "currency": request.currency,
                    "timezone": request.timezone,
                    "user_name": request.user_name,
                    "user_email": request.user_email,
                    "access_token": request.access_token,
                    "created_via": "ad_account_selection",
                    "service_type": "facebook_marketing"
                },
                is_active=True
            )
            session.add(digital_asset)
            session.commit()
            session.refresh(digital_asset)
            
            # Encrypt access token
            access_token_enc = facebook_service._encrypt_token(request.access_token)
            
            # Calculate expiry time (default to 1 hour if not specified)
            expires_at = datetime.utcnow() + timedelta(seconds=3600)
            
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
                message=f"Successfully connected Facebook ad account: {request.ad_account_name}",
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
        print(f"ERROR: Failed to create Facebook Marketing connection: {str(e)}")
        return OAuthCallbackResponse(
            success=False,
            message=f"Failed to create Facebook Marketing connection: {str(e)}"
        )
