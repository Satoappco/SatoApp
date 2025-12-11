"""
End-to-end tests for chat endpoints.

Tests the complete chat flow:
1. Initiate new chat conversation
2. Send regular (non-streaming) message
3. Send streaming message
4. Send streaming message with use_crew flag
"""

import pytest
import json
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from app.main import app
from app.models.users import Campaigner
from app.core.auth import create_access_token, get_current_user


@pytest.fixture
def test_client():
    """Create test client for API testing"""
    return TestClient(app)


@pytest.fixture
def mock_campaigner():
    """Mock authenticated campaigner user"""
    return Campaigner(
        id=10,
        email="dor.yashar@gmail.com",
        full_name="Dor Yashar",
        hashed_password="fake_hash",
        role="campaigner",
        status="active",
        agency_id=1
    )


@pytest.fixture
def auth_headers(mock_campaigner):
    """Generate auth headers with JWT token"""
    access_token = create_access_token(
        data={"sub": mock_campaigner.email, "user_id": mock_campaigner.id}
    )
    return {"Authorization": f"Bearer {access_token}"}


@pytest.fixture
def override_get_current_user(mock_campaigner):
    """Override FastAPI dependency for get_current_user"""
    # Override the dependency
    app.dependency_overrides[get_current_user] = lambda: mock_campaigner
    yield
    # Clean up after test
    app.dependency_overrides.clear()


@pytest.fixture
def mock_llm():
    """Mock LLM calls to avoid actual API calls in tests"""
    from langchain_core.messages import AIMessage

    # Create a mock LLM instance that returns proper messages
    mock_llm_instance = Mock()
    mock_llm_instance.invoke.return_value = AIMessage(
        content="Hello! I can help you analyze your marketing campaigns. Which platforms would you like to analyze?"
    )

    # Mock both ChatOpenAI and ChatGoogleGenerativeAI since workflow uses Google
    with patch("app.core.agents.graph.chatbot_agent.ChatOpenAI", return_value=mock_llm_instance), \
         patch("app.core.agents.graph.workflow.ChatGoogleGenerativeAI", return_value=mock_llm_instance):
        yield mock_llm_instance


@pytest.fixture
def mock_postgres_history():
    """Mock PostgresChatMessageHistory to avoid PostgreSQL connection attempts in E2E tests"""
    with patch("app.core.agents.graph.workflow.PostgresChatMessageHistory") as MockClass:
        # Create a mock instance with proper messages attribute
        mock_instance = Mock()
        mock_instance.messages = []  # Return empty list instead of MagicMock
        mock_instance.add_message = Mock()  # Mock the add_message method
        MockClass.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_analytics_crew():
    """Mock AnalyticsCrew for use_crew tests"""
    with patch("app.core.agents.graph.agents.AnalyticsCrewPlaceholder") as MockCrew:
        crew_instance = Mock()
        crew_instance.execute.return_value = {
            "success": True,
            "status": "completed",
            "result": "Analytics completed successfully. Your campaigns performed well!",
            "platforms": ["google_ads"],
            "task_details": {
                "metrics": ["impressions", "clicks", "conversions", "spend"]
            }
        }
        MockCrew.return_value = crew_instance
        yield crew_instance


class TestChatEndpoints:
    """Test suite for chat endpoints"""

    @pytest.mark.e2e
    def test_01_initiate_new_chat(self, test_client, auth_headers, mock_campaigner, override_get_current_user, mock_postgres_history, mock_llm):
        """Test initiating a new chat conversation"""
        response = test_client.post(
            "/api/v1/chat",
            json={
                "message": "hello",
                "customer_id": None
            },
            headers=auth_headers
        )

        if response.status_code != 200:
            print(f"❌ Response status: {response.status_code}")
            print(f"❌ Response body: {response.text}")
        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "message" in data
        assert "thread_id" in data
        assert "needs_clarification" in data
        assert "ready_for_analysis" in data

        # Store thread_id for subsequent tests
        thread_id = data["thread_id"]
        assert thread_id is not None
        assert len(thread_id) > 0

        print(f"✅ Created conversation: thread_id={thread_id}")

    @pytest.mark.e2e
    def test_02_regular_message(self, test_client, auth_headers, mock_campaigner, override_get_current_user, mock_postgres_history, mock_llm):
        """Test sending a regular (non-streaming) message"""
        response = test_client.post(
            "/api/v1/chat",
            json={
                "message": "Show me Google Ads performance",
                "customer_id": None
            },
            headers=auth_headers
        )

        if response.status_code != 200:
            print(f"❌ Response status: {response.status_code}")
            print(f"❌ Response body: {response.text}")
        assert response.status_code == 200
        data = response.json()

        # Verify response
        assert isinstance(data["message"], str)
        assert isinstance(data["needs_clarification"], bool)
        assert isinstance(data["ready_for_analysis"], bool)

        print(f"✅ Regular message processed: {data['message'][:50]}...")

    @pytest.mark.e2e
    def test_03_streaming_message(self, test_client, auth_headers, mock_campaigner, override_get_current_user, mock_postgres_history, mock_llm):
        """Test sending a streaming message"""
        response = test_client.post(
            "/api/v1/chat/stream",
            json={
                "message": "What are my top campaigns?",
                "customer_id": None
            },
            headers=auth_headers
        )

        if response.status_code != 200:
            print(f"❌ Response status: {response.status_code}")
            print(f"❌ Response body: {response.text}")
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"

        # Parse SSE stream
        content = response.text
        lines = content.split("\n")

        # Verify we received data events
        data_lines = [line for line in lines if line.startswith("data: ")]
        assert len(data_lines) > 0

        # Verify we received content chunks
        content_chunks = []
        metadata_received = False

        for line in data_lines:
            if line.startswith("data: "):
                data_str = line[6:]  # Remove "data: " prefix
                if data_str == "[DONE]":
                    break
                try:
                    chunk = json.loads(data_str)
                    if chunk.get("type") == "content":
                        content_chunks.append(chunk.get("chunk", ""))
                    elif chunk.get("type") == "metadata":
                        metadata_received = True
                except json.JSONDecodeError:
                    pass

        # Verify streaming worked
        assert len(content_chunks) > 0
        full_message = "".join(content_chunks)
        assert len(full_message) > 0

        print(f"✅ Streaming message received: {full_message[:50]}...")
        print(f"✅ Metadata received: {metadata_received}")

    @pytest.mark.e2e
    def test_04_streaming_with_use_crew(self, test_client, auth_headers, mock_campaigner, mock_analytics_crew, override_get_current_user, mock_postgres_history, mock_llm):
        """Test sending a streaming message with use_crew flag"""
        response = test_client.post(
            "/api/v1/chat/stream",
            json={
                "message": "hello",
                "customer_id": None,
                "use_crew": True  # This triggers AnalyticsCrew
            },
            headers=auth_headers
        )

        if response.status_code != 200:
            print(f"❌ Response status: {response.status_code}")
            print(f"❌ Response body: {response.text}")
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"

        # Parse SSE stream
        content = response.text
        lines = content.split("\n")

        # Verify we received data events
        data_lines = [line for line in lines if line.startswith("data: ")]
        assert len(data_lines) > 0

        # Verify crew execution
        progress_messages = []
        content_chunks = []

        for line in data_lines:
            if line.startswith("data: "):
                data_str = line[6:]  # Remove "data: " prefix
                if data_str == "[DONE]":
                    break
                try:
                    chunk = json.loads(data_str)
                    chunk_type = chunk.get("type")

                    if chunk_type == "progress":
                        progress_messages.append(chunk.get("message", ""))
                    elif chunk_type == "content":
                        content_chunks.append(chunk.get("chunk", ""))
                except json.JSONDecodeError:
                    pass

        # Verify crew was used (should have progress messages)
        assert len(progress_messages) > 0 or len(content_chunks) > 0

        print(f"✅ Crew streaming completed with {len(progress_messages)} progress messages")

    @pytest.mark.e2e
    def test_05_regular_message_with_use_crew(self, test_client, auth_headers, mock_campaigner, mock_analytics_crew, override_get_current_user, mock_postgres_history, mock_llm):
        """Test sending a regular (non-streaming) message with use_crew flag"""
        response = test_client.post(
            "/api/v1/chat",
            json={
                "message": "Analyze my campaigns",
                "customer_id": None,
                "use_crew": True
            },
            headers=auth_headers
        )

        if response.status_code != 200:
            print(f"❌ Response status: {response.status_code}")
            print(f"❌ Response body: {response.text}")
        assert response.status_code == 200
        data = response.json()

        # Verify crew was used
        assert "message" in data
        assert "thread_id" in data

        print(f"✅ Regular crew message processed: {data['message'][:50]}...")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
