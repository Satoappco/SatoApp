"""
Google Ads data API routes
Handles Google Ads data fetching and analysis
"""

import os
from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

from app.core.auth import get_current_user
from app.models.users import User

router = APIRouter(prefix="/google-ads", tags=["Google Ads Data"])

# Initialize service lazily to avoid startup errors
def get_google_ads_service():
    from app.services.google_ads_service import GoogleAdsService
    return GoogleAdsService()


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


class GoogleAdsConnectionListResponse(BaseModel):
    connections: List[GoogleAdsConnectionResponse]


class CreateAdsConnectionRequest(BaseModel):
    customer_id: str
    customer_name: str
    currency_code: str
    time_zone: str
    access_token: str
    refresh_token: str
    expires_in: int = 3600


@router.post("/data", response_model=GoogleAdsDataResponse)
async def get_google_ads_data(
    request: GoogleAdsDataRequest,
    current_user: User = Depends(get_current_user)
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
    current_user: User = Depends(get_current_user)
):
    """
    Get all Google Ads connections for the current authenticated user
    """
    try:
        from app.config.database import get_session
        from app.models.analytics import Connection, DigitalAsset, AssetType
        from sqlmodel import select, and_
        
        with get_session() as session:
            # Get all Google Ads connections
            statement = select(Connection, DigitalAsset).join(
                DigitalAsset, Connection.digital_asset_id == DigitalAsset.id
            ).where(
                and_(
                    DigitalAsset.asset_type == AssetType.GOOGLE_ADS,
                    DigitalAsset.provider == "Google",
                    Connection.revoked == False,
                    Connection.user_id == current_user.id
                )
            )
            
            results = session.exec(statement).all()
            print(f"DEBUG: Found {len(results)} Google Ads connections")
            
            connections = []
            for connection, asset in results:
                print(f"DEBUG: Google Ads connection: {connection.id} - {asset.name}")
                connections.append(GoogleAdsConnectionResponse(
                    success=True,
                    message=f"Connected to {asset.name}",
                    connection_id=connection.id
                ))
            
            return GoogleAdsConnectionListResponse(connections=connections)
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get Google Ads connections: {str(e)}"
        )


@router.delete("/connections/{connection_id}")
async def revoke_google_ads_connection(
    connection_id: int,
    current_user: User = Depends(get_current_user)
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
                    Connection.user_id == current_user.id,
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
            
            # Mark connection as revoked
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
        from app.models.users import User
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
            user_statement = select(User).where(User.email == user_email)
            user = session.exec(user_statement).first()
            
            if not user:
                return {"success": False, "message": f"User {user_email} not found in database"}
            
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
                    subclient_id=1,  # Default subclient
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