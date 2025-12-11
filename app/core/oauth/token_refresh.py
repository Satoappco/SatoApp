"""
OAuth Token Refresh Module

Handles automatic refresh of OAuth tokens before they expire.
Supports Google OAuth (Analytics, Ads) and Facebook/Meta OAuth.
"""

from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
import requests
from sqlmodel import select

from app.config.database import get_session
from app.config.logging import get_logger
from app.config.settings import get_settings
from app.models.analytics import Connection, AssetType
from app.core.agents.mcp_clients.mcp_registry import MCPServer
from app.utils.connection_failure_utils import record_connection_failure, record_connection_success

logger = get_logger(__name__)


class OAuthRefreshError(Exception):
    """Raised when OAuth token refresh fails."""

    def __init__(self, provider: str, error: str, error_description: str):
        self.provider = provider
        self.error = error
        self.error_description = error_description
        super().__init__(f"{provider} token refresh failed: {error} - {error_description}")


def is_token_expired(expires_at: Optional[datetime], buffer_minutes: int = 5) -> bool:
    """
    Check if token is expired or will expire soon.

    Args:
        expires_at: Token expiration timestamp
        buffer_minutes: Refresh token this many minutes before expiry

    Returns:
        True if token is expired or will expire within buffer period
    """
    if not expires_at:
        return True  # No expiry info = assume expired

    # Ensure expires_at is timezone-aware for comparison
    if expires_at.tzinfo is None:
        # If naive, assume UTC
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    buffer = timedelta(minutes=buffer_minutes)
    return datetime.now(timezone.utc) + buffer >= expires_at


def refresh_google_token(refresh_token: str) -> Dict[str, any]:
    """
    Refresh Google OAuth token.

    Args:
        refresh_token: Google OAuth refresh token

    Returns:
        Dict with 'access_token', 'expires_in', 'expires_at'

    Raises:
        OAuthRefreshError: If refresh fails
    """
    try:
        settings = get_settings()
        response = requests.post(
            'https://oauth2.googleapis.com/token',
            data={
                'client_id': settings.google_client_id,
                'client_secret': settings.google_client_secret,
                'refresh_token': refresh_token,
                'grant_type': 'refresh_token'
            },
            timeout=10
        )

        if response.status_code != 200:
            error_data = response.json() if response.text else {}
            logger.error(f"❌ Google token refresh failed: {response.status_code} - {response.text}")
            raise OAuthRefreshError(
                provider="google",
                error=error_data.get('error', 'unknown'),
                error_description=error_data.get('error_description', 'Token refresh failed')
            )

        data = response.json()
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=data['expires_in'])

        logger.info(f"✅ Google token refreshed successfully, expires at {expires_at}")

        return {
            'access_token': data['access_token'],
            'expires_in': data['expires_in'],
            'expires_at': expires_at
        }

    except requests.RequestException as e:
        logger.error(f"❌ Network error refreshing Google token: {e}")
        raise OAuthRefreshError(provider="google", error="network_error", error_description=str(e))
    except OAuthRefreshError:
        raise  # Re-raise OAuth errors as-is
    except Exception as e:
        logger.error(f"❌ Unexpected error refreshing Google token: {e}")
        raise OAuthRefreshError(provider="google", error="network_error", error_description=str(e))


def refresh_facebook_token(access_token: str) -> Dict[str, any]:
    """
    Refresh Facebook OAuth token.

    Args:
        access_token: Current Facebook access token

    Returns:
        Dict with 'access_token', 'expires_in', 'expires_at'

    Raises:
        OAuthRefreshError: If refresh fails
    """
    try:
        settings = get_settings()
        response = requests.get(
            'https://graph.facebook.com/v18.0/oauth/access_token',
            params={
                'grant_type': 'fb_exchange_token',
                'client_id': settings.facebook_app_id,
                'client_secret': settings.facebook_app_secret,
                'fb_exchange_token': access_token
            },
            timeout=10
        )

        if response.status_code != 200:
            error_data = response.json() if response.text else {}
            logger.error(f"❌ Facebook token refresh failed: {response.status_code} - {response.text}")
            raise OAuthRefreshError(
                provider="facebook",
                error=error_data.get('error', {}).get('type', 'unknown'),
                error_description=error_data.get('error', {}).get('message', 'Token refresh failed')
            )

        data = response.json()
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=data['expires_in'])

        logger.info(f"✅ Facebook token refreshed successfully, expires at {expires_at}")

        return {
            'access_token': data['access_token'],
            'expires_in': data['expires_in'],
            'expires_at': expires_at
        }

    except requests.RequestException as e:
        logger.error(f"❌ Network error refreshing Facebook token: {e}")
        raise OAuthRefreshError(provider="facebook", error="network_error", error_description=str(e))


def update_connection_token(
    campaigner_id: int,
    asset_type: AssetType,
    access_token: str,
    expires_at: datetime
) -> None:
    """Update connection with refreshed token."""
    with get_session() as session:
        from app.models.analytics import DigitalAsset
        from sqlmodel import and_

        # Find connection for this asset type
        connection = session.exec(
            select(Connection)
            .join(DigitalAsset)
            .where(
                and_(
                    Connection.campaigner_id == campaigner_id,
                    DigitalAsset.asset_type == asset_type,
                    DigitalAsset.is_active == True
                )
            )
        ).first()

        if connection:
            # Update token (assuming tokens are stored as plain text for now)
            # In production, these should be encrypted
            connection.expires_at = expires_at
            connection.updated_at = datetime.now(timezone.utc)
            connection.needs_reauth = False  # Successfully refreshed
            session.add(connection)
            session.commit()
            logger.info(f"✅ Updated {asset_type} token for campaigner {campaigner_id}")

            # Record successful token refresh
            record_connection_success(connection.id, reset_failure_count=True)


def mark_needs_reauth(campaigner_id: int, asset_type: AssetType) -> None:
    """Mark a connection as needing re-authentication."""
    with get_session() as session:
        from app.models.analytics import DigitalAsset
        from sqlmodel import and_

        connection = session.exec(
            select(Connection)
            .join(DigitalAsset)
            .where(
                and_(
                    Connection.campaigner_id == campaigner_id,
                    DigitalAsset.asset_type == asset_type,
                    DigitalAsset.is_active == True
                )
            )
        ).first()

        if connection:
            connection.needs_reauth = True
            session.add(connection)
            session.commit()
            logger.warning(f"⚠️  Marked {asset_type} connection as needs_reauth for campaigner {campaigner_id}")

            # Record connection failure
            record_connection_failure(connection.id, "token_refresh_failed", also_set_needs_reauth=False)


def refresh_tokens_for_platforms(
    campaigner_id: int,
    platforms: List[MCPServer],
    user_tokens: Dict[str, str],
    force_refresh: bool = False
) -> Dict[str, str]:
    """
    Refresh OAuth tokens for requested platforms if needed.

    Args:
        campaigner_id: ID of campaigner whose tokens to refresh
        platforms: List of MCP platforms being used
        user_tokens: Current tokens from database
        force_refresh: If True, refresh tokens regardless of expiry

    Returns:
        Updated user_tokens dict with fresh tokens

    Raises:
        OAuthRefreshError: If token refresh fails critically
    """
    from app.models.analytics import DigitalAsset
    from sqlmodel import and_

    refreshed_tokens = user_tokens.copy()

    # Check Google Analytics
    if MCPServer.GOOGLE_ANALYTICS_OFFICIAL in platforms:
        with get_session() as session:
            conn = session.exec(
                select(Connection)
                .join(DigitalAsset)
                .where(
                    and_(
                        Connection.campaigner_id == campaigner_id,
                        DigitalAsset.asset_type == AssetType.GA4,
                        DigitalAsset.is_active == True
                    )
                )
            ).first()

            if conn and (is_token_expired(conn.expires_at) or force_refresh):
                logger.info(f"🔄 Google Analytics token expired, refreshing...")
                try:
                    # Note: refresh_token should be decrypted in production
                    # For now, assuming we have access to the refresh token
                    refresh_token = user_tokens.get('google_analytics')
                    if refresh_token:
                        refreshed = refresh_google_token(refresh_token)
                        update_connection_token(
                            campaigner_id,
                            AssetType.GA4,
                            refreshed['access_token'],
                            refreshed['expires_at']
                        )
                        refreshed_tokens['google_analytics'] = refreshed['access_token']
                except OAuthRefreshError as e:
                    logger.error(f"❌ Failed to refresh Google Analytics token: {e}")
                    if e.error == 'invalid_grant':
                        mark_needs_reauth(campaigner_id, AssetType.GA4)
                    else:
                        # Record failure for other error types
                        if conn and conn.id:
                            record_connection_failure(conn.id, f"token_refresh_failed: {e.error}", also_set_needs_reauth=False)
                    # Remove failed token from result so MCP manager knows it failed
                    if 'google_analytics' in refreshed_tokens:
                        del refreshed_tokens['google_analytics']

    # Check Google Ads
    if MCPServer.GOOGLE_ADS_OFFICIAL in platforms:
        with get_session() as session:
            conn = session.exec(
                select(Connection)
                .join(DigitalAsset)
                .where(
                    and_(
                        Connection.campaigner_id == campaigner_id,
                        DigitalAsset.asset_type == AssetType.GOOGLE_ADS_CAPS,
                        DigitalAsset.is_active == True
                    )
                )
            ).first()

            if conn and (is_token_expired(conn.expires_at) or force_refresh):
                logger.info(f"🔄 Google Ads token expired, refreshing...")
                try:
                    refresh_token = user_tokens.get('google_ads')
                    if refresh_token:
                        refreshed = refresh_google_token(refresh_token)
                        update_connection_token(
                            campaigner_id,
                            AssetType.GOOGLE_ADS_CAPS,
                            refreshed['access_token'],
                            refreshed['expires_at']
                        )
                        refreshed_tokens['google_ads'] = refreshed['access_token']
                except OAuthRefreshError as e:
                    logger.error(f"❌ Failed to refresh Google Ads token: {e}")
                    if e.error == 'invalid_grant':
                        mark_needs_reauth(campaigner_id, AssetType.GOOGLE_ADS_CAPS)
                    else:
                        # Record failure for other error types
                        if conn and conn.id:
                            record_connection_failure(conn.id, f"token_refresh_failed: {e.error}", also_set_needs_reauth=False)
                    # Remove failed token from result so MCP manager knows it failed
                    if 'google_ads' in refreshed_tokens:
                        del refreshed_tokens['google_ads']

    # Check Facebook
    if MCPServer.META_ADS in platforms:
        with get_session() as session:
            conn = session.exec(
                select(Connection)
                .join(DigitalAsset)
                .where(
                    and_(
                        Connection.campaigner_id == campaigner_id,
                        DigitalAsset.asset_type == AssetType.FACEBOOK_ADS_CAPS,
                        DigitalAsset.is_active == True
                    )
                )
            ).first()

            if conn and (is_token_expired(conn.expires_at) or force_refresh):
                logger.info(f"🔄 Facebook token expired, refreshing...")
                try:
                    access_token = user_tokens.get('facebook')
                    if access_token:
                        refreshed = refresh_facebook_token(access_token)
                        update_connection_token(
                            campaigner_id,
                            AssetType.FACEBOOK_ADS_CAPS,
                            refreshed['access_token'],
                            refreshed['expires_at']
                        )
                        refreshed_tokens['facebook'] = refreshed['access_token']
                except OAuthRefreshError as e:
                    logger.error(f"❌ Failed to refresh Facebook token: {e}")
                    if 'invalid' in e.error.lower():
                        mark_needs_reauth(campaigner_id, AssetType.FACEBOOK_ADS_CAPS)
                    else:
                        # Record failure for other error types
                        if conn and conn.id:
                            record_connection_failure(conn.id, f"token_refresh_failed: {e.error}", also_set_needs_reauth=False)
                    # Remove failed token from result so MCP manager knows it failed
                    if 'facebook' in refreshed_tokens:
                        del refreshed_tokens['facebook']

    return refreshed_tokens
