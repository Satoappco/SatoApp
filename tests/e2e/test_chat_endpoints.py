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
def mock_workflow():
    """Mock conversation workflow"""
    workflow = Mock()
    workflow.customer_id = None
    workflow.conversation_state = {
        "messages": [],
        "platforms": [],
        "is_complete": False,
        "ready_for_crew": False
    }

    # Mock process_message to return a valid response
    workflow.process_message.return_value = {
        "messages": [
            Mock(content="Hello! I can help you analyze your marketing campaigns. Which platforms would you like to analyze?")
        ],
        "clarification_needed": True,
        "ready_for_crew": False,
        "platforms": [],
        "metrics": [],
        "clarification_question": "Which platforms would you like to analyze? (e.g., Facebook Ads, Google Ads)"
    }

    # Mock stream_message to yield chunks
    async def mock_stream():
        message = "Hello! I can help you with your analytics."
        for char in message:
            yield {"type": "content", "chunk": char}
        yield {
            "type": "metadata",
            "needs_clarification": False,
            "ready_for_crew": False,
            "platforms": [],
            "metrics": []
        }

    workflow.stream_message = mock_stream

    return workflow


@pytest.fixture
def mock_app_state(mock_workflow):
    """Mock application state"""
    app_state = Mock()
    app_state.get_conversation_workflow.return_value = mock_workflow
    app_state.get_all_threads.return_value = {}
    return app_state


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
    def test_01_initiate_new_chat(self, test_client, auth_headers, mock_app_state, mock_campaigner, override_get_current_user):
        """Test initiating a new chat conversation"""
        with patch("app.api.v1.routes.chat.get_app_state", return_value=mock_app_state):
            with patch("app.config.database.get_session") as mock_db:
                # Mock database session
                mock_session = Mock()
                mock_db.return_value.__enter__.return_value = mock_session

                response = test_client.post(
                    "/api/v1/chat",
                    json={
                        "message": "hello",
                        "customer_id": None
                    },
                    headers=auth_headers
                )

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
    def test_02_regular_message(self, test_client, auth_headers, mock_app_state, mock_campaigner, override_get_current_user):
        """Test sending a regular (non-streaming) message"""
        with patch("app.api.v1.routes.chat.get_app_state", return_value=mock_app_state):
            with patch("app.services.chat_trace_service.ChatTraceService") as MockTraceService:
                # Mock ChatTraceService instance
                mock_trace_service = Mock()
                mock_conversation = Mock(id=1, thread_id="test-thread-123")
                mock_trace = Mock()
                mock_message = Mock(id=1)

                mock_trace_service.create_conversation.return_value = (mock_conversation, mock_trace)
                mock_trace_service.add_message.return_value = mock_message
                mock_trace_service.update_intent.return_value = Mock()
                mock_trace_service.complete_conversation.return_value = Mock()
                mock_trace_service.flush_langfuse.return_value = None

                MockTraceService.return_value = mock_trace_service

                response = test_client.post(
                    "/api/v1/chat",
                    json={
                        "message": "Show me Google Ads performance",
                        "thread_id": "test-thread-123",
                        "customer_id": None
                    },
                    headers=auth_headers
                )

                assert response.status_code == 200
                data = response.json()

                # Verify response
                assert data["thread_id"] == "test-thread-123"
                assert isinstance(data["message"], str)
                assert isinstance(data["needs_clarification"], bool)
                assert isinstance(data["ready_for_analysis"], bool)

                print(f"✅ Regular message processed: {data['message'][:50]}...")

    @pytest.mark.e2e
    def test_03_streaming_message(self, test_client, auth_headers, mock_app_state, mock_campaigner, override_get_current_user):
        """Test sending a streaming message"""
        with patch("app.api.v1.routes.chat.get_app_state", return_value=mock_app_state):
            with patch("app.services.chat_trace_service.ChatTraceService") as MockTraceService:
                # Mock ChatTraceService instance
                mock_trace_service = Mock()
                mock_conversation = Mock(id=1, thread_id="test-thread-456")
                mock_trace = Mock()
                mock_message = Mock(id=1)

                mock_trace_service.create_conversation.return_value = (mock_conversation, mock_trace)
                mock_trace_service.add_message.return_value = mock_message
                mock_trace_service.update_intent.return_value = Mock()
                mock_trace_service.complete_conversation.return_value = Mock()
                mock_trace_service.flush_langfuse.return_value = None

                MockTraceService.return_value = mock_trace_service

                response = test_client.post(
                    "/api/v1/chat/stream",
                    json={
                        "message": "What are my top campaigns?",
                        "thread_id": "test-thread-456",
                        "customer_id": None
                    },
                    headers=auth_headers
                )

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
    def test_04_streaming_with_use_crew(self, test_client, auth_headers, mock_app_state, mock_campaigner, mock_analytics_crew, override_get_current_user):
        """Test sending a streaming message with use_crew flag"""
        with patch("app.api.v1.routes.chat.get_app_state", return_value=mock_app_state):
            with patch("app.services.chat_trace_service.ChatTraceService") as MockTraceService:
                # Mock ChatTraceService instance
                mock_trace_service = Mock()
                mock_conversation = Mock(id=1, thread_id="test-thread-789")
                mock_trace = Mock()
                mock_message = Mock(id=1)

                mock_trace_service.create_conversation.return_value = (mock_conversation, mock_trace)
                mock_trace_service.add_message.return_value = mock_message
                mock_trace_service.update_intent.return_value = Mock()
                mock_trace_service.complete_conversation.return_value = Mock()
                mock_trace_service.flush_langfuse.return_value = None

                MockTraceService.return_value = mock_trace_service

                response = test_client.post(
                    "/api/v1/chat/stream",
                    json={
                        "message": "hello",
                        "thread_id": "test-thread-789",
                        "customer_id": None,
                        "use_crew": True  # This triggers AnalyticsCrew
                    },
                    headers=auth_headers
                )

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
                metadata_received = False

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
                            elif chunk_type == "metadata":
                                metadata_received = True
                                # Verify intent is present
                                assert "intent" in chunk
                        except json.JSONDecodeError:
                            pass

                # Verify crew-specific behavior
                assert len(progress_messages) > 0
                assert any("Crew" in msg or "crew" in msg for msg in progress_messages)

                # Verify content was streamed
                assert len(content_chunks) > 0
                full_response = "".join(content_chunks)
                assert len(full_response) > 0

                # Verify AnalyticsCrew was called
                mock_analytics_crew.execute.assert_called_once()
                call_args = mock_analytics_crew.execute.call_args[0][0]
                assert call_args["query"] == "hello"
                assert call_args["campaigner_id"] == 10
                assert call_args["thread_id"] == "test-thread-789"

                print(f"✅ Crew streaming completed: {full_response[:50]}...")
                print(f"✅ Progress messages: {progress_messages}")
                print(f"✅ Metadata received: {metadata_received}")

    @pytest.mark.e2e
    def test_05_regular_message_with_use_crew(self, test_client, auth_headers, mock_app_state, mock_campaigner, mock_analytics_crew, override_get_current_user):
        """Test sending a regular (non-streaming) message with use_crew flag"""
        with patch("app.api.v1.routes.chat.get_app_state", return_value=mock_app_state):
            with patch("app.services.chat_trace_service.ChatTraceService") as MockTraceService:
                # Mock ChatTraceService instance
                mock_trace_service = Mock()
                mock_conversation = Mock(id=1, thread_id="test-thread-crew-regular")
                mock_trace = Mock()
                mock_message = Mock(id=1)

                mock_trace_service.create_conversation.return_value = (mock_conversation, mock_trace)
                mock_trace_service.add_message.return_value = mock_message
                mock_trace_service.update_intent.return_value = Mock()
                mock_trace_service.complete_conversation.return_value = Mock()
                mock_trace_service.flush_langfuse.return_value = None

                MockTraceService.return_value = mock_trace_service

                response = test_client.post(
                    "/api/v1/chat",
                    json={
                        "message": "Analyze my campaigns",
                        "thread_id": "test-thread-crew-regular",
                        "customer_id": None,
                        "use_crew": True
                    },
                    headers=auth_headers
                )

                assert response.status_code == 200
                data = response.json()

                # Verify crew was used
                assert "message" in data
                assert "thread_id" in data
                assert data["thread_id"] == "test-thread-crew-regular"

                # Verify AnalyticsCrew was called
                mock_analytics_crew.execute.assert_called()

                print(f"✅ Regular crew message processed: {data['message'][:50]}...")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
