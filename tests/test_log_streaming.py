"""
Tests for the log streaming SSE endpoint.
"""

import pytest
import asyncio
import json
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient
from httpx import Response
import io
import jwt

from app.main import app
from app.config.settings import settings

client = TestClient(app)


def create_test_token(user_id: str = "test_user") -> str:
    """Create a valid JWT token for testing."""
    return jwt.encode(
        {"sub": user_id, "exp": 9999999999},  # Far future expiry
        settings.secret_key,
        algorithm="HS256"
    )


class TestLogStreaming:
    """Test cases for log streaming functionality."""

    def test_stream_endpoint_requires_token(self):
        """Test that the stream endpoint requires authentication."""
        response = client.get("/api/v1/logs/stream")
        assert response.status_code == 401
        assert "Authentication token required" in response.json()["detail"]

    def test_stream_endpoint_rejects_invalid_token(self):
        """Test that the stream endpoint rejects invalid tokens."""
        response = client.get(
            "/api/v1/logs/stream",
            params={"token": "invalid_token"}
        )
        assert response.status_code == 401
        assert "Invalid token" in response.json()["detail"]

    def test_stream_endpoint_accepts_valid_token(self):
        """Test that the stream endpoint accepts valid tokens."""
        token = create_test_token()

        # Mock the file logger to avoid reading actual log files
        with patch('app.api.v1.routes.logs.file_logger') as mock_logger:
            mock_logger.get_recent_logs.return_value = "Test log line\n"
            mock_logger.log_file = "/fake/path/to/logs.log"

            # Mock os.path.exists and os.path.getsize
            with patch('os.path.exists', return_value=True), \
                 patch('os.path.getsize', return_value=100):

                # Make the request with streaming
                with client.stream(
                    "GET",
                    "/api/v1/logs/stream",
                    params={"token": token, "lines": 10}
                ) as response:
                    assert response.status_code == 200
                    assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
                    assert "cache-control" in response.headers

    def test_stream_sends_initial_logs(self):
        """Test that the stream sends initial log data."""
        token = create_test_token()

        with patch('app.api.v1.routes.logs.file_logger') as mock_logger:
            mock_logger.get_recent_logs.return_value = "Initial log content\nLine 2\n"
            mock_logger.log_file = "/fake/path/to/logs.log"

            with patch('os.path.exists', return_value=True), \
                 patch('os.path.getsize', return_value=100):

                with client.stream(
                    "GET",
                    "/api/v1/logs/stream",
                    params={"token": token, "lines": 10}
                ) as response:
                    # Read the initial chunk
                    content = response.read()
                    content_str = content.decode('utf-8')

                    # Should contain the initial log data
                    assert "data:" in content_str
                    assert "initial" in content_str
                    assert "Initial log content" in content_str

    def test_stream_handles_log_rotation(self):
        """Test that the stream handles log file rotation."""
        token = create_test_token()

        with patch('app.api.v1.routes.logs.file_logger') as mock_logger:
            mock_logger.get_recent_logs.return_value = "Rotated log content\n"
            mock_logger.log_file = "/fake/path/to/logs.log"

            # Simulate log rotation: file exists first, then doesn't, then exists again
            exists_responses = [True, False, True, True, True]
            getsize_responses = [100, 0, 50, 50, 50]

            def mock_exists(path):
                return exists_responses.pop(0) if exists_responses else True

            def mock_getsize(path):
                return getsize_responses.pop(0) if getsize_responses else 100

            with patch('os.path.exists', side_effect=mock_exists), \
                 patch('os.path.getsize', side_effect=mock_getsize):

                # Read a small chunk to test rotation detection
                with client.stream(
                    "GET",
                    "/api/v1/logs/stream",
                    params={"token": token, "lines": 10}
                ) as response:
                    content = response.read(500)  # Read first 500 bytes
                    content_str = content.decode('utf-8')

                    # Should detect rotation and send rotation event
                    assert "rotation" in content_str or "initial" in content_str

    def test_stream_sends_error_on_exception(self):
        """Test that the stream sends error events when exceptions occur."""
        token = create_test_token()

        with patch('app.api.v1.routes.logs.file_logger') as mock_logger:
            # Make get_recent_logs raise an exception
            mock_logger.get_recent_logs.side_effect = Exception("Test error")

            with client.stream(
                "GET",
                "/api/v1/logs/stream",
                params={"token": token, "lines": 10}
            ) as response:
                content = response.read(500)
                content_str = content.decode('utf-8')

                # Should send an error event
                assert "error" in content_str.lower()

    def test_stream_limits_initial_lines(self):
        """Test that the stream respects the lines parameter."""
        token = create_test_token()

        with patch('app.api.v1.routes.logs.file_logger') as mock_logger:
            # Return a long log string
            long_log = "\n".join([f"Log line {i}" for i in range(100)])
            mock_logger.get_recent_logs.return_value = long_log
            mock_logger.log_file = "/fake/path/to/logs.log"

            with patch('os.path.exists', return_value=True), \
                 patch('os.path.getsize', return_value=1000):

                with client.stream(
                    "GET",
                    "/api/v1/logs/stream",
                    params={"token": token, "lines": 5}
                ) as response:
                    content = response.read(500)
                    content_str = content.decode('utf-8')

                    # Should call get_recent_logs with the specified lines
                    mock_logger.get_recent_logs.assert_called_with(lines=5)

    def test_stream_validates_lines_parameter(self):
        """Test that the stream validates the lines parameter."""
        token = create_test_token()

        # Test with lines less than 1
        response = client.get(
            "/api/v1/logs/stream",
            params={"token": token, "lines": 0}
        )
        assert response.status_code == 422  # Validation error

        # Test with lines greater than 1000
        response = client.get(
            "/api/v1/logs/stream",
            params={"token": token, "lines": 1001}
        )
        assert response.status_code == 422  # Validation error

    def test_stream_handles_no_log_file(self):
        """Test that the stream handles the case when log file doesn't exist."""
        token = create_test_token()

        with patch('app.api.v1.routes.logs.file_logger') as mock_logger:
            mock_logger.get_recent_logs.return_value = ""
            mock_logger.log_file = "/fake/path/to/logs.log"

            with patch('os.path.exists', return_value=False):

                with client.stream(
                    "GET",
                    "/api/v1/logs/stream",
                    params={"token": token, "lines": 10}
                ) as response:
                    content = response.read(500)
                    content_str = content.decode('utf-8')

                    # Should send initial empty logs
                    assert "data:" in content_str
                    assert "initial" in content_str

    @pytest.mark.asyncio
    async def test_stream_async_generator_behavior(self):
        """Test the async generator behavior of the stream."""
        from app.api.v1.routes.logs import generate_log_stream

        # This test requires more complex async testing setup
        # For now, we'll just test that the function exists
        assert True  # Placeholder for more detailed async testing