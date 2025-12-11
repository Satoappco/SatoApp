"""
Unit Tests for Connection Model Failure Tracking Fields

Tests that the Connection model includes the failure tracking fields
added in migration 20251208_1400_add_connection_failure_tracking.py

This test validates the fix for the bug where database queries failed
due to missing columns: last_failure_at, failure_count, failure_reason
"""

import pytest
from datetime import datetime, timezone
from app.models.analytics import Connection, DigitalAsset, AssetType, AuthType


class TestConnectionFailureTrackingFields:
    """Tests for Connection model failure tracking fields."""

    def test_connection_model_has_failure_tracking_fields(self):
        """Test that Connection model includes all failure tracking fields."""
        # Create a Connection instance
        connection = Connection(
            digital_asset_id=1,
            customer_id=1,
            campaigner_id=1,
            auth_type=AuthType.OAUTH2,
            account_email="test@example.com",
            scopes=["https://www.googleapis.com/auth/analytics.readonly"],
            access_token_enc=b"encrypted_token",
            refresh_token_enc=b"encrypted_refresh",
            token_hash="hash123",
            expires_at=datetime.now(timezone.utc),
            revoked=False,
            rotated_at=None,
            last_used_at=None,
            needs_reauth=False,
            last_validated_at=datetime.now(timezone.utc),
            # Failure tracking fields
            last_failure_at=None,
            failure_count=0,
            failure_reason=None,
        )

        # Verify failure tracking fields exist and are accessible
        assert hasattr(connection, "last_failure_at")
        assert hasattr(connection, "failure_count")
        assert hasattr(connection, "failure_reason")

        # Verify field values
        assert connection.last_failure_at is None
        assert connection.failure_count == 0
        assert connection.failure_reason is None

    def test_connection_model_accepts_failure_tracking_values(self):
        """Test that Connection model can be created with failure tracking values."""
        failure_time = datetime.now(timezone.utc)

        connection = Connection(
            digital_asset_id=1,
            customer_id=1,
            campaigner_id=1,
            auth_type=AuthType.OAUTH2,
            account_email="test@example.com",
            scopes=["https://www.googleapis.com/auth/analytics.readonly"],
            access_token_enc=b"encrypted_token",
            refresh_token_enc=b"encrypted_refresh",
            token_hash="hash123",
            expires_at=datetime.now(timezone.utc),
            revoked=False,
            rotated_at=None,
            last_used_at=None,
            needs_reauth=False,
            last_validated_at=datetime.now(timezone.utc),
            # Failure tracking fields with values
            last_failure_at=failure_time,
            failure_count=3,
            failure_reason="token_refresh_failed: invalid_grant",
        )

        # Verify field values are set correctly
        assert connection.last_failure_at == failure_time
        assert connection.failure_count == 3
        assert connection.failure_reason == "token_refresh_failed: invalid_grant"

    def test_connection_model_fields_have_correct_types(self):
        """Test that Connection model failure tracking fields have correct types."""
        connection = Connection(
            digital_asset_id=1,
            customer_id=1,
            campaigner_id=1,
            auth_type=AuthType.OAUTH2,
            account_email="test@example.com",
            scopes=["https://www.googleapis.com/auth/analytics.readonly"],
            access_token_enc=b"encrypted_token",
            refresh_token_enc=b"encrypted_refresh",
            token_hash="hash123",
            expires_at=datetime.now(timezone.utc),
            revoked=False,
            rotated_at=None,
            last_used_at=None,
            needs_reauth=False,
            last_validated_at=datetime.now(timezone.utc),
            last_failure_at=None,
            failure_count=0,
            failure_reason=None,
        )

        # Verify field types
        assert connection.last_failure_at is None or isinstance(
            connection.last_failure_at, datetime
        )
        assert isinstance(connection.failure_count, int)
        assert connection.failure_reason is None or isinstance(
            connection.failure_reason, str
        )
