"""
Facebook Page OAuth routes
Handles OAuth flow specifically for Facebook Pages (not ads)
"""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import os

router = APIRouter(prefix="/facebook-page-oauth", tags=["facebook-page-oauth"])


class OAuthCallbackResponse(BaseModel):
    """Response model for OAuth callback"""
    success: bool
    message: str
    pages: Optional[List[Dict[str, Any]]] = None
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
    """Test endpoint to verify Facebook Page OAuth routes are working"""
    return {"status": "ok", "message": "Facebook Page OAuth endpoints are working"}


@router.get("/oauth-url")
async def get_oauth_url(redirect_uri: str, state: str = None):
    """
    Get Facebook Page OAuth URL for frontend to redirect to
    Note: Only requests Facebook Page scopes. For Facebook Ads, use the separate Facebook Marketing OAuth flow.
    """
    try:
        from app.config.settings import get_settings
        settings = get_settings()
        
        # Facebook Page specific scopes - only for page management and insights
        page_scopes = [
            'email',                     # Basic user email
            'public_profile',            # Basic user profile
            'pages_read_engagement',     # Read page insights
            'pages_manage_metadata',     # Manage page metadata
            'pages_show_list',          # Show pages list
            'read_insights',            # Read insights data
            'pages_read_user_content',  # Read user content on pages
            'pages_manage_posts',       # Manage page posts
            'pages_manage_engagement'   # Manage page engagement
        ]
        
        params = {
            'client_id': settings.facebook_app_id,
            'redirect_uri': redirect_uri,
            'scope': ','.join(page_scopes),
            'response_type': 'code',
            'state': state or 'facebook_page_oauth'
        }
        
        auth_url = f"https://www.facebook.com/v18.0/dialog/oauth?" + "&".join([f"{k}={v}" for k, v in params.items()])
        
        return {"auth_url": auth_url}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate Facebook Page OAuth URL: {str(e)}"
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
    Handle Facebook Page OAuth callback (public endpoint)
    Exchanges authorization code for tokens and returns available pages
    Note: Only handles Facebook Page scopes. For Facebook Ads, use the separate Facebook Marketing OAuth flow.
    """
    
    print(f"DEBUG: Facebook Page OAuth callback started with code: {request.code[:10]}...")
    
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
            
            # Get available Facebook pages (only pages, not ad accounts)
            print(f"🔍 DEBUG: Fetching Facebook pages for Page connection...")
            print(f"🔍 DEBUG: Using access token: {token_data['access_token'][:20]}...")
            
            # Check what permissions were granted
            print(f"🔍 Checking granted permissions for access token...")
            try:
                import requests
                permissions_url = f"{facebook_service.base_url}/me/permissions"
                permissions_response = requests.get(permissions_url, params={'access_token': token_data['access_token']})
                if permissions_response.ok:
                    permissions_data = permissions_response.json()
                    granted_permissions = [p['permission'] for p in permissions_data.get('data', []) if p.get('status') == 'granted']
                    print(f"✅ Granted permissions: {', '.join(granted_permissions)}")
                    
                    # Check if pages permissions are granted
                    has_pages_show_list = 'pages_show_list' in granted_permissions
                    has_pages_read_engagement = 'pages_read_engagement' in granted_permissions
                    
                    if not has_pages_show_list:
                        print(f"⚠️ WARNING: pages_show_list permission is not granted!")
                        print(f"   This means Facebook won't return any pages.")
                        print(f"   The user needs to re-authorize with pages permissions.")
                else:
                    print(f"⚠️ Could not fetch permissions: {permissions_response.text}")
            except Exception as e:
                print(f"⚠️ Error checking permissions: {str(e)}")
            
            pages = await facebook_service._get_user_pages(token_data['access_token'])
            
            print(f"✅ DEBUG: Found {len(pages)} Facebook pages for Page connection")
            print(f"🔍 DEBUG: Pages data: {pages}")
        
        return OAuthCallbackResponse(
            success=True,
            message=f"Found {len(pages)} Facebook pages available for connection.",
            pages=pages,  # Return pages for selection
            access_token=token_data['access_token'],
            expires_in=token_data['expires_in'],
            user_name=token_data['user_name'],
            user_email=user_email,
            state=request.state,  # Pass through the state parameter
            user_id=user.id if user else None
        )
        
    except Exception as e:
        print(f"ERROR: Facebook Page OAuth callback failed: {str(e)}")
        return OAuthCallbackResponse(
            success=False,
            message=f"Failed to connect to Facebook Page: {str(e)}"
        )


class CreatePageConnectionRequest(BaseModel):
    """Request model for creating Facebook Page connection"""
    user_id: int
    subclient_id: int
    page_id: str
    page_name: str
    page_username: Optional[str] = None
    page_category: Optional[str] = None
    user_name: str
    user_email: str
    access_token: str


@router.post("/create-connection", response_model=OAuthCallbackResponse)
async def create_facebook_page_connection(
    request: CreatePageConnectionRequest
):
    """
    Create Facebook Page connection for a specific page
    """
    
    try:
        from app.services.facebook_service import FacebookService
        from app.config.database import get_session
        from app.models.analytics import DigitalAsset, Connection, AssetType, AuthType
        from datetime import datetime, timedelta
        
        facebook_service = FacebookService()
        
        with get_session() as session:
            # First, deactivate all other SOCIAL_MEDIA assets for this user/subclient
            print(f"DEBUG: Deactivating other SOCIAL_MEDIA assets for user {request.user_id}, subclient {request.subclient_id}")
            from sqlmodel import select, and_
            deactivate_statement = select(DigitalAsset).where(
                and_(
                    DigitalAsset.subclient_id == request.subclient_id,
                    DigitalAsset.asset_type == AssetType.SOCIAL_MEDIA,
                    DigitalAsset.provider == "Facebook",
                    DigitalAsset.is_active == True
                )
            )
            other_assets = session.exec(deactivate_statement).all()
            for asset in other_assets:
                asset.is_active = False
                print(f"DEBUG: Deactivated asset {asset.id}: {asset.name}")
            session.commit()
            
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
                    "created_via": "page_selection",
                    "service_type": "facebook_page"
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
        
    except Exception as e:
        print(f"ERROR: Failed to create Facebook Page connection: {str(e)}")
        return OAuthCallbackResponse(
            success=False,
            message=f"Failed to create Facebook Page connection: {str(e)}"
        )
