"""
Tests for file-based logging system.
"""

import pytest
import requests
import os
from pathlib import Path
from datetime import datetime, timedelta

# Backend URL and API token from environment
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8080")
API_TOKEN = os.getenv("API_TOKEN")  # Must be set in environment

# Skip all tests if API_TOKEN not configured
pytestmark = pytest.mark.skipif(
    not API_TOKEN,
    reason="API_TOKEN environment variable not set. Set it to run e2e tests against real backend."
)

headers = {"Authorization": f"Bearer {API_TOKEN}"} if API_TOKEN else {}


@pytest.fixture(scope="module", autouse=True)
def validate_api_token():
    """Validate API token works before running tests"""
    if not API_TOKEN:
        pytest.skip("API_TOKEN not set")

    # Quick health check with the token
    try:
        response = requests.get(
            f"{BACKEND_URL}/api/v1/logs/stats",
            headers=headers,
            timeout=5
        )

        if response.status_code == 401:
            pytest.exit(
                f"\n❌ API_TOKEN is INVALID for backend: {BACKEND_URL}\n"
                f"   Response: {response.text}\n"
                f"   Please check:\n"
                f"   1. API_TOKEN environment variable is set correctly\n"
                f"   2. Token matches the backend's configured API_TOKEN\n"
                f"   3. Backend URL is correct: {BACKEND_URL}\n"
            )
        elif response.status_code >= 500:
            pytest.exit(f"\n❌ Backend error ({response.status_code}): {BACKEND_URL}\n")
    except requests.RequestException as e:
        pytest.exit(f"\n❌ Cannot connect to backend: {BACKEND_URL}\n   Error: {e}\n")


def test_get_recent_logs():
    """Test getting recent log entries."""
    response = requests.get(
        f"{BACKEND_URL}/api/v1/logs/recent",
        params={"lines": 10},
        headers=headers
    )
    assert response.status_code == 200

    data = response.json()
    assert data["success"] is True
    assert "logs" in data
    assert data["lines_returned"] > 0
    assert "message" in data
    print(f"✅ Retrieved {data['lines_returned']} recent log lines")


def test_search_logs():
    """Test searching logs by keyword."""
    response = requests.get(
        f"{BACKEND_URL}/api/v1/logs/search",
        params={"query": "File logging", "max_results": 50},
        headers=headers
    )
    assert response.status_code == 200

    data = response.json()
    assert data["success"] is True
    assert "logs" in data
    assert data["lines_returned"] >= 0
    print(f"✅ Found {data['lines_returned']} matching log lines")


def test_get_logs_by_level():
    """Test filtering logs by level."""
    for level in ["DEBUG", "INFO", "WARNING", "ERROR"]:
        response = requests.get(
            f"{BACKEND_URL}/api/v1/logs/level/{level}",
            params={"max_results": 100},
            headers=headers
        )
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert "logs" in data
        print(f"✅ Retrieved {data['lines_returned']} {level} log lines")


def test_get_log_stats():
    """Test getting log file statistics."""
    response = requests.get(
        f"{BACKEND_URL}/api/v1/logs/stats",
        headers=headers
    )
    assert response.status_code == 200

    data = response.json()
    assert data["success"] is True
    assert "stats" in data
    assert "total_files" in data["stats"]
    assert "total_size_bytes" in data["stats"]
    assert "files" in data["stats"]

    print(f"✅ Log stats: {data['stats']['total_files']} file(s), "
          f"{data['stats']['total_size_mb']:.2f}MB")


def test_tail_logs():
    """Test tailing log file."""
    response = requests.get(
        f"{BACKEND_URL}/api/v1/logs/tail",
        params={"lines": 20},
        headers=headers
    )
    assert response.status_code == 200

    data = response.json()
    assert data["success"] is True
    assert "logs" in data
    assert data["lines_returned"] > 0
    print(f"✅ Tailed {data['lines_returned']} log lines")


def test_get_logs_by_timerange():
    """Test filtering logs by time range."""
    # Get logs from last hour
    response = requests.get(
        f"{BACKEND_URL}/api/v1/logs/timerange",
        params={"hours_ago": 1, "max_results": 1000},
        headers=headers
    )
    assert response.status_code == 200

    data = response.json()
    assert data["success"] is True
    assert "logs" in data
    print(f"✅ Retrieved {data['lines_returned']} log lines from last hour")


def test_authentication_required():
    """Test that endpoints require authentication."""
    # Try without authentication
    response = requests.get(f"{BACKEND_URL}/api/v1/logs/recent")
    assert response.status_code == 403  # Forbidden without auth

    # Try with invalid token
    invalid_headers = {"Authorization": "Bearer invalid_token"}
    response = requests.get(
        f"{BACKEND_URL}/api/v1/logs/recent",
        headers=invalid_headers
    )
    assert response.status_code == 401  # Unauthorized with invalid token

    print("✅ Authentication is properly enforced")


def test_validation_errors():
    """Test that validation works for invalid parameters."""
    # Test invalid lines parameter (too high)
    response = requests.get(
        f"{BACKEND_URL}/api/v1/logs/recent",
        params={"lines": 100000},  # Max is 10000
        headers=headers
    )
    assert response.status_code == 422  # Validation error

    # Test invalid log level
    response = requests.get(
        f"{BACKEND_URL}/api/v1/logs/level/INVALID",
        headers=headers
    )
    assert response.status_code == 422  # Validation error

    print("✅ Input validation is working correctly")


if __name__ == "__main__":
    print("\n" + "="*80)
    print("Testing File-Based Logging System")
    print("="*80 + "\n")

    # Run all tests
    test_get_recent_logs()
    test_search_logs()
    test_get_logs_by_level()
    test_get_log_stats()
    test_tail_logs()
    test_get_logs_by_timerange()
    test_authentication_required()
    test_validation_errors()

    print("\n" + "="*80)
    print("All tests passed! ✅")
    print("="*80 + "\n")
