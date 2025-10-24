"""
Google Analytics API routes for token management and data fetching
"""

from datetime import datetime
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, EmailStr
from sqlmodel import select

from app.core.auth import get_current_user
from app.models.users import Campaigner, Customer
from app.models.analytics import DigitalAsset, Connection, AssetType
from app.services.google_analytics_service import GoogleAnalyticsService
from app.config.database import get_session

router = APIRouter(prefix="/google-analytics", tags=["google-analytics"])

# Initialize service
ga_service = GoogleAnalyticsService()


# Request/Response Models
class SaveGAConnectionRequest(BaseModel):
    """Request model for saving GA connection"""
    customer_id: int
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
    current_user: Campaigner = Depends(get_current_user)
):
    """
    Save Google Analytics OAuth connection
    """
    
    try:
        result = await ga_service.save_ga_connection(
            campaigner_id=current_user.id,  # Use real authenticated campaigner ID
            customer_id=request.customer_id,
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
    customer_id: int = Query(None, description="Filter connections by customer ID"),
    current_user: Campaigner = Depends(get_current_user)
):
    """
    Get GA connections for the current authenticated campaigner, optionally filtered by customer
    """
    
    try:
        # Use real authenticated campaigner ID and optional customer filter
        connections = await ga_service.get_user_ga_connections(current_user.id, customer_id)
        return GAConnectionListResponse(connections=connections)
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get GA connections: {str(e)}"
        )


@router.post("/connections/{connection_id}/refresh")
async def refresh_ga_token(
    connection_id: int,
    current_user: Campaigner = Depends(get_current_user)
):
    """
    Refresh GA access token - if refresh token is expired, returns re-auth URL
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
    current_user: Campaigner = Depends(get_current_user)
):
    """
    Get re-authorization URL for expired refresh tokens
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
    current_user: Campaigner = Depends(get_current_user)
):
    """
    Update connection with fresh OAuth tokens after re-authorization
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
    current_user: Campaigner = Depends(get_current_user)
):
    """
    Revoke GA connection
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
    current_user: Campaigner = Depends(get_current_user)
):
    """
    Fetch data from Google Analytics 4
    """
    
    try:
        # Verify campaigner owns this connection
        with get_session() as session:
            statement = select(Connection).where(
                Connection.id == request.connection_id,
                Connection.campaigner_id == current_user.id
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
    current_user: Campaigner = Depends(get_current_user)
):
    """
    Get GA properties accessible through this connection
    """
    
    try:
        # Verify campaigner owns this connection
        with get_session() as session:
            statement = select(Connection, DigitalAsset).join(
                DigitalAsset, Connection.digital_asset_id == DigitalAsset.id
            ).where(
                Connection.id == connection_id,
                Connection.campaigner_id == current_user.id
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


@router.get("/available-properties/{customer_id}")
async def get_available_ga_properties(
    customer_id: int,
    current_user: Campaigner = Depends(get_current_user)
):
    """
    Get ALL available GA properties from Google using an existing connection's tokens.
    This allows users to see all their GA properties even if not all are connected.
    """
    
    try:
        with get_session() as session:
            # Find any active GA connection for this campaigner and customer
            statement = select(Connection, DigitalAsset).join(
                DigitalAsset, Connection.digital_asset_id == DigitalAsset.id
            ).where(
                Connection.campaigner_id == current_user.id,
                DigitalAsset.customer_id == customer_id,
                DigitalAsset.asset_type == AssetType.GA4,
                Connection.revoked == False
            ).limit(1)
            
            result = session.exec(statement).first()
            
            if not result:
                return {
                    "success": False,
                    "message": "No Google Analytics connection found. Please connect to Google Analytics first.",
                    "properties": []
                }
            
            connection, digital_asset = result
            
            # Check if token needs refresh (with 5-minute buffer)
            from datetime import timedelta
            buffer_time = timedelta(minutes=5)
            if connection.expires_at and connection.expires_at < datetime.utcnow() + buffer_time:
                print(f"🔄 Google Analytics token expired or expiring soon, refreshing...")
                try:
                    # Refresh the token
                    refresh_result = await ga_service.refresh_ga_token(connection.id)
                    if not refresh_result.get("success"):
                        print(f"❌ Failed to refresh Google Analytics token")
                        return {
                            "success": False,
                            "message": "Token expired. Please reconnect to Google Analytics.",
                            "properties": []
                        }
                    print(f"✅ Successfully refreshed Google Analytics token")
                    # Reload connection with new token
                    session.refresh(connection)
                except ValueError as e:
                    # Token refresh failed - campaigner needs to re-authenticate
                    error_message = str(e)
                    print(f"❌ Token refresh failed: {error_message}")
                    
                    # Check if the error message contains a re-auth URL
                    if "Please re-authorize your Google Analytics connection:" in error_message:
                        # Extract the re-auth URL from the error message
                        import re
                        url_match = re.search(r'https://[^\s]+', error_message)
                        reauth_url = url_match.group(0) if url_match else None
                        
                        return {
                            "success": False,
                            "message": "Your Google Analytics token has expired. Please reconnect your account.",
                            "properties": [],
                            "requires_reauth": True,
                            "reauth_url": reauth_url
                        }
                    
                    return {
                        "success": False,
                        "message": "Token expired. Please reconnect to Google Analytics.",
                        "properties": [],
                        "requires_reauth": True
                    }
                except Exception as e:
                    print(f"❌ Unexpected error during token refresh: {str(e)}")
                    return {
                        "success": False,
                        "message": "Token expired. Please reconnect to Google Analytics.",
                        "properties": []
                    }
            
            # Decrypt access token
            access_token = ga_service._decrypt_token(connection.access_token_enc)
            
            # Fetch all available properties from Google Analytics
            from google.oauth2.credentials import Credentials
            from google.analytics.admin import AnalyticsAdminServiceClient
            from google.analytics.admin_v1alpha.types import ListPropertiesRequest
            
            credentials = Credentials(token=access_token)
            client = AnalyticsAdminServiceClient(credentials=credentials)
            
            properties = []
            
            print(f"DEBUG: Fetching all available GA4 properties for user {current_user.id}")
            
            # List all accounts
            accounts = client.list_accounts()
            for account in accounts:
                print(f"DEBUG: Found GA account: {account.display_name}")
                # List properties for each account
                request = ListPropertiesRequest(filter=f"parent:{account.name}")
                account_properties = client.list_properties(request=request)
                for property_obj in account_properties:
                    property_id = property_obj.name.split('/')[-1]
                    properties.append({
                        'property_id': property_id,
                        'property_name': property_obj.display_name,
                        'account_id': account.name.split('/')[-1],
                        'account_name': account.display_name,
                        'display_name': property_obj.display_name
                    })
                    print(f"DEBUG: Found GA property: {property_obj.display_name} (ID: {property_id})")
            
            print(f"DEBUG: Found {len(properties)} total GA4 properties")
            
            # Mark which properties are already connected
            connected_property_ids = []
            assets_statement = select(DigitalAsset).where(
                DigitalAsset.customer_id == customer_id,
                DigitalAsset.asset_type == AssetType.GA4
            )
            connected_assets = session.exec(assets_statement).all()
            connected_property_ids = [asset.external_id for asset in connected_assets]
            
            # Add connected flag to each property
            for prop in properties:
                prop['is_connected'] = prop['property_id'] in connected_property_ids
            
            return {
                "success": True,
                "properties": properties,
                "message": f"Found {len(properties)} Google Analytics properties",
                "access_token": access_token,  # Include for creating new connections
                "refresh_token": ga_service._decrypt_token(connection.refresh_token_enc) if connection.refresh_token_enc else None
            }
    
    except Exception as e:
        print(f"DEBUG: Error fetching available GA properties: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch available GA properties: {str(e)}"
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
        "newCampaigners",
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
