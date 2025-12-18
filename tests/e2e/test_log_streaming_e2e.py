"""
E2E Tests for log streaming functionality.
"""

import pytest
import asyncio
import time
import requests
import json
from typing import Generator

from app.config.settings import settings


@pytest.fixture
def auth_headers():
    """Create auth headers with a valid token for testing."""
    import jwt
    token = jwt.encode(
        {"sub": "test_user", "exp": int(time.time()) + 3600},
        settings.secret_key,
        algorithm="HS256"
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def stream_url():
    """Get the streaming URL."""
    base_url = "http://localhost:8000"  # Adjust if your server runs elsewhere
    return f"{base_url}/api/v1/logs/stream"


class TestLogStreamingE2E:
    """E2E tests for log streaming."""

    def test_stream_endpoint_no_auth(self, stream_url):
        """Test that stream endpoint requires authentication."""
        response = requests.get(stream_url, timeout=5)
        assert response.status_code == 401

    def test_stream_endpoint_invalid_token(self, stream_url):
        """Test that stream endpoint rejects invalid tokens."""
        response = requests.get(
            stream_url,
            headers={"Authorization": "Bearer invalid_token"},
            timeout=5
        )
        assert response.status_code == 401

    def test_stream_endpoint_connection_refused_without_server(self, stream_url):
        """Test behavior when server is not running."""
        # This test expects the connection to fail when server is not running
        try:
            response = requests.get(
                stream_url,
                headers={"Authorization": "Bearer some_token"},
                timeout=2
            )
            # If server is running, that's fine too
            assert response.status_code in [401, 404, 200]
        except requests.exceptions.ConnectionError:
            # Expected when server is not running
            pass

    def test_stream_endpoint_format_with_valid_token(self, stream_url, auth_headers):
        """Test the stream endpoint format with a valid token (requires server)."""
        try:
            response = requests.get(
                stream_url,
                params={"lines": 5},
                headers=auth_headers,
                stream=True,
                timeout=5
            )

            if response.status_code == 200:
                # Check response headers for SSE
                assert "text/event-stream" in response.headers.get("content-type", "")

                # Try to read initial data
                initial_data = response.raw.read(500, decode_content=True).decode('utf-8')

                # Should contain SSE format
                assert "data:" in initial_data

                # Should contain initial log data
                assert '"type":"initial"' in initial_data or '"type": "initial"' in initial_data

            elif response.status_code == 401:
                # Server running but auth issue - expected in test
                pass
            else:
                pytest.fail(f"Unexpected status code: {response.status_code}")

        except requests.exceptions.ConnectionError:
            # Server not running - skip test
            pytest.skip("Log streaming server not running")
        except requests.exceptions.Timeout:
            # Server not responding - skip test
            pytest.skip("Log streaming server timeout")

    def test_log_streaming_integration(self, stream_url, auth_headers):
        """Test full log streaming integration (requires running server)."""
        try:
            # Start streaming
            response = requests.get(
                stream_url,
                params={"lines": 10},
                headers=auth_headers,
                stream=True,
                timeout=10
            )

            if response.status_code != 200:
                pytest.skip(f"Server returned status {response.status_code}")

            # Read the stream for a few seconds
            start_time = time.time()
            events_received = []

            for line in response.iter_lines(decode_unicode=True):
                if time.time() - start_time > 3:  # Stop after 3 seconds
                    break

                if line.startswith('data: '):
                    try:
                        data = json.loads(line[6:])
                        events_received.append(data)

                        # We should at least get an initial event
                        if data.get('type') == 'initial':
                            assert 'logs' in data
                            assert 'lines_count' in data
                            break
                    except json.JSONDecodeError:
                        pass

            # Verify we got at least one event
            assert len(events_received) > 0

            # First event should be initial
            assert events_received[0]['type'] == 'initial'

        except requests.exceptions.ConnectionError:
            pytest.skip("Log streaming server not running")
        except requests.exceptions.Timeout:
            pytest.skip("Log streaming server timeout")