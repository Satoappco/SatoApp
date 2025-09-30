"""
Authentication utilities for JWT tokens and Google OAuth
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from google.auth.transport import requests
from google.oauth2 import id_token
from app.config.settings import get_settings
from app.models.users import User, UserSession
from app.config.database import get_session

settings = get_settings()
security = HTTPBearer()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT Configuration
ALGORITHM = "HS256"

# Get token expiration from settings, with development overrides
def get_token_expiration():
    settings = get_settings()
    # Use consistent expiration times for both development and production
    return {
        "access_token_minutes": settings.jwt_access_token_expire_minutes,  # 8 hours
        "refresh_token_days": settings.jwt_refresh_token_expire_days       # 30 days
    }

TOKEN_CONFIG = get_token_expiration()
ACCESS_TOKEN_EXPIRE_MINUTES = TOKEN_CONFIG["access_token_minutes"]
REFRESH_TOKEN_EXPIRE_DAYS = TOKEN_CONFIG["refresh_token_days"]


class AuthenticationError(HTTPException):
    """Custom authentication error"""
    def __init__(self, detail: str = "Authentication failed"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token"""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=ALGORITHM)
    
    # Log token creation for debugging
    print(f"DEBUG: Created JWT token expiring at {expire.isoformat()} (in {ACCESS_TOKEN_EXPIRE_MINUTES} minutes)")
    
    return encoded_jwt


def create_refresh_token(data: Dict[str, Any]) -> str:
    """Create JWT refresh token"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(token: str, token_type: str = "access") -> Dict[str, Any]:
    """Verify and decode JWT token"""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        
        # Check token type
        if payload.get("type") != token_type:
            print(f"DEBUG: Token type mismatch - expected {token_type}, got {payload.get('type')}")
            raise AuthenticationError("Invalid token type")
        
        # Check expiration
        exp = payload.get("exp")
        if exp is None:
            print("DEBUG: Token has no expiration claim")
            raise AuthenticationError("Token has expired")
        
        exp_time = datetime.fromtimestamp(exp)
        now = datetime.utcnow()
        
        if exp_time < now:
            print(f"DEBUG: Token expired at {exp_time.isoformat()}, current time {now.isoformat()}")
            raise AuthenticationError("Token has expired")
        
        print(f"DEBUG: Token valid until {exp_time.isoformat()}")
        return payload
    
    except JWTError as e:
        print(f"DEBUG: JWT decode error: {e}")
        raise AuthenticationError("Invalid token")


def verify_google_token(token: str) -> Dict[str, Any]:
    """Verify Google OAuth token"""
    try:
        # Verify the token with Google
        idinfo = id_token.verify_oauth2_token(
            token, 
            requests.Request(), 
            settings.google_client_id
        )
        
        # Check issuer
        if idinfo['iss'] not in ['accounts.google.com', 'https://accounts.google.com']:
            raise AuthenticationError("Invalid token issuer")
        
        return idinfo
    
    except ValueError:
        raise AuthenticationError("Invalid Google token")


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> User:
    """Get current authenticated user from JWT token"""
    
    try:
        # Verify the access token
        payload = verify_token(credentials.credentials, "access")
        user_id = payload.get("user_id")
        
        if user_id is None:
            raise AuthenticationError("Invalid token payload")
        
        # Get user from database
        with get_session() as session:
            user = session.get(User, user_id)
            if user is None:
                raise AuthenticationError("User not found")
            
            if user.status != "active":
                raise AuthenticationError("User account is not active")
            
            return user
    
    except JWTError:
        raise AuthenticationError("Invalid token")


def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """Get current active user (additional check)"""
    if current_user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    return current_user


def create_user_session(
    user: User, 
    access_token: str, 
    refresh_token: str,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
) -> UserSession:
    """Create a new user session"""
    
    import secrets
    
    session = UserSession(
        user_id=user.id,
        session_token=secrets.token_urlsafe(32),
        access_token=access_token,
        refresh_token=refresh_token,
        expires_at=datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        ip_address=ip_address,
        user_agent=user_agent,
        is_active=True
    )
    
    return session


def revoke_user_session(session_token: str) -> bool:
    """Revoke a user session"""
    
    with get_session() as db_session:
        session = db_session.query(UserSession).filter(
            UserSession.session_token == session_token
        ).first()
        
        if session:
            session.is_active = False
            session.revoked_at = datetime.utcnow()
            db_session.add(session)
            db_session.commit()
            return True
    
    return False


def refresh_access_token(refresh_token: str) -> Dict[str, str]:
    """Refresh access token using refresh token"""
    
    # Verify refresh token
    payload = verify_token(refresh_token, "refresh")
    user_id = payload.get("user_id")
    
    if user_id is None:
        raise AuthenticationError("Invalid refresh token")
    
    # Get user from database
    with get_session() as session:
        user = session.get(User, user_id)
        if user is None or user.status != "active":
            raise AuthenticationError("User not found or inactive")
        
        # Create new access token
        access_token_data = {
            "user_id": user.id,
            "email": user.email,
            "role": user.role,
            "primary_customer_id": user.primary_customer_id
        }
        
        new_access_token = create_access_token(access_token_data)
        
        return {
            "access_token": new_access_token,
            "token_type": "bearer"
        }


def hash_password(password: str) -> str:
    """Hash password using bcrypt"""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash"""
    return pwd_context.verify(plain_password, hashed_password)
