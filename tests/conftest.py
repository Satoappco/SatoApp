"""
Pytest configuration and shared fixtures for Sato AI testing
"""

import os
import time
import pytest
import asyncio
from typing import Generator, AsyncGenerator
from unittest.mock import Mock, MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.exc import OperationalError
from sqlmodel import Session

# Mock Google Auth before any app imports to prevent credential errors in CI/CD
# Create a mock credentials JSON file if it doesn't exist
import json
import tempfile

_mock_creds_file = os.path.join(tempfile.gettempdir(), "test_google_credentials.json")
if not os.path.exists(_mock_creds_file):
    with open(_mock_creds_file, "w") as f:
        json.dump({
            "type": "service_account",
            "project_id": "test-project",
            "private_key_id": "test-key-id",
            "private_key": "-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEA2Z3qX2BTLS4e0TyL...\n-----END RSA PRIVATE KEY-----\n",
            "client_email": "test@test-project.iam.gserviceaccount.com",
            "client_id": "123456789",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs"
        }, f)

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = _mock_creds_file
os.environ["GOOGLE_CLOUD_PROJECT"] = "test-project"

from app.config.settings import Settings
from app.models.base import BaseModel


@pytest.fixture(scope="session", autouse=True)
def mock_google_auth():
    """Mock Google authentication globally to prevent credential errors in CI/CD.

    This fixture runs automatically for all tests and mocks Google auth
    so tests don't need real Google Cloud credentials.
    """
    with patch("google.auth.default") as mock_default:
        # Create mock credentials
        mock_credentials = Mock()
        mock_credentials.valid = True
        mock_credentials.token = "mock-token"
        mock_credentials.refresh = Mock()

        # Return mock credentials and project
        mock_default.return_value = (mock_credentials, "test-project")

        yield mock_default


def is_integration_test(request):
    """Check if current test is an integration test"""
    # Check if test file is in integration directory
    if "integration" in str(request.fspath):
        return True
    # Check if test has integration marker
    if request.node.get_closest_marker("integration"):
        return True
    return False


def get_test_database_url(request=None):
    """Get appropriate database URL for test type

    SAFETY: This function will NEVER use DATABASE_URL (production database).
    It only uses TEST_DATABASE_URL to prevent accidental production database corruption.
    """
    # Check if this is an integration test
    if request and is_integration_test(request):
        # Use PostgreSQL for integration tests
        # ALWAYS use TEST_DATABASE_URL, never production DATABASE_URL
        test_url = os.getenv("TEST_DATABASE_URL")
        if test_url:
            # Safety check: ensure it's not accidentally pointing to production
            if (
                "localhost" not in test_url
                and "127.0.0.1" not in test_url
                and "test" not in test_url.lower()
            ):
                raise RuntimeError(
                    f"SAFETY ERROR: TEST_DATABASE_URL appears to point to a production database!\n"
                    f"URL: {test_url}\n"
                    f"Test database URLs must either:\n"
                    f"  1. Contain 'localhost' or '127.0.0.1'\n"
                    f"  2. Contain 'test' in the database name\n"
                    f"This prevents accidental production database corruption."
                )
            return test_url

        # Fallback to default local test database
        return "postgresql://postgres:postgres@localhost:5433/postgres"

    # Use SQLite for unit tests (faster)
    return "sqlite:///:memory:"


@pytest.fixture(scope="function")
def test_engine(request):
    """Create test database engine based on test type"""
    db_url = get_test_database_url(request)

    # Configure engine based on database type
    if db_url.startswith("sqlite"):
        engine = create_engine(
            db_url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            echo=False,
        )
        # Create tables immediately for SQLite
        BaseModel.metadata.create_all(bind=engine)
    else:
        # PostgreSQL configuration
        engine = create_engine(
            db_url,
            echo=False,
            pool_pre_ping=True,
        )

        # Wait for PostgreSQL to be ready and create tables with retry
        max_attempts = 10
        for attempt in range(max_attempts):
            try:
                BaseModel.metadata.create_all(bind=engine)
                break  # Success
            except OperationalError as e:
                if attempt == max_attempts - 1:
                    raise  # Re-raise on final attempt
                time.sleep(1)  # Wait 1 second before retry

    yield engine

    # Clean up
    try:
        BaseModel.metadata.drop_all(bind=engine)
    except OperationalError:
        pass  # Ignore errors during cleanup
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(test_engine) -> Generator[Session, None, None]:
    """Create test database session"""
    connection = test_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="function")
def mock_settings(request):
    """Mock settings for testing"""
    settings = Mock(spec=Settings)
    settings.secret_key = "test-secret-key"
    settings.google_client_id = "test-google-client-id"
    settings.google_client_secret = "test-google-client-secret"
    settings.facebook_app_id = "test-facebook-app-id"
    settings.facebook_app_secret = "test-facebook-app-secret"
    settings.database_url = get_test_database_url(request)
    settings.jwt_access_token_expire_minutes = 60
    settings.jwt_refresh_token_expire_days = 7
    return settings


@pytest.fixture
def sample_campaigner_data():
    """Sample campaigner data for testing"""
    return {
        "id": 1,
        "email": "test@example.com",
        "full_name": "Test User",
        "role": "campaigner",
        "status": "active",
        "agency_id": 1,
    }


@pytest.fixture
def sample_agency_data():
    """Sample agency data for testing"""
    return {
        "id": 1,
        "name": "Test Agency",
        "email": "agency@example.com",
        "status": "active",
    }


@pytest.fixture
def sample_customer_data():
    """Sample customer data for testing"""
    return {
        "id": 1,
        "full_name": "Test Customer",
        "email": "customer@example.com",
        "status": "active",
        "agency_id": 1,
        "assigned_campaigner_id": 1,
    }


# Custom markers
def pytest_configure(config):
    """Configure pytest with custom markers"""
    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "e2e: End-to-end tests")
    config.addinivalue_line("markers", "slow: Slow running tests")
    config.addinivalue_line("markers", "database: Tests requiring database")
    config.addinivalue_line("markers", "external: Tests requiring external services")


# Test utilities
def async_return(result):
    """Helper to create async mock return values"""

    async def _async_return(*args, **kwargs):
        return result

    return _async_return


def create_mock_coro(result=None):
    """Create a mock coroutine"""

    async def coro(*args, **kwargs):
        return result

    return coro


@pytest.fixture(scope="function")
def mock_facebook_api():
    """Mock Facebook Graph API responses"""
    with patch("httpx.AsyncClient") as mock_client:
        mock_response = Mock()
        mock_response.json.return_value = {
            "data": [{"name": "page_impressions", "values": [{"value": 1000}]}]
        }
        mock_response.status_code = 200
        mock_client.return_value.__aenter__.return_value.get.return_value = (
            mock_response
        )
        yield mock_client


@pytest.fixture(scope="function")
def mock_ga4_api():
    """Mock Google Analytics 4 API responses"""
    with patch("google.analytics.data_v1beta.BetaAnalyticsDataClient") as mock_client:
        mock_response = Mock()
        mock_response.rows = [
            Mock(
                dimension_values=[Mock(value="2024-01-01")],
                metric_values=[Mock(value="1000")],
            )
        ]
        mock_client.return_value.run_report.return_value = mock_response
        yield mock_client


@pytest.fixture(scope="function")
def mock_google_ads_api():
    """Mock Google Ads API responses"""
    with patch("google.ads.googleads.client.GoogleAdsClient") as mock_client:
        mock_service = Mock()
        mock_service.search.return_value = [
            Mock(
                campaign=Mock(id="123", name="Test Campaign"),
                metrics=Mock(impressions="1000", clicks="50", cost_micros="5000000"),
            )
        ]
        mock_client.return_value.get_service.return_value = mock_service
        yield mock_client
