"""
Tests for ChatTraceService
"""

import pytest
from datetime import datetime
from sqlmodel import Session, create_engine, SQLModel
from sqlalchemy.pool import StaticPool

from app.services.chat_trace_service import ChatTraceService
from app.models.conversations import Conversation, Message, AgentStep, ToolUsage


@pytest.fixture(name="session")
def session_fixture():
    """Create a test database session."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_create_conversation(session):
    """Test creating a new conversation."""
    service = ChatTraceService(session=session)

    conversation, trace = service.create_conversation(
        thread_id="test_thread_1",
        campaigner_id=1,
        customer_id=10,
        metadata={"test": "data"}
    )

    assert conversation is not None
    assert conversation.thread_id == "test_thread_1"
    assert conversation.campaigner_id == 1
    assert conversation.customer_id == 10
    assert conversation.status == "active"
    assert conversation.message_count == 0
    assert conversation.extra_metadata == {"test": "data"}


def test_create_conversation_idempotent(session):
    """Test that creating a conversation twice returns the existing one."""
    service = ChatTraceService(session=session)

    conv1, _ = service.create_conversation(
        thread_id="test_thread_2",
        campaigner_id=1
    )

    conv2, _ = service.create_conversation(
        thread_id="test_thread_2",
        campaigner_id=1
    )

    assert conv1.id == conv2.id


def test_add_message(session):
    """Test adding messages to a conversation."""
    service = ChatTraceService(session=session)

    # Create conversation
    conversation, _ = service.create_conversation(
        thread_id="test_thread_3",
        campaigner_id=1
    )

    # Add user message
    msg1 = service.add_message(
        thread_id="test_thread_3",
        role="user",
        content="Hello, how are you?"
    )

    assert msg1 is not None
    assert msg1.role == "user"
    assert msg1.content == "Hello, how are you?"
    assert msg1.conversation_id == conversation.id

    # Add assistant message
    msg2 = service.add_message(
        thread_id="test_thread_3",
        role="assistant",
        content="I'm doing well, thank you!",
        model="gpt-4",
        tokens_used=10
    )

    assert msg2 is not None
    assert msg2.role == "assistant"
    assert msg2.model == "gpt-4"
    assert msg2.tokens_used == 10

    # Check conversation metrics updated
    updated_conv = service.get_conversation("test_thread_3")
    assert updated_conv.message_count == 2
    assert updated_conv.total_tokens == 10


def test_add_agent_step(session):
    """Test adding agent steps to a conversation."""
    service = ChatTraceService(session=session)

    # Create conversation
    conversation, _ = service.create_conversation(
        thread_id="test_thread_4",
        campaigner_id=1
    )

    # Add agent step
    step = service.add_agent_step(
        thread_id="test_thread_4",
        step_type="thought",
        content="I need to analyze the user's request",
        agent_name="AnalysisAgent",
        agent_role="analyst",
        task_index=0,
        metadata={"confidence": 0.9}
    )

    assert step is not None
    assert step.step_type == "thought"
    assert step.agent_name == "AnalysisAgent"
    assert step.agent_role == "analyst"
    assert step.task_index == 0
    assert step.extra_metadata == {"confidence": 0.9}

    # Check conversation metrics updated
    updated_conv = service.get_conversation("test_thread_4")
    assert updated_conv.agent_step_count == 1


def test_add_tool_usage(session):
    """Test adding tool usages to a conversation."""
    service = ChatTraceService(session=session)

    # Create conversation
    conversation, _ = service.create_conversation(
        thread_id="test_thread_5",
        campaigner_id=1
    )

    # Add successful tool usage
    tool1 = service.add_tool_usage(
        thread_id="test_thread_5",
        tool_name="search_database",
        tool_input={"query": "SELECT * FROM users"},
        tool_output={"rows": 5},
        success=True,
        latency_ms=150
    )

    assert tool1 is not None
    assert tool1.tool_name == "search_database"
    assert tool1.success is True
    assert tool1.latency_ms == 150

    # Add failed tool usage
    tool2 = service.add_tool_usage(
        thread_id="test_thread_5",
        tool_name="api_call",
        tool_input={"endpoint": "/test"},
        success=False,
        error="Connection timeout"
    )

    assert tool2 is not None
    assert tool2.success is False
    assert tool2.error == "Connection timeout"

    # Check conversation metrics updated
    updated_conv = service.get_conversation("test_thread_5")
    assert updated_conv.tool_usage_count == 2


def test_update_intent(session):
    """Test updating conversation intent."""
    service = ChatTraceService(session=session)

    # Create conversation
    conversation, _ = service.create_conversation(
        thread_id="test_thread_6",
        campaigner_id=1
    )

    # Update intent
    updated = service.update_intent(
        thread_id="test_thread_6",
        intent={"platforms": ["google_ads"], "metrics": ["impressions"]},
        needs_clarification=False,
        ready_for_analysis=True
    )

    assert updated is not None
    assert updated.intent == {"platforms": ["google_ads"], "metrics": ["impressions"]}
    assert updated.needs_clarification is False
    assert updated.ready_for_analysis is True


def test_complete_conversation(session):
    """Test completing a conversation."""
    service = ChatTraceService(session=session)

    # Create conversation
    conversation, _ = service.create_conversation(
        thread_id="test_thread_7",
        campaigner_id=1
    )

    # Complete conversation
    completed = service.complete_conversation(
        thread_id="test_thread_7",
        status="completed",
        final_intent={"platforms": ["google_ads"]}
    )

    assert completed is not None
    assert completed.status == "completed"
    assert completed.completed_at is not None
    assert completed.duration_seconds is not None
    assert completed.intent == {"platforms": ["google_ads"]}


def test_get_conversation_history(session):
    """Test retrieving full conversation history."""
    service = ChatTraceService(session=session)

    # Create conversation
    conversation, _ = service.create_conversation(
        thread_id="test_thread_8",
        campaigner_id=1,
        metadata={"source": "web"}
    )

    # Add messages
    service.add_message("test_thread_8", "user", "Hello")
    service.add_message("test_thread_8", "assistant", "Hi there!", model="gpt-4", tokens_used=5)

    # Add agent step
    service.add_agent_step("test_thread_8", "thought", "Analyzing...", agent_name="Agent1")

    # Add tool usage
    service.add_tool_usage("test_thread_8", "search", tool_input={"q": "test"}, success=True)

    # Get history with all data
    history = service.get_conversation_history(
        thread_id="test_thread_8",
        include_messages=True,
        include_steps=True,
        include_tools=True
    )

    assert history is not None
    assert history["conversation"]["thread_id"] == "test_thread_8"
    assert history["conversation"]["message_count"] == 2
    assert history["conversation"]["agent_step_count"] == 1
    assert history["conversation"]["tool_usage_count"] == 1
    assert history["conversation"]["total_tokens"] == 5
    assert history["conversation"]["extra_metadata"] == {"source": "web"}

    assert len(history["messages"]) == 2
    assert history["messages"][0]["role"] == "user"
    assert history["messages"][1]["role"] == "assistant"

    assert len(history["agent_steps"]) == 1
    assert history["agent_steps"][0]["step_type"] == "thought"

    assert len(history["tool_usages"]) == 1
    assert history["tool_usages"][0]["tool_name"] == "search"


def test_get_conversation_history_not_found(session):
    """Test retrieving history for non-existent conversation."""
    service = ChatTraceService(session=session)

    history = service.get_conversation_history("nonexistent_thread")

    assert history is None


def test_add_message_to_nonexistent_conversation(session):
    """Test adding message to non-existent conversation."""
    service = ChatTraceService(session=session)

    message = service.add_message(
        thread_id="nonexistent_thread",
        role="user",
        content="Test"
    )

    assert message is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
