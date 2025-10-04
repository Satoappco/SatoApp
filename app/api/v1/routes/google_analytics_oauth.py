"""
Google Analytics OAuth callback handler
Handles the OAuth flow and automatically creates GA4 connections
"""

import os
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from google_auth_oauthlib.flow import Flow

router = APIRouter(prefix="/google-analytics", tags=["google-analytics-oauth"])


@router.get("/debug")
async def debug_oauth_config():
    """Debug endpoint to check OAuth configuration"""
    import os
    return {
        "google_client_id": os.getenv("GOOGLE_CLIENT_ID", "NOT_SET"),
        "google_client_secret": "SET" if os.getenv("GOOGLE_CLIENT_SECRET") else "NOT_SET",
        "env_file_exists": os.path.exists(".env")
    }


@router.get("/debug-connections")
async def debug_connections():
    """Debug endpoint to check existing connections and their scopes"""
    try:
        from app.config.database import get_session
        from app.models.analytics import Connection
        from sqlmodel import select
        
        with get_session() as session:
            # Get all connections
            statement = select(Connection).where(Connection.auth_type == "oauth2")
            connections = session.exec(statement).all()
            
            connection_info = []
            for conn in connections:
                connection_info.append({
                    "id": conn.id,
                    "account_email": conn.account_email,
                    "scopes": conn.scopes,
                    "expires_at": conn.expires_at.isoformat() if conn.expires_at else None,
                    "revoked": conn.revoked,
                    "last_used_at": conn.last_used_at.isoformat() if conn.last_used_at else None
                })
            
            return {
                "total_connections": len(connections),
                "connections": connection_info
            }
    except Exception as e:
        return {"error": str(e)}


@router.post("/clear-invalid-scopes")
async def clear_connections_with_invalid_scopes():
    """
    Clear connections that have Google Ads scopes (which should be separate)
    This fixes the OAuth scope mismatch issue
    """
    try:
        from app.config.database import get_session
        from app.models.analytics import Connection
        from sqlmodel import select
        
        with get_session() as session:
            # Find connections with Google Ads scopes
            statement = select(Connection).where(Connection.auth_type == "oauth2")
            connections = session.exec(statement).all()
            
            invalid_connections = []
            for conn in connections:
                if conn.scopes and any(scope in conn.scopes for scope in [
                    'https://www.googleapis.com/auth/adwords',
                    'https://www.googleapis.com/auth/adsdatahub'
                ]):
                    invalid_connections.append(conn)
            
            # Revoke invalid connections
            for conn in invalid_connections:
                conn.revoked = True
                conn.access_token_enc = None
                conn.refresh_token_enc = None
                conn.token_hash = None
                session.add(conn)
            
            session.commit()
            
            return {
                "success": True,
                "message": f"Revoked {len(invalid_connections)} connections with invalid scopes",
                "revoked_connections": [
                    {
                        "id": conn.id,
                        "account_email": conn.account_email,
                        "scopes": conn.scopes
                    } for conn in invalid_connections
                ]
            }
    except Exception as e:
        return {"error": str(e), "success": False}


@router.get("/test")
async def test_endpoint():
    """Simple test endpoint"""
    return {"status": "ok", "message": "Google Analytics OAuth endpoints are working"}


@router.get("/oauth-url")
async def get_oauth_url(redirect_uri: str):
    """
    Get Google Analytics OAuth URL for frontend to redirect to
    Note: Only requests Analytics scopes. For Google Ads, use the separate Google Ads OAuth flow.
    """
    try:
        # Get settings
        from app.config.settings import get_settings
        settings = get_settings()
        
        # Create OAuth flow
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [redirect_uri]
                }
            },
            scopes=[
                'openid',
                'https://www.googleapis.com/auth/userinfo.profile',
                'https://www.googleapis.com/auth/userinfo.email',
                'https://www.googleapis.com/auth/analytics.readonly',
                'https://www.googleapis.com/auth/analytics',  # Full analytics access
                'https://www.googleapis.com/auth/analytics.manage.users.readonly'
                # Note: Google Ads scopes removed - use separate Google Ads OAuth flow
            ]
        )
        
        # Set redirect URI
        flow.redirect_uri = redirect_uri
        
        # Get authorization URL
        # Note: include_granted_scopes removed to prevent Google from adding previously granted scopes
        auth_url, _ = flow.authorization_url(
            access_type='offline',
            prompt='consent'
        )
        
        return {"auth_url": auth_url}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate OAuth URL: {str(e)}"
        )


class OAuthCallbackRequest(BaseModel):
    """Request model for OAuth callback"""
    code: str
    redirect_uri: str


class OAuthCallbackResponse(BaseModel):
    """Response model for OAuth callback"""
    success: bool
    message: str
    property_name: Optional[str] = None
    property_id: Optional[str] = None
    connection_id: Optional[int] = None
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    expires_in: Optional[int] = None
    properties: Optional[List[Dict[str, Any]]] = None  # List of available properties


class CreateConnectionRequest(BaseModel):
    """Request model for creating GA connection after property selection"""
    property_id: str
    property_name: str
    account_id: str
    account_name: str
    access_token: str
    refresh_token: str
    expires_in: int = 3600
    subclient_id: int  # Required: which subclient owns this connection


@router.options("/oauth-callback")
async def handle_oauth_callback_options():
    """Handle CORS preflight request for OAuth callback"""
    return {"message": "OK"}

@router.post("/oauth-callback", response_model=OAuthCallbackResponse)
async def handle_oauth_callback(
    request: OAuthCallbackRequest
):
    """
    Public OAuth callback endpoint - no authentication required
    Handle Google Analytics OAuth callback (public endpoint)
    Exchanges authorization code for tokens
    Note: Only handles Analytics scopes. For Google Ads, use the separate Google Ads OAuth flow.
    """
    
    print(f"DEBUG: OAuth callback started with code: {request.code[:10]}... and redirect_uri: {request.redirect_uri}")
    
    try:
        # Get settings
        from app.config.settings import get_settings
        settings = get_settings()
        
        # Create OAuth flow
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [request.redirect_uri]
                }
            },
            scopes=[
                'openid',
                'https://www.googleapis.com/auth/userinfo.profile',
                'https://www.googleapis.com/auth/userinfo.email',
                'https://www.googleapis.com/auth/analytics.readonly',
                'https://www.googleapis.com/auth/analytics',  # Full analytics access
                'https://www.googleapis.com/auth/analytics.manage.users.readonly'
                # Note: Google Ads scopes removed - use separate Google Ads OAuth flow
            ]
        )
        
        # Set redirect URI
        flow.redirect_uri = request.redirect_uri
        
        # Exchange code for tokens
        print(f"🔧 Google OAuth Debug:")
        print(f"  - Code: {request.code[:10]}...")
        print(f"  - Redirect URI: {request.redirect_uri}")
        print(f"  - Client ID: {settings.google_client_id[:10] if settings.google_client_id else 'NOT SET'}...")
        print(f"  - Client Secret: {'SET' if settings.google_client_secret else 'NOT SET'}")
        
        try:
            flow.fetch_token(code=request.code)
            print(f"  - Token exchange successful")
        except Exception as e:
            print(f"  - Token exchange failed: {str(e)}")
            print(f"  - Error type: {type(e).__name__}")
            if "invalid_grant" in str(e):
                print(f"  - This is usually caused by:")
                print(f"    1. Authorization code already used")
                print(f"    2. Authorization code expired")
                print(f"    3. Redirect URI mismatch")
                print(f"    4. Client ID/Secret mismatch")
            raise Exception(f"Google OAuth token exchange failed: {str(e)}")
        
        # Get credentials
        credentials = flow.credentials
        print(f"  - Got credentials with token: {credentials.token[:10] if credentials.token else 'NO TOKEN'}...")
        
        # Get user info from the token
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request as GoogleAuthRequest
        
        # Get user info
        user_info = None
        try:
            # Use the access token to get user info
            import requests
            user_info_response = requests.get(
                f"https://www.googleapis.com/oauth2/v2/userinfo?access_token={credentials.token}"
            )
            if user_info_response.status_code == 200:
                user_info = user_info_response.json()
        except Exception as e:
            print(f"Failed to get user info: {e}")
        
        # Store OAuth tokens temporarily (in a real app, use Redis or database)
        # For now, we'll just return the tokens and available properties to the frontend
        
        # Get real GA4 properties
        properties = []
        try:
            from google.analytics.admin import AnalyticsAdminServiceClient
            from google.analytics.admin_v1alpha.types import ListPropertiesRequest
            client = AnalyticsAdminServiceClient(credentials=credentials)
            
            print("DEBUG: Fetching real GA4 properties from Google...")
            
            # List all accounts
            accounts = client.list_accounts()
            for account in accounts:
                print(f"DEBUG: Found GA account: {account.display_name}")
                # List properties for each account using proper request format
                request = ListPropertiesRequest(filter=f"parent:{account.name}")
                account_properties = client.list_properties(request=request)
                for property_obj in account_properties:
                    properties.append({
                        'property_id': property_obj.name.split('/')[-1],
                        'property_name': property_obj.display_name,
                        'account_id': account.name.split('/')[-1],
                        'account_name': account.display_name,
                        'display_name': property_obj.display_name
                    })
                    print(f"DEBUG: Found GA property: {property_obj.display_name} (ID: {property_obj.name.split('/')[-1]})")
        except Exception as e:
            print(f"DEBUG: Failed to get GA4 properties: {e}")
            import traceback
            traceback.print_exc()
            # Return error instead of demo data
            return {
                "success": False,
                "error": f"Failed to fetch Google Analytics properties: {str(e)}",
                "properties": []
            }
        
        if not properties:
            return OAuthCallbackResponse(
                success=False,
                message="No Google Analytics properties found for this account"
            )
        
        print(f"DEBUG: Found {len(properties)} GA properties total")
        
        # Debug: Print all properties found
        for i, prop in enumerate(properties):
            print(f"DEBUG: Property {i+1}: {prop['property_name']} (ID: {prop['property_id']})")
        
        # Find user by email
        from app.models.users import User
        from app.config.database import get_session
        from sqlmodel import select
        
        with get_session() as session:
            user = None
            if user_info and user_info.get('email'):
                user_email = user_info.get('email')
                user_statement = select(User).where(User.email == user_email)
                user = session.exec(user_statement).first()
                print(f"DEBUG: Looking for user with email {user_email}, found: {user.id if user else 'None'}")
            
            if not user:
                print("DEBUG: No user found in database")
                return OAuthCallbackResponse(
                    success=False,
                    message="No user found. Please sign in first."
                )
            
            # Store tokens temporarily (in production, store in Redis with expiration)
            # For now, we'll pass them back to frontend to handle property selection
            print(f"DEBUG: OAuth successful for user {user.id} ({user.email})")
        
        return OAuthCallbackResponse(
            success=True,
            message="OAuth successful! Please select a property to connect.",
            property_name=None,  # No property selected yet
            property_id=None,    # No property selected yet
            connection_id=None,  # No connection created yet
            access_token=credentials.token,
            refresh_token=credentials.refresh_token or '',
            expires_in=3600,
            properties=properties  # Include the properties list for frontend selection
        )
        
    except Exception as e:
        print(f"DEBUG: OAuth callback failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
        return OAuthCallbackResponse(
            success=False,
            message=f"OAuth failed: {str(e)}"
        )


@router.post("/create-connection")
async def create_ga_connection(request: CreateConnectionRequest):
    """
    Create GA connection after user selects a property
    """
    print(f"DEBUG: Creating connection for property {request.property_id} ({request.property_name})")
    
    try:
        # Find user by access token (in production, use proper session management)
        from app.models.users import User
        from app.config.database import get_session
        from sqlmodel import select
        import requests
        
        # Get user info from Google using the access token
        user_info_response = requests.get(
            f"https://www.googleapis.com/oauth2/v2/userinfo?access_token={request.access_token}"
        )
        
        if user_info_response.status_code != 200:
            return {"success": False, "message": "Invalid access token"}
        
        user_info = user_info_response.json()
        user_email = user_info.get('email')
        
        if not user_email:
            return {"success": False, "message": "Could not get user email from token"}
        
        # Find user in database
        with get_session() as session:
            user_statement = select(User).where(User.email == user_email)
            user = session.exec(user_statement).first()
            
            if not user:
                return {"success": False, "message": f"User {user_email} not found in database"}
            
            print(f"DEBUG: Creating connection for user {user.id} ({user.email})")
            
            # Create GA connection using the service
            from app.services.google_analytics_service import GoogleAnalyticsService
            ga_service = GoogleAnalyticsService()
            
            # Update the service to accept property details
            connection_result = await ga_service.save_ga_connection_with_property(
                user_id=user.id,
                subclient_id=request.subclient_id,  # Use the provided subclient_id
                property_id=request.property_id,
                property_name=request.property_name,
                account_id=request.account_id,
                account_name=request.account_name,
                access_token=request.access_token,
                refresh_token=request.refresh_token,
                expires_in=request.expires_in,
                account_email=user_email
            )
            
            print(f"DEBUG: Connection created successfully: {connection_result}")
            
            # Note: Google Ads connections are now created separately
            # Users must explicitly connect to Google Ads via the separate OAuth flow
            
            return {
                "success": True,
                "message": f"Successfully connected to Google Analytics: {request.property_name}",
                "connection_id": connection_result.get('connection_id'),
                "property_id": request.property_id,
                "property_name": request.property_name
            }
    
    except Exception as e:
        print(f"DEBUG: Failed to create GA connection: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"success": False, "message": f"Failed to create connection: {str(e)}"}


@router.post("/get-properties")
async def get_ga_properties(request: dict):
    """
    Get available GA properties using access token
    """
    access_token = request.get('access_token')
    if not access_token:
        return {"success": False, "message": "Access token required"}
    
    print(f"DEBUG: Getting GA properties for access token: {access_token[:10]}...")
    
    try:
        # Get user info from Google using the access token
        import requests
        user_info_response = requests.get(
            f"https://www.googleapis.com/oauth2/v2/userinfo?access_token={access_token}"
        )
        
        if user_info_response.status_code != 200:
            return {"success": False, "message": "Invalid access token"}
        
        # Create credentials from access token
        from google.oauth2.credentials import Credentials
        credentials = Credentials(token=access_token)
        
        # Get GA4 properties
        properties = []
        try:
            from google.analytics.admin import AnalyticsAdminServiceClient
            from google.analytics.admin_v1alpha.types import ListPropertiesRequest
            client = AnalyticsAdminServiceClient(credentials=credentials)
            
            print("DEBUG: Fetching GA4 properties from Google...")
            
            # List all accounts
            accounts = client.list_accounts()
            for account in accounts:
                print(f"DEBUG: Found GA account: {account.display_name}")
                # List properties for each account using proper request format
                request = ListPropertiesRequest(filter=f"parent:{account.name}")
                account_properties = client.list_properties(request=request)
                for property_obj in account_properties:
                    properties.append({
                        'property_id': property_obj.name.split('/')[-1],
                        'property_name': property_obj.display_name,
                        'account_id': account.name.split('/')[-1],
                        'account_name': account.display_name,
                        'display_name': property_obj.display_name
                    })
                    print(f"DEBUG: Found GA property: {property_obj.display_name} (ID: {property_obj.name.split('/')[-1]})")
        except Exception as e:
            print(f"DEBUG: Failed to get GA4 properties: {e}")
            import traceback
            traceback.print_exc()
            # Return error instead of demo data
            return {
                "success": False,
                "error": f"Failed to fetch Google Analytics properties: {str(e)}",
                "properties": []
            }
        
        print(f"DEBUG: Returning {len(properties)} properties")
        
        return {
            "success": True,
            "properties": properties,
            "message": f"Found {len(properties)} Google Analytics properties"
        }
    
    except Exception as e:
        print(f"DEBUG: Failed to get GA properties: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"success": False, "message": f"Failed to get properties: {str(e)}"}