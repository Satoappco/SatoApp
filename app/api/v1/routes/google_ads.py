"""
Google Ads data API routes
Handles Google Ads data fetching and analysis
"""

import os
from datetime import datetime
from fastapi import APIRouter, HTTPException, status, Depends, Query
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from sqlmodel import select

from app.core.auth import get_current_user
from app.models.users import Campaigner
from app.models.analytics import DigitalAsset, Connection, AssetType
from app.config.database import get_session

router = APIRouter(prefix="/google-ads", tags=["Google Ads Data"])

# Initialize service lazily to avoid startup errors
def get_google_ads_service():
    from app.services.google_ads_service import GoogleAdsService
    return GoogleAdsService()

# Initialize service for use in endpoints
google_ads_service = get_google_ads_service()


class GoogleAdsDataRequest(BaseModel):
    connection_id: int
    customer_id: str
    metrics: List[str]
    dimensions: List[str] = []
    start_date: str
    end_date: str
    limit: int = 100


class GoogleAdsDataResponse(BaseModel):
    success: bool
    data: List[Dict[str, Any]]
    total_rows: int
    metrics: List[str]
    dimensions: List[str]


class GoogleAdsConnectionResponse(BaseModel):
    success: bool
    message: str
    connection_id: int
    customer_id: str
    customer_name: str
    account_email: str
    is_active: bool
    expires_at: Optional[str] = None
    last_used_at: Optional[str] = None
    is_outdated: Optional[bool] = None


class GoogleAdsConnectionListResponse(BaseModel):
    connections: List[GoogleAdsConnectionResponse]


class CreateAdsConnectionRequest(BaseModel):
    account_id: str
    account_name: str
    currency_code: str
    time_zone: str
    access_token: str
    refresh_token: str
    expires_in: int = 3600
    customer_id: int  # Required: which customer owns this connection


@router.post("/data", response_model=GoogleAdsDataResponse)
async def get_google_ads_data(
    request: GoogleAdsDataRequest,
    current_user: Campaigner = Depends(get_current_user)
):
    """
    Fetch Google Ads data for analysis
    """
    
    try:
        from app.services.google_analytics_service import GoogleAnalyticsService
        
        ga_service = GoogleAnalyticsService()
        
        # Fetch Google Ads data using the connection
        result = await ga_service.fetch_google_ads_data(
            connection_id=request.connection_id,
            customer_id=request.customer_id,
            metrics=request.metrics,
            dimensions=request.dimensions,
            start_date=request.start_date,
            end_date=request.end_date,
            limit=request.limit
        )
        
        if result.get("success"):
            return GoogleAdsDataResponse(
                success=True,
                data=result.get("data", []),
                total_rows=result.get("total_rows", 0),
                metrics=request.metrics,
                dimensions=request.dimensions
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("error", "Failed to fetch data")
            )
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch Google Ads data: {str(e)}"
        )


@router.get("/connections", response_model=GoogleAdsConnectionListResponse)
async def get_google_ads_connections(
    customer_id: int = Query(None, description="Filter connections by customer ID"),
    current_user: Campaigner = Depends(get_current_user)
):
    """
    Get Google Ads connections for the current authenticated user, optionally filtered by customer
    """
    try:
        from app.config.database import get_session
        from app.models.analytics import Connection, DigitalAsset, AssetType
        from sqlmodel import select, and_
        
        with get_session() as session:
            # Build query conditions - now with direct customer relationship
            conditions = [
                DigitalAsset.asset_type == AssetType.GOOGLE_ADS,
                DigitalAsset.provider == "Google",
                Connection.revoked == False,
                Connection.campaigner_id == current_user.id
            ]
            
            # Add customer filter if provided - now direct on connections table
            if customer_id is not None:
                conditions.append(Connection.customer_id == customer_id)
            
            # Get Google Ads connections
            statement = select(Connection, DigitalAsset).join(
                DigitalAsset, Connection.digital_asset_id == DigitalAsset.id
            ).where(and_(*conditions))
            
            results = session.exec(statement).all()
            print(f"DEBUG: Found {len(results)} Google Ads connections")
            
            connections = []
            for connection, asset in results:
                print(f"DEBUG: Google Ads connection: {connection.id} - {asset.name} - Active: {asset.is_active}")
                
                # Compute token status using backend logic
                is_outdated = google_ads_service.is_token_expired(connection.expires_at) if connection.expires_at else True
                
                connections.append(GoogleAdsConnectionResponse(
                    success=True,
                    message=f"Connected to {asset.name}",
                    connection_id=connection.id,
                    customer_id=asset.external_id,
                    customer_name=asset.name,
                    account_email=connection.account_email,
                    is_active=asset.is_active,
                    expires_at=connection.expires_at.isoformat() if connection.expires_at else None,
                    last_used_at=connection.last_used_at.isoformat() if connection.last_used_at else None,
                    is_outdated=is_outdated
                ))
            
            return GoogleAdsConnectionListResponse(connections=connections)
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get Google Ads connections: {str(e)}"
        )


@router.post("/connections/{connection_id}/refresh")
async def refresh_google_ads_token(
    connection_id: int,
    current_user: Campaigner = Depends(get_current_user)
):
    """
    Refresh Google Ads access token - if refresh token is expired, returns re-auth URL
    """
    
    try:
        # Verify campaigner owns this connection
        with get_session() as session:
            statement = select(Connection).where(
                Connection.id == connection_id,
                Connection.campaigner_id == current_user.id
            )
            connection = session.exec(statement).first()
            
            if not connection:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Connection not found"
                )
        
        result = await google_ads_service.refresh_google_ads_token(connection_id)
        return result
    
    except ValueError as e:
        error_msg = str(e)
        # If refresh token is expired, return re-auth URL instead of error
        if "Please re-authorize:" in error_msg:
            reauth_url = error_msg.split("Please re-authorize: ")[1]
            return {
                "success": False,
                "requires_reauth": True,
                "reauth_url": reauth_url,
                "message": "Refresh token expired. Please re-authorize to get fresh tokens."
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to refresh token: {str(e)}"
        )


@router.delete("/connections/{connection_id}")
async def revoke_google_ads_connection(
    connection_id: int,
    current_user: Campaigner = Depends(get_current_user)
):
    """
    Revoke Google Ads connection
    """
    
    try:
        from app.config.database import get_session
        from app.models.analytics import Connection, DigitalAsset, AssetType
        from sqlmodel import select, and_
        
        with get_session() as session:
            # Verify user owns this connection
            statement = select(Connection, DigitalAsset).join(
                DigitalAsset, Connection.digital_asset_id == DigitalAsset.id
            ).where(
                and_(
                    Connection.id == connection_id,
                    Connection.campaigner_id == current_user.id,
                    DigitalAsset.asset_type == AssetType.GOOGLE_ADS,
                    DigitalAsset.provider == "Google"
                )
            )
            
            result = session.exec(statement).first()
            if not result:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Connection not found"
                )
            
            connection, asset = result
            
            # First, revoke the token with Google
            try:
                import requests
                from app.services.google_analytics_service import GoogleAnalyticsService
                
                ga_service = GoogleAnalyticsService()
                access_token = ga_service._decrypt_token(connection.access_token_enc)
                
                # Revoke the token with Google OAuth2
                revoke_url = "https://oauth2.googleapis.com/revoke"
                response = requests.post(
                    revoke_url,
                    params={'token': access_token},
                    headers={'content-type': 'application/x-www-form-urlencoded'}
                )
                
                if response.status_code == 200:
                    print(f"Successfully revoked Google Ads token with Google for connection {connection_id}")
                else:
                    print(f"Warning: Google revocation returned status {response.status_code} for connection {connection_id}")
                    
            except Exception as e:
                print(f"Error revoking token with Google for connection {connection_id}: {str(e)}")
                # Continue anyway to mark as revoked in our DB
            
            # Mark connection as revoked in our database
            connection.revoked = True
            session.add(connection)
            session.commit()
            
            return {"message": "Google Ads connection revoked successfully"}
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to revoke Google Ads connection: {str(e)}"
        )


@router.post("/create-connection")
async def create_ads_connection(request: CreateAdsConnectionRequest):
    """
    Create Google Ads connection after user selects an account
    """
    try:
        from app.services.google_analytics_service import GoogleAnalyticsService
        from app.config.database import get_session
        from app.models.users import Campaigner
        from sqlmodel import select
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request as GoogleAuthRequest
        import json
        
        # Get user info from the token
        credentials = Credentials(
            token=request.access_token,
            refresh_token=request.refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=os.getenv("GOOGLE_CLIENT_ID"),
            client_secret=os.getenv("GOOGLE_CLIENT_SECRET")
        )
        
        # Get user info
        import requests
        user_info_response = requests.get(
            'https://www.googleapis.com/oauth2/v2/userinfo',
            headers={'Authorization': f'Bearer {request.access_token}'}
        )
        
        if user_info_response.status_code != 200:
            return {"success": False, "message": "Could not get user info from token"}
        
        user_info = user_info_response.json()
        user_email = user_info.get('email')
        
        if not user_email:
            return {"success": False, "message": "Could not get user email from token"}
        
        # Find user in database
        with get_session() as session:
            user_statement = select(Campaigner).where(Campaigner.email == user_email)
            user = session.exec(user_statement).first()
            
            if not user:
                return {"success": False, "message": f"Campaigner {user_email} not found in database"}
            
            print(f"DEBUG: Creating Google Ads connection for user {user.id} ({user.email})")
            
            # Create Google Ads connection using the service
            ga_service = GoogleAnalyticsService()
            
            # Create a Google Ads connection with the selected account details
            from app.config.database import get_session
            from app.models.analytics import DigitalAsset, Connection, AssetType, AuthType
            from datetime import datetime, timedelta
            
            with get_session() as session:
                # Create digital asset for Google Ads account
                digital_asset = DigitalAsset(
                    customer_id=request.customer_id,  # Use the provided customer_id
                    asset_type=AssetType.GOOGLE_ADS,
                    provider="Google",
                    name=request.customer_name,
                    external_id=request.customer_id,
                    meta={
                        "customer_id": request.customer_id,
                        "customer_name": request.customer_name,
                        "currency_code": request.currency_code,
                        "time_zone": request.time_zone,
                        "account_email": user_email,
                        "is_demo": False,
                        "created_via": "oauth_flow"
                    },
                    is_active=True
                )
                session.add(digital_asset)
                session.commit()
                session.refresh(digital_asset)
                
                # Encrypt tokens
                access_token_enc = ga_service._encrypt_token(request.access_token)
                refresh_token_enc = ga_service._encrypt_token(request.refresh_token)
                
                # Calculate expiry time
                expires_at = datetime.utcnow() + timedelta(seconds=request.expires_in)
                
                # Create connection
                connection = Connection(
                    user_id=user.id,
                    digital_asset_id=digital_asset.id,
                    auth_type=AuthType.OAUTH2,
                    access_token_enc=access_token_enc,
                    refresh_token_enc=refresh_token_enc,
                    expires_at=expires_at,
                    is_active=True,
                    revoked=False,
                    last_used_at=datetime.utcnow()
                )
                session.add(connection)
                session.commit()
                session.refresh(connection)
                
                print(f"DEBUG: Google Ads connection created successfully: {connection.id}")
                
                return {
                    "success": True,
                    "message": f"Successfully connected to {request.customer_name}",
                    "connection_id": connection.id,
                    "customer_id": request.customer_id,
                    "customer_name": request.customer_name
                }
    
    except Exception as e:
        print(f"DEBUG: Failed to create Google Ads connection: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"success": False, "message": f"Failed to create connection: {str(e)}"}


@router.get("/metrics")
async def get_available_metrics():
    """
    Get list of available Google Ads metrics
    """
    return {
        "metrics": [
            # Campaign metrics
            "metrics.impressions",
            "metrics.clicks",
            "metrics.ctr",
            "metrics.cost_micros",
            "metrics.conversions",
            "metrics.conversions_value",
            "metrics.cost_per_conversion",
            "metrics.average_cpc",
            "metrics.average_cpm",
            "metrics.average_cpv",
            
            # Ad group metrics
            "metrics.search_impression_share",
            "metrics.search_exact_match_impression_share",
            "metrics.search_rank_lost_impression_share",
            "metrics.search_budget_lost_impression_share",
            
            # Quality metrics
            "metrics.quality_score",
            "metrics.historical_quality_score",
            "metrics.historical_landing_page_quality_score",
            "metrics.historical_creative_quality_score",
            
            # Conversion metrics
            "metrics.all_conversions",
            "metrics.all_conversions_value",
            "metrics.conversion_rate",
            "metrics.cost_per_all_conversions",
            "metrics.value_per_conversion",
            "metrics.value_per_all_conversions"
        ],
        "dimensions": [
            # Time dimensions
            "segments.date",
            "segments.week",
            "segments.month",
            "segments.quarter",
            "segments.year",
            
            # Campaign dimensions
            "campaign.id",
            "campaign.name",
            "campaign.status",
            "campaign.advertising_channel_type",
            "campaign.bidding_strategy_type",
            
            # Ad group dimensions
            "ad_group.id",
            "ad_group.name",
            "ad_group.status",
            "ad_group.type",
            
            # Keyword dimensions
            "ad_group_criterion.keyword.text",
            "ad_group_criterion.keyword.match_type",
            "ad_group_criterion.quality_info.quality_score",
            
            # Geographic dimensions
            "geographic_view.country_criterion_id",
            "geographic_view.location_type",
            
            # Device dimensions
            "segments.device",
            "segments.click_type"
        ]
    }


@router.get("/available-accounts/{customer_id}")
async def get_available_google_ads_accounts(
    customer_id: int,
    current_user: Campaigner = Depends(get_current_user)
):
    """
    Get ALL available Google Ads accounts from Google using an existing connection's tokens.
    This allows users to see all their Google Ads accounts even if not all are connected.
    """
    
    try:
        with get_session() as session:
            # Find any active Google Ads connection for this user and subclient
            statement = select(Connection, DigitalAsset).join(
                DigitalAsset, Connection.digital_asset_id == DigitalAsset.id
            ).where(
                Connection.campaigner_id == current_user.id,
                DigitalAsset.customer_id == customer_id,
                DigitalAsset.asset_type == AssetType.GOOGLE_ADS,
                Connection.revoked == False
            ).limit(1)
            
            result = session.exec(statement).first()
            
            if not result:
                return {
                    "success": False,
                    "message": "No Google Ads connection found. Please connect to Google Ads first.",
                    "accounts": []
                }
            
            connection, digital_asset = result
            
            # Check if token needs refresh (with 5-minute buffer)
            from datetime import timedelta
            buffer_time = timedelta(minutes=5)
            if connection.expires_at and connection.expires_at < datetime.utcnow() + buffer_time:
                print(f"🔄 Google Ads token expired or expiring soon, refreshing...")
                # Refresh the token
                refresh_result = await google_ads_service.refresh_google_ads_token(connection.id)
                if not refresh_result.get("success"):
                    print(f"❌ Failed to refresh Google Ads token")
                    return {
                        "success": False,
                        "message": "Token expired. Please reconnect to Google Ads.",
                        "accounts": []
                    }
                print(f"✅ Successfully refreshed Google Ads token")
                # Reload connection with new token
                session.refresh(connection)
            
            # Decrypt access token
            access_token = google_ads_service._decrypt_token(connection.access_token_enc)
            refresh_token = google_ads_service._decrypt_token(connection.refresh_token_enc) if connection.refresh_token_enc else None
            
            # Fetch all available Google Ads accounts
            from google.oauth2.credentials import Credentials
            from google.ads.googleads.client import GoogleAdsClient
            from app.config.settings import get_settings
            
            settings = get_settings()
            
            credentials = Credentials(
                token=access_token,
                refresh_token=refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=settings.google_client_id,
                client_secret=settings.google_client_secret
            )
            
            accounts = []
            
            print(f"DEBUG: Fetching all available Google Ads accounts for user {current_user.id}")
            
            try:
                # Get developer token from environment
                developer_token = os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN")
                if not developer_token:
                    return {
                        "success": False,
                        "message": "Google Ads Developer Token not configured",
                        "accounts": []
                    }
                
                # Create Google Ads client
                google_ads_client = GoogleAdsClient(
                    credentials=credentials,
                    developer_token=developer_token,
                    login_customer_id=None  # Will list all accessible accounts
                )
                
                # Get the CustomerService
                customer_service = google_ads_client.get_service("CustomerService")
                
                # List accessible customers
                accessible_customers = customer_service.list_accessible_customers()
                
                print(f"DEBUG: Found {len(accessible_customers.resource_names)} accessible customers")
                
                # Get details for each customer
                for resource_name in accessible_customers.resource_names:
                    customer_id = resource_name.split('/')[-1]
                    
                    try:
                        # Create a new client for this customer
                        customer_client = GoogleAdsClient(
                            credentials=credentials,
                            developer_token=developer_token,
                            login_customer_id=customer_id
                        )
                        
                        ga_service = customer_client.get_service("GoogleAdsService")
                        
                        query = """
                            SELECT
                                customer.id,
                                customer.descriptive_name,
                                customer.currency_code,
                                customer.time_zone,
                                customer.manager
                            FROM customer
                            LIMIT 1
                        """
                        
                        response = ga_service.search(customer_id=customer_id, query=query)
                        
                        for row in response:
                            # Skip manager accounts
                            if not row.customer.manager:
                                accounts.append({
                                    'customer_id': str(row.customer.id),
                                    'customer_name': row.customer.descriptive_name,
                                    'currency_code': row.customer.currency_code,
                                    'time_zone': row.customer.time_zone
                                })
                                print(f"DEBUG: Found Google Ads account: {row.customer.descriptive_name} (ID: {row.customer.id})")
                    
                    except Exception as e:
                        print(f"DEBUG: Failed to get details for customer {customer_id}: {str(e)}")
                        continue
            
            except Exception as e:
                print(f"DEBUG: Failed to fetch Google Ads accounts: {str(e)}")
                import traceback
                traceback.print_exc()
                return {
                    "success": False,
                    "error": f"Failed to fetch Google Ads accounts: {str(e)}",
                    "accounts": []
                }
            
            print(f"DEBUG: Found {len(accounts)} total Google Ads accounts")
            
            # Mark which accounts are already connected
            connected_account_ids = []
            assets_statement = select(DigitalAsset).where(
                DigitalAsset.customer_id == customer_id,
                DigitalAsset.asset_type == AssetType.GOOGLE_ADS
            )
            connected_assets = session.exec(assets_statement).all()
            connected_account_ids = [asset.external_id for asset in connected_assets]
            
            # Add connected flag to each account
            for account in accounts:
                account['is_connected'] = account['customer_id'] in connected_account_ids
            
            return {
                "success": True,
                "accounts": accounts,
                "message": f"Found {len(accounts)} Google Ads accounts",
                "access_token": access_token,
                "refresh_token": refresh_token
            }
    
    except Exception as e:
        print(f"DEBUG: Error fetching available Google Ads accounts: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch available Google Ads accounts: {str(e)}"
        )