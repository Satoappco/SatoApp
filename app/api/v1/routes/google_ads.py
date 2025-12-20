"""
Google Ads data API routes
Handles Google Ads data fetching and analysis
"""

import os
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, status, Depends, Query
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from sqlmodel import select

from app.core.auth import get_current_user
from app.core.rbac import user_can_access_customer
from app.models.users import Campaigner
from app.models.analytics import DigitalPlatform, Connection, AssetType
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
    request: GoogleAdsDataRequest, current_user: Campaigner = Depends(get_current_user)
):
    """
    Fetch Google Ads data for analysis
    """

    # Validate connection ownership and customer access
    with get_session() as session:
        connection = session.get(Connection, request.connection_id)
        if not connection or connection.campaigner_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found"
            )

        # Validate customer access
        if not user_can_access_customer(current_user, connection.customer_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this customer",
            )

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
            limit=request.limit,
        )

        if result.get("success"):
            return GoogleAdsDataResponse(
                success=True,
                data=result.get("data", []),
                total_rows=result.get("total_rows", 0),
                metrics=request.metrics,
                dimensions=request.dimensions,
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("error", "Failed to fetch data"),
            )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch Google Ads data: {str(e)}",
        )


@router.get("/connections", response_model=GoogleAdsConnectionListResponse)
async def get_google_ads_connections(
    customer_id: int = Query(None, description="Filter connections by customer ID"),
    current_user: Campaigner = Depends(get_current_user),
):
    """
    Get Google Ads connections for the current authenticated user, optionally filtered by customer
    """

    # Validate customer access if customer_id is provided
    if customer_id is not None and not user_can_access_customer(
        current_user, customer_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this customer",
        )

    try:
        from app.config.database import get_session
        from app.models.analytics import DigitalPlatform, AssetType
        from sqlmodel import select, and_

        with get_session() as session:
            # Build query conditions - now with direct customer relationship
            conditions = [
                DigitalPlatform.asset_type == AssetType.GOOGLE_ADS,
                DigitalPlatform.provider == "Google",
                Connection.revoked == False,
                Connection.campaigner_id == current_user.id,
            ]

            # Add customer filter if provided - now direct on connections table
            if customer_id is not None:
                conditions.append(Connection.customer_id == customer_id)

            # Get Google Ads connections
            statement = (
                select(Connection, DigitalPlatform)
                .join(DigitalPlatform, Connection.digital_platform_id == DigitalPlatform.id)
                .where(and_(*conditions))
            )

            results = session.exec(statement).all()
            print(f"DEBUG: Found {len(results)} Google Ads connections")

            connections = []
            for connection, asset in results:
                print(
                    f"DEBUG: Google Ads connection: {connection.id} - {asset.name} - Active: {asset.is_active}"
                )

                # Compute token status using backend logic
                is_outdated = (
                    google_ads_service.is_token_expired(connection.expires_at)
                    if connection.expires_at
                    else True
                )

                # Helper to format datetime with timezone
                def format_datetime(dt):
                    if not dt:
                        return None
                    # If timezone-naive, assume UTC and add Z
                    if dt.tzinfo is None:
                        return dt.isoformat() + "Z"
                    return dt.isoformat()

                connections.append(
                    GoogleAdsConnectionResponse(
                        success=True,
                        message=f"Connected to {asset.name}",
                        connection_id=connection.id,
                        customer_id=asset.external_id,
                        customer_name=asset.name,
                        account_email=connection.account_email,
                        is_active=asset.is_active,
                        expires_at=format_datetime(connection.expires_at),
                        last_used_at=format_datetime(connection.last_used_at),
                        is_outdated=is_outdated,
                    )
                )

            return GoogleAdsConnectionListResponse(connections=connections)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get Google Ads connections: {str(e)}",
        )


@router.post("/connections/{connection_id}/refresh")
async def refresh_google_ads_token(
    connection_id: int, current_user: Campaigner = Depends(get_current_user)
):
    """
    Refresh Google Ads access token - if refresh token is expired, returns re-auth URL
    """

    try:
        # Verify campaigner owns this connection
        with get_session() as session:
            statement = select(Connection).where(
                Connection.id == connection_id,
                Connection.campaigner_id == current_user.id,
            )
            connection = session.exec(statement).first()

            if not connection:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found"
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
                "message": "Refresh token expired. Please re-authorize to get fresh tokens.",
            }
        # Return a consistent JSON error payload for other failures
        return {"success": False, "error": error_msg}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to refresh token: {str(e)}",
        )


@router.get("/connections/{connection_id}")
async def get_google_ads_connection(
    connection_id: int,
    include_refresh_token: bool = Query(
        False, description="Include decrypted refresh token (dev-only)"
    ),
    current_user: Campaigner = Depends(get_current_user),
):
    """
    Get a single Google Ads connection by ID (includes access token for debugging)
    """
    try:
        from app.config.database import get_session
        from app.models.analytics import DigitalPlatform, AssetType
        from sqlmodel import select, and_

        with get_session() as session:
            # Verify user owns this connection
            statement = (
                select(Connection, DigitalPlatform)
                .join(DigitalPlatform, Connection.digital_platform_id == DigitalPlatform.id)
                .where(
                    and_(
                        Connection.id == connection_id,
                        Connection.campaigner_id == current_user.id,
                        DigitalPlatform.asset_type == AssetType.GOOGLE_ADS,
                        DigitalPlatform.provider == "Google",
                    )
                )
            )

            result = session.exec(statement).first()
            if not result:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found"
                )

            connection, asset = result

            # Decrypt access token for display
            access_token = google_ads_service._decrypt_token(
                connection.access_token_enc
            )
            refresh_token = None
            if include_refresh_token:
                # Dev-only safety: only expose in non-production
                env = os.getenv("ENVIRONMENT", "development").lower()
                if env != "production":
                    if connection.refresh_token_enc:
                        try:
                            refresh_token = google_ads_service._decrypt_token(
                                connection.refresh_token_enc
                            )
                        except Exception:
                            refresh_token = None

            # Compute token status
            is_outdated = (
                google_ads_service.is_token_expired(connection.expires_at)
                if connection.expires_at
                else True
            )

            # Helper to format datetime with timezone
            def format_datetime(dt):
                if not dt:
                    return None
                # If timezone-naive, assume UTC and add Z
                if dt.tzinfo is None:
                    return dt.isoformat() + "Z"
                return dt.isoformat()

            response = {
                "connection_id": connection.id,
                "customer_id": asset.external_id,
                "customer_name": asset.name,
                "account_email": connection.account_email,
                "is_active": asset.is_active,
                "expires_at": format_datetime(connection.expires_at),
                "last_used_at": format_datetime(connection.last_used_at),
                "is_outdated": is_outdated,
                "access_token": access_token,
            }
            if include_refresh_token and refresh_token is not None:
                response["refresh_token"] = refresh_token
            return response

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get connection: {str(e)}",
        )


@router.delete("/connections/{connection_id}")
async def revoke_google_ads_connection(
    connection_id: int, current_user: Campaigner = Depends(get_current_user)
):
    """
    Revoke Google Ads connection
    """

    try:
        from app.config.database import get_session
        from app.models.analytics import DigitalPlatform, AssetType
        from sqlmodel import select, and_

        with get_session() as session:
            # Verify user owns this connection
            statement = (
                select(Connection, DigitalPlatform)
                .join(DigitalPlatform, Connection.digital_platform_id == DigitalPlatform.id)
                .where(
                    and_(
                        Connection.id == connection_id,
                        Connection.campaigner_id == current_user.id,
                        DigitalPlatform.asset_type == AssetType.GOOGLE_ADS,
                        DigitalPlatform.provider == "Google",
                    )
                )
            )

            result = session.exec(statement).first()
            if not result:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found"
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
                    params={"token": access_token},
                    headers={"content-type": "application/x-www-form-urlencoded"},
                )

                if response.status_code == 200:
                    print(
                        f"Successfully revoked Google Ads token with Google for connection {connection_id}"
                    )
                else:
                    print(
                        f"Warning: Google revocation returned status {response.status_code} for connection {connection_id}"
                    )

            except Exception as e:
                print(
                    f"Error revoking token with Google for connection {connection_id}: {str(e)}"
                )
                # Continue anyway to delete from our DB

            # Store the digital asset ID before deleting the connection
            digital_platform_id = connection.digital_platform_id

            # Delete the connection from our database
            session.delete(connection)
            session.commit()

            # Check if the digital asset should be deleted (no remaining connections)
            from app.services.digital_platform_service import delete_orphaned_digital_platform

            asset_deleted = delete_orphaned_digital_platform(session, digital_platform_id)

            message = "Google Ads connection deleted successfully"
            if asset_deleted:
                message += (
                    " and associated digital asset was removed (no other connections)"
                )

            return {"message": message}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to revoke Google Ads connection: {str(e)}",
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
            client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
        )

        # Get user info
        import requests

        user_info_response = requests.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {request.access_token}"},
        )

        if user_info_response.status_code != 200:
            return {"success": False, "message": "Could not get user info from token"}

        user_info = user_info_response.json()
        user_email = user_info.get("email")

        if not user_email:
            return {"success": False, "message": "Could not get user email from token"}

        # Find user in database
        with get_session() as session:
            user_statement = select(Campaigner).where(Campaigner.email == user_email)
            user = session.exec(user_statement).first()

            if not user:
                return {
                    "success": False,
                    "message": f"Campaigner {user_email} not found in database",
                }

            print(
                f"DEBUG: Creating Google Ads connection for user {user.id} ({user.email})"
            )

            # Create Google Ads connection using the service
            ga_service = GoogleAnalyticsService()

            # Create a Google Ads connection with the selected account details
            from app.config.database import get_session
            from app.models.analytics import (
                DigitalPlatform,
                Connection,
                AssetType,
                AuthType,
            )
            from datetime import datetime, timedelta

            with get_session() as session:
                # Create digital asset for Google Ads account
                digital_platform = DigitalPlatform(
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
                        "created_via": "oauth_flow",
                    },
                    is_active=True,
                )
                session.add(digital_platform)
                session.commit()
                session.refresh(digital_platform)

                # Encrypt tokens
                access_token_enc = ga_service._encrypt_token(request.access_token)
                refresh_token_enc = ga_service._encrypt_token(request.refresh_token)

                # Calculate expiry time
                expires_at = datetime.now(timezone.utc) + timedelta(
                    seconds=request.expires_in
                )

                # Create connection
                connection = Connection(
                    user_id=user.id,
                    digital_platform_id=digital_platform.id,
                    auth_type=AuthType.OAUTH2,
                    access_token_enc=access_token_enc,
                    refresh_token_enc=refresh_token_enc,
                    expires_at=expires_at,
                    is_active=True,
                    revoked=False,
                    last_used_at=datetime.now(timezone.utc),
                )
                session.add(connection)
                session.commit()
                session.refresh(connection)

                print(
                    f"DEBUG: Google Ads connection created successfully: {connection.id}"
                )

                # Sync metrics for the new digital asset
                # Note: sync_metrics_new will automatically detect this is a new asset and sync all 90 days
                try:
                    from app.services.campaign_sync_service import CampaignSyncService

                    print(f"🔄 Starting metrics sync for new Google Ads connection...")
                    sync_service = CampaignSyncService()
                    sync_result = sync_service.sync_metrics_new(
                        customer_id=request.customer_id
                    )
                    if sync_result.get("success"):
                        print(
                            f"✅ Metrics sync completed: {sync_result.get('metrics_upserted', 0)} metrics synced"
                        )
                    else:
                        print(
                            f"⚠️ Metrics sync completed with errors: {sync_result.get('error_details', [])}"
                        )
                except Exception as sync_error:
                    print(f"⚠️ Failed to sync metrics for new connection: {sync_error}")
                    # Don't fail the connection creation if metrics sync fails

                return {
                    "success": True,
                    "message": f"Successfully connected to {request.customer_name}",
                    "connection_id": connection.id,
                    "customer_id": request.customer_id,
                    "customer_name": request.customer_name,
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
            "metrics.value_per_all_conversions",
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
            "segments.click_type",
        ],
    }


@router.get("/available-accounts/{customer_id}")
async def get_available_google_ads_accounts(
    customer_id: int, current_user: Campaigner = Depends(get_current_user)
):
    """
    Get ALL available Google Ads accounts from Google using an existing connection's tokens.
    This allows users to see all their Google Ads accounts even if not all are connected.
    """

    try:
        with get_session() as session:
            # Find any active Google Ads connection for this user and subclient
            statement = (
                select(Connection, DigitalPlatform)
                .join(DigitalPlatform, Connection.digital_platform_id == DigitalPlatform.id)
                .where(
                    Connection.campaigner_id == current_user.id,
                    DigitalPlatform.customer_id == customer_id,
                    DigitalPlatform.asset_type == AssetType.GOOGLE_ADS,
                    Connection.revoked == False,
                )
                .limit(1)
            )

            result = session.exec(statement).first()

            if not result:
                return {
                    "success": False,
                    "message": "No Google Ads connection found. Please connect to Google Ads first.",
                    "accounts": [],
                }

            connection, digital_platform = result

            # Check if token needs refresh (with 5-minute buffer)
            from datetime import timedelta

            buffer_time = timedelta(minutes=5)
            if (
                connection.expires_at
                and connection.expires_at < datetime.now(timezone.utc) + buffer_time
            ):
                print(f"🔄 Google Ads token expired or expiring soon, refreshing...")
                # Refresh the token
                refresh_result = await google_ads_service.refresh_google_ads_token(
                    connection.id
                )
                if not refresh_result.get("success"):
                    print(f"❌ Failed to refresh Google Ads token")
                    return {
                        "success": False,
                        "message": "Token expired. Please reconnect to Google Ads.",
                        "accounts": [],
                    }
                print(f"✅ Successfully refreshed Google Ads token")
                # Reload connection with new token
                session.refresh(connection)

            # Decrypt access token
            access_token = google_ads_service._decrypt_token(
                connection.access_token_enc
            )
            refresh_token = (
                google_ads_service._decrypt_token(connection.refresh_token_enc)
                if connection.refresh_token_enc
                else None
            )

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
                client_secret=settings.google_client_secret,
            )

            accounts = []

            print(
                f"DEBUG: Fetching all available Google Ads accounts for user {current_user.id}"
            )

            try:
                # Get developer token from environment
                developer_token = os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN")
                if not developer_token:
                    return {
                        "success": False,
                        "message": "Google Ads Developer Token not configured",
                        "accounts": [],
                    }

                # Create Google Ads client
                google_ads_client = GoogleAdsClient(
                    credentials=credentials,
                    developer_token=developer_token,
                    login_customer_id=None,  # Will list all accessible accounts
                )

                # Get the CustomerService
                customer_service = google_ads_client.get_service("CustomerService")

                # List accessible customers
                accessible_customers = customer_service.list_accessible_customers()

                print(
                    f"DEBUG: Found {len(accessible_customers.resource_names)} accessible customers"
                )

                # Get details for each customer
                for resource_name in accessible_customers.resource_names:
                    customer_id = resource_name.split("/")[-1]

                    try:
                        # Create a new client for this customer
                        customer_client = GoogleAdsClient(
                            credentials=credentials,
                            developer_token=developer_token,
                            login_customer_id=customer_id,
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

                        response = ga_service.search(
                            customer_id=customer_id, query=query
                        )

                        for row in response:
                            # Skip manager accounts
                            if not row.customer.manager:
                                accounts.append(
                                    {
                                        "customer_id": str(row.customer.id),
                                        "customer_name": row.customer.descriptive_name,
                                        "currency_code": row.customer.currency_code,
                                        "time_zone": row.customer.time_zone,
                                    }
                                )
                                print(
                                    f"DEBUG: Found Google Ads account: {row.customer.descriptive_name} (ID: {row.customer.id})"
                                )

                    except Exception as e:
                        print(
                            f"DEBUG: Failed to get details for customer {customer_id}: {str(e)}"
                        )
                        continue

            except Exception as e:
                print(f"DEBUG: Failed to fetch Google Ads accounts: {str(e)}")
                import traceback

                traceback.print_exc()
                return {
                    "success": False,
                    "error": f"Failed to fetch Google Ads accounts: {str(e)}",
                    "accounts": [],
                }

            print(f"DEBUG: Found {len(accounts)} total Google Ads accounts")

            # Mark which accounts are already connected
            connected_account_ids = []
            assets_statement = select(DigitalPlatform).where(
                DigitalPlatform.customer_id == customer_id,
                DigitalPlatform.asset_type == AssetType.GOOGLE_ADS,
            )
            connected_assets = session.exec(assets_statement).all()
            connected_account_ids = [asset.external_id for asset in connected_assets]

            # Add connected flag to each account
            for account in accounts:
                account["is_connected"] = (
                    account["customer_id"] in connected_account_ids
                )

            return {
                "success": True,
                "accounts": accounts,
                "message": f"Found {len(accounts)} Google Ads accounts",
                "access_token": access_token,
                "refresh_token": refresh_token,
            }

    except Exception as e:
        print(f"DEBUG: Error fetching available Google Ads accounts: {str(e)}")
        import traceback

        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch available Google Ads accounts: {str(e)}",
        )


# ========================================
# Google Ads Mutation Endpoints
# ========================================


@router.post("/campaigns/create")
async def create_campaign(
    request: "CreateCampaignRequest",
    current_user: Campaigner = Depends(get_current_user),
):
    """
    Create a new Google Ads campaign with budget and bidding strategy.
    """
    from app.models.google_ads import CreateCampaignRequest, CampaignCreationResponse

    try:
        # Validate connection ownership
        with get_session() as session:
            connection = session.get(Connection, request.connection_id)
            if not connection or connection.campaigner_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Connection not found",
                )

            # Validate customer access
            if not user_can_access_customer(current_user, connection.customer_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You don't have access to this customer",
                )

        # Create campaign using service
        result = await google_ads_service.create_campaign(
            connection_id=request.connection_id,
            customer_id=request.customer_id,
            campaign_name=request.campaign_name,
            budget_amount_micros=request.daily_budget_micros,
            campaign_type=request.campaign_type.value,
            bidding_strategy_type=request.bidding_strategy.value,
            bidding_config=request.bidding_config,
            network_settings=request.network_settings,
            start_date=request.start_date,
            end_date=request.end_date,
        )

        if result.get("success"):
            return CampaignCreationResponse(**result)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("error", "Failed to create campaign"),
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create campaign: {str(e)}",
        )


@router.patch("/campaigns/{campaign_id}")
async def update_campaign(
    campaign_id: str,
    request: "UpdateCampaignRequest",
    current_user: Campaigner = Depends(get_current_user),
):
    """
    Update campaign settings (name, status, dates).
    """
    from app.models.google_ads import UpdateCampaignRequest, MutationResponse

    try:
        # Validate connection ownership
        with get_session() as session:
            connection = session.get(Connection, request.connection_id)
            if not connection or connection.campaigner_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Connection not found",
                )

            # Validate customer access
            if not user_can_access_customer(current_user, connection.customer_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You don't have access to this customer",
                )

        # Build updates dict from request
        updates = {}
        if request.name is not None:
            updates["name"] = request.name
        if request.status is not None:
            updates["status"] = request.status.value
        if request.start_date is not None:
            updates["start_date"] = request.start_date
        if request.end_date is not None:
            updates["end_date"] = request.end_date

        # Update campaign using service
        result = await google_ads_service.update_campaign(
            connection_id=request.connection_id,
            customer_id=request.customer_id,
            campaign_id=campaign_id,
            updates=updates,
        )

        if result.get("success"):
            return MutationResponse(**result)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("error", "Failed to update campaign"),
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update campaign: {str(e)}",
        )


@router.post("/campaigns/{campaign_id}/budget")
async def update_campaign_budget(
    campaign_id: str,
    request: "UpdateBudgetRequest",
    current_user: Campaigner = Depends(get_current_user),
):
    """
    Update campaign budget amount.
    """
    from app.models.google_ads import UpdateBudgetRequest, MutationResponse

    try:
        # Validate connection ownership
        with get_session() as session:
            connection = session.get(Connection, request.connection_id)
            if not connection or connection.campaigner_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Connection not found",
                )

            # Validate customer access
            if not user_can_access_customer(current_user, connection.customer_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You don't have access to this customer",
                )

        # Get campaign to find budget ID
        # For now, we'll need to query the campaign to get the budget resource name
        # This is a simplified version - in production you'd want to cache this
        from app.services.google_ads_service import GoogleAdsService

        service = GoogleAdsService()
        # Query campaign to get budget
        query = f"""
            SELECT campaign.id, campaign.campaign_budget
            FROM campaign
            WHERE campaign.id = {campaign_id}
        """

        result = await service.execute_query(
            connection_id=request.connection_id,
            customer_id=request.customer_id,
            query=query,
        )

        if not result.get("success") or not result.get("data"):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Campaign not found",
            )

        budget_resource_name = result["data"][0].get("campaign.campaign_budget")
        if not budget_resource_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Campaign has no budget",
            )

        # Extract budget ID from resource name
        budget_id = budget_resource_name.split("/")[-1]

        # Update budget using service
        update_result = await google_ads_service.update_campaign_budget(
            connection_id=request.connection_id,
            customer_id=request.customer_id,
            budget_id=budget_id,
            amount_micros=request.new_daily_budget_micros,
        )

        if update_result.get("success"):
            return MutationResponse(**update_result)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=update_result.get("error", "Failed to update budget"),
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update budget: {str(e)}",
        )


@router.post("/campaigns/{campaign_id}/bidding")
async def update_campaign_bidding(
    campaign_id: str,
    request: "UpdateBiddingRequest",
    current_user: Campaigner = Depends(get_current_user),
):
    """
    Update campaign bidding strategy and configuration.
    """
    from app.models.google_ads import UpdateBiddingRequest, MutationResponse

    try:
        # Validate connection ownership
        with get_session() as session:
            connection = session.get(Connection, request.connection_id)
            if not connection or connection.campaigner_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Connection not found",
                )

            # Validate customer access
            if not user_can_access_customer(current_user, connection.customer_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You don't have access to this customer",
                )

        # Build bidding config from request
        bidding_config = {}
        if request.target_cpa_micros is not None:
            bidding_config["target_cpa_micros"] = request.target_cpa_micros
        if request.target_roas is not None:
            bidding_config["target_roas"] = request.target_roas
        if request.target_spend_cpc_bid_ceiling_micros is not None:
            bidding_config["target_spend_cpc_bid_ceiling_micros"] = (
                request.target_spend_cpc_bid_ceiling_micros
            )

        # Update bidding using service
        result = await google_ads_service.update_campaign_bidding_strategy(
            connection_id=request.connection_id,
            customer_id=request.customer_id,
            campaign_id=campaign_id,
            bidding_strategy_type=request.bidding_strategy.value,
            bidding_config=bidding_config if bidding_config else None,
        )

        if result.get("success"):
            return MutationResponse(**result)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("error", "Failed to update bidding strategy"),
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update bidding strategy: {str(e)}",
        )


@router.post("/campaigns/{campaign_id}/status")
async def update_campaign_status(
    campaign_id: str,
    request: "UpdateStatusRequest",
    current_user: Campaigner = Depends(get_current_user),
):
    """
    Update campaign status (ENABLED, PAUSED, REMOVED).
    """
    from app.models.google_ads import UpdateStatusRequest, MutationResponse

    try:
        # Validate connection ownership
        with get_session() as session:
            connection = session.get(Connection, request.connection_id)
            if not connection or connection.campaigner_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Connection not found",
                )

            # Validate customer access
            if not user_can_access_customer(current_user, connection.customer_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You don't have access to this customer",
                )

        # Update status using service
        result = await google_ads_service.update_campaign_status(
            connection_id=request.connection_id,
            customer_id=request.customer_id,
            campaign_id=campaign_id,
            status=request.status.value,
        )

        if result.get("success"):
            return MutationResponse(**result)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("error", "Failed to update campaign status"),
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update campaign status: {str(e)}",
        )


@router.post("/ad-groups/create")
async def create_ad_group(
    request: "CreateAdGroupRequest",
    current_user: Campaigner = Depends(get_current_user),
):
    """
    Create a new ad group in a campaign.
    """
    from app.models.google_ads import CreateAdGroupRequest, AdGroupCreationResponse

    try:
        # Validate connection ownership
        with get_session() as session:
            connection = session.get(Connection, request.connection_id)
            if not connection or connection.campaigner_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Connection not found",
                )

            # Validate customer access
            if not user_can_access_customer(current_user, connection.customer_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You don't have access to this customer",
                )

        # Create ad group using service
        result = await google_ads_service.create_ad_group(
            connection_id=request.connection_id,
            customer_id=request.customer_id,
            campaign_id=request.campaign_id,
            ad_group_name=request.ad_group_name,
            cpc_bid_micros=request.cpc_bid_micros,
        )

        if result.get("success"):
            return AdGroupCreationResponse(**result)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("error", "Failed to create ad group"),
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create ad group: {str(e)}",
        )


@router.post("/ads/create")
async def create_responsive_search_ad(
    request: "CreateAdRequest",
    current_user: Campaigner = Depends(get_current_user),
):
    """
    Create a responsive search ad in an ad group.
    """
    from app.models.google_ads import CreateAdRequest, AdCreationResponse

    try:
        # Validate connection ownership
        with get_session() as session:
            connection = session.get(Connection, request.connection_id)
            if not connection or connection.campaigner_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Connection not found",
                )

            # Validate customer access
            if not user_can_access_customer(current_user, connection.customer_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You don't have access to this customer",
                )

        # Create ad using service
        result = await google_ads_service.create_responsive_search_ad(
            connection_id=request.connection_id,
            customer_id=request.customer_id,
            ad_group_id=request.ad_group_id,
            headlines=request.headlines,
            descriptions=request.descriptions,
            final_urls=request.final_urls,
            path1=request.path1,
            path2=request.path2,
        )

        if result.get("success"):
            return AdCreationResponse(**result)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("error", "Failed to create ad"),
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create ad: {str(e)}",
        )
