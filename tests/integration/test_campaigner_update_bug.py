"""
Test to reproduce and validate fix for campaigner update bug.
Bug: 'function' object has no attribute 'role' when updating workers.
Root cause: Missing parentheses in Depends(require_admin()) calls.
"""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from app.main import app
from app.models.users import Campaigner, Agency, UserRole, UserStatus
from app.config.database import get_session
from app.core.auth import create_access_token


class TestCampaignerUpdateBug:
    """Test campaigner update bug fix"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)

    @pytest.fixture
    def test_agency(self):
        """Create a test agency"""
        with get_session() as session:
            agency = Agency(
                name="Test Agency for Bug",
                email="test@agency-bug.com",
                phone="123-456-7890"
            )
            session.add(agency)
            session.commit()
            session.refresh(agency)

            yield agency

            # Cleanup
            session.delete(agency)
            session.commit()

    @pytest.fixture
    def admin_user(self, test_agency):
        """Create an admin user for testing"""
        with get_session() as session:
            admin = Campaigner(
                email="admin-bug@test.com",
                full_name="Admin User Bug Test",
                role=UserRole.ADMIN,
                status=UserStatus.ACTIVE,
                agency_id=test_agency.id,
                email_verified=True
            )
            session.add(admin)
            session.commit()
            session.refresh(admin)

            yield admin

            # Cleanup
            session.delete(admin)
            session.commit()

    @pytest.fixture
    def worker_user(self, test_agency):
        """Create a worker user to be updated"""
        with get_session() as session:
            worker = Campaigner(
                email="worker-bug@test.com",
                full_name="Worker User Bug Test",
                role=UserRole.CAMPAIGNER,
                status=UserStatus.ACTIVE,
                agency_id=test_agency.id,
                email_verified=True
            )
            session.add(worker)
            session.commit()
            session.refresh(worker)

            yield worker

            # Cleanup
            session.delete(worker)
            session.commit()

    @pytest.fixture
    def admin_token(self, admin_user):
        """Create access token for admin user"""
        return create_access_token({"sub": str(admin_user.id)})

    def test_update_worker_reproduces_bug(self, client, admin_token, worker_user):
        """
        Test that reproduces the bug: 'function' object has no attribute 'role'

        This test will FAIL before the fix and PASS after the fix.
        The bug occurs because Depends(require_admin()) should be Depends(require_admin())
        """
        # Prepare the update request
        update_data = {
            "full_name": "Updated Worker Name",
            "role": "ADMIN"
        }

        # Make the API request
        response = client.patch(
            f"/api/v1/campaigners/workers/{worker_user.id}",
            json=update_data,
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        # Before fix: will get 500 error with "'function' object has no attribute 'role'"
        # After fix: should return 200
        assert response.status_code == 200, f"Expected 200, got {response.status_code}. Response: {response.json()}"

        # Validate the response
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "Worker updated successfully"
        assert data["data"]["full_name"] == "Updated Worker Name"
        assert data["data"]["role"] == "ADMIN"

    def test_create_worker_with_admin_role(self, client, admin_token, test_agency):
        """
        Test creating a worker - also affected by the bug
        """
        create_data = {
            "email": "newworker-bug@test.com",
            "full_name": "New Worker Bug Test",
            "agency_id": test_agency.id,
            "role": "CAMPAIGNER"
        }

        response = client.post(
            "/api/v1/campaigners/workers",
            json=create_data,
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        # Clean up if created
        if response.status_code == 200:
            data = response.json()
            worker_id = data["data"]["id"]
            with get_session() as session:
                worker = session.get(Campaigner, worker_id)
                if worker:
                    session.delete(worker)
                    session.commit()

        assert response.status_code == 200, f"Expected 200, got {response.status_code}. Response: {response.json()}"

        data = response.json()
        assert data["success"] is True
        assert data["message"] == "Worker created successfully"

    def test_generate_invite_link(self, client, admin_token):
        """
        Test generating invite link - also affected by the bug
        """
        invite_data = {
            "role": "CAMPAIGNER",
            "email": "invite-bug@test.com"
        }

        response = client.post(
            "/api/v1/campaigners/invite/generate",
            json=invite_data,
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code == 200, f"Expected 200, got {response.status_code}. Response: {response.json()}"

        data = response.json()
        assert data["success"] is True
        assert "invite_token" in data
        assert "invite_url" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
