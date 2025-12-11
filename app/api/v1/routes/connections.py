"""
Connection Health API Endpoints

Provides endpoints for viewing connection health status and managing failed connections.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel
import logging
import os

from app.config.database import get_session
from app.models.analytics import Connection, DigitalAsset, AssetType
from app.api.dependencies import get_current_user
from app.utils.connection_failure_utils import (
    record_connection_success,
    should_retry_connection,
)
from app.core.oauth.token_refresh import refresh_tokens_for_platforms
from app.core.agents.mcp_clients.mcp_registry import MCPServer
from app.services.clickup_service import ClickUpService
from app.utils.security_utils import decrypt_token
from sqlmodel import select, and_
from fastapi import Header

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/connections", tags=["connections"])


# Internal auth dependency
async def verify_internal_token(
    x_internal_auth_token: str = Header(..., alias="X-Internal-Auth-Token"),
):
    """Verify internal auth token for Cloud Scheduler"""
    internal_token = os.getenv("INTERNAL_AUTH_TOKEN", "")
    if not internal_token:
        raise HTTPException(
            status_code=500, detail="Internal auth token not configured"
        )

    if x_internal_auth_token != internal_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
        )


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


class RefreshResult(BaseModel):
    """Result of individual connection refresh."""

    connection_id: int
    platform: str
    asset_name: str
    success: bool
    message: str
    invalidated: bool
    clickup_task_created: bool


class BulkRefreshResponse(BaseModel):
    """Response from bulk token refresh."""

    total_connections: int
    successful_refreshes: int
    failed_refreshes: int
    invalidated_connections: int
    clickup_tasks_created: int
    results: List[RefreshResult]  # List of individual refresh results


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
    customer_id: Optional[int] = None, current_user=Depends(get_current_user)
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
        customer_id = getattr(current_user, "primary_customer_id", None)
        if customer_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No customer_id provided and user has no primary customer",
            )

    with get_session() as session:
        # Get all connections for this campaigner and customer
        query = (
            select(Connection, DigitalAsset)
            .join(DigitalAsset)
            .where(
                and_(
                    Connection.campaigner_id == campaigner_id,
                    Connection.customer_id == customer_id,
                    Connection.revoked == False,
                    DigitalAsset.is_active == True,
                )
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
            connections.append(
                ConnectionHealthResponse(
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
                    should_retry=should_retry_connection(connection, max_failures=3),
                )
            )

        return ConnectionHealthSummary(
            total_connections=total,
            healthy_connections=healthy,
            failing_connections=failing,
            needs_reauth_connections=needs_reauth,
            connections=connections,
        )


@router.get("/{connection_id}/health", response_model=ConnectionHealthResponse)
async def get_connection_health(
    connection_id: int, current_user=Depends(get_current_user)
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
        query = (
            select(Connection, DigitalAsset)
            .join(DigitalAsset)
            .where(
                and_(
                    Connection.id == connection_id,
                    Connection.campaigner_id == campaigner_id,
                    Connection.revoked == False,
                )
            )
        )

        result = session.exec(query).first()

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Connection {connection_id} not found or access denied",
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
            should_retry=should_retry_connection(connection, max_failures=3),
        )


@router.get("/failing", response_model=List[ConnectionHealthResponse])
async def get_failing_connections_endpoint(
    customer_id: Optional[int] = None,
    min_failure_count: int = 1,
    current_user=Depends(get_current_user),
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
        customer_id = getattr(current_user, "primary_customer_id", None)

    with get_session() as session:
        # Get failing connections
        query = (
            select(Connection, DigitalAsset)
            .join(DigitalAsset)
            .where(
                and_(
                    Connection.campaigner_id == campaigner_id,
                    Connection.failure_count >= min_failure_count,
                    Connection.revoked == False,
                    DigitalAsset.is_active == True,
                )
            )
        )

        if customer_id:
            query = query.where(Connection.customer_id == customer_id)

        results = session.exec(query).all()

        failing_connections = []
        for connection, asset in results:
            failing_connections.append(
                ConnectionHealthResponse(
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
                    should_retry=should_retry_connection(connection, max_failures=3),
                )
            )

        return failing_connections


@router.post("/{connection_id}/retry", response_model=ConnectionRetryResponse)
async def retry_connection(
    connection_id: int,
    request: ConnectionRetryRequest,
    current_user=Depends(get_current_user),
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
                    Connection.revoked == False,
                )
            )
        ).first()

        if not connection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Connection {connection_id} not found or access denied",
            )

        # Check if retry is allowed
        if not request.force and not should_retry_connection(
            connection, max_failures=3
        ):
            return ConnectionRetryResponse(
                success=False,
                message=f"Connection has too many failures ({connection.failure_count}). Requires re-authentication.",
                connection_id=connection_id,
                new_failure_count=connection.failure_count,
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
        new_failure_count=connection.failure_count or 0,
    )


@router.post("/{connection_id}/mark-healthy")
async def mark_connection_healthy(
    connection_id: int, current_user=Depends(get_current_user)
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
                    Connection.revoked == False,
                )
            )
        ).first()

        if not connection:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Connection {connection_id} not found or access denied",
            )

    # Record success (this will clear failures)
    success = record_connection_success(connection_id, reset_failure_count=True)

    if success:
        return {
            "success": True,
            "message": f"Connection {connection_id} marked as healthy",
            "connection_id": connection_id,
        }
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update connection status",
        )


@router.get("/test-internal-auth")
async def test_internal_auth(_: None = Depends(verify_internal_token)):
    """Test endpoint to verify internal auth is working"""
    import os

    return {
        "message": "Internal auth working",
        "token": os.getenv("INTERNAL_AUTH_TOKEN", "NOT_SET"),
    }


@router.post("/refresh-all", response_model=BulkRefreshResponse)
async def refresh_all_tokens(_: None = Depends(verify_internal_token)):
    """
    Refresh all OAuth tokens for all active connections.

    This endpoint:
    1. Iterates through all active connections for all users
    2. Attempts to refresh tokens for each connection
    3. Invalidates connections that fail to refresh
    4. Creates ClickUp tasks for invalidated connections

    Returns:
        Summary of refresh results including success/failure counts
    """
    with get_session() as session:
        # Get all active connections for all users
        query = (
            select(Connection, DigitalAsset)
            .join(DigitalAsset)
            .where(and_(Connection.revoked == False, DigitalAsset.is_active == True))
        )

        results = session.exec(query).all()

        total_connections = len(results)
        successful_refreshes = 0
        failed_refreshes = 0
        invalidated_connections = 0
        clickup_tasks_created = 0
        refresh_results = []

        for connection, asset in results:
            try:
                # Determine platform and get current tokens
                platform = _get_platform_name(asset.asset_type)
                user_tokens = {}

                # Decrypt tokens for refresh
                if connection.refresh_token_enc:
                    try:
                        refresh_token = decrypt_token(connection.refresh_token_enc)
                        if platform in ["google_analytics", "google_ads"]:
                            user_tokens["refresh_token"] = refresh_token
                        elif platform == "facebook_ads":
                            user_tokens["access_token"] = (
                                decrypt_token(connection.access_token_enc)
                                if connection.access_token_enc
                                else None
                            )
                    except Exception as decrypt_error:
                        # Provide detailed error message for token decryption failures
                        error_type = type(decrypt_error).__name__
                        error_msg = str(decrypt_error) if str(decrypt_error) else error_type

                        # cryptography.fernet.InvalidToken has empty message, provide context
                        if error_type == "InvalidToken":
                            error_msg = "Invalid or corrupted token (possibly encrypted with different key)"
                        elif not error_msg:
                            error_msg = f"{error_type} exception occurred"

                        detailed_error = f"Token decryption failed for connection {connection.id}: {error_msg}"
                        logger.error(f"❌ {detailed_error}")

                        _invalidate_connection_and_create_clickup_task(
                            session,
                            connection,
                            asset,
                            detailed_error,
                        )
                        invalidated_connections += 1
                        clickup_tasks_created += 1
                        refresh_results.append(
                            RefreshResult(
                                connection_id=connection.id,
                                platform=platform,
                                asset_name=asset.name,
                                success=False,
                                message=detailed_error,
                                invalidated=True,
                                clickup_task_created=True,
                            )
                        )
                        continue

                # Attempt token refresh
                try:
                    # Map platform to MCP server for refresh function
                    platform_mapping = {
                        "google_analytics": [MCPServer.GOOGLE_ANALYTICS_OFFICIAL],
                        "google_ads": [MCPServer.GOOGLE_ADS_OFFICIAL],
                        "facebook_ads": [MCPServer.META_ADS],
                        "FACEBOOK_ADS": [
                            MCPServer.META_ADS
                        ],  # Handle enum string representation
                        "GA4": [MCPServer.GOOGLE_ANALYTICS_OFFICIAL],
                        "GOOGLE_ADS": [MCPServer.GOOGLE_ADS_OFFICIAL],
                    }

                    platforms_to_refresh = platform_mapping.get(platform, [])
                    if platforms_to_refresh:
                        # Prepare tokens in the format expected by refresh_tokens_for_platforms
                        refresh_input_tokens = {}
                        if (
                            platform in ["google_analytics", "GA4"]
                        ) and "refresh_token" in user_tokens:
                            refresh_input_tokens["google_analytics"] = user_tokens[
                                "refresh_token"
                            ]
                        elif (
                            platform in ["google_ads", "GOOGLE_ADS"]
                        ) and "refresh_token" in user_tokens:
                            refresh_input_tokens["google_ads"] = user_tokens[
                                "refresh_token"
                            ]
                        elif (
                            platform in ["facebook_ads", "FACEBOOK_ADS"]
                        ) and "access_token" in user_tokens:
                            refresh_input_tokens["facebook"] = user_tokens[
                                "access_token"
                            ]

                        if refresh_input_tokens:
                            refreshed_tokens = refresh_tokens_for_platforms(
                                connection.campaigner_id,
                                platforms_to_refresh,
                                refresh_input_tokens,
                            )

                            # Check if refresh was successful
                            # If the token key is still in refreshed_tokens, refresh succeeded
                            token_key = (
                                "google_analytics"
                                if platform == "google_analytics"
                                else "google_ads"
                                if platform == "google_ads"
                                else "facebook"
                            )
                            if token_key in refreshed_tokens:
                                successful_refreshes += 1
                                refresh_results.append(
                                    RefreshResult(
                                        connection_id=connection.id,
                                        platform=platform,
                                        asset_name=asset.name,
                                        success=True,
                                        message="Token refreshed successfully",
                                        invalidated=False,
                                        clickup_task_created=False,
                                    )
                                )
                            else:
                                # Refresh failed
                                _invalidate_connection_and_create_clickup_task(
                                    session, connection, asset, "Token refresh failed"
                                )
                                failed_refreshes += 1
                                invalidated_connections += 1
                                clickup_tasks_created += 1
                                refresh_results.append(
                                    RefreshResult(
                                        connection_id=connection.id,
                                        platform=platform,
                                        asset_name=asset.name,
                                        success=False,
                                        message="Token refresh failed",
                                        invalidated=True,
                                        clickup_task_created=True,
                                    )
                                )
                        else:
                            # No tokens available for refresh
                            successful_refreshes += 1
                            refresh_results.append(
                                RefreshResult(
                                    connection_id=connection.id,
                                    platform=platform,
                                    asset_name=asset.name,
                                    success=True,
                                    message="No tokens available for refresh",
                                    invalidated=False,
                                    clickup_task_created=False,
                                )
                            )
                    else:
                        # Unsupported platform
                        successful_refreshes += 1
                        refresh_results.append(
                            RefreshResult(
                                connection_id=connection.id,
                                platform=platform,
                                asset_name=asset.name,
                                success=True,
                                message="Platform not supported for refresh",
                                invalidated=False,
                                clickup_task_created=False,
                            )
                        )

                except Exception as refresh_error:
                    logger.error(
                        f"❌ Exception during token refresh for connection {connection.id}: {refresh_error}"
                    )
                    _invalidate_connection_and_create_clickup_task(
                        session,
                        connection,
                        asset,
                        f"Token refresh exception: {refresh_error}",
                    )
                    failed_refreshes += 1
                    invalidated_connections += 1
                    clickup_tasks_created += 1
                    refresh_results.append(
                        RefreshResult(
                            connection_id=connection.id,
                            platform=platform,
                            asset_name=asset.name,
                            success=False,
                            message=f"Token refresh exception: {refresh_error}",
                            invalidated=True,
                            clickup_task_created=True,
                        )
                    )

            except Exception as e:
                logger.error(
                    f"❌ Unexpected error processing connection {connection.id}: {e}"
                )
                failed_refreshes += 1
                refresh_results.append(
                    RefreshResult(
                        connection_id=connection.id,
                        platform=_get_platform_name(asset.asset_type),
                        asset_name=asset.name,
                        success=False,
                        message=f"Unexpected error: {e}",
                        invalidated=False,
                        clickup_task_created=False,
                    )
                )

        return BulkRefreshResponse(
            total_connections=total_connections,
            successful_refreshes=successful_refreshes,
            failed_refreshes=failed_refreshes,
            invalidated_connections=invalidated_connections,
            clickup_tasks_created=clickup_tasks_created,
            results=refresh_results,
        )


def _invalidate_connection_and_create_clickup_task(
    session, connection: Connection, asset: DigitalAsset, failure_reason: str
):
    """Invalidate a connection and create a ClickUp task for it."""
    try:
        # Mark connection as revoked and needing reauth
        connection.revoked = True
        connection.needs_reauth = True
        connection.failure_reason = failure_reason
        session.add(connection)
        session.commit()

        # Record connection failure
        record_connection_failure(
            connection.id, failure_reason, also_set_needs_reauth=False
        )

        # Create ClickUp task
        try:
            clickup_service = ClickUpService(session)
            task_result = clickup_service.create_task(
                task_name=f"Connection Invalidated: {asset.name} ({asset.provider})",
                description=f"""# Connection Invalidated

**Connection Details:**
- Asset: {asset.name}
- Provider: {asset.provider}
- Platform: {_get_platform_name(asset.asset_type)}
- Connection ID: {connection.id}

**Failure Reason:** {failure_reason}

**Action Required:**
1. Investigate the failure reason
2. Check API credentials and permissions
3. Re-establish the connection through the OAuth flow
4. Test the connection after re-establishing

**Timestamp:** {datetime.now().isoformat()}
""",
            )

            if task_result.get("id"):
                logger.info(
                    f"✅ Created ClickUp task for invalidated connection {connection.id}: {task_result.get('url')}"
                )
            else:
                logger.error(
                    f"❌ Failed to create ClickUp task for connection {connection.id}"
                )

        except Exception as clickup_error:
            logger.error(
                f"❌ Error creating ClickUp task for connection {connection.id}: {clickup_error}"
            )

    except Exception as e:
        logger.error(
            f"❌ Error invalidating connection {connection.id} and creating ClickUp task: {e}"
        )
