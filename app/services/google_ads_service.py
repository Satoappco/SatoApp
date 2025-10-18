"""
Google Ads OAuth and data fetching service
Handles token storage, refresh, and Google Ads API calls
"""

import json
import hashlib
import base64
from datetime import datetime, timedelta
import os
import asyncio
from typing import Dict, Any, Optional, List
from cryptography.fernet import Fernet
from google.oauth2.credentials import Credentials
from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException
from google.auth.transport.requests import Request
from sqlmodel import select, and_

from app.config.database import get_session
from app.models.analytics import DigitalAsset, Connection, AssetType, AuthType
from app.models.users import Campaigner
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


class GoogleAdsService:
    """Service for managing Google Ads OAuth and data fetching"""
    
    # Class-level refresh locks to prevent simultaneous token refresh attempts
    _refresh_locks = {}
    
    # Google Ads scopes - for advertising data access
    GOOGLE_ADS_SCOPES = [
        'https://www.googleapis.com/auth/adwords',
        'https://www.googleapis.com/auth/adsdatahub',
        'https://www.googleapis.com/auth/userinfo.email',  # User email for account identification
        'https://www.googleapis.com/auth/userinfo.profile',  # User profile for account identification
        'openid'  # OpenID Connect for authentication
    ]
    
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
    
    def _decrypt_token(self, encrypted_token) -> str:
        """Decrypt token for use"""
        # Validate input
        if encrypted_token is None:
            raise ValueError("Encrypted token is None - connection may not be properly initialized")
        
        if not isinstance(encrypted_token, (bytes, str)):
            raise ValueError(f"Encrypted token must be bytes or str, got {type(encrypted_token)}")
        
        # Convert to bytes if it's a string
        if isinstance(encrypted_token, str):
            try:
                encrypted_token = encrypted_token.encode('utf-8')
            except Exception as e:
                raise ValueError(f"Failed to convert string token to bytes: {e}")
        
        try:
            decrypted_bytes = self.cipher_suite.decrypt(encrypted_token)
            return decrypted_bytes.decode('utf-8')
        except Exception as e:
            raise ValueError(f"Failed to decrypt token: {e}")
    
    def _generate_token_hash(self, token: str) -> str:
        """Generate hash for token validation"""
        return hashlib.sha256(token.encode()).hexdigest()
    
    
    async def save_google_ads_connection(
        self,
        campaigner_id: int,
        customer_id: int,
        account_id: str,
        account_name: str,
        access_token: str,
        refresh_token: str,
        expires_in: int,
        account_email: str
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
        
        print(f"🔄 Creating Google Ads connection for account {account_id} ({account_name})")
        
        with get_session() as session:
            # First, find or create the digital asset
            digital_asset_statement = select(DigitalAsset).where(
                and_(
                    DigitalAsset.customer_id == customer_id,
                    DigitalAsset.asset_type == AssetType.GOOGLE_ADS,
                    DigitalAsset.external_id == account_id
                )
            )
            digital_asset = session.exec(digital_asset_statement).first()
            
            if not digital_asset:
                # Create new digital asset
                digital_asset = DigitalAsset(
                    customer_id=customer_id,
                    asset_type=AssetType.GOOGLE_ADS,
                    provider="Google",
                    name=account_name,
                    handle=None,  # Google Ads doesn't have handles
                    url=f"https://ads.google.com/aw/overview?ocid={account_id}",
                    external_id=account_id,
                    meta={
                        "account_id": account_id,
                        "currency_code": "USD",  # Default, will be updated from API
                        "time_zone": "America/New_York"  # Default, will be updated from API
                    },
                    is_active=True
                )
                session.add(digital_asset)
                session.commit()
                session.refresh(digital_asset)
            else:
                # Activate existing asset
                digital_asset.is_active = True
                digital_asset.name = account_name  # Update name in case it changed
                session.add(digital_asset)
                session.commit()
            
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
                    Connection.campaigner_id == campaigner_id,
                    Connection.auth_type == AuthType.OAUTH2
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
                connection.scopes = self.GOOGLE_ADS_SCOPES
                connection.rotated_at = datetime.utcnow()
                connection.last_used_at = datetime.utcnow()
                connection.revoked = False
            else:
                # Create new connection
                connection = Connection(
                    digital_asset_id=digital_asset.id,
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
                    last_used_at=datetime.utcnow()
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
                    property_name=account_name
                )
                print(f"DEBUG: Automatically saved Google Ads account selection for {account_name}")
            except Exception as e:
                print(f"DEBUG: Failed to save Google Ads account selection: {e}")
                # Don't fail the connection creation if property selection save fails
            
            print(f"✅ Google Ads connection created/updated: {connection.id}")
            print(f"   Account: {account_name} ({account_id})")
            print(f"   User: {campaigner_id}")
            print(f"   Expires at: {expires_at}")
            
            return {
                "success": True,
                "connection_id": connection.id,
                "digital_asset_id": digital_asset.id,
                "account_id": account_id,
                "account_name": account_name,
                "expires_at": expires_at.isoformat(),
                "scopes": self.GOOGLE_ADS_SCOPES
            }
    
    async def refresh_google_ads_token(self, connection_id: int) -> Dict[str, Any]:
        """Refresh Google Ads access token using refresh token"""
        
        with get_session() as session:
            # Get connection with digital asset
            statement = select(Connection, DigitalAsset).join(
                DigitalAsset, Connection.digital_asset_id == DigitalAsset.id
            ).where(
                and_(
                    Connection.id == connection_id,
                    Connection.auth_type == AuthType.OAUTH2,
                    Connection.revoked == False
                )
            )
            result = session.exec(statement).first()
            
            if not result:
                raise ValueError("Connection not found or revoked")
            
            connection, digital_asset = result
            
            # Decrypt refresh token
            refresh_token = self._decrypt_token(connection.refresh_token_enc)
            
            # Create credentials and refresh using stored scopes
            stored_scopes = connection.scopes if connection.scopes else self.GOOGLE_ADS_SCOPES
            credentials = Credentials(
                token=None,
                refresh_token=refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=get_google_client_id(),
                client_secret=get_google_client_secret(),
                scopes=stored_scopes
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
                
                print(f"✅ Google Ads token refreshed for connection {connection_id}")
                print(f"   Expires at: {connection.expires_at}")
                
                return {
                    "success": True,
                    "connection_id": connection_id,
                    "expires_at": connection.expires_at.isoformat(),
                    "rotated_at": connection.rotated_at.isoformat(),
                    "scopes": stored_scopes
                }
                
            except Exception as e:
                print(f"❌ Google Ads token refresh failed for connection {connection_id}: {e}")
                
                # Try to handle specific errors
                if "invalid_grant" in str(e).lower():
                    print(f"🔄 Invalid grant - attempting to renew refresh token...")
                    try:
                        # Try to renew the refresh token
                        credentials.refresh(Request())
                        print(f"✅ Refresh token renewed successfully")
                    except Exception as renewal_error:
                        print(f"❌ Automatic renewal failed: {renewal_error}")
                    
                    # If automatic renewal fails, generate re-auth URL and fail clearly
                    reauth_url = self.generate_reauth_url(connection_id, connection.account_email)
                    raise ValueError(f"Google Ads token refresh failed. Please re-authorize your Google Ads connection: {reauth_url}")

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
            if not refresh_token.startswith('1//'):
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
                    scopes=self.GOOGLE_ADS_SCOPES
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
        
        current_time = datetime.utcnow()
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
        params = {
            'client_id': get_google_client_id(),
            'redirect_uri': f"{os.getenv('FRONTEND_URL', 'https://localhost:3000')}/auth/google-ads-callback",
            'scope': ' '.join(self.GOOGLE_ADS_SCOPES),
            'response_type': 'code',
            'access_type': 'offline',
            'prompt': 'consent',
            'state': state
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
        limit: int = 100
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
                        print(f"🔄 Google Ads Token was already refreshed by another process")
                    else:
                        current_time = datetime.utcnow()
                        if connection.expires_at:
                            time_until_expiry = connection.expires_at - current_time
                            print(f"🔄 Token expires soon ({time_until_expiry}), refreshing...")
                        else:
                            print(f"🔄 No token expiry time set, refreshing...")
                        
                        try:
                            await self.refresh_google_ads_token(connection_id)
                            session.refresh(connection)
                            print(f"✅ Token refreshed successfully")
                        except Exception as refresh_error:
                            print(f"❌ Token refresh failed: {refresh_error}")
                            raise ValueError(f"Failed to refresh Google Ads token: {refresh_error}")
            
            # Validate refresh token format (no API call needed)
            refresh_token = self._decrypt_token(connection.refresh_token_enc)
            if not self.validate_refresh_token(refresh_token):
                print(f"❌ Refresh token format is invalid, attempting refresh...")
                try:
                    await self.refresh_google_ads_token(connection_id)
                    session.refresh(connection)
                    # Re-validate after refresh
                    new_refresh_token = self._decrypt_token(connection.refresh_token_enc)
                    if not self.validate_refresh_token(new_refresh_token):
                        raise ValueError("Refresh token is invalid and cannot be fixed")
                    print(f"✅ Refresh token validation successful after refresh")
                except Exception as validation_error:
                    print(f"❌ Refresh token validation and refresh failed: {validation_error}")
                    raise ValueError(f"Google Ads refresh token is invalid: {validation_error}")
            
            # Decrypt tokens
            try:
                access_token = self._decrypt_token(connection.access_token_enc)
                refresh_token = self._decrypt_token(connection.refresh_token_enc)
                print(f"✅ Tokens decrypted successfully")
            except Exception as decrypt_error:
                print(f"❌ Token decryption failed: {decrypt_error}")
                raise ValueError(f"Failed to decrypt Google Ads tokens: {decrypt_error}")
        
        # Create Google Ads client
        try:
            # Check if we have a developer token
            developer_token = os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN", "")
            
            if developer_token:
                # Use Google Ads API with developer token
                client = GoogleAdsClient.load_from_dict({
                    "developer_token": developer_token,
                    "client_id": get_google_client_id(),
                    "client_secret": get_google_client_secret(),
                    "refresh_token": refresh_token,
                    "use_proto_plus": True
                })
                
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
                        real_data.append({
                            "date": row.segments.date,
                            "campaign_id": row.campaign.id,
                            "campaign_name": row.campaign.name,
                            "impressions": row.metrics.impressions,
                            "clicks": row.metrics.clicks,
                            "cost": row.metrics.cost_micros / 1_000_000,  # Convert from micros to currency units
                            "conversions": row.metrics.conversions
                        })
                    
                    print(f"✅ Retrieved {len(real_data)} real Google Ads records using Google Ads API")
                    demo_data = real_data
                    
                except GoogleAdsException as gads_error:
                    error_msg = str(gads_error)
                    print(f"❌ Google Ads API error: {error_msg}")
                    
                    # Check if it's an authentication error
                    if any(keyword in error_msg.lower() for keyword in ['authentication', 'unauthorized', 'invalid_grant', '401', 'credentials']):
                        print(f"🔄 Authentication error detected, attempting token refresh...")
                        try:
                            # Try to refresh the token
                            await self.refresh_google_ads_token(connection_id)
                            print(f"✅ Token refreshed successfully, retrying query...")
                            
                            # Retry the query with refreshed token
                            # Recreate the client with new token
                            with get_session() as retry_session:
                                retry_connection = retry_session.get(Connection, connection_id)
                                retry_refresh_token = self._decrypt_token(retry_connection.refresh_token_enc)
                            
                            retry_client = GoogleAdsClient.load_from_dict({
                                "developer_token": developer_token,
                                "client_id": get_google_client_id(),
                                "client_secret": get_google_client_secret(),
                                "refresh_token": retry_refresh_token,
                                "use_proto_plus": True
                            })
                            
                            retry_ga_service = retry_client.get_service("GoogleAdsService")
                            response = retry_ga_service.search(customer_id=customer_id, query=query)
                            
                            real_data = []
                            for row in response:
                                real_data.append({
                                    "date": row.segments.date,
                                    "campaign_id": row.campaign.id,
                                    "campaign_name": row.campaign.name,
                                    "impressions": row.metrics.impressions,
                                    "clicks": row.metrics.clicks,
                                    "cost": row.metrics.cost_micros / 1_000_000,
                                    "conversions": row.metrics.conversions
                                })
                            
                            print(f"✅ Retrieved {len(real_data)} records after token refresh")
                            demo_data = real_data
                            
                        except Exception as refresh_error:
                            print(f"❌ Token refresh failed: {refresh_error}")
                            raise ValueError(f"Google Ads authentication failed and token refresh unsuccessful: {error_msg}")
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
                    "customer_id": customer_id
                }
            
            return {
                "success": True,
                "data": demo_data,
                "total_rows": len(demo_data),
                "metrics": metrics,
                "dimensions": dimensions or [],
                "customer_id": customer_id
            }
            
        except Exception as e:
            print(f"❌ Failed to fetch Google Ads data: {e}")
            import traceback
            traceback.print_exc()
            raise ValueError(f"Failed to fetch Google Ads data: {str(e)}")
    
    async def get_user_google_ads_connections(self, campaigner_id: int, customer_id: int = None) -> List[Dict[str, Any]]:
        """Get all Google Ads connections for a user and subclient"""
        
        with get_session() as session:
            conditions = [
                Connection.campaigner_id == campaigner_id,
                DigitalAsset.provider == "Google",
                Connection.revoked == False
            ]
            
            # Check for GOOGLE_ADS asset type (database uses 'GOOGLE_ADS' uppercase)
            conditions.append(DigitalAsset.asset_type == AssetType.GOOGLE_ADS_CAPS)
            
            # Add customer_id filter if provided
            if customer_id is not None:
                conditions.append(DigitalAsset.customer_id == customer_id)
            
            statement = select(Connection, DigitalAsset).join(
                DigitalAsset, Connection.digital_asset_id == DigitalAsset.id
            ).where(and_(*conditions))
            
            results = session.exec(statement).all()
            
            connections = []
            for connection, digital_asset in results:
                connections.append({
                    "connection_id": connection.id,
                    "digital_asset_id": digital_asset.id,
                    "customer_id": digital_asset.external_id,
                    "account_name": digital_asset.name,
                    "account_email": connection.account_email,
                    "expires_at": connection.expires_at.isoformat() if connection.expires_at else None,
                    "is_active": digital_asset.is_active,
                    "created_at": connection.created_at.isoformat() if connection.created_at else None
                })
            
            return connections
