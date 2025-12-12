"""
Test for Connection Status Reset on Create/Update

This test validates that when creating or updating connections with fresh tokens,
all failure-related fields are properly reset to healthy status.

Fields that should be reset:
- revoked: False (connection is not revoked)
- needs_reauth: False (no re-authentication needed)
- failure_count: 0 (no failures)
- failure_reason: None (no failure reason)
- last_failure_at: None (no failure timestamp)
"""

import pytest
import os


class TestConnectionStatusReset:
    """Test that connection status fields are reset when creating/updating connections."""

    def test_facebook_page_oauth_resets_status_on_update(self):
        """Test that Facebook Page OAuth resets all status fields when updating connection."""
        file_path = os.path.join(
            os.path.dirname(__file__),
            "../../app/api/v1/routes/facebook_page_oauth.py"
        )
        with open(file_path, 'r') as f:
            source = f.read()

        # Verify all status fields are reset when updating
        assert "connection.revoked = False" in source, \
            "Should reset revoked to False on update"
        assert "connection.needs_reauth = False" in source, \
            "Should reset needs_reauth to False on update"
        assert "connection.failure_count = 0" in source, \
            "Should reset failure_count to 0 on update"
        assert "connection.failure_reason = None" in source, \
            "Should reset failure_reason to None on update"
        assert "connection.last_failure_at = None" in source, \
            "Should reset last_failure_at to None on update"

    def test_facebook_page_oauth_sets_status_on_create(self):
        """Test that Facebook Page OAuth sets all status fields when creating connection."""
        file_path = os.path.join(
            os.path.dirname(__file__),
            "../../app/api/v1/routes/facebook_page_oauth.py"
        )
        with open(file_path, 'r') as f:
            source = f.read()

        # Verify all status fields are set correctly on creation
        assert "revoked=False" in source, \
            "Should set revoked=False on creation"
        assert "needs_reauth=False" in source, \
            "Should set needs_reauth=False on creation"
        assert "failure_count=0" in source, \
            "Should set failure_count=0 on creation"
        assert "failure_reason=None" in source, \
            "Should set failure_reason=None on creation"
        assert "last_failure_at=None" in source, \
            "Should set last_failure_at=None on creation"

    def test_facebook_oauth_resets_status_on_update(self):
        """Test that Facebook OAuth resets all status fields when updating connection."""
        file_path = os.path.join(
            os.path.dirname(__file__),
            "../../app/api/v1/routes/facebook_oauth.py"
        )
        with open(file_path, 'r') as f:
            source = f.read()

        # Verify all status fields are reset
        assert "connection.revoked = False" in source
        assert "connection.needs_reauth = False" in source
        assert "connection.failure_count = 0" in source
        assert "connection.failure_reason = None" in source
        assert "connection.last_failure_at = None" in source

    def test_facebook_marketing_oauth_resets_status_on_update(self):
        """Test that Facebook Marketing OAuth resets all status fields when updating connection."""
        file_path = os.path.join(
            os.path.dirname(__file__),
            "../../app/api/v1/routes/facebook_marketing_oauth.py"
        )
        with open(file_path, 'r') as f:
            source = f.read()

        # Verify all status fields are reset
        assert "connection.revoked = False" in source
        assert "connection.needs_reauth = False" in source
        assert "connection.failure_count = 0" in source
        assert "connection.failure_reason = None" in source
        assert "connection.last_failure_at = None" in source

    def test_google_ads_service_resets_status_on_update(self):
        """Test that Google Ads service resets all status fields when updating connection."""
        file_path = os.path.join(
            os.path.dirname(__file__),
            "../../app/services/google_ads_service.py"
        )
        with open(file_path, 'r') as f:
            source = f.read()

        # Verify all status fields are reset
        assert "connection.revoked = False" in source
        assert "connection.needs_reauth = False" in source
        assert "connection.failure_count = 0" in source
        assert "connection.failure_reason = None" in source
        assert "connection.last_failure_at = None" in source

    def test_google_ads_service_sets_status_on_create(self):
        """Test that Google Ads service sets all status fields when creating connection."""
        file_path = os.path.join(
            os.path.dirname(__file__),
            "../../app/services/google_ads_service.py"
        )
        with open(file_path, 'r') as f:
            source = f.read()

        # Verify all status fields are set correctly on creation
        assert "revoked=False" in source
        assert "needs_reauth=False" in source
        assert "failure_count=0" in source
        assert "failure_reason=None" in source
        assert "last_failure_at=None" in source

    def test_google_analytics_service_resets_status_on_update(self):
        """Test that Google Analytics service resets all status fields when updating connection."""
        file_path = os.path.join(
            os.path.dirname(__file__),
            "../../app/services/google_analytics_service.py"
        )
        with open(file_path, 'r') as f:
            source = f.read()

        # Verify all status fields are reset
        assert "connection.revoked = False" in source
        assert "connection.needs_reauth = False" in source
        assert "connection.failure_count = 0" in source
        assert "connection.failure_reason = None" in source
        assert "connection.last_failure_at = None" in source

    def test_google_analytics_service_sets_status_on_create(self):
        """Test that Google Analytics service sets all status fields when creating connection."""
        file_path = os.path.join(
            os.path.dirname(__file__),
            "../../app/services/google_analytics_service.py"
        )
        with open(file_path, 'r') as f:
            source = f.read()

        # Verify all status fields are set correctly on creation
        assert "revoked=False" in source
        assert "needs_reauth=False" in source
        assert "failure_count=0" in source
        assert "failure_reason=None" in source
        assert "last_failure_at=None" in source

    def test_status_reset_comment_present(self):
        """Test that status reset includes explanatory comment."""
        files_to_check = [
            "app/api/v1/routes/facebook_page_oauth.py",
            "app/api/v1/routes/facebook_oauth.py",
            "app/api/v1/routes/facebook_marketing_oauth.py",
            "app/services/google_ads_service.py",
            "app/services/google_analytics_service.py",
        ]

        for file_rel_path in files_to_check:
            file_path = os.path.join(os.path.dirname(__file__), "../..", file_rel_path)
            with open(file_path, 'r') as f:
                source = f.read()

            assert "Reset connection status" in source or "fresh tokens mean connection is healthy" in source, \
                f"{file_rel_path} should have explanatory comment about status reset"

    def test_all_five_fields_reset_together(self):
        """Test that all 5 status fields are reset together (not separately)."""
        files_to_check = [
            "app/api/v1/routes/facebook_page_oauth.py",
            "app/api/v1/routes/facebook_oauth.py",
            "app/api/v1/routes/facebook_marketing_oauth.py",
            "app/services/google_ads_service.py",
            "app/services/google_analytics_service.py",
        ]

        for file_rel_path in files_to_check:
            file_path = os.path.join(os.path.dirname(__file__), "../..", file_rel_path)
            with open(file_path, 'r') as f:
                source = f.read()

            # Check that when revoked is set to False, all other fields follow
            lines = source.split('\n')
            for i, line in enumerate(lines):
                if "connection.revoked = False" in line:
                    # Check that the next few lines contain the other status resets
                    next_lines = '\n'.join(lines[i:i+10])
                    assert "needs_reauth" in next_lines, \
                        f"{file_rel_path}: needs_reauth should be reset near revoked"
                    assert "failure_count" in next_lines, \
                        f"{file_rel_path}: failure_count should be reset near revoked"
                    assert "failure_reason" in next_lines, \
                        f"{file_rel_path}: failure_reason should be reset near revoked"
                    assert "last_failure_at" in next_lines, \
                        f"{file_rel_path}: last_failure_at should be reset near revoked"


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
