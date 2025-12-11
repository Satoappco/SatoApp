"""API request/response models."""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, field_validator
from datetime import datetime


# ===== Chat/Conversation Models =====

class Message(BaseModel):
    """Chat message."""
    role: str = Field(..., description="Message role: 'user' or 'assistant'")
    content: str = Field(..., description="Message content")


class ChatRequest(BaseModel):
    """Chat request."""
    message: str = Field(..., description="User message", min_length=0)
    thread_id: Optional[str] = Field(None, description="Conversation thread ID")
    customer_id: Optional[int] = Field(None, description="Customer ID associated with the conversation")
    use_crew: Optional[bool] = Field(False, description="Whether to use the crew for processing")

    @field_validator('customer_id', mode='before')
    @classmethod
    def coerce_customer_id(cls, v):
        """Convert string customer_id to int if needed."""
        if v is None or v == '':
            return None
        if isinstance(v, str):
            try:
                return int(v)
            except ValueError:
                raise ValueError(f"customer_id must be an integer, got: {v}")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "message": "Show me Facebook Ads performance for last month",
                "thread_id": "user-123",
            }
        }


class ChatResponse(BaseModel):
    """Chat response."""
    message: str = Field(..., description="Assistant's response")
    thread_id: str = Field(..., description="Conversation thread ID")
    needs_clarification: bool = Field(..., description="Whether user clarification is needed")
    ready_for_analysis: bool = Field(..., description="Whether ready to run analytics")
    intent: Optional[Dict[str, Any]] = Field(None, description="Extracted user intent")
    user_message_id: Optional[int] = Field(None, description="ID of the user message in chat_traces")
    assistant_message_id: Optional[int] = Field(None, description="ID of the assistant message in chat_traces")

    @field_validator('user_message_id', 'assistant_message_id', mode='before')
    @classmethod
    def coerce_message_ids(cls, v):
        """Convert string message IDs to int if needed."""
        if v is None or v == '':
            return None
        if isinstance(v, str):
            try:
                return int(v)
            except ValueError:
                raise ValueError(f"message_id must be an integer, got: {v}")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "message": "I'll analyze Facebook Ads for last month. What metrics would you like to see?",
                "thread_id": "user-123",
                "needs_clarification": True,
                "ready_for_analysis": False,
                "intent": {
                    "platforms": ["facebook"],
                    "date_range_start": "2025-09-01",
                    "date_range_end": "2025-09-30"
                },
                "user_message_id": 123,
                "assistant_message_id": 124
            }
        }


# ===== Analytics Models =====

class AnalyticsRequest(BaseModel):
    """Analytics request."""
    platforms: List[str] = Field(..., description="Platforms to analyze: 'facebook', 'google'")
    metrics: List[str] = Field(..., description="Metrics to retrieve")
    date_range_start: str = Field(..., description="Start date (YYYY-MM-DD)")
    date_range_end: str = Field(..., description="End date (YYYY-MM-DD)")
    comparison_period: bool = Field(False, description="Compare with previous period")
    specific_campaigns: Optional[List[str]] = Field(None, description="Specific campaign IDs")
    thread_id: Optional[str] = Field(None, description="Associated conversation thread")

    class Config:
        json_schema_extra = {
            "example": {
                "platforms": ["facebook", "google"],
                "metrics": ["traffic", "conversions", "ad_spend"],
                "date_range_start": "2025-09-01",
                "date_range_end": "2025-09-30",
                "comparison_period": True,
                "specific_campaigns": ["campaign_123"]
            }
        }


class InsightModel(BaseModel):
    """Analytics insight."""
    title: str
    description: str
    severity: str = Field(default="info", description="info, warning, critical, positive")
    related_metrics: List[str] = Field(default_factory=list)
    recommendation: Optional[str] = None
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)


class AnalyticsResponse(BaseModel):
    """Analytics response."""
    success: bool
    platforms: List[str]
    summary: str = Field(..., description="Executive summary")
    insights: List[InsightModel] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    data: Optional[Dict[str, Any]] = Field(None, description="Raw analytics data")
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    thread_id: Optional[str] = None
    error: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "platforms": ["facebook", "google"],
                "summary": "Overall performance improved by 15% compared to previous period.",
                "insights": [
                    {
                        "title": "Traffic Spike",
                        "description": "30% increase in organic traffic",
                        "severity": "positive",
                        "related_metrics": ["traffic", "sessions"],
                        "confidence": 0.9
                    }
                ],
                "recommendations": [
                    "Increase budget for top-performing campaigns",
                    "Test new audience segments"
                ],
                "generated_at": "2025-10-19T22:00:00Z"
            }
        }


# ===== Conversation State Models =====

class ConversationThread(BaseModel):
    """Conversation thread info."""
    thread_id: str
    created_at: datetime
    last_message_at: datetime
    message_count: int
    intent_complete: bool
    platforms: List[str] = Field(default_factory=list)

    class Config:
        json_schema_extra = {
            "example": {
                "thread_id": "user-123",
                "created_at": "2025-10-19T20:00:00Z",
                "last_message_at": "2025-10-19T20:05:00Z",
                "message_count": 4,
                "intent_complete": True,
                "platforms": ["facebook"]
            }
        }


class ThreadListResponse(BaseModel):
    """List of conversation threads."""
    threads: List[ConversationThread]
    total: int


# ===== Health & Info Models =====

class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    services: Dict[str, str] = Field(default_factory=dict)

    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "version": "0.1.0",
                "timestamp": "2025-10-19T22:00:00Z",
                "services": {
                    "langgraph": "ok",
                    "crewai": "ok",
                    "llm": "ok"
                }
            }
        }


class InfoResponse(BaseModel):
    """API information."""
    name: str = "Sato Marketing Analytics API"
    version: str = "0.1.0"
    description: str = "AI-powered marketing analytics combining LangGraph and CrewAI"
    features: List[str] = Field(default_factory=list)
    supported_platforms: List[str] = Field(default_factory=lambda: ["facebook", "google"])
    supported_metrics: List[str] = Field(default_factory=lambda: [
        "traffic", "conversions", "ad_spend", "roi", "engagement", "demographics"
    ])
