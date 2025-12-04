"""
Unit tests for ChatTraceService
"""

import pytest
from unittest.mock import patch, MagicMock, Mock
from datetime import datetime
from sqlmodel import Session

from app.services.chat_trace_service import ChatTraceService
from app.models.chat_traces import ChatTrace, RecordType


@pytest.fixture
def mock_session():
    """Create a mock database session."""
    return MagicMock(spec=Session)


@pytest.fixture
def service(mock_session):
    """Create ChatTraceService with mocked session."""
    return ChatTraceService(session=mock_session)


class TestChatTraceService:
    """Test ChatTraceService functionality."""

    def test_init_with_session(self, mock_session):
        """Test initialization with provided session."""
        service = ChatTraceService(session=mock_session)
        assert service.session == mock_session
        assert not service._should_close_session

    def test_init_without_session(self):
        """Test initialization without session."""
        with patch("app.services.chat_trace_service.get_engine") as mock_engine:
            service = ChatTraceService()
            assert service.session is None
            assert service._should_close_session

    @patch("app.services.chat_trace_service.get_engine")
    def test_get_session_with_existing(self, mock_engine, mock_session):
        """Test _get_session when session already exists."""
        service = ChatTraceService(session=mock_session)
        result = service._get_session()
        assert result == mock_session
        mock_engine.assert_not_called()

    @patch("app.services.chat_trace_service.get_engine")
    @patch("app.services.chat_trace_service.Session")
    def test_get_session_creates_new(self, mock_session_class, mock_engine):
        """Test _get_session creates new session when none exists."""
        # Create service WITHOUT providing a session
        service = ChatTraceService()

        mock_new_session = MagicMock()
        mock_session_class.return_value = mock_new_session

        result = service._get_session()

        assert result is mock_new_session
        mock_session_class.assert_called_once_with(mock_engine.return_value)

    def test_close_session_when_should_close(self):
        """Test _close_session when _should_close_session is True."""
        with patch("app.services.chat_trace_service.get_engine") as mock_engine:
            service = ChatTraceService()
            mock_session = MagicMock()

            service._close_session(mock_session)
            mock_session.close.assert_called_once()

    def test_close_session_when_should_not_close(self, mock_session):
        """Test _close_session when _should_close_session is False."""
        service = ChatTraceService(session=mock_session)

        service._close_session(mock_session)
        mock_session.close.assert_not_called()

    @patch("app.services.chat_trace_service.tiktoken")
    def test_count_tokens(self, mock_tiktoken):
        """Test token counting functionality."""
        mock_encoding = MagicMock()
        mock_encoding.encode.return_value = [1, 2, 3, 4, 5]  # 5 tokens
        mock_tiktoken.encoding_for_model.return_value = mock_encoding

        result = ChatTraceService.count_tokens("test text", "gpt-4")

        assert result == 5
        mock_tiktoken.encoding_for_model.assert_called_once_with("gpt-4")

    @patch("app.services.chat_trace_service.tiktoken")
    def test_count_tokens_fallback(self, mock_tiktoken):
        """Test token counting with fallback encoding."""
        mock_tiktoken.encoding_for_model.side_effect = Exception("Encoding failed")

        result = ChatTraceService.count_tokens("test", "gpt-3.5-turbo")

        assert result == 1  # len("test") // 4 = 1
        mock_tiktoken.encoding_for_model.assert_called_once_with("gpt-3.5-turbo")

    @patch("app.services.chat_trace_service.LangfuseConfig")
    def test_create_conversation_success(
        self, mock_langfuse_config, service, mock_session
    ):
        """Test successful conversation creation."""
        # Mock Langfuse config
        mock_config = MagicMock()
        mock_langfuse_config.return_value = mock_config

        # Mock database operations
        mock_conversation = MagicMock(spec=ChatTrace)
        mock_conversation.id = 1
        mock_conversation.thread_id = "test_thread"
        mock_conversation.status = "active"
        mock_conversation.message_count = 0
        mock_conversation.extra_metadata = {"test": "data"}

        mock_session.add.return_value = None
        mock_session.commit.return_value = None
        mock_session.refresh.return_value = None

        # Mock the exec result - no existing conversation
        mock_session.exec.return_value.first.return_value = None

        result_conversation, result_trace = service.create_conversation(
            thread_id="test_thread",
            campaigner_id=1,
            customer_id=10,
            metadata={"test": "data"},
        )

        # Verify a ChatTrace object was created and returned
        assert result_conversation is not None
        assert hasattr(result_conversation, "thread_id")
        assert result_conversation.thread_id == "test_thread"
        assert result_conversation.record_type.value == "conversation"
        assert result_conversation.campaigner_id == 1
        assert result_conversation.customer_id == 10
        assert result_trace is None  # No Langfuse trace in test

        # Verify session methods were called
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()

    @patch("app.services.chat_trace_service.LangfuseConfig")
    def test_create_conversation_idempotent(
        self, mock_langfuse_config, service, mock_session
    ):
        """Test conversation creation is idempotent."""
        # Mock existing conversation
        mock_existing = MagicMock(spec=ChatTrace)
        mock_existing.id = 1
        mock_existing.thread_id = "test_thread"
        mock_existing.status = "active"

        # Mock exec to return existing conversation
        mock_session.exec.return_value.first.return_value = mock_existing

        result_conversation, result_trace = service.create_conversation(
            thread_id="test_thread", campaigner_id=1, customer_id=10
        )

        assert result_conversation is mock_existing
        # Verify no new conversation was created
        mock_session.add.assert_not_called()
        mock_session.commit.assert_not_called()

    def test_get_conversation_found(self, service, mock_session):
        """Test getting existing conversation."""
        mock_conversation = MagicMock(spec=ChatTrace)
        mock_conversation.id = 1
        mock_conversation.thread_id = "test_thread"

        # Mock exec
        mock_session.exec.return_value.first.return_value = mock_conversation

        result = service.get_conversation("test_thread")

        assert result is mock_conversation

    def test_get_conversation_not_found(self, service, mock_session):
        """Test getting non-existent conversation."""
        # Mock exec returns None
        mock_session.exec.return_value.first.return_value = None

        result = service.get_conversation("nonexistent_thread")

        assert result is None

    @patch("app.services.chat_trace_service.flag_modified")
    def test_update_conversation_data(self, mock_flag_modified, service, mock_session):
        """Test updating conversation data."""
        # Use a real dict so it can be modified
        conversation_data = {"existing": "data"}
        mock_conversation = MagicMock(spec=ChatTrace)
        mock_conversation.data = conversation_data

        # Mock the exec result to return our conversation
        mock_session.exec.return_value.first.return_value = mock_conversation

        result = service.update_conversation_data("test_thread", {"new": "data"})

        # Verify data was updated
        expected_data = {"existing": "data", "new": "data"}
        assert mock_conversation.data == expected_data
        assert result is mock_conversation
        mock_flag_modified.assert_called_once_with(mock_conversation, "data")
        mock_session.commit.assert_called_once()

    def test_update_conversation_data_not_found(self, service, mock_session):
        """Test updating data for non-existent conversation."""
        # Mock exec to return None (conversation not found)
        mock_session.exec.return_value.first.return_value = None

        # Should not raise exception
        result = service.update_conversation_data("nonexistent", {"data": "value"})

        # Should return None when conversation not found
        assert result is None
        # Should not commit when conversation not found
        mock_session.commit.assert_not_called()

    @patch("app.services.chat_trace_service.flag_modified")
    @patch("app.services.chat_trace_service.datetime")
    def test_complete_conversation(
        self, mock_datetime, mock_flag_modified, service, mock_session
    ):
        """Test completing a conversation."""
        from datetime import timezone

        mock_datetime.now.return_value = datetime(
            2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc
        )

        # Use real dict so it can be modified
        conversation_data = {"status": "active", "message_count": 5}
        mock_conversation = MagicMock(spec=ChatTrace)
        mock_conversation.data = conversation_data

        # Mock exec to return our conversation
        mock_session.exec.return_value.first.return_value = mock_conversation

        result = service.complete_conversation("test_thread", status="completed")

        # Verify conversation was updated
        assert mock_conversation.data["status"] == "completed"
        assert mock_conversation.data["completed_at"] == "2023-01-01T12:00:00+00:00"
        assert mock_conversation.data["message_count"] == 5
        assert result is mock_conversation
        mock_flag_modified.assert_called_once()
        mock_session.commit.assert_called_once()

    @patch("app.services.chat_trace_service.ChatTrace")
    @patch("app.services.chat_trace_service.LangfuseConfig")
    @patch("app.services.chat_trace_service.flag_modified")
    def test_add_message(
        self,
        mock_flag_modified,
        mock_langfuse_config,
        mock_chat_trace_class,
        service,
        mock_session,
    ):
        """Test adding a message to conversation."""
        # Mock conversation
        conversation_data = {"message_count": 0, "total_tokens": 0}
        mock_conversation = MagicMock(spec=ChatTrace)
        mock_conversation.id = 1
        mock_conversation.thread_id = "test_thread"
        mock_conversation.campaigner_id = 1
        mock_conversation.customer_id = 10
        mock_conversation.data = conversation_data

        # Mock new message with SQLAlchemy state attribute
        mock_message = MagicMock(spec=ChatTrace)
        mock_message.id = 2
        mock_message._sa_instance_state = MagicMock()  # Add SQLAlchemy state

        mock_chat_trace_class.return_value = mock_message

        # Mock get_conversation and session operations
        with patch.object(service, "get_conversation", return_value=mock_conversation):
            # Mock the count query to return 0 (no existing messages)
            mock_session.exec.return_value.one.return_value = 0

            with patch(
                "app.services.chat_trace_service.ChatTraceService.count_tokens",
                return_value=50,
            ):
                result = service.add_message(
                    thread_id="test_thread",
                    role="user",
                    content="Hello world",
                    model="gpt-4",
                    tokens_used=50,
                    latency_ms=100,
                )

                assert result is mock_message

                # Verify message was created
                mock_chat_trace_class.assert_called_once()
                call_kwargs = mock_chat_trace_class.call_args[1]
                assert call_kwargs["record_type"] == RecordType.MESSAGE
                assert call_kwargs["thread_id"] == "test_thread"
                assert call_kwargs["campaigner_id"] == 1
                assert call_kwargs["customer_id"] == 10

                # Verify conversation was updated
                assert mock_conversation.data["message_count"] == 1
                assert mock_conversation.data["total_tokens"] == 50
                mock_session.commit.assert_called_once()

    @patch("app.services.chat_trace_service.ChatTrace")
    @patch("app.services.chat_trace_service.LangfuseConfig")
    @patch("app.services.chat_trace_service.flag_modified")
    def test_add_agent_step(
        self,
        mock_flag_modified,
        mock_langfuse_config,
        mock_chat_trace_class,
        service,
        mock_session,
    ):
        """Test adding an agent step."""
        # Mock conversation
        mock_conversation = MagicMock(spec=ChatTrace)
        mock_conversation.id = 1
        mock_conversation.thread_id = "test_thread"
        mock_conversation.campaigner_id = 1
        mock_conversation.customer_id = 10
        mock_conversation.data = {"agent_step_count": 0}

        # Mock new step with SQLAlchemy state attribute
        mock_step = MagicMock(spec=ChatTrace)
        mock_step.id = 3
        mock_step._sa_instance_state = MagicMock()  # Add SQLAlchemy state

        mock_chat_trace_class.return_value = mock_step

        with patch.object(service, "get_conversation", return_value=mock_conversation):
            result = service.add_agent_step(
                thread_id="test_thread",
                step_type="thought",
                agent_name="TestAgent",
                agent_role="assistant",
                content="Thinking about the problem",
                task_index=1,
            )

            assert result is mock_step

            # Verify step was created with correct data
            call_kwargs = mock_chat_trace_class.call_args[1]
            assert call_kwargs["record_type"] == RecordType.AGENT_STEP
            assert call_kwargs["thread_id"] == "test_thread"

            # Verify conversation was updated
            assert mock_conversation.data["agent_step_count"] == 1
            mock_flag_modified.assert_called_once()

    @patch("app.services.chat_trace_service.ChatTrace")
    @patch("app.services.chat_trace_service.LangfuseConfig")
    @patch("app.services.chat_trace_service.flag_modified")
    def test_add_tool_usage(
        self,
        mock_flag_modified,
        mock_langfuse_config,
        mock_chat_trace_class,
        service,
        mock_session,
    ):
        """Test adding tool usage."""
        # Mock conversation
        mock_conversation = MagicMock(spec=ChatTrace)
        mock_conversation.id = 1
        mock_conversation.thread_id = "test_thread"
        mock_conversation.campaigner_id = 1
        mock_conversation.customer_id = 10
        mock_conversation.data = {"tool_usage_count": 0}

        # Mock new tool usage with SQLAlchemy state attribute
        mock_tool_usage = MagicMock(spec=ChatTrace)
        mock_tool_usage.id = 4
        mock_tool_usage._sa_instance_state = MagicMock()  # Add SQLAlchemy state

        mock_chat_trace_class.return_value = mock_tool_usage

        with patch.object(service, "get_conversation", return_value=mock_conversation):
            result = service.add_tool_usage(
                thread_id="test_thread",
                tool_name="calculator",
                tool_input={"expression": "2+2"},
                tool_output={"result": 4},
                success=True,
                latency_ms=50,
            )

            assert result is mock_tool_usage

            # Verify tool usage was created
            call_kwargs = mock_chat_trace_class.call_args[1]
            assert call_kwargs["record_type"] == RecordType.TOOL_USAGE

            # Verify conversation was updated
            assert mock_conversation.data["tool_usage_count"] == 1
            mock_flag_modified.assert_called_once()

    @patch("app.services.chat_trace_service.flag_modified")
    def test_update_intent(self, mock_flag_modified, service, mock_session):
        """Test updating conversation intent."""
        # Use real dict so it can be modified
        conversation_data = {"existing": "data"}
        mock_conversation = MagicMock(spec=ChatTrace)
        mock_conversation.data = conversation_data

        # Mock exec to return our conversation
        mock_session.exec.return_value.first.return_value = mock_conversation

        new_intent = {
            "platforms": ["facebook", "google"],
            "metrics": ["impressions", "clicks"],
        }

        result = service.update_intent("test_thread", new_intent)

        # Verify intent was added to data
        assert "intent" in mock_conversation.data
        assert mock_conversation.data["intent"] == new_intent
        assert result is mock_conversation
        mock_flag_modified.assert_called_once()
        mock_session.commit.assert_called_once()

    def test_get_conversation_history(self, service, mock_session):
        """Test getting conversation history."""
        # Mock conversation
        mock_conversation = MagicMock(spec=ChatTrace)
        mock_conversation.id = 1
        mock_conversation.thread_id = "test_thread"
        mock_conversation.campaigner_id = 1
        mock_conversation.customer_id = 10
        mock_conversation.created_at = None
        mock_conversation.updated_at = None
        mock_conversation.langfuse_trace_url = None
        mock_conversation.data = {"status": "active"}

        # Mock messages
        mock_message = MagicMock(spec=ChatTrace)
        mock_message.id = 2
        mock_message.created_at = None
        mock_message.data = {"role": "user", "content": "Hello"}

        # Mock exec calls
        mock_session.exec.side_effect = [
            MagicMock(
                first=MagicMock(return_value=mock_conversation)
            ),  # conversation query
            MagicMock(all=MagicMock(return_value=[mock_message])),  # messages query
            MagicMock(all=MagicMock(return_value=[])),  # steps query
            MagicMock(all=MagicMock(return_value=[])),  # tools query
            MagicMock(all=MagicMock(return_value=[])),  # crewai query
        ]

        result = service.get_conversation_history("test_thread")

        assert result is not None
        assert "conversation" in result
        assert "messages" in result
        assert len(result["messages"]) == 1
        # Check that message data is included
        message_data = result["messages"][0]
        assert message_data["id"] == 2
        assert message_data["role"] == "user"
        assert message_data["content"] == "Hello"

    @patch("app.services.chat_trace_service.LANGFUSE_AVAILABLE", True)
    @patch("app.services.chat_trace_service.LangfuseConfig")
    def test_get_or_create_langfuse_trace_with_langfuse(
        self, mock_langfuse_config, service
    ):
        """Test getting/creating Langfuse trace when Langfuse is available."""
        # Mock conversation
        mock_conversation = MagicMock(spec=ChatTrace)
        mock_conversation.langfuse_trace_id = None  # No existing trace
        mock_conversation.campaigner_id = 1  # Set campaigner_id

        # Mock Langfuse
        mock_langfuse = MagicMock()
        mock_trace = MagicMock()
        mock_langfuse.trace.return_value = mock_trace
        mock_langfuse_config.get_client.return_value = mock_langfuse

        with patch.object(service, "get_conversation", return_value=mock_conversation):
            result = service.get_or_create_langfuse_trace("test_thread")

            assert result == mock_trace
            mock_langfuse.trace.assert_called_once_with(
                name="chat_conversation",
                session_id="test_thread",
                user_id="1",  # Should be string of campaigner_id
                metadata={"thread_id": "test_thread"},
            )

    @patch("app.services.chat_trace_service.LANGFUSE_AVAILABLE", False)
    def test_get_or_create_langfuse_trace_without_langfuse(self, service):
        """Test getting/creating Langfuse trace when Langfuse is not available."""
        result = service.get_or_create_langfuse_trace("test_thread")

        assert result is None

    @patch("app.services.chat_trace_service.LangfuseConfig")
    def test_flush_langfuse_with_langfuse(self, mock_langfuse_config, service):
        """Test flushing Langfuse when available."""
        with patch("app.services.chat_trace_service.LANGFUSE_AVAILABLE", True):
            mock_langfuse = MagicMock()
            mock_langfuse_config.get_client.return_value = mock_langfuse

            service.flush_langfuse()

            mock_langfuse.flush.assert_called_once()

    def test_flush_langfuse_without_langfuse(self, service):
        """Test flushing Langfuse when not available."""
        with patch("app.services.chat_trace_service.LANGFUSE_AVAILABLE", False):
            # Should not raise exception
            service.flush_langfuse()
