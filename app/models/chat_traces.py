"""
Single-table chat trace model with JSON schemas for different record types.

This consolidates conversations, messages, agent_steps, tool_usages, and customer_logs
into a single flexible table using the event sourcing pattern.
"""

from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum
from sqlmodel import SQLModel, Field, Column
from sqlalchemy import Index
from sqlalchemy.dialects import postgresql
from sqlalchemy import Text
from .base import BaseModel


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
            postgresql.JSONB(astext_type=Text()), 
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
    __table_args__ = (
        Index('idx_chat_traces_thread_id', 'thread_id'),
        Index('idx_chat_traces_record_type', 'record_type'),
        Index('idx_chat_traces_campaigner_id', 'campaigner_id'),
        Index('idx_chat_traces_customer_id', 'customer_id'),
        Index('idx_chat_traces_session_id', 'session_id'),
        Index('idx_chat_traces_created_at', 'created_at'),
        Index('idx_chat_traces_thread_record', 'thread_id', 'record_type'),  # Composite for filtering
        # GIN index for JSONB data field (allows efficient querying of JSON fields)
        Index('idx_chat_traces_data_gin', 'data', postgresql_using='gin'),
    )
