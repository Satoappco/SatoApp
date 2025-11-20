"""
Chat feedback model for storing like/dislike reactions to messages
"""

from datetime import datetime
from typing import Optional
from enum import Enum
from sqlmodel import Field, Index
from .base import BaseModel


class FeedbackType(str, Enum):
    """Type of feedback given by user."""
    LIKE = "like"
    DISLIKE = "dislike"


class ChatFeedback(BaseModel, table=True):
    """
    Stores user feedback (like/dislike) for chat messages.
    Used to collect good/bad examples for model training and validation.
    """

    __tablename__ = "chat_feedback"

    # Reference to the conversation trace
    thread_id: str = Field(index=True, max_length=255, description="Thread ID from chat_traces")

    # Reference to the specific message that was rated
    message_id: int = Field(index=True, description="ID of the message record from chat_traces table")

    # Type of feedback
    feedback_type: str = Field(index=True, max_length=20, description="Type of feedback: like or dislike")

    # Ownership - who gave the feedback
    campaigner_id: int = Field(foreign_key="campaigners.id", index=True)
    customer_id: Optional[int] = Field(default=None, foreign_key="customers.id", index=True)

    # ClickUp task tracking (for dislikes that create validation tasks)
    clickup_task_id: Optional[str] = Field(default=None, max_length=255, description="ClickUp task ID if notification was created")
    clickup_task_url: Optional[str] = Field(default=None, description="ClickUp task URL")

    # Track if notification was sent
    notification_sent: bool = Field(default=False, description="Whether ClickUp notification was sent")
    notification_error: Optional[str] = Field(default=None, description="Error message if notification failed")

    __table_args__ = (
        Index('idx_chat_feedback_thread_id', 'thread_id'),
        Index('idx_chat_feedback_message_id', 'message_id'),
        Index('idx_chat_feedback_type', 'feedback_type'),
        Index('idx_chat_feedback_campaigner_id', 'campaigner_id'),
        Index('idx_chat_feedback_customer_id', 'customer_id'),
        Index('idx_chat_feedback_created_at', 'created_at'),
        # Unique constraint to prevent duplicate feedback on same message
        Index('idx_chat_feedback_unique', 'thread_id', 'message_id', 'campaigner_id', unique=True),
    )
