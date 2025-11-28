"""
Task API request/response schemas
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from app.models.tasks import TaskPriority, TaskStatus


class TaskCreate(BaseModel):
    """Schema for creating a new task"""
    customer_id: int = Field(..., description="Customer ID this task belongs to")
    title: str = Field(..., min_length=1, max_length=255, description="Task title")
    description: Optional[str] = Field(None, description="Task description (markdown supported)")
    assigned_campaigners: List[int] = Field(default_factory=list, description="List of campaigner IDs to assign")
    due_date: Optional[datetime] = Field(None, description="Task due date")
    priority: TaskPriority = Field(default=TaskPriority.MEDIUM, description="Task priority")
    status: TaskStatus = Field(default=TaskStatus.TODO, description="Initial task status")
    tags: List[str] = Field(default_factory=list, description="Task tags for categorization")

    class Config:
        json_schema_extra = {
            "example": {
                "customer_id": 123,
                "title": "Review Q4 marketing campaign performance",
                "description": "Analyze Google Ads and Meta campaigns for Q4",
                "assigned_campaigners": [5, 8],
                "due_date": "2025-12-31T23:59:59Z",
                "priority": "high",
                "status": "todo",
                "tags": ["marketing", "quarterly-review"]
            }
        }


class TaskUpdate(BaseModel):
    """Schema for updating a task"""
    title: Optional[str] = Field(None, min_length=1, max_length=255, description="Task title")
    description: Optional[str] = Field(None, description="Task description")
    assigned_campaigners: Optional[List[int]] = Field(None, description="List of campaigner IDs")
    due_date: Optional[datetime] = Field(None, description="Task due date")
    priority: Optional[TaskPriority] = Field(None, description="Task priority")
    status: Optional[TaskStatus] = Field(None, description="Task status")
    tags: Optional[List[str]] = Field(None, description="Task tags")

    class Config:
        json_schema_extra = {
            "example": {
                "status": "in_progress",
                "assigned_campaigners": [5, 8, 12],
                "priority": "urgent"
            }
        }


class TaskResponse(BaseModel):
    """Schema for task response"""
    id: int
    customer_id: int
    created_by: int
    created_at: datetime
    updated_at: datetime
    title: str
    description: Optional[str]
    assigned_campaigners: List[int]
    due_date: Optional[datetime]
    status: TaskStatus
    priority: TaskPriority
    tags: List[str]
    completed_at: Optional[datetime]
    completed_by: Optional[int]
    is_active: bool

    # Denormalized fields (populated by API)
    customer_name: Optional[str] = None
    created_by_name: Optional[str] = None
    assigned_campaigners_names: List[str] = Field(default_factory=list)
    completed_by_name: Optional[str] = None

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": 456,
                "customer_id": 123,
                "created_by": 5,
                "created_at": "2025-11-26T10:00:00Z",
                "updated_at": "2025-11-26T15:30:00Z",
                "title": "Review Q4 marketing campaign performance",
                "description": "Analyze Google Ads and Meta campaigns for Q4",
                "assigned_campaigners": [5, 8],
                "due_date": "2025-12-31T23:59:59Z",
                "status": "in_progress",
                "priority": "high",
                "tags": ["marketing", "quarterly-review"],
                "completed_at": None,
                "completed_by": None,
                "is_active": True,
                "customer_name": "Brand X Store #12",
                "created_by_name": "John Doe",
                "assigned_campaigners_names": ["John Doe", "Jane Smith"],
                "completed_by_name": None
            }
        }


class TaskListResponse(BaseModel):
    """Schema for paginated task list response"""
    tasks: List[TaskResponse]
    total: int
    page: int
    page_size: int
    total_pages: int

    class Config:
        json_schema_extra = {
            "example": {
                "tasks": [],
                "total": 42,
                "page": 1,
                "page_size": 20,
                "total_pages": 3
            }
        }


class TaskFilters(BaseModel):
    """Schema for task filtering parameters"""
    customer_id: Optional[int] = Field(None, description="Filter by customer ID")
    created_by: Optional[int] = Field(None, description="Filter by creator")
    assigned_to: Optional[int] = Field(None, description="Filter by assigned campaigner")
    status: Optional[TaskStatus] = Field(None, description="Filter by status")
    priority: Optional[TaskPriority] = Field(None, description="Filter by priority")
    tags: Optional[List[str]] = Field(None, description="Filter by tags (OR logic)")
    due_before: Optional[datetime] = Field(None, description="Tasks due before this date")
    due_after: Optional[datetime] = Field(None, description="Tasks due after this date")
    is_overdue: Optional[bool] = Field(None, description="Filter overdue tasks")
    search: Optional[str] = Field(None, description="Search in title and description")
    page: int = Field(default=1, ge=1, description="Page number")
    page_size: int = Field(default=20, ge=1, le=100, description="Items per page")
    sort_by: Optional[str] = Field(default="created_at", description="Field to sort by")
    sort_order: Optional[str] = Field(default="desc", description="Sort order: asc or desc")
