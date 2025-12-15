"""E2E tests for QA Testing API."""

import pytest
import json
from unittest.mock import patch, AsyncMock


class TestQATestingAPI:
    """Test cases for QA Testing API endpoints."""

    @pytest.mark.asyncio
    async def test_start_qa_test_success(self, client, auth_headers):
        """Test starting a QA test job successfully."""
        request_data = {
            "sheet_url": "https://docs.google.com/spreadsheets/d/test123/edit?gid=0",
            "customer_name": "AEF",
            "start_row": 0,
            "end_row": None,
            "sheet_name": "Automated",
            "fail_fast": True,
            "max_concurrent": 5,
            "fill_blanks": False,
            "save_local": False,
        }

        response = client.post(
            "/api/v1/qa/test", json=request_data, headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data
        assert data["status"] == "pending"
        assert data["message"] == "QA testing job started"
        assert data["total_rows"] is None
        assert data["processed_rows"] is None
        assert "created_at" in data

    @pytest.mark.asyncio
    async def test_get_qa_test_status_not_found(self, client, auth_headers):
        """Test getting status of non-existent job."""
        response = client.get(
            "/api/v1/qa/test/non-existent-job-id", headers=auth_headers
        )

        assert response.status_code == 404
        data = response.json()
        assert data["detail"] == "Job not found"

    @pytest.mark.asyncio
    async def test_start_qa_test_invalid_request(self, client, auth_headers):
        """Test starting QA test with invalid request data."""
        request_data = {
            "sheet_url": "",  # Invalid: empty URL
            "customer_name": "AEF",
        }

        response = client.post(
            "/api/v1/qa/test", json=request_data, headers=auth_headers
        )

        # Should fail validation
        assert response.status_code == 422

    @pytest.mark.asyncio
    @patch("app.api.v1.routes.qa.QATestingService")
    async def test_qa_test_background_processing(
        self, mock_qa_service, client, auth_headers
    ):
        """Test that background QA processing is called correctly."""
        # Mock the QA service
        mock_service_instance = AsyncMock()
        mock_qa_service.return_value.__aenter__.return_value = mock_service_instance
        mock_qa_service.return_value.__aexit__.return_value = None

        mock_service_instance.run_qa_test.return_value = {
            "total_rows": 10,
            "processed_rows": 10,
            "ranking_distribution": {
                "both_good": 5,
                "current_better": 3,
                "previous_better": 2,
            },
            "save_location": "test_location",
        }

        request_data = {
            "sheet_url": "https://docs.google.com/spreadsheets/d/test123/edit?gid=0",
            "customer_name": "AEF",
            "start_row": 0,
            "end_row": 10,
            "sheet_name": "Automated",
            "fail_fast": True,
            "max_concurrent": 5,
            "fill_blanks": False,
            "save_local": False,
        }

        # Start the job
        response = client.post(
            "/api/v1/qa/test", json=request_data, headers=auth_headers
        )

        assert response.status_code == 200
        job_data = response.json()
        job_id = job_data["job_id"]

        # Give background task time to complete (in real scenario, we'd poll)
        import asyncio

        await asyncio.sleep(0.1)

        # Check that the service was called
        mock_service_instance.run_qa_test.assert_called_once()
        call_args = mock_service_instance.run_qa_test.call_args

        # Verify the arguments passed to run_qa_test
        assert call_args[1]["sheet_url"] == request_data["sheet_url"]
        assert call_args[1]["customer_name"] == request_data["customer_name"]
        assert call_args[1]["start_row"] == request_data["start_row"]
        assert call_args[1]["end_row"] == request_data["end_row"]
        assert call_args[1]["sheet_name"] == request_data["sheet_name"]
        assert call_args[1]["fail_fast"] == request_data["fail_fast"]
        assert call_args[1]["max_concurrent"] == request_data["max_concurrent"]
        assert call_args[1]["fill_blanks"] == request_data["fill_blanks"]
        assert call_args[1]["save_local"] == request_data["save_local"]
