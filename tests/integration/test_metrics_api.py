"""
Integration tests for Metrics API endpoint
Tests role-based access control, filtering, and pagination
"""

import pytest
from datetime import date, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import create_app
from app.models.users import (
    Campaigner,
    Agency,
    Customer,
    CustomerCampaignerAssignment,
    UserRole,
    UserStatus,
    CustomerStatus,
)
from app.models.analytics import DigitalAsset, Metrics, AssetType
from app.core.auth import create_access_token


@pytest.fixture
def client():
    """Create test client"""
    app = create_app()
    return TestClient(app)


@pytest.fixture
def setup_test_data(db_session):
    """Setup test data for metrics API tests"""
    # Create agencies
    agency1 = Agency(
        name="Agency 1",
        email="agency1@test.com",
        status=CustomerStatus.ACTIVE,
    )
    agency2 = Agency(
        name="Agency 2",
        email="agency2@test.com",
        status=CustomerStatus.ACTIVE,
    )
    db_session.add_all([agency1, agency2])
    db_session.commit()
    db_session.refresh(agency1)
    db_session.refresh(agency2)

    # Create campaigners with different roles
    owner = Campaigner(
        email="owner@test.com",
        full_name="Owner User",
        role=UserRole.OWNER,
        status=UserStatus.ACTIVE,
        agency_id=agency1.id,
    )
    admin = Campaigner(
        email="admin@test.com",
        full_name="Admin User",
        role=UserRole.ADMIN,
        status=UserStatus.ACTIVE,
        agency_id=agency1.id,
    )
    campaigner1 = Campaigner(
        email="campaigner1@test.com",
        full_name="Campaigner 1",
        role=UserRole.CAMPAIGNER,
        status=UserStatus.ACTIVE,
        agency_id=agency1.id,
    )
    campaigner2 = Campaigner(
        email="campaigner2@test.com",
        full_name="Campaigner 2",
        role=UserRole.CAMPAIGNER,
        status=UserStatus.ACTIVE,
        agency_id=agency2.id,
    )
    db_session.add_all([owner, admin, campaigner1, campaigner2])
    db_session.commit()
    db_session.refresh(owner)
    db_session.refresh(admin)
    db_session.refresh(campaigner1)
    db_session.refresh(campaigner2)

    # Create customers
    customer1 = Customer(
        full_name="Customer 1",
        contact_email="customer1@test.com",
        agency_id=agency1.id,
        status=CustomerStatus.ACTIVE,
    )
    customer2 = Customer(
        full_name="Customer 2",
        contact_email="customer2@test.com",
        agency_id=agency1.id,
        status=CustomerStatus.ACTIVE,
    )
    customer3 = Customer(
        full_name="Customer 3",
        contact_email="customer3@test.com",
        agency_id=agency2.id,
        status=CustomerStatus.ACTIVE,
    )
    db_session.add_all([customer1, customer2, customer3])
    db_session.commit()
    db_session.refresh(customer1)
    db_session.refresh(customer2)
    db_session.refresh(customer3)

    # Assign campaigner1 to customer1 only
    assignment1 = CustomerCampaignerAssignment(
        customer_id=customer1.id,
        campaigner_id=campaigner1.id,
        is_primary=True,
        is_active=True,
    )
    db_session.add(assignment1)
    db_session.commit()

    # Create digital assets (platforms)
    asset1 = DigitalAsset(
        customer_id=customer1.id,
        asset_type=AssetType.GOOGLE_ADS,
        platform_name="Google Ads",
        is_active=True,
    )
    asset2 = DigitalAsset(
        customer_id=customer2.id,
        asset_type=AssetType.FACEBOOK_ADS,
        platform_name="Facebook Ads",
        is_active=True,
    )
    asset3 = DigitalAsset(
        customer_id=customer3.id,
        asset_type=AssetType.GOOGLE_ADS,
        platform_name="Google Ads",
        is_active=True,
    )
    db_session.add_all([asset1, asset2, asset3])
    db_session.commit()
    db_session.refresh(asset1)
    db_session.refresh(asset2)
    db_session.refresh(asset3)

    # Create metrics for different dates
    today = date.today()
    yesterday = today - timedelta(days=1)
    week_ago = today - timedelta(days=7)

    metrics_data = [
        # Customer 1 metrics (agency1, assigned to campaigner1)
        Metrics(
            metric_date=today,
            item_id="ad-1",
            platform_id=asset1.id,
            item_type="ad",
            impressions=1000,
            clicks=50,
            spent=100.0,
            conversions=5,
            cpa=20.0,
        ),
        Metrics(
            metric_date=yesterday,
            item_id="ad-1",
            platform_id=asset1.id,
            item_type="ad",
            impressions=900,
            clicks=45,
            spent=90.0,
            conversions=4,
            cpa=22.5,
        ),
        Metrics(
            metric_date=week_ago,
            item_id="adgroup-1",
            platform_id=asset1.id,
            item_type="ad_group",
            impressions=5000,
            clicks=200,
            spent=400.0,
            conversions=15,
            cpa=26.67,
        ),
        # Customer 2 metrics (agency1, not assigned to campaigner1)
        Metrics(
            metric_date=today,
            item_id="ad-2",
            platform_id=asset2.id,
            item_type="ad",
            impressions=2000,
            clicks=100,
            spent=200.0,
            conversions=10,
            cpa=20.0,
        ),
        # Customer 3 metrics (agency2, different agency)
        Metrics(
            metric_date=today,
            item_id="ad-3",
            platform_id=asset3.id,
            item_type="ad",
            impressions=3000,
            clicks=150,
            spent=300.0,
            conversions=15,
            cpa=20.0,
        ),
    ]
    db_session.add_all(metrics_data)
    db_session.commit()

    return {
        "owner": owner,
        "admin": admin,
        "campaigner1": campaigner1,
        "campaigner2": campaigner2,
        "customer1": customer1,
        "customer2": customer2,
        "customer3": customer3,
        "asset1": asset1,
        "asset2": asset2,
        "asset3": asset3,
        "agency1": agency1,
        "agency2": agency2,
    }


class TestMetricsAPIAccess:
    """Test role-based access control for metrics API"""

    def test_owner_can_access_all_metrics(self, client, setup_test_data, db_session):
        """OWNER should be able to access all metrics across all agencies"""
        owner = setup_test_data["owner"]
        token = create_access_token(data={"sub": owner.email})

        response = client.get(
            "/api/v1/metrics",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["total"] == 5  # All 5 metrics from all agencies

    def test_admin_can_access_agency_metrics_only(self, client, setup_test_data, db_session):
        """ADMIN should only access metrics for customers in their agency"""
        admin = setup_test_data["admin"]
        token = create_access_token(data={"sub": admin.email})

        response = client.get(
            "/api/v1/metrics",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["total"] == 4  # 3 from customer1 + 1 from customer2 (both in agency1)

    def test_campaigner_can_access_assigned_metrics_only(self, client, setup_test_data, db_session):
        """CAMPAIGNER should only access metrics for assigned customers"""
        campaigner1 = setup_test_data["campaigner1"]
        token = create_access_token(data={"sub": campaigner1.email})

        response = client.get(
            "/api/v1/metrics",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["total"] == 3  # Only customer1's metrics (campaigner1 is assigned)

    def test_campaigner_cannot_access_unassigned_customer(self, client, setup_test_data, db_session):
        """CAMPAIGNER should get 403 when accessing unassigned customer"""
        campaigner1 = setup_test_data["campaigner1"]
        customer2 = setup_test_data["customer2"]
        token = create_access_token(data={"sub": campaigner1.email})

        response = client.get(
            f"/api/v1/metrics?customer_id={customer2.id}",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 403
        assert "do not have access" in response.json()["detail"]

    def test_admin_cannot_access_other_agency_customer(self, client, setup_test_data, db_session):
        """ADMIN should get 403 when accessing other agency's customer"""
        admin = setup_test_data["admin"]
        customer3 = setup_test_data["customer3"]  # agency2
        token = create_access_token(data={"sub": admin.email})

        response = client.get(
            f"/api/v1/metrics?customer_id={customer3.id}",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 403
        assert "do not have access" in response.json()["detail"]


class TestMetricsAPIFiltering:
    """Test filtering options for metrics API"""

    def test_filter_by_date_range(self, client, setup_test_data, db_session):
        """Test filtering metrics by date range"""
        owner = setup_test_data["owner"]
        token = create_access_token(data={"sub": owner.email})

        today = date.today()
        yesterday = today - timedelta(days=1)

        response = client.get(
            f"/api/v1/metrics?start_date={yesterday}&end_date={today}",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        # Should only return today and yesterday metrics (4 records)
        assert data["total"] == 4

    def test_filter_by_platform_id(self, client, setup_test_data, db_session):
        """Test filtering metrics by platform_id"""
        owner = setup_test_data["owner"]
        asset1 = setup_test_data["asset1"]
        token = create_access_token(data={"sub": owner.email})

        response = client.get(
            f"/api/v1/metrics?platform_id={asset1.id}",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        # Should only return asset1 metrics (3 records)
        assert data["total"] == 3
        for metric in data["metrics"]:
            assert metric["platform_id"] == asset1.id

    def test_filter_by_item_type_ad(self, client, setup_test_data, db_session):
        """Test filtering metrics by item_type='ad'"""
        owner = setup_test_data["owner"]
        token = create_access_token(data={"sub": owner.email})

        response = client.get(
            "/api/v1/metrics?item_type=ad",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        # Should only return ad-level metrics (4 records)
        assert data["total"] == 4
        for metric in data["metrics"]:
            assert metric["item_type"] == "ad"

    def test_filter_by_item_type_ad_group(self, client, setup_test_data, db_session):
        """Test filtering metrics by item_type='ad_group'"""
        owner = setup_test_data["owner"]
        token = create_access_token(data={"sub": owner.email})

        response = client.get(
            "/api/v1/metrics?item_type=ad_group",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        # Should only return ad_group metrics (1 record)
        assert data["total"] == 1
        assert data["metrics"][0]["item_type"] == "ad_group"

    def test_filter_by_customer_id_owner(self, client, setup_test_data, db_session):
        """Test filtering by customer_id as OWNER"""
        owner = setup_test_data["owner"]
        customer1 = setup_test_data["customer1"]
        token = create_access_token(data={"sub": owner.email})

        response = client.get(
            f"/api/v1/metrics?customer_id={customer1.id}",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        # Should only return customer1 metrics (3 records)
        assert data["total"] == 3

    def test_combined_filters(self, client, setup_test_data, db_session):
        """Test combining multiple filters"""
        owner = setup_test_data["owner"]
        asset1 = setup_test_data["asset1"]
        token = create_access_token(data={"sub": owner.email})

        today = date.today()

        response = client.get(
            f"/api/v1/metrics?platform_id={asset1.id}&item_type=ad&start_date={today}",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        # Should only return today's ad metrics for asset1 (1 record)
        assert data["total"] == 1
        assert data["metrics"][0]["item_type"] == "ad"
        assert data["metrics"][0]["platform_id"] == asset1.id


class TestMetricsAPIPagination:
    """Test pagination for metrics API"""

    def test_pagination_limit(self, client, setup_test_data, db_session):
        """Test pagination with limit"""
        owner = setup_test_data["owner"]
        token = create_access_token(data={"sub": owner.email})

        response = client.get(
            "/api/v1/metrics?limit=2",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["metrics"]) == 2  # Should return only 2 records
        assert data["total"] == 5  # Total should still be 5
        assert data["limit"] == 2
        assert data["offset"] == 0

    def test_pagination_offset(self, client, setup_test_data, db_session):
        """Test pagination with offset"""
        owner = setup_test_data["owner"]
        token = create_access_token(data={"sub": owner.email})

        response = client.get(
            "/api/v1/metrics?limit=2&offset=2",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["metrics"]) == 2  # Should return 2 records
        assert data["limit"] == 2
        assert data["offset"] == 2

    def test_pagination_limit_exceeds_max(self, client, setup_test_data, db_session):
        """Test that limit cannot exceed max value (1000)"""
        owner = setup_test_data["owner"]
        token = create_access_token(data={"sub": owner.email})

        response = client.get(
            "/api/v1/metrics?limit=2000",
            headers={"Authorization": f"Bearer {token}"}
        )

        # Should get validation error
        assert response.status_code == 422


class TestMetricsAPIValidation:
    """Test validation and error handling"""

    def test_invalid_item_type(self, client, setup_test_data, db_session):
        """Test error when providing invalid item_type"""
        owner = setup_test_data["owner"]
        token = create_access_token(data={"sub": owner.email})

        response = client.get(
            "/api/v1/metrics?item_type=invalid",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 400
        assert "must be 'ad' or 'ad_group'" in response.json()["detail"]

    def test_unauthorized_access(self, client, setup_test_data, db_session):
        """Test error when accessing without authentication"""
        response = client.get("/api/v1/metrics")

        assert response.status_code == 401  # Unauthorized

    def test_invalid_date_format(self, client, setup_test_data, db_session):
        """Test error when providing invalid date format"""
        owner = setup_test_data["owner"]
        token = create_access_token(data={"sub": owner.email})

        response = client.get(
            "/api/v1/metrics?start_date=invalid-date",
            headers={"Authorization": f"Bearer {token}"}
        )

        # Should get validation error
        assert response.status_code == 422


class TestMetricsAPIResponseStructure:
    """Test response structure and data format"""

    def test_response_structure(self, client, setup_test_data, db_session):
        """Test that response has correct structure"""
        owner = setup_test_data["owner"]
        token = create_access_token(data={"sub": owner.email})

        response = client.get(
            "/api/v1/metrics?limit=1",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()

        # Check top-level structure
        assert "success" in data
        assert "metrics" in data
        assert "total" in data
        assert "limit" in data
        assert "offset" in data
        assert "filters_applied" in data

        # Check metrics array structure
        if data["metrics"]:
            metric = data["metrics"][0]
            assert "metric_date" in metric
            assert "item_id" in metric
            assert "platform_id" in metric
            assert "item_type" in metric
            # Check optional metrics fields
            assert "cpa" in metric
            assert "cvr" in metric
            assert "clicks" in metric
            assert "impressions" in metric
            assert "spent" in metric
            assert "conversions" in metric

    def test_empty_result_structure(self, client, setup_test_data, db_session):
        """Test response structure when no metrics found"""
        campaigner2 = setup_test_data["campaigner2"]  # No assignments
        token = create_access_token(data={"sub": campaigner2.email})

        response = client.get(
            "/api/v1/metrics",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["metrics"] == []
        assert data["total"] == 0
