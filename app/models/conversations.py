"""
Conversation and messaging models for chat trace recording
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from sqlmodel import SQLModel, Field, Column, JSON, Relationship
from sqlalchemy import Index
from .base import BaseModel


class Conversation(BaseModel, table=True):
    """Main conversation thread."""

    __tablename__ = "conversations"

    # Primary key inherited from BaseModel (id)
    thread_id: str = Field(unique=True, index=True, max_length=255)
    campaigner_id: int = Field(foreign_key="campaigners.id", index=True)
    customer_id: Optional[int] = Field(default=None, foreign_key="customers.id", index=True)

    # Langfuse integration
    langfuse_trace_id: Optional[str] = Field(default=None, max_length=255)
    langfuse_trace_url: Optional[str] = Field(default=None)

    # Conversation metadata
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = Field(default=None)
    status: str = Field(default="active", max_length=50, index=True)  # active, completed, abandoned, error

    # Intent/Goal tracking (stored as JSON)
    intent: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    needs_clarification: bool = Field(default=True)
    ready_for_analysis: bool = Field(default=False)

    # Metrics
    message_count: int = Field(default=0)
    agent_step_count: int = Field(default=0)
    tool_usage_count: int = Field(default=0)
    total_tokens: int = Field(default=0)
    duration_seconds: Optional[float] = Field(default=None)

    # Extra metadata (stored as JSON)
    extra_metadata: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))

    # Relationships
    messages: List["Message"] = Relationship(back_populates="conversation", sa_relationship_kwargs={"cascade": "all, delete-orphan"})
    agent_steps: List["AgentStep"] = Relationship(back_populates="conversation", sa_relationship_kwargs={"cascade": "all, delete-orphan"})
    tool_usages: List["ToolUsage"] = Relationship(back_populates="conversation", sa_relationship_kwargs={"cascade": "all, delete-orphan"})

    __table_args__ = (
        Index('idx_conversations_thread_id', 'thread_id'),
        Index('idx_conversations_campaigner_id', 'campaigner_id'),
        Index('idx_conversations_customer_id', 'customer_id'),
        Index('idx_conversations_status', 'status'),
        Index('idx_conversations_started_at', 'started_at'),
    )


class Message(BaseModel, table=True):
    """Individual message in a conversation."""

    __tablename__ = "messages"

    # Primary key inherited from BaseModel (id)
    conversation_id: int = Field(foreign_key="conversations.id", index=True)

    # Message content
    role: str = Field(max_length=50, index=True)  # user, assistant, system, tool
    content: str = Field()

    # Langfuse integration
    langfuse_generation_id: Optional[str] = Field(default=None, max_length=255)

    # Message metadata
    model: Optional[str] = Field(default=None, max_length=100)
    tokens_used: Optional[int] = Field(default=None)
    latency_ms: Optional[int] = Field(default=None)

    # Additional data (stored as JSON)
    extra_metadata: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))

    # Relationship
    conversation: Optional["Conversation"] = Relationship(back_populates="messages")

    __table_args__ = (
        Index('idx_messages_conversation_id', 'conversation_id'),
        Index('idx_messages_created_at', 'created_at'),
        Index('idx_messages_role', 'role'),
    )


class AgentStep(BaseModel, table=True):
    """Agent reasoning step (for CrewAI and other agents)."""

    __tablename__ = "agent_steps"

    # Primary key inherited from BaseModel (id)
    conversation_id: int = Field(foreign_key="conversations.id", index=True)

    # Step details
    step_type: str = Field(max_length=100, index=True)  # thought, action, observation, task_start, task_complete
    agent_name: Optional[str] = Field(default=None, max_length=255)
    agent_role: Optional[str] = Field(default=None, max_length=255)
    content: str = Field()

    # Task tracking (for CrewAI)
    task_index: Optional[int] = Field(default=None)
    task_description: Optional[str] = Field(default=None)

    # Langfuse integration
    langfuse_span_id: Optional[str] = Field(default=None, max_length=255)

    # Extra metadata (stored as JSON)
    extra_metadata: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))

    # Relationship
    conversation: Optional["Conversation"] = Relationship(back_populates="agent_steps")
    tool_usages: List["ToolUsage"] = Relationship(back_populates="agent_step")

    __table_args__ = (
        Index('idx_agent_steps_conversation_id', 'conversation_id'),
        Index('idx_agent_steps_step_type', 'step_type'),
        Index('idx_agent_steps_created_at', 'created_at'),
    )


class ToolUsage(BaseModel, table=True):
    """Tool/function call tracking."""

    __tablename__ = "tool_usages"

    # Primary key inherited from BaseModel (id)
    conversation_id: int = Field(foreign_key="conversations.id", index=True)
    agent_step_id: Optional[int] = Field(default=None, foreign_key="agent_steps.id")

    # Tool details
    tool_name: str = Field(max_length=255, index=True)
    tool_input: Optional[str] = Field(default=None)
    tool_output: Optional[str] = Field(default=None)
    success: bool = Field(default=True, index=True)
    error: Optional[str] = Field(default=None)

    # Performance
    latency_ms: Optional[int] = Field(default=None)

    # Langfuse integration
    langfuse_span_id: Optional[str] = Field(default=None, max_length=255)

    # Extra metadata (stored as JSON)
    extra_metadata: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))

    # Relationships
    conversation: Optional["Conversation"] = Relationship(back_populates="tool_usages")
    agent_step: Optional["AgentStep"] = Relationship(back_populates="tool_usages")

    __table_args__ = (
        Index('idx_tool_usages_conversation_id', 'conversation_id'),
        Index('idx_tool_usages_tool_name', 'tool_name'),
        Index('idx_tool_usages_success', 'success'),
        Index('idx_tool_usages_created_at', 'created_at'),
    )
