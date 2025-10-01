"""
Google Ads OAuth and data fetching service
Handles token storage, refresh, and Google Ads API calls
"""

import json
import hashlib
import base64
from datetime import datetime, timedelta
import os
from typing import Dict, Any, Optional, List
from cryptography.fernet import Fernet
from google.oauth2.credentials import Credentials
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


class GoogleAdsService:
    """Service for managing Google Ads OAuth and data fetching"""
    
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
        user_id: int,
        subclient_id: int,
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
            user_id: ID of user creating the connection
            subclient_id: ID of subclient this asset belongs to
            account_id: Google Ads account ID (e.g., "123-456-7890")
            account_name: Human-readable account name
            access_token: OAuth access token
            refresh_token: OAuth refresh token
            expires_in: Token expiration time in seconds
            account_email: Google account email
        """
        
        print(f"🔄 Creating Google Ads connection for account {account_id} ({account_name})")
        
        with get_session() as session:
            # First, deactivate all other GOOGLE_ADS assets for this user/subclient
            print(f"DEBUG: Deactivating other GOOGLE_ADS assets for user {user_id}, subclient {subclient_id}")
            deactivate_statement = select(DigitalAsset).where(
                and_(
                    DigitalAsset.subclient_id == subclient_id,
                    DigitalAsset.asset_type == AssetType.GOOGLE_ADS,
                    DigitalAsset.provider == "Google",
                    DigitalAsset.is_active == True
                )
            )
            other_assets = session.exec(deactivate_statement).all()
            for asset in other_assets:
                asset.is_active = False
                print(f"DEBUG: Deactivated asset {asset.id}: {asset.name}")
            session.commit()
            
            # Create or get digital asset
            digital_asset_statement = select(DigitalAsset).where(
                and_(
                    DigitalAsset.subclient_id == subclient_id,
                    DigitalAsset.asset_type == AssetType.GOOGLE_ADS,
                    DigitalAsset.external_id == account_id
                )
            )
            digital_asset = session.exec(digital_asset_statement).first()
            
            if not digital_asset:
                # Create new digital asset
                digital_asset = DigitalAsset(
                    subclient_id=subclient_id,
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
                    user_id=user_id,
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
            
            print(f"✅ Google Ads connection created/updated: {connection.id}")
            print(f"   Account: {account_name} ({account_id})")
            print(f"   User: {user_id}")
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
        
        # Get connection and refresh token if needed
        with get_session() as session:
            connection = session.get(Connection, connection_id)
            if not connection:
                raise ValueError(f"Connection {connection_id} not found")
            
            # Check if token needs refresh
            if connection.expires_at and connection.expires_at <= datetime.utcnow() + timedelta(minutes=5):
                print(f"🔄 Token expires soon, refreshing...")
                await self.refresh_google_ads_token(connection_id)
                session.refresh(connection)
            
            # Decrypt access token
            access_token = self._decrypt_token(connection.access_token_enc)
            refresh_token = self._decrypt_token(connection.refresh_token_enc)
        
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
                    WHERE segments.date BETWEEN '{start_date}' AND '{end_date}'
                    AND campaign.status = 'ENABLED'
                    ORDER BY segments.date DESC
                    LIMIT {limit}
                """
                
                # Execute the query
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
    
    async def get_user_google_ads_connections(self, user_id: int, subclient_id: int = None) -> List[Dict[str, Any]]:
        """Get all Google Ads connections for a user and subclient"""
        
        with get_session() as session:
            conditions = [
                Connection.user_id == user_id,
                DigitalAsset.asset_type == AssetType.GOOGLE_ADS,
                DigitalAsset.provider == "Google",
                Connection.revoked == False
            ]
            
            # Add subclient_id filter if provided
            if subclient_id is not None:
                conditions.append(DigitalAsset.subclient_id == subclient_id)
            
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
