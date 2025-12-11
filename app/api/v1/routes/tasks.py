"""
Task Management API routes
Handles CRUD operations for tasks
"""

from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlmodel import select, and_, or_, func
from sqlalchemy import JSON

from app.core.auth import get_current_user
from app.models.users import Campaigner, Customer
from app.models.tasks import Task, TaskPriority, TaskStatus
from app.api.schemas.tasks import (
    TaskCreate,
    TaskUpdate,
    TaskResponse,
    TaskListResponse,
    TaskFilters
)
from app.config.database import get_session
from app.config.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/tasks", tags=["tasks"])


def enrich_task_response(task: Task, session) -> TaskResponse:
    """
    Enrich task with denormalized fields (names).

    Args:
        task: Task model instance
        session: Database session

    Returns:
        TaskResponse with populated name fields
    """
    response = TaskResponse.from_orm(task)

    # Get customer name
    customer = session.get(Customer, task.customer_id)
    if customer:
        response.customer_name = customer.full_name

    # Get creator name
    creator = session.get(Campaigner, task.created_by)
    if creator:
        response.created_by_name = creator.full_name

    # Get assigned campaigners names
    if task.assigned_campaigners:
        assigned_names = []
        for campaigner_id in task.assigned_campaigners:
            campaigner = session.get(Campaigner, campaigner_id)
            if campaigner:
                assigned_names.append(campaigner.full_name)
        response.assigned_campaigners_names = assigned_names

    # Get completer name
    if task.completed_by:
        completer = session.get(Campaigner, task.completed_by)
        if completer:
            response.completed_by_name = completer.full_name

    return response


@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    task_data: TaskCreate,
    current_user: Campaigner = Depends(get_current_user)
):
    """
    Create a new task.

    The task will be created by the current user and assigned to the specified customer.
    """
    try:
        with get_session() as session:
            # Verify customer exists and belongs to user's agency
            customer = session.get(Customer, task_data.customer_id)
            if not customer:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Customer {task_data.customer_id} not found"
                )

            if customer.agency_id != current_user.agency_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Customer belongs to a different agency"
                )

            # Verify assigned campaigners exist and belong to same agency
            if task_data.assigned_campaigners:
                for campaigner_id in task_data.assigned_campaigners:
                    campaigner = session.get(Campaigner, campaigner_id)
                    if not campaigner:
                        raise HTTPException(
                            status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Campaigner {campaigner_id} not found"
                        )
                    if campaigner.agency_id != current_user.agency_id:
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail=f"Campaigner {campaigner_id} belongs to a different agency"
                        )

            # Create task
            task = Task(
                customer_id=task_data.customer_id,
                created_by=current_user.id,
                title=task_data.title,
                description=task_data.description,
                assigned_campaigners=task_data.assigned_campaigners,
                due_date=task_data.due_date,
                priority=task_data.priority,
                status=task_data.status,
                tags=task_data.tags
            )

            session.add(task)
            session.commit()
            session.refresh(task)

            logger.info(f"✅ Task {task.id} created by campaigner {current_user.id} for customer {task_data.customer_id}")

            return enrich_task_response(task, session)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error creating task: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create task: {str(e)}"
        )


@router.get("", response_model=TaskListResponse)
async def list_tasks(
    customer_id: Optional[int] = Query(None, description="Filter by customer ID"),
    created_by: Optional[int] = Query(None, description="Filter by creator"),
    assigned_to: Optional[int] = Query(None, description="Filter by assigned campaigner"),
    status_filter: Optional[TaskStatus] = Query(None, alias="status", description="Filter by status"),
    priority_filter: Optional[TaskPriority] = Query(None, alias="priority", description="Filter by priority"),
    is_overdue: Optional[bool] = Query(None, description="Filter overdue tasks"),
    search: Optional[str] = Query(None, description="Search in title and description"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    sort_by: str = Query("created_at", description="Field to sort by"),
    sort_order: str = Query("desc", description="Sort order: asc or desc"),
    current_user: Campaigner = Depends(get_current_user)
):
    """
    Get tasks with filtering, pagination, and sorting.

    Users can only see tasks for customers in their agency.
    """
    try:
        with get_session() as session:
            # Base query: only tasks for customers in user's agency
            statement = select(Task).join(Customer).where(
                and_(
                    Customer.agency_id == current_user.agency_id,
                    Task.is_active == True
                )
            )

            # Apply filters
            if customer_id:
                statement = statement.where(Task.customer_id == customer_id)

            if created_by:
                statement = statement.where(Task.created_by == created_by)

            if assigned_to:
                # Check if campaigner is in assigned_campaigners array
                statement = statement.where(
                    Task.assigned_campaigners.contains([assigned_to])
                )

            if status_filter:
                statement = statement.where(Task.status == status_filter)

            if priority_filter:
                statement = statement.where(Task.priority == priority_filter)

            if is_overdue is not None:
                now = datetime.now(timezone.utc)
                if is_overdue:
                    # Overdue: due_date is in the past and status is not completed
                    statement = statement.where(
                        and_(
                            Task.due_date < now,
                            Task.status != TaskStatus.COMPLETED,
                            Task.status != TaskStatus.CANCELLED
                        )
                    )
                else:
                    # Not overdue
                    statement = statement.where(
                        or_(
                            Task.due_date >= now,
                            Task.due_date.is_(None),
                            Task.status == TaskStatus.COMPLETED,
                            Task.status == TaskStatus.CANCELLED
                        )
                    )

            if search:
                search_pattern = f"%{search}%"
                statement = statement.where(
                    or_(
                        Task.title.ilike(search_pattern),
                        Task.description.ilike(search_pattern)
                    )
                )

            # Get total count before pagination
            count_statement = select(func.count()).select_from(statement.subquery())
            total = session.exec(count_statement).one()

            # Apply sorting
            sort_column = getattr(Task, sort_by, Task.created_at)
            if sort_order.lower() == "asc":
                statement = statement.order_by(sort_column.asc())
            else:
                statement = statement.order_by(sort_column.desc())

            # Apply pagination
            offset = (page - 1) * page_size
            statement = statement.offset(offset).limit(page_size)

            # Execute query
            tasks = session.exec(statement).all()

            # Enrich with names
            enriched_tasks = [enrich_task_response(task, session) for task in tasks]

            # Calculate pagination metadata
            total_pages = (total + page_size - 1) // page_size

            return TaskListResponse(
                tasks=enriched_tasks,
                total=total,
                page=page,
                page_size=page_size,
                total_pages=total_pages
            )

    except Exception as e:
        logger.error(f"❌ Error listing tasks: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list tasks: {str(e)}"
        )


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: int,
    current_user: Campaigner = Depends(get_current_user)
):
    """
    Get a single task by ID.

    Users can only access tasks for customers in their agency.
    """
    try:
        with get_session() as session:
            task = session.get(Task, task_id)

            if not task or not task.is_active:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Task {task_id} not found"
                )

            # Verify task belongs to customer in user's agency
            customer = session.get(Customer, task.customer_id)
            if not customer or customer.agency_id != current_user.agency_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied"
                )

            return enrich_task_response(task, session)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting task {task_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get task: {str(e)}"
        )


@router.put("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: int,
    task_data: TaskUpdate,
    current_user: Campaigner = Depends(get_current_user)
):
    """
    Update a task.

    Users can only update tasks for customers in their agency.
    """
    try:
        with get_session() as session:
            task = session.get(Task, task_id)

            if not task or not task.is_active:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Task {task_id} not found"
                )

            # Verify task belongs to customer in user's agency
            customer = session.get(Customer, task.customer_id)
            if not customer or customer.agency_id != current_user.agency_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied"
                )

            # Update fields
            update_data = task_data.dict(exclude_unset=True)

            # Verify assigned campaigners if being updated
            if "assigned_campaigners" in update_data and update_data["assigned_campaigners"]:
                for campaigner_id in update_data["assigned_campaigners"]:
                    campaigner = session.get(Campaigner, campaigner_id)
                    if not campaigner:
                        raise HTTPException(
                            status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Campaigner {campaigner_id} not found"
                        )
                    if campaigner.agency_id != current_user.agency_id:
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail=f"Campaigner {campaigner_id} belongs to a different agency"
                        )

            # If status is being set to completed, record completion
            if "status" in update_data and update_data["status"] == TaskStatus.COMPLETED:
                if task.status != TaskStatus.COMPLETED:
                    task.completed_at = datetime.now(timezone.utc)
                    task.completed_by = current_user.id

            # If status is being changed from completed to something else, clear completion
            if "status" in update_data and update_data["status"] != TaskStatus.COMPLETED:
                if task.status == TaskStatus.COMPLETED:
                    task.completed_at = None
                    task.completed_by = None

            # Apply updates
            for field, value in update_data.items():
                setattr(task, field, value)

            session.add(task)
            session.commit()
            session.refresh(task)

            logger.info(f"✅ Task {task_id} updated by campaigner {current_user.id}")

            return enrich_task_response(task, session)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error updating task {task_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update task: {str(e)}"
        )


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: int,
    current_user: Campaigner = Depends(get_current_user)
):
    """
    Delete a task (soft delete).

    Users can only delete tasks for customers in their agency.
    """
    try:
        with get_session() as session:
            task = session.get(Task, task_id)

            if not task or not task.is_active:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Task {task_id} not found"
                )

            # Verify task belongs to customer in user's agency
            customer = session.get(Customer, task.customer_id)
            if not customer or customer.agency_id != current_user.agency_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied"
                )

            # Soft delete
            task.is_active = False
            session.add(task)
            session.commit()

            logger.info(f"✅ Task {task_id} deleted by campaigner {current_user.id}")

            return None

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error deleting task {task_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete task: {str(e)}"
        )
