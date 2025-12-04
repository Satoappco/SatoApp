"""
Facebook OAuth and data fetching service
Handles token storage, refresh, and Facebook API calls
"""

import json
import hashlib
import base64
import requests
from datetime import datetime, timedelta
import os
import asyncio
from typing import Dict, Any, Optional, List
from cryptography.fernet import Fernet
from sqlmodel import select, and_

from app.config.database import get_session
from app.models.analytics import DigitalAsset, Connection, AssetType, AuthType
from app.models.users import Campaigner
from app.core.security import get_secret_key


class FacebookService:
    """Service for managing Facebook OAuth and data fetching"""

    # Class-level refresh locks to prevent simultaneous token refresh attempts
    _refresh_locks = {}

    # Facebook OAuth scopes - comprehensive set for marketing and analytics
    # Note: Advanced permissions require Facebook App Review or Business Manager access
    FACEBOOK_SCOPES = [
        "email",  # Basic user email
        "public_profile",  # Basic user profile
        "pages_read_engagement",  # Read page insights (requires app review)
        "pages_manage_metadata",  # Manage page metadata (requires app review)
        "ads_read",  # Read ads data (requires app review)
        "ads_management",  # Manage ads (requires app review)
        "business_management",  # Manage business assets (requires app review)
        "pages_show_list",  # Show pages list (requires app review)
        "read_insights",  # Read insights data (requires app review)
        "pages_read_user_content",  # Read user content on pages (requires app review)
        "pages_manage_posts",  # Manage page posts (requires app review)
        "pages_manage_engagement",  # Manage page engagement (requires app review)
    ]

    def __init__(self):
        self.encryption_key = self._get_encryption_key()
        self.cipher_suite = Fernet(self.encryption_key)
        self.api_version = os.getenv("FACEBOOK_API_VERSION", "v18.0")
        self.base_url = f"https://graph.facebook.com/{self.api_version}"

    def _get_encryption_key(self) -> bytes:
        """Get or create encryption key for token storage"""
        # Use a fixed key based on a known secret for consistency
        # In production, this should be stored in environment variables
        fixed_secret = os.getenv(
            "ANALYTICS_TOKEN_ENCRYPTION_KEY", "sato-analytics-token-encryption-key-2025"
        )

        # Create a consistent 32-byte key
        key_bytes = fixed_secret.encode("utf-8")
        key_bytes = key_bytes.ljust(32, b"0")[:32]
        return base64.urlsafe_b64encode(key_bytes)

    def _encrypt_token(self, token: str) -> bytes:
        """Encrypt token for secure storage"""
        return self.cipher_suite.encrypt(token.encode())

    def _decrypt_token(self, encrypted_token: bytes) -> str:
        """Decrypt token for use"""
        return self.cipher_suite.decrypt(encrypted_token).decode()

    def _generate_token_hash(self, token: str) -> str:
        """Generate hash for token validation"""
        return hashlib.sha256(token.encode()).hexdigest()

    def get_oauth_url(self, redirect_uri: str, state: str = None) -> str:
        """Generate Facebook OAuth URL"""
        from app.config.settings import get_settings

        settings = get_settings()

        params = {
            "client_id": settings.facebook_app_id,
            "redirect_uri": redirect_uri,
            "scope": ",".join(self.FACEBOOK_SCOPES),
            "response_type": "code",
            "state": state or "facebook_oauth",
        }

        return f"https://www.facebook.com/v18.0/dialog/oauth?" + "&".join(
            [f"{k}={v}" for k, v in params.items()]
        )

    async def exchange_code_for_token(
        self, code: str, redirect_uri: str
    ) -> Dict[str, Any]:
        """Exchange authorization code for access token"""
        from app.config.settings import get_settings

        settings = get_settings()

        print(f"🔧 Facebook OAuth Debug:")
        print(f"  - Code: {code[:10]}...")
        print(f"  - Redirect URI: {redirect_uri}")
        print(
            f"  - App ID: {settings.facebook_app_id[:10] if settings.facebook_app_id else 'NOT SET'}..."
        )
        print(f"  - App Secret: {'SET' if settings.facebook_app_secret else 'NOT SET'}")

        token_url = f"{self.base_url}/oauth/access_token"

        data = {
            "client_id": settings.facebook_app_id,
            "client_secret": settings.facebook_app_secret,
            "redirect_uri": redirect_uri,
            "code": code,
        }

        print(f"  - Token URL: {token_url}")
        print(f"  - Request data: {dict(data, client_secret='***', code='***')}")

        try:
            response = requests.post(token_url, data=data)
            print(f"  - Response status: {response.status_code}")
            print(f"  - Response headers: {dict(response.headers)}")

            if response.status_code != 200:
                response_text = response.text
                print(f"  - Response text: {response_text}")
                raise Exception(
                    f"Facebook token exchange failed: {response.status_code} - {response_text}"
                )

            token_data = response.json()
            print(f"  - Token data keys: {list(token_data.keys())}")

            if "error" in token_data:
                error_msg = token_data["error"].get("message", "Unknown error")
                print(f"  - Facebook OAuth error: {error_msg}")
                raise Exception(f"Facebook OAuth error: {error_msg}")

            if "access_token" not in token_data:
                print(f"  - No access_token in response: {token_data}")
                raise Exception("No access_token received from Facebook")

            # Get long-lived token
            print(f"  - Getting long-lived token...")
            long_lived_token = await self._get_long_lived_token(
                token_data["access_token"]
            )

            # Get user info
            print(f"  - Getting user info...")
            user_info = await self._get_user_info(long_lived_token["access_token"])
            print(
                f"  - User info: {dict(user_info, email=user_info.get('email', 'NO EMAIL'))}"
            )

            if not user_info.get("email"):
                print("  - WARNING: No email in user info - checking permissions")
                # Try to get email permission explicitly
                try:
                    email_response = requests.get(
                        f"https://graph.facebook.com/v18.0/me?fields=email&access_token={long_lived_token['access_token']}"
                    )
                    if email_response.status_code == 200:
                        email_data = email_response.json()
                        if email_data.get("email"):
                            user_info["email"] = email_data["email"]
                            print(
                                f"  - Retrieved email from separate request: {email_data['email']}"
                            )
                except Exception as e:
                    print(f"  - Failed to get email separately: {e}")

            return {
                "access_token": long_lived_token["access_token"],
                "expires_in": long_lived_token.get("expires_in", 3600),
                "campaigner_id": user_info["id"],
                "user_name": user_info.get("name", ""),
                "user_email": user_info.get("email", ""),
            }

        except requests.exceptions.RequestException as e:
            print(f"  - Request exception: {str(e)}")
            raise Exception(f"Facebook API request failed: {str(e)}")
        except Exception as e:
            print(f"  - Exception during token exchange: {str(e)}")
            raise

    async def _get_long_lived_token(self, short_lived_token: str) -> Dict[str, Any]:
        """Exchange short-lived token for long-lived token"""
        from app.config.settings import get_settings

        settings = get_settings()

        url = f"{self.base_url}/oauth/access_token"
        params = {
            "grant_type": "fb_exchange_token",
            "client_id": settings.facebook_app_id,
            "client_secret": settings.facebook_app_secret,
            "fb_exchange_token": short_lived_token,
        }

        response = requests.get(url, params=params)
        response.raise_for_status()

        return response.json()

    async def _extend_facebook_token(self, access_token: str) -> Dict[str, Any]:
        """Extend Facebook long-lived token (can be called multiple times)"""
        from app.config.settings import get_settings

        settings = get_settings()

        url = f"{self.base_url}/oauth/access_token"
        params = {
            "grant_type": "fb_exchange_token",
            "client_id": settings.facebook_app_id,
            "client_secret": settings.facebook_app_secret,
            "fb_exchange_token": access_token,
        }

        print(f"🔄 Extending Facebook token...")
        print(f"🔍 Facebook App ID: {settings.facebook_app_id}")
        print(
            f"🔍 Facebook App Secret: {'*' * len(settings.facebook_app_secret) if settings.facebook_app_secret else 'NOT SET'}"
        )
        print(f"🔍 Token length: {len(access_token)}")

        response = requests.get(url, params=params)

        print(f"🔍 Facebook API Response Status: {response.status_code}")
        print(f"🔍 Facebook API Response Headers: {dict(response.headers)}")

        if response.status_code != 200:
            error_data = (
                response.json()
                if response.headers.get("content-type", "").startswith(
                    "application/json"
                )
                else {}
            )
            error_msg = error_data.get("error", {}).get(
                "message", f"HTTP {response.status_code}"
            )
            error_code = error_data.get("error", {}).get("code", 0)
            error_subcode = error_data.get("error", {}).get("error_subcode", 0)

            print(f"❌ Facebook token extension failed: {error_msg}")
            print(f"❌ Error code: {error_code}, subcode: {error_subcode}")
            print(f"❌ Full error response: {error_data}")

            # Check if this is an invalid token error (not just expired)
            if error_code == 190 and error_subcode == 460:
                # Token is completely invalid - user needs to re-authenticate
                raise ValueError(
                    "Facebook token is completely invalid. User needs to re-authenticate their Facebook account."
                )
            else:
                # Other errors (rate limits, etc.)
                raise Exception(f"Facebook token extension failed: {error_msg}")

        result = response.json()
        print(f"✅ Facebook token extended successfully")
        return result

    async def _get_user_info(self, access_token: str) -> Dict[str, Any]:
        """Get user information from Facebook"""
        url = f"{self.base_url}/me"
        params = {"access_token": access_token, "fields": "id,name,email"}

        response = requests.get(url, params=params)
        response.raise_for_status()

        return response.json()

    async def save_facebook_connection(
        self,
        campaigner_id: int,
        customer_id: int,
        access_token: str,
        expires_in: int,
        user_name: str,
        user_email: str = None,
    ) -> Dict[str, Any]:
        """
        Save Facebook OAuth connection to database

        Args:
            campaigner_id: ID of campaigner creating the connection
            customer_id: ID of customer this asset belongs to
            access_token: OAuth access token
            expires_in: Token expiration time in seconds
            user_name: Facebook user name
            user_email: Facebook user email (optional)
        """

        # Get user's pages and ad accounts
        pages = await self._get_user_pages(access_token)
        ad_accounts = await self._get_user_ad_accounts(access_token)

        with get_session() as session:
            # Create digital assets for each page
            created_assets = []

            for page in pages:
                # Create or update digital asset
                from app.services.digital_asset_service import upsert_digital_asset

                digital_asset = upsert_digital_asset(
                    session=session,
                    customer_id=customer_id,
                    external_id=page["id"],
                    asset_type=AssetType.SOCIAL_MEDIA,
                    provider="Facebook",
                    name=page["name"],
                    handle=page.get("username"),
                    meta={
                        "page_id": page["id"],
                        "page_name": page["name"],
                        "page_username": page.get("username"),
                        "page_category": page.get("category"),
                        "user_name": user_name,
                        "user_email": user_email,
                        "access_token": access_token,
                        "created_via": "oauth_flow",
                    },
                    is_active=True,
                )
                created_assets.append(digital_asset)

            # Create digital assets for ad accounts
            for ad_account in ad_accounts:
                digital_asset = upsert_digital_asset(
                    session=session,
                    customer_id=customer_id,
                    external_id=ad_account["id"],
                    asset_type=AssetType.ADVERTISING,
                    provider="Facebook",
                    name=ad_account["name"],
                    meta={
                        "ad_account_id": ad_account["id"],
                        "ad_account_name": ad_account["name"],
                        "ad_account_currency": ad_account.get("currency"),
                        "user_name": user_name,
                        "user_email": user_email,
                        "access_token": access_token,
                        "created_via": "oauth_flow",
                    },
                    is_active=True,
                )
                created_assets.append(digital_asset)

            # Create connections for each asset
            connections = []
            for asset in created_assets:
                # Encrypt tokens
                access_token_enc = self._encrypt_token(access_token)
                token_hash = self._generate_token_hash(access_token)

                # Calculate expiration time
                expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

                # Check for existing connection
                connection_statement = select(Connection).where(
                    and_(
                        Connection.digital_asset_id == asset.id,
                        Connection.campaigner_id == campaigner_id,
                        Connection.revoked == False,
                    )
                )
                connection = session.exec(connection_statement).first()

                if connection:
                    # Update existing connection
                    connection.access_token_enc = access_token_enc
                    connection.token_hash = token_hash
                    connection.expires_at = expires_at
                    connection.account_email = user_email
                    connection.scopes = self.FACEBOOK_SCOPES
                    connection.rotated_at = datetime.now(timezone.utc)
                    connection.last_used_at = datetime.now(timezone.utc)
                else:
                    # Create new connection
                    connection = Connection(
                        digital_asset_id=asset.id,
                        customer_id=customer_id,
                        campaigner_id=campaigner_id,
                        auth_type=AuthType.OAUTH2,
                        account_email=user_email,
                        scopes=self.FACEBOOK_SCOPES,
                        access_token_enc=access_token_enc,
                        token_hash=token_hash,
                        expires_at=expires_at,
                        revoked=False,
                        last_used_at=datetime.now(timezone.utc),
                    )

                session.add(connection)
                session.commit()
                session.refresh(connection)
                connections.append(connection)

            # Automatically save the first page and first ad account as selected properties
            from app.services.property_selection_service import PropertySelectionService

            property_selection_service = PropertySelectionService()

            # Save first Facebook page as selected (if any)
            facebook_pages = [
                asset
                for asset in created_assets
                if asset.asset_type == AssetType.SOCIAL_MEDIA
            ]
            if facebook_pages:
                first_page = facebook_pages[0]
                try:
                    await property_selection_service.save_property_selection(
                        campaigner_id=campaigner_id,
                        customer_id=customer_id,
                        service="facebook_page",
                        property_id=first_page.external_id,
                        property_name=first_page.name,
                    )
                    print(
                        f"DEBUG: Automatically saved Facebook page selection for {first_page.name}"
                    )
                except Exception as e:
                    print(f"DEBUG: Failed to save Facebook page selection: {e}")

            # Save first Facebook ad account as selected (if any)
            facebook_ads = [
                asset
                for asset in created_assets
                if asset.asset_type == AssetType.ADVERTISING
            ]
            if facebook_ads:
                first_ad_account = facebook_ads[0]
                try:
                    await property_selection_service.save_property_selection(
                        campaigner_id=campaigner_id,
                        customer_id=customer_id,
                        service="facebook_ads",
                        property_id=first_ad_account.external_id,
                        property_name=first_ad_account.name,
                    )
                    print(
                        f"DEBUG: Automatically saved Facebook ads selection for {first_ad_account.name}"
                    )
                except Exception as e:
                    print(f"DEBUG: Failed to save Facebook ads selection: {e}")

            # Sync metrics for the last 90 days for new asset
            # Note: sync_metrics_new will automatically detect this is a new asset and sync all 90 days
            try:
                from app.services.campaign_sync_service import CampaignSyncService

                print(f"🔄 Starting metrics sync for new Facebook connection...")
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

            # Create a lookup dict for faster asset access
            assets_by_id = {asset.id: asset for asset in created_assets}

            def get_asset_attribute(asset_id, attribute, default_value):
                """Safely get attribute from asset, with fallback for missing assets"""
                asset = assets_by_id.get(asset_id)
                if asset:
                    return getattr(asset, attribute, default_value)
                return default_value

            return {
                "connections": [
                    {
                        "connection_id": conn.id,
                        "digital_asset_id": conn.digital_asset_id,
                        "asset_name": get_asset_attribute(
                            conn.digital_asset_id,
                            "name",
                            f"Unknown Asset (ID: {conn.digital_asset_id})",
                        ),
                        "asset_type": get_asset_attribute(
                            conn.digital_asset_id, "asset_type", "unknown"
                        ),
                        "external_id": get_asset_attribute(
                            conn.digital_asset_id, "external_id", None
                        ),
                    }
                    for conn in connections
                ],
                "user_name": user_name,
                "user_email": user_email,
                "expires_at": expires_at.isoformat(),
                "scopes": self.FACEBOOK_SCOPES,
            }

    async def _get_user_pages(self, access_token: str) -> List[Dict[str, Any]]:
        """Get user's Facebook pages"""
        url = f"{self.base_url}/me/accounts"
        params = {
            "access_token": access_token,
            "fields": "id,name,username,category,access_token",
        }

        print(f"🔍 DEBUG: Fetching Facebook pages from: {url}")
        print(f"🔍 DEBUG: Request params: {params['fields']}")

        try:
            response = requests.get(url, params=params)
            response.raise_for_status()

            data = response.json()
            pages = data.get("data", [])

            print(
                f"📊 DEBUG: Raw Facebook Pages API response: {json.dumps(data, indent=2)}"
            )
            print(f"📊 DEBUG: Found {len(pages)} raw pages from API")

            # Check if Facebook returned an error
            if "error" in data:
                print(f"❌ Facebook Pages API returned error: {data['error']}")
                return []

            return pages

        except requests.exceptions.HTTPError as e:
            print(f"❌ HTTP Error fetching pages: {e}")
            print(
                f"❌ Response text: {e.response.text if hasattr(e, 'response') else 'N/A'}"
            )
            return []
        except Exception as e:
            print(f"❌ Error fetching pages: {str(e)}")
            return []

    async def _get_user_ad_accounts(self, access_token: str) -> List[Dict[str, Any]]:
        """Get user's Facebook ad accounts"""

        # First, check what permissions were granted
        print(f"🔍 Checking granted permissions for access token...")
        try:
            permissions_url = f"{self.base_url}/me/permissions"
            permissions_response = requests.get(
                permissions_url, params={"access_token": access_token}
            )
            if permissions_response.ok:
                permissions_data = permissions_response.json()
                granted_permissions = [
                    p["permission"]
                    for p in permissions_data.get("data", [])
                    if p.get("status") == "granted"
                ]
                print(f"✅ Granted permissions: {', '.join(granted_permissions)}")

                # Check if ads permissions are granted
                has_ads_read = "ads_read" in granted_permissions
                has_ads_management = "ads_management" in granted_permissions
                has_business_management = "business_management" in granted_permissions

                if not has_ads_read and not has_ads_management:
                    print(
                        f"⚠️ WARNING: Neither ads_read nor ads_management permissions are granted!"
                    )
                    print(f"   This means Facebook won't return any ad accounts.")
                    print(f"   The user needs to re-authorize with these permissions.")
                    return []
            else:
                print(f"⚠️ Could not fetch permissions: {permissions_response.text}")
        except Exception as e:
            print(f"⚠️ Error checking permissions: {str(e)}")

        url = f"{self.base_url}/me/adaccounts"
        params = {
            "access_token": access_token,
            "fields": "id,name,currency,account_status,timezone_name",
        }

        print(f"🔍 DEBUG: Fetching Facebook ad accounts from: {url}")
        print(f"🔍 DEBUG: Request params: {params['fields']}")

        try:
            response = requests.get(url, params=params)
            response.raise_for_status()

            data = response.json()
            ad_accounts = data.get("data", [])

            print(f"📊 DEBUG: Raw Facebook API response: {json.dumps(data, indent=2)}")
            print(f"📊 DEBUG: Found {len(ad_accounts)} raw ad accounts from API")

            # Check if Facebook returned an error
            if "error" in data:
                print(f"❌ Facebook API returned error: {data['error']}")
                return []

            # Format the ad accounts to include proper fields
            formatted_accounts = []
            for account in ad_accounts:
                # Facebook ad account IDs come with 'act_' prefix
                account_id = account.get("id", "")
                account_name = account.get("name", "Unknown Ad Account")

                print(
                    f"🔍 DEBUG: Processing ad account - ID: {account_id}, Name: {account_name}"
                )

                # Only include accounts that have the 'act_' prefix (real ad accounts)
                if account_id.startswith("act_"):
                    formatted_accounts.append(
                        {
                            "id": account_id,
                            "name": account_name,
                            "currency": account.get("currency", "USD"),
                            "timezone": account.get("timezone_name", "UTC"),
                            "account_status": account.get("account_status", 1),
                        }
                    )
                else:
                    print(f"⚠️ DEBUG: Skipping non-ad-account entry: {account_id}")

            print(
                f"✅ DEBUG: Returning {len(formatted_accounts)} formatted ad accounts"
            )
            return formatted_accounts

        except requests.exceptions.HTTPError as e:
            print(f"❌ HTTP Error fetching ad accounts: {e}")
            print(
                f"❌ Response text: {e.response.text if hasattr(e, 'response') else 'N/A'}"
            )
            return []
        except Exception as e:
            print(f"❌ Error fetching ad accounts: {str(e)}")
            return []

    async def fetch_facebook_data(
        self,
        connection_id: int,
        data_type: str = "page_insights",
        start_date: str = "7daysAgo",
        end_date: str = "today",
        metrics: List[str] = None,
        limit: int = 100,
    ) -> Dict[str, Any]:
        """
        Fetch Facebook data using stored connection

        Args:
            connection_id: ID of the connection to use
            data_type: Type of data to fetch (page_insights, ad_insights, page_posts)
            start_date: Start date in YYYY-MM-DD format or relative
            end_date: End date in YYYY-MM-DD format or relative
            metrics: List of metrics to fetch
            limit: Maximum number of results
        """

        with get_session() as session:
            # Get connection and asset info
            statement = (
                select(Connection, DigitalAsset)
                .join(DigitalAsset, Connection.digital_asset_id == DigitalAsset.id)
                .where(Connection.id == connection_id)
            )

            result = session.exec(statement).first()
            if not result:
                raise ValueError(f"Connection {connection_id} not found")

            connection, asset = result

            # Decrypt access token
            access_token = self._decrypt_token(connection.access_token_enc)

            # Check if token is expired (with 5-minute buffer) and refresh if needed
            buffer_time = timedelta(minutes=5)
            if (
                connection.expires_at
                and connection.expires_at < datetime.now(timezone.utc) + buffer_time
            ):
                # Use refresh lock to prevent simultaneous refresh attempts
                if connection_id not in self._refresh_locks:
                    self._refresh_locks[connection_id] = asyncio.Lock()

                async with self._refresh_locks[connection_id]:
                    # Double-check if token still needs refresh (another process might have refreshed it)
                    session.refresh(connection)  # Reload from DB
                    if not (
                        connection.expires_at
                        and connection.expires_at < datetime.now(timezone.utc) + buffer_time
                    ):
                        print(
                            f"🔄 Facebook token was already refreshed by another process"
                        )
                        access_token = self._decrypt_token(connection.access_token_enc)
                    else:
                        print(
                            f"🔄 Facebook token expired or expiring soon, refreshing..."
                        )

                        # Facebook DOES support long-lived token refresh!
                        # Try to extend the token using Facebook's token extension API
                        try:
                            extended_token = await self._extend_facebook_token(
                                access_token
                            )

                            # Update the connection with the new token
                            new_access_token = extended_token["access_token"]
                            new_expires_in = extended_token.get("expires_in", 3600)
                            new_expires_at = datetime.now(timezone.utc) + timedelta(
                                seconds=new_expires_in
                            )

                            # Encrypt and store the new token
                            connection.access_token_enc = self._encrypt_token(
                                new_access_token
                            )
                            connection.expires_at = new_expires_at
                            connection.rotated_at = datetime.now(timezone.utc)
                            session.add(connection)
                            session.commit()

                            print(
                                f"✅ Successfully refreshed Facebook token for connection {connection_id}"
                            )
                            access_token = new_access_token  # Use the new token

                        except ValueError as e:
                            # Token is completely invalid - user needs to re-authenticate
                            print(f"❌ Facebook token is invalid: {e}")
                            raise ValueError(
                                "Facebook token is completely invalid. Please re-authenticate your Facebook account."
                            )
                        except Exception as e:
                            # Other errors (rate limits, network issues, etc.)
                            print(f"❌ Failed to refresh Facebook token: {e}")
                            raise ValueError(
                                "Facebook token refresh failed. Please re-authenticate your Facebook account."
                            )

            # Update last used time
            connection.last_used_at = datetime.now(timezone.utc)
            session.add(connection)
            session.commit()

            # Fetch data based on type
            if data_type == "page_insights":
                return await self._fetch_page_insights(
                    asset, access_token, start_date, end_date, metrics, limit
                )
            elif data_type == "ad_insights":
                return await self._fetch_ad_insights(
                    asset, access_token, start_date, end_date, metrics, limit
                )
            elif data_type == "page_posts":
                return await self._fetch_page_posts(
                    asset, access_token, start_date, end_date, limit
                )
            else:
                raise ValueError(f"Unsupported data type: {data_type}")

    async def _fetch_page_insights(
        self,
        asset: DigitalAsset,
        access_token: str,
        start_date: str,
        end_date: str,
        metrics: List[str],
        limit: int,
    ) -> Dict[str, Any]:
        """Fetch page insights data"""

        if not metrics:
            metrics = [
                "page_impressions",
                "page_post_engagements",
                "page_video_views",
                "page_fans",
            ]

        # Validate metrics to prevent invalid API calls
        valid_metrics = {
            "page_impressions",
            "page_post_engagements",
            "page_video_views",
            "page_fans",
            "page_reach",
            "page_engaged_users",
            "page_actions_post_reactions_total",
            "page_posts_impressions",
            "page_posts_impressions_unique",
            "page_posts_impressions_viral",
            "page_posts_impressions_paid",
            "page_posts_impressions_organic",
        }

        invalid_metrics = [m for m in metrics if m not in valid_metrics]
        if invalid_metrics:
            print(f"⚠️ Invalid Facebook metrics detected: {invalid_metrics}")
            print(
                f"✅ Using only valid metrics: {[m for m in metrics if m in valid_metrics]}"
            )
            metrics = [m for m in metrics if m in valid_metrics]

            # If no valid metrics remain, use defaults
            if not metrics:
                metrics = [
                    "page_impressions",
                    "page_post_engagements",
                    "page_video_views",
                    "page_fans",
                ]

        page_id = asset.meta.get("page_id")
        if not page_id:
            raise ValueError("Page ID not found in asset metadata")

        url = f"{self.base_url}/{page_id}/insights"
        params = {
            "access_token": access_token,
            "metric": ",".join(metrics),
            "period": "day",
            "since": start_date,
            "until": end_date,
            "limit": limit,
        }

        response = requests.get(url, params=params)
        response.raise_for_status()

        data = response.json()

        return {
            "data_type": "page_insights",
            "page_id": page_id,
            "page_name": asset.name,
            "metrics": metrics,
            "date_range": {"start": start_date, "end": end_date},
            "data": data.get("data", []),
            "paging": data.get("paging", {}),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def _fetch_ad_insights(
        self,
        asset: DigitalAsset,
        access_token: str,
        start_date: str,
        end_date: str,
        metrics: List[str],
        limit: int,
    ) -> Dict[str, Any]:
        """Fetch ad insights data"""

        if not metrics:
            metrics = [
                "impressions",
                "reach",
                "clicks",
                "spend",
                "cpm",
                "cpc",
                "ctr",
                "conversions",
            ]

        ad_account_id = asset.meta.get("ad_account_id")
        if not ad_account_id:
            raise ValueError("Ad account ID not found in asset metadata")

        url = f"{self.base_url}/{ad_account_id}/insights"
        params = {
            "access_token": access_token,
            "fields": ",".join(metrics),
            "time_range": json.dumps({"since": start_date, "until": end_date}),
            "level": "account",
            "limit": limit,
        }

        print(f"🔍 Facebook Ads API Request:")
        print(f"   URL: {url}")
        print(f"   Ad Account ID: {ad_account_id}")
        print(f"   Date Range: {start_date} to {end_date}")
        print(f"   Metrics: {metrics}")
        print(f"   Token length: {len(access_token)}")

        response = requests.get(url, params=params)

        print(f"🔍 Facebook Ads API Response:")
        print(f"   Status: {response.status_code}")
        print(f"   Headers: {dict(response.headers)}")

        if response.status_code != 200:
            print(f"❌ Facebook Ads API Error Response:")
            print(f"   Content: {response.text}")

        response.raise_for_status()

        data = response.json()

        return {
            "data_type": "ad_insights",
            "ad_account_id": ad_account_id,
            "ad_account_name": asset.name,
            "metrics": metrics,
            "date_range": {"start": start_date, "end": end_date},
            "data": data.get("data", []),
            "paging": data.get("paging", {}),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def _fetch_page_posts(
        self,
        asset: DigitalAsset,
        access_token: str,
        start_date: str,
        end_date: str,
        limit: int,
    ) -> Dict[str, Any]:
        """Fetch page posts data"""

        page_id = asset.meta.get("page_id")
        if not page_id:
            raise ValueError("Page ID not found in asset metadata")

        url = f"{self.base_url}/{page_id}/posts"
        params = {
            "access_token": access_token,
            "fields": "id,message,created_time,type,permalink_url,insights.metric(post_impressions,post_engaged_users,post_clicks)",
            "limit": limit,
        }

        response = requests.get(url, params=params)
        response.raise_for_status()

        data = response.json()

        return {
            "data_type": "page_posts",
            "page_id": page_id,
            "page_name": asset.name,
            "date_range": {"start": start_date, "end": end_date},
            "data": data.get("data", []),
            "paging": data.get("paging", {}),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def refresh_facebook_token(self, connection_id: int) -> Dict[str, Any]:
        """Refresh Facebook access token using stored connection"""

        with get_session() as session:
            # Get connection with digital asset
            statement = (
                select(Connection, DigitalAsset)
                .join(DigitalAsset, Connection.digital_asset_id == DigitalAsset.id)
                .where(
                    and_(Connection.id == connection_id, Connection.revoked == False)
                )
            )
            result = session.exec(statement).first()

            if not result:
                raise ValueError("Connection not found or revoked")

            connection, digital_asset = result

            # Decrypt access token
            access_token = self._decrypt_token(connection.access_token_enc)

            # Check if token is expired (with 5-minute buffer)
            buffer_time = timedelta(minutes=5)
            if (
                connection.expires_at
                and connection.expires_at < datetime.now(timezone.utc) + buffer_time
            ):
                # Use refresh lock to prevent simultaneous refresh attempts
                if connection_id not in self._refresh_locks:
                    self._refresh_locks[connection_id] = asyncio.Lock()

                async with self._refresh_locks[connection_id]:
                    # Double-check if token still needs refresh (another process might have refreshed it)
                    session.refresh(connection)  # Reload from DB
                    if not (
                        connection.expires_at
                        and connection.expires_at < datetime.now(timezone.utc) + buffer_time
                    ):
                        print(
                            f"🔄 Facebook token was already refreshed by another process"
                        )
                        access_token = self._decrypt_token(connection.access_token_enc)
                    else:
                        print(
                            f"🔄 Facebook token expired or expiring soon, refreshing..."
                        )

                        # Facebook DOES support long-lived token refresh!
                        # Try to extend the token using Facebook's token extension API
                        try:
                            extended_token = await self._extend_facebook_token(
                                access_token
                            )

                            # Update the connection with the new token
                            new_access_token = extended_token["access_token"]
                            new_expires_in = extended_token.get("expires_in", 3600)
                            new_expires_at = datetime.now(timezone.utc) + timedelta(
                                seconds=new_expires_in
                            )

                            # Encrypt and store the new token
                            connection.access_token_enc = self._encrypt_token(
                                new_access_token
                            )
                            connection.expires_at = new_expires_at
                            connection.rotated_at = datetime.now(timezone.utc)
                            session.add(connection)
                            session.commit()

                            print(
                                f"✅ Successfully refreshed Facebook token for connection {connection_id}"
                            )
                            access_token = new_access_token  # Use the new token

                        except ValueError as e:
                            # Token is completely invalid - user needs to re-authenticate
                            print(f"❌ Facebook token is invalid: {e}")
                            raise ValueError(
                                "Facebook token is completely invalid. Please re-authenticate your Facebook account."
                            )
                        except Exception as e:
                            # Other errors (rate limits, network issues, etc.)
                            print(f"❌ Failed to refresh Facebook token: {e}")
                            raise ValueError(
                                "Facebook token refresh failed. Please re-authenticate your Facebook account."
                            )

            # Update last used time
            connection.last_used_at = datetime.now(timezone.utc)
            session.add(connection)
            session.commit()

            return {
                "access_token": access_token,
                "expires_at": connection.expires_at.isoformat()
                if connection.expires_at
                else None,
                "connection_id": connection_id,
                "asset_name": digital_asset.name,
                "asset_type": digital_asset.asset_type,
            }

    async def get_facebook_connection_for_user(
        self, campaigner_id: int, customer_id: int, asset_type: str = "SOCIAL_MEDIA"
    ) -> Optional[Dict[str, Any]]:
        """Get active Facebook connection for user/subclient with token refresh - ALWAYS prioritizes real Page IDs"""

        with get_session() as session:
            # Build conditions list
            from sqlmodel import or_

            conditions = [
                Connection.campaigner_id == campaigner_id,
                DigitalAsset.customer_id == customer_id,
                DigitalAsset.provider == "Facebook",
                Connection.revoked == False,
            ]

            # Handle both old and new asset type naming conventions
            if asset_type == "ADVERTISING":
                # Check for both ADVERTISING and FACEBOOK_ADS types (database has both)
                conditions.append(
                    or_(
                        DigitalAsset.asset_type == "ADVERTISING",
                        DigitalAsset.asset_type == "FACEBOOK_ADS",
                        DigitalAsset.asset_type == "facebook_ads",
                    )
                )
            else:
                conditions.append(DigitalAsset.asset_type == asset_type)

            # Look for Facebook connections
            statement = (
                select(Connection, DigitalAsset)
                .join(DigitalAsset, Connection.digital_asset_id == DigitalAsset.id)
                .where(and_(*conditions))
            )

            results = session.exec(statement).all()
            if not results:
                return None

            # CRITICAL: Validate Facebook IDs based on asset type
            # - For SOCIAL_MEDIA: Page IDs are numeric (15+ digits)
            # - For ADVERTISING/FACEBOOK_ADS: Ad Account IDs start with "act_" followed by digits
            real_connections = []
            fake_connections = []

            for connection, digital_asset in results:
                external_id = digital_asset.external_id
                is_valid = False

                # Validate based on asset type
                if asset_type in ["ADVERTISING", "FACEBOOK_ADS", "facebook_ads"]:
                    # Ad Account IDs must start with "act_" and have numeric part
                    if external_id and external_id.startswith("act_"):
                        numeric_part = external_id[4:]  # Remove "act_" prefix
                        is_valid = numeric_part.isdigit() and len(numeric_part) >= 10
                else:
                    # Page IDs must be numeric with 15+ digits
                    is_valid = (
                        external_id and external_id.isdigit() and len(external_id) >= 15
                    )

                if is_valid:
                    real_connections.append((connection, digital_asset))
                else:
                    fake_connections.append((connection, digital_asset))

            # Always use real connections first, never fake ones
            if real_connections:
                connection, digital_asset = real_connections[0]
                print(
                    f"✅ Using REAL Facebook ID: {digital_asset.external_id} ({digital_asset.name}) - Type: {asset_type}"
                )
            elif fake_connections:
                connection, digital_asset = fake_connections[0]
                print(
                    f"⚠️ WARNING: Using fake/invalid Facebook ID: {digital_asset.external_id} ({digital_asset.name}) - This will cause API errors!"
                )
                return {
                    "error": f"Invalid Facebook ID: {digital_asset.external_id}. Please re-authenticate your Facebook account.",
                    "status": "error",
                    "requires_reauth": True,
                    "suggestion": "Please re-authenticate your Facebook account in the Connections tab",
                }
            else:
                return None

            try:
                # Try to refresh token (this will also check expiration)
                refreshed_token = await self.refresh_facebook_token(connection.id)
                return {
                    "connection_id": connection.id,
                    "digital_asset_id": digital_asset.id,
                    "asset_name": digital_asset.name,
                    "asset_type": digital_asset.asset_type,
                    "external_id": digital_asset.external_id,
                    "access_token": refreshed_token["access_token"],
                    "expires_at": refreshed_token["expires_at"],
                }
            except ValueError as e:
                if "invalid" in str(e).lower():
                    return {
                        "error": "Facebook token is completely invalid. Please re-authenticate your Facebook account.",
                        "connection_id": connection.id,
                        "digital_asset_id": digital_asset.id,
                        "asset_name": digital_asset.name,
                        "requires_reauth": True,
                    }
                elif "expired" in str(e).lower():
                    return {
                        "error": "Facebook token has expired. Please re-authenticate your Facebook account.",
                        "connection_id": connection.id,
                        "digital_asset_id": digital_asset.id,
                        "asset_name": digital_asset.name,
                        "requires_reauth": True,
                    }
                else:
                    raise e
