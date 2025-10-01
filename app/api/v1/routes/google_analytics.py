"""
Google Analytics API routes for token management and data fetching
"""

from datetime import datetime
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, EmailStr
from sqlmodel import select

from app.core.auth import get_current_user
from app.models.users import User, SubCustomer
from app.models.analytics import DigitalAsset, Connection, AssetType
from app.services.google_analytics_service import GoogleAnalyticsService
from app.config.database import get_session

router = APIRouter(prefix="/google-analytics", tags=["google-analytics"])

# Initialize service
ga_service = GoogleAnalyticsService()


@router.get("/subclients")
async def get_user_subclients(
    current_user: User = Depends(get_current_user)
):
    """
    Get all subclients for current user's customer, with default subclient first
    """
    
    try:
        with get_session() as session:
            # Get user's customer ID
            customer_id = current_user.primary_customer_id
            
            # Get subclients for the user's customer, ordered by ID (default first)
            statement = select(SubCustomer).where(
                SubCustomer.customer_id == customer_id
            ).order_by(SubCustomer.id.asc())  # First subclient = default
            
            subclients = session.exec(statement).all()
            
            result = [
                {
                    "id": sc.id,
                    "name": sc.name,
                    "customer_id": sc.customer_id,
                    "subtype": sc.subtype,
                    "status": sc.status,
                    "is_default": idx == 0  # Mark first one as default
                }
                for idx, sc in enumerate(subclients)
            ]
            
            return {
                "subclients": result,
                "default_subclient_id": result[0]["id"] if result else None
            }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get subclients: {str(e)}"
        )


# Request/Response Models
class SaveGAConnectionRequest(BaseModel):
    """Request model for saving GA connection"""
    subclient_id: int
    access_token: str
    refresh_token: str
    expires_in: int
    account_email: EmailStr


class GAConnectionResponse(BaseModel):
    """Response model for GA connection"""
    connection_id: int
    digital_asset_id: int
    property_id: str
    property_name: str
    account_email: str
    expires_at: str
    scopes: List[str]


class GAConnectionListResponse(BaseModel):
    """Response model for GA connections list"""
    connections: List[Dict[str, Any]]


class GA4DataRequest(BaseModel):
    """Request model for fetching GA4 data"""
    connection_id: int
    property_id: str
    metrics: List[str]
    dimensions: Optional[List[str]] = None
    start_date: str = "7daysAgo"
    end_date: str = "today"
    limit: int = 1000


class GA4DataResponse(BaseModel):
    """Response model for GA4 data"""
    dimension_headers: List[str]
    metric_headers: List[str]
    rows: List[Dict[str, Any]]
    row_count: int
    totals: List[Dict[str, Any]]


@router.post("/connections", response_model=GAConnectionResponse)
async def save_ga_connection(
    request: SaveGAConnectionRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Save Google Analytics OAuth connection
    """
    
    try:
        result = await ga_service.save_ga_connection(
            user_id=current_user.id,  # Use real authenticated user ID
            subclient_id=request.subclient_id,
            access_token=request.access_token,
            refresh_token=request.refresh_token,
            expires_in=request.expires_in,
            account_email=request.account_email
        )
        
        return GAConnectionResponse(**result)
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save GA connection: {str(e)}"
        )


@router.get("/connections", response_model=GAConnectionListResponse)
async def get_ga_connections(
    subclient_id: int = Query(None, description="Filter connections by subclient ID"),
    current_user: User = Depends(get_current_user)
):
    """
    Get GA connections for the current authenticated user, optionally filtered by subclient
    """
    
    try:
        # Use real authenticated user ID and optional subclient filter
        connections = await ga_service.get_user_ga_connections(current_user.id, subclient_id)
        return GAConnectionListResponse(connections=connections)
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get GA connections: {str(e)}"
        )


@router.post("/connections/{connection_id}/refresh")
async def refresh_ga_token(
    connection_id: int,
    current_user: User = Depends(get_current_user)
):
    """
    Refresh GA access token - if refresh token is expired, returns re-auth URL
    """
    
    try:
        # Verify user owns this connection
        with get_session() as session:
            statement = select(Connection).where(
                Connection.id == connection_id,
                Connection.user_id == current_user.id
            )
            connection = session.exec(statement).first()
            
            if not connection:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Connection not found"
                )
        
        result = await ga_service.refresh_ga_token(connection_id)
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


@router.post("/connections/{connection_id}/reauth")
async def get_reauth_url(
    connection_id: int,
    current_user: User = Depends(get_current_user)
):
    """
    Get re-authorization URL for expired refresh tokens
    """
    
    try:
        # Verify user owns this connection
        with get_session() as session:
            statement = select(Connection).where(
                Connection.id == connection_id,
                Connection.user_id == current_user.id
            )
            connection = session.exec(statement).first()
            
            if not connection:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Connection not found"
                )
        
        reauth_url = ga_service.generate_reauth_url(connection_id, "satoappco@gmail.com")
        
        return {
            "success": True,
            "reauth_url": reauth_url,
            "message": "Please complete re-authorization to get fresh tokens"
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate re-auth URL: {str(e)}"
        )


@router.post("/connections/{connection_id}/update-tokens")
async def update_connection_tokens(
    connection_id: int,
    access_token: str = Query(..., description="New access token"),
    refresh_token: str = Query(..., description="New refresh token"),
    expires_in: int = Query(3600, description="Token expiry in seconds"),
    current_user: User = Depends(get_current_user)
):
    """
    Update connection with fresh OAuth tokens after re-authorization
    """
    
    try:
        # Verify user owns this connection
        with get_session() as session:
            statement = select(Connection).where(
                Connection.id == connection_id,
                Connection.user_id == current_user.id
            )
            connection = session.exec(statement).first()
            
            if not connection:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Connection not found"
                )
        
        # Update the connection with fresh tokens
        result = await ga_service.update_connection_tokens(
            connection_id=connection_id,
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=expires_in
        )
        
        return {
            "success": True,
            "connection_id": connection_id,
            "message": "Connection updated with fresh tokens",
            "expires_at": result.get("expires_at"),
            "rotated_at": result.get("rotated_at")
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update connection tokens: {str(e)}"
        )


@router.delete("/connections/{connection_id}")
async def revoke_ga_connection(
    connection_id: int,
    current_user: User = Depends(get_current_user)
):
    """
    Revoke GA connection
    """
    
    try:
        # Verify user owns this connection
        with get_session() as session:
            statement = select(Connection).where(
                Connection.id == connection_id,
                Connection.user_id == current_user.id
            )
            connection = session.exec(statement).first()
            
            if not connection:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Connection not found"
                )
        
        success = await ga_service.revoke_ga_connection(connection_id)
        
        if success:
            return {"message": "Connection revoked successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to revoke connection"
            )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to revoke connection: {str(e)}"
        )


@router.post("/data", response_model=GA4DataResponse)
async def fetch_ga4_data(
    request: GA4DataRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Fetch data from Google Analytics 4
    """
    
    try:
        # Verify user owns this connection
        with get_session() as session:
            statement = select(Connection).where(
                Connection.id == request.connection_id,
                Connection.user_id == current_user.id
            )
            connection = session.exec(statement).first()
            
            if not connection:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Connection not found"
                )
        
        result = await ga_service.fetch_ga4_data(
            connection_id=request.connection_id,
            property_id=request.property_id,
            metrics=request.metrics,
            dimensions=request.dimensions,
            start_date=request.start_date,
            end_date=request.end_date,
            limit=request.limit
        )
        
        return GA4DataResponse(**result)
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch GA4 data: {str(e)}"
        )


@router.get("/properties/{connection_id}")
async def get_ga_properties(
    connection_id: int,
    current_user: User = Depends(get_current_user)
):
    """
    Get GA properties accessible through this connection
    """
    
    try:
        # Verify user owns this connection
        with get_session() as session:
            statement = select(Connection, DigitalAsset).join(
                DigitalAsset, Connection.digital_asset_id == DigitalAsset.id
            ).where(
                Connection.id == connection_id,
                Connection.user_id == current_user.id
            )
            result = session.exec(statement).first()
            
            if not result:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Connection not found"
                )
            
            connection, digital_asset = result
            
            # Return property info
            return {
                "property_id": digital_asset.external_id,
                "property_name": digital_asset.name,
                "account_email": connection.account_email,
                "meta": digital_asset.meta
            }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get GA properties: {str(e)}"
        )


# Common GA4 metrics and dimensions for reference
@router.get("/metrics")
async def get_available_metrics():
    """
    Get list of available GA4 metrics
    """
    
    common_metrics = [
        "sessions",
        "users",
        "newUsers",
        "bounceRate",
        "sessionDuration",
        "pageviews",
        "screenPageViews",
        "conversions",
        "totalRevenue",
        "purchaseRevenue",
        "advertisingRevenue",
        "organicGoogleSearchSessions",
        "paidGoogleSearchSessions",
        "socialSessions",
        "emailSessions",
        "directSessions",
        "referralSessions"
    ]
    
    return {"metrics": common_metrics}


@router.get("/dimensions")
async def get_available_dimensions():
    """
    Get list of available GA4 dimensions
    """
    
    common_dimensions = [
        "date",
        "country",
        "city",
        "region",
        "deviceCategory",
        "operatingSystem",
        "browser",
        "channelGroup",
        "source",
        "medium",
        "campaign",
        "landingPage",
        "pagePath",
        "pageTitle",
        "eventName",
        "customEvent:event_category",
        "customEvent:event_label"
    ]
    
    return {"dimensions": common_dimensions}
