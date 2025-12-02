"""
Tests for crew-related API schemas
"""

import pytest
from datetime import datetime
from pydantic import ValidationError
from app.api.schemas.crew import (
    CrewRequest,
    CrewResponse,
    MasterAgentRequest,
    MasterAgentResponse,
)


class TestCrewRequest:
    """Test CrewRequest schema"""

    def test_crew_request_creation(self):
        """Test creating a CrewRequest with default year"""
        request = CrewRequest(topic="Test topic")
        assert request.topic == "Test topic"
        assert request.current_year == str(datetime.now().year)

    def test_crew_request_custom_year(self):
        """Test creating a CrewRequest with custom year"""
        request = CrewRequest(topic="Test topic", current_year="2023")
        assert request.topic == "Test topic"
        assert request.current_year == "2023"

    def test_crew_request_dict_conversion(self):
        """Test CrewRequest can be converted to dict"""
        request = CrewRequest(topic="Test topic")
        data = request.model_dump()
        assert data["topic"] == "Test topic"
        assert "current_year" in data


class TestCrewResponse:
    """Test CrewResponse schema"""

    def test_crew_response_creation_minimal(self):
        """Test creating a minimal CrewResponse"""
        response = CrewResponse(
            result="Test result",
            topic="Test topic",
            execution_time=1.5,
            timestamp="2023-01-01",
        )
        assert response.result == "Test result"
        assert response.topic == "Test topic"
        assert response.execution_time == 1.5
        assert response.timestamp == "2023-01-01"
        assert response.agent_type is None
        assert response.thinking_steps is None

    def test_crew_response_creation_full(self):
        """Test creating a full CrewResponse"""
        thinking_steps = ["Step 1", "Step 2"]
        response = CrewResponse(
            result="Test result",
            topic="Test topic",
            execution_time=2.5,
            timestamp="2023-01-01",
            agent_type="test_agent",
            thinking_steps=thinking_steps,
        )
        assert response.result == "Test result"
        assert response.topic == "Test topic"
        assert response.execution_time == 2.5
        assert response.timestamp == "2023-01-01"
        assert response.agent_type == "test_agent"
        assert response.thinking_steps == thinking_steps

    def test_crew_response_dict_conversion(self):
        """Test CrewResponse can be converted to dict"""
        response = CrewResponse(
            result="Test result",
            topic="Test topic",
            execution_time=1.5,
            timestamp="2023-01-01",
        )
        data = response.model_dump()
        assert data["result"] == "Test result"
        assert data["topic"] == "Test topic"
        assert data["execution_time"] == 1.5
        assert data["timestamp"] == "2023-01-01"


class TestMasterAgentRequest:
    """Test MasterAgentRequest schema"""

    def test_master_agent_request_creation_minimal(self):
        """Test creating a minimal MasterAgentRequest"""
        request = MasterAgentRequest(user_text="Test message")
        assert request.user_text == "Test message"
        assert request.user_parameters == {}
        assert request.session_id is None
        assert request.source == "api_call"

    def test_master_agent_request_creation_full(self):
        """Test creating a full MasterAgentRequest"""
        params = {"param1": "value1", "param2": 42}
        request = MasterAgentRequest(
            user_text="Test message",
            user_parameters=params,
            session_id="session_123",
            source="web_app",
        )
        assert request.user_text == "Test message"
        assert request.user_parameters == params
        assert request.session_id == "session_123"
        assert request.source == "web_app"

    def test_master_agent_request_dict_conversion(self):
        """Test MasterAgentRequest can be converted to dict"""
        request = MasterAgentRequest(user_text="Test message")
        data = request.model_dump()
        assert data["user_text"] == "Test message"
        assert data["user_parameters"] == {}
        assert data["source"] == "api_call"


class TestMasterAgentResponse:
    """Test MasterAgentResponse schema"""

    def test_master_agent_response_creation_minimal(self):
        """Test creating a minimal MasterAgentResponse"""
        fulfillment = {"response": "Test response"}
        response = MasterAgentResponse(fulfillment_response=fulfillment)
        assert response.fulfillment_response == fulfillment
        assert response.analysis_complete is True
        assert response.session_id is None
        assert response.timestamp is None

    def test_master_agent_response_creation_full(self):
        """Test creating a full MasterAgentResponse"""
        fulfillment = {"response": "Test response", "data": [1, 2, 3]}
        response = MasterAgentResponse(
            fulfillment_response=fulfillment,
            analysis_complete=False,
            session_id="session_123",
            timestamp="2023-01-01T12:00:00Z",
        )
        assert response.fulfillment_response == fulfillment
        assert response.analysis_complete is False
        assert response.session_id == "session_123"
        assert response.timestamp == "2023-01-01T12:00:00Z"

    def test_master_agent_response_dict_conversion(self):
        """Test MasterAgentResponse can be converted to dict"""
        fulfillment = {"response": "Test response"}
        response = MasterAgentResponse(fulfillment_response=fulfillment)
        data = response.model_dump()
        assert data["fulfillment_response"] == fulfillment
        assert data["analysis_complete"] is True


class TestCrewSchemasValidation:
    """Test validation behavior of crew schemas"""

    def test_crew_request_required_fields(self):
        """Test that CrewRequest requires topic"""
        with pytest.raises(ValidationError):
            CrewRequest.model_validate({})

    def test_crew_response_required_fields(self):
        """Test that CrewResponse requires all mandatory fields"""
        with pytest.raises(ValidationError):
            CrewResponse.model_validate({})

        # Test missing topic
        with pytest.raises(ValidationError):
            CrewResponse.model_validate(
                {"result": "test", "execution_time": 1.5, "timestamp": "2023-01-01"}
            )

        # Test missing execution_time
        with pytest.raises(ValidationError):
            CrewResponse.model_validate(
                {"result": "test", "topic": "topic", "timestamp": "2023-01-01"}
            )

        # Test missing timestamp
        with pytest.raises(ValidationError):
            CrewResponse.model_validate(
                {"result": "test", "topic": "topic", "execution_time": 1.5}
            )

    def test_master_agent_request_required_fields(self):
        """Test that MasterAgentRequest requires user_text"""
        with pytest.raises(ValidationError):
            MasterAgentRequest.model_validate({})

    def test_master_agent_response_required_fields(self):
        """Test that MasterAgentResponse requires fulfillment_response"""
        with pytest.raises(ValidationError):
            MasterAgentResponse.model_validate({})
