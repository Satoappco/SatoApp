"""
Google Ads OAuth callback handler
Handles the OAuth flow and automatically creates Google Ads connections
"""

import os
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from google_auth_oauthlib.flow import Flow

router = APIRouter(prefix="/google-ads-oauth", tags=["google-ads-oauth"])


@router.get("/test")
async def test_endpoint():
    """Simple test endpoint"""
    return {"status": "ok", "message": "Google Ads OAuth endpoints are working"}


@router.post("/clear-invalid-scopes")
async def clear_connections_with_invalid_scopes():
    """
    Clear Google Ads connections that have Analytics scopes (which should be separate)
    This fixes any OAuth scope mismatch issues
    """
    try:
        from app.config.database import get_session
        from app.models.analytics import Connection, DigitalAsset, AssetType
        from sqlmodel import select, and_

        with get_session() as session:
            # Find Google Ads connections with Analytics scopes
            statement = (
                select(Connection, DigitalAsset)
                .join(DigitalAsset, Connection.digital_asset_id == DigitalAsset.id)
                .where(
                    and_(
                        DigitalAsset.asset_type == AssetType.GOOGLE_ADS,
                        Connection.auth_type == "oauth2",
                    )
                )
            )
            results = session.exec(statement).all()

            invalid_connections = []
            for conn, asset in results:
                if conn.scopes and any(
                    scope in conn.scopes
                    for scope in [
                        "https://www.googleapis.com/auth/analytics.readonly",
                        "https://www.googleapis.com/auth/analytics",
                        "https://www.googleapis.com/auth/analytics.manage.users.readonly",
                    ]
                ):
                    invalid_connections.append((conn, asset))

            # Revoke invalid connections
            for conn, asset in invalid_connections:
                conn.revoked = True
                conn.access_token_enc = None
                conn.refresh_token_enc = None
                conn.token_hash = None
                session.add(conn)

            session.commit()

            return {
                "success": True,
                "message": f"Revoked {len(invalid_connections)} Google Ads connections with invalid Analytics scopes",
                "revoked_connections": [
                    {
                        "id": conn.id,
                        "account_email": conn.account_email,
                        "scopes": conn.scopes,
                        "asset_type": asset.asset_type.value,
                    }
                    for conn, asset in invalid_connections
                ],
            }
    except Exception as e:
        return {"error": str(e), "success": False}


@router.get("/oauth-url")
async def get_oauth_url(redirect_uri: str, state: Optional[str] = None):
    """
    Get Google Ads OAuth URL for frontend to redirect to
    Accepts optional state parameter to preserve user context through OAuth flow
    Note: Only requests Google Ads scopes. For Analytics, use the separate Google Analytics OAuth flow.
    Only shows consent screen if no existing connection or scopes have changed
    """
    try:
        # Get settings
        from app.config.settings import get_settings

        settings = get_settings()

        # Requested scopes for Google Ads
        requested_scopes = [
            "openid",
            "https://www.googleapis.com/auth/userinfo.profile",
            "https://www.googleapis.com/auth/userinfo.email",
            "https://www.googleapis.com/auth/adwords",  # Google Ads API access
            "https://www.googleapis.com/auth/adsdatahub",  # Google Ads Data Hub access
            # Note: Analytics scopes removed - use separate Google Analytics OAuth flow
        ]

        # Determine if consent is needed by checking for existing connections
        prompt_consent = True  # Default to consent

        if state:
            try:
                import jwt
                from datetime import datetime

                # Decode JWT state to get campaigner_id and customer_id
                payload = jwt.decode(
                    state, settings.oauth_state_secret, algorithms=["HS256"]
                )

                campaigner_id = payload.get("campaigner_id")
                customer_id = payload.get("customer_id")

                # Check expiration
                if datetime.now(timezone.utc).timestamp() > payload.get("exp", 0):
                    raise HTTPException(
                        status_code=400, detail="OAuth state has expired"
                    )

                # Query database for existing connections
                if campaigner_id and customer_id:
                    from app.config.database import get_session
                    from app.models.analytics import Connection, DigitalAsset, AssetType
                    from sqlmodel import select, and_

                    with get_session() as session:
                        # Find existing Google Ads connections
                        statement = (
                            select(Connection, DigitalAsset)
                            .join(
                                DigitalAsset,
                                Connection.digital_asset_id == DigitalAsset.id,
                            )
                            .where(
                                and_(
                                    Connection.campaigner_id == campaigner_id,
                                    Connection.customer_id == customer_id,
                                    DigitalAsset.asset_type == AssetType.GOOGLE_ADS,
                                    Connection.revoked == False,
                                    Connection.expires_at.isnot(None),
                                )
                            )
                        )

                        results = session.exec(statement).all()

                        # Check if any existing connection has matching scopes
                        for conn, asset in results:
                            if conn.scopes:
                                # Sort and compare scope lists
                                conn_scopes = sorted(conn.scopes)
                                requested_scopes_sorted = sorted(requested_scopes)

                                if conn_scopes == requested_scopes_sorted:
                                    # Matching scopes found - no need for consent
                                    prompt_consent = False
                                    print(
                                        f"✅ Found existing connection with matching scopes - skipping consent"
                                    )
                                    break

                        if not prompt_consent:
                            print(
                                f"✅ Existing connection found with matching Google Ads scopes - no consent needed"
                            )
                        else:
                            print(
                                f"⚠️ No existing connection or scopes differ - consent required"
                            )

            except jwt.InvalidTokenError:
                # If state is invalid, default to consent
                print(f"⚠️ Invalid OAuth state - defaulting to consent")
                prompt_consent = True
            except Exception as e:
                # On any error, default to consent for safety
                print(
                    f"⚠️ Error checking existing connections: {e} - defaulting to consent"
                )
                prompt_consent = True

        # Create OAuth flow
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [redirect_uri],
                }
            },
            scopes=requested_scopes,
        )

        # Set redirect URI
        flow.redirect_uri = redirect_uri

        # Build authorization URL parameters
        auth_params = {
            "access_type": "offline",
            "state": state,  # Pass through the state parameter
        }

        # Only add prompt parameter if consent is needed
        if prompt_consent:
            auth_params["prompt"] = "consent"

        # Get authorization URL with state parameter
        auth_url, _ = flow.authorization_url(**auth_params)

        return {"auth_url": auth_url}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate OAuth URL: {str(e)}",
        )


class OAuthCallbackRequest(BaseModel):
    """Request model for OAuth callback"""

    code: str
    redirect_uri: str
    state: Optional[str] = None  # JWT-signed state parameter


class OAuthCallbackResponse(BaseModel):
    """Response model for OAuth callback"""

    success: bool
    message: str
    account_name: Optional[str] = None
    account_id: Optional[str] = None
    connection_id: Optional[int] = None
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    expires_in: Optional[int] = None
    accounts: Optional[List[Dict[str, Any]]] = None  # List of available ad accounts


class CreateConnectionRequest(BaseModel):
    """Request model for creating Google Ads connection after account selection"""

    account_id: str
    account_name: str
    access_token: str
    refresh_token: Optional[str] = None
    expires_in: int = 3600
    customer_id: int  # Required: which customer owns this connection
    campaigner_id: int  # Required: which campaigner is creating this connection


@router.options("/oauth-callback")
async def handle_oauth_callback_options():
    """Handle CORS preflight request for OAuth callback"""
    return {"message": "OK"}


@router.post("/oauth-callback", response_model=OAuthCallbackResponse)
async def handle_oauth_callback(request: OAuthCallbackRequest):
    """
    Public OAuth callback endpoint - no authentication required
    Handle Google Ads OAuth callback (public endpoint)
    Exchanges authorization code for tokens
    Note: Only handles Google Ads scopes. For Analytics, use the separate Google Analytics OAuth flow.
    """

    print(
        f"DEBUG: Google Ads OAuth callback started with code: {request.code[:10]}... and redirect_uri: {request.redirect_uri}"
    )

    # Verify and extract user context from signed state
    campaigner_id = None
    customer_id = None

    if request.state:
        try:
            from app.config.settings import get_settings

            settings = get_settings()

            # Decode and verify the JWT
            import jwt

            payload = jwt.decode(
                request.state, settings.oauth_state_secret, algorithms=["HS256"]
            )

            campaigner_id = payload.get("campaigner_id")
            customer_id = payload.get("customer_id")
            timestamp = payload.get("timestamp")

            # Check expiration using JWT exp field
            from datetime import datetime

            if datetime.now(timezone.utc).timestamp() > payload.get("exp", 0):
                raise HTTPException(status_code=400, detail="OAuth state has expired")

            print(
                f"DEBUG: User context extracted - Campaigner ID: {campaigner_id}, Customer ID: {customer_id}"
            )

        except jwt.InvalidTokenError as e:
            print(f"❌ Invalid OAuth state: {e}")
            raise HTTPException(
                status_code=400, detail=f"Invalid OAuth state: {str(e)}"
            )
        except Exception as e:
            print(f"❌ OAuth state verification failed: {e}")
            raise HTTPException(
                status_code=500, detail=f"Failed to verify OAuth state: {str(e)}"
            )

    if not campaigner_id or not customer_id:
        raise HTTPException(
            status_code=400, detail="No user found. Please sign in first."
        )

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
                    "redirect_uris": [request.redirect_uri],
                }
            },
            scopes=[
                "openid",
                "https://www.googleapis.com/auth/userinfo.profile",
                "https://www.googleapis.com/auth/userinfo.email",
                "https://www.googleapis.com/auth/adwords",  # Google Ads API access
                "https://www.googleapis.com/auth/adsdatahub",  # Google Ads Data Hub access
                # Note: Analytics scopes removed - use separate Google Analytics OAuth flow
            ],
        )

        # Set redirect URI
        flow.redirect_uri = request.redirect_uri

        # Exchange code for tokens
        print(f"🔧 Google Ads OAuth Debug:")
        print(f"  - Code: {request.code[:10]}...")
        print(f"  - Redirect URI: {request.redirect_uri}")
        print(
            f"  - Client ID: {settings.google_client_id[:10] if settings.google_client_id else 'NOT SET'}..."
        )
        print(
            f"  - Client Secret: {'SET' if settings.google_client_secret else 'NOT SET'}"
        )

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
            raise Exception(f"Google Ads OAuth token exchange failed: {str(e)}")

        # Get credentials
        credentials = flow.credentials
        print(
            f"  - Got credentials with token: {credentials.token[:10] if credentials.token else 'NO TOKEN'}..."
        )

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

        # Get Google Ads accounts using OAuth tokens directly (like the old method)
        accounts = []
        try:
            # Check if we have a developer token, but don't require it
            developer_token = os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN", "")

            print(f"🔍 DEBUG: Checking for Google Ads Developer Token...")
            print(f"🔍 DEBUG: Token present: {bool(developer_token)}")
            print(
                f"🔍 DEBUG: Token length: {len(developer_token) if developer_token else 0}"
            )
            if developer_token:
                print(f"🔍 DEBUG: Token (first 10 chars): {developer_token[:10]}...")

            if developer_token:
                # Use Google Ads API with developer token
                from google.ads.googleads.client import GoogleAdsClient
                from google.ads.googleads.errors import GoogleAdsException

                client = GoogleAdsClient.load_from_dict(
                    {
                        "developer_token": developer_token,
                        "client_id": settings.google_client_id,
                        "client_secret": settings.google_client_secret,
                        "refresh_token": credentials.refresh_token,
                        "use_proto_plus": True,
                    }
                )

                print("DEBUG: Fetching real Google Ads accounts from Google Ads API...")

                # List all accessible customer accounts
                customer_service = client.get_service("CustomerService")
                accessible_customers = customer_service.list_accessible_customers()

                for customer_resource_name in accessible_customers.resource_names:
                    customer_id = customer_resource_name.split("/")[-1]

                    try:
                        # Get customer details using GoogleAdsService and a query
                        # This is the correct way in Google Ads API v21
                        ga_service = client.get_service("GoogleAdsService")

                        query = """
                            SELECT
                                customer.id,
                                customer.descriptive_name,
                                customer.currency_code,
                                customer.time_zone,
                                customer.manager
                            FROM customer
                            LIMIT 1
                        """

                        response = ga_service.search(
                            customer_id=customer_id, query=query
                        )

                        for row in response:
                            # Skip manager accounts (MCC accounts)
                            if not row.customer.manager:
                                accounts.append(
                                    {
                                        "account_id": str(row.customer.id),
                                        "account_name": row.customer.descriptive_name,
                                        "currency_code": row.customer.currency_code,
                                        "time_zone": row.customer.time_zone,
                                    }
                                )
                                print(
                                    f"DEBUG: Found Google Ads account: {row.customer.descriptive_name} (ID: {row.customer.id})"
                                )

                    except GoogleAdsException as e:
                        print(f"DEBUG: Could not access account {customer_id}: {e}")
                        continue

            else:
                # No Developer Token - cannot fetch real accounts
                print("❌ No Developer Token found")
                raise Exception(
                    "GOOGLE_ADS_DEVELOPER_TOKEN is required to connect Google Ads accounts. Please configure it in your .env file."
                )

        except Exception as e:
            error_msg = str(e)
            print(f"❌ Google Ads API error: {error_msg}")

            # Even if Google Ads API fails, we can still create a connection
            # The user can use the OAuth token for other Google services
            accounts = [
                {
                    "account_id": "oauth_connected",
                    "account_name": f"Google Ads Account (OAuth Connected)",
                    "manager_account": False,
                    "currency_code": "USD",
                    "time_zone": "UTC",
                }
            ]

            print(f"⚠️ Using fallback account entry due to API error: {error_msg}")

        if not accounts:
            return OAuthCallbackResponse(
                success=False,
                message="No Google Ads accounts found for this account. Make sure you have access to at least one Google Ads account.",
            )

        print(f"DEBUG: Found {len(accounts)} Google Ads accounts total")

        # Debug: Print all accounts found
        for i, account in enumerate(accounts):
            print(
                f"DEBUG: Account {i+1}: {account['account_name']} (ID: {account['account_id']})"
            )

        # Use campaigner_id from JWT state (already validated above)
        from app.models.users import Campaigner
        from app.config.database import get_session
        from sqlmodel import select

        with get_session() as session:
            # Get the campaigner who initiated this OAuth flow
            campaigner = session.exec(
                select(Campaigner).where(Campaigner.id == campaigner_id)
            ).first()

            if not campaigner:
                print(f"DEBUG: Campaigner {campaigner_id} not found in database")
                return OAuthCallbackResponse(
                    success=False, message="No user found. Please sign in first."
                )

            print(
                f"DEBUG: OAuth successful for campaigner {campaigner.id} ({campaigner.email}), connecting for customer {customer_id}"
            )

        return OAuthCallbackResponse(
            success=True,
            message="OAuth successful! Please select an account to connect.",
            account_name=None,  # No account selected yet
            account_id=None,  # No account selected yet
            connection_id=None,  # No connection created yet
            access_token=credentials.token,
            refresh_token=credentials.refresh_token or "",
            expires_in=3600,
            accounts=accounts,  # Include the accounts list for frontend selection
        )

    except Exception as e:
        print(f"DEBUG: Google Ads OAuth callback failed with error: {str(e)}")
        import traceback

        traceback.print_exc()
        return OAuthCallbackResponse(success=False, message=f"OAuth failed: {str(e)}")


@router.post("/create-connection")
async def create_google_ads_connection(request: CreateConnectionRequest):
    """
    Create Google Ads connection after user selects an account
    """
    print(
        f"DEBUG: Creating Google Ads connection for account {request.account_id} ({request.account_name})"
    )

    try:
        # Use campaigner_id from request (no need to look up by email)
        from app.models.users import Campaigner
        from app.config.database import get_session
        from sqlmodel import select

        # Validate that campaigner exists
        with get_session() as session:
            campaigner = session.exec(
                select(Campaigner).where(Campaigner.id == request.campaigner_id)
            ).first()

            if not campaigner:
                return {
                    "success": False,
                    "message": f"Campaigner {request.campaigner_id} not found in database",
                }

            print(
                f"DEBUG: Creating Google Ads connection for campaigner {campaigner.id} ({campaigner.email}), customer {request.customer_id}"
            )

            # Create Google Ads connection using the service
            from app.services.google_ads_service import GoogleAdsService

            ads_service = GoogleAdsService()

            # Create the connection
            connection_result = await ads_service.save_google_ads_connection(
                campaigner_id=request.campaigner_id,  # Use campaigner_id from request
                customer_id=request.customer_id,
                account_id=request.account_id,
                account_name=request.account_name,
                access_token=request.access_token,
                refresh_token=request.refresh_token,
                expires_in=request.expires_in,
                account_email=campaigner.email,  # Use campaigner's email
            )

            print(
                f"DEBUG: Google Ads connection created successfully: {connection_result}"
            )

            return {
                "success": True,
                "message": f"Successfully connected to Google Ads: {request.account_name}",
                "connection_id": connection_result.get("connection_id"),
                "account_id": request.account_id,
                "account_name": request.account_name,
            }

    except Exception as e:
        print(f"DEBUG: Failed to create Google Ads connection: {str(e)}")
        import traceback

        traceback.print_exc()
        return {"success": False, "message": f"Failed to create connection: {str(e)}"}


@router.post("/get-accounts")
async def get_google_ads_accounts(request: dict):
    """
    Get available Google Ads accounts using access token
    """
    access_token = request.get("access_token")
    if not access_token:
        return {"success": False, "message": "Access token required"}

    print(
        f"DEBUG: Getting Google Ads accounts for access token: {access_token[:10]}..."
    )

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

        # Get Google Ads accounts
        accounts = []
        try:
            from google.ads.googleads.client import GoogleAdsClient
            from google.ads.googleads.errors import GoogleAdsException

            # Create Google Ads client
            client = GoogleAdsClient.load_from_dict(
                {
                    "developer_token": os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN", ""),
                    "client_id": os.getenv("GOOGLE_CLIENT_ID", ""),
                    "client_secret": os.getenv("GOOGLE_CLIENT_SECRET", ""),
                    "refresh_token": credentials.refresh_token,
                    "use_proto_plus": True,
                }
            )

            print("DEBUG: Fetching Google Ads accounts from Google...")

            # List all accessible customer accounts
            customer_service = client.get_service("CustomerService")
            accessible_customers = customer_service.list_accessible_customers()

            for customer_resource_name in accessible_customers.resource_names:
                customer_id = customer_resource_name.split("/")[-1]

                try:
                    # Get customer details using GoogleAdsService and a query
                    # This is the correct way in Google Ads API v21
                    ga_service = client.get_service("GoogleAdsService")

                    query = """
                        SELECT
                            customer.id,
                            customer.descriptive_name,
                            customer.currency_code,
                            customer.time_zone,
                            customer.manager
                        FROM customer
                        LIMIT 1
                    """

                    response = ga_service.search(customer_id=customer_id, query=query)

                    for row in response:
                        # Skip manager accounts (MCC accounts)
                        if not row.customer.manager:
                            accounts.append(
                                {
                                    "account_id": str(row.customer.id),
                                    "account_name": row.customer.descriptive_name,
                                    "currency_code": row.customer.currency_code,
                                    "time_zone": row.customer.time_zone,
                                }
                            )
                            print(
                                f"DEBUG: Found Google Ads account: {row.customer.descriptive_name} (ID: {row.customer.id})"
                            )

                except GoogleAdsException as e:
                    print(f"DEBUG: Could not access account {customer_id}: {e}")
                    continue

        except Exception as e:
            error_msg = str(e)
            print(f"DEBUG: Failed to get Google Ads accounts: {error_msg}")
            import traceback

            traceback.print_exc()

            # Return proper error messages instead of demo data
            if "SERVICE_DISABLED" in error_msg or "API has not been used" in error_msg:
                return {
                    "success": False,
                    "message": "Google Ads API is not enabled. Please enable it at: https://console.developers.google.com/apis/api/googleads.googleapis.com/overview?project=397762748853",
                }
            elif "DEVELOPER_TOKEN" in error_msg or not os.getenv(
                "GOOGLE_ADS_DEVELOPER_TOKEN"
            ):
                return {
                    "success": False,
                    "message": "Google Ads Developer Token is missing. Please set GOOGLE_ADS_DEVELOPER_TOKEN in your environment variables.",
                }
            else:
                return {
                    "success": False,
                    "message": f"Failed to fetch Google Ads accounts: {error_msg}",
                }

        if not accounts:
            return {
                "success": False,
                "message": "No Google Ads accounts found. Make sure you have access to at least one Google Ads account.",
            }

        print(f"DEBUG: Returning {len(accounts)} Google Ads accounts")

        return {
            "success": True,
            "accounts": accounts,
            "message": f"Found {len(accounts)} Google Ads accounts",
        }

    except Exception as e:
        print(f"DEBUG: Failed to get Google Ads accounts: {str(e)}")
        import traceback

        traceback.print_exc()
        return {"success": False, "message": f"Failed to get accounts: {str(e)}"}
