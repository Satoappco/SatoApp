"""
Single-table chat trace model with JSON schemas for different record types.

This consolidates conversations, messages, agent_steps, tool_usages, and customer_logs
into a single flexible table using the event sourcing pattern.
"""

from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum
from sqlmodel import SQLModel, Field, Column
from sqlalchemy import Index, JSON, Text
from sqlalchemy.dialects import postgresql
from .base import BaseModel


def get_json_column_type():
    """Get the appropriate JSON column type based on the database.

    Returns JSONB for PostgreSQL (better performance and indexing)
    and JSON for other databases like SQLite.
    """
    import os
    # Check both DATABASE_URL and TEST_DATABASE_URL
    database_url = os.getenv("DATABASE_URL", "") or os.getenv("TEST_DATABASE_URL", "")

    # Use JSONB for PostgreSQL, JSON for everything else (including SQLite)
    # Check for both postgres:// and postgresql:// schemes
    if "postgres" in database_url.lower():
        return postgresql.JSONB(astext_type=Text())
    else:
        return JSON()


def is_using_postgresql():
    """Check if we're using PostgreSQL database."""
    import os
    database_url = os.getenv("DATABASE_URL", "") or os.getenv("TEST_DATABASE_URL", "")
    return "postgres" in database_url.lower()


class RecordType(str, Enum):
    """Types of records stored in chat_traces table."""
    CONVERSATION = "conversation"      # Conversation metadata and state
    MESSAGE = "message"                # User/assistant messages
    AGENT_STEP = "agent_step"          # Agent reasoning steps
    TOOL_USAGE = "tool_usage"          # Tool/function calls
    CREWAI_EXECUTION = "crewai_execution"  # CrewAI analysis results


class ChatTrace(BaseModel, table=True):
    """
    Single table for all chat trace records.

    Uses event sourcing pattern where each record represents an event in the conversation.
    The 'data' JSON field contains type-specific information based on 'record_type'.

    JSON Schemas by record_type:

    CONVERSATION:
      {
        "status": "active|completed|error",
        "started_at": "ISO datetime",
        "completed_at": "ISO datetime",
        "intent": {"platforms": [], "metrics": [], ...},
        "needs_clarification": bool,
        "ready_for_analysis": bool,
        "message_count": int,
        "agent_step_count": int,
        "tool_usage_count": int,
        "total_tokens": int,
        "duration_seconds": float
      }

    MESSAGE:
      {
        "role": "user|assistant|system|tool",
        "content": "message text",
        "model": "gpt-4",
        "tokens_used": int,
        "latency_ms": int
      }

    AGENT_STEP:
      {
        "step_type": "thought|action|observation|task_start|task_complete",
        "agent_name": "...",
        "agent_role": "...",
        "content": "...",
        "task_index": int,
        "task_description": "..."
      }

    TOOL_USAGE:
      {
        "tool_name": "...",
        "tool_input": "...",
        "tool_output": "...",
        "success": bool,
        "error": "...",
        "latency_ms": int,
        "agent_step_id": int
      }

    CREWAI_EXECUTION:
      {
        "user_intent": "Insight only/Campaigns Opt/...",
        "original_query": "...",
        "crewai_input_prompt": "...",
        "master_answer": "...",
        "crewai_log": "...",
        "total_execution_time_ms": int,
        "timing_breakdown": {...},
        "agents_used": [...],
        "tools_used": [...],
        "success": bool,
        "error_message": "...",
        "analysis_id": "..."
      }
    """

    __tablename__ = "chat_traces"

    # Core identification
    thread_id: str = Field(index=True, max_length=255, description="Conversation thread identifier")
    record_type: str = Field(index=True, max_length=50, description="Type of record (conversation, message, etc.)")

    # Ownership
    campaigner_id: int = Field(foreign_key="campaigners.id", index=True)
    customer_id: Optional[int] = Field(default=None, foreign_key="customers.id", index=True)

    data: Dict[str, Any] = Field(
        sa_column=Column(
            get_json_column_type(),
            nullable=False
        ),
        description="Type-specific data based on record_type",
    )

    # Langfuse integration
    langfuse_trace_id: Optional[str] = Field(default=None, max_length=255, description="Langfuse trace ID (for conversation records)")
    langfuse_trace_url: Optional[str] = Field(default=None, description="Langfuse trace URL")
    langfuse_span_id: Optional[str] = Field(default=None, max_length=255, description="Langfuse span ID (for steps/tools)")

    # Session tracking (for grouping)
    session_id: Optional[str] = Field(default=None, max_length=255, index=True, description="Session ID for batch operations")

    # Sorting/ordering within thread
    sequence_number: Optional[int] = Field(default=None, description="Order within thread for messages/steps")

    # Indexes for efficient queries
    # Build indexes list - conditionally add GIN index for PostgreSQL only
    _indexes = [
        Index('idx_chat_traces_thread_id', 'thread_id'),
        Index('idx_chat_traces_record_type', 'record_type'),
        Index('idx_chat_traces_campaigner_id', 'campaigner_id'),
        Index('idx_chat_traces_customer_id', 'customer_id'),
        Index('idx_chat_traces_session_id', 'session_id'),
        Index('idx_chat_traces_created_at', 'created_at'),
        Index('idx_chat_traces_thread_record', 'thread_id', 'record_type'),  # Composite for filtering
    ]

    # Only add GIN index when using PostgreSQL (JSONB)
    if is_using_postgresql():
        _indexes.append(
            # GIN index for JSONB data field (allows efficient querying of JSON fields)
            Index('idx_chat_traces_data_gin', 'data', postgresql_using='gin')
        )

    __table_args__ = tuple(_indexes)

    # Convenience properties for accessing common fields in data JSON
    # These provide backwards compatibility and better developer experience

    @property
    def status(self) -> Optional[str]:
        """Get conversation status from data field."""
        if self.record_type == RecordType.CONVERSATION:
            return self.data.get('status')
        return None

    @property
    def message_count(self) -> Optional[int]:
        """Get message count from data field."""
        if self.record_type == RecordType.CONVERSATION:
            return self.data.get('message_count', 0)
        return None

    @property
    def agent_step_count(self) -> Optional[int]:
        """Get agent step count from data field."""
        if self.record_type == RecordType.CONVERSATION:
            return self.data.get('agent_step_count', 0)
        return None

    @property
    def tool_usage_count(self) -> Optional[int]:
        """Get tool usage count from data field."""
        if self.record_type == RecordType.CONVERSATION:
            return self.data.get('tool_usage_count', 0)
        return None

    @property
    def total_tokens(self) -> Optional[int]:
        """Get total tokens from data field."""
        if self.record_type == RecordType.CONVERSATION:
            return self.data.get('total_tokens', 0)
        return None

    @property
    def intent(self) -> Optional[Dict[str, Any]]:
        """Get intent from data field."""
        if self.record_type == RecordType.CONVERSATION:
            return self.data.get('intent')
        return None

    @property
    def needs_clarification(self) -> Optional[bool]:
        """Get needs_clarification from data field."""
        if self.record_type == RecordType.CONVERSATION:
            return self.data.get('needs_clarification')
        return None

    @property
    def ready_for_analysis(self) -> Optional[bool]:
        """Get ready_for_analysis from data field."""
        if self.record_type == RecordType.CONVERSATION:
            return self.data.get('ready_for_analysis')
        return None

    @property
    def completed_at(self) -> Optional[str]:
        """Get completed_at from data field."""
        if self.record_type == RecordType.CONVERSATION:
            return self.data.get('completed_at')
        return None

    @property
    def duration_seconds(self) -> Optional[float]:
        """Get duration_seconds from data field."""
        if self.record_type == RecordType.CONVERSATION:
            return self.data.get('duration_seconds')
        return None

    @property
    def extra_metadata(self) -> Optional[Dict[str, Any]]:
        """Get extra_metadata from data field."""
        return self.data.get('extra_metadata')

    # MESSAGE properties
    @property
    def role(self) -> Optional[str]:
        """Get message role from data field."""
        if self.record_type == RecordType.MESSAGE:
            return self.data.get('role')
        return None

    @property
    def content(self) -> Optional[str]:
        """Get content from data field."""
        if self.record_type in [RecordType.MESSAGE, RecordType.AGENT_STEP]:
            return self.data.get('content')
        return None

    @property
    def model(self) -> Optional[str]:
        """Get model from data field."""
        if self.record_type == RecordType.MESSAGE:
            return self.data.get('model')
        return None

    @property
    def tokens_used(self) -> Optional[int]:
        """Get tokens_used from data field."""
        if self.record_type == RecordType.MESSAGE:
            return self.data.get('tokens_used')
        return None

    # AGENT_STEP properties
    @property
    def step_type(self) -> Optional[str]:
        """Get step_type from data field."""
        if self.record_type == RecordType.AGENT_STEP:
            return self.data.get('step_type')
        return None

    @property
    def agent_name(self) -> Optional[str]:
        """Get agent_name from data field."""
        if self.record_type == RecordType.AGENT_STEP:
            return self.data.get('agent_name')
        return None

    @property
    def agent_role(self) -> Optional[str]:
        """Get agent_role from data field."""
        if self.record_type == RecordType.AGENT_STEP:
            return self.data.get('agent_role')
        return None

    @property
    def task_index(self) -> Optional[int]:
        """Get task_index from data field."""
        if self.record_type == RecordType.AGENT_STEP:
            return self.data.get('task_index')
        return None

    # TOOL_USAGE properties
    @property
    def tool_name(self) -> Optional[str]:
        """Get tool_name from data field."""
        if self.record_type == RecordType.TOOL_USAGE:
            return self.data.get('tool_name')
        return None

    @property
    def tool_input(self) -> Optional[Any]:
        """Get tool_input from data field."""
        if self.record_type == RecordType.TOOL_USAGE:
            return self.data.get('tool_input')
        return None

    @property
    def tool_output(self) -> Optional[Any]:
        """Get tool_output from data field."""
        if self.record_type == RecordType.TOOL_USAGE:
            return self.data.get('tool_output')
        return None

    @property
    def success(self) -> Optional[bool]:
        """Get success from data field."""
        if self.record_type == RecordType.TOOL_USAGE:
            return self.data.get('success')
        return None

    @property
    def error(self) -> Optional[str]:
        """Get error from data field."""
        if self.record_type == RecordType.TOOL_USAGE:
            return self.data.get('error')
        return None

    @property
    def latency_ms(self) -> Optional[int]:
        """Get latency_ms from data field."""
        if self.record_type in [RecordType.MESSAGE, RecordType.TOOL_USAGE]:
            return self.data.get('latency_ms')
        return None

    @property
    def conversation_id(self) -> Optional[int]:
        """Get conversation ID for MESSAGE, AGENT_STEP, or TOOL_USAGE records.

        Returns the ID of the conversation (CONVERSATION record) that this record belongs to.
        For CONVERSATION records themselves, returns their own ID.
        """
        if self.record_type == RecordType.CONVERSATION:
            return self.id
        # For MESSAGE, AGENT_STEP, TOOL_USAGE - return conversation_id from data if set
        # (The service should populate this when creating child records)
        return self.data.get('conversation_id')
