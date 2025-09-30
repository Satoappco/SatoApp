"""
Authentication routes for JWT token management
Handles user login, token refresh, and session management
"""

from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, HTTPException, status, Depends, Request
from pydantic import BaseModel
from sqlmodel import select

from app.core.auth import create_access_token, get_current_user, verify_google_token, ACCESS_TOKEN_EXPIRE_MINUTES
from app.config.database import get_session
from app.config.settings import get_settings
from app.models.users import User, Customer, CustomerType, CustomerStatus, UserRole, UserStatus

router = APIRouter(prefix="/auth", tags=["Authentication"])


class GoogleAuthRequest(BaseModel):
    google_token: str
    user_info: Optional[dict] = None


class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str
    role: str
    status: str
    primary_customer_id: int
    additional_customer_ids: list
    locale: str
    timezone: str
    avatar_url: Optional[str]
    email_verified: bool
    last_login_at: Optional[datetime]


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in: int
    user: UserResponse


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
            google_id = google_user_info.get("sub")
            email = google_user_info.get("email")
            full_name = google_user_info.get("name")
            avatar_url = google_user_info.get("picture")
            email_verified = google_user_info.get("email_verified", False)
        elif auth_request.user_info:
            # Use user_info from frontend
            google_id = f"google_{auth_request.user_info.get('email', '')}"
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
            statement = select(User).where(
                (User.google_id == google_id) | (User.email == email)
            )
            existing_user = session.exec(statement).first()
            
            if existing_user:
                # Update existing user with Google info
                existing_user.google_id = google_id
                existing_user.avatar_url = avatar_url
                existing_user.email_verified = email_verified
                existing_user.last_login_at = datetime.utcnow()
                
                session.add(existing_user)
                session.commit()
                session.refresh(existing_user)
                user = existing_user
                
            else:
                # Check if we have any customers, if not create a default one
                
                customers = session.exec(select(Customer)).all()
                if not customers:
                    # Create default customer first (without primary_contact_user_id for now)
                    default_customer = Customer(
                        name="Default Agency",
                        type=CustomerType.AGENCY,
                        status=CustomerStatus.ACTIVE,
                        plan="basic",
                        billing_currency="USD",
                        address="Default Address"
                    )
                    session.add(default_customer)
                    session.commit()
                    session.refresh(default_customer)
                    customer_id = default_customer.id
                else:
                    customer_id = customers[0].id
                
                # Create new user
                user = User(
                    email=email,
                    full_name=full_name,
                    google_id=google_id,
                    avatar_url=avatar_url,
                    email_verified=email_verified,
                    role=UserRole.VIEWER,  # Default role
                    status=UserStatus.ACTIVE,
                    provider="google",
                    locale="he-IL",
                    timezone="Asia/Jerusalem",
                    primary_customer_id=customer_id,
                    additional_customer_ids=[],
                    last_login_at=datetime.utcnow()
                )
                
                session.add(user)
                session.commit()
                session.refresh(user)
            
            # Create JWT tokens
            token_data = {
                "user_id": user.id,
                "email": user.email,
                "role": user.role,
                "primary_customer_id": user.primary_customer_id
            }
            
            access_token = create_access_token(data=token_data)
            
            return TokenResponse(
                access_token=access_token,
                token_type="bearer",
                expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,  # Convert minutes to seconds
                user=UserResponse(
                    id=user.id,
                    email=user.email,
                    full_name=user.full_name,
                    role=user.role,
                    status=user.status,
                    primary_customer_id=user.primary_customer_id,
                    additional_customer_ids=user.additional_customer_ids,
                    locale=user.locale,
                    timezone=user.timezone,
                    avatar_url=user.avatar_url,
                    email_verified=user.email_verified,
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


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """
    Get current user information
    """
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        role=current_user.role,
        status=current_user.status,
        primary_customer_id=current_user.primary_customer_id,
        additional_customer_ids=current_user.additional_customer_ids,
        locale=current_user.locale,
        timezone=current_user.timezone,
        avatar_url=current_user.avatar_url,
        email_verified=current_user.email_verified,
        last_login_at=current_user.last_login_at
    )


@router.post("/refresh")
async def refresh_token(current_user: User = Depends(get_current_user)):
    """
    Refresh access token
    """
    token_data = {
        "user_id": current_user.id,
        "email": current_user.email,
        "role": current_user.role,
        "primary_customer_id": current_user.primary_customer_id
    }
    
    new_access_token = create_access_token(data=token_data)
    
    return {
        "access_token": new_access_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60  # Convert minutes to seconds
    }


@router.get("/sessions")
async def get_user_sessions(current_user: User = Depends(get_current_user)):
    """
    Get user's active sessions
    """
    # For now, return basic session info
    # In production, you might want to track sessions in Redis or database
    with get_session() as session:
        user = session.get(User, current_user.id)
        
        session_data = [{
            "session_id": f"session_{current_user.id}",
            "user_id": current_user.id,
            "email": current_user.email,
            "last_login": user.last_login_at.isoformat() if user.last_login_at else None,
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