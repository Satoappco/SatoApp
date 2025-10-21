"""
Authentication routes for JWT token management
Handles user login, token refresh, and session management
"""

from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, HTTPException, status, Depends, Request
from pydantic import BaseModel
from sqlmodel import select
from jose import jwt
import logging

logger = logging.getLogger(__name__)

from app.core.auth import create_access_token, create_refresh_token, get_current_user, verify_google_token, ACCESS_TOKEN_EXPIRE_MINUTES, ALGORITHM
from app.config.database import get_session
from app.config.settings import get_settings
from app.models.users import Campaigner, Agency, CustomerType, CustomerStatus, UserRole, UserStatus

router = APIRouter(prefix="/auth", tags=["Authentication"])


class GoogleAuthRequest(BaseModel):
    google_token: str
    user_info: Optional[dict] = None


class CampaignerResponse(BaseModel):
    id: int
    email: str
    full_name: str
    role: str
    status: str
    agency_id: int
    phone: Optional[str]
    google_id: Optional[str]
    email_verified: bool
    avatar_url: Optional[str]
    locale: str
    timezone: str
    last_login_at: Optional[datetime]


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int
    user: CampaignerResponse


@router.post("/google", response_model=TokenResponse)
async def authenticate_with_google(
    auth_request: GoogleAuthRequest,
    request: Request
):
    """
    Authenticate user with Google OAuth token
    Creates new user if doesn't exist, or logs in existing user
    """
    
    try:
        # Try to verify Google token first, fallback to user_info if available
        google_user_info = None
        if auth_request.google_token:
            try:
                google_user_info = verify_google_token(auth_request.google_token)
            except Exception as e:
                print(f"Google token verification failed: {e}")
                google_user_info = None
        
        # Extract user information from Google token or user_info
        if google_user_info:
            google_id = google_user_info.get("sub")  # Unique Google user ID
            email = google_user_info.get("email")
            full_name = google_user_info.get("name")
            avatar_url = google_user_info.get("picture")
            email_verified = google_user_info.get("email_verified", False)
        elif auth_request.user_info:
            # Use user_info from frontend
            google_id = f"google_{auth_request.user_info.get('email', '')}"  # Fallback ID
            email = auth_request.user_info.get("email")
            full_name = auth_request.user_info.get("name")
            avatar_url = auth_request.user_info.get("picture")
            email_verified = True  # Assume verified if coming from OAuth
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No valid Google token or user info provided"
            )
        
        if not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email is required for authentication"
            )
        
        with get_session() as session:
            # Check if user exists by Google ID or email
            statement = select(Campaigner).where(
                (Campaigner.google_id == google_id) | (Campaigner.email == email)
            )
            existing_user = session.exec(statement).first()
            
            if existing_user:
                # Update Google OAuth fields
                existing_user.google_id = google_id
                existing_user.email_verified = email_verified
                existing_user.avatar_url = avatar_url
                existing_user.last_login_at = datetime.utcnow()
                
                # Merge full_name: prefer Google if admin left it empty or generic
                if full_name and (not existing_user.full_name or len(existing_user.full_name.strip()) < 3):
                    existing_user.full_name = full_name
                
                # Auto-activate INVITED users on first Google login
                if existing_user.status == UserStatus.INVITED:
                    existing_user.status = UserStatus.ACTIVE
                
                session.add(existing_user)
                session.commit()
                session.refresh(existing_user)
                user = existing_user
                
            else:
                # Block new user signup - registration is invite-only
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Registration is invite-only. Please contact your administrator for access."
                )
                
                # OLD LOGIC - Uncomment to restore automatic agency creation for new users
                # # Create a new agency for the new user
                # # Extract domain from email for agency name
                # email_domain = email.split('@')[1] if '@' in email else 'unknown'
                # agency_name = f"{full_name}'s Agency" if full_name else f"{email_domain} Agency"
                # 
                # new_agency = Agency(
                #     name=agency_name,
                #     email=email,
                #     phone=None,
                #     status=CustomerStatus.ACTIVE
                # )
                # session.add(new_agency)
                # session.commit()
                # session.refresh(new_agency)
                # agency_id = new_agency.id
                # 
                # # Create new user as OWNER of the new agency
                # user = Campaigner(
                #     email=email,
                #     full_name=full_name,
                #     google_id=google_id,
                #     avatar_url=avatar_url,
                #     email_verified=email_verified,
                #     locale="he-IL",
                #     timezone="Asia/Jerusalem",
                #     last_login_at=datetime.utcnow(),
                #     role=UserRole.OWNER,  # New users become OWNER of their agency
                #     status=UserStatus.ACTIVE,
                #     agency_id=agency_id
                # )
                # 
                # session.add(user)
                # session.commit()
                # session.refresh(user)
                # 
                # # Create default data for new user's agency
                # try:
                #     from app.services.default_data_service import default_data_service
                #     default_data_service.create_default_data_for_agency(agency_id)
                #     logger.info(f"✅ Created default data for new user's agency {agency_id}")
                # except Exception as e:
                #     logger.warning(f"⚠️ Failed to create default data for agency {agency_id}: {str(e)}")
                #     # Don't fail user creation if default data fails
            # Create JWT tokens
            token_data = {
                "user_id": user.id,
                "email": user.email,
                "role": user.role,
                "agency_id": user.agency_id
            }
            
            access_token = create_access_token(data=token_data)
            refresh_token = create_refresh_token(data=token_data)
            
            return TokenResponse(
                access_token=access_token,
                refresh_token=refresh_token,
                token_type="bearer",
                expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,  # Convert minutes to seconds
                user=CampaignerResponse(
                    id=user.id,
                    email=user.email,
                    full_name=user.full_name,
                    role=user.role,
                    status=user.status,
                    agency_id=user.agency_id,
                    phone=user.phone,
                    google_id=user.google_id,
                    email_verified=user.email_verified,
                    avatar_url=user.avatar_url,
                    locale=user.locale,
                    timezone=user.timezone,
                    last_login_at=user.last_login_at
                )
            )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Authentication failed: {str(e)}"
        )


@router.get("/me", response_model=CampaignerResponse)
async def get_current_user_info(current_user: Campaigner = Depends(get_current_user)):
    """
    Get current user information
    """
    return CampaignerResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        role=current_user.role,
        status=current_user.status,
        agency_id=current_user.agency_id,
        phone=current_user.phone,
        google_id=current_user.google_id,
        email_verified=current_user.email_verified,
        avatar_url=current_user.avatar_url,
        locale=current_user.locale,
        timezone=current_user.timezone,
        last_login_at=current_user.last_login_at
    )


class RefreshTokenRequest(BaseModel):
    refresh_token: str


@router.post("/refresh")
async def refresh_token(request: RefreshTokenRequest):
    """
    Refresh access token using refresh token
    """
    try:
        # Verify the refresh token
        payload = jwt.decode(
            request.refresh_token,
            get_settings().secret_key,
            algorithms=[ALGORITHM]
        )
        
        # Check token type
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type"
            )
        
        # Check expiration
        exp = payload.get("exp")
        if exp is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired"
            )
        
        exp_time = datetime.fromtimestamp(exp)
        now = datetime.utcnow()
        
        if exp_time < now:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token has expired"
            )
        
        # Get user ID from refresh token
        user_id = payload.get("user_id")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )
        
        # Get user from database
        with get_session() as session:
            statement = select(Campaigner).where(Campaigner.id == user_id)
            user = session.exec(statement).first()
            
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="User not found"
                )
        
        # Create new access token
        token_data = {
            "user_id": user.id,
            "email": user.email,
            "role": user.role,
            "agency_id": user.agency_id
        }
        
        new_access_token = create_access_token(data=token_data)
        new_refresh_token = create_refresh_token(data=token_data)
        
        return {
            "access_token": new_access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer",
            "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60  # Convert minutes to seconds
        }
        
    except jwt.JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Token refresh failed: {str(e)}"
        )


@router.get("/sessions")
async def get_user_sessions(current_user: Campaigner = Depends(get_current_user)):
    """
    Get user's active sessions
    """
    # For now, return basic session info
    # In production, you might want to track sessions in Redis or database
    with get_session() as session:
        user = session.get(Campaigner, current_user.id)
        
        session_data = [{
            "session_id": f"session_{current_user.id}",
            "user_id": current_user.id,
            "email": current_user.email,
            "phone": user.phone,
            "is_current": True
        }]

        
        return {"sessions": session_data}


@router.get("/google/callback")
async def google_oauth_callback(
    code: str,
    state: Optional[str] = None,
    error: Optional[str] = None
):
    """
    Handle Google OAuth callback for service data connection
    This endpoint receives the OAuth callback and redirects to the frontend
    """
    
    if error:
        # Handle OAuth error
        return {"error": f"OAuth error: {error}"}
    
    if not code:
        return {"error": "No authorization code received"}
    
    try:
        # Import the Google Analytics OAuth handler
        from app.api.v1.routes.google_analytics_oauth import handle_oauth_callback, OAuthCallbackRequest
        
        # Create the callback request
        callback_request = OAuthCallbackRequest(
            code=code,
            redirect_uri="https://localhost:8000/api/v1/auth/google/callback"
        )
        
        # Process the OAuth callback
        result = await handle_oauth_callback(callback_request)
        
        if result.success and result.access_token:
            # Store OAuth tokens temporarily and redirect to dual selection (GA + Ads)
            try:
                from app.api.v1.routes.google_analytics_oauth import get_ga_properties
                from app.services.google_analytics_service import GoogleAnalyticsService
                
                # Get available GA properties
                properties_response = await get_ga_properties({"access_token": result.access_token})
                
                # Create a temporary connection to get Google Ads accounts
                # We need to create a minimal connection first to use the get_google_ads_accounts method
                ga_service = GoogleAnalyticsService()
                
                # Get Google Ads accounts using the OAuth tokens directly
                ads_accounts = []
                try:
                    # We'll create a temporary method to get ads accounts without a connection
                    from google.ads.googleads.client import GoogleAdsClient
                    import os
                    
                    # Get Google Ads developer token
                    developer_token = os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN", os.getenv("GOOGLE_DEVELOPER_TOKEN", ""))
                    if developer_token:
                        # Create Google Ads client
                        client = GoogleAdsClient.load_from_dict({
                            "developer_token": developer_token,
                            "client_id": os.getenv("GOOGLE_CLIENT_ID"),
                            "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
                            "refresh_token": result.refresh_token,
                            "use_proto_plus": True
                        })
                        
                        # Get customer service
                        customer_service = client.get_service("CustomerService")
                        
                        # List accessible customers
                        accessible_customers = customer_service.list_accessible_customers()
                        
                        for customer_resource in accessible_customers.resource_names:
                            customer_id = customer_resource.split('/')[-1]
                            
                            try:
                                # Get customer details
                                customer = customer_service.get_customer(resource_name=customer_resource)
                                ads_accounts.append({
                                    "customer_id": customer_id,
                                    "customer_name": customer.descriptive_name or f"Account {customer_id}",
                                    "currency_code": customer.currency_code,
                                    "time_zone": customer.time_zone
                                })
                            except Exception as e:
                                print(f"DEBUG: Failed to get customer {customer_id}: {e}")
                                # Add basic info even if we can't get details
                                ads_accounts.append({
                                    "customer_id": customer_id,
                                    "customer_name": f"Google Ads Account {customer_id}",
                                    "currency_code": "USD",
                                    "time_zone": "UTC"
                                })
                    
                    print(f"DEBUG: Found {len(ads_accounts)} Google Ads accounts")
                
                except Exception as e:
                    print(f"DEBUG: Failed to get Google Ads accounts: {e}")
                    # Continue without ads accounts if there's an error
                    ads_accounts = []
                
                if properties_response.get("success") and properties_response.get("properties"):
                    properties = properties_response["properties"]
                    
                    # Encode BOTH properties and ads accounts for frontend
                    import json
                    import base64
                    dual_data = {
                        "ga_properties": properties,
                        "ads_accounts": ads_accounts,
                        "access_token": result.access_token,
                        "refresh_token": result.refresh_token or "",
                        "expires_in": result.expires_in or 3600
                    }
                    
                    # Encode the data for URL parameter
                    encoded_data = base64.b64encode(json.dumps(dual_data).encode()).decode()
                    
                    # Redirect to frontend with dual selection
                    from fastapi.responses import RedirectResponse
                    settings = get_settings()
                    return RedirectResponse(
                        url=f"{settings.frontend_url}/?oauth_dual_selection={encoded_data}",
                        status_code=302
                    )
                else:
                    # No properties found
                    from fastapi.responses import RedirectResponse
                    settings = get_settings()
                    return RedirectResponse(
                        url=f"{settings.frontend_url}/?oauth_error=true&message=No Google Analytics properties found",
                        status_code=302
                    )
                    
            except Exception as e:
                # Redirect to frontend with error message
                from fastapi.responses import RedirectResponse
                settings = get_settings()
                return RedirectResponse(
                    url=f"{settings.frontend_url}/?oauth_error=true&message=Failed to get accounts: {str(e)}",
                    status_code=302
                )
        else:
            # Redirect to frontend with error message
            from fastapi.responses import RedirectResponse
            settings = get_settings()
            return RedirectResponse(
                url=f"{settings.frontend_url}/?oauth_error=true&message={result.message}",
                status_code=302
            )
    
    except Exception as e:
        # Redirect to frontend with error message
        from fastapi.responses import RedirectResponse
        settings = get_settings()
        return RedirectResponse(
            url=f"{settings.frontend_url}/?oauth_error=true&message=OAuth callback failed: {str(e)}",
            status_code=302
        )