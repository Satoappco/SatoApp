"""
Facebook API routes for data fetching and connection management
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from fastapi import APIRouter, HTTPException, status, Depends, Query
from pydantic import BaseModel
from sqlmodel import select, and_

from app.config.database import get_session
from app.models.analytics import Connection, DigitalAsset, AssetType
from app.services.facebook_service import FacebookService
from app.core.auth import get_current_user
from app.models.users import Campaigner

router = APIRouter(prefix="/facebook", tags=["facebook"])


class FacebookConnection(BaseModel):
    """Facebook connection model"""
    id: int
    asset_name: str
    asset_type: str
    external_id: str
    provider: str
    account_email: Optional[str] = None
    is_active: bool
    created_at: datetime
    last_used_at: Optional[datetime] = None


class FacebookConnectionsResponse(BaseModel):
    """Response model for Facebook connections"""
    connections: List[FacebookConnection]


class FacebookDataRequest(BaseModel):
    """Request model for Facebook data fetching"""
    connection_id: int
    data_type: str = "page_insights"  # page_insights, ad_insights, page_posts
    start_date: str = "7daysAgo"
    end_date: str = "today"
    metrics: Optional[List[str]] = None
    limit: int = 100


class FacebookDataResponse(BaseModel):
    """Response model for Facebook data"""
    success: bool
    data_type: str
    asset_name: str
    external_id: str
    metrics: List[str]
    date_range: Dict[str, str]
    data: List[Dict[str, Any]]
    paging: Optional[Dict[str, Any]] = None
    timestamp: str


@router.get("/connections", response_model=FacebookConnectionsResponse)
async def get_facebook_connections(
    customer_id: int = Query(None, description="Filter connections by customer ID"),
    current_user: Campaigner = Depends(get_current_user)
):
    """
    Get Facebook connections for the current authenticated user, optionally filtered by customer
    """
    
    try:
        with get_session() as session:
            # Build query conditions - now with direct customer relationship
            conditions = [
                Connection.campaigner_id == current_user.id,  # Real authenticated user ID
                DigitalAsset.provider == "Facebook",
                Connection.revoked == False
            ]
            
            # Add customer filter if provided - now direct on connections table
            if customer_id is not None:
                conditions.append(Connection.customer_id == customer_id)
            
            # Get Facebook connections for the current user - still need to join for asset info
            statement = select(Connection, DigitalAsset).join(
                DigitalAsset, Connection.digital_asset_id == DigitalAsset.id
            ).where(and_(*conditions))
            
            results = session.exec(statement).all()
            
            connections = []
            for connection, asset in results:
                connections.append(FacebookConnection(
                    id=connection.id,
                    asset_name=asset.name,
                    asset_type=asset.asset_type,
                    external_id=asset.external_id,
                    provider=asset.provider,
                    account_email=connection.account_email,
                    is_active=asset.is_active,
                    created_at=connection.created_at,
                    last_used_at=connection.last_used_at
                ))
            
            return FacebookConnectionsResponse(connections=connections)
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch Facebook connections: {str(e)}"
        )


@router.delete("/connections/{connection_id}")
async def revoke_facebook_connection(
    connection_id: int,
    current_user: Campaigner = Depends(get_current_user)
):
    """
    Revoke Facebook connection
    """
    
    try:
        with get_session() as session:
            # Verify user owns this connection
            statement = select(Connection).where(
                and_(
                    Connection.id == connection_id,
                    Connection.campaigner_id == current_user.id
                )
            )
            connection = session.exec(statement).first()
            
            if not connection:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Connection not found"
                )
            
            # First, revoke the token with Facebook
            try:
                import requests
                from app.services.google_analytics_service import GoogleAnalyticsService
                
                ga_service = GoogleAnalyticsService()
                access_token = ga_service._decrypt_token(connection.access_token_enc)
                
                # Get Facebook App ID from environment
                import os
                app_id = os.getenv('FACEBOOK_APP_ID')
                
                if app_id:
                    # Revoke the token with Facebook Graph API
                    # Facebook requires: DELETE https://graph.facebook.com/{user-id}/permissions?access_token={access-token}
                    revoke_url = f"https://graph.facebook.com/me/permissions"
                    response = requests.delete(
                        revoke_url,
                        params={'access_token': access_token}
                    )
                    
                    if response.status_code == 200:
                        print(f"Successfully revoked Facebook token for connection {connection_id}")
                    else:
                        print(f"Warning: Facebook revocation returned status {response.status_code} for connection {connection_id}")
                else:
                    print(f"Warning: FACEBOOK_APP_ID not set, cannot revoke with Facebook")
                    
            except Exception as e:
                print(f"Error revoking token with Facebook for connection {connection_id}: {str(e)}")
                # Continue anyway to delete from our DB

            # Store the digital asset ID before deleting the connection
            digital_asset_id = connection.digital_asset_id

            # Delete the connection from our database
            session.delete(connection)
            session.commit()

            # Check if the digital asset should be deleted (no remaining connections)
            from app.services.digital_asset_service import delete_orphaned_digital_asset
            asset_deleted = delete_orphaned_digital_asset(session, digital_asset_id)

            message = "Facebook connection deleted successfully"
            if asset_deleted:
                message += " and associated digital asset was removed (no other connections)"

            return {"message": message}
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to revoke connection: {str(e)}"
        )


@router.post("/data", response_model=FacebookDataResponse)
async def fetch_facebook_data(
    request: FacebookDataRequest,
    current_user: Campaigner = Depends(get_current_user)
):
    """
    Fetch data from Facebook
    """
    
    try:
        # Verify user owns this connection
        with get_session() as session:
            statement = select(Connection, DigitalAsset).join(
                DigitalAsset, Connection.digital_asset_id == DigitalAsset.id
            ).where(
                and_(
                    Connection.id == request.connection_id,
                    Connection.user_id == 5  # Demo user ID
                )
            )
            result = session.exec(statement).first()
            
            if not result:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Connection not found"
                )
            
            connection, asset = result
        
        # Fetch data using Facebook service
        facebook_service = FacebookService()
        result = await facebook_service.fetch_facebook_data(
            connection_id=request.connection_id,
            data_type=request.data_type,
            start_date=request.start_date,
            end_date=request.end_date,
            metrics=request.metrics,
            limit=request.limit
        )
        
        return FacebookDataResponse(**result)
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch Facebook data: {str(e)}"
        )


@router.get("/pages/{connection_id}")
async def get_facebook_pages(
    connection_id: int,
    current_user: Campaigner = Depends(get_current_user)
):
    """
    Get Facebook pages for a connection
    """
    
    try:
        with get_session() as session:
            # Verify user owns this connection
            statement = select(Connection, DigitalAsset).join(
                DigitalAsset, Connection.digital_asset_id == DigitalAsset.id
            ).where(
                and_(
                    Connection.id == connection_id,
                    Connection.user_id == 5  # Demo user ID
                )
            )
            result = session.exec(statement).first()
            
            if not result:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Connection not found"
                )
            
            connection, asset = result
            
            # Get all pages for this user
            pages_statement = select(DigitalAsset).where(
                and_(
                    DigitalAsset.provider == "Facebook",
                    DigitalAsset.asset_type == AssetType.SOCIAL_MEDIA,
                    DigitalAsset.subclient_id == asset.subclient_id
                )
            )
            pages = session.exec(pages_statement).all()
            
            return {
                "pages": [
                    {
                        "id": page.external_id,
                        "name": page.name,
                        "username": page.meta.get("page_username"),
                        "category": page.meta.get("page_category")
                    }
                    for page in pages
                ]
            }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch Facebook pages: {str(e)}"
        )


@router.get("/ad-accounts/{connection_id}")
async def get_facebook_ad_accounts(
    connection_id: int,
    current_user: Campaigner = Depends(get_current_user)
):
    """
    Get Facebook ad accounts for a connection
    """
    
    try:
        with get_session() as session:
            # Verify user owns this connection
            statement = select(Connection, DigitalAsset).join(
                DigitalAsset, Connection.digital_asset_id == DigitalAsset.id
            ).where(
                and_(
                    Connection.id == connection_id,
                    Connection.user_id == 5  # Demo user ID
                )
            )
            result = session.exec(statement).first()
            
            if not result:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Connection not found"
                )
            
            connection, asset = result
            
            # Get all ad accounts for this user
            ad_accounts_statement = select(DigitalAsset).where(
                and_(
                    DigitalAsset.provider == "Facebook",
                    DigitalAsset.asset_type == AssetType.ADVERTISING,
                    DigitalAsset.subclient_id == asset.subclient_id
                )
            )
            ad_accounts = session.exec(ad_accounts_statement).all()
            
            return {
                "ad_accounts": [
                    {
                        "id": ad_account.external_id,
                        "name": ad_account.name,
                        "currency": ad_account.meta.get("ad_account_currency")
                    }
                    for ad_account in ad_accounts
                ]
            }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch Facebook ad accounts: {str(e)}"
        )


@router.get("/available-pages/{subclient_id}")
async def get_available_facebook_pages(
    subclient_id: int,
    current_user: Campaigner = Depends(get_current_user)
):
    """
    Get ALL available Facebook pages from Facebook using an existing connection's tokens.
    This allows users to see all their Facebook pages even if not all are connected.
    """
    
    try:
        with get_session() as session:
            # Find any active Facebook Page connection for this user and subclient
            statement = select(Connection, DigitalAsset).join(
                DigitalAsset, Connection.digital_asset_id == DigitalAsset.id
            ).where(
                Connection.campaigner_id == current_user.id,
                DigitalAsset.subclient_id == subclient_id,
                DigitalAsset.asset_type == AssetType.SOCIAL_MEDIA,
                DigitalAsset.provider == "Facebook",
                Connection.revoked == False
            ).limit(1)
            
            result = session.exec(statement).first()
            
            if not result:
                return {
                    "success": False,
                    "message": "No Facebook Page connection found. Please connect to Facebook first.",
                    "pages": []
                }
            
            connection, digital_asset = result
            
            # Check if token is expired or expiring soon, and refresh if needed
            from datetime import timedelta
            buffer_time = timedelta(minutes=5)
            if connection.expires_at and connection.expires_at < datetime.utcnow() + buffer_time:
                print(f"🔄 Facebook token expired or expiring soon, refreshing...")
                try:
                    # Refresh the token using the service method
                    refresh_result = await facebook_service.refresh_facebook_token(connection.id)
                    access_token = refresh_result.get("access_token")
                    print(f"✅ Successfully refreshed Facebook token")
                    # Reload connection to get updated data
                    session.refresh(connection)
                except Exception as e:
                    print(f"❌ Failed to refresh Facebook token: {str(e)}")
                    return {
                        "success": False,
                        "message": "Token expired. Please reconnect to Facebook.",
                        "pages": []
                    }
            else:
                # Decrypt access token
                access_token = facebook_service._decrypt_token(connection.access_token_enc)
            
            print(f"DEBUG: Fetching all available Facebook pages for user {current_user.id}")
            
            # Fetch all available Facebook pages
            pages = await facebook_service._get_user_pages(access_token)
            
            print(f"DEBUG: Found {len(pages)} total Facebook pages")
            
            # Mark which pages are already connected
            connected_page_ids = []
            assets_statement = select(DigitalAsset).where(
                DigitalAsset.subclient_id == subclient_id,
                DigitalAsset.asset_type == AssetType.SOCIAL_MEDIA,
                DigitalAsset.provider == "Facebook"
            )
            connected_assets = session.exec(assets_statement).all()
            connected_page_ids = [asset.external_id for asset in connected_assets]
            
            # Add connected flag to each page
            for page in pages:
                page['is_connected'] = page['id'] in connected_page_ids
            
            return {
                "success": True,
                "pages": pages,
                "message": f"Found {len(pages)} Facebook pages",
                "access_token": access_token
            }
    
    except Exception as e:
        print(f"DEBUG: Error fetching available Facebook pages: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch available Facebook pages: {str(e)}"
        )


@router.get("/available-ad-accounts/{subclient_id}")
async def get_available_facebook_ad_accounts(
    subclient_id: int,
    current_user: Campaigner = Depends(get_current_user)
):
    """
    Get ALL available Facebook ad accounts from Facebook using an existing connection's tokens.
    This allows users to see all their Facebook ad accounts even if not all are connected.
    """
    
    try:
        with get_session() as session:
            # Find any active Facebook Ads connection for this user and subclient
            statement = select(Connection, DigitalAsset).join(
                DigitalAsset, Connection.digital_asset_id == DigitalAsset.id
            ).where(
                Connection.campaigner_id == current_user.id,
                DigitalAsset.subclient_id == subclient_id,
                DigitalAsset.asset_type == AssetType.ADVERTISING,
                DigitalAsset.provider == "Facebook",
                Connection.revoked == False
            ).limit(1)
            
            result = session.exec(statement).first()
            
            if not result:
                return {
                    "success": False,
                    "message": "No Facebook Ads connection found. Please connect to Facebook Ads first.",
                    "ad_accounts": []
                }
            
            connection, digital_asset = result
            
            # Check if token is expired or expiring soon, and refresh if needed
            buffer_time = timedelta(minutes=5)
            if connection.expires_at and connection.expires_at < datetime.utcnow() + buffer_time:
                print(f"🔄 Facebook token expired or expiring soon, refreshing...")
                try:
                    # Refresh the token using the service method
                    refresh_result = await facebook_service.refresh_facebook_token(connection.id)
                    access_token = refresh_result.get("access_token")
                    print(f"✅ Successfully refreshed Facebook token")
                    # Reload connection to get updated data
                    session.refresh(connection)
                except Exception as e:
                    print(f"❌ Failed to refresh Facebook token: {str(e)}")
                    return {
                        "success": False,
                        "message": "Token expired. Please reconnect to Facebook Ads.",
                        "ad_accounts": []
                    }
            else:
                # Decrypt access token
                access_token = facebook_service._decrypt_token(connection.access_token_enc)
            
            print(f"DEBUG: Fetching all available Facebook ad accounts for user {current_user.id}")
            
            # Fetch all available Facebook ad accounts
            ad_accounts = await facebook_service._get_user_ad_accounts(access_token)
            
            print(f"DEBUG: Found {len(ad_accounts)} total Facebook ad accounts")
            
            # Mark which ad accounts are already connected
            connected_ad_account_ids = []
            assets_statement = select(DigitalAsset).where(
                DigitalAsset.subclient_id == subclient_id,
                DigitalAsset.asset_type == AssetType.ADVERTISING,
                DigitalAsset.provider == "Facebook"
            )
            connected_assets = session.exec(assets_statement).all()
            connected_ad_account_ids = [asset.external_id for asset in connected_assets]
            
            # Add connected flag to each ad account
            for ad_account in ad_accounts:
                ad_account['is_connected'] = ad_account['id'] in connected_ad_account_ids
            
            return {
                "success": True,
                "ad_accounts": ad_accounts,
                "message": f"Found {len(ad_accounts)} Facebook ad accounts",
                "access_token": access_token
            }
    
    except Exception as e:
        print(f"DEBUG: Error fetching available Facebook ad accounts: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch available Facebook ad accounts: {str(e)}"
        )

