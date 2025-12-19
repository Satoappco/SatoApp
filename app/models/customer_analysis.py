"""
Customer Analysis database models.

This module defines the database schema for the comprehensive customer analysis system,
including analysis sessions, work plans, weekly reviews, and automation settings.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlmodel import SQLModel, Field, Column, Relationship, JSON
from sqlalchemy import Text, Index


class CustomerAnalysisSession(SQLModel, table=True):
    """
    Main customer analysis session record.

    Tracks the execution of a complete customer analysis including client brief,
    website research, market research, campaign analysis, and recommendations.
    """
    __tablename__ = "customer_analysis_sessions"

    # Primary identification
    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: str = Field(unique=True, index=True, max_length=255)
    campaigner_id: int = Field(foreign_key="campaigners.id", index=True)
    customer_id: Optional[int] = Field(default=None, foreign_key="customers.id", index=True)

    # Analysis metadata
    analysis_type: str = Field(max_length=50)  # initial, quarterly, manual
    trigger_source: str = Field(max_length=50)  # auto_onboarding, scheduled, manual
    status: str = Field(default="pending", max_length=50, index=True)  # pending, running, completed, error

    # Scheduling and automation
    next_quarterly_analysis_at: Optional[datetime] = None
    next_weekly_review_at: Optional[datetime] = None

    # Phase results (JSON stored)
    client_brief_json: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    website_analysis_json: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    market_research_json: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    campaign_analysis_json: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    recommendations_json: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    work_plan_json: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))

    # Full report
    full_report_markdown: Optional[str] = Field(default=None, sa_column=Column(Text))

    # Comparison and progress tracking
    previous_session_id: Optional[str] = Field(default=None, max_length=255)
    progress_since_last_analysis: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))

    # Execution metrics
    total_execution_time_ms: Optional[int] = None
    tokens_used: Optional[int] = None
    api_calls_made: Optional[int] = None

    # Tracing
    langfuse_trace_id: Optional[str] = Field(default=None, max_length=255)
    langfuse_trace_url: Optional[str] = Field(default=None, max_length=512)

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None

    # Relationships
    work_plan: Optional["WorkPlan"] = Relationship(back_populates="analysis_session")
    weekly_reviews: List["WeeklyReview"] = Relationship(back_populates="analysis_session")
    phase_results: List["AnalysisPhaseResult"] = Relationship(back_populates="analysis_session")
    sources: List["AnalysisSource"] = Relationship(back_populates="analysis_session")


class WorkPlan(SQLModel, table=True):
    """
    Work plan generated from customer analysis.

    Contains structured tasks organized by week with dependencies, priorities, and tracking.
    """
    __tablename__ = "work_plans"

    # Primary identification
    id: Optional[int] = Field(default=None, primary_key=True)
    plan_id: str = Field(unique=True, index=True, max_length=255)
    analysis_session_id: int = Field(foreign_key="customer_analysis_sessions.id", index=True)
    campaigner_id: int = Field(foreign_key="campaigners.id", index=True)

    # Plan metadata
    status: str = Field(default="active", max_length=50)  # active, completed, archived
    plan_period_weeks: int = Field(default=8)
    current_week: int = Field(default=1)

    # Progress tracking
    total_tasks: int = Field(default=0)
    completed_tasks: int = Field(default=0)
    blocked_tasks: int = Field(default=0)
    in_progress_tasks: int = Field(default=0)
    progress_percent: float = Field(default=0.0)

    # Health scoring
    overall_health_score: Optional[float] = None  # 0-100

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    archived_at: Optional[datetime] = None

    # Relationships
    analysis_session: Optional["CustomerAnalysisSession"] = Relationship(back_populates="work_plan")
    tasks: List["WorkPlanTask"] = Relationship(back_populates="work_plan")


class WorkPlanTask(SQLModel, table=True):
    """
    Individual task within a work plan.

    Tasks are organized by week, have priorities and dependencies, and track progress.
    """
    __tablename__ = "work_plan_tasks"

    # Primary identification
    id: Optional[int] = Field(default=None, primary_key=True)
    task_id: str = Field(unique=True, index=True, max_length=255)
    work_plan_id: int = Field(foreign_key="work_plans.id", index=True)

    # Task organization
    week_number: int = Field(index=True)
    category: str = Field(max_length=100)  # campaign_optimization, content_creation, technical_seo, etc.

    # Task details
    title: str = Field(max_length=255)
    description: str = Field(sa_column=Column(Text))

    # Priority and impact
    priority: str = Field(max_length=20)  # high, medium, low
    impact: str = Field(max_length=20)  # high, medium, low
    effort: str = Field(max_length=20)  # high, medium, low

    # Status tracking
    status: str = Field(default="pending", max_length=50, index=True)  # pending, in_progress, completed, blocked

    # Dependencies and relationships
    dependencies: List[str] = Field(default_factory=list, sa_column=Column(JSON))  # List of task_ids

    # Progress notes
    review_notes: List[Dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))

    # Metrics
    expected_impact_description: Optional[str] = Field(default=None, sa_column=Column(Text))
    actual_impact_notes: Optional[str] = Field(default=None, sa_column=Column(Text))

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # Relationships
    work_plan: Optional["WorkPlan"] = Relationship(back_populates="tasks")


class WeeklyReview(SQLModel, table=True):
    """
    Weekly review of work plan progress.

    Automatically generated every Monday to track achievements, blockers, and adjustments.
    """
    __tablename__ = "weekly_reviews"

    # Primary identification
    id: Optional[int] = Field(default=None, primary_key=True)
    review_id: str = Field(unique=True, index=True, max_length=255)
    analysis_session_id: int = Field(foreign_key="customer_analysis_sessions.id", index=True)
    work_plan_id: int = Field(foreign_key="work_plans.id", index=True)
    campaigner_id: int = Field(foreign_key="campaigners.id", index=True)

    # Review metadata
    week_number: int = Field(index=True)
    status: str = Field(default="pending", max_length=50)  # pending, completed, acknowledged

    # Metrics snapshot
    metrics_snapshot: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))

    # Review content
    achievements: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    blockers: List[Dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    risks: List[Dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    opportunities: List[Dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))

    # Recommendations
    new_recommendations: List[Dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    task_adjustments: List[Dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))

    # Health scoring
    overall_health_score: float = Field(default=0.0)  # 0-100
    progress_velocity: Optional[float] = None  # Tasks completed per week

    # Full review report
    full_review_markdown: Optional[str] = Field(default=None, sa_column=Column(Text))

    # Execution metrics
    execution_time_ms: Optional[int] = None
    langfuse_span_id: Optional[str] = Field(default=None, max_length=255)

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    acknowledged_at: Optional[datetime] = None

    # Relationships
    analysis_session: Optional["CustomerAnalysisSession"] = Relationship(back_populates="weekly_reviews")


class AnalysisSettings(SQLModel, table=True):
    """
    Per-campaigner settings for customer analysis automation.

    Controls automatic triggers, notifications, and scheduling preferences.
    """
    __tablename__ = "analysis_settings"

    # Primary identification
    id: Optional[int] = Field(default=None, primary_key=True)
    campaigner_id: int = Field(foreign_key="campaigners.id", unique=True, index=True)

    # Automation flags
    auto_analysis_on_create: bool = Field(default=False)
    auto_weekly_reviews: bool = Field(default=True)
    auto_quarterly_reanalysis: bool = Field(default=True)

    # Notification preferences
    notification_emails: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    notify_on_analysis_complete: bool = Field(default=True)
    notify_on_weekly_review: bool = Field(default=True)
    notify_on_quarterly_reanalysis: bool = Field(default=True)

    # Scheduling preferences
    weekly_review_day: str = Field(default="monday", max_length=20)  # monday, tuesday, etc.
    weekly_review_time: str = Field(default="09:00", max_length=10)  # HH:MM format

    # LLM configuration preferences
    preferred_analysis_model: Optional[str] = Field(default="openai:gpt-4o", max_length=100)
    preferred_summarization_model: Optional[str] = Field(default="openai:gpt-4o-mini", max_length=100)

    # Research depth preferences
    default_research_depth: str = Field(default="medium", max_length=20)  # shallow, medium, deep

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class AnalysisPhaseResult(SQLModel, table=True):
    """
    Individual phase results within a customer analysis session.

    Tracks execution details for each phase: client brief, website research, etc.
    """
    __tablename__ = "analysis_phase_results"

    # Primary identification
    id: Optional[int] = Field(default=None, primary_key=True)
    analysis_session_id: int = Field(foreign_key="customer_analysis_sessions.id", index=True)

    # Phase metadata
    phase_name: str = Field(max_length=100, index=True)  # client_brief, website_research, etc.
    phase_index: int
    status: str = Field(default="pending", max_length=50)  # pending, running, completed, error

    # Phase data
    input_data: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    output_data: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    error_message: Optional[str] = Field(default=None, sa_column=Column(Text))

    # Execution metrics
    execution_time_ms: Optional[int] = None
    tokens_used: Optional[int] = None
    langfuse_span_id: Optional[str] = Field(default=None, max_length=255)

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # Relationships
    analysis_session: Optional["CustomerAnalysisSession"] = Relationship(back_populates="phase_results")


class AnalysisSource(SQLModel, table=True):
    """
    Sources discovered and used during customer analysis.

    Tracks URLs, documents, and data sources used in research phases.
    """
    __tablename__ = "analysis_sources"

    # Primary identification
    id: Optional[int] = Field(default=None, primary_key=True)
    analysis_session_id: int = Field(foreign_key="customer_analysis_sessions.id", index=True)
    phase_result_id: Optional[int] = Field(default=None, foreign_key="analysis_phase_results.id")

    # Source details
    source_type: str = Field(max_length=50)  # website, competitor, document, api, search_result
    url: Optional[str] = Field(default=None, max_length=1024)
    title: Optional[str] = Field(default=None, max_length=512)
    content_summary: Optional[str] = Field(default=None, sa_column=Column(Text))

    # Relevance and source metadata
    relevance_score: Optional[float] = None
    search_query: Optional[str] = Field(default=None, max_length=512)
    source_metadata: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    analysis_session: Optional["CustomerAnalysisSession"] = Relationship(back_populates="sources")


class AnalysisComparison(SQLModel, table=True):
    """
    Comparison between analysis sessions (for quarterly re-analysis).

    Tracks progress and changes between initial and subsequent analyses.
    """
    __tablename__ = "analysis_comparisons"

    # Primary identification
    id: Optional[int] = Field(default=None, primary_key=True)
    current_session_id: int = Field(foreign_key="customer_analysis_sessions.id", index=True)
    previous_session_id: int = Field(foreign_key="customer_analysis_sessions.id")
    campaigner_id: int = Field(foreign_key="campaigners.id", index=True)

    # Comparison metadata
    comparison_type: str = Field(max_length=50)  # quarterly, manual

    # Comparison results
    changes_detected: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    progress_metrics: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    improvement_areas: List[Dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    regression_areas: List[Dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))

    # Summary
    overall_progress_score: Optional[float] = None  # 0-100
    comparison_summary_markdown: Optional[str] = Field(default=None, sa_column=Column(Text))

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)


# Create indexes for performance
Index("idx_analysis_session_campaigner_status",
      CustomerAnalysisSession.campaigner_id, CustomerAnalysisSession.status)
Index("idx_work_plan_campaigner_status",
      WorkPlan.campaigner_id, WorkPlan.status)
Index("idx_work_plan_task_status_week",
      WorkPlanTask.status, WorkPlanTask.week_number)
Index("idx_weekly_review_campaigner_week",
      WeeklyReview.campaigner_id, WeeklyReview.week_number)
