"""
Facebook Marketing OAuth routes
Handles OAuth flow specifically for Facebook Ads/Marketing (not pages)
"""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta, timezone
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
    
    # Verify and extract user context from signed state
    campaigner_id = None
    customer_id = None
    
    if request.state:
        try:
            from app.config.settings import get_settings
            settings = get_settings()
            
            # Decode and verify the JWT
            import jwt
            payload = jwt.decode(
                request.state,
                settings.oauth_state_secret,
                algorithms=["HS256"]
            )
            
            campaigner_id = payload.get('campaigner_id')
            customer_id = payload.get('customer_id')
            timestamp = payload.get('timestamp')

            # Check expiration using JWT exp field
            if datetime.now(timezone.utc).timestamp() > payload.get('exp', 0):
                raise HTTPException(
                    status_code=400,
                    detail="OAuth state has expired"
                )
            
            print(f"DEBUG: User context extracted - Campaigner ID: {campaigner_id}, Customer ID: {customer_id}")
            
        except jwt.InvalidTokenError as e:
            print(f"❌ Invalid OAuth state: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Invalid OAuth state: {str(e)}"
            )
        except Exception as e:
            print(f"❌ OAuth state verification failed: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to verify OAuth state: {str(e)}"
            )
    
    if not campaigner_id or not customer_id:
        raise HTTPException(
            status_code=400,
            detail="No user found. Please sign in first."
        )
    
    try:
        from app.services.facebook_service import FacebookService
        
        facebook_service = FacebookService()
        
        # Exchange code for tokens
        token_data = await facebook_service.exchange_code_for_token(
            code=request.code,
            redirect_uri=request.redirect_uri
        )
        
        print(f"DEBUG: Token exchange successful for user: {token_data['user_name']}")
        
        # Use campaigner_id from JWT state (already validated above)
        from app.models.users import Campaigner
        from app.config.database import get_session
        from sqlmodel import select
        
        with get_session() as session:
            # Get the campaigner who initiated this OAuth flow
            campaigner = session.exec(
                select(Campaigner).where(Campaigner.id == campaigner_id)
            ).first()
            
            if not campaigner:
                print(f"DEBUG: Campaigner {campaigner_id} not found in database")
                return OAuthCallbackResponse(
                    success=False,
                    message="No user found. Please sign in first."
                )
            
            print(f"DEBUG: OAuth successful for campaigner {campaigner.id} ({campaigner.email}), connecting for customer {customer_id}")
            
            # Get available Facebook ad accounts (only ad accounts, not pages)
            print(f"🔍 DEBUG: Fetching Facebook ad accounts for Marketing connection...")
            print(f"🔍 DEBUG: Using access token: {token_data['access_token'][:20]}...")
            
            ad_accounts = await facebook_service._get_user_ad_accounts(token_data['access_token'])
            
            print(f"✅ DEBUG: Found {len(ad_accounts)} Facebook ad accounts for Marketing connection")
            print(f"🔍 DEBUG: Ad accounts data: {ad_accounts}")
            
            # Also check what pages would be returned for comparison
            pages = await facebook_service._get_user_pages(token_data['access_token'])
            print(f"🔍 DEBUG: For comparison - Found {len(pages)} Facebook pages")
            print(f"🔍 DEBUG: Pages data: {pages}")
            
            # Check if we got any ad accounts
            if len(ad_accounts) == 0:
                print(f"⚠️ WARNING: No ad accounts found. This could mean:")
                print(f"   1. User doesn't have any Facebook Ads accounts")
                print(f"   2. Facebook app doesn't have ads_read/ads_management permissions approved")
                print(f"   3. User didn't grant ads permissions during OAuth")
                
                return OAuthCallbackResponse(
                    success=False,
                    message="No Facebook ad accounts found. Please ensure: (1) You have at least one Facebook Ads account, (2) The Facebook app has ads_read and ads_management permissions approved via App Review, (3) You granted ads permissions during the OAuth process.",
                    ad_accounts=[],
                    access_token=token_data['access_token'],
                    expires_in=token_data['expires_in'],
                    user_name=token_data['user_name'],
                    user_email=token_data.get('user_email', ''),
                    state=request.state,
                    user_id=campaigner.id if campaigner else None
                )
        
        return OAuthCallbackResponse(
            success=True,
            message=f"Found {len(ad_accounts)} Facebook ad account(s) available for connection.",
            ad_accounts=ad_accounts,  # Return ad accounts for selection
            access_token=token_data['access_token'],
            expires_in=token_data['expires_in'],
            user_name=token_data['user_name'],
            user_email=token_data.get('user_email', ''),
            state=request.state,  # Pass through the state parameter
            user_id=campaigner.id if campaigner else None
        )
        
    except Exception as e:
        print(f"ERROR: Facebook Marketing OAuth callback failed: {str(e)}")
        return OAuthCallbackResponse(
            success=False,
            message=f"Failed to connect to Facebook Marketing: {str(e)}"
        )


class CreateMarketingConnectionRequest(BaseModel):
    """Request model for creating Facebook Marketing connection"""
    campaigner_id: int
    customer_id: int
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
            # First, deactivate all other FACEBOOK_ADS assets for this campaigner/customer
            print(f"DEBUG: Deactivating other FACEBOOK_ADS assets for campaigner {request.campaigner_id}, customer {request.customer_id}")
            from sqlmodel import select, and_
            deactivate_statement = select(DigitalAsset).where(
                and_(
                    DigitalAsset.customer_id == request.customer_id,
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
                customer_id=request.customer_id,
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
            token_hash = facebook_service._generate_token_hash(request.access_token)

            # Calculate expiry time (default to 1 hour if not specified)
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=3600)

            # Check for existing connection and update if found
            connection_statement = select(Connection).where(
                and_(
                    Connection.digital_asset_id == digital_asset.id,
                    Connection.campaigner_id == request.campaigner_id,
                    Connection.auth_type == AuthType.OAUTH2
                )
            )
            connection = session.exec(connection_statement).first()

            if connection:
                # Update existing connection
                print(f"DEBUG: Updating existing connection {connection.id} for asset {digital_asset.id}")
                connection.access_token_enc = access_token_enc
                connection.token_hash = token_hash
                connection.expires_at = expires_at
                connection.scopes = facebook_service.FACEBOOK_SCOPES
                connection.rotated_at = datetime.now(timezone.utc)
                connection.last_used_at = datetime.now(timezone.utc)
                # Reset connection status - fresh tokens mean connection is healthy
                connection.revoked = False
                connection.needs_reauth = False
                connection.failure_count = 0
                connection.failure_reason = None
                connection.last_failure_at = None
            else:
                # Create new connection
                print(f"DEBUG: Creating new connection for asset {digital_asset.id}")
                connection = Connection(
                    digital_asset_id=digital_asset.id,
                    customer_id=request.customer_id,
                    campaigner_id=request.campaigner_id,
                    auth_type=AuthType.OAUTH2,
                    access_token_enc=access_token_enc,
                    token_hash=token_hash,
                    scopes=facebook_service.FACEBOOK_SCOPES,
                    expires_at=expires_at,
                    revoked=False,
                    needs_reauth=False,
                    failure_count=0,
                    failure_reason=None,
                    last_failure_at=None,
                    last_used_at=datetime.now(timezone.utc)
                )

            session.add(connection)
            session.commit()
            session.refresh(connection)

            # Sync metrics for the new digital asset
            # Note: sync_metrics_new will automatically detect this is a new asset and sync all 90 days
            try:
                from app.services.campaign_sync_service import CampaignSyncService
                print(f"🔄 Starting metrics sync for new Facebook Ads connection...")
                sync_service = CampaignSyncService()
                sync_result = sync_service.sync_metrics_new(customer_id=request.customer_id)
                if sync_result.get("success"):
                    print(f"✅ Metrics sync completed: {sync_result.get('metrics_upserted', 0)} metrics synced")
                else:
                    print(f"⚠️ Metrics sync completed with errors: {sync_result.get('error_details', [])}")
            except Exception as sync_error:
                print(f"⚠️ Failed to sync metrics for new connection: {sync_error}")
                # Don't fail the connection creation if metrics sync fails

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
