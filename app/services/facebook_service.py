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
from typing import Dict, Any, Optional, List
from cryptography.fernet import Fernet
from sqlmodel import select, and_

from app.config.database import get_session
from app.models.analytics import DigitalAsset, Connection, AssetType, AuthType
from app.models.users import User
from app.core.security import get_secret_key


class FacebookService:
    """Service for managing Facebook OAuth and data fetching"""
    
    # Facebook OAuth scopes - comprehensive set for marketing and analytics
    # Note: Advanced permissions require Facebook App Review or Business Manager access
    FACEBOOK_SCOPES = [
        'email',                     # Basic user email
        'public_profile',            # Basic user profile
        'pages_read_engagement',     # Read page insights (requires app review)
        'pages_manage_metadata',     # Manage page metadata (requires app review)
        'ads_read',                  # Read ads data (requires app review)
        'ads_management',            # Manage ads (requires app review)
        'business_management',       # Manage business assets (requires app review)
        'pages_show_list',          # Show pages list (requires app review)
        'read_insights',            # Read insights data (requires app review)
        'pages_read_user_content',  # Read user content on pages (requires app review)
        'pages_manage_posts',       # Manage page posts (requires app review)
        'pages_manage_engagement'   # Manage page engagement (requires app review)
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
        fixed_secret = os.getenv("ANALYTICS_TOKEN_ENCRYPTION_KEY", "sato-analytics-token-encryption-key-2025")
        
        # Create a consistent 32-byte key
        key_bytes = fixed_secret.encode('utf-8')
        key_bytes = key_bytes.ljust(32, b'0')[:32]
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
            'client_id': settings.facebook_app_id,
            'redirect_uri': redirect_uri,
            'scope': ','.join(self.FACEBOOK_SCOPES),
            'response_type': 'code',
            'state': state or 'facebook_oauth'
        }
        
        return f"https://www.facebook.com/v18.0/dialog/oauth?" + "&".join([f"{k}={v}" for k, v in params.items()])
    
    async def exchange_code_for_token(self, code: str, redirect_uri: str) -> Dict[str, Any]:
        """Exchange authorization code for access token"""
        from app.config.settings import get_settings
        settings = get_settings()
        
        print(f"🔧 Facebook OAuth Debug:")
        print(f"  - Code: {code[:10]}...")
        print(f"  - Redirect URI: {redirect_uri}")
        print(f"  - App ID: {settings.facebook_app_id[:10] if settings.facebook_app_id else 'NOT SET'}...")
        print(f"  - App Secret: {'SET' if settings.facebook_app_secret else 'NOT SET'}")
        
        token_url = f"{self.base_url}/oauth/access_token"
        
        data = {
            'client_id': settings.facebook_app_id,
            'client_secret': settings.facebook_app_secret,
            'redirect_uri': redirect_uri,
            'code': code
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
                raise Exception(f"Facebook token exchange failed: {response.status_code} - {response_text}")
            
            token_data = response.json()
            print(f"  - Token data keys: {list(token_data.keys())}")
            
            if 'error' in token_data:
                error_msg = token_data['error'].get('message', 'Unknown error')
                print(f"  - Facebook OAuth error: {error_msg}")
                raise Exception(f"Facebook OAuth error: {error_msg}")
            
            if 'access_token' not in token_data:
                print(f"  - No access_token in response: {token_data}")
                raise Exception("No access_token received from Facebook")
            
            # Get long-lived token
            print(f"  - Getting long-lived token...")
            long_lived_token = await self._get_long_lived_token(token_data['access_token'])
            
            # Get user info
            print(f"  - Getting user info...")
            user_info = await self._get_user_info(long_lived_token['access_token'])
            print(f"  - User info: {dict(user_info, email=user_info.get('email', 'NO EMAIL'))}")
            
            if not user_info.get('email'):
                print("  - WARNING: No email in user info - checking permissions")
                # Try to get email permission explicitly
                try:
                    email_response = requests.get(
                        f"https://graph.facebook.com/v18.0/me?fields=email&access_token={long_lived_token['access_token']}"
                    )
                    if email_response.status_code == 200:
                        email_data = email_response.json()
                        if email_data.get('email'):
                            user_info['email'] = email_data['email']
                            print(f"  - Retrieved email from separate request: {email_data['email']}")
                except Exception as e:
                    print(f"  - Failed to get email separately: {e}")
            
            return {
                'access_token': long_lived_token['access_token'],
                'expires_in': long_lived_token.get('expires_in', 3600),
                'user_id': user_info['id'],
                'user_name': user_info.get('name', ''),
                'user_email': user_info.get('email', '')
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
            'grant_type': 'fb_exchange_token',
            'client_id': settings.facebook_app_id,
            'client_secret': settings.facebook_app_secret,
            'fb_exchange_token': short_lived_token
        }
        
        response = requests.get(url, params=params)
        response.raise_for_status()
        
        return response.json()
    
    async def _get_user_info(self, access_token: str) -> Dict[str, Any]:
        """Get user information from Facebook"""
        url = f"{self.base_url}/me"
        params = {
            'access_token': access_token,
            'fields': 'id,name,email'
        }
        
        response = requests.get(url, params=params)
        response.raise_for_status()
        
        return response.json()
    
    async def save_facebook_connection(
        self,
        user_id: int,
        subclient_id: int,
        access_token: str,
        expires_in: int,
        user_name: str,
        user_email: str = None
    ) -> Dict[str, Any]:
        """
        Save Facebook OAuth connection to database
        
        Args:
            user_id: ID of user creating the connection
            subclient_id: ID of subclient this asset belongs to
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
                # Check if digital asset already exists
                statement = select(DigitalAsset).where(
                    and_(
                        DigitalAsset.subclient_id == subclient_id,
                        DigitalAsset.asset_type == AssetType.SOCIAL_MEDIA,
                        DigitalAsset.provider == "Facebook",
                        DigitalAsset.external_id == page['id']
                    )
                )
                digital_asset = session.exec(statement).first()
                
                if not digital_asset:
                    # Create new digital asset
                    digital_asset = DigitalAsset(
                        subclient_id=subclient_id,
                        asset_type=AssetType.SOCIAL_MEDIA,
                        provider="Facebook",
                        name=page['name'],
                        handle=page.get('username'),
                        external_id=page['id'],
                        meta={
                            "page_id": page['id'],
                            "page_name": page['name'],
                            "page_username": page.get('username'),
                            "page_category": page.get('category'),
                            "user_name": user_name,
                            "user_email": user_email,
                            "access_token": access_token,  # Store for API calls
                            "created_via": "oauth_flow"
                        },
                        is_active=True
                    )
                    session.add(digital_asset)
                    session.commit()
                    session.refresh(digital_asset)
                    created_assets.append(digital_asset)
                else:
                    # Update existing asset
                    digital_asset.meta.update({
                        "page_name": page['name'],
                        "page_username": page.get('username'),
                        "page_category": page.get('category'),
                        "user_name": user_name,
                        "user_email": user_email,
                        "access_token": access_token
                    })
                    session.add(digital_asset)
                    session.commit()
                    created_assets.append(digital_asset)
            
            # Create digital assets for ad accounts
            for ad_account in ad_accounts:
                statement = select(DigitalAsset).where(
                    and_(
                        DigitalAsset.subclient_id == subclient_id,
                        DigitalAsset.asset_type == AssetType.ADVERTISING,
                        DigitalAsset.provider == "Facebook",
                        DigitalAsset.external_id == ad_account['id']
                    )
                )
                digital_asset = session.exec(statement).first()
                
                if not digital_asset:
                    digital_asset = DigitalAsset(
                        subclient_id=subclient_id,
                        asset_type=AssetType.ADVERTISING,
                        provider="Facebook",
                        name=ad_account['name'],
                        external_id=ad_account['id'],
                        meta={
                            "ad_account_id": ad_account['id'],
                            "ad_account_name": ad_account['name'],
                            "ad_account_currency": ad_account.get('currency'),
                            "user_name": user_name,
                            "user_email": user_email,
                            "access_token": access_token,
                            "created_via": "oauth_flow"
                        },
                        is_active=True
                    )
                    session.add(digital_asset)
                    session.commit()
                    session.refresh(digital_asset)
                    created_assets.append(digital_asset)
            
            # Create connections for each asset
            connections = []
            for asset in created_assets:
                # Encrypt tokens
                access_token_enc = self._encrypt_token(access_token)
                token_hash = self._generate_token_hash(access_token)
                
                # Calculate expiration time
                expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
                
                # Check for existing connection
                connection_statement = select(Connection).where(
                    and_(
                        Connection.digital_asset_id == asset.id,
                        Connection.user_id == user_id,
                        Connection.revoked == False
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
                    connection.rotated_at = datetime.utcnow()
                    connection.last_used_at = datetime.utcnow()
                else:
                    # Create new connection
                    connection = Connection(
                        digital_asset_id=asset.id,
                        user_id=user_id,
                        auth_type=AuthType.OAUTH2,
                        account_email=user_email,
                        scopes=self.FACEBOOK_SCOPES,
                        access_token_enc=access_token_enc,
                        token_hash=token_hash,
                        expires_at=expires_at,
                        revoked=False,
                        last_used_at=datetime.utcnow()
                    )
                
                session.add(connection)
                session.commit()
                session.refresh(connection)
                connections.append(connection)
            
            return {
                "connections": [
                    {
                        "connection_id": conn.id,
                        "digital_asset_id": conn.digital_asset_id,
                        "asset_name": next(asset.name for asset in created_assets if asset.id == conn.digital_asset_id),
                        "asset_type": next(asset.asset_type for asset in created_assets if asset.id == conn.digital_asset_id),
                        "external_id": next(asset.external_id for asset in created_assets if asset.id == conn.digital_asset_id)
                    }
                    for conn in connections
                ],
                "user_name": user_name,
                "user_email": user_email,
                "expires_at": expires_at.isoformat(),
                "scopes": self.FACEBOOK_SCOPES
            }
    
    async def _get_user_pages(self, access_token: str) -> List[Dict[str, Any]]:
        """Get user's Facebook pages"""
        url = f"{self.base_url}/me/accounts"
        params = {
            'access_token': access_token,
            'fields': 'id,name,username,category,access_token'
        }
        
        response = requests.get(url, params=params)
        response.raise_for_status()
        
        data = response.json()
        return data.get('data', [])
    
    async def _get_user_ad_accounts(self, access_token: str) -> List[Dict[str, Any]]:
        """Get user's Facebook ad accounts"""
        url = f"{self.base_url}/me/adaccounts"
        params = {
            'access_token': access_token,
            'fields': 'id,name,currency,account_status'
        }
        
        response = requests.get(url, params=params)
        response.raise_for_status()
        
        data = response.json()
        return data.get('data', [])
    
    async def fetch_facebook_data(
        self,
        connection_id: int,
        data_type: str = "page_insights",
        start_date: str = "7daysAgo",
        end_date: str = "today",
        metrics: List[str] = None,
        limit: int = 100
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
            statement = select(Connection, DigitalAsset).join(
                DigitalAsset, Connection.digital_asset_id == DigitalAsset.id
            ).where(Connection.id == connection_id)
            
            result = session.exec(statement).first()
            if not result:
                raise ValueError(f"Connection {connection_id} not found")
            
            connection, asset = result
            
            # Check if token is expired
            if connection.expires_at and connection.expires_at < datetime.utcnow():
                raise ValueError("Facebook access token has expired. Please re-authenticate.")
            
            # Decrypt access token
            access_token = self._decrypt_token(connection.access_token_enc)
            
            # Update last used time
            connection.last_used_at = datetime.utcnow()
            session.add(connection)
            session.commit()
            
            # Fetch data based on type
            if data_type == "page_insights":
                return await self._fetch_page_insights(asset, access_token, start_date, end_date, metrics, limit)
            elif data_type == "ad_insights":
                return await self._fetch_ad_insights(asset, access_token, start_date, end_date, metrics, limit)
            elif data_type == "page_posts":
                return await self._fetch_page_posts(asset, access_token, start_date, end_date, limit)
            else:
                raise ValueError(f"Unsupported data type: {data_type}")
    
    async def _fetch_page_insights(
        self, 
        asset: DigitalAsset, 
        access_token: str, 
        start_date: str, 
        end_date: str, 
        metrics: List[str], 
        limit: int
    ) -> Dict[str, Any]:
        """Fetch page insights data"""
        
        if not metrics:
            metrics = [
                'page_impressions',
                'page_reach',
                'page_engaged_users',
                'page_post_engagements',
                'page_video_views',
                'page_fans'
            ]
        
        page_id = asset.meta.get('page_id')
        if not page_id:
            raise ValueError("Page ID not found in asset metadata")
        
        url = f"{self.base_url}/{page_id}/insights"
        params = {
            'access_token': access_token,
            'metric': ','.join(metrics),
            'period': 'day',
            'since': start_date,
            'until': end_date,
            'limit': limit
        }
        
        response = requests.get(url, params=params)
        response.raise_for_status()
        
        data = response.json()
        
        return {
            'data_type': 'page_insights',
            'page_id': page_id,
            'page_name': asset.name,
            'metrics': metrics,
            'date_range': {'start': start_date, 'end': end_date},
            'data': data.get('data', []),
            'paging': data.get('paging', {}),
            'timestamp': datetime.utcnow().isoformat()
        }
    
    async def _fetch_ad_insights(
        self, 
        asset: DigitalAsset, 
        access_token: str, 
        start_date: str, 
        end_date: str, 
        metrics: List[str], 
        limit: int
    ) -> Dict[str, Any]:
        """Fetch ad insights data"""
        
        if not metrics:
            metrics = [
                'impressions',
                'reach',
                'clicks',
                'spend',
                'cpm',
                'cpc',
                'ctr',
                'conversions'
            ]
        
        ad_account_id = asset.meta.get('ad_account_id')
        if not ad_account_id:
            raise ValueError("Ad account ID not found in asset metadata")
        
        url = f"{self.base_url}/{ad_account_id}/insights"
        params = {
            'access_token': access_token,
            'fields': ','.join(metrics),
            'time_range': json.dumps({
                'since': start_date,
                'until': end_date
            }),
            'level': 'account',
            'limit': limit
        }
        
        response = requests.get(url, params=params)
        response.raise_for_status()
        
        data = response.json()
        
        return {
            'data_type': 'ad_insights',
            'ad_account_id': ad_account_id,
            'ad_account_name': asset.name,
            'metrics': metrics,
            'date_range': {'start': start_date, 'end': end_date},
            'data': data.get('data', []),
            'paging': data.get('paging', {}),
            'timestamp': datetime.utcnow().isoformat()
        }
    
    async def _fetch_page_posts(
        self, 
        asset: DigitalAsset, 
        access_token: str, 
        start_date: str, 
        end_date: str, 
        limit: int
    ) -> Dict[str, Any]:
        """Fetch page posts data"""
        
        page_id = asset.meta.get('page_id')
        if not page_id:
            raise ValueError("Page ID not found in asset metadata")
        
        url = f"{self.base_url}/{page_id}/posts"
        params = {
            'access_token': access_token,
            'fields': 'id,message,created_time,type,permalink_url,insights.metric(post_impressions,post_engaged_users,post_clicks)',
            'limit': limit
        }
        
        response = requests.get(url, params=params)
        response.raise_for_status()
        
        data = response.json()
        
        return {
            'data_type': 'page_posts',
            'page_id': page_id,
            'page_name': asset.name,
            'date_range': {'start': start_date, 'end': end_date},
            'data': data.get('data', []),
            'paging': data.get('paging', {}),
            'timestamp': datetime.utcnow().isoformat()
        }
    
    async def refresh_facebook_token(self, connection_id: int) -> Dict[str, Any]:
        """Refresh Facebook access token using stored connection"""
        
        with get_session() as session:
            # Get connection with digital asset
            statement = select(Connection, DigitalAsset).join(
                DigitalAsset, Connection.digital_asset_id == DigitalAsset.id
            ).where(
                and_(
                    Connection.id == connection_id,
                    Connection.revoked == False
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
            if connection.expires_at and connection.expires_at < datetime.utcnow() + buffer_time:
                print(f"🔄 Facebook token expired or expiring soon, refreshing...")
                
                # For Facebook, we need to get a new long-lived token
                # Facebook doesn't have refresh tokens like Google, so we need to re-authenticate
                # For now, we'll return an error asking for re-authentication
                raise ValueError("Facebook token has expired. Please re-authenticate your Facebook account.")
            
            # Update last used time
            connection.last_used_at = datetime.utcnow()
            session.add(connection)
            session.commit()
            
            return {
                "access_token": access_token,
                "expires_at": connection.expires_at.isoformat() if connection.expires_at else None,
                "connection_id": connection_id,
                "asset_name": digital_asset.name,
                "asset_type": digital_asset.asset_type
            }
    
    async def get_facebook_connection_for_user(self, user_id: int, subclient_id: int, asset_type: str = "SOCIAL_MEDIA") -> Optional[Dict[str, Any]]:
        """Get active Facebook connection for user/subclient with token refresh"""
        
        with get_session() as session:
            # Look for Facebook connections
            statement = select(Connection, DigitalAsset).join(
                DigitalAsset, Connection.digital_asset_id == DigitalAsset.id
            ).where(
                and_(
                    Connection.user_id == user_id,
                    DigitalAsset.subclient_id == subclient_id,
                    DigitalAsset.provider == "Facebook",
                    DigitalAsset.asset_type == asset_type,
                    Connection.revoked == False
                )
            )
            
            result = session.exec(statement).first()
            if not result:
                return None
            
            connection, digital_asset = result
            
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
                    "expires_at": refreshed_token["expires_at"]
                }
            except ValueError as e:
                if "expired" in str(e).lower():
                    return {
                        "error": "Facebook token has expired. Please re-authenticate your Facebook account.",
                        "connection_id": connection.id,
                        "digital_asset_id": digital_asset.id,
                        "asset_name": digital_asset.name,
                        "requires_reauth": True
                    }
                else:
                    raise e