"""
Task management models for the agency system.

Tasks are created by campaigners and assigned to customers.
Multiple campaigners can be assigned to a task.
"""

from datetime import datetime
from enum import Enum
from typing import Optional, List
from sqlmodel import SQLModel, Field, Column, JSON
from .base import BaseModel


class TaskPriority(str, Enum):
    """Task priority levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class TaskStatus(str, Enum):
    """Task status states"""
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ON_HOLD = "on_hold"


class Task(BaseModel, table=True):
    """
    Tasks for customer management.

    Tasks are created by campaigners for specific customers.
    Multiple campaigners can be assigned to work on a task.
    """
    __tablename__ = "tasks"

    # Required relationships
    customer_id: int = Field(
        foreign_key="customers.id",
        description="Customer this task belongs to"
    )
    created_by: int = Field(
        foreign_key="campaigners.id",
        description="Campaigner who created this task"
    )

    # Task details
    title: str = Field(
        max_length=255,
        description="Task title/summary"
    )
    description: Optional[str] = Field(
        default=None,
        sa_column=Column(JSON),
        description="Detailed task description (can be rich text/markdown)"
    )

    # Assignment and scheduling
    assigned_campaigners: List[int] = Field(
        default_factory=list,
        sa_column=Column(JSON),
        description="List of campaigner IDs assigned to this task"
    )
    due_date: Optional[datetime] = Field(
        default=None,
        description="Task due date"
    )

    # Status and priority
    status: TaskStatus = Field(
        default=TaskStatus.TODO,
        description="Current task status"
    )
    priority: TaskPriority = Field(
        default=TaskPriority.MEDIUM,
        description="Task priority level"
    )

    # Additional metadata
    completed_at: Optional[datetime] = Field(
        default=None,
        description="Timestamp when task was marked as completed"
    )
    completed_by: Optional[int] = Field(
        default=None,
        foreign_key="campaigners.id",
        description="Campaigner who completed the task"
    )

    # Tags for categorization (optional)
    tags: List[str] = Field(
        default_factory=list,
        sa_column=Column(JSON),
        description="Tags for categorizing tasks"
    )

    # Soft delete
    is_active: bool = Field(
        default=True,
        description="Whether this task is active (soft delete)"
    )
