"""Test validate_mcp.py script with Facebook/Meta Ads support.

NOTE: These tests are deprecated. Credential fetching functionality moved to CustomerCredentialManager.
See: tests/integration/test_credential_manager_integration.py for current tests.
"""

import pytest


@pytest.mark.skip(reason="Credential fetching moved to CustomerCredentialManager - see test_credential_manager_integration.py")
def test_fetch_meta_ads_token():
    """Test fetching Meta Ads credentials from database."""
    # NOTE: This functionality moved to CustomerCredentialManager
    # See: app/core/agents/customer_credentials.py
    # Tests: tests/integration/test_credential_manager_integration.py
    pass


@pytest.mark.skip(reason="Credential fetching moved to CustomerCredentialManager - see test_credential_manager_integration.py")
def test_fetch_google_ads_token():
    """Test fetching Google Ads credentials from database."""
    # NOTE: This functionality moved to CustomerCredentialManager
    pass


@pytest.mark.skip(reason="Credential fetching moved to CustomerCredentialManager - see test_credential_manager_integration.py")
def test_fetch_all_credentials():
    """Test fetching all platform credentials."""
    # NOTE: This functionality moved to CustomerCredentialManager
    pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
