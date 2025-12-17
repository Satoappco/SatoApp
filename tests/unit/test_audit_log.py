import pytest
from unittest.mock import patch, MagicMock
import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.core.audit_log import log_authorization_check
from app.models.users import Campaigner, UserRole


class TestAuditLogging:
    """Test audit logging functionality"""

    @pytest.fixture
    def owner_user(self):
        """Create a test owner user"""
        return Campaigner(
            id=1,
            email="owner@test.com",
            full_name="Test Owner",
            agency_id=1,
            role=UserRole.OWNER,
        )

    @pytest.fixture
    def admin_user(self):
        """Create a test admin user"""
        return Campaigner(
            id=2,
            email="admin@test.com",
            full_name="Test Admin",
            agency_id=1,
            role=UserRole.ADMIN,
        )

    @patch("app.core.audit_log.logger")
    def test_log_successful_authorization(self, mock_logger, owner_user):
        """Test logging successful authorization"""
        log_authorization_check(
            user=owner_user,
            action="read",
            resource_type="customer",
            resource_id=123,
            allowed=True,
        )

        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args[0][0]
        assert "✅ [AUTHZ]" in call_args
        assert "owner@test.com" in call_args
        assert "OWNER" in call_args
        assert "read" in call_args
        assert "customer:123" in call_args

    @patch("app.core.audit_log.logger")
    def test_log_denied_authorization(self, mock_logger, admin_user):
        """Test logging denied authorization"""
        log_authorization_check(
            user=admin_user,
            action="delete",
            resource_type="agency",
            resource_id=456,
            allowed=False,
            reason="Insufficient role",
        )

        mock_logger.warning.assert_called_once()
        call_args = mock_logger.warning.call_args[0][0]
        assert "🚫 [AUTHZ]" in call_args
        assert "admin@test.com" in call_args
        assert "ADMIN" in call_args
        assert "DENIED" in call_args
        assert "delete" in call_args
        assert "agency:456" in call_args
        assert "Insufficient role" in call_args

    @patch("app.core.audit_log.logger")
    def test_log_without_resource_id(self, mock_logger, owner_user):
        """Test logging without resource ID"""
        log_authorization_check(
            user=owner_user, action="list", resource_type="customers", allowed=True
        )

        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args[0][0]
        assert "✅ [AUTHZ]" in call_args
        assert "customers:None" in call_args

    @patch("app.core.audit_log.logger")
    def test_log_without_reason_for_allowed(self, mock_logger, admin_user):
        """Test logging allowed access without reason"""
        log_authorization_check(
            user=admin_user,
            action="update",
            resource_type="campaigner",
            resource_id=789,
            allowed=True,
        )

        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args[0][0]
        assert "✅ [AUTHZ]" in call_args
        assert "admin@test.com" in call_args
        assert "update" in call_args
        assert "campaigner:789" in call_args

    @patch("app.core.audit_log.logger")
    def test_log_denied_without_reason(self, mock_logger, admin_user):
        """Test logging denied access without explicit reason"""
        log_authorization_check(
            user=admin_user,
            action="delete",
            resource_type="system",
            resource_id=999,
            allowed=False,
        )

        mock_logger.warning.assert_called_once()
        call_args = mock_logger.warning.call_args[0][0]
        assert "🚫 [AUTHZ]" in call_args
        assert "DENIED" in call_args
        assert "system:999" in call_args
        assert " - None" in call_args

    @patch("app.core.audit_log.logger")
    def test_log_with_viewer_role(self, mock_logger):
        """Test logging with VIEWER role"""
        viewer = Campaigner(
            id=3,
            email="viewer@test.com",
            full_name="Test Viewer",
            agency_id=1,
            role=UserRole.VIEWER,
        )

        log_authorization_check(
            user=viewer,
            action="read",
            resource_type="report",
            resource_id=555,
            allowed=True,
        )

        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args[0][0]
        assert "viewer@test.com" in call_args
        assert "VIEWER" in call_args
        assert "report:555" in call_args
