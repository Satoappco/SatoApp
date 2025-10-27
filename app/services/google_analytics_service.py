"""
Google Analytics OAuth and data fetching service
Handles token storage, refresh, and GA4 API calls
"""

import json
import hashlib
import base64
from datetime import datetime, timedelta, timezone
import os
import asyncio
from typing import Dict, Any, Optional, List
import requests
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


class GoogleAnalyticsService:
    """Service for managing Google Analytics OAuth and data fetching"""
    
    # Class-level refresh locks to prevent simultaneous token refresh attempts
    _refresh_locks = {}
    
    # In-memory property cache: {cache_key: {properties: [...], timestamp: datetime}}
    _property_cache = {}
    
    # Google Analytics 4 scopes - comprehensive set for modern GA4 API
    GA4_SCOPES = [
        'https://www.googleapis.com/auth/analytics.readonly',
        'https://www.googleapis.com/auth/analytics',  # Full analytics access for data API
        'https://www.googleapis.com/auth/analytics.manage.users.readonly',
        'https://www.googleapis.com/auth/userinfo.email',  # User email for account identification
        'https://www.googleapis.com/auth/userinfo.profile',  # User profile for account identification
        'openid'  # OpenID Connect for authentication
    ]
    
    # Note: Google Ads scopes are handled by the separate GoogleAdsService
    # Each service should only use its own scopes to avoid scope conflicts
    
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
    
    def _extract_date_from_tool_result(self, tool_result: str) -> str:
        """Extract YYYY-MM-DD date from DateConversionTool result"""
        import re
        # Look for "Start Date: YYYY-MM-DD" or "End Date: YYYY-MM-DD" pattern
        date_match = re.search(r'(?:Start Date|End Date):\s*(\d{4}-\d{2}-\d{2})', tool_result)
        if date_match:
            return date_match.group(1)
        
        # Fallback: look for any YYYY-MM-DD pattern
        date_match = re.search(r'(\d{4}-\d{2}-\d{2})', tool_result)
        if date_match:
            return date_match.group(1)
        
        # If no date found, log error and raise exception
        print(f"❌ ERROR: Could not extract date from DateConversionTool result: {tool_result}")
        raise ValueError(f"Failed to extract date from DateConversionTool result. Tool returned: {tool_result}")
    
    async def save_ga_connection_with_property(
        self,
        campaigner_id: int,
        customer_id: int,
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
            # First, deactivate all other GA4 assets for this user/subclient
            print(f"DEBUG: Deactivating other GA4 assets for user {campaigner_id}, subclient {customer_id}")
            deactivate_statement = select(DigitalAsset).where(
                and_(
                    DigitalAsset.customer_id == customer_id,
                    DigitalAsset.asset_type == AssetType.GA4,
                    DigitalAsset.provider == "Google",
                    DigitalAsset.is_active == True
                )
            )
            other_assets = session.exec(deactivate_statement).all()
            for asset in other_assets:
                asset.is_active = False
                print(f"DEBUG: Deactivated asset {asset.id}: {asset.name}")
            session.commit()
            
            # Check if digital asset already exists
            statement = select(DigitalAsset).where(
                and_(
                    DigitalAsset.customer_id == customer_id,
                    DigitalAsset.asset_type == AssetType.GA4,
                    DigitalAsset.provider == "Google",
                    DigitalAsset.external_id == property_id
                )
            )
            digital_asset = session.exec(statement).first()
            
            if not digital_asset:
                print(f"DEBUG: Creating new digital asset for property {property_id}")
                # Create new digital asset with real property details
                digital_asset = DigitalAsset(
                    customer_id=customer_id,
                    asset_type=AssetType.GA4,
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
                # Activate this asset and update metadata if needed
                digital_asset.is_active = True
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
            
            # Calculate expiration time with timezone-aware datetime
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
            now = datetime.now(timezone.utc)
            
            # Check for existing connection first
            connection_statement = select(Connection).where(
                and_(
                    Connection.digital_asset_id == digital_asset.id,
                    Connection.campaigner_id == campaigner_id,
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
                connection.rotated_at = now
                connection.last_used_at = now
            else:
                print(f"DEBUG: Creating new connection for user {campaigner_id} and asset {digital_asset.id}")
                # Create new connection
                connection = Connection(
                    digital_asset_id=digital_asset.id,
                    customer_id=customer_id,
                    campaigner_id=campaigner_id,
                    auth_type=AuthType.OAUTH2,
                    account_email=account_email,
                    scopes=self.GA4_SCOPES,
                    access_token_enc=access_token_enc,
                    refresh_token_enc=refresh_token_enc,
                    token_hash=token_hash,
                    expires_at=expires_at,
                    revoked=False,
                    last_used_at=now
                )
            
            session.add(connection)
            session.commit()
            session.refresh(connection)
            
            # Automatically save this property as the selected property for the user
            from app.services.property_selection_service import PropertySelectionService
            property_selection_service = PropertySelectionService()
            
            try:
                await property_selection_service.save_property_selection(
                    campaigner_id=campaigner_id,
                    customer_id=customer_id,
                    service="google_analytics",
                    property_id=property_id,
                    property_name=property_name
                )
                print(f"DEBUG: Automatically saved property selection for {property_name}")
            except Exception as e:
                print(f"DEBUG: Failed to save property selection: {e}")
                # Don't fail the connection creation if property selection save fails
            
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
            
            # Create credentials and refresh using stored scopes
            stored_scopes = connection.scopes if connection.scopes else self.GA4_SCOPES
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
                now = datetime.now(timezone.utc)
                connection.expires_at = now + timedelta(seconds=3600)  # 1 hour
                connection.rotated_at = now
                connection.last_used_at = now
                
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
            
            # Calculate expiry with timezone-aware datetime
            now = datetime.now(timezone.utc)
            expires_at = now + timedelta(seconds=expires_in)
            
            # Update connection
            connection.access_token_enc = access_token_enc
            connection.refresh_token_enc = refresh_token_enc
            connection.token_hash = token_hash
            connection.expires_at = expires_at
            connection.rotated_at = now
            connection.last_used_at = now
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
                
                # Create credentials using stored scopes
                stored_scopes = connection.scopes if connection.scopes else self.GA4_SCOPES
                credentials = Credentials(
                    token=None,
                    refresh_token=refresh_token,
                    token_uri="https://oauth2.googleapis.com/token",
                    client_id=get_google_client_id(),
                    client_secret=get_google_client_secret(),
                    scopes=stored_scopes
                )
                
                # Try to refresh with new scopes
                credentials.refresh(Request())
                
                # If successful, update the connection
                access_token_enc = self._encrypt_token(credentials.token)
                refresh_token_enc = self._encrypt_token(credentials.refresh_token)
                token_hash = self._generate_token_hash(credentials.token)
                now = datetime.now(timezone.utc)
                expires_at = now + timedelta(seconds=3600)
                
                # Update connection
                connection.access_token_enc = access_token_enc
                connection.refresh_token_enc = refresh_token_enc
                connection.token_hash = token_hash
                connection.expires_at = expires_at
                connection.rotated_at = now
                connection.last_used_at = now
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
                    
                    # Update connection with timezone-aware datetime
                    now = datetime.now(timezone.utc)
                    fresh_connection.access_token_enc = access_token_enc
                    fresh_connection.refresh_token_enc = refresh_token_enc
                    fresh_connection.token_hash = token_hash
                    fresh_connection.expires_at = now + timedelta(seconds=3600)  # 1 hour
                    fresh_connection.rotated_at = now
                    fresh_connection.last_used_at = now
                    
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
    
    def validate_ga_refresh_token(self, refresh_token: str) -> bool:
        """
        Validate GA4 refresh token without making API calls
        
        Args:
            refresh_token: The refresh token to validate
            
        Returns:
            True if token appears valid, False otherwise
        """
        try:
            # Basic validation checks
            if not refresh_token or len(refresh_token) < 10:
                print("❌ Invalid GA4 refresh token format")
                return False
            
            # Check if it looks like a valid Google OAuth2 refresh token
            if not refresh_token.startswith('1//'):
                print("❌ GA4 Refresh token doesn't match Google OAuth2 format")
                return False
            
            # Try to create a Credentials object to validate the token structure
            try:
                credentials = Credentials(
                    token=None,
                    refresh_token=refresh_token,
                    token_uri="https://oauth2.googleapis.com/token",
                    client_id=get_google_client_id(),
                    client_secret=get_google_client_secret(),
                    scopes=self.GA4_SCOPES
                )
                print("✅ GA4 Refresh token format appears valid")
                return True
            except Exception as cred_error:
                print(f"❌ GA4 Refresh token credentials validation failed: {cred_error}")
                return False
            
        except Exception as e:
            print(f"❌ GA4 Refresh token validation error: {e}")
            return False
    
    def is_ga_token_expired(self, expires_at: datetime) -> bool:
        """
        Check if GA4 token is expired with buffer
        
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
            
            # Check if tokens are properly encrypted
            if not connection.access_token_enc or not connection.refresh_token_enc:
                raise ValueError(f"Connection {connection_id} has missing or invalid encrypted tokens. Please re-authorize this connection.")
            
            # Check if token needs refresh (efficient check without API calls)
            token_needs_refresh = self.is_ga_token_expired(connection.expires_at)
            
            if token_needs_refresh:
                # Use refresh lock to prevent simultaneous refresh attempts
                if connection_id not in self._refresh_locks:
                    self._refresh_locks[connection_id] = asyncio.Lock()
                
                async with self._refresh_locks[connection_id]:
                    # Double-check if token still needs refresh (another process might have refreshed it)
                    connection = session.exec(statement).first()  # Reload from DB
                    if not self.is_ga_token_expired(connection.expires_at):
                        print(f"🔄 GA4 Token was already refreshed by another process")
                    else:
                        current_time = datetime.now(timezone.utc)
                        if connection.expires_at:
                            time_until_expiry = connection.expires_at - current_time
                            print(f"🔄 GA4 Token expires soon ({time_until_expiry}), refreshing...")
                        else:
                            print(f"🔄 GA4 No token expiry time set, refreshing...")
                        
                        try:
                            await self.refresh_ga_token(connection_id)
                            # Reload connection
                            connection = session.exec(statement).first()
                            print(f"✅ GA4 Token refreshed successfully")
                        except Exception as refresh_error:
                            print(f"❌ GA4 Token refresh failed: {refresh_error}")
                            raise ValueError(f"Failed to refresh GA4 token: {refresh_error}")
                        
                        # Re-validate tokens after refresh
                        if not connection.access_token_enc or not connection.refresh_token_enc:
                            raise ValueError(f"Connection {connection_id} tokens are still invalid after refresh. Please re-authorize this connection.")
            
            # Validate refresh token format (no API call needed)
            refresh_token = self._decrypt_token(connection.refresh_token_enc)
            if not self.validate_ga_refresh_token(refresh_token):
                print(f"❌ GA4 Refresh token format is invalid, attempting refresh...")
                try:
                    await self.refresh_ga_token(connection_id)
                    # Reload connection
                    connection = session.exec(statement).first()
                    # Re-validate after refresh
                    new_refresh_token = self._decrypt_token(connection.refresh_token_enc)
                    if not self.validate_ga_refresh_token(new_refresh_token):
                        raise ValueError("GA4 Refresh token is invalid and cannot be fixed")
                    print(f"✅ GA4 Refresh token validation successful after refresh")
                except Exception as validation_error:
                    print(f"❌ GA4 Refresh token validation and refresh failed: {validation_error}")
                    raise ValueError(f"GA4 refresh token is invalid: {validation_error}")
            
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
            # Validate metrics - fix common invalid metric names
            valid_metrics = []
            for metric in metrics:
                # Fix common invalid metric names
                if metric == "averageEngagementTime":
                    print(f"WARNING: Converting invalid metric 'averageEngagementTime' to 'engagementRate'")
                    valid_metrics.append("engagementRate")
                elif metric == "averageSessionDuration":
                    print(f"WARNING: Converting invalid metric 'averageSessionDuration' to 'averageSessionDuration'")
                    valid_metrics.append("averageSessionDuration")
                else:
                    valid_metrics.append(metric)
            
            # Get valid credentials
            credentials = await self.get_ga_credentials(connection_id)
            
            # Initialize GA4 client
            client = BetaAnalyticsDataClient(credentials=credentials)
            
            # Build request
            request = RunReportRequest(
                property=f"properties/{property_id}",
                dimensions=[Dimension(name=dim) for dim in (dimensions or [])],
                metrics=[Metric(name=metric) for metric in valid_metrics],
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
            error_msg = str(e)
            print(f"Error in fetch_ga4_data: {error_msg}")
            import traceback
            traceback.print_exc()
            
            # Provide more specific error information
            if "401" in error_msg or "unauthorized" in error_msg.lower():
                detailed_error = f"GA4 Authentication Error: {error_msg}. Please re-authorize your Google Analytics connection."
            elif "403" in error_msg or "forbidden" in error_msg.lower():
                detailed_error = f"GA4 Permission Error: {error_msg}. Check if your account has access to the GA4 property."
            elif "quota" in error_msg.lower():
                detailed_error = f"GA4 Quota Error: {error_msg}. You may have exceeded the API quota limit."
            elif "property" in error_msg.lower():
                detailed_error = f"GA4 Property Error: {error_msg}. Check if the property ID is correct."
            else:
                detailed_error = f"GA4 API Error: {error_msg}"
            
            return {
                "success": False,
                "error": detailed_error,
                "original_error": error_msg,
                "dimension_headers": [],
                "metric_headers": [],
                "rows": [],
                "row_count": 0,
                "totals": []
            }
    
    async def get_user_ga_connections(self, campaigner_id: int, customer_id: int = None) -> List[Dict[str, Any]]:
        """Get all GA connections for a user and subclient"""
        
        with get_session() as session:
            conditions = [
                Connection.campaigner_id == campaigner_id,
                DigitalAsset.provider == "Google",
                Connection.revoked == False
            ]
            
            # Check for GA4 asset type
            conditions.append(DigitalAsset.asset_type == AssetType.GA4)
            
            # Add customer_id filter if provided - now direct on connections table
            if customer_id is not None:
                conditions.append(Connection.customer_id == customer_id)
            
            statement = select(Connection, DigitalAsset).join(
                DigitalAsset, Connection.digital_asset_id == DigitalAsset.id
            ).where(and_(*conditions))
            
            results = session.exec(statement).all()
            
            connections = []
            for connection, digital_asset in results:
                # Check if token is outdated using backend logic (avoids timezone issues)
                is_outdated = self.is_ga_token_expired(connection.expires_at) if connection.expires_at else True
                
                # Helper to format datetime with timezone
                def format_datetime(dt):
                    if not dt:
                        return None
                    # If timezone-naive, assume UTC and add Z
                    if dt.tzinfo is None:
                        return dt.isoformat() + 'Z'
                    return dt.isoformat()
                
                connections.append({
                    "connection_id": connection.id,
                    "digital_asset_id": digital_asset.id,
                    "property_id": digital_asset.external_id,
                    "property_name": digital_asset.name,
                    "account_email": connection.account_email,
                    "expires_at": format_datetime(connection.expires_at),
                    "last_used_at": format_datetime(connection.last_used_at),
                    "is_active": digital_asset.is_active,
                    "is_outdated": is_outdated
                })
            
            return connections
    

    async def get_user_connections(self, campaigner_id: int) -> List[Dict[str, Any]]:
        """Get user connections for webhook processing"""
        return await self.get_user_ga_connections(campaigner_id)
    
    async def revoke_ga_connection(self, connection_id: int) -> bool:
        """Revoke a GA connection - marks as revoked in DB and revokes with Google"""
        
        with get_session() as session:
            statement = select(Connection).where(Connection.id == connection_id)
            connection = session.exec(statement).first()
            
            if not connection:
                return False
            
            # First, revoke the token with Google
            try:
                access_token = self._decrypt_token(connection.access_token_enc)
                
                # Revoke the token with Google OAuth2
                revoke_url = "https://oauth2.googleapis.com/revoke"
                response = requests.post(
                    revoke_url,
                    params={'token': access_token},
                    headers={'content-type': 'application/x-www-form-urlencoded'}
                )
                
                # Google returns 200 for successful revocation
                if response.status_code == 200:
                    print(f"Successfully revoked token with Google for connection {connection_id}")
                else:
                    print(f"Warning: Google revocation returned status {response.status_code} for connection {connection_id}")
                    # Continue anyway to mark as revoked in our DB
                    
            except Exception as e:
                print(f"Error revoking token with Google for connection {connection_id}: {str(e)}")
                # Continue anyway to mark as revoked in our DB
            
            # Mark as revoked in our database
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
        """
        Fetch Google Ads data using the Google Ads API
        
        Args:
            connection_id: ID of the connection to use
            customer_id: Google Ads customer ID
            metrics: List of metrics to fetch
            dimensions: List of dimensions to group by
            start_date: Start date (relative or YYYY-MM-DD format)
            end_date: End date (relative or YYYY-MM-DD format)
            limit: Maximum number of rows to return
        """
        
        print(f"🔄 Fetching Google Ads data for customer {customer_id}")
        print(f"   Metrics: {metrics}")
        print(f"   Dimensions: {dimensions}")
        print(f"   Date range: {start_date} to {end_date}")
        
        # Use DateConversionTool to convert relative dates to ISO format
        from app.tools.date_conversion_tool import DateConversionTool
        date_tool = DateConversionTool()
        
        # Convert dates using LLM-based tool
        if start_date and end_date:
            # Check if dates are already in YYYY-MM-DD format
            import re
            if re.match(r'^\d{4}-\d{2}-\d{2}$', start_date) and re.match(r'^\d{4}-\d{2}-\d{2}$', end_date):
                start_date_iso, end_date_iso = start_date, end_date
                print(f"   Using provided ISO dates: {start_date_iso} to {end_date_iso}")
            else:
                # Use DateConversionTool to convert relative dates
                try:
                    start_result = date_tool._run(start_date)
                    end_result = date_tool._run(end_date)
                    
                    # Extract dates from tool results
                    start_date_iso = self._extract_date_from_tool_result(start_result)
                    end_date_iso = self._extract_date_from_tool_result(end_result)
                    print(f"   Converted dates: {start_date_iso} to {end_date_iso}")
                except Exception as e:
                    print(f"❌ ERROR: Failed to convert dates using DateConversionTool: {e}")
                    print(f"   Original dates: {start_date} to {end_date}")
                    raise ValueError(f"Date conversion failed: {e}")
        else:
            # Use default dates if not provided
            from datetime import datetime, timedelta
            end_date_iso = datetime.now().strftime("%Y-%m-%d")
            start_date_iso = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
            print(f"   Using default dates: {start_date_iso} to {end_date_iso}")
        
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
                    WHERE segments.date BETWEEN '{start_date_iso}' AND '{end_date_iso}'
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
    
    @staticmethod
    def cache_user_properties(campaigner_id: int, customer_id: int, properties: List[Dict[str, Any]]) -> None:
        """Cache user properties for quick retrieval"""
        from app.config.settings import get_settings
        settings = get_settings()
        
        cache_key = f"ga_properties_{campaigner_id}_{customer_id}"
        GoogleAnalyticsService._property_cache[cache_key] = {
            "properties": properties,
            "timestamp": datetime.now()
        }
    
    @staticmethod
    def get_cached_properties(campaigner_id: int, customer_id: int) -> Optional[List[Dict[str, Any]]]:
        """Get cached properties if still fresh"""
        from app.config.settings import get_settings
        settings = get_settings()
        
        cache_key = f"ga_properties_{campaigner_id}_{customer_id}"
        
        if cache_key not in GoogleAnalyticsService._property_cache:
            return None
        
        cache_entry = GoogleAnalyticsService._property_cache[cache_key]
        cache_age = datetime.now() - cache_entry["timestamp"]
        
        # Return cached properties if less than TTL
        if cache_age.total_seconds() < settings.ga_property_cache_ttl:
            return cache_entry["properties"]
        else:
            # Cache expired, remove it
            del GoogleAnalyticsService._property_cache[cache_key]
            return None
    
    @staticmethod
    def clear_property_cache(campaigner_id: int, customer_id: int) -> None:
        """Clear property cache for user/customer"""
        cache_key = f"ga_properties_{campaigner_id}_{customer_id}"
        if cache_key in GoogleAnalyticsService._property_cache:
            del GoogleAnalyticsService._property_cache[cache_key]
