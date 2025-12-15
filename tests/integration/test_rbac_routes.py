import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from app.main import app
from app.models.users import Campaigner, UserRole, Agency, Customer
from app.core.rbac import (
    user_is_at_least,
    user_can_access_agency,
    user_can_access_customer,
    get_accessible_customers,
)
from app.config.database import get_session


class TestRBACRoutes:
    """Test RBAC on protected routes"""

    def test_role_hierarchy_logic(self):
        """Test that role hierarchy logic works correctly"""
        # Test OWNER permissions
        owner = Campaigner(
            email="owner@test.com",
            full_name="Test Owner",
            agency_id=1,
            role=UserRole.OWNER,
        )
        assert user_is_at_least(owner, UserRole.OWNER) is True
        assert user_is_at_least(owner, UserRole.ADMIN) is True
        assert user_is_at_least(owner, UserRole.CAMPAIGNER) is True
        assert user_is_at_least(owner, UserRole.VIEWER) is True

        # Test ADMIN permissions
        admin = Campaigner(
            email="admin@test.com",
            full_name="Test Admin",
            agency_id=1,
            role=UserRole.ADMIN,
        )
        assert user_is_at_least(admin, UserRole.OWNER) is False
        assert user_is_at_least(admin, UserRole.ADMIN) is True
        assert user_is_at_least(admin, UserRole.CAMPAIGNER) is True
        assert user_is_at_least(admin, UserRole.VIEWER) is True

        # Test CAMPAIGNER permissions
        campaigner = Campaigner(
            email="campaigner@test.com",
            full_name="Test Campaigner",
            agency_id=1,
            role=UserRole.CAMPAIGNER,
        )
        assert user_is_at_least(campaigner, UserRole.OWNER) is False
        assert user_is_at_least(campaigner, UserRole.ADMIN) is False
        assert user_is_at_least(campaigner, UserRole.CAMPAIGNER) is True
        assert user_is_at_least(campaigner, UserRole.VIEWER) is True

        # Test VIEWER permissions
        viewer = Campaigner(
            email="viewer@test.com",
            full_name="Test Viewer",
            agency_id=1,
            role=UserRole.VIEWER,
        )
        assert user_is_at_least(viewer, UserRole.OWNER) is False
        assert user_is_at_least(viewer, UserRole.ADMIN) is False
        assert user_is_at_least(viewer, UserRole.CAMPAIGNER) is False
        assert user_is_at_least(viewer, UserRole.VIEWER) is True

    def test_owner_can_access_all_agencies(self):
        """OWNER users can access all agencies"""
        owner = Campaigner(
            email="owner@test.com",
            full_name="Test Owner",
            agency_id=1,
            role=UserRole.OWNER,
        )

        # OWNER can access their own agency
        assert user_can_access_agency(owner, 1) is True

        # OWNER can access other agencies
        assert user_can_access_agency(owner, 2) is True
        assert user_can_access_agency(owner, 999) is True

    def test_admin_can_only_access_own_agency(self):
        """ADMIN users can only access their own agency"""
        admin = Campaigner(
            email="admin@test.com",
            full_name="Test Admin",
            agency_id=1,
            role=UserRole.ADMIN,
        )

        # ADMIN can access their own agency
        assert user_can_access_agency(admin, 1) is True

        # ADMIN cannot access other agencies
        assert user_can_access_agency(admin, 2) is False
        assert user_can_access_agency(admin, 999) is False

    def test_campaigner_can_only_access_own_agency(self):
        """CAMPAIGNER users can only access their own agency"""
        campaigner = Campaigner(
            email="campaigner@test.com",
            full_name="Test Campaigner",
            agency_id=1,
            role=UserRole.CAMPAIGNER,
        )

        # CAMPAIGNER can access their own agency
        assert user_can_access_agency(campaigner, 1) is True

        # CAMPAIGNER cannot access other agencies
        assert user_can_access_agency(campaigner, 2) is False
        assert user_can_access_agency(campaigner, 999) is False

    def test_customer_creation_requires_admin(self, client: TestClient):
        """POST /customers should require ADMIN role"""
        # Without authentication, should get 401
        response = client.post(
            "/api/v1/customers",
            json={
                "full_name": "Test Customer",
                "contact_email": "test@example.com",
                "agency_id": 1,
            },
        )
        assert response.status_code == 401

    def test_customer_deletion_requires_admin(self, client: TestClient):
        """DELETE /customers should require ADMIN role"""
        # Without authentication, should get 401
        response = client.delete("/api/v1/customers/1")
        assert response.status_code == 401

    def test_agency_creation_requires_owner(self, client: TestClient):
        """POST /agencies should require OWNER role"""
        # Without authentication, should get 401
        response = client.post(
            "/api/v1/agencies",
            json={
                "name": "Test Agency",
                "email": "test@example.com",
            },
        )
        assert response.status_code == 401

    def test_campaigner_creation_requires_admin(self, client: TestClient):
        """POST /campaigners/workers should require ADMIN role"""
        # Without authentication, should get 401
        response = client.post(
            "/api/v1/campaigners/workers",
            json={
                "email": "new@example.com",
                "full_name": "New Worker",
                "agency_id": 1,
            },
        )
        assert response.status_code == 401

    def test_agency_endpoints_require_auth(self, client: TestClient):
        """Agency endpoints require authentication"""
        # Test GET agencies
        response = client.get("/api/v1/agencies/")
        assert response.status_code in [401, 403]

        # Test POST agency
        response = client.post(
            "/api/v1/agencies/",
            json={"name": "Test Agency", "email": "test@example.com"},
        )
        assert response.status_code in [401, 403]

        # Test PUT agency
        response = client.put("/api/v1/agencies/1", json={"name": "Updated Agency"})
        assert response.status_code in [401, 403]

        # Test DELETE agency
        response = client.delete("/api/v1/agencies/1")
        assert response.status_code in [401, 403]

    def test_customer_endpoints_require_auth(self, client: TestClient):
        """Customer endpoints require authentication"""
        # Test GET customers
        response = client.get("/api/v1/customers/")
        assert response.status_code in [401, 403]

        # Test GET specific customer
        response = client.get("/api/v1/customers/1")
        assert response.status_code in [401, 403]

        # Test POST customer
        response = client.post(
            "/api/v1/customers/", json={"full_name": "Test Customer", "agency_id": 1}
        )
        assert response.status_code in [401, 403]

    def test_campaigner_endpoints_require_auth(self, client: TestClient):
        """Campaigner endpoints require authentication"""
        # Test GET workers
        response = client.get("/api/v1/campaigners/workers")
        assert response.status_code in [401, 403]

        # Test GET specific worker
        response = client.get("/api/v1/campaigners/workers/1")
        assert response.status_code in [401, 403]

        # Test POST worker
        response = client.post(
            "/api/v1/campaigners/workers",
            json={
                "email": "new@example.com",
                "full_name": "New Worker",
                "agency_id": 1,
            },
        )
        assert response.status_code in [401, 403]

        # Test PATCH worker
        response = client.patch(
            "/api/v1/campaigners/workers/1", json={"full_name": "Updated Worker"}
        )
        assert response.status_code in [401, 403]

        # Test DELETE worker
        response = client.delete("/api/v1/campaigners/workers/1")
        assert response.status_code in [401, 403]
