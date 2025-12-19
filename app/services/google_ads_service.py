"""
Google Ads OAuth and data fetching service
Handles token storage, refresh, and Google Ads API calls
"""

import json
from datetime import datetime, timedelta, timezone
import os
import asyncio
from typing import Dict, Any, Optional, List
from google.oauth2.credentials import Credentials
from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException
from google.auth.transport.requests import Request
from sqlmodel import select, and_

from app.config.database import get_session
from app.models.analytics import DigitalPlatform, Connection, AssetType, AuthType
from app.models.users import Campaigner
from app.core.security import get_secret_key
from app.config.settings import get_settings
from app.utils.security_utils import get_token_crypto
from app.utils.connection_utils import get_connection_for_save


# Google client functions
def get_google_client_id() -> str:
    from dotenv import load_dotenv

    load_dotenv()  # Ensure .env is loaded
    return os.getenv("GOOGLE_CLIENT_ID", "")


def get_google_client_secret() -> str:
    from dotenv import load_dotenv

    load_dotenv()  # Ensure .env is loaded
    return os.getenv("GOOGLE_CLIENT_SECRET", "")


class GoogleAdsService:
    """Service for managing Google Ads OAuth and data fetching"""

    # Class-level refresh locks to prevent simultaneous token refresh attempts
    _refresh_locks = {}

    # Google Ads scopes - for advertising data access
    GOOGLE_ADS_SCOPES = [
        "https://www.googleapis.com/auth/adwords",
        "https://www.googleapis.com/auth/adsdatahub",
        "https://www.googleapis.com/auth/userinfo.email",  # User email for account identification
        "https://www.googleapis.com/auth/userinfo.profile",  # User profile for account identification
        "openid",  # OpenID Connect for authentication
    ]

    def __init__(self):
        self.crypto = get_token_crypto()

    def _encrypt_token(self, token: Optional[str]) -> Optional[bytes]:
        """Encrypt token for secure storage"""
        if not token:
            return None
        return self.crypto.encrypt_token(token)

    def _decrypt_token(self, encrypted_token) -> str:
        """Decrypt token for use"""
        # Validate input
        if encrypted_token is None:
            raise ValueError(
                "Encrypted token is None - connection may not be properly initialized"
            )

        if not isinstance(encrypted_token, (bytes, str)):
            raise ValueError(
                f"Encrypted token must be bytes or str, got {type(encrypted_token)}"
            )

        # Convert to bytes if it's a string
        if isinstance(encrypted_token, str):
            try:
                encrypted_token = encrypted_token.encode("utf-8")
            except Exception as e:
                raise ValueError(f"Failed to convert string token to bytes: {e}")

        try:
            return self.crypto.decrypt_token(encrypted_token)
        except Exception as e:
            raise ValueError(f"Failed to decrypt token: {e}")

    def _generate_token_hash(self, token: str) -> str:
        """Generate hash for token validation"""
        return self.crypto.generate_token_hash(token)

    async def save_google_ads_connection(
        self,
        campaigner_id: int,
        customer_id: int,
        account_id: str,
        account_name: str,
        access_token: str,
        refresh_token: Optional[str],
        expires_in: int,
        account_email: str,
    ) -> Dict[str, Any]:
        """
        Save Google Ads OAuth connection to database

        Args:
            campaigner_id: ID of campaigner creating the connection
            customer_id: ID of customer this asset belongs to
            account_id: Google Ads account ID (e.g., "123-456-7890")
            account_name: Human-readable account name
            access_token: OAuth access token
            refresh_token: OAuth refresh token
            expires_in: Token expiration time in seconds
            account_email: Google account email
        """

        print(
            f"🔄 Creating Google Ads connection for account {account_id} ({account_name})"
        )

        with get_session() as session:
            # Create or update the digital asset
            from app.services.digital_platform_service import upsert_digital_platform

            digital_platform = upsert_digital_platform(
                session=session,
                customer_id=customer_id,
                external_id=account_id,
                asset_type=AssetType.GOOGLE_ADS,
                provider="Google",
                name=account_name,
                handle=None,
                url=f"https://ads.google.com/aw/overview?ocid={account_id}",
                meta={
                    "account_id": account_id,
                    "currency_code": "USD",  # Default, will be updated from API
                    "time_zone": "America/New_York",  # Default, will be updated from API
                },
                is_active=True,
            )

            # Encrypt tokens
            access_token_enc = self._encrypt_token(access_token)
            refresh_token_enc = (
                self._encrypt_token(refresh_token) if refresh_token else None
            )
            token_hash = self._generate_token_hash(access_token)

            # Calculate expiration time with timezone-aware datetime
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
            now = datetime.now(timezone.utc)

            # Create or update connection using centralized query
            connection = get_connection_for_save(
                digital_platform_id=digital_platform.id,
                campaigner_id=campaigner_id,
                auth_type=AuthType.OAUTH2,
                session=session,
            )

            if connection:
                # Update existing connection
                connection.access_token_enc = access_token_enc
                connection.refresh_token_enc = refresh_token_enc
                connection.token_hash = token_hash
                connection.expires_at = expires_at
                connection.account_email = account_email
                connection.scopes = self.GOOGLE_ADS_SCOPES
                connection.rotated_at = now
                connection.last_used_at = now
                # Reset connection status - fresh tokens mean connection is healthy
                connection.revoked = False
                connection.needs_reauth = False
                connection.failure_count = 0
                connection.failure_reason = None
                connection.last_failure_at = None
            else:
                # Create new connection
                connection = Connection(
                    digital_platform_id=digital_platform.id,
                    customer_id=customer_id,
                    campaigner_id=campaigner_id,
                    auth_type=AuthType.OAUTH2,
                    account_email=account_email,
                    scopes=self.GOOGLE_ADS_SCOPES,
                    access_token_enc=access_token_enc,
                    refresh_token_enc=refresh_token_enc,
                    token_hash=token_hash,
                    expires_at=expires_at,
                    is_active=True,
                    revoked=False,
                    needs_reauth=False,
                    failure_count=0,
                    failure_reason=None,
                    last_failure_at=None,
                    last_used_at=now,
                )
                session.add(connection)

            session.commit()
            session.refresh(connection)

            # Automatically save this account as the selected property for the user
            from app.services.property_selection_service import PropertySelectionService

            property_selection_service = PropertySelectionService()

            try:
                await property_selection_service.save_property_selection(
                    campaigner_id=campaigner_id,
                    customer_id=customer_id,
                    service="google_ads",
                    property_id=account_id,
                    property_name=account_name,
                )
                print(
                    f"DEBUG: Automatically saved Google Ads account selection for {account_name}"
                )
            except Exception as e:
                print(f"DEBUG: Failed to save Google Ads account selection: {e}")
                # Don't fail the connection creation if property selection save fails

            print(f"✅ Google Ads connection created/updated: {connection.id}")
            print(f"   Account: {account_name} ({account_id})")
            print(f"   User: {campaigner_id}")
            print(f"   Expires at: {expires_at}")

            # Sync metrics for the last 90 days for new asset
            # Note: sync_metrics_new will automatically detect this is a new asset and sync all 90 days
            try:
                from app.services.campaign_sync_service import CampaignSyncService

                print(f"🔄 Starting metrics sync for new Google Ads connection...")
                sync_service = CampaignSyncService()
                sync_result = sync_service.sync_metrics_new(customer_id=customer_id)
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
                "connection_id": connection.id,
                "digital_platform_id": digital_platform.id,
                "account_id": account_id,
                "account_name": account_name,
                "expires_at": expires_at.isoformat(),
                "scopes": self.GOOGLE_ADS_SCOPES,
            }

    async def refresh_google_ads_token(self, connection_id: int) -> Dict[str, Any]:
        """Refresh Google Ads access token using refresh token"""

        with get_session() as session:
            # Get connection with digital asset
            statement = (
                select(Connection, DigitalPlatform)
                .join(DigitalPlatform, Connection.digital_platform_id == DigitalPlatform.id)
                .where(
                    and_(
                        Connection.id == connection_id,
                        Connection.auth_type == AuthType.OAUTH2,
                        Connection.revoked == False,
                    )
                )
            )
            result = session.exec(statement).first()

            if not result:
                raise ValueError("Connection not found or revoked")

            connection, digital_platform = result

            # Decrypt refresh token
            if not connection.refresh_token_enc:
                # No stored refresh token -> must re-authorize
                reauth_url = self.generate_reauth_url(
                    connection_id, connection.account_email
                )
                raise ValueError(f"Please re-authorize: {reauth_url}")
            refresh_token = self._decrypt_token(connection.refresh_token_enc)
            prev_refresh_hash = self._generate_token_hash(refresh_token)

            # Create credentials and refresh using stored scopes
            stored_scopes = (
                connection.scopes if connection.scopes else self.GOOGLE_ADS_SCOPES
            )
            credentials = Credentials(
                token=None,
                refresh_token=refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=get_google_client_id(),
                client_secret=get_google_client_secret(),
                scopes=stored_scopes,
            )

            try:
                # Refresh the token
                credentials.refresh(Request())

                # Encrypt and update new access token
                access_token_enc = self._encrypt_token(credentials.token)
                token_hash = self._generate_token_hash(credentials.token)
                connection.access_token_enc = access_token_enc
                connection.token_hash = token_hash

                # Only rotate refresh token if Google returned a new one
                new_refresh_token = getattr(credentials, "refresh_token", None)
                if new_refresh_token:
                    connection.refresh_token_enc = self._encrypt_token(
                        new_refresh_token
                    )
                    new_refresh_hash = self._generate_token_hash(new_refresh_token)
                    refresh_rotated = new_refresh_hash != prev_refresh_hash
                else:
                    # Keep existing refresh token
                    new_refresh_hash = prev_refresh_hash
                    refresh_rotated = False

                now = datetime.now(timezone.utc)
                connection.expires_at = now + timedelta(seconds=3600)  # 1 hour
                connection.rotated_at = now
                connection.last_used_at = now

                session.add(connection)
                session.commit()

                print(f"✅ Google Ads token refreshed for connection {connection_id}")
                print(f"   Expires at: {connection.expires_at}")

                return {
                    "success": True,
                    "connection_id": connection_id,
                    "expires_at": connection.expires_at.isoformat(),
                    "rotated_at": connection.rotated_at.isoformat(),
                    "scopes": stored_scopes,
                    # Debug-safe visibility for whether refresh token changed
                    "refresh_token_rotated": refresh_rotated,
                    "refresh_token_hash": new_refresh_hash,
                }

            except Exception as e:
                print(
                    f"❌ Google Ads token refresh failed for connection {connection_id}: {e}"
                )
                error_text = str(e)
                # For invalid_grant or obviously bad refresh tokens -> force reauth
                if "invalid_grant" in error_text.lower() or not refresh_token:
                    reauth_url = self.generate_reauth_url(
                        connection_id, connection.account_email
                    )
                    raise ValueError(f"Please re-authorize: {reauth_url}")
                # Propagate as ValueError for route to format
                raise ValueError(f"Refresh failed: {error_text}")

    def validate_refresh_token(self, refresh_token: str) -> bool:
        """
        Validate refresh token without making API calls

        Args:
            refresh_token: The refresh token to validate

        Returns:
            True if token appears valid, False otherwise
        """
        try:
            # Basic validation checks
            if not refresh_token or len(refresh_token) < 10:
                print("❌ Invalid refresh token format")
                return False

            # Check if it looks like a valid Google OAuth2 refresh token
            # Google refresh tokens typically start with '1//' and are base64-like
            if not refresh_token.startswith("1//"):
                print("❌ Refresh token doesn't match Google OAuth2 format")
                return False

            # Try to create a Credentials object to validate the token structure
            # This doesn't make an API call, just validates the format
            try:
                credentials = Credentials(
                    token=None,
                    refresh_token=refresh_token,
                    token_uri="https://oauth2.googleapis.com/token",
                    client_id=get_google_client_id(),
                    client_secret=get_google_client_secret(),
                    scopes=self.GOOGLE_ADS_SCOPES,
                )
                # If we can create the credentials object, the token format is valid
                print("✅ Refresh token format appears valid")
                return True
            except Exception as cred_error:
                print(f"❌ Refresh token credentials validation failed: {cred_error}")
                return False

        except Exception as e:
            print(f"❌ Refresh token validation error: {e}")
            return False

    def is_token_expired(self, expires_at: datetime) -> bool:
        """
        Check if token is expired with buffer

        Args:
            expires_at: Token expiration datetime

        Returns:
            True if expired or expiring soon, False otherwise
        """
        if not expires_at:
            return True  # No expiry time means assume expired

        # If datetime is naive, assume it's UTC
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        current_time = datetime.now(timezone.utc)
        time_until_expiry = expires_at - current_time

        # Consider expired if it expires within 5 minutes
        return time_until_expiry <= timedelta(minutes=5)

    def generate_reauth_url(self, connection_id: int, user_email: str) -> str:
        """Generate a new OAuth URL for re-authorization when refresh tokens are invalid"""
        from urllib.parse import urlencode
        import secrets

        # Generate state parameter for security
        state = secrets.token_urlsafe(32)

        # Store state in session or database for validation
        # For now, we'll just return the URL

        # Build OAuth URL
        settings = get_settings()
        frontend_url = os.getenv("FRONTEND_URL") or settings.frontend_url
        params = {
            "client_id": get_google_client_id(),
            "redirect_uri": f"{frontend_url}/auth/google-ads-callback",
            "scope": " ".join(self.GOOGLE_ADS_SCOPES),
            "response_type": "code",
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
        }

        return f"https://accounts.google.com/o/oauth2/auth?{urlencode(params)}"

    async def get_google_ads_data(
        self,
        connection_id: int,
        customer_id: str,
        metrics: List[str],
        dimensions: List[str] = None,
        start_date: str = None,
        end_date: str = None,
        limit: int = 100,
    ) -> Dict[str, Any]:
        """
        Get Google Ads data using the Google Ads API

        Args:
            connection_id: ID of the connection to use
            customer_id: Google Ads customer ID
            metrics: List of metrics to fetch
            dimensions: List of dimensions to group by
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            limit: Maximum number of rows to return
        """

        print(f"🔄 Fetching Google Ads data for customer {customer_id}")
        print(f"   Metrics: {metrics}")
        print(f"   Dimensions: {dimensions}")
        print(f"   Date range: {start_date} to {end_date}")

        # Use default dates if not provided, otherwise assume dates are already in correct format
        if not start_date or not end_date:
            end_date_iso = datetime.now().strftime("%Y-%m-%d")
            start_date_iso = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
            print(f"   Using default dates: {start_date_iso} to {end_date_iso}")
        else:
            # Assume dates are already in correct format (conversion handled by calling tool)
            start_date_iso, end_date_iso = start_date, end_date
            print(f"   Using provided dates: {start_date_iso} to {end_date_iso}")

        # Get connection and ensure token is valid before proceeding
        with get_session() as session:
            connection = session.get(Connection, connection_id)
            if not connection:
                raise ValueError(f"Connection {connection_id} not found")

            # Check if token needs refresh (efficient check without API calls)
            token_needs_refresh = self.is_token_expired(connection.expires_at)

            if token_needs_refresh:
                # Use refresh lock to prevent simultaneous refresh attempts
                if connection_id not in self._refresh_locks:
                    self._refresh_locks[connection_id] = asyncio.Lock()

                async with self._refresh_locks[connection_id]:
                    # Double-check if token still needs refresh (another process might have refreshed it)
                    session.refresh(connection)  # Reload from DB
                    if not self.is_token_expired(connection.expires_at):
                        print(
                            f"🔄 Google Ads Token was already refreshed by another process"
                        )
                    else:
                        current_time = datetime.now(timezone.utc)
                        if connection.expires_at:
                            time_until_expiry = connection.expires_at - current_time
                            print(
                                f"🔄 Token expires soon ({time_until_expiry}), refreshing..."
                            )
                        else:
                            print(f"🔄 No token expiry time set, refreshing...")

                        try:
                            await self.refresh_google_ads_token(connection_id)
                            session.refresh(connection)
                            print(f"✅ Token refreshed successfully")
                        except Exception as refresh_error:
                            print(f"❌ Token refresh failed: {refresh_error}")
                            raise ValueError(
                                f"Failed to refresh Google Ads token: {refresh_error}"
                            )

            # Validate refresh token format (no API call needed)
            refresh_token = self._decrypt_token(connection.refresh_token_enc)
            if not self.validate_refresh_token(refresh_token):
                print(f"❌ Refresh token format is invalid, attempting refresh...")
                try:
                    await self.refresh_google_ads_token(connection_id)
                    session.refresh(connection)
                    # Re-validate after refresh
                    new_refresh_token = self._decrypt_token(
                        connection.refresh_token_enc
                    )
                    if not self.validate_refresh_token(new_refresh_token):
                        raise ValueError("Refresh token is invalid and cannot be fixed")
                    print(f"✅ Refresh token validation successful after refresh")
                except Exception as validation_error:
                    print(
                        f"❌ Refresh token validation and refresh failed: {validation_error}"
                    )
                    raise ValueError(
                        f"Google Ads refresh token is invalid: {validation_error}"
                    )

            # Decrypt tokens
            try:
                access_token = self._decrypt_token(connection.access_token_enc)
                refresh_token = self._decrypt_token(connection.refresh_token_enc)
                print(f"✅ Tokens decrypted successfully")
            except Exception as decrypt_error:
                print(f"❌ Token decryption failed: {decrypt_error}")
                raise ValueError(
                    f"Failed to decrypt Google Ads tokens: {decrypt_error}"
                )

        # Create Google Ads client
        try:
            # Check if we have a developer token
            developer_token = os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN", "")

            if developer_token:
                # Use Google Ads API with developer token
                client = GoogleAdsClient.load_from_dict(
                    {
                        "developer_token": developer_token,
                        "client_id": get_google_client_id(),
                        "client_secret": get_google_client_secret(),
                        "refresh_token": refresh_token,
                        "use_proto_plus": True,
                    }
                )

                # Get Google Ads service
                ga_service = client.get_service("GoogleAdsService")

                # Build query for campaigns and their performance
                query = f"""
                    SELECT 
                        campaign.id,
                        campaign.name,
                        campaign.status,
                        metrics.impressions,
                        metrics.clicks,
                        metrics.cost_micros,
                        metrics.conversions,
                        segments.date
                    FROM campaign
                    WHERE segments.date BETWEEN '{start_date_iso}' AND '{end_date_iso}'
                    AND campaign.status = 'ENABLED'
                    ORDER BY segments.date DESC
                    LIMIT {limit}
                """

                # Execute the query
                try:
                    response = ga_service.search(customer_id=customer_id, query=query)

                    real_data = []
                    for row in response:
                        real_data.append(
                            {
                                "date": row.segments.date,
                                "campaign_id": row.campaign.id,
                                "campaign_name": row.campaign.name,
                                "impressions": row.metrics.impressions,
                                "clicks": row.metrics.clicks,
                                "cost": row.metrics.cost_micros
                                / 1_000_000,  # Convert from micros to currency units
                                "conversions": row.metrics.conversions,
                            }
                        )

                    print(
                        f"✅ Retrieved {len(real_data)} real Google Ads records using Google Ads API"
                    )
                    demo_data = real_data

                except GoogleAdsException as gads_error:
                    error_msg = str(gads_error)
                    print(f"❌ Google Ads API error: {error_msg}")

                    # Check if it's an authentication error
                    if any(
                        keyword in error_msg.lower()
                        for keyword in [
                            "authentication",
                            "unauthorized",
                            "invalid_grant",
                            "401",
                            "credentials",
                        ]
                    ):
                        print(
                            f"🔄 Authentication error detected, attempting token refresh..."
                        )
                        try:
                            # Try to refresh the token
                            await self.refresh_google_ads_token(connection_id)
                            print(f"✅ Token refreshed successfully, retrying query...")

                            # Retry the query with refreshed token
                            # Recreate the client with new token
                            with get_session() as retry_session:
                                retry_connection = retry_session.get(
                                    Connection, connection_id
                                )
                                retry_refresh_token = self._decrypt_token(
                                    retry_connection.refresh_token_enc
                                )

                            retry_client = GoogleAdsClient.load_from_dict(
                                {
                                    "developer_token": developer_token,
                                    "client_id": get_google_client_id(),
                                    "client_secret": get_google_client_secret(),
                                    "refresh_token": retry_refresh_token,
                                    "use_proto_plus": True,
                                }
                            )

                            retry_ga_service = retry_client.get_service(
                                "GoogleAdsService"
                            )
                            response = retry_ga_service.search(
                                customer_id=customer_id, query=query
                            )

                            real_data = []
                            for row in response:
                                real_data.append(
                                    {
                                        "date": row.segments.date,
                                        "campaign_id": row.campaign.id,
                                        "campaign_name": row.campaign.name,
                                        "impressions": row.metrics.impressions,
                                        "clicks": row.metrics.clicks,
                                        "cost": row.metrics.cost_micros / 1_000_000,
                                        "conversions": row.metrics.conversions,
                                    }
                                )

                            print(
                                f"✅ Retrieved {len(real_data)} records after token refresh"
                            )
                            demo_data = real_data

                        except Exception as refresh_error:
                            print(f"❌ Token refresh failed: {refresh_error}")
                            raise ValueError(
                                f"Google Ads authentication failed and token refresh unsuccessful: {error_msg}"
                            )
                    else:
                        # Not an auth error, re-raise
                        raise

            else:
                # No Developer Token available - return error instead of fake data
                return {
                    "success": False,
                    "error": "Google Ads Developer Token is required for data access. Please configure GOOGLE_ADS_DEVELOPER_TOKEN environment variable.",
                    "data": [],
                    "total_rows": 0,
                    "metrics": metrics,
                    "dimensions": dimensions or [],
                    "customer_id": customer_id,
                }

            return {
                "success": True,
                "data": demo_data,
                "total_rows": len(demo_data),
                "metrics": metrics,
                "dimensions": dimensions or [],
                "customer_id": customer_id,
            }

        except Exception as e:
            print(f"❌ Failed to fetch Google Ads data: {e}")
            import traceback

            traceback.print_exc()
            raise ValueError(f"Failed to fetch Google Ads data: {str(e)}")

    async def get_user_google_ads_connections(
        self, campaigner_id: int, customer_id: int = None
    ) -> List[Dict[str, Any]]:
        """Get all Google Ads connections for a user and subclient"""

        with get_session() as session:
            conditions = [
                Connection.campaigner_id == campaigner_id,
                DigitalPlatform.provider == "Google",
                Connection.revoked == False,
            ]

            # Check for GOOGLE_ADS asset type (database uses 'GOOGLE_ADS' uppercase)
            conditions.append(DigitalPlatform.asset_type == AssetType.GOOGLE_ADS_CAPS)

            # Add customer_id filter if provided
            if customer_id is not None:
                conditions.append(DigitalPlatform.customer_id == customer_id)

            statement = (
                select(Connection, DigitalPlatform)
                .join(DigitalPlatform, Connection.digital_platform_id == DigitalPlatform.id)
                .where(and_(*conditions))
            )

            results = session.exec(statement).all()

            connections = []
            for connection, digital_platform in results:
                # Check if token is outdated using backend logic (avoids timezone issues)
                is_outdated = (
                    self.is_token_expired(connection.expires_at)
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
                    {
                        "connection_id": connection.id,
                        "digital_platform_id": digital_platform.id,
                        "customer_id": digital_platform.external_id,
                        "account_name": digital_platform.name,
                        "account_email": connection.account_email,
                        "expires_at": format_datetime(connection.expires_at),
                        "is_active": digital_platform.is_active,
                        "created_at": format_datetime(connection.created_at),
                        "is_outdated": is_outdated,
                    }
                )

            return connections

    # ===================================================================
    # CAMPAIGN & AD MUTATION METHODS
    # ===================================================================

    def _get_google_ads_client(self, connection_id: int) -> GoogleAdsClient:
        """Get authenticated Google Ads client for connection."""
        with get_session() as session:
            connection = session.get(Connection, connection_id)
            if not connection:
                raise ValueError(f"Connection {connection_id} not found")

            # Decrypt tokens
            refresh_token = self._decrypt_token(connection.refresh_token_enc)

            # Get developer token
            developer_token = os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN", "")
            if not developer_token:
                raise ValueError("GOOGLE_ADS_DEVELOPER_TOKEN is required for mutations")

            # Create Google Ads client
            client = GoogleAdsClient.load_from_dict(
                {
                    "developer_token": developer_token,
                    "client_id": get_google_client_id(),
                    "client_secret": get_google_client_secret(),
                    "refresh_token": refresh_token,
                    "use_proto_plus": True,
                }
            )

            return client

    # === Campaign Management ===

    async def create_campaign(
        self,
        connection_id: int,
        customer_id: str,
        campaign_name: str,
        budget_amount_micros: int,
        campaign_type: str,
        bidding_strategy_type: str,
        bidding_config: Dict[str, Any] = None,
        network_settings: Dict[str, bool] = None,
        start_date: str = None,
        end_date: str = None,
    ) -> Dict[str, Any]:
        """Create a new Google Ads campaign with budget and bidding strategy."""
        from app.services.google_ads_mutations import (
            get_campaign_service,
            get_campaign_budget_service,
            create_budget_operation,
            create_campaign_operation,
            apply_network_settings,
            apply_bidding_strategy,
            execute_mutation,
        )
        from app.services.google_ads_validators import (
            validate_campaign_name,
            validate_campaign_type,
            validate_bidding_strategy,
            validate_budget_amount,
            validate_customer_id,
            validate_date_format,
        )

        try:
            # Validate inputs
            validate_customer_id(customer_id)
            validate_campaign_name(campaign_name)
            validate_campaign_type(campaign_type)
            validate_bidding_strategy(bidding_strategy_type, bidding_config)
            validate_budget_amount(budget_amount_micros)

            if start_date:
                validate_date_format(start_date, "start_date")
            if end_date:
                validate_date_format(end_date, "end_date")

            client = self._get_google_ads_client(connection_id)

            # Create budget
            budget_result = await self._create_budget(
                client,
                customer_id,
                f"{campaign_name} Budget",
                budget_amount_micros,
            )

            if not budget_result["success"]:
                return budget_result

            budget_resource_name = budget_result["resource_names"][0]

            # Create campaign
            campaign_result = await self._create_campaign_with_settings(
                client,
                customer_id,
                campaign_name,
                budget_resource_name,
                campaign_type,
                bidding_strategy_type,
                bidding_config,
                network_settings,
                start_date,
                end_date,
            )

            if campaign_result["success"]:
                campaign_result["budget_resource_name"] = budget_resource_name

            return campaign_result

        except Exception as e:
            print(f"❌ Campaign creation failed: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    async def _create_budget(
        self,
        client: GoogleAdsClient,
        customer_id: str,
        budget_name: str,
        amount_micros: int,
    ) -> Dict[str, Any]:
        """Create campaign budget - internal helper."""
        from app.services.google_ads_mutations import (
            get_campaign_budget_service,
            create_budget_operation,
            execute_mutation,
        )

        budget_service = get_campaign_budget_service(client)
        budget_operation = create_budget_operation(
            client,
            budget_name,
            amount_micros,
        )

        return execute_mutation(
            budget_service.mutate_campaign_budgets,
            customer_id,
            [budget_operation],
            "Budget creation",
        )

    async def _create_campaign_with_settings(
        self,
        client: GoogleAdsClient,
        customer_id: str,
        campaign_name: str,
        budget_resource_name: str,
        campaign_type: str,
        bidding_strategy_type: str,
        bidding_config: Optional[Dict[str, Any]],
        network_settings: Optional[Dict[str, bool]],
        start_date: Optional[str],
        end_date: Optional[str],
    ) -> Dict[str, Any]:
        """Create campaign with all settings - internal helper."""
        from app.services.google_ads_mutations import (
            get_campaign_service,
            create_campaign_operation,
            apply_network_settings,
            apply_bidding_strategy,
            execute_mutation,
        )

        campaign_service = get_campaign_service(client)
        campaign_operation = create_campaign_operation(
            client,
            campaign_name,
            budget_resource_name,
            campaign_type,
        )

        campaign = campaign_operation.create

        # Apply bidding strategy
        apply_bidding_strategy(
            client,
            campaign,
            bidding_strategy_type,
            bidding_config or {},
        )

        # Apply network settings
        if network_settings:
            apply_network_settings(campaign, **network_settings)
        else:
            apply_network_settings(campaign)  # Use defaults

        # Apply dates if provided
        if start_date:
            campaign.start_date = start_date
        if end_date:
            campaign.end_date = end_date

        return execute_mutation(
            campaign_service.mutate_campaigns,
            customer_id,
            [campaign_operation],
            "Campaign creation",
        )

    async def update_campaign(
        self,
        connection_id: int,
        customer_id: str,
        campaign_id: str,
        updates: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Update campaign settings using field mask."""
        from app.services.google_ads_mutations import (
            get_campaign_service,
            update_campaign_field,
            build_campaign_resource_name,
            execute_mutation,
        )
        from app.services.google_ads_validators import validate_customer_id

        try:
            validate_customer_id(customer_id)

            client = self._get_google_ads_client(connection_id)
            campaign_service = get_campaign_service(client)

            campaign_resource_name = build_campaign_resource_name(
                customer_id,
                campaign_id,
            )

            campaign_operation = update_campaign_field(
                client,
                campaign_resource_name,
                updates,
            )

            return execute_mutation(
                campaign_service.mutate_campaigns,
                customer_id,
                [campaign_operation],
                "Campaign update",
            )

        except Exception as e:
            print(f"❌ Campaign update failed: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    async def update_campaign_status(
        self,
        connection_id: int,
        customer_id: str,
        campaign_id: str,
        status: str,
    ) -> Dict[str, Any]:
        """Update campaign status."""
        from app.services.google_ads_validators import validate_campaign_status

        validate_campaign_status(status)

        return await self.update_campaign(
            connection_id,
            customer_id,
            campaign_id,
            {"status": status},
        )

    async def remove_campaign(
        self,
        connection_id: int,
        customer_id: str,
        campaign_id: str,
    ) -> Dict[str, Any]:
        """Remove (soft delete) a campaign."""
        return await self.update_campaign_status(
            connection_id,
            customer_id,
            campaign_id,
            "REMOVED",
        )

    # === Budget Management ===

    async def create_campaign_budget(
        self,
        connection_id: int,
        customer_id: str,
        budget_name: str,
        amount_micros: int,
        delivery_method: str = "STANDARD",
        explicitly_shared: bool = False,
    ) -> Dict[str, Any]:
        """Create a new campaign budget."""
        from app.services.google_ads_mutations import (
            get_campaign_budget_service,
            create_budget_operation,
            execute_mutation,
        )
        from app.services.google_ads_validators import (
            validate_customer_id,
            validate_budget_amount,
        )

        try:
            validate_customer_id(customer_id)
            validate_budget_amount(amount_micros)

            client = self._get_google_ads_client(connection_id)
            budget_service = get_campaign_budget_service(client)

            budget_operation = create_budget_operation(
                client,
                budget_name,
                amount_micros,
                delivery_method,
                explicitly_shared,
            )

            return execute_mutation(
                budget_service.mutate_campaign_budgets,
                customer_id,
                [budget_operation],
                "Budget creation",
            )

        except Exception as e:
            print(f"❌ Budget creation failed: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    async def update_campaign_budget(
        self,
        connection_id: int,
        customer_id: str,
        budget_id: str,
        amount_micros: int,
    ) -> Dict[str, Any]:
        """Update budget amount."""
        from app.services.google_ads_mutations import (
            get_campaign_budget_service,
            update_budget_operation,
            build_budget_resource_name,
            execute_mutation,
        )
        from app.services.google_ads_validators import (
            validate_customer_id,
            validate_budget_amount,
        )

        try:
            validate_customer_id(customer_id)
            validate_budget_amount(amount_micros)

            client = self._get_google_ads_client(connection_id)
            budget_service = get_campaign_budget_service(client)

            budget_resource_name = build_budget_resource_name(customer_id, budget_id)

            budget_operation = update_budget_operation(
                client,
                budget_resource_name,
                amount_micros,
            )

            return execute_mutation(
                budget_service.mutate_campaign_budgets,
                customer_id,
                [budget_operation],
                "Budget update",
            )

        except Exception as e:
            print(f"❌ Budget update failed: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    # === Bidding Strategy Management ===

    async def update_campaign_bidding_strategy(
        self,
        connection_id: int,
        customer_id: str,
        campaign_id: str,
        bidding_strategy_type: str,
        bidding_config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Update campaign's bidding strategy."""
        from app.services.google_ads_validators import validate_bidding_strategy

        try:
            validate_bidding_strategy(bidding_strategy_type, bidding_config)

            # Build updates dict for bidding strategy
            updates = {}
            if bidding_strategy_type == "TARGET_CPA":
                updates["target_cpa_micros"] = bidding_config.get("target_cpa_micros")
            elif bidding_strategy_type == "TARGET_ROAS":
                updates["target_roas"] = bidding_config.get("target_roas")

            return await self.update_campaign(
                connection_id,
                customer_id,
                campaign_id,
                updates,
            )

        except Exception as e:
            print(f"❌ Bidding strategy update failed: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    # === Asset Management ===

    async def upload_image_asset(
        self,
        connection_id: int,
        customer_id: str,
        asset_name: str,
        image_data: bytes,
        mime_type: str = "IMAGE_PNG",
    ) -> Dict[str, Any]:
        """Upload an image asset."""
        from app.services.google_ads_mutations import (
            get_asset_service,
            create_image_asset_operation,
            execute_mutation,
        )
        from app.services.google_ads_validators import (
            validate_customer_id,
            validate_asset_name,
            validate_image_data,
        )

        try:
            validate_customer_id(customer_id)
            validate_asset_name(asset_name)
            validate_image_data(image_data)

            client = self._get_google_ads_client(connection_id)
            asset_service = get_asset_service(client)

            asset_operation = create_image_asset_operation(
                client,
                asset_name,
                image_data,
                mime_type,
            )

            return execute_mutation(
                asset_service.mutate_assets,
                customer_id,
                [asset_operation],
                "Asset upload",
            )

        except Exception as e:
            print(f"❌ Asset upload failed: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    async def link_asset_to_campaign(
        self,
        connection_id: int,
        customer_id: str,
        asset_resource_name: str,
        campaign_id: str,
        field_type: str,
    ) -> Dict[str, Any]:
        """Link an asset to a campaign."""
        from app.services.google_ads_mutations import (
            get_campaign_asset_service,
            create_campaign_asset_link_operation,
            build_campaign_resource_name,
            execute_mutation,
        )
        from app.services.google_ads_validators import (
            validate_customer_id,
            validate_asset_field_type,
        )

        try:
            validate_customer_id(customer_id)
            validate_asset_field_type(field_type)

            client = self._get_google_ads_client(connection_id)
            campaign_asset_service = get_campaign_asset_service(client)

            campaign_resource_name = build_campaign_resource_name(customer_id, campaign_id)

            link_operation = create_campaign_asset_link_operation(
                client,
                asset_resource_name,
                campaign_resource_name,
                field_type,
            )

            return execute_mutation(
                campaign_asset_service.mutate_campaign_assets,
                customer_id,
                [link_operation],
                "Asset linking",
            )

        except Exception as e:
            print(f"❌ Asset linking failed: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    async def unlink_asset_from_campaign(
        self,
        connection_id: int,
        customer_id: str,
        campaign_asset_resource_name: str,
    ) -> Dict[str, Any]:
        """Remove asset link from campaign."""
        from app.services.google_ads_mutations import (
            get_campaign_asset_service,
            remove_campaign_asset_link_operation,
            execute_mutation,
        )
        from app.services.google_ads_validators import validate_customer_id

        try:
            validate_customer_id(customer_id)

            client = self._get_google_ads_client(connection_id)
            campaign_asset_service = get_campaign_asset_service(client)

            remove_operation = remove_campaign_asset_link_operation(
                client,
                campaign_asset_resource_name,
            )

            return execute_mutation(
                campaign_asset_service.mutate_campaign_assets,
                customer_id,
                [remove_operation],
                "Asset unlinking",
            )

        except Exception as e:
            print(f"❌ Asset unlinking failed: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    # === Ad Management ===

    async def create_ad_group(
        self,
        connection_id: int,
        customer_id: str,
        campaign_id: str,
        ad_group_name: str,
        cpc_bid_micros: int = None,
    ) -> Dict[str, Any]:
        """Create a new ad group."""
        from app.services.google_ads_mutations import (
            get_ad_group_service,
            create_ad_group_operation,
            build_campaign_resource_name,
            execute_mutation,
        )
        from app.services.google_ads_validators import (
            validate_customer_id,
            validate_ad_group_name,
        )

        try:
            validate_customer_id(customer_id)
            validate_ad_group_name(ad_group_name)

            client = self._get_google_ads_client(connection_id)
            ad_group_service = get_ad_group_service(client)

            campaign_resource_name = build_campaign_resource_name(customer_id, campaign_id)

            ad_group_operation = create_ad_group_operation(
                client,
                ad_group_name,
                campaign_resource_name,
                cpc_bid_micros,
            )

            return execute_mutation(
                ad_group_service.mutate_ad_groups,
                customer_id,
                [ad_group_operation],
                "Ad group creation",
            )

        except Exception as e:
            print(f"❌ Ad group creation failed: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    async def create_responsive_search_ad(
        self,
        connection_id: int,
        customer_id: str,
        ad_group_id: str,
        headlines: List[str],
        descriptions: List[str],
        final_urls: List[str],
        path1: str = None,
        path2: str = None,
    ) -> Dict[str, Any]:
        """Create a responsive search ad."""
        from app.services.google_ads_mutations import (
            get_ad_group_ad_service,
            create_responsive_search_ad_operation,
            build_ad_group_resource_name,
            execute_mutation,
        )
        from app.services.google_ads_validators import (
            validate_customer_id,
            validate_headlines,
            validate_descriptions,
            validate_final_urls,
            validate_display_path,
        )

        try:
            validate_customer_id(customer_id)
            validate_headlines(headlines)
            validate_descriptions(descriptions)
            validate_final_urls(final_urls)

            if path1:
                validate_display_path(path1, "path1")
            if path2:
                validate_display_path(path2, "path2")

            client = self._get_google_ads_client(connection_id)
            ad_group_ad_service = get_ad_group_ad_service(client)

            ad_group_resource_name = build_ad_group_resource_name(customer_id, ad_group_id)

            ad_operation = create_responsive_search_ad_operation(
                client,
                ad_group_resource_name,
                headlines,
                descriptions,
                final_urls,
                path1,
                path2,
            )

            return execute_mutation(
                ad_group_ad_service.mutate_ad_group_ads,
                customer_id,
                [ad_operation],
                "Ad creation",
            )

        except Exception as e:
            print(f"❌ Ad creation failed: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    async def update_ad_status(
        self,
        connection_id: int,
        customer_id: str,
        ad_group_ad_resource_name: str,
        status: str,
    ) -> Dict[str, Any]:
        """Update ad status."""
        from app.services.google_ads_mutations import (
            get_ad_group_ad_service,
            update_ad_status_operation,
            execute_mutation,
        )
        from app.services.google_ads_validators import (
            validate_customer_id,
            validate_campaign_status,  # Same enum values
        )

        try:
            validate_customer_id(customer_id)
            validate_campaign_status(status)  # Reuse validation

            client = self._get_google_ads_client(connection_id)
            ad_group_ad_service = get_ad_group_ad_service(client)

            status_operation = update_ad_status_operation(
                client,
                ad_group_ad_resource_name,
                status,
            )

            return execute_mutation(
                ad_group_ad_service.mutate_ad_group_ads,
                customer_id,
                [status_operation],
                "Ad status update",
            )

        except Exception as e:
            print(f"❌ Ad status update failed: {e}")
            return {
                "success": False,
                "error": str(e),
            }
