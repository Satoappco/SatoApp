"""
Integration tests for Metrics API endpoint
Tests role-based access control, filtering, and pagination
"""

import pytest
from datetime import date, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import select
from unittest.mock import patch
from contextlib import contextmanager

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
def client(db_session):
    """Create test client with mocked database session"""
    app = create_app()

    # Mock get_session to return the test database session
    @contextmanager
    def mock_get_session():
        yield db_session

    # Patch get_session throughout the app
    with patch('app.config.database.get_session', mock_get_session):
        with patch('app.core.auth.get_session', mock_get_session):
            with patch('app.api.v1.routes.metrics.get_session', mock_get_session):
                yield TestClient(app)


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
        provider="Google",
        name="Google Ads Account 1",
        external_id="google-ads-123",
        is_active=True,
    )
    asset2 = DigitalAsset(
        customer_id=customer2.id,
        asset_type=AssetType.FACEBOOK_ADS,
        provider="Facebook",
        name="Facebook Ads Account 2",
        external_id="facebook-ads-456",
        is_active=True,
    )
    asset3 = DigitalAsset(
        customer_id=customer3.id,
        asset_type=AssetType.GOOGLE_ADS,
        provider="Google",
        name="Google Ads Account 3",
        external_id="google-ads-789",
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
            reach=800,
            frequency=1.25,
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
            reach=750,
            frequency=1.20,
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
            reach=4000,
            frequency=1.25,
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
            reach=1600,
            frequency=1.25,
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
            reach=2400,
            frequency=1.25,
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

        assert response.status_code == 403  # Forbidden (no auth credentials provided)

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


class TestAggregatedMetricsAPI:
    """Test aggregated metrics endpoint"""

    def test_aggregate_metrics_default_per_ad(self, client, setup_test_data, db_session):
        """Test that metrics are aggregated per ad by default"""
        owner = setup_test_data["owner"]
        token = create_access_token(data={"sub": owner.email})

        today = date.today()
        yesterday = today - timedelta(days=1)

        response = client.get(
            f"/api/v1/metrics/aggregated?start_date={yesterday}&end_date={today}",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "aggregated_metrics" in data
        # Default grouping by item_id should return 3 items (ad-1, ad-2, ad-3)
        assert len(data["aggregated_metrics"]) == 3

    def test_aggregate_metrics_total_with_group_by_none(self, client, setup_test_data, db_session):
        """Test aggregating all metrics into a single total with group_by=none"""
        owner = setup_test_data["owner"]
        token = create_access_token(data={"sub": owner.email})

        today = date.today()
        yesterday = today - timedelta(days=1)

        response = client.get(
            f"/api/v1/metrics/aggregated?start_date={yesterday}&end_date={today}&group_by=none",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "aggregated_metrics" in data
        assert len(data["aggregated_metrics"]) == 1

        # Check aggregated values
        agg = data["aggregated_metrics"][0]
        # Total impressions: 1000 + 900 + 2000 + 3000 = 6900
        assert agg["impressions"] == 6900
        # Total clicks: 50 + 45 + 100 + 150 = 345
        assert agg["clicks"] == 345
        # Total spent: 100 + 90 + 200 + 300 = 690
        assert agg["spent"] == 690.0
        # Total conversions: 5 + 4 + 10 + 15 = 34
        assert agg["conversions"] == 34

        # Check calculated metrics
        # CPA = 690 / 34 ≈ 20.29
        assert agg["cpa"] == pytest.approx(20.29, rel=0.01)
        # CTR = (345 / 6900) * 100 = 5.0
        assert agg["ctr"] == 5.0
        # CPC = 690 / 345 = 2.0
        assert agg["cpc"] == 2.0

    def test_aggregate_metrics_by_item_id(self, client, setup_test_data, db_session):
        """Test aggregating metrics grouped by item_id"""
        owner = setup_test_data["owner"]
        asset1 = setup_test_data["asset1"]
        token = create_access_token(data={"sub": owner.email})

        today = date.today()
        yesterday = today - timedelta(days=1)

        response = client.get(
            f"/api/v1/metrics/aggregated?start_date={yesterday}&end_date={today}&group_by=item_id",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["aggregated_metrics"]) == 3  # ad-1, ad-2, ad-3

        # Find ad-1 aggregation (from asset1)
        ad1_agg = next((m for m in data["aggregated_metrics"] if m["item_id"] == "ad-1"), None)
        assert ad1_agg is not None
        assert ad1_agg["platform_id"] == asset1.id
        # ad-1 has 2 days: impressions 1000 + 900 = 1900
        assert ad1_agg["impressions"] == 1900
        # clicks: 50 + 45 = 95
        assert ad1_agg["clicks"] == 95
        # spent: 100 + 90 = 190
        assert ad1_agg["spent"] == 190.0
        # conversions: 5 + 4 = 9
        assert ad1_agg["conversions"] == 9
        # CPA = 190 / 9 ≈ 21.11
        assert ad1_agg["cpa"] == pytest.approx(21.11, rel=0.01)

    def test_aggregate_metrics_by_platform_id(self, client, setup_test_data, db_session):
        """Test aggregating metrics grouped by platform_id"""
        owner = setup_test_data["owner"]
        asset1 = setup_test_data["asset1"]
        token = create_access_token(data={"sub": owner.email})

        today = date.today()
        yesterday = today - timedelta(days=1)

        response = client.get(
            f"/api/v1/metrics/aggregated?start_date={yesterday}&end_date={today}&group_by=platform_id",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["aggregated_metrics"]) == 3  # 3 assets

        # Find asset1 aggregation
        asset1_agg = next((m for m in data["aggregated_metrics"] if m["platform_id"] == asset1.id), None)
        assert asset1_agg is not None
        # asset1 has 2 records in this range: impressions 1000 + 900 = 1900
        assert asset1_agg["impressions"] == 1900
        assert asset1_agg["clicks"] == 95

    def test_aggregate_metrics_by_item_type(self, client, setup_test_data, db_session):
        """Test aggregating metrics grouped by item_type"""
        owner = setup_test_data["owner"]
        token = create_access_token(data={"sub": owner.email})

        today = date.today()
        yesterday = today - timedelta(days=1)

        response = client.get(
            f"/api/v1/metrics/aggregated?start_date={yesterday}&end_date={today}&group_by=item_type",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["aggregated_metrics"]) == 1  # Only 'ad' type in this date range

        ad_agg = data["aggregated_metrics"][0]
        assert ad_agg["item_type"] == "ad"
        # All 4 ads: impressions 1000 + 900 + 2000 + 3000 = 6900
        assert ad_agg["impressions"] == 6900

    def test_aggregate_metrics_with_filters(self, client, setup_test_data, db_session):
        """Test aggregating metrics with additional filters"""
        owner = setup_test_data["owner"]
        asset1 = setup_test_data["asset1"]
        token = create_access_token(data={"sub": owner.email})

        today = date.today()
        yesterday = today - timedelta(days=1)

        response = client.get(
            f"/api/v1/metrics/aggregated?start_date={yesterday}&end_date={today}&platform_id={asset1.id}&item_type=ad",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["aggregated_metrics"]) == 1

        agg = data["aggregated_metrics"][0]
        # Only ad-1 from asset1: impressions 1000 + 900 = 1900
        assert agg["impressions"] == 1900
        assert agg["clicks"] == 95

    def test_aggregate_metrics_with_specific_item(self, client, setup_test_data, db_session):
        """Test aggregating metrics for a specific item_id"""
        owner = setup_test_data["owner"]
        token = create_access_token(data={"sub": owner.email})

        today = date.today()
        yesterday = today - timedelta(days=1)

        response = client.get(
            f"/api/v1/metrics/aggregated?start_date={yesterday}&end_date={today}&item_id=ad-1",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["aggregated_metrics"]) == 1

        agg = data["aggregated_metrics"][0]
        # Only ad-1: impressions 1000 + 900 = 1900
        assert agg["impressions"] == 1900
        assert agg["clicks"] == 95

    def test_aggregate_metrics_access_control_campaigner(self, client, setup_test_data, db_session):
        """Test that campaigner can only aggregate their assigned customers' metrics"""
        campaigner1 = setup_test_data["campaigner1"]
        token = create_access_token(data={"sub": campaigner1.email})

        today = date.today()
        yesterday = today - timedelta(days=1)

        response = client.get(
            f"/api/v1/metrics/aggregated?start_date={yesterday}&end_date={today}",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        # campaigner1 only has access to customer1's metrics (ad-1)
        assert len(data["aggregated_metrics"]) == 1

        agg = data["aggregated_metrics"][0]
        assert agg["item_id"] == "ad-1"
        # impressions: 1000 + 900 = 1900
        assert agg["impressions"] == 1900

    def test_aggregate_metrics_access_control_admin(self, client, setup_test_data, db_session):
        """Test that admin can aggregate all metrics in their agency"""
        admin = setup_test_data["admin"]
        token = create_access_token(data={"sub": admin.email})

        today = date.today()
        yesterday = today - timedelta(days=1)

        response = client.get(
            f"/api/v1/metrics/aggregated?start_date={yesterday}&end_date={today}&group_by=none",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["aggregated_metrics"]) == 1

        agg = data["aggregated_metrics"][0]
        # admin has access to customer1 and customer2 (agency1)
        # impressions: 1000 + 900 + 2000 = 3900 (excluding customer3 from agency2)
        assert agg["impressions"] == 3900

    def test_aggregate_metrics_handles_null_conversions(self, client, setup_test_data, db_session):
        """Test that CPA returns None when conversions is 0 or None"""
        owner = setup_test_data["owner"]
        asset1 = setup_test_data["asset1"]
        token = create_access_token(data={"sub": owner.email})

        # Add a metric with no conversions
        no_conv_metric = Metrics(
            metric_date=date.today(),
            item_id="ad-no-conv",
            platform_id=asset1.id,
            item_type="ad",
            impressions=1000,
            clicks=50,
            spent=100.0,
            conversions=0,  # No conversions
        )
        db_session.add(no_conv_metric)
        db_session.commit()

        response = client.get(
            f"/api/v1/metrics/aggregated?start_date={date.today()}&end_date={date.today()}&item_id=ad-no-conv",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()
        agg = data["aggregated_metrics"][0]
        # CPA should be None when conversions is 0
        assert agg["cpa"] is None

    def test_aggregate_metrics_response_structure(self, client, setup_test_data, db_session):
        """Test aggregated metrics response structure"""
        owner = setup_test_data["owner"]
        token = create_access_token(data={"sub": owner.email})

        today = date.today()

        response = client.get(
            f"/api/v1/metrics/aggregated?start_date={today}&end_date={today}",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()

        # Check top-level structure
        assert "success" in data
        assert "aggregated_metrics" in data
        assert "date_range" in data
        assert "filters_applied" in data
        assert "notes" in data

        # Check date_range structure
        assert "start_date" in data["date_range"]
        assert "end_date" in data["date_range"]

        # Check filters_applied structure
        filters = data["filters_applied"]
        assert "platform_id" in filters
        assert "item_type" in filters
        assert "item_id" in filters
        assert "customer_id" in filters
        assert "group_by" in filters

        # Check notes structure
        notes = data["notes"]
        assert "reach_bounds" in notes
        assert "frequency_bounds" in notes
        assert "accuracy" in notes

    def test_aggregate_metrics_reach_bounds(self, client, setup_test_data, db_session):
        """Test that reach bounds are calculated correctly"""
        owner = setup_test_data["owner"]
        token = create_access_token(data={"sub": owner.email})

        today = date.today()
        yesterday = today - timedelta(days=1)

        response = client.get(
            f"/api/v1/metrics/aggregated?start_date={yesterday}&end_date={today}&item_id=ad-1",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["aggregated_metrics"]) == 1

        agg = data["aggregated_metrics"][0]

        # Check reach bounds
        # reach_min should be the max of daily reach values (800, 750) = 800
        assert agg["reach_min"] == 800
        # reach_max should be the sum of daily reach values (800 + 750) = 1550
        assert agg["reach_max"] == 1550

        # Check frequency bounds
        # Total impressions: 1000 + 900 = 1900
        # frequency_min = 1900 / 1550 ≈ 1.23
        assert agg["frequency_min"] == pytest.approx(1.23, rel=0.01)
        # frequency_max = 1900 / 800 = 2.38
        assert agg["frequency_max"] == pytest.approx(2.38, rel=0.01)

    def test_aggregate_metrics_reach_bounds_with_grouping(self, client, setup_test_data, db_session):
        """Test reach bounds with group_by=none"""
        owner = setup_test_data["owner"]
        token = create_access_token(data={"sub": owner.email})

        today = date.today()
        yesterday = today - timedelta(days=1)

        response = client.get(
            f"/api/v1/metrics/aggregated?start_date={yesterday}&end_date={today}&group_by=none",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["aggregated_metrics"]) == 1

        agg = data["aggregated_metrics"][0]

        # Check that reach bounds exist
        assert "reach_min" in agg
        assert "reach_max" in agg
        assert "frequency_min" in agg
        assert "frequency_max" in agg

        # Verify reach_min <= reach_max
        if agg["reach_min"] is not None and agg["reach_max"] is not None:
            assert agg["reach_min"] <= agg["reach_max"]

        # Verify frequency_min <= frequency_max
        if agg["frequency_min"] is not None and agg["frequency_max"] is not None:
            assert agg["frequency_min"] <= agg["frequency_max"]

    def test_aggregate_metrics_invalid_group_by(self, client, setup_test_data, db_session):
        """Test error when providing invalid group_by value"""
        owner = setup_test_data["owner"]
        token = create_access_token(data={"sub": owner.email})

        today = date.today()

        response = client.get(
            f"/api/v1/metrics/aggregated?start_date={today}&end_date={today}&group_by=invalid",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 400
        assert "group_by must be" in response.json()["detail"]

    def test_aggregate_metrics_missing_required_dates(self, client, setup_test_data, db_session):
        """Test error when start_date or end_date is missing"""
        owner = setup_test_data["owner"]
        token = create_access_token(data={"sub": owner.email})

        # Missing start_date
        response = client.get(
            f"/api/v1/metrics/aggregated?end_date={date.today()}",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 422

        # Missing end_date
        response = client.get(
            f"/api/v1/metrics/aggregated?start_date={date.today()}",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 422

    def test_aggregate_metrics_score_calculation(self, client, setup_test_data, db_session):
        """Test that performance score is calculated for aggregated metrics"""
        owner = setup_test_data["owner"]
        token = create_access_token(data={"sub": owner.email})

        today = date.today()
        yesterday = today - timedelta(days=1)

        response = client.get(
            f"/api/v1/metrics/aggregated?start_date={yesterday}&end_date={today}&item_id=ad-1",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["aggregated_metrics"]) == 1

        agg = data["aggregated_metrics"][0]

        # Check that score exists
        assert "score" in agg
        # Score should be a number or None
        if agg["score"] is not None:
            assert isinstance(agg["score"], (int, float))
            # Score should be between 0 and 100
            assert 0 <= agg["score"] <= 100

    def test_aggregate_metrics_score_with_default_settings(self, client, setup_test_data, db_session):
        """Test score calculation with default weight settings"""
        from app.models.settings import AppSettings

        # Ensure default settings exist
        default_settings = [
            AppSettings(key="metric_score_normalizer", value="1", value_type="float", category="performance"),
            AppSettings(key="metric_weight_cpa", value="0.25", value_type="float", category="performance"),
            AppSettings(key="metric_weight_cvr", value="0.20", value_type="float", category="performance"),
            AppSettings(key="metric_weight_ctr", value="0.15", value_type="float", category="performance"),
            AppSettings(key="metric_weight_cpc", value="0.15", value_type="float", category="performance"),
            AppSettings(key="metric_weight_cpm", value="0.10", value_type="float", category="performance"),
            AppSettings(key="metric_weight_cpl", value="0.15", value_type="float", category="performance"),
        ]
        for setting in default_settings:
            db_session.add(setting)
        db_session.commit()

        owner = setup_test_data["owner"]
        token = create_access_token(data={"sub": owner.email})

        today = date.today()

        response = client.get(
            f"/api/v1/metrics/aggregated?start_date={today}&end_date={today}",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()

        # All aggregated metrics should have a score
        for agg in data["aggregated_metrics"]:
            assert "score" in agg

    def test_aggregate_metrics_score_with_missing_metrics(self, client, setup_test_data, db_session):
        """Test that score calculation handles missing metrics gracefully"""
        owner = setup_test_data["owner"]
        asset1 = setup_test_data["asset1"]
        token = create_access_token(data={"sub": owner.email})

        # Add a metric with some missing values
        incomplete_metric = Metrics(
            metric_date=date.today(),
            item_id="ad-incomplete",
            platform_id=asset1.id,
            item_type="ad",
            impressions=1000,
            clicks=50,
            spent=100.0,
            # Missing conversions, leads, etc.
        )
        db_session.add(incomplete_metric)
        db_session.commit()

        response = client.get(
            f"/api/v1/metrics/aggregated?start_date={date.today()}&end_date={date.today()}&item_id=ad-incomplete",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()
        agg = data["aggregated_metrics"][0]

        # Score should still be calculated with available metrics
        assert "score" in agg
        # Some calculated metrics will be None
        assert agg["cpa"] is None  # No conversions

    def test_aggregate_metrics_notes_include_score_info(self, client, setup_test_data, db_session):
        """Test that response notes include score calculation info"""
        owner = setup_test_data["owner"]
        token = create_access_token(data={"sub": owner.email})

        response = client.get(
            f"/api/v1/metrics/aggregated?start_date={date.today()}&end_date={date.today()}",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()

        # Check notes include score information
        assert "notes" in data
        assert "score" in data["notes"]
        # Should mention weights and normalizer
        assert "Weights:" in data["notes"]["score"]
        assert "Normalizer=" in data["notes"]["score"]
