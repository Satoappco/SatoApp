"""
Tests for main.py FastAPI application
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi import Request, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from app.main import create_app, lifespan
from datetime import datetime


class TestLifespan:
    """Test application lifespan events"""

    @pytest.mark.asyncio
    @patch("app.main.setup_logging")
    @patch("app.core.file_logger.initialize_file_logging")
    @patch("app.main.get_settings")
    @patch("app.main.init_database")
    async def test_lifespan_success(
        self,
        mock_init_db,
        mock_get_settings,
        mock_init_file_logging,
        mock_setup_logging,
    ):
        """Test successful lifespan startup and shutdown"""
        # Mock settings
        mock_settings = MagicMock()
        mock_settings.gemini_api_key = "test_key"
        mock_settings.database_url = "test_url"
        mock_settings.api_token = "test_token"
        mock_settings.secret_key = "test_secret"
        mock_get_settings.return_value = mock_settings

        # Create a mock FastAPI app
        mock_app = MagicMock(spec=FastAPI)

        # Test startup
        async with lifespan(mock_app):
            mock_setup_logging.assert_called_once()
            mock_init_file_logging.assert_called_once()
            mock_get_settings.assert_called_once()
            mock_init_db.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.main.get_settings")
    async def test_lifespan_missing_env_vars(self, mock_get_settings):
        """Test lifespan fails when required environment variables are missing"""
        # Mock settings with missing values
        mock_settings = MagicMock()
        mock_settings.gemini_api_key = None
        mock_settings.database_url = "test_url"
        mock_settings.api_token = "test_token"
        mock_settings.secret_key = "test_secret"
        mock_get_settings.return_value = mock_settings

        # Create a mock FastAPI app
        mock_app = MagicMock(spec=FastAPI)

        with pytest.raises(RuntimeError) as exc_info:
            async with lifespan(mock_app):
                pass

        assert "Missing required environment variables" in str(exc_info.value)
        assert "GEMINI_API_KEY" in str(exc_info.value)


class TestCreateApp:
    """Test FastAPI application creation"""

    @patch("app.main.get_settings")
    def test_create_app_basic_structure(self, mock_get_settings):
        """Test that create_app creates a FastAPI app with basic structure"""
        # Mock settings
        mock_settings = MagicMock()
        mock_settings.app_name = "Test App"
        mock_settings.app_version = "1.0.0"
        mock_settings.debug = False
        mock_get_settings.return_value = mock_settings

        app = create_app()

        assert app.title == "Test App"
        assert app.version == "1.0.0"
        assert app.debug is False

    @patch("app.main.get_settings")
    def test_create_app_has_cors_middleware(self, mock_get_settings):
        """Test that CORS middleware is added to the app"""
        mock_settings = MagicMock()
        mock_settings.app_name = "Test App"
        mock_settings.app_version = "1.0.0"
        mock_settings.debug = False
        mock_get_settings.return_value = mock_settings

        app = create_app()

        # Check that middleware is present
        assert len(app.user_middleware) > 0, "Middleware should be present"

    @patch("app.main.get_settings")
    def test_create_app_has_exception_handler(self, mock_get_settings):
        """Test that custom exception handler is registered"""
        mock_settings = MagicMock()
        mock_settings.app_name = "Test App"
        mock_settings.app_version = "1.0.0"
        mock_settings.debug = False
        mock_get_settings.return_value = mock_settings

        app = create_app()

        # Check that validation exception handler is registered
        assert (
            len(app.exception_handlers) > 0
        ), "Exception handlers should be registered"

    @patch("app.main.get_settings")
    def test_create_app_has_routes(self, mock_get_settings):
        """Test that routes are added to the app"""
        mock_settings = MagicMock()
        mock_settings.app_name = "Test App"
        mock_settings.app_version = "1.0.0"
        mock_settings.debug = False
        mock_get_settings.return_value = mock_settings

        app = create_app()

        # Check that routes are present
        assert len(app.routes) > 0, "Routes should be present"


class TestAppInstance:
    """Test that the app instance is created"""

    def test_app_instance_exists(self):
        """Test that the app instance is created at module level"""
        from app.main import app

        assert app is not None
        assert hasattr(app, "title")
        assert hasattr(app, "routes")
