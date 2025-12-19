"""
Customer Analysis API Schemas.

Request and response models for customer analysis endpoints.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


# Analysis Settings Schemas

class AnalysisSettingsUpdate(BaseModel):
    """Schema for updating analysis settings."""
    auto_analysis_on_create: Optional[bool] = None
    auto_weekly_reviews: Optional[bool] = None
    auto_quarterly_reanalysis: Optional[bool] = None
    notification_emails: Optional[List[str]] = None
    notify_on_analysis_complete: Optional[bool] = None
    notify_on_weekly_review: Optional[bool] = None
    notify_on_quarterly_reanalysis: Optional[bool] = None
    weekly_review_day: Optional[str] = Field(None, pattern="^(monday|tuesday|wednesday|thursday|friday|saturday|sunday)$")
    weekly_review_time: Optional[str] = Field(None, pattern="^([0-1][0-9]|2[0-3]):[0-5][0-9]$")
    preferred_analysis_model: Optional[str] = None
    preferred_summarization_model: Optional[str] = None
    default_research_depth: Optional[str] = Field(None, pattern="^(shallow|medium|deep)$")


class AnalysisSettingsResponse(BaseModel):
    """Schema for analysis settings response."""
    campaigner_id: int
    auto_analysis_on_create: bool
    auto_weekly_reviews: bool
    auto_quarterly_reanalysis: bool
    notification_emails: List[str]
    notify_on_analysis_complete: bool
    notify_on_weekly_review: bool
    notify_on_quarterly_reanalysis: bool
    weekly_review_day: str
    weekly_review_time: str
    preferred_analysis_model: Optional[str]
    preferred_summarization_model: Optional[str]
    default_research_depth: str
    created_at: datetime
    updated_at: datetime


# Customer Analysis Schemas

class AnalysisRequest(BaseModel):
    """Schema for requesting a customer analysis."""
    customer_id: Optional[int] = Field(None, description="Customer ID for customer-specific analysis")
    analysis_type: str = Field(
        default="initial",
        pattern="^(initial|quarterly|manual)$",
        description="Type of analysis: initial, quarterly, or manual"
    )
    thread_id: Optional[str] = Field(None, description="Optional chat thread ID for tracing")
    custom_config: Optional[Dict[str, Any]] = Field(None, description="Optional custom configuration")


class AnalysisResponse(BaseModel):
    """Schema for analysis response."""
    success: bool
    session_id: str
    status: str
    execution_time_ms: Optional[int] = None
    tokens_used: Optional[int] = None
    api_calls_made: Optional[int] = None
    error: Optional[str] = None


class AnalysisSessionListItem(BaseModel):
    """Schema for analysis session list item."""
    session_id: str
    customer_id: Optional[int]
    analysis_type: str
    trigger_source: str
    status: str
    created_at: datetime
    completed_at: Optional[datetime]
    execution_time_ms: Optional[int]


class AnalysisSessionList(BaseModel):
    """Schema for list of analysis sessions."""
    sessions: List[AnalysisSessionListItem]
    total: int
    limit: int
    offset: int


class ClientBriefSection(BaseModel):
    """Schema for client brief section."""
    company_name: str
    industry: Optional[str] = None
    target_audience: Optional[str] = None
    unique_value_proposition: Optional[str] = None
    business_goals: Optional[List[str]] = None
    key_challenges: Optional[List[str]] = None


class WebsiteAnalysisSection(BaseModel):
    """Schema for website analysis section."""
    url: Optional[str] = None
    key_pages: List[Dict[str, str]] = []
    products_services: List[str] = []
    user_experience_notes: Optional[str] = None
    technical_seo_score: Optional[float] = None


class MarketResearchSection(BaseModel):
    """Schema for market research section."""
    competitors: List[Dict[str, Any]] = []
    market_size: Optional[str] = None
    trends: List[str] = []
    opportunities: List[str] = []
    threats: List[str] = []


class CampaignAnalysisSection(BaseModel):
    """Schema for campaign analysis section."""
    active_campaigns: List[Dict[str, Any]] = []
    performance_summary: Dict[str, Any] = {}
    key_metrics: Dict[str, float] = {}
    recommendations: List[str] = []


class RecommendationsSection(BaseModel):
    """Schema for recommendations section."""
    strategic: List[Dict[str, str]] = []
    tactical: List[Dict[str, str]] = []
    priority_actions: List[Dict[str, str]] = []


class WorkPlanSection(BaseModel):
    """Schema for work plan section."""
    period_weeks: int
    tasks_by_week: Dict[str, List[Dict[str, Any]]]


class AnalysisSessionDetail(BaseModel):
    """Schema for detailed analysis session."""
    session_id: str
    campaigner_id: int
    customer_id: Optional[int]
    analysis_type: str
    trigger_source: str
    status: str
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime]

    # Phase results
    client_brief: Optional[ClientBriefSection] = None
    website_analysis: Optional[WebsiteAnalysisSection] = None
    market_research: Optional[MarketResearchSection] = None
    campaign_analysis: Optional[CampaignAnalysisSection] = None
    recommendations: Optional[RecommendationsSection] = None
    work_plan: Optional[WorkPlanSection] = None

    # Full report
    full_report_markdown: Optional[str] = None

    # Metrics
    total_execution_time_ms: Optional[int] = None
    tokens_used: Optional[int] = None
    api_calls_made: Optional[int] = None

    # Tracing
    langfuse_trace_url: Optional[str] = None


# Work Plan Schemas

class WorkPlanSummary(BaseModel):
    """Schema for work plan summary."""
    plan_id: str
    status: str
    plan_period_weeks: int
    current_week: int
    total_tasks: int
    completed_tasks: int
    blocked_tasks: int
    in_progress_tasks: int
    progress_percent: float
    overall_health_score: Optional[float] = None
    created_at: datetime
    updated_at: datetime


class WorkPlanTaskDetail(BaseModel):
    """Schema for work plan task detail."""
    task_id: str
    week_number: int
    category: str
    title: str
    description: str
    priority: str
    impact: str
    effort: str
    status: str
    dependencies: List[str]
    review_notes: List[Dict[str, Any]]
    expected_impact_description: Optional[str] = None
    actual_impact_notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class WorkPlanTaskUpdate(BaseModel):
    """Schema for updating a work plan task."""
    status: str = Field(pattern="^(pending|in_progress|completed|blocked)$")
    note: Optional[str] = None


class WorkPlanTaskList(BaseModel):
    """Schema for list of work plan tasks."""
    tasks: List[WorkPlanTaskDetail]
    total: int


# Weekly Review Schemas

class WeeklyReviewSummary(BaseModel):
    """Schema for weekly review summary."""
    review_id: str
    week_number: int
    status: str
    overall_health_score: float
    progress_velocity: Optional[float] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    acknowledged_at: Optional[datetime] = None


class WeeklyReviewDetail(BaseModel):
    """Schema for detailed weekly review."""
    review_id: str
    analysis_session_id: int
    work_plan_id: int
    week_number: int
    status: str

    # Metrics
    metrics_snapshot: Dict[str, Any]

    # Review content
    achievements: List[str]
    blockers: List[Dict[str, Any]]
    risks: List[Dict[str, Any]]
    opportunities: List[Dict[str, Any]]

    # Recommendations
    new_recommendations: List[Dict[str, Any]]
    task_adjustments: List[Dict[str, Any]]

    # Scoring
    overall_health_score: float
    progress_velocity: Optional[float] = None

    # Full report
    full_review_markdown: Optional[str] = None

    # Timing
    execution_time_ms: Optional[int] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    acknowledged_at: Optional[datetime] = None


class WeeklyReviewList(BaseModel):
    """Schema for list of weekly reviews."""
    reviews: List[WeeklyReviewSummary]
    total: int


# Error Schemas

class ErrorResponse(BaseModel):
    """Schema for error responses."""
    error: str
    detail: Optional[str] = None
    session_id: Optional[str] = None
