"""
Tests for security utilities
"""

import pytest
from unittest.mock import patch
from app.core.security import get_current_user_id, get_secret_key


class TestGetCurrentUserId:
    """Test get_current_user_id function"""

    def test_get_current_user_id_returns_default(self):
        """Test that function returns the default user ID"""
        result = get_current_user_id()
        assert result == 7001


class TestGetSecretKey:
    """Test get_secret_key function"""

    @patch("app.core.security.settings")
    def test_get_secret_key_from_settings(self, mock_settings):
        """Test that function returns secret key from settings"""
        mock_settings.secret_key = "my-secret-key"
        result = get_secret_key()
        assert result == "my-secret-key"

    @patch("app.core.security.settings")
    def test_get_secret_key_default_fallback(self, mock_settings):
        """Test that function returns default when no secret key in settings"""
        mock_settings.secret_key = None
        result = get_secret_key()
        assert result == "default-secret-key-for-encryption"


class TestSecurityConstants:
    """Test security module constants and setup"""

    @patch("app.core.security.get_settings")
    def test_security_initialization(self, mock_get_settings):
        """Test that security module initializes correctly"""
        mock_settings = mock_get_settings.return_value
        mock_settings.api_key = "test_key"
        mock_settings.secret_key = "test_secret"

        # Re-import to test initialization
        import importlib
        import app.core.security

        importlib.reload(app.core.security)

        # Check that settings and security objects are created
        assert hasattr(app.core.security, "settings")
        assert hasattr(app.core.security, "security")
