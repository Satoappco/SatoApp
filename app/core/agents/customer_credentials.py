"""Customer credential management for agents."""

from typing import Dict, Any, List, Optional
import logging
import os
from sqlmodel import select
from app.config.database import get_session
from app.models.analytics import DigitalAsset, Connection, AssetType
from app.services.google_ads_service import GoogleAdsService
from app.services.facebook_service import FacebookService

logger = logging.getLogger(__name__)


class CustomerCredentialManager:
    """Manages fetching and providing customer credentials for analytics agents."""

    def __init__(self):
        """Initialize the credential manager."""
        self.google_ads_service = GoogleAdsService()
        self.facebook_ads_service = FacebookService()
    def fetch_customer_platforms(self, customer_id: int) -> List[str]:
        """Fetch customer's enabled platforms from digital_assets table.

        Args:
            customer_id: Customer ID

        Returns:
            List of platform names (e.g., ["google", "facebook"])
        """
        platforms = []
        try:
            with get_session() as session:
                # Get digital assets for this customer
                digital_assets = session.exec(
                    select(DigitalAsset).where(
                        DigitalAsset.customer_id == customer_id,
                        DigitalAsset.is_active == True
                    )
                ).all()

                # Extract unique platforms from asset_type and provider
                platform_set = set()
                for asset in digital_assets:
                    asset_type_str = asset.asset_type.value if hasattr(asset.asset_type, 'value') else str(asset.asset_type)
                    provider = asset.provider.lower() if asset.provider else ""

                    # Map asset types to platforms
                    if asset_type_str in ["GA4", "GOOGLE_ADS", "GOOGLE_ADS_CAPS"]:
                        platform_set.add("google")
                    elif asset_type_str in ["FACEBOOK_ADS", "FACEBOOK_ADS_CAPS"] or "facebook" in provider or "meta" in provider:
                        platform_set.add("facebook")

                platforms = list(platform_set)
                logger.info(f"📊 [CredentialManager] Customer {customer_id} platforms: {platforms}")

        except Exception as e:
            logger.warning(f"⚠️  [CredentialManager] Failed to fetch platforms for customer {customer_id}: {e}")
            platforms = ["google"]  # Fallback to default

        return platforms

    def fetch_google_analytics_credentials(self, customer_id: int, campaigner_id: int) -> Optional[Dict[str, str]]:
        """Fetch customer's Google Analytics refresh token and property ID.

        Args:
            customer_id: Customer ID
            campaigner_id: Campaigner ID

        Returns:
            Dictionary with 'refresh_token', 'property_id', 'client_id', 'client_secret' or None
        """
        try:
            with get_session() as session:
                # Get Google Analytics digital asset for this customer
                ga_asset = session.exec(
                    select(DigitalAsset).where(
                        DigitalAsset.customer_id == customer_id,
                        DigitalAsset.asset_type == AssetType.GA4,
                        DigitalAsset.is_active == True
                    )
                ).first()

                if not ga_asset:
                    logger.warning(f"⚠️  [CredentialManager] No GA4 asset found for customer {customer_id}")
                    return None

                # Get the connection for this digital asset
                connection = session.exec(
                    select(Connection).where(
                        Connection.digital_asset_id == ga_asset.id,
                        Connection.customer_id == customer_id,
                        Connection.campaigner_id == campaigner_id,
                        Connection.revoked != True
                    )
                ).first()

                if not connection or not connection.refresh_token_enc:
                    logger.warning(f"⚠️  [CredentialManager] No active connection for GA4 asset")
                    return None

                # Decrypt the tokens
                try:
                    refresh_token = self.google_ads_service._decrypt_token(connection.refresh_token_enc)
                except Exception as decrypt_error:
                    logger.warning(f"⚠️  [CredentialManager] Failed to decrypt refresh_token: {decrypt_error}")
                    return None

                access_token = None
                if connection.access_token_enc:
                    try:
                        access_token = self.google_ads_service._decrypt_token(connection.access_token_enc)
                    except Exception as decrypt_error:
                        logger.warning(f"⚠️  [CredentialManager] Failed to decrypt access_token: {decrypt_error}")
                        access_token = None

                # Extract property_id from digital asset meta field
                property_id = ga_asset.meta.get("property_id") if ga_asset.meta else None

                if not property_id:
                    logger.warning(f"⚠️  [CredentialManager] No property_id in GA4 asset meta")
                    return None

                # Get OAuth client credentials from environment
                client_id = os.getenv("GOOGLE_CLIENT_ID")
                client_secret = os.getenv("GOOGLE_CLIENT_SECRET")

                if not client_id or not client_secret:
                    logger.warning(f"⚠️  [CredentialManager] Missing GOOGLE_CLIENT_ID or GOOGLE_CLIENT_SECRET")

                logger.info(f"✅ [CredentialManager] Found GA4 credentials, property: {property_id}")

                return {
                    "refresh_token": refresh_token,
                    "property_id": property_id,
                    "access_token": access_token,
                    "client_id": client_id,
                    "client_secret": client_secret
                }

        except Exception as e:
            logger.warning(f"⚠️  [CredentialManager] Failed to fetch GA credentials: {e}")
            import traceback
            logger.warning(f"   Traceback: {traceback.format_exc()}")

        return None

    def fetch_google_ads_credentials(self, customer_id: int, campaigner_id: int) -> Optional[Dict[str, str]]:
        """Fetch customer's Google Ads credentials.

        Args:
            customer_id: Customer ID
            campaigner_id: Campaigner ID

        Returns:
            Dictionary with 'refresh_token', 'customer_id', 'client_id', 'client_secret', 'developer_token' or None
        """
        try:
            with get_session() as session:
                # Get Google Ads digital asset for this customer
                gads_asset = session.exec(
                    select(DigitalAsset).where(
                        DigitalAsset.customer_id == customer_id,
                        DigitalAsset.asset_type == AssetType.GOOGLE_ADS,
                        DigitalAsset.is_active == True
                    )
                ).first()

                if not gads_asset:
                    logger.warning(f"⚠️  [CredentialManager] No Google Ads asset found for customer {customer_id}")
                    return None

                # Get the connection for this digital asset
                connection = session.exec(
                    select(Connection).where(
                        Connection.digital_asset_id == gads_asset.id,
                        Connection.customer_id == customer_id,
                        Connection.campaigner_id == campaigner_id,
                        Connection.revoked != True
                    )
                ).first()

                if not connection or not connection.refresh_token_enc:
                    logger.warning(f"⚠️  [CredentialManager] No active connection for Google Ads asset")
                    return None

                # Decrypt the tokens
                try:
                    refresh_token = self.google_ads_service._decrypt_token(connection.refresh_token_enc)
                except Exception as decrypt_error:
                    logger.warning(f"⚠️  [CredentialManager] Failed to decrypt refresh_token: {decrypt_error}")
                    return None

                # Extract account_id from digital asset meta field
                gads_account_id = gads_asset.meta.get("account_id") if gads_asset.meta else None

                if not gads_account_id:
                    logger.warning(f"⚠️  [CredentialManager] No account_id in Google Ads asset meta : {gads_asset.meta}")
                    return None

                # Get OAuth client credentials from environment
                client_id = os.getenv("GOOGLE_CLIENT_ID")
                client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
                developer_token = os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN")

                if not client_id or not client_secret or not developer_token:
                    logger.warning(f"⚠️  [CredentialManager] Missing Google Ads environment credentials")

                logger.info(f"✅ [CredentialManager] Found Google Ads credentials, account: {gads_account_id}")

                return {
                    "refresh_token": refresh_token,
                    "account_id": gads_account_id,
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "developer_token": developer_token
                }

        except Exception as e:
            logger.warning(f"⚠️  [CredentialManager] Failed to fetch Google Ads credentials: {e}")
            import traceback
            logger.warning(f"   Traceback: {traceback.format_exc()}")

        return None

    def fetch_meta_ads_credentials(self, customer_id: int, campaigner_id: int) -> Optional[Dict[str, str]]:
        """Fetch customer's Facebook/Meta Ads access token.

        Args:
            customer_id: Customer ID
            campaigner_id: Campaigner ID

        Returns:
            Dictionary with 'access_token', 'ad_account_id' or None
        """
        try:
            with get_session() as session:
                # Get Facebook Ads digital asset for this customer
                fb_asset = session.exec(
                    select(DigitalAsset).where(
                        DigitalAsset.customer_id == customer_id,
                        DigitalAsset.asset_type == AssetType.FACEBOOK_ADS,
                        Connection.campaigner_id == campaigner_id,
                        DigitalAsset.is_active == True
                    )
                ).first()

                if not fb_asset:
                    logger.warning(f"⚠️  [CredentialManager] No Facebook Ads asset found for customer {customer_id}")
                    return None

                # Get the connection for this digital asset
                connection = session.exec(
                    select(Connection).where(
                        Connection.digital_asset_id == fb_asset.id,
                        Connection.customer_id == customer_id,
                        Connection.campaigner_id == campaigner_id,
                        Connection.revoked != True
                    )
                ).first()

                if not connection or not connection.access_token_enc:
                    logger.warning(f"⚠️  [CredentialManager] No active connection for Facebook Ads asset")
                    return None

                # Decrypt the access token
                access_token = None
                try:
                    access_token = self.facebook_ads_service._decrypt_token(connection.access_token_enc)
                except Exception as decrypt_error:
                    logger.warning(f"⚠️  [CredentialManager] Failed to decrypt access_token: {decrypt_error}")
                    return None

                # Extract ad_account_id from digital asset meta field
                ad_account_id = fb_asset.meta.get("ad_account_id") if fb_asset.meta else None

                if not ad_account_id:
                    logger.warning(f"⚠️  [CredentialManager] No ad_account_id in Facebook Ads asset meta")
                    return None

                logger.info(f"✅ [CredentialManager] Found Facebook Ads credentials, account: {ad_account_id}")
                # from app.services.campaign_sync_service import CampaignSyncService
                # sync_service = CampaignSyncService()
                # res = sync_service.fetch_facebook_campaign_metrics(campaign_id, connection, fb_asset)
                # logger.info(f"✅ [CredentialManager] RES: {res}")
                return {
                    "access_token": access_token,
                    "ad_account_id": ad_account_id
                }

        except Exception as e:
            logger.warning(f"⚠️  [CredentialManager] Failed to fetch Facebook Ads credentials: {e}")
            import traceback
            logger.warning(f"   Traceback: {traceback.format_exc()}")

        return None

    def fetch_all_credentials(self, customer_id: int, campaigner_id: int) -> Dict[str, Any]:
        """Fetch all credentials for a customer.

        Args:
            customer_id: Customer ID
            campaigner_id: Campaigner ID

        Returns:
            Dictionary with platforms and all credentials
        """
        platforms = self.fetch_customer_platforms(customer_id)

        credentials = {
            "platforms": platforms,
            "google_analytics": None,
            "google_ads": None,
            "meta_ads": None
        }

        if "google" in platforms:
            credentials["google_analytics"] = self.fetch_google_analytics_credentials(customer_id, campaigner_id)
            credentials["google_ads"] = self.fetch_google_ads_credentials(customer_id, campaigner_id)

        if "facebook" in platforms:
            credentials["meta_ads"] = self.fetch_meta_ads_credentials(customer_id, campaigner_id)

        return credentials
