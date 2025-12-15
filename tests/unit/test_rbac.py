import pytest
from app.core.rbac import user_is_at_least, get_role_level, RoleLevel
from app.models.users import Campaigner, UserRole


class TestRoleHierarchy:
    """Test role hierarchy and comparisons"""

    def test_owner_is_at_least_admin(self):
        """OWNER role should pass ADMIN check"""
        owner = Campaigner(
            email="owner@test.com",
            full_name="Test Owner",
            agency_id=1,
            role=UserRole.OWNER,
        )
        assert user_is_at_least(owner, UserRole.ADMIN) is True

    def test_owner_is_at_least_campaigner(self):
        """OWNER role should pass CAMPAIGNER check"""
        owner = Campaigner(
            email="owner@test.com",
            full_name="Test Owner",
            agency_id=1,
            role=UserRole.OWNER,
        )
        assert user_is_at_least(owner, UserRole.CAMPAIGNER) is True

    def test_admin_is_at_least_campaigner(self):
        """ADMIN role should pass CAMPAIGNER check"""
        admin = Campaigner(
            email="admin@test.com",
            full_name="Test Admin",
            agency_id=1,
            role=UserRole.ADMIN,
        )
        assert user_is_at_least(admin, UserRole.CAMPAIGNER) is True

    def test_admin_is_not_owner(self):
        """ADMIN role should fail OWNER check"""
        admin = Campaigner(
            email="admin@test.com",
            full_name="Test Admin",
            agency_id=1,
            role=UserRole.ADMIN,
        )
        assert user_is_at_least(admin, UserRole.OWNER) is False

    def test_campaigner_is_not_admin(self):
        """CAMPAIGNER role should fail ADMIN check"""
        campaigner = Campaigner(
            email="campaigner@test.com",
            full_name="Test Campaigner",
            agency_id=1,
            role=UserRole.CAMPAIGNER,
        )
        assert user_is_at_least(campaigner, UserRole.ADMIN) is False

    def test_viewer_is_not_campaigner(self):
        """VIEWER role should fail CAMPAIGNER check"""
        viewer = Campaigner(
            email="viewer@test.com",
            full_name="Test Viewer",
            agency_id=1,
            role=UserRole.VIEWER,
        )
        assert user_is_at_least(viewer, UserRole.CAMPAIGNER) is False

    def test_role_levels_are_ordered(self):
        """Verify role level numeric ordering"""
        assert get_role_level(UserRole.VIEWER) < get_role_level(UserRole.CAMPAIGNER)
        assert get_role_level(UserRole.CAMPAIGNER) < get_role_level(UserRole.ADMIN)
        assert get_role_level(UserRole.ADMIN) < get_role_level(UserRole.OWNER)

    def test_same_role_passes_check(self):
        """Same role should pass check"""
        for role in UserRole:
            user = Campaigner(
                email=f"{role.value}@test.com",
                full_name=f"Test {role.value}",
                agency_id=1,
                role=role,
            )
            assert user_is_at_least(user, role) is True

    def test_viewer_is_at_least_viewer(self):
        """VIEWER role should pass VIEWER check"""
        viewer = Campaigner(
            email="viewer@test.com",
            full_name="Test Viewer",
            agency_id=1,
            role=UserRole.VIEWER,
        )
        assert user_is_at_least(viewer, UserRole.VIEWER) is True

    def test_campaigner_is_at_least_viewer(self):
        """CAMPAIGNER role should pass VIEWER check"""
        campaigner = Campaigner(
            email="campaigner@test.com",
            full_name="Test Campaigner",
            agency_id=1,
            role=UserRole.CAMPAIGNER,
        )
        assert user_is_at_least(campaigner, UserRole.VIEWER) is True

    def test_admin_is_at_least_viewer(self):
        """ADMIN role should pass VIEWER check"""
        admin = Campaigner(
            email="admin@test.com",
            full_name="Test Admin",
            agency_id=1,
            role=UserRole.ADMIN,
        )
        assert user_is_at_least(admin, UserRole.VIEWER) is True

    def test_owner_is_at_least_viewer(self):
        """OWNER role should pass VIEWER check"""
        owner = Campaigner(
            email="owner@test.com",
            full_name="Test Owner",
            agency_id=1,
            role=UserRole.OWNER,
        )
        assert user_is_at_least(owner, UserRole.VIEWER) is True
