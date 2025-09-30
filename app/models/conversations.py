"""
Conversation and messaging models
"""

from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field
from .base import BaseModel


class ChatMessage(BaseModel, table=True):
    """Chat messages storage"""
    __tablename__ = "chat_messages"
    
    user_name: str = Field(max_length=255)
    message: str = Field()
    session_id: str = Field(max_length=255)
    intent: Optional[str] = Field(default=None, max_length=100)
    confidence: Optional[float] = Field(default=None)
    response: Optional[str] = Field(default=None)
    agent_type: Optional[str] = Field(default=None, max_length=50)
    execution_time: Optional[float] = Field(default=None)
    raw_data: Optional[str] = Field(default=None)  # JSON raw data


class WebhookEntry(BaseModel, table=True):
    """Webhook entries table"""
    __tablename__ = "webhook_entries"
    
    user_name: Optional[str] = Field(default=None, max_length=255)
    user_choice: Optional[str] = Field(default=None, max_length=255)
    raw_payload: str = Field(description="JSON payload as string")


class NarrativeReport(BaseModel, table=True):
    """Generated narrative reports"""
    __tablename__ = "narrative_reports"
    
    user_id: int = Field(foreign_key="users.id")
    report_title: str = Field(max_length=255)
    report_content: str = Field()
    report_type: str = Field(max_length=100)  # seo_analysis, traffic_report, etc.
    data_sources: str = Field()  # JSON array of data sources used
    generated_by_agent: str = Field(max_length=100)
    metrics_included: Optional[str] = Field(default=None)  # JSON array
    date_range_start: Optional[datetime] = Field(default=None)
    date_range_end: Optional[datetime] = Field(default=None)
    is_published: bool = Field(default=False)
