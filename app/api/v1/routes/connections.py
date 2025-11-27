"""
Connection Health API Endpoints

Provides endpoints for viewing connection health status and managing failed connections.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel

from app.config.database import get_session
from app.models.analytics import Connection, DigitalAsset, AssetType
from app.api.dependencies import get_current_user
from app.utils.connection_failure_utils import (
    record_connection_success,
    should_retry_connection
)
from sqlmodel import select, and_

router = APIRouter(prefix="/connections", tags=["connections"])


# Response Models
class ConnectionHealthResponse(BaseModel):
    """Connection health status response."""
    id: int
    platform: str
    asset_type: str
    asset_name: str
    status: str  # "healthy", "failing", "needs_reauth"
    last_validated_at: Optional[datetime]
    last_failure_at: Optional[datetime]
    failure_count: int
    failure_reason: Optional[str]
    expires_at: Optional[datetime]
    needs_reauth: bool
    should_retry: bool

    class Config:
        from_attributes = True


class ConnectionHealthSummary(BaseModel):
    """Summary of all connections for a user."""
    total_connections: int
    healthy_connections: int
    failing_connections: int
    needs_reauth_connections: int
    connections: List[ConnectionHealthResponse]


class ConnectionRetryRequest(BaseModel):
    """Request to retry a failed connection."""
    force: bool = False  # Force retry even if max failures reached


class ConnectionRetryResponse(BaseModel):
    """Response from retry attempt."""
    success: bool
    message: str
    connection_id: int
    new_failure_count: int


# Helper Functions
def _get_connection_status(connection: Connection) -> str:
    """Determine connection status based on failure state."""
    if connection.needs_reauth:
        return "needs_reauth"
    elif connection.failure_count > 0:
        return "failing"
    else:
        return "healthy"


def _get_platform_name(asset_type: AssetType) -> str:
    """Get friendly platform name from asset type."""
    mapping = {
        AssetType.GA4: "google_analytics",
        AssetType.GOOGLE_ADS: "google_ads",
        AssetType.GOOGLE_ADS_CAPS: "google_ads",
        AssetType.FACEBOOK_ADS: "facebook_ads",
        AssetType.FACEBOOK_ADS_CAPS: "facebook_ads",
        AssetType.SOCIAL_MEDIA: "facebook_page",
        AssetType.ADVERTISING: "facebook_ads",
    }
    return mapping.get(asset_type, str(asset_type.value))


# Endpoints
@router.get("/health", response_model=ConnectionHealthSummary)
async def get_connections_health(
    customer_id: Optional[int] = None,
    current_user = Depends(get_current_user)
):
    """
    Get health status for all connections.

    Returns detailed health information for each connection including:
    - Connection status (healthy, failing, needs_reauth)
    - Failure count and reason
    - Last validation and failure timestamps
    - Token expiration
    - Whether retry is recommended

    Args:
        customer_id: Optional customer ID to filter by (defaults to user's primary customer)

    Returns:
        Summary of connection health with details for each connection
    """
    campaigner_id = current_user.id

    # Use customer_id from query or user's primary customer
    if customer_id is None:
        customer_id = getattr(current_user, 'primary_customer_id', None)
        if customer_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No customer_id provided and user has no primary customer"
            )

    with get_session() as session:
        # Get all connections for this campaigner and customer
        query = select(Connection, DigitalAsset).join(DigitalAsset).where(
            and_(
                Connection.campaigner_id == campaigner_id,
                Connection.customer_id == customer_id,
                Connection.revoked == False,
                DigitalAsset.is_active == True
            )
        )

        results = session.exec(query).all()

        connections = []
        total = 0
        healthy = 0
        failing = 0
        needs_reauth = 0

        for connection, asset in results:
            total += 1

            # Determine status
            conn_status = _get_connection_status(connection)
            if conn_status == "healthy":
                healthy += 1
            elif conn_status == "failing":
                failing += 1
            elif conn_status == "needs_reauth":
                needs_reauth += 1

            # Build response
            connections.append(ConnectionHealthResponse(
                id=connection.id,
                platform=_get_platform_name(asset.asset_type),
                asset_type=asset.asset_type.value,
                asset_name=asset.name,
                status=conn_status,
                last_validated_at=connection.last_validated_at,
                last_failure_at=connection.last_failure_at,
                failure_count=connection.failure_count or 0,
                failure_reason=connection.failure_reason,
                expires_at=connection.expires_at,
                needs_reauth=connection.needs_reauth,
                should_retry=should_retry_connection(connection, max_failures=3)
            ))

        return ConnectionHealthSummary(
            total_connections=total,
            healthy_connections=healthy,
            failing_connections=failing,
            needs_reauth_connections=needs_reauth,
            connections=connections
        )


@router.get("/{connection_id}/health", response_model=ConnectionHealthResponse)
async def get_connection_health(
    connection_id: int,
    current_user = Depends(get_current_user)
):
    """
    Get health status for a specific connection.

    Args:
        connection_id: ID of the connection

    Returns:
        Detailed health information for the connection
    """
    campaigner_id = current_user.id

    with get_session() as session:
        # Get connection with asset info
        query = select(Connection, DigitalAsset).join(DigitalAsset).where(
            and_(
                Connection.id == connection_id,
                Connection.campaigner_id == campaigner_id,
                Connection.revoked == False
            )
        )

        result = session.exec(query).first()

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Connection {connection_id} not found or access denied"
            )

        connection, asset = result

        return ConnectionHealthResponse(
            id=connection.id,
            platform=_get_platform_name(asset.asset_type),
            asset_type=asset.asset_type.value,
            asset_name=asset.name,
            status=_get_connection_status(connection),
            last_validated_at=connection.last_validated_at,
            last_failure_at=connection.last_failure_at,
            failure_count=connection.failure_count or 0,
            failure_reason=connection.failure_reason,
            expires_at=connection.expires_at,
            needs_reauth=connection.needs_reauth,
            should_retry=should_retry_connection(connection, max_failures=3)
        )


@router.get("/failing", response_model=List[ConnectionHealthResponse])
async def get_failing_connections_endpoint(
    customer_id: Optional[int] = None,
    min_failure_count: int = 1,
    current_user = Depends(get_current_user)
):
    """
    Get all failing connections for the current user.

    Args:
        customer_id: Optional customer ID to filter by
        min_failure_count: Minimum failure count to consider (default: 1)

    Returns:
        List of failing connections with health details
    """
    campaigner_id = current_user.id

    if customer_id is None:
        customer_id = getattr(current_user, 'primary_customer_id', None)

    with get_session() as session:
        # Get failing connections
        query = select(Connection, DigitalAsset).join(DigitalAsset).where(
            and_(
                Connection.campaigner_id == campaigner_id,
                Connection.failure_count >= min_failure_count,
                Connection.revoked == False,
                DigitalAsset.is_active == True
            )
        )

        if customer_id:
            query = query.where(Connection.customer_id == customer_id)

        results = session.exec(query).all()

        failing_connections = []
        for connection, asset in results:
            failing_connections.append(ConnectionHealthResponse(
                id=connection.id,
                platform=_get_platform_name(asset.asset_type),
                asset_type=asset.asset_type.value,
                asset_name=asset.name,
                status=_get_connection_status(connection),
                last_validated_at=connection.last_validated_at,
                last_failure_at=connection.last_failure_at,
                failure_count=connection.failure_count or 0,
                failure_reason=connection.failure_reason,
                expires_at=connection.expires_at,
                needs_reauth=connection.needs_reauth,
                should_retry=should_retry_connection(connection, max_failures=3)
            ))

        return failing_connections


@router.post("/{connection_id}/retry", response_model=ConnectionRetryResponse)
async def retry_connection(
    connection_id: int,
    request: ConnectionRetryRequest,
    current_user = Depends(get_current_user)
):
    """
    Retry a failed connection by triggering token refresh.

    This endpoint:
    1. Checks if retry is allowed based on failure count
    2. Triggers token refresh for the connection
    3. Updates failure status accordingly

    Args:
        connection_id: ID of the connection to retry
        request: Retry request with optional force flag

    Returns:
        Result of the retry attempt
    """
    campaigner_id = current_user.id

    with get_session() as session:
        # Get connection
        connection = session.exec(
            select(Connection).where(
                and_(
                    Connection.id == connection_id,
                    Connection.campaigner_id == campaigner_id,
                    Connection.revoked == False
                )
            )
        ).first()

        if not connection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Connection {connection_id} not found or access denied"
            )

        # Check if retry is allowed
        if not request.force and not should_retry_connection(connection, max_failures=3):
            return ConnectionRetryResponse(
                success=False,
                message=f"Connection has too many failures ({connection.failure_count}). Requires re-authentication.",
                connection_id=connection_id,
                new_failure_count=connection.failure_count
            )

    # TODO: Trigger actual token refresh
    # For now, this is a placeholder that simulates retry
    # In production, this would call:
    # - refresh_tokens_for_platforms() for token refresh
    # - Or trigger a background job to refresh and validate

    # Placeholder response
    return ConnectionRetryResponse(
        success=False,
        message="Connection retry is not yet implemented. Please reconnect manually.",
        connection_id=connection_id,
        new_failure_count=connection.failure_count or 0
    )


@router.post("/{connection_id}/mark-healthy")
async def mark_connection_healthy(
    connection_id: int,
    current_user = Depends(get_current_user)
):
    """
    Manually mark a connection as healthy (admin/debugging endpoint).

    This clears all failure tracking and resets the connection to healthy state.

    Args:
        connection_id: ID of the connection

    Returns:
        Success message
    """
    campaigner_id = current_user.id

    with get_session() as session:
        connection = session.exec(
            select(Connection).where(
                and_(
                    Connection.id == connection_id,
                    Connection.campaigner_id == campaigner_id,
                    Connection.revoked == False
                )
            )
        ).first()

        if not connection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Connection {connection_id} not found or access denied"
            )

    # Record success (this will clear failures)
    success = record_connection_success(connection_id, reset_failure_count=True)

    if success:
        return {
            "success": True,
            "message": f"Connection {connection_id} marked as healthy",
            "connection_id": connection_id
        }
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update connection status"
        )
