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
from app.models.users import User

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
    subclient_id: int = Query(None, description="Filter connections by subclient ID"),
    current_user: User = Depends(get_current_user)
):
    """
    Get Facebook connections for the current authenticated user, optionally filtered by subclient
    """
    
    try:
        with get_session() as session:
            # Build query conditions
            conditions = [
                Connection.user_id == current_user.id,  # Real authenticated user ID
                DigitalAsset.provider == "Facebook",
                Connection.revoked == False
            ]
            
            # Add subclient filter if provided
            if subclient_id is not None:
                conditions.append(DigitalAsset.subclient_id == subclient_id)
            
            # Get Facebook connections for the current user
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
    current_user: User = Depends(get_current_user)
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
                    Connection.user_id == 5  # Demo user ID
                )
            )
            connection = session.exec(statement).first()
            
            if not connection:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Connection not found"
                )
            
            # Revoke connection
            connection.revoked = True
            session.add(connection)
            session.commit()
            
            return {"message": "Facebook connection revoked successfully"}
    
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
    current_user: User = Depends(get_current_user)
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
    current_user: User = Depends(get_current_user)
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
    current_user: User = Depends(get_current_user)
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

