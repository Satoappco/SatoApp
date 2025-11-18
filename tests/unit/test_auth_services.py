"""
Unit tests for authentication services
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from jose import jwt
from app.core.auth import (
    create_access_token,
    create_refresh_token,
    verify_token,
    get_current_user,
    create_user_session,
    AuthenticationError,
)
from app.core.api_auth import APITokenService, verify_api_token
from app.models.users import Campaigner


class TestJWTAuthentication:
    """Test JWT token creation and verification"""

    def test_create_access_token(self):
        """Test access token creation"""
        from app.config.settings import get_settings

        settings = get_settings()

        data = {"campaigner_id": 1, "email": "test@example.com"}
        token = create_access_token(data)

        assert isinstance(token, str)
        assert len(token) > 0

        # Decode and verify
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        assert payload["campaigner_id"] == 1
        assert payload["email"] == "test@example.com"
        assert payload["type"] == "access"
        assert "exp" in payload

    def test_create_refresh_token(self):
        """Test refresh token creation"""
        from app.config.settings import get_settings

        settings = get_settings()

        data = {"campaigner_id": 1}
        token = create_refresh_token(data)

        assert isinstance(token, str)

        # Decode and verify
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        assert payload["campaigner_id"] == 1
        assert payload["type"] == "refresh"
        assert "exp" in payload

    def test_verify_token_valid(self, mock_settings):
        """Test token verification with valid token"""
        data = {"campaigner_id": 1, "type": "access"}
        token = create_access_token(data)

        payload = verify_token(token, "access")
        assert payload["campaigner_id"] == 1
        assert payload["type"] == "access"

    def test_verify_token_expired(self):
        """Test token verification with expired token"""
        # Create token that expires immediately
        data = {"campaigner_id": 1, "type": "access"}
        expired_token = create_access_token(data, expires_delta=timedelta(seconds=-1))

        with pytest.raises(AuthenticationError, match="Invalid token"):
            verify_token(expired_token, "access")

    def test_verify_token_wrong_type(self, mock_settings):
        """Test token verification with wrong token type"""
        data = {"campaigner_id": 1, "type": "refresh"}
        token = create_refresh_token(data)

        with pytest.raises(AuthenticationError, match="Invalid token type"):
            verify_token(token, "access")

    def test_verify_token_invalid(self, mock_settings):
        """Test token verification with invalid token"""
        with pytest.raises(AuthenticationError, match="Invalid token"):
            verify_token("invalid.token.here", "access")


class TestAPITokenAuthentication:
    """Test API token authentication"""

    def test_api_token_service_creation(self):
        """Test API token service initialization"""
        service = APITokenService()
        assert hasattr(service, "api_token")

    @patch("app.core.api_auth.get_settings")
    def test_api_token_service_with_env_var(self, mock_get_settings):
        """Test API token service with environment variable"""
        # Mock settings to return None for api_token
        mock_settings = Mock()
        mock_settings.api_token = None
        mock_get_settings.return_value = mock_settings

        # Mock environment variables
        with patch.dict(
            "os.environ", {"WEBHOOK_API_TOKEN": "test-api-token"}, clear=True
        ):
            service = APITokenService()
            assert service.api_token == "test-api-token"

    def test_validate_token_valid(self):
        """Test valid API token validation"""
        service = APITokenService()
        service.api_token = "test-token"

        result = service.validate_token("test-token")
        assert result is not None
        assert result["service"] == "universal"
        assert result["token"] == "test-token"
        assert result["valid"] is True

    def test_validate_token_invalid(self):
        """Test invalid API token validation"""
        service = APITokenService()
        service.api_token = "test-token"

        result = service.validate_token("wrong-token")
        assert result is None

    def test_validate_token_no_token_set(self):
        """Test token validation when no token is configured"""
        service = APITokenService()
        service.api_token = None

        result = service.validate_token("any-token")
        assert result is None

    def test_get_token_permissions(self):
        """Test token permissions retrieval"""
        service = APITokenService()
        permissions = service.get_token_permissions("universal")

        expected_permissions = [
            "webhooks:write",
            "dialogcx:access",
            "crewai:test",
            "analysis:run",
            "api:test",
            "endpoints:access",
        ]
        assert permissions == expected_permissions


class TestUserAuthentication:
    """Test user authentication and session management"""

    @patch("app.core.auth.get_session")
    def test_get_current_user_valid_token(self, mock_get_session, mock_settings):
        """Test getting current user with valid token"""
        # Mock database session and user
        mock_session = Mock()
        mock_user = Mock(spec=Campaigner)
        mock_user.id = 1
        mock_user.email = "test@example.com"
        mock_user.status = "active"

        mock_session.get.return_value = mock_user
        mock_get_session.return_value.__enter__.return_value = mock_session

        # Create valid token
        data = {"campaigner_id": 1, "email": "test@example.com"}
        token = create_access_token(data)

        # Mock HTTPAuthorizationCredentials
        credentials = Mock()
        credentials.credentials = token

        user = get_current_user(credentials)
        assert user.id == 1
        assert user.email == "test@example.com"

    @patch("app.core.auth.get_session")
    def test_get_current_user_inactive_user(self, mock_get_session, mock_settings):
        """Test getting current user with inactive account"""
        # Mock database session and inactive user
        mock_session = Mock()
        mock_user = Mock(spec=Campaigner)
        mock_user.id = 1
        mock_user.status = "inactive"

        mock_session.get.return_value = mock_user
        mock_get_session.return_value.__enter__.return_value = mock_session

        # Create valid token
        data = {"campaigner_id": 1}
        token = create_access_token(data)

        credentials = Mock()
        credentials.credentials = token

        with pytest.raises(
            AuthenticationError, match="Campaigner account is not active"
        ):
            get_current_user(credentials)

    @patch("app.core.auth.get_session")
    def test_get_current_user_user_not_found(self, mock_get_session, mock_settings):
        """Test getting current user when user doesn't exist"""
        # Mock database session with no user found
        mock_session = Mock()
        mock_session.get.return_value = None
        mock_get_session.return_value.__enter__.return_value = mock_session

        # Create valid token
        data = {"campaigner_id": 999}
        token = create_access_token(data)

        credentials = Mock()
        credentials.credentials = token

        with pytest.raises(AuthenticationError, match="Campaigner not found"):
            get_current_user(credentials)

    def test_create_user_session(self, mock_settings):
        """Test user session creation"""
        mock_user = Mock(spec=Campaigner)
        mock_user.id = 1

        session = create_user_session(mock_user, "access_token", "refresh_token")

        assert session.campaigner_id == 1
        assert session.access_token == "access_token"
        assert session.refresh_token == "refresh_token"
        assert session.is_active is True
        assert isinstance(session.expires_at, datetime)


class TestAPITokenVerification:
    """Test API token verification functions"""

    @patch("app.core.api_auth.api_token_service")
    def test_verify_api_token_valid(self, mock_service):
        """Test API token verification with valid token"""
        mock_service.validate_token.return_value = {
            "service": "universal",
            "token": "test-token",
            "valid": True,
        }

        credentials = Mock()
        credentials.credentials = "test-token"

        result = verify_api_token(credentials)
        assert result["service"] == "universal"
        assert result["valid"] is True

    @patch("app.core.api_auth.api_token_service")
    def test_verify_api_token_invalid(self, mock_service):
        """Test API token verification with invalid token"""
        mock_service.validate_token.return_value = None

        credentials = Mock()
        credentials.credentials = "invalid-token"

        with pytest.raises(Exception):  # Should raise HTTPException
            verify_api_token(credentials)
