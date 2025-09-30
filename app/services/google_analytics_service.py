"""
Google Analytics OAuth and data fetching service
Handles token storage, refresh, and GA4 API calls
"""

import json
import hashlib
import base64
from datetime import datetime, timedelta
import os
from typing import Dict, Any, Optional, List
from cryptography.fernet import Fernet
from google.oauth2.credentials import Credentials
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    RunReportRequest,
    DateRange,
    Dimension,
    Metric,
    OrderBy
)
from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException
from google.auth.transport.requests import Request
from sqlmodel import select, and_

from app.config.database import get_session
from app.models.analytics import DigitalAsset, Connection, AssetType, AuthType
from app.models.users import User
from app.core.security import get_secret_key
from app.config.settings import get_settings

# Google client functions
def get_google_client_id() -> str:
    from dotenv import load_dotenv
    load_dotenv()  # Ensure .env is loaded
    return os.getenv("GOOGLE_CLIENT_ID", "")

def get_google_client_secret() -> str:
    from dotenv import load_dotenv
    load_dotenv()  # Ensure .env is loaded
    return os.getenv("GOOGLE_CLIENT_SECRET", "")


class GoogleAnalyticsService:
    """Service for managing Google Analytics OAuth and data fetching"""
    
    # Google Analytics 4 scopes - comprehensive set for modern GA4 API
    GA4_SCOPES = [
        'https://www.googleapis.com/auth/analytics.readonly',
        'https://www.googleapis.com/auth/analytics',  # Full analytics access for data API
        'https://www.googleapis.com/auth/analytics.manage.users.readonly',
        'https://www.googleapis.com/auth/userinfo.email',  # User email for account identification
        'https://www.googleapis.com/auth/userinfo.profile',  # User profile for account identification
        'openid'  # OpenID Connect for authentication
    ]
    
    # Google Ads scopes - for advertising data access
    GOOGLE_ADS_SCOPES = [
        'https://www.googleapis.com/auth/adwords',
        'https://www.googleapis.com/auth/adsdatahub'
    ]
    
    # Combined scopes for both Analytics and Ads
    COMBINED_SCOPES = GA4_SCOPES + GOOGLE_ADS_SCOPES
    
    def __init__(self):
        self.encryption_key = self._get_encryption_key()
        self.cipher_suite = Fernet(self.encryption_key)
    
    def _get_encryption_key(self) -> bytes:
        """Get encryption key for token storage - uses GOOGLE_CLIENT_SECRET"""
        # Use GOOGLE_CLIENT_SECRET as encryption key (pad to 32 bytes if needed)
        client_secret = get_google_client_secret()
        secret_key = client_secret.encode('utf-8')
        if len(secret_key) < 32:
            secret_key = secret_key.ljust(32, b'0')  # Pad with zeros
        elif len(secret_key) > 32:
            secret_key = secret_key[:32]  # Truncate to 32 bytes
        return base64.urlsafe_b64encode(secret_key)
    
    def _encrypt_token(self, token: str) -> bytes:
        """Encrypt token for secure storage"""
        return self.cipher_suite.encrypt(token.encode())
    
    def _decrypt_token(self, encrypted_token: bytes) -> str:
        """Decrypt token for use"""
        try:
            return self.cipher_suite.decrypt(encrypted_token).decode()
        except Exception as e:
            print(f"Warning: Failed to decrypt token with current key: {e}")
            # Try with the old encryption method as fallback
            try:
                # Use the old fixed key method
                old_key = base64.urlsafe_b64encode(b"sato-analytics-token-encryption-key-2025".ljust(32, b'0')[:32])
                old_cipher = Fernet(old_key)
                return old_cipher.decrypt(encrypted_token).decode()
            except Exception as e2:
                print(f"Warning: Failed to decrypt token with old key too: {e2}")
                raise e  # Re-raise the original error
    
    def _generate_token_hash(self, token: str) -> str:
        """Generate hash for token validation"""
        return hashlib.sha256(token.encode()).hexdigest()
    
    async def save_ga_connection(
        self,
        user_id: int,
        subclient_id: int,
        access_token: str,
        refresh_token: str,
        expires_in: int,
        account_email: str
    ) -> Dict[str, Any]:
        """
        Save Google Analytics OAuth connection to database
        
        Args:
            user_id: ID of user creating the connection
            subclient_id: ID of subclient this asset belongs to
            property_id: GA4 property ID (e.g., "123456789")
            property_name: Human-readable property name
            access_token: OAuth access token
            refresh_token: OAuth refresh token
            expires_in: Token expiration time in seconds
            account_email: Google account email
        """
        
        # For now, use demo data - in the future this will fetch real GA4 properties
        property_id = f"ga4-property-{user_id}-{subclient_id}"
        property_name = f"Google Analytics Property for {account_email}"
        
        with get_session() as session:
            # Check if digital asset already exists
            statement = select(DigitalAsset).where(
                and_(
                    DigitalAsset.subclient_id == subclient_id,
                    DigitalAsset.asset_type == AssetType.ANALYTICS,
                    DigitalAsset.provider == "Google",
                    DigitalAsset.external_id == property_id
                )
            )
            digital_asset = session.exec(statement).first()
            
            if not digital_asset:
                # Create new digital asset
                digital_asset = DigitalAsset(
                    subclient_id=subclient_id,
                    asset_type=AssetType.ANALYTICS,
                    provider="Google",
                    name=property_name,
                    external_id=property_id,
                    meta={
                        "property_id": property_id,
                        "account_email": account_email,
                        "is_demo": True,  # Mark as demo data
                        "note": "This is demo data. Real GA4 properties will be fetched in future updates."
                    },
                    is_active=True
                )
                session.add(digital_asset)
                session.commit()
                session.refresh(digital_asset)
            
            # Encrypt tokens
            access_token_enc = self._encrypt_token(access_token)
            refresh_token_enc = self._encrypt_token(refresh_token)
            token_hash = self._generate_token_hash(access_token)
            
            # Calculate expiration time
            expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
            
            # Create or update connection
            connection_statement = select(Connection).where(
                and_(
                    Connection.digital_asset_id == digital_asset.id,
                    Connection.user_id == user_id,
                    Connection.revoked == False
                )
            )
            connection = session.exec(connection_statement).first()
            
            if connection:
                # Update existing connection
                connection.access_token_enc = access_token_enc
                connection.refresh_token_enc = refresh_token_enc
                connection.token_hash = token_hash
                connection.expires_at = expires_at
                connection.account_email = account_email
                connection.scopes = self.GA4_SCOPES
                connection.rotated_at = datetime.utcnow()
                connection.last_used_at = datetime.utcnow()
            else:
                # Create new connection
                connection = Connection(
                    digital_asset_id=digital_asset.id,
                    user_id=user_id,
                    auth_type=AuthType.OAUTH2,
                    account_email=account_email,
                    scopes=self.GA4_SCOPES,
                    access_token_enc=access_token_enc,
                    refresh_token_enc=refresh_token_enc,
                    token_hash=token_hash,
                    expires_at=expires_at,
                    revoked=False,
                    last_used_at=datetime.utcnow()
                )
            
            session.add(connection)
            session.commit()
            session.refresh(connection)
            
            return {
                "connection_id": connection.id,
                "digital_asset_id": digital_asset.id,
                "property_id": property_id,
                "property_name": property_name,
                "account_email": account_email,
                "expires_at": expires_at.isoformat(),
                "scopes": self.GA4_SCOPES
            }
    
    async def save_ga_connection_with_property(
        self,
        user_id: int,
        subclient_id: int,
        property_id: str,
        property_name: str,
        account_id: str,
        account_name: str,
        access_token: str,
        refresh_token: str,
        expires_in: int,
        account_email: str
    ) -> Dict[str, Any]:
        """
        Save Google Analytics OAuth connection with specific property details
        """
        
        with get_session() as session:
            # Check if digital asset already exists
            statement = select(DigitalAsset).where(
                and_(
                    DigitalAsset.subclient_id == subclient_id,
                    DigitalAsset.asset_type == AssetType.ANALYTICS,
                    DigitalAsset.provider == "Google",
                    DigitalAsset.external_id == property_id
                )
            )
            digital_asset = session.exec(statement).first()
            
            if not digital_asset:
                print(f"DEBUG: Creating new digital asset for property {property_id}")
                # Create new digital asset with real property details
                digital_asset = DigitalAsset(
                    subclient_id=subclient_id,
                    asset_type=AssetType.ANALYTICS,
                    provider="Google",
                    name=property_name,
                    external_id=property_id,
                    meta={
                        "property_id": property_id,
                        "property_name": property_name,
                        "account_id": account_id,
                        "account_name": account_name,
                        "account_email": account_email,
                        "is_demo": False,  # This is real data
                        "created_via": "oauth_flow"
                    },
                    is_active=True
                )
                session.add(digital_asset)
                session.commit()
                session.refresh(digital_asset)
            else:
                print(f"DEBUG: Using existing digital asset {digital_asset.id} for property {property_id}")
                # Update metadata if needed
                if digital_asset.meta.get("property_name") != property_name:
                    digital_asset.meta.update({
                        "property_name": property_name,
                        "account_id": account_id,
                        "account_name": account_name,
                        "account_email": account_email
                    })
                    session.add(digital_asset)
                    session.commit()
            
            # Encrypt tokens
            access_token_enc = self._encrypt_token(access_token)
            refresh_token_enc = self._encrypt_token(refresh_token)
            token_hash = self._generate_token_hash(access_token)
            
            # Calculate expiration time
            expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
            
            # Check for existing connection first
            connection_statement = select(Connection).where(
                and_(
                    Connection.digital_asset_id == digital_asset.id,
                    Connection.user_id == user_id,
                    Connection.revoked == False
                )
            )
            connection = session.exec(connection_statement).first()
            
            if connection:
                print(f"DEBUG: Updating existing connection {connection.id}")
                # Update existing connection with new tokens
                connection.access_token_enc = access_token_enc
                connection.refresh_token_enc = refresh_token_enc
                connection.token_hash = token_hash
                connection.expires_at = expires_at
                connection.account_email = account_email
                connection.scopes = self.GA4_SCOPES
                connection.rotated_at = datetime.utcnow()
                connection.last_used_at = datetime.utcnow()
            else:
                print(f"DEBUG: Creating new connection for user {user_id} and asset {digital_asset.id}")
                # Create new connection
                connection = Connection(
                    digital_asset_id=digital_asset.id,
                    user_id=user_id,
                    auth_type=AuthType.OAUTH2,
                    account_email=account_email,
                    scopes=self.GA4_SCOPES,
                    access_token_enc=access_token_enc,
                    refresh_token_enc=refresh_token_enc,
                    token_hash=token_hash,
                    expires_at=expires_at,
                    revoked=False,
                    last_used_at=datetime.utcnow()
                )
            
            session.add(connection)
            session.commit()
            session.refresh(connection)
            
            return {
                "connection_id": connection.id,
                "digital_asset_id": digital_asset.id,
                "property_id": property_id,
                "property_name": property_name,
                "account_email": account_email,
                "expires_at": expires_at.isoformat(),
                "scopes": self.GA4_SCOPES
            }
    
    async def refresh_ga_token(self, connection_id: int) -> Dict[str, Any]:
        """Refresh Google Analytics access token using refresh token"""
        
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
            
            # Decrypt refresh token
            refresh_token = self._decrypt_token(connection.refresh_token_enc)
            
            # Create credentials and refresh
            credentials = Credentials(
                token=None,
                refresh_token=refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=get_google_client_id(),
                client_secret=get_google_client_secret(),
                scopes=self.GA4_SCOPES
            )
            
            try:
                # Refresh the token
                credentials.refresh(Request())
                
                # Encrypt new tokens
                access_token_enc = self._encrypt_token(credentials.token)
                refresh_token_enc = self._encrypt_token(credentials.refresh_token)
                token_hash = self._generate_token_hash(credentials.token)
                
                # Update connection
                connection.access_token_enc = access_token_enc
                connection.refresh_token_enc = refresh_token_enc
                connection.token_hash = token_hash
                connection.expires_at = datetime.utcnow() + timedelta(seconds=3600)  # 1 hour
                connection.rotated_at = datetime.utcnow()
                connection.last_used_at = datetime.utcnow()
                
                session.add(connection)
                session.commit()
                
                return {
                    "access_token": credentials.token,
                    "expires_at": connection.expires_at.isoformat(),
                    "rotated_at": connection.rotated_at.isoformat()
                }
                
            except Exception as e:
                # If refresh fails (invalid_scope, expired refresh token, etc.)
                print(f"⚠️ Token refresh failed for connection {connection_id}: {e}")
                
                # Try automatic token renewal first
                try:
                    print(f"🔄 Attempting automatic token renewal for connection {connection_id}...")
                    renewed = await self.automatic_token_renewal(connection_id, connection, digital_asset)
                    if renewed:
                        print(f"✅ Automatic token renewal successful!")
                        return renewed
                except Exception as renewal_error:
                    print(f"❌ Automatic renewal failed: {renewal_error}")
                
                # If automatic renewal fails, generate re-auth URL and fail clearly
                reauth_url = self.generate_reauth_url(connection_id, connection.account_email)
                raise ValueError(f"GA4 token refresh failed. Please re-authorize your Google Analytics connection: {reauth_url}")

    def generate_reauth_url(self, connection_id: int, user_email: str) -> str:
        """Generate a new OAuth URL for re-authorization when refresh tokens are invalid"""
        from urllib.parse import urlencode
        import secrets
        
        # Generate state parameter for security
        state = secrets.token_urlsafe(32)
        
        # OAuth parameters
        settings = get_settings()
        params = {
            'client_id': get_google_client_id(),
            'redirect_uri': f'{settings.frontend_url}/auth/ga-callback',
            'response_type': 'code',
            'scope': ' '.join(self.GA4_SCOPES),
            'access_type': 'offline',
            'prompt': 'consent',  # Force consent screen to get new refresh token
            'state': f"{state}|connection_id:{connection_id}|user:{user_email}",
            'include_granted_scopes': 'true'
        }
        
        return f"https://accounts.google.com/o/oauth2/auth?{urlencode(params)}"
    
    async def update_connection_tokens(
        self, 
        connection_id: int, 
        access_token: str, 
        refresh_token: str, 
        expires_in: int = 3600
    ) -> Dict[str, Any]:
        """Update existing connection with fresh OAuth tokens"""
        
        print(f"🔄 Updating connection {connection_id} with fresh tokens...")
        
        with get_session() as session:
            # Get the connection
            connection = session.get(Connection, connection_id)
            if not connection:
                raise ValueError(f"Connection {connection_id} not found")
            
            # Encrypt new tokens
            access_token_enc = self._encrypt_token(access_token)
            refresh_token_enc = self._encrypt_token(refresh_token)
            token_hash = self._generate_token_hash(access_token)
            
            # Calculate expiry
            expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
            
            # Update connection
            connection.access_token_enc = access_token_enc
            connection.refresh_token_enc = refresh_token_enc
            connection.token_hash = token_hash
            connection.expires_at = expires_at
            connection.rotated_at = datetime.utcnow()
            connection.last_used_at = datetime.utcnow()
            connection.revoked = False  # Ensure it's not marked as revoked
            
            session.add(connection)
            session.commit()
            
            print(f"✅ Connection {connection_id} updated with fresh tokens")
            print(f"   Expires at: {expires_at}")
            
            return {
                "connection_id": connection_id,
                "expires_at": expires_at.isoformat(),
                "rotated_at": connection.rotated_at.isoformat(),
                "success": True
            }
    
    async def update_connection_scopes(self, connection_id: int) -> Dict[str, Any]:
        """Update existing connection to use comprehensive GA4 scopes"""
        
        print(f"🔧 Updating connection {connection_id} to use comprehensive GA4 scopes...")
        
        with get_session() as session:
            # Get the connection
            connection = session.get(Connection, connection_id)
            if not connection:
                raise ValueError(f"Connection {connection_id} not found")
            
            # Try to refresh with comprehensive scopes
            try:
                # Decrypt existing refresh token
                refresh_token = self._decrypt_token(connection.refresh_token_enc)
                
                # Create credentials with comprehensive scopes
                credentials = Credentials(
                    token=None,
                    refresh_token=refresh_token,
                    token_uri="https://oauth2.googleapis.com/token",
                    client_id=get_google_client_id(),
                    client_secret=get_google_client_secret(),
                    scopes=self.GA4_SCOPES  # Use comprehensive scopes
                )
                
                # Try to refresh with new scopes
                credentials.refresh(Request())
                
                # If successful, update the connection
                access_token_enc = self._encrypt_token(credentials.token)
                refresh_token_enc = self._encrypt_token(credentials.refresh_token)
                token_hash = self._generate_token_hash(credentials.token)
                expires_at = datetime.utcnow() + timedelta(seconds=3600)
                
                # Update connection
                connection.access_token_enc = access_token_enc
                connection.refresh_token_enc = refresh_token_enc
                connection.token_hash = token_hash
                connection.expires_at = expires_at
                connection.rotated_at = datetime.utcnow()
                connection.last_used_at = datetime.utcnow()
                connection.revoked = False
                
                session.add(connection)
                session.commit()
                
                print(f"✅ Connection {connection_id} updated with comprehensive scopes")
                print(f"   New scopes: {', '.join(self.GA4_SCOPES)}")
                print(f"   Expires at: {expires_at}")
                
                return {
                    "success": True,
                    "connection_id": connection_id,
                    "expires_at": expires_at.isoformat(),
                    "rotated_at": connection.rotated_at.isoformat(),
                    "scopes": self.GA4_SCOPES
                }
                
            except Exception as e:
                print(f"❌ Failed to update scopes for connection {connection_id}: {e}")
                # Generate re-auth URL with comprehensive scopes
                reauth_url = self.generate_reauth_url(connection_id, "user@example.com")
                
                return {
                    "success": False,
                    "requires_reauth": True,
                    "reauth_url": reauth_url,
                    "error": str(e),
                    "message": "Refresh token expired. Please re-authorize with comprehensive scopes."
                }

    async def automatic_token_renewal(self, connection_id: int, connection, digital_asset) -> Dict[str, Any]:
        """
        Automatically renew tokens programmatically for B2B systems
        This method attempts to get fresh tokens without user intervention
        """
        print(f"🤖 Starting automatic token renewal for connection {connection_id}")
        
        # For Google Analytics, when refresh tokens fail with invalid_scope,
        # it usually means the scopes have changed or the refresh token is too old
        
        # Method 1: Try with different scopes
        try:
            print("🔄 Method 1: Trying token refresh with updated scopes...")
            
            # Use the same scopes as the original connection
            updated_scopes = self.GA4_SCOPES
            
            # Decrypt refresh token
            refresh_token = self._decrypt_token(connection.refresh_token_enc)
            
            # Create credentials with updated scopes
            credentials = Credentials(
                token=None,
                refresh_token=refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=get_google_client_id(),
                client_secret=get_google_client_secret(),
                scopes=updated_scopes
            )
            
            # Try to refresh with new scopes
            credentials.refresh(Request())
            
            # If successful, update the connection
            with get_session() as new_session:
                # Get a fresh connection object in the new session
                fresh_connection = new_session.get(Connection, connection_id)
                if fresh_connection:
                    # Encrypt new tokens
                    access_token_enc = self._encrypt_token(credentials.token)
                    refresh_token_enc = self._encrypt_token(credentials.refresh_token)
                    token_hash = self._generate_token_hash(credentials.token)
                    
                    # Update connection
                    fresh_connection.access_token_enc = access_token_enc
                    fresh_connection.refresh_token_enc = refresh_token_enc
                    fresh_connection.token_hash = token_hash
                    fresh_connection.expires_at = datetime.utcnow() + timedelta(seconds=3600)  # 1 hour
                    fresh_connection.rotated_at = datetime.utcnow()
                    fresh_connection.last_used_at = datetime.utcnow()
                    
                    new_session.add(fresh_connection)
                    new_session.commit()
                
                print("✅ Method 1 successful: Token renewed with updated scopes")
                return {
                    "access_token": credentials.token,
                    "expires_at": connection.expires_at.isoformat(),
                    "rotated_at": connection.rotated_at.isoformat(),
                    "renewal_method": "updated_scopes"
                }
                
        except Exception as e1:
            print(f"❌ Method 1 failed: {e1}")
        
        # Method 2: Check if we have a backup refresh token or service account
        try:
            print("🔄 Method 2: Checking for service account credentials...")
            
            # In B2B systems, you might have service account credentials
            # that can be used to maintain access without user intervention
            service_account_path = os.getenv("GOOGLE_SERVICE_ACCOUNT_PATH")
            if service_account_path and os.path.exists(service_account_path):
                print("🔑 Found service account credentials, attempting renewal...")
                # This would require implementing service account delegation
                # For now, we'll skip this method
                raise Exception("Service account delegation not implemented yet")
                
        except Exception as e2:
            print(f"❌ Method 2 failed: {e2}")
        
        # Method 3: All automatic renewal methods failed - require manual re-authorization
        print("❌ All automatic renewal methods failed - manual re-authorization required")
        
        # Mark connection as needing manual renewal
        with get_session() as new_session:
            fresh_connection = new_session.get(Connection, connection_id)
            if fresh_connection:
                fresh_connection.last_used_at = datetime.utcnow()
                new_session.add(fresh_connection)
                new_session.commit()
        
        # Return failure - no fake success
        raise ValueError("All automatic token renewal methods failed. Manual re-authorization required.")
    
    async def get_ga_credentials(self, connection_id: int) -> Credentials:
        """Get valid Google Analytics credentials for API calls"""
        
        with get_session() as session:
            # Get connection
            statement = select(Connection).where(
                and_(
                    Connection.id == connection_id,
                    Connection.revoked == False
                )
            )
            connection = session.exec(statement).first()
            
            if not connection:
                raise ValueError("Connection not found or revoked")
            
            # Check if token needs refresh
            if connection.expires_at and connection.expires_at <= datetime.utcnow():
                # Refresh token
                await self.refresh_ga_token(connection_id)
                # Reload connection
                connection = session.exec(statement).first()
            
            # Decrypt tokens
            access_token = self._decrypt_token(connection.access_token_enc)
            refresh_token = self._decrypt_token(connection.refresh_token_enc)
            
            # Create credentials
            credentials = Credentials(
                token=access_token,
                refresh_token=refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=get_google_client_id(),
                client_secret=get_google_client_secret(),
                scopes=self.GA4_SCOPES
            )
            
            # Update last used time
            connection.last_used_at = datetime.utcnow()
            session.add(connection)
            session.commit()
            
            return credentials
    
    async def fetch_ga4_data(
        self,
        connection_id: int,
        property_id: str,
        metrics: List[str],
        dimensions: List[str] = None,
        start_date: str = "7daysAgo",
        end_date: str = "today",
        limit: int = 1000
    ) -> Dict[str, Any]:
        """
        Fetch data from Google Analytics 4
        
        Args:
            connection_id: Database connection ID
            property_id: GA4 property ID
            metrics: List of metrics to fetch
            dimensions: List of dimensions to fetch
            start_date: Start date in YYYY-MM-DD format or relative (e.g., "7daysAgo")
            end_date: End date in YYYY-MM-DD format or relative (e.g., "today")
            limit: Maximum number of rows to return
        """
        
        try:
            # Get valid credentials
            credentials = await self.get_ga_credentials(connection_id)
            
            # Initialize GA4 client
            client = BetaAnalyticsDataClient(credentials=credentials)
            
            # Build request
            request = RunReportRequest(
                property=f"properties/{property_id}",
                dimensions=[Dimension(name=dim) for dim in (dimensions or [])],
                metrics=[Metric(name=metric) for metric in metrics],
                date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
                limit=limit
            )
            
            # Execute request
            response = client.run_report(request=request)
            
            # Parse response
            result = {
                "dimension_headers": [header.name for header in response.dimension_headers],
                "metric_headers": [header.name for header in response.metric_headers],
                "rows": [],
                "row_count": response.row_count,
                "totals": []
            }
            
            # Parse rows
            for row in response.rows:
                row_data = {
                    "dimension_values": [value.value for value in row.dimension_values],
                    "metric_values": [value.value for value in row.metric_values]
                }
                result["rows"].append(row_data)
            
            # Parse totals
            for total in response.totals:
                total_data = {
                    "metric_values": [value.value for value in total.metric_values]
                }
                result["totals"].append(total_data)
            
            return result
            
        except Exception as e:
            print(f"Error in fetch_ga4_data: {str(e)}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": str(e),
                "dimension_headers": [],
                "metric_headers": [],
                "rows": [],
                "row_count": 0,
                "totals": []
            }
    
    async def get_user_ga_connections(self, user_id: int) -> List[Dict[str, Any]]:
        """Get all GA connections for a user"""
        
        with get_session() as session:
            statement = select(Connection, DigitalAsset).join(
                DigitalAsset, Connection.digital_asset_id == DigitalAsset.id
            ).where(
                and_(
                    Connection.user_id == user_id,
                    DigitalAsset.asset_type == AssetType.ANALYTICS,
                    DigitalAsset.provider == "Google",
                    Connection.revoked == False
                )
            )
            
            results = session.exec(statement).all()
            
            connections = []
            for connection, digital_asset in results:
                connections.append({
                    "connection_id": connection.id,
                    "digital_asset_id": digital_asset.id,
                    "property_id": digital_asset.external_id,
                    "property_name": digital_asset.name,
                    "account_email": connection.account_email,
                    "expires_at": connection.expires_at.isoformat() if connection.expires_at else None,
                    "last_used_at": connection.last_used_at.isoformat() if connection.last_used_at else None,
                    "is_active": digital_asset.is_active
                })
            
            return connections
    

    async def get_user_connections(self, user_id: int) -> List[Dict[str, Any]]:
        """Get user connections for webhook processing"""
        return await self.get_user_ga_connections(user_id)
    
    async def revoke_ga_connection(self, connection_id: int) -> bool:
        """Revoke a GA connection"""
        
        with get_session() as session:
            statement = select(Connection).where(Connection.id == connection_id)
            connection = session.exec(statement).first()
            
            if not connection:
                return False
            
            connection.revoked = True
            connection.rotated_at = datetime.utcnow()
            
            session.add(connection)
            session.commit()
            
            return True
    
    # Google Ads functionality integrated into this service
    async def get_google_ads_accounts(self, connection_id: int) -> List[Dict[str, Any]]:
        """Get Google Ads accounts accessible to the user"""
        
        try:
            with get_session() as session:
                # Get connection
                connection = session.get(Connection, connection_id)
                if not connection:
                    return []
                
                # Check if token needs refresh
                if connection.expires_at and connection.expires_at <= datetime.utcnow() + timedelta(minutes=5):
                    refresh_result = await self.refresh_ga_token(connection_id)
                    if not refresh_result.get("access_token"):
                        return []
                
                # Decrypt access token
                access_token = self._decrypt_token(connection.access_token_enc)
                
                # Get Google Ads developer token
                developer_token = os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN", os.getenv("GOOGLE_DEVELOPER_TOKEN", ""))
                if not developer_token:
                    raise ValueError("Google Ads developer token not configured")
                
                # Create Google Ads client
                client = GoogleAdsClient.load_from_dict({
                    "developer_token": developer_token,
                    "client_id": get_google_client_id(),
                    "client_secret": get_google_client_secret(),
                    "refresh_token": connection.refresh_token_enc,
                    "use_proto_plus": True
                })
                
                # Get customer service
                customer_service = client.get_service("CustomerService")
                
                # List accessible customers
                accessible_customers = customer_service.list_accessible_customers()
                
                accounts = []
                for customer_resource in accessible_customers.resource_names:
                    customer_id = customer_resource.split("/")[-1]
                    
                    # Get customer details
                    try:
                        customer = customer_service.get_customer(resource_name=customer_resource)
                        accounts.append({
                            "customer_id": customer_id,
                            "descriptive_name": customer.descriptive_name,
                            "currency_code": customer.currency_code,
                            "time_zone": customer.time_zone,
                            "manager": customer.manager,
                            "test_account": customer.test_account
                        })
                    except GoogleAdsException as e:
                        print(f"Error getting customer {customer_id}: {e}")
                        continue
                
                return accounts
                
        except Exception as e:
            print(f"Error getting Google Ads accounts: {e}")
            return []
    
    async def fetch_google_ads_data(
        self,
        connection_id: int,
        customer_id: str,
        metrics: List[str],
        dimensions: List[str],
        start_date: str,
        end_date: str,
        limit: int = 100
    ) -> Dict[str, Any]:
        """Fetch Google Ads data for analysis"""
        
        try:
            with get_session() as session:
                # Get connection
                connection = session.get(Connection, connection_id)
                if not connection:
                    return {"success": False, "error": "Connection not found"}
                
                # Check if token needs refresh
                if connection.expires_at and connection.expires_at <= datetime.utcnow() + timedelta(minutes=5):
                    refresh_result = await self.refresh_ga_token(connection_id)
                    if not refresh_result.get("access_token"):
                        return {"success": False, "error": "Token refresh failed"}
                
                # Decrypt access token
                access_token = self._decrypt_token(connection.access_token_enc)
                
                # Get Google Ads developer token
                developer_token = os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN", os.getenv("GOOGLE_DEVELOPER_TOKEN", ""))
                if not developer_token:
                    return {"success": False, "error": "Google Ads developer token not configured"}
                
                # Create Google Ads client
                client = GoogleAdsClient.load_from_dict({
                    "developer_token": developer_token,
                    "client_id": get_google_client_id(),
                    "client_secret": get_google_client_secret(),
                    "refresh_token": connection.refresh_token_enc,
                    "use_proto_plus": True
                })
                
                # Get Google Ads service
                ga_service = client.get_service("GoogleAdsService")
                
                # Build query
                query = f"""
                    SELECT {', '.join(metrics + dimensions)}
                    FROM campaign
                    WHERE segments.date BETWEEN '{start_date}' AND '{end_date}'
                    ORDER BY segments.date DESC
                    LIMIT {limit}
                """
                
                # Execute query
                response = ga_service.search(customer_id=customer_id, query=query)
                
                # Process results
                rows = []
                for row in response:
                    row_data = {}
                    
                    # Add metrics
                    for metric in metrics:
                        if hasattr(row, metric):
                            row_data[metric] = str(getattr(row, metric))
                    
                    # Add dimensions
                    for dimension in dimensions:
                        if hasattr(row, dimension):
                            row_data[dimension] = str(getattr(row, dimension))
                    
                    rows.append(row_data)
                
                return {
                    "success": True,
                    "rows": rows,
                    "row_count": len(rows),
                    "metrics": metrics,
                    "dimensions": dimensions,
                    "date_range": {"start": start_date, "end": end_date}
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
