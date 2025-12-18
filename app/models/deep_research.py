"""
Deep Research database models.

Stores research sessions, steps, and sources for comprehensive research feature.
"""

from datetime import datetime
from typing import Optional, Dict, Any
from sqlmodel import SQLModel, Field, Column, Index
from sqlalchemy import Text, ForeignKey
from sqlalchemy.dialects import postgresql
from .base import BaseModel
from .chat_traces import get_json_column_type


class ResearchSession(BaseModel, table=True):
    """
    Main research session record.

    Tracks a complete deep research session from query to final report.
    """
    __tablename__ = "research_sessions"

    # Core identification
    session_id: str = Field(unique=True, index=True, max_length=255)
    thread_id: Optional[str] = Field(default=None, index=True, max_length=255)

    # Ownership
    campaigner_id: int = Field(foreign_key="campaigners.id", index=True)
    customer_id: Optional[int] = Field(default=None, foreign_key="customers.id")

    # Request
    query: str = Field(sa_column=Column(Text))
    status: str = Field(default="pending", index=True, max_length=50)  # pending, running, completed, error, cancelled

    # Configuration (JSONB)
    config: Dict[str, Any] = Field(default={}, sa_column=Column(get_json_column_type()))

    # Results
    final_report: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    intermediate_artifacts: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(get_json_column_type(), nullable=True))

    # Tracing
    langfuse_trace_id: Optional[str] = Field(default=None, max_length=255)
    langfuse_trace_url: Optional[str] = Field(default=None, max_length=1024)

    # Metrics
    total_execution_time_ms: Optional[int] = Field(default=None)
    tokens_used: Optional[int] = Field(default=None)
    api_calls_made: Optional[int] = Field(default=None)

    # Timestamps inherited from BaseModel: created_at, updated_at


class ResearchStep(BaseModel, table=True):
    """
    Individual research steps within a session.

    Tracks each phase of the research process (planning, search, compression, synthesis, report).
    """
    __tablename__ = "research_steps"

    # Core identification
    research_session_id: int = Field(foreign_key="research_sessions.id", index=True)

    # Step details
    step_type: str = Field(max_length=50)  # planning, search, compression, synthesis, report
    step_index: int = Field(default=0)  # Order within session
    status: str = Field(default="pending", max_length=50)  # pending, running, completed, error

    # Step data (JSONB)
    input_data: Dict[str, Any] = Field(default={}, sa_column=Column(get_json_column_type()))
    output_data: Dict[str, Any] = Field(default={}, sa_column=Column(get_json_column_type()))

    # Error handling
    error_message: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))

    # Metrics
    execution_time_ms: Optional[int] = Field(default=None)
    tokens_used: Optional[int] = Field(default=None)

    # Tracing
    langfuse_span_id: Optional[str] = Field(default=None, max_length=255)

    # Timestamps inherited from BaseModel: created_at, updated_at


class ResearchSource(BaseModel, table=True):
    """
    Sources discovered and used during research.

    Tracks web sources, their relevance, and which step discovered them.
    """
    __tablename__ = "research_sources"

    # Core identification
    research_session_id: int = Field(foreign_key="research_sessions.id", index=True)
    research_step_id: Optional[int] = Field(default=None, foreign_key="research_steps.id")

    # Source details
    url: str = Field(max_length=2048)
    title: Optional[str] = Field(default=None, max_length=1024)
    content_summary: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    relevance_score: Optional[float] = Field(default=None)
    search_query: Optional[str] = Field(default=None, max_length=1024)

    # Metadata (JSONB) - renamed to avoid SQLAlchemy reserved name
    source_metadata: Dict[str, Any] = Field(default={}, sa_column=Column("metadata", get_json_column_type()))

    # Only created_at timestamp needed (sources don't update)
    # updated_at inherited from BaseModel but not used
