"""
Tests for conversation models
"""

import pytest
from datetime import datetime, UTC
from sqlmodel import Session, select
from app.models.conversations import Conversation, Message, AgentStep, ToolUsage
from app.models.base import BaseModel


class TestConversationModel:
    """Test Conversation model"""

    def test_conversation_creation(self):
        """Test creating a Conversation instance"""
        conversation = Conversation(
            thread_id="test_thread_123",
            campaigner_id=1,
            customer_id=2,
            status="active",
            intent={"goal": "test goal"},
            needs_clarification=False,
            ready_for_analysis=True,
            message_count=5,
            agent_step_count=3,
            tool_usage_count=2,
            total_tokens=150,
            duration_seconds=45.5,
            extra_metadata={"key": "value"},
        )

        assert conversation.thread_id == "test_thread_123"
        assert conversation.campaigner_id == 1
        assert conversation.customer_id == 2
        assert conversation.status == "active"
        assert conversation.intent == {"goal": "test goal"}
        assert conversation.message_count == 5
        assert conversation.agent_step_count == 3
        assert conversation.tool_usage_count == 2
        assert conversation.total_tokens == 150
        assert conversation.duration_seconds == 45.5
        assert conversation.extra_metadata == {"key": "value"}

    def test_conversation_defaults(self):
        """Test Conversation default values"""
        conversation = Conversation(thread_id="test_thread_123", campaigner_id=1)

        assert conversation.customer_id is None
        assert conversation.status == "active"
        assert conversation.intent is None
        assert conversation.message_count == 0
        assert conversation.agent_step_count == 0
        assert conversation.tool_usage_count == 0
        assert conversation.total_tokens == 0
        assert conversation.duration_seconds is None
        assert conversation.extra_metadata is None
        assert isinstance(conversation.started_at, datetime)

    def test_conversation_table_structure(self):
        """Test Conversation table structure exists"""
        # Check that table name and structure are defined
        assert hasattr(Conversation, "__tablename__")
        assert hasattr(Conversation, "__table_args__")


class TestMessageModel:
    """Test Message model"""

    def test_message_creation(self):
        """Test creating a Message instance"""
        message = Message(
            conversation_id=1,
            role="user",
            content="Hello, world!",
            model="gpt-4",
            tokens_used=10,
            latency_ms=500,
            extra_metadata={"temperature": 0.7},
        )

        assert message.conversation_id == 1
        assert message.role == "user"
        assert message.content == "Hello, world!"
        assert message.model == "gpt-4"
        assert message.tokens_used == 10
        assert message.latency_ms == 500
        assert message.extra_metadata == {"temperature": 0.7}

    def test_message_defaults(self):
        """Test Message default values"""
        message = Message(
            conversation_id=1, role="assistant", content="Response content"
        )

        assert message.model is None
        assert message.tokens_used is None
        assert message.latency_ms is None

    def test_message_relationship(self):
        """Test Message relationship to Conversation"""
        # This tests that the relationship is properly defined
        assert hasattr(Message, "conversation")
        assert Message.conversation is not None


class TestAgentStepModel:
    """Test AgentStep model"""

    def test_agent_step_creation(self):
        """Test creating an AgentStep instance"""
        agent_step = AgentStep(
            conversation_id=1,
            step_type="thought",
            agent_name="TestAgent",
            agent_role="Analyst",
            content="I need to analyze this data",
            task_index=1,
            task_description="Analyze customer data",
            extra_metadata={"confidence": 0.95},
        )

        assert agent_step.conversation_id == 1
        assert agent_step.step_type == "thought"
        assert agent_step.agent_name == "TestAgent"
        assert agent_step.agent_role == "Analyst"
        assert agent_step.content == "I need to analyze this data"
        assert agent_step.task_index == 1
        assert agent_step.task_description == "Analyze customer data"
        assert agent_step.extra_metadata == {"confidence": 0.95}

    def test_agent_step_defaults(self):
        """Test AgentStep default values"""
        agent_step = AgentStep(
            conversation_id=1, step_type="action", content="Execute action"
        )

        assert agent_step.agent_name is None
        assert agent_step.agent_role is None
        assert agent_step.task_index is None
        assert agent_step.task_description is None

    def test_agent_step_relationships(self):
        """Test AgentStep relationships"""
        assert hasattr(AgentStep, "conversation")
        assert hasattr(AgentStep, "tool_usages")


class TestToolUsageModel:
    """Test ToolUsage model"""

    def test_tool_usage_creation(self):
        """Test creating a ToolUsage instance"""
        tool_usage = ToolUsage(
            conversation_id=1,
            agent_step_id=2,
            tool_name="google_analytics_tool",
            tool_input="get page views",
            tool_output='{"page_views": 1000}',
            success=True,
            latency_ms=200,
            extra_metadata={"api_calls": 1},
        )

        assert tool_usage.conversation_id == 1
        assert tool_usage.agent_step_id == 2
        assert tool_usage.tool_name == "google_analytics_tool"
        assert tool_usage.tool_input == "get page views"
        assert tool_usage.tool_output == '{"page_views": 1000}'
        assert tool_usage.latency_ms == 200
        assert tool_usage.extra_metadata == {"api_calls": 1}

    def test_tool_usage_defaults(self):
        """Test ToolUsage default values"""
        tool_usage = ToolUsage(conversation_id=1, tool_name="calculator_tool")

        assert tool_usage.agent_step_id is None
        assert tool_usage.tool_input is None
        assert tool_usage.tool_output is None
        assert tool_usage.error is None
        assert tool_usage.latency_ms is None

    def test_tool_usage_relationships(self):
        """Test ToolUsage relationships"""
        assert hasattr(ToolUsage, "conversation")
        assert hasattr(ToolUsage, "agent_step")


class TestModelInheritance:
    """Test that models inherit from BaseModel"""

    def test_conversation_inherits_base(self):
        """Test Conversation inherits from BaseModel"""
        assert issubclass(Conversation, BaseModel)

    def test_message_inherits_base(self):
        """Test Message inherits from BaseModel"""
        assert issubclass(Message, BaseModel)

    def test_agent_step_inherits_base(self):
        """Test AgentStep inherits from BaseModel"""
        assert issubclass(AgentStep, BaseModel)

    def test_tool_usage_inherits_base(self):
        """Test ToolUsage inherits from BaseModel"""
        assert issubclass(ToolUsage, BaseModel)


class TestModelValidation:
    """Test model validation"""

    def test_conversation_model_fields(self):
        """Test Conversation model has expected fields"""
        # Test that we can create valid instances
        valid_conversation = Conversation(thread_id="test", campaigner_id=1)
        assert valid_conversation.thread_id == "test"
        assert valid_conversation.campaigner_id == 1

    def test_message_model_fields(self):
        """Test Message model has expected fields"""
        # Valid message
        valid_message = Message(conversation_id=1, role="user", content="test")
        assert valid_message.conversation_id == 1
        assert valid_message.role == "user"
        assert valid_message.content == "test"

    def test_agent_step_model_fields(self):
        """Test AgentStep model has expected fields"""
        # Valid agent step
        valid_step = AgentStep(
            conversation_id=1, step_type="thought", content="thinking"
        )
        assert valid_step.conversation_id == 1
        assert valid_step.step_type == "thought"
        assert valid_step.content == "thinking"

    def test_tool_usage_model_fields(self):
        """Test ToolUsage model has expected fields"""
        # Valid tool usage
        valid_usage = ToolUsage(conversation_id=1, tool_name="test_tool")
        assert valid_usage.conversation_id == 1
        assert valid_usage.tool_name == "test_tool"
