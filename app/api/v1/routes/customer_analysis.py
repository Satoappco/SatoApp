"""
Customer Analysis API Routes.

Endpoints for conducting comprehensive customer analysis including:
- Starting new analysis sessions
- Retrieving analysis results
- Managing work plans and tasks
- Viewing weekly reviews
- Configuring analysis settings
"""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from sqlmodel import Session

from app.config.database import get_session
from app.core.auth import get_current_user
from app.models.users import Campaigner
from app.api.schemas.customer_analysis import (
    AnalysisRequest,
    AnalysisResponse,
    AnalysisSessionList,
    AnalysisSessionListItem,
    AnalysisSessionDetail,
    AnalysisSettingsUpdate,
    AnalysisSettingsResponse,
    WorkPlanSummary,
    WorkPlanTaskList,
    WorkPlanTaskDetail,
    WorkPlanTaskUpdate,
    WeeklyReviewList,
    WeeklyReviewSummary,
    WeeklyReviewDetail,
    ErrorResponse
)
from app.services.customer_analysis_service import CustomerAnalysisService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/customer-analysis", tags=["customer-analysis"])


# Analysis Settings Endpoints

@router.get("/settings", response_model=AnalysisSettingsResponse)
async def get_analysis_settings(
    db: Session = Depends(get_session),
    current_user: Campaigner = Depends(get_current_user)
):
    """
    Get analysis settings for the current campaigner.

    Returns:
        Current analysis settings including automation flags and preferences
    """
    try:
        service = CustomerAnalysisService(db)
        settings = service.get_or_create_analysis_settings(current_user.id)

        return AnalysisSettingsResponse(
            campaigner_id=settings.campaigner_id,
            auto_analysis_on_create=settings.auto_analysis_on_create,
            auto_weekly_reviews=settings.auto_weekly_reviews,
            auto_quarterly_reanalysis=settings.auto_quarterly_reanalysis,
            notification_emails=settings.notification_emails,
            notify_on_analysis_complete=settings.notify_on_analysis_complete,
            notify_on_weekly_review=settings.notify_on_weekly_review,
            notify_on_quarterly_reanalysis=settings.notify_on_quarterly_reanalysis,
            weekly_review_day=settings.weekly_review_day,
            weekly_review_time=settings.weekly_review_time,
            preferred_analysis_model=settings.preferred_analysis_model,
            preferred_summarization_model=settings.preferred_summarization_model,
            default_research_depth=settings.default_research_depth,
            created_at=settings.created_at,
            updated_at=settings.updated_at
        )
    except Exception as e:
        logger.error(f"Error getting analysis settings: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get analysis settings: {str(e)}"
        )


@router.put("/settings", response_model=AnalysisSettingsResponse)
async def update_analysis_settings(
    settings_update: AnalysisSettingsUpdate,
    db: Session = Depends(get_session),
    current_user: Campaigner = Depends(get_current_user)
):
    """
    Update analysis settings for the current campaigner.

    Args:
        settings_update: Settings to update

    Returns:
        Updated analysis settings
    """
    try:
        service = CustomerAnalysisService(db)

        # Convert to dict, excluding None values
        settings_data = settings_update.model_dump(exclude_none=True)

        settings = service.update_analysis_settings(
            campaigner_id=current_user.id,
            settings_data=settings_data
        )

        return AnalysisSettingsResponse(
            campaigner_id=settings.campaigner_id,
            auto_analysis_on_create=settings.auto_analysis_on_create,
            auto_weekly_reviews=settings.auto_weekly_reviews,
            auto_quarterly_reanalysis=settings.auto_quarterly_reanalysis,
            notification_emails=settings.notification_emails,
            notify_on_analysis_complete=settings.notify_on_analysis_complete,
            notify_on_weekly_review=settings.notify_on_weekly_review,
            notify_on_quarterly_reanalysis=settings.notify_on_quarterly_reanalysis,
            weekly_review_day=settings.weekly_review_day,
            weekly_review_time=settings.weekly_review_time,
            preferred_analysis_model=settings.preferred_analysis_model,
            preferred_summarization_model=settings.preferred_summarization_model,
            default_research_depth=settings.default_research_depth,
            created_at=settings.created_at,
            updated_at=settings.updated_at
        )
    except Exception as e:
        logger.error(f"Error updating analysis settings: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update analysis settings: {str(e)}"
        )


# Health Check Endpoint

@router.get("/health")
async def customer_analysis_health_check(db: Session = Depends(get_session)):
    """
    Check the health of the customer analysis system.

    Returns:
        Health status including scheduler state, database connectivity,
        and pending analyses count
    """
    try:
        from app.services.customer_analysis_scheduler import get_scheduler
        from app.models.customer_analysis import CustomerAnalysisSession
        from sqlmodel import select, func

        scheduler = get_scheduler()

        # Count pending/running analyses
        pending_count = db.exec(
            select(func.count())
            .select_from(CustomerAnalysisSession)
            .where(CustomerAnalysisSession.status.in_(["pending", "running"]))
        ).first() or 0

        # Count total sessions
        total_count = db.exec(
            select(func.count())
            .select_from(CustomerAnalysisSession)
        ).first() or 0

        # Count completed sessions (last 24 hours)
        from datetime import datetime, timedelta
        day_ago = datetime.utcnow() - timedelta(days=1)
        recent_completed = db.exec(
            select(func.count())
            .select_from(CustomerAnalysisSession)
            .where(CustomerAnalysisSession.status == "completed")
            .where(CustomerAnalysisSession.completed_at >= day_ago)
        ).first() or 0

        return {
            "status": "healthy",
            "scheduler_running": scheduler._running if scheduler else False,
            "database": "connected",
            "statistics": {
                "pending_analyses": pending_count,
                "total_sessions": total_count,
                "completed_last_24h": recent_completed
            },
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Health check failed: {str(e)}", exc_info=True)
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


# Customer Analysis Endpoints

@router.post("", response_model=AnalysisResponse, status_code=status.HTTP_202_ACCEPTED)
async def start_customer_analysis(
    request: AnalysisRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_session),
    current_user: Campaigner = Depends(get_current_user)
):
    """
    Start a new customer analysis session.

    The analysis runs in the background and includes:
    - Client brief generation
    - Website research
    - Market research
    - Campaign analysis
    - Recommendations and work plan

    Args:
        request: Analysis request parameters

    Returns:
        Analysis session information with session_id for tracking
    """
    try:
        service = CustomerAnalysisService(db)

        # Create session immediately
        session = service.create_analysis_session(
            campaigner_id=current_user.id,
            customer_id=request.customer_id,
            analysis_type=request.analysis_type,
            trigger_source="manual",
            thread_id=request.thread_id
        )

        # Execute analysis in background
        async def run_analysis():
            try:
                await service.conduct_analysis(
                    campaigner_id=current_user.id,
                    customer_id=request.customer_id,
                    analysis_type=request.analysis_type,
                    trigger_source="manual",
                    thread_id=request.thread_id,
                    custom_config=request.custom_config,
                    streaming=False
                )
            except Exception as e:
                logger.error(f"Background analysis failed: {str(e)}", exc_info=True)

        background_tasks.add_task(run_analysis)

        return AnalysisResponse(
            success=True,
            session_id=session.session_id,
            status=session.status
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error starting analysis: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start analysis: {str(e)}"
        )


@router.get("", response_model=AnalysisSessionList)
async def list_analysis_sessions(
    customer_id: Optional[int] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_session),
    current_user: Campaigner = Depends(get_current_user)
):
    """
    List customer analysis sessions for the current campaigner.

    Args:
        customer_id: Optional filter by customer
        status: Optional filter by status (pending, running, completed, error)
        limit: Maximum number of sessions to return
        offset: Offset for pagination

    Returns:
        List of analysis sessions
    """
    try:
        service = CustomerAnalysisService(db)

        sessions = service.list_analysis_sessions(
            campaigner_id=current_user.id,
            customer_id=customer_id,
            status=status,
            limit=limit,
            offset=offset
        )

        session_items = [
            AnalysisSessionListItem(
                session_id=s.session_id,
                customer_id=s.customer_id,
                analysis_type=s.analysis_type,
                trigger_source=s.trigger_source,
                status=s.status,
                created_at=s.created_at,
                completed_at=s.completed_at,
                execution_time_ms=s.total_execution_time_ms
            )
            for s in sessions
        ]

        return AnalysisSessionList(
            sessions=session_items,
            total=len(session_items),
            limit=limit,
            offset=offset
        )

    except Exception as e:
        logger.error(f"Error listing analysis sessions: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list analysis sessions: {str(e)}"
        )


@router.get("/{session_id}", response_model=AnalysisSessionDetail)
async def get_analysis_session(
    session_id: str,
    db: Session = Depends(get_session),
    current_user: Campaigner = Depends(get_current_user)
):
    """
    Get detailed analysis session by ID.

    Args:
        session_id: The analysis session ID

    Returns:
        Detailed analysis session including all phase results
    """
    try:
        service = CustomerAnalysisService(db)

        session = service.get_analysis_session(
            session_id=session_id,
            campaigner_id=current_user.id
        )

        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Analysis session {session_id} not found"
            )

        return AnalysisSessionDetail(
            session_id=session.session_id,
            campaigner_id=session.campaigner_id,
            customer_id=session.customer_id,
            analysis_type=session.analysis_type,
            trigger_source=session.trigger_source,
            status=session.status,
            created_at=session.created_at,
            updated_at=session.updated_at,
            completed_at=session.completed_at,
            client_brief=session.client_brief_json,
            website_analysis=session.website_analysis_json,
            market_research=session.market_research_json,
            campaign_analysis=session.campaign_analysis_json,
            recommendations=session.recommendations_json,
            work_plan=session.work_plan_json,
            full_report_markdown=session.full_report_markdown,
            total_execution_time_ms=session.total_execution_time_ms,
            tokens_used=session.tokens_used,
            api_calls_made=session.api_calls_made,
            langfuse_trace_url=session.langfuse_trace_url
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting analysis session: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get analysis session: {str(e)}"
        )


@router.get("/{session_id}/report")
async def get_analysis_report(
    session_id: str,
    db: Session = Depends(get_session),
    current_user: Campaigner = Depends(get_current_user)
):
    """
    Get the full analysis report in markdown format.

    Args:
        session_id: The analysis session ID

    Returns:
        Full markdown report
    """
    try:
        service = CustomerAnalysisService(db)

        session = service.get_analysis_session(
            session_id=session_id,
            campaigner_id=current_user.id
        )

        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Analysis session {session_id} not found"
            )

        if not session.full_report_markdown:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Report not yet generated"
            )

        return {
            "session_id": session.session_id,
            "report": session.full_report_markdown
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting analysis report: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get analysis report: {str(e)}"
        )


# Work Plan Endpoints

@router.get("/work-plans/active", response_model=WorkPlanSummary)
async def get_active_work_plan(
    customer_id: Optional[int] = None,
    db: Session = Depends(get_session),
    current_user: Campaigner = Depends(get_current_user)
):
    """
    Get the active work plan for the current campaigner.

    Args:
        customer_id: Optional filter by customer

    Returns:
        Active work plan summary
    """
    try:
        service = CustomerAnalysisService(db)

        work_plan = service.get_active_work_plan(
            campaigner_id=current_user.id,
            customer_id=customer_id
        )

        if not work_plan:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No active work plan found"
            )

        return WorkPlanSummary(
            plan_id=work_plan.plan_id,
            status=work_plan.status,
            plan_period_weeks=work_plan.plan_period_weeks,
            current_week=work_plan.current_week,
            total_tasks=work_plan.total_tasks,
            completed_tasks=work_plan.completed_tasks,
            blocked_tasks=work_plan.blocked_tasks,
            in_progress_tasks=work_plan.in_progress_tasks,
            progress_percent=work_plan.progress_percent,
            overall_health_score=work_plan.overall_health_score,
            created_at=work_plan.created_at,
            updated_at=work_plan.updated_at
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting active work plan: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get active work plan: {str(e)}"
        )


@router.get("/work-plans/{plan_id}/tasks", response_model=WorkPlanTaskList)
async def get_work_plan_tasks(
    plan_id: str,
    week_number: Optional[int] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_session),
    current_user: Campaigner = Depends(get_current_user)
):
    """
    Get tasks for a work plan.

    Args:
        plan_id: The work plan ID
        week_number: Optional filter by week number
        status: Optional filter by status

    Returns:
        List of work plan tasks
    """
    try:
        service = CustomerAnalysisService(db)

        # First verify work plan belongs to campaigner
        from app.models.customer_analysis import WorkPlan
        from sqlmodel import select

        work_plan = db.exec(
            select(WorkPlan).where(WorkPlan.plan_id == plan_id)
        ).first()

        if not work_plan or work_plan.campaigner_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Work plan {plan_id} not found"
            )

        tasks = service.get_work_plan_tasks(
            work_plan_id=work_plan.id,
            week_number=week_number,
            status=status
        )

        task_details = [
            WorkPlanTaskDetail(
                task_id=t.task_id,
                week_number=t.week_number,
                category=t.category,
                title=t.title,
                description=t.description,
                priority=t.priority,
                impact=t.impact,
                effort=t.effort,
                status=t.status,
                dependencies=t.dependencies,
                review_notes=t.review_notes,
                expected_impact_description=t.expected_impact_description,
                actual_impact_notes=t.actual_impact_notes,
                created_at=t.created_at,
                updated_at=t.updated_at,
                started_at=t.started_at,
                completed_at=t.completed_at
            )
            for t in tasks
        ]

        return WorkPlanTaskList(
            tasks=task_details,
            total=len(task_details)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting work plan tasks: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get work plan tasks: {str(e)}"
        )


@router.patch("/tasks/{task_id}", response_model=WorkPlanTaskDetail)
async def update_work_plan_task(
    task_id: str,
    task_update: WorkPlanTaskUpdate,
    db: Session = Depends(get_session),
    current_user: Campaigner = Depends(get_current_user)
):
    """
    Update a work plan task status.

    Args:
        task_id: The task ID
        task_update: Task update data

    Returns:
        Updated task details
    """
    try:
        # Verify task belongs to campaigner
        from app.models.customer_analysis import WorkPlanTask, WorkPlan
        from sqlmodel import select

        task = db.exec(
            select(WorkPlanTask)
            .join(WorkPlan)
            .where(WorkPlanTask.task_id == task_id)
            .where(WorkPlan.campaigner_id == current_user.id)
        ).first()

        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task {task_id} not found"
            )

        service = CustomerAnalysisService(db)

        updated_task = service.update_task_status(
            task_id=task_id,
            status=task_update.status,
            note=task_update.note
        )

        return WorkPlanTaskDetail(
            task_id=updated_task.task_id,
            week_number=updated_task.week_number,
            category=updated_task.category,
            title=updated_task.title,
            description=updated_task.description,
            priority=updated_task.priority,
            impact=updated_task.impact,
            effort=updated_task.effort,
            status=updated_task.status,
            dependencies=updated_task.dependencies,
            review_notes=updated_task.review_notes,
            expected_impact_description=updated_task.expected_impact_description,
            actual_impact_notes=updated_task.actual_impact_notes,
            created_at=updated_task.created_at,
            updated_at=updated_task.updated_at,
            started_at=updated_task.started_at,
            completed_at=updated_task.completed_at
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating task: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update task: {str(e)}"
        )


# Weekly Review Endpoints

@router.get("/sessions/{session_id}/reviews", response_model=WeeklyReviewList)
async def list_weekly_reviews(
    session_id: str,
    db: Session = Depends(get_session),
    current_user: Campaigner = Depends(get_current_user)
):
    """
    List weekly reviews for an analysis session.

    Args:
        session_id: The analysis session ID

    Returns:
        List of weekly reviews
    """
    try:
        service = CustomerAnalysisService(db)

        # Verify session belongs to campaigner
        session = service.get_analysis_session(
            session_id=session_id,
            campaigner_id=current_user.id
        )

        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Analysis session {session_id} not found"
            )

        from app.models.customer_analysis import WeeklyReview
        from sqlmodel import select

        reviews = db.exec(
            select(WeeklyReview)
            .where(WeeklyReview.analysis_session_id == session.id)
            .order_by(WeeklyReview.week_number.desc())
        ).all()

        review_summaries = [
            WeeklyReviewSummary(
                review_id=r.review_id,
                week_number=r.week_number,
                status=r.status,
                overall_health_score=r.overall_health_score,
                progress_velocity=r.progress_velocity,
                created_at=r.created_at,
                completed_at=r.completed_at,
                acknowledged_at=r.acknowledged_at
            )
            for r in reviews
        ]

        return WeeklyReviewList(
            reviews=review_summaries,
            total=len(review_summaries)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing weekly reviews: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list weekly reviews: {str(e)}"
        )


@router.get("/reviews/{review_id}", response_model=WeeklyReviewDetail)
async def get_weekly_review(
    review_id: str,
    db: Session = Depends(get_session),
    current_user: Campaigner = Depends(get_current_user)
):
    """
    Get detailed weekly review.

    Args:
        review_id: The review ID

    Returns:
        Detailed weekly review
    """
    try:
        from app.models.customer_analysis import WeeklyReview
        from sqlmodel import select

        review = db.exec(
            select(WeeklyReview)
            .where(WeeklyReview.review_id == review_id)
            .where(WeeklyReview.campaigner_id == current_user.id)
        ).first()

        if not review:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Weekly review {review_id} not found"
            )

        return WeeklyReviewDetail(
            review_id=review.review_id,
            analysis_session_id=review.analysis_session_id,
            work_plan_id=review.work_plan_id,
            week_number=review.week_number,
            status=review.status,
            metrics_snapshot=review.metrics_snapshot,
            achievements=review.achievements,
            blockers=review.blockers,
            risks=review.risks,
            opportunities=review.opportunities,
            new_recommendations=review.new_recommendations,
            task_adjustments=review.task_adjustments,
            overall_health_score=review.overall_health_score,
            progress_velocity=review.progress_velocity,
            full_review_markdown=review.full_review_markdown,
            execution_time_ms=review.execution_time_ms,
            created_at=review.created_at,
            completed_at=review.completed_at,
            acknowledged_at=review.acknowledged_at
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting weekly review: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get weekly review: {str(e)}"
        )
