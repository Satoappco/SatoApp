"""
Facebook OAuth callback handler
Handles the OAuth flow and automatically creates Facebook connections
"""

import os
from typing import Dict, Any, Optional
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

# Use campaigner_id from JWT state (already validated above)
from app.models.users import Campaigner
from app.config.database import get_session
from sqlmodel import select
from app.services.facebook_service import FacebookService
        
router = APIRouter(prefix="/facebook", tags=["facebook-oauth"])


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
            from datetime import datetime
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
        facebook_service = FacebookService()
        
        # Exchange code for tokens
        token_data = await facebook_service.exchange_code_for_token(
            code=request.code,
            redirect_uri=request.redirect_uri
        )
        
        print(f"DEBUG: Token exchange successful for user: {token_data['user_name']}")
        
        
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
            user_email=token_data.get('user_email', ''),
            state=request.state,  # Pass through the state parameter
            user_id=campaigner.id if campaigner else None
        )
        
    except Exception as e:
        print(f"ERROR: Facebook OAuth callback failed: {str(e)}")
        return OAuthCallbackResponse(
            success=False,
            message=f"Failed to connect to Facebook: {str(e)}"
        )


class CreateConnectionRequest(BaseModel):
    """Request model for creating Facebook Page connection"""
    campaigner_id: int
    customer_id: int
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
    campaigner_id: int
    customer_id: int
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
                    customer_id=request.customer_id,
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
                token_hash = facebook_service._generate_token_hash(request.access_token)

                # Calculate expiry time
                expires_at = datetime.now(timezone.utc) + timedelta(seconds=request.expires_in)

                # Check for existing connection and update if found
                from sqlmodel import and_
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
                    connection.revoked = False  # Reactivate if it was revoked
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
                        last_used_at=datetime.now(timezone.utc)
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
                campaigner_id=request.campaigner_id,
                customer_id=request.customer_id,
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
        print(f"❌ ERROR in create-facebook-connection: {str(e)}")
        import traceback
        print(f"❌ Traceback: {traceback.format_exc()}")
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

    print(f"📥 CREATE-ADS-CONNECTION request received:")
    print(f"   Ad Account: {request.ad_account_name} (ID: {request.ad_account_id})")
    print(f"   Campaigner ID: {request.campaigner_id}, Customer ID: {request.customer_id}")
    print(f"   Currency: {request.currency}, Timezone: {request.timezone}")

    try:
        from app.services.facebook_service import FacebookService
        from app.config.database import get_session
        from app.models.analytics import DigitalAsset, Connection, AssetType, AuthType
        from datetime import datetime, timedelta
        
        facebook_service = FacebookService()
        
        with get_session() as session:
            # Create digital asset for the ad account
            digital_asset = DigitalAsset(
                customer_id=request.customer_id,
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
            token_hash = facebook_service._generate_token_hash(request.access_token)

            # Calculate expiry time
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=request.expires_in)

            # Check for existing connection and update if found
            from sqlmodel import and_
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
                connection.account_email = request.user_email
                connection.scopes = facebook_service.FACEBOOK_SCOPES
                connection.rotated_at = datetime.now(timezone.utc)
                connection.last_used_at = datetime.now(timezone.utc)
                connection.revoked = False  # Reactivate if it was revoked
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
                    account_email=request.user_email,
                    scopes=facebook_service.FACEBOOK_SCOPES,
                    expires_at=expires_at,
                    revoked=False,
                    last_used_at=datetime.now(timezone.utc)
                )

            session.add(connection)
            session.commit()
            session.refresh(connection)

            print(f"✅ SUCCESS: Created Facebook Ads connection for account {request.ad_account_name} (ID: {request.ad_account_id})")
            print(f"   Connection ID: {connection.id}, Digital Asset ID: {digital_asset.id}")

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
        print(f"❌ ERROR in create-ads-connection: {str(e)}")
        import traceback
        print(f"❌ Traceback: {traceback.format_exc()}")
        return OAuthCallbackResponse(
            success=False,
            message=f"Failed to create Facebook Ads connection: {str(e)}"
        )

