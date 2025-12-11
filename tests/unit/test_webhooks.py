"""
Tests for webhooks API routes
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from app.main import app
from app.models.users import Campaigner
from app.models.agents import CustomerLog
from app.core.auth import get_current_user
from app.core.api_auth import verify_webhook_token


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_current_user():
    """Mock current user for authentication."""
    user = MagicMock(spec=Campaigner)
    user.id = 1
    user.role = "CAMPAIGNER"
    return user


@pytest.fixture(autouse=True)
def override_dependencies(mock_current_user):
    """Override FastAPI dependencies for all tests."""
    app.dependency_overrides[get_current_user] = lambda: mock_current_user
    app.dependency_overrides[verify_webhook_token] = lambda: True
    yield
    app.dependency_overrides.clear()


class TestWebhooksRoutes:
    """Test webhooks API routes."""

    @patch("app.config.database.get_session")
    def test_get_customer_logs_empty_result(self, mock_get_session, client):
        """Test get customer logs with no customer_id for regular user."""
        # Mock session
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__.return_value = mock_session

        # Mock query that returns empty
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.count.return_value = 0
        mock_query.all.return_value = []

        response = client.get("/api/v1/webhooks/customer-logs")
        assert response.status_code == 200
        data = response.json()
        assert data["logs"] == []
        assert data["total_count"] == 0

    @patch("app.config.database.get_session")
    def test_get_customer_logs_with_customer_id(self, mock_get_session, client):
        """Test get customer logs with customer_id filter."""
        # Mock session
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__.return_value = mock_session

        # Mock customer log
        mock_log = MagicMock()
        mock_log.id = 1
        mock_log.session_id = "test_session"
        mock_log.date_time = MagicMock()
        mock_log.date_time.isoformat.return_value = "2023-01-01T00:00:00Z"
        mock_log.user_intent = "test intent"
        mock_log.original_query = "test query"
        mock_log.crewai_input_prompt = "test prompt"
        mock_log.master_answer = "test answer"
        mock_log.crewai_log = '{"test": "log"}'
        mock_log.total_execution_time_ms = 1000
        mock_log.timing_breakdown = '{"test": "timing"}'
        mock_log.campaigner_id = 1
        mock_log.customer_id = 1
        mock_log.analysis_id = "test_analysis"
        mock_log.success = True
        mock_log.error_message = None
        mock_log.agents_used = '["agent1"]'
        mock_log.tools_used = '["tool1"]'

        # Mock query
        mock_query = MagicMock()
        mock_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.count.return_value = 1
        mock_query.all.return_value = [mock_log]

        response = client.get("/api/v1/webhooks/customer-logs?customer_id=1")
        assert response.status_code == 200
        data = response.json()
        assert len(data["logs"]) == 1
        assert data["total_count"] == 1

    def test_dialogcx_webhook_missing_session_id(self, client):
        """Test dialogcx webhook with missing session_id."""
        payload = {
            "campaigner_id": 1,
            "customer_id": 1,
            "user_question": "test question",
        }

        response = client.post("/api/v1/webhooks/dialogcx", json=payload)
        assert response.status_code == 200  # Webhook always returns 200, even on errors

        data = response.json()
        assert "fulfillment_response" in data
        # The error is logged but doesn't change the response status

    def test_dialogcx_webhook_success_bypass_crewai(self, client):
        """Test dialogcx webhook success with CrewAI bypassed."""
        # Temporarily set ENABLE_CREWAI to False
        import app.api.v1.routes.webhooks as webhooks_module

        original_enable_crewai = webhooks_module.ENABLE_CREWAI
        webhooks_module.ENABLE_CREWAI = False

        try:
            payload = {
                "campaigner_id": 1,
                "customer_id": 1,
                "session_id": "test_session_123",
                "user_question": "What is the performance of my campaigns?",
                "user_intent": "analytics",
                "parameters": {"data_sources": ["facebook", "google_ads"]},
            }

            response = client.post("/api/v1/webhooks/dialogcx", json=payload)
            assert response.status_code == 200

            data = response.json()
            assert "fulfillment_response" in data
            # When CrewAI is disabled, it returns a simple response
            assert "messages" in data["fulfillment_response"] or isinstance(
                data["fulfillment_response"], str
            )
        finally:
            # Restore original value
            webhooks_module.ENABLE_CREWAI = original_enable_crewai

    @patch("app.api.v1.routes.webhooks.run_crewai_analysis_async")
    def test_dialogcx_webhook_with_crewai_enabled(
        self, mock_crewai_analysis, client
    ):
        """Test dialogcx webhook with CrewAI enabled."""
        # Temporarily set ENABLE_CREWAI to True
        import app.api.v1.routes.webhooks as webhooks_module

        original_enable_crewai = webhooks_module.ENABLE_CREWAI
        webhooks_module.ENABLE_CREWAI = True

        try:
            # Mock CrewAI analysis async function
            mock_crewai_analysis.return_value = {
                "success": True,
                "result": "CrewAI analysis result",
                "execution_time": 1.0,
                "agents_used": ["master_agent"],
            }

            payload = {
                "campaigner_id": 1,
                "customer_id": 1,
                "session_id": "test_session_123",
                "user_question": "What is the performance of my campaigns?",
                "user_intent": "analytics",
                "parameters": {"data_sources": ["facebook", "google_ads"]},
            }

            response = client.post("/api/v1/webhooks/dialogcx", json=payload)
            assert response.status_code == 200

            data = response.json()
            assert "fulfillment_response" in data

            # Verify CrewAI analysis was called
            mock_crewai_analysis.assert_called_once()

            # Verify the call arguments
            call_args = mock_crewai_analysis.call_args[1]  # Get keyword arguments
            assert call_args["campaigner_id"] == 1
            assert call_args["customer_id"] == 1
            assert call_args["user_question"] == "What is the performance of my campaigns?"
        finally:
            # Restore original value
            webhooks_module.ENABLE_CREWAI = original_enable_crewai

    def test_dialogcx_webhook_invalid_payload(self, client):
        """Test dialogcx webhook with invalid payload."""
        # Empty payload
        response = client.post("/api/v1/webhooks/dialogcx", json={})
        assert response.status_code == 200  # Webhook always returns 200, even on errors

        data = response.json()
        assert "fulfillment_response" in data

    @patch("app.api.v1.routes.webhooks.send_dialogcx_custom_event")
    def test_dialogcx_webhook_crewai_failure(self, mock_send_event, client):
        """Test dialogcx webhook when CrewAI processing fails."""
        # Mock send event to raise exception
        mock_send_event.side_effect = Exception("Custom event failed")

        payload = {
            "campaigner_id": 1,
            "customer_id": 1,
            "session_id": "test_session_123",
            "user_question": "What is the performance of my campaigns?",
            "user_intent": "analytics",
            "parameters": {"data_sources": ["facebook", "google_ads"]},
        }

        # Should still return 200 as the immediate response is sent
        response = client.post("/api/v1/webhooks/dialogcx", json=payload)
        assert response.status_code == 200
