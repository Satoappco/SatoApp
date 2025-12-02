"""
Tests for debug campaigners routes
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi import HTTPException
from app.api.v1.routes.debug_campaigners import (
    get_campaigner_by_id_debug,
    authenticate_as_campaigner_debug,
)
from app.models.users import Campaigner


class TestGetCampaignerByIdDebug:
    """Test get_campaigner_by_id_debug endpoint"""

    @pytest.mark.asyncio
    @patch("app.api.v1.routes.debug_campaigners.os.getenv")
    async def test_non_development_environment_blocked(self, mock_getenv):
        """Test that endpoint is blocked in non-development environments"""
        mock_getenv.return_value = "production"

        with pytest.raises(HTTPException) as exc_info:
            await get_campaigner_by_id_debug(1)

        assert exc_info.value.status_code == 403
        assert "development mode" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    @patch("app.api.v1.routes.debug_campaigners.os.getenv")
    @patch("app.api.v1.routes.debug_campaigners.get_session")
    async def test_campaigner_not_found(self, mock_get_session, mock_getenv):
        """Test handling when campaigner is not found"""
        mock_getenv.return_value = "development"
        mock_session = MagicMock()
        mock_session.get.return_value = None
        mock_get_session.return_value.__enter__.return_value = mock_session

        with pytest.raises(HTTPException) as exc_info:
            await get_campaigner_by_id_debug(999)

        assert exc_info.value.status_code == 404
        assert "Campaigner with ID 999 not found" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    @patch("app.api.v1.routes.debug_campaigners.os.getenv")
    @patch("app.api.v1.routes.debug_campaigners.get_session")
    async def test_successful_campaigner_retrieval(self, mock_get_session, mock_getenv):
        """Test successful campaigner data retrieval"""
        mock_getenv.return_value = "development"

        # Create mock campaigner
        mock_campaigner = MagicMock(spec=Campaigner)
        mock_campaigner.id = 1
        mock_campaigner.email = "test@example.com"
        mock_campaigner.full_name = "Test User"
        mock_campaigner.role = "campaigner"
        mock_campaigner.status = "active"
        mock_campaigner.avatar_url = "https://example.com/avatar.jpg"
        mock_campaigner.email_verified = True
        mock_campaigner.agency_id = 1
        mock_campaigner.last_login_at = None
        mock_campaigner.created_at = None
        mock_campaigner.phone = "+1234567890"
        mock_campaigner.locale = "en"
        mock_campaigner.timezone = "UTC"
        mock_campaigner.google_id = "google_123"

        mock_session = MagicMock()
        mock_session.get.return_value = mock_campaigner
        mock_get_session.return_value.__enter__.return_value = mock_session

        result = await get_campaigner_by_id_debug(1)

        assert result["id"] == 1
        assert result["email"] == "test@example.com"
        assert result["name"] == "Test User"
        assert result["full_name"] == "Test User"
        assert result["role"] == "campaigner"
        assert result["status"] == "active"
        assert result["profile_image_url"] == "https://example.com/avatar.jpg"
        assert result["avatar_url"] == "https://example.com/avatar.jpg"
        assert result["email_verified"] is True
        assert result["agency_id"] == 1
        assert result["last_login_at"] is None
        assert result["created_at"] is None
        assert result["phone"] == "+1234567890"
        assert result["locale"] == "en"
        assert result["timezone"] == "UTC"
        assert result["google_id"] == "google_123"

    @pytest.mark.asyncio
    @patch("app.api.v1.routes.debug_campaigners.os.getenv")
    @patch("app.api.v1.routes.debug_campaigners.get_session")
    async def test_database_error_handling(self, mock_get_session, mock_getenv):
        """Test handling of database errors"""
        mock_getenv.return_value = "development"

        mock_session = MagicMock()
        mock_session.get.side_effect = Exception("Database connection failed")
        mock_get_session.return_value.__enter__.return_value = mock_session

        with pytest.raises(HTTPException) as exc_info:
            await get_campaigner_by_id_debug(1)

        assert exc_info.value.status_code == 500
        assert "Failed to get campaigner" in str(exc_info.value.detail)


class TestAuthenticateAsCampaignerDebug:
    """Test authenticate_as_campaigner_debug endpoint"""

    @pytest.mark.asyncio
    @patch("app.api.v1.routes.debug_campaigners.os.getenv")
    async def test_non_development_environment_blocked_auth(self, mock_getenv):
        """Test that auth endpoint is blocked in non-development environments"""
        mock_getenv.return_value = "production"

        with pytest.raises(HTTPException) as exc_info:
            await authenticate_as_campaigner_debug(1)

        assert exc_info.value.status_code == 403
        assert "development mode" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    @patch("app.api.v1.routes.debug_campaigners.os.getenv")
    @patch("app.api.v1.routes.debug_campaigners.get_session")
    async def test_campaigner_not_found_auth(self, mock_get_session, mock_getenv):
        """Test handling when campaigner is not found for auth"""
        mock_getenv.return_value = "development"
        mock_session = MagicMock()
        mock_session.get.return_value = None
        mock_get_session.return_value.__enter__.return_value = mock_session

        with pytest.raises(HTTPException) as exc_info:
            await authenticate_as_campaigner_debug(999)

        assert exc_info.value.status_code == 404
        assert "Campaigner with ID 999 not found" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    @patch("app.api.v1.routes.debug_campaigners.os.getenv")
    @patch("app.api.v1.routes.debug_campaigners.create_access_token")
    @patch("app.api.v1.routes.debug_campaigners.create_refresh_token")
    @patch("app.api.v1.routes.debug_campaigners.get_session")
    async def test_successful_authentication(
        self, mock_get_session, mock_refresh_token, mock_access_token, mock_getenv
    ):
        """Test successful campaigner authentication"""
        mock_getenv.return_value = "development"
        mock_access_token.return_value = "access_token_123"
        mock_refresh_token.return_value = "refresh_token_456"

        # Create mock campaigner
        mock_campaigner = MagicMock(spec=Campaigner)
        mock_campaigner.id = 1
        mock_campaigner.email = "test@example.com"
        mock_campaigner.full_name = "Test User"
        mock_campaigner.role = "campaigner"
        mock_campaigner.status = "active"
        mock_campaigner.avatar_url = "https://example.com/avatar.jpg"
        mock_campaigner.email_verified = True
        mock_campaigner.agency_id = 1
        mock_campaigner.last_login_at = None
        mock_campaigner.created_at = None
        mock_campaigner.phone = "+1234567890"
        mock_campaigner.locale = "en"
        mock_campaigner.timezone = "UTC"
        mock_campaigner.google_id = "google_123"

        mock_session = MagicMock()
        mock_session.get.return_value = mock_campaigner
        mock_get_session.return_value.__enter__.return_value = mock_session

        result = await authenticate_as_campaigner_debug(1)

        assert result["access_token"] == "access_token_123"
        assert result["refresh_token"] == "refresh_token_456"
        assert result["token_type"] == "bearer"

        user_data = result["user"]
        assert user_data["id"] == 1
        assert user_data["email"] == "test@example.com"
        assert user_data["name"] == "Test User"
        assert user_data["role"] == "campaigner"

        # Verify tokens were created with correct payload
        mock_access_token.assert_called_once_with({"user_id": 1})
        mock_refresh_token.assert_called_once_with({"user_id": 1})

    @pytest.mark.asyncio
    @patch("app.api.v1.routes.debug_campaigners.os.getenv")
    @patch("app.api.v1.routes.debug_campaigners.get_session")
    async def test_auth_database_error_handling(self, mock_get_session, mock_getenv):
        """Test handling of database errors in auth"""
        mock_getenv.return_value = "development"

        mock_session = MagicMock()
        mock_session.get.side_effect = Exception("Database connection failed")
        mock_get_session.return_value.__enter__.return_value = mock_session

        with pytest.raises(HTTPException) as exc_info:
            await authenticate_as_campaigner_debug(1)

        assert exc_info.value.status_code == 500
        assert "Failed to authenticate as campaigner" in str(exc_info.value.detail)


class TestEnvironmentChecks:
    """Test environment validation logic"""

    @pytest.mark.asyncio
    @patch("app.api.v1.routes.debug_campaigners.os.getenv")
    async def test_development_environments_allowed(self, mock_getenv):
        """Test that various development environment names are allowed"""
        for env in ["development", "dev", "local"]:
            mock_getenv.return_value = env

            # Should not raise an exception for environment check
            try:
                # We can't call the actual functions without mocking everything,
                # but we can test the environment check logic by triggering it
                await get_campaigner_by_id_debug(1)
            except HTTPException as e:
                # Should not be a 403 error
                assert e.status_code != 403
            except:
                # Other errors are expected (like missing session mocks)
                pass

    @pytest.mark.asyncio
    @patch("app.api.v1.routes.debug_campaigners.os.getenv")
    async def test_production_environments_blocked(self, mock_getenv):
        """Test that production and other non-dev environments are blocked"""
        for env in ["production", "staging", "test", None]:
            mock_getenv.return_value = env

            with pytest.raises(HTTPException) as exc_info:
                await get_campaigner_by_id_debug(1)

            assert exc_info.value.status_code == 403
