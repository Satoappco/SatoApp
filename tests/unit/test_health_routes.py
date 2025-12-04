"""
Tests for health check routes
"""

import pytest
from unittest.mock import patch
from datetime import datetime
from app.api.v1.routes.health import health_check, root


class TestHealthCheck:
    """Test health check endpoint"""

    @patch("app.api.v1.routes.health.settings")
    def test_health_check_response(self, mock_settings):
        """Test health check returns correct response structure"""
        mock_settings.app_name = "TestApp"
        mock_settings.app_version = "1.0.0"

        with patch("app.api.v1.routes.health.datetime") as mock_datetime:
            from datetime import timezone

            mock_datetime.now.return_value = datetime(
                2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc
            )

            result = health_check()

            assert result["status"] == "healthy"
            assert result["service"] == "TestApp"
            assert result["version"] == "1.0.0"
            assert result["timestamp"] == "2023-01-01T12:00:00+00:00"

    @patch("app.api.v1.routes.health.settings")
    def test_health_check_contains_required_fields(self, mock_settings):
        """Test health check response contains all required fields"""
        mock_settings.app_name = "TestApp"
        mock_settings.app_version = "1.0.0"

        result = health_check()

        required_fields = ["status", "service", "version", "timestamp"]
        for field in required_fields:
            assert field in result

        assert isinstance(result["timestamp"], str)


class TestRoot:
    """Test root endpoint"""

    @patch("app.api.v1.routes.health.settings")
    def test_root_response(self, mock_settings):
        """Test root endpoint returns correct response structure"""
        mock_settings.app_name = "TestApp"
        mock_settings.app_version = "1.0.0"

        with patch("app.api.v1.routes.health.datetime") as mock_datetime:
            from datetime import timezone

            mock_datetime.now.return_value = datetime(
                2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc
            )

            result = root()

            assert result["message"] == "TestApp"
            assert result["version"] == "1.0.0"
            assert result["status"] == "active"
            assert result["timestamp"] == "2023-01-01T12:00:00+00:00"

    @patch("app.api.v1.routes.health.settings")
    def test_root_contains_required_fields(self, mock_settings):
        """Test root response contains all required fields"""
        mock_settings.app_name = "TestApp"
        mock_settings.app_version = "1.0.0"

        result = root()

        required_fields = ["message", "version", "status", "timestamp"]
        for field in required_fields:
            assert field in result

        assert isinstance(result["timestamp"], str)


class TestHealthRoutesIntegration:
    """Test health routes integration"""

    def test_routes_are_functions(self):
        """Test that route functions are callable"""
        assert callable(health_check)
        assert callable(root)

    def test_response_types(self):
        """Test that responses are dictionaries"""
        with patch("app.api.v1.routes.health.settings"):
            health_result = health_check()
            root_result = root()

            assert isinstance(health_result, dict)
            assert isinstance(root_result, dict)
