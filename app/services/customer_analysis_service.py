"""
Customer Analysis Service.

This service orchestrates comprehensive customer analysis including:
- Client brief generation
- Website research and analysis
- Market research and competitor analysis
- Digital content/campaign analysis
- Recommendations and work plan generation
"""

import os
import uuid
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, AsyncGenerator
from sqlmodel import Session, select

from app.models.customer_analysis import (
    CustomerAnalysisSession,
    WorkPlan,
    WorkPlanTask,
    WeeklyReview,
    AnalysisSettings,
    AnalysisPhaseResult,
    AnalysisSource,
    AnalysisComparison
)
from app.models.users import Campaigner, Customer
from app.services.chat_trace_service import ChatTraceService
from app.models.chat_traces import RecordType
from app.config.settings import get_settings

logger = logging.getLogger(__name__)


class CustomerAnalysisService:
    """Service for conducting comprehensive customer analysis."""

    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()
        self.chat_trace_service = ChatTraceService(db)

    def get_or_create_analysis_settings(
        self,
        campaigner_id: int
    ) -> AnalysisSettings:
        """
        Get or create analysis settings for a campaigner.

        Args:
            campaigner_id: The campaigner ID

        Returns:
            AnalysisSettings instance
        """
        settings = self.db.exec(
            select(AnalysisSettings).where(
                AnalysisSettings.campaigner_id == campaigner_id
            )
        ).first()

        if not settings:
            settings = AnalysisSettings(
                campaigner_id=campaigner_id,
                auto_analysis_on_create=False,
                auto_weekly_reviews=True,
                auto_quarterly_reanalysis=True,
                notification_emails=[],
                notify_on_analysis_complete=True,
                notify_on_weekly_review=True,
                notify_on_quarterly_reanalysis=True,
                weekly_review_day="monday",
                weekly_review_time="09:00",
                default_research_depth="medium"
            )
            self.db.add(settings)
            self.db.commit()
            self.db.refresh(settings)
            logger.info(f"Created default analysis settings for campaigner {campaigner_id}")

        return settings

    def update_analysis_settings(
        self,
        campaigner_id: int,
        settings_data: Dict[str, Any]
    ) -> AnalysisSettings:
        """
        Update analysis settings for a campaigner.

        Args:
            campaigner_id: The campaigner ID
            settings_data: Dict with settings to update

        Returns:
            Updated AnalysisSettings instance
        """
        settings = self.get_or_create_analysis_settings(campaigner_id)

        # Update fields
        for key, value in settings_data.items():
            if hasattr(settings, key):
                setattr(settings, key, value)

        settings.updated_at = datetime.utcnow()
        self.db.add(settings)
        self.db.commit()
        self.db.refresh(settings)

        logger.info(f"Updated analysis settings for campaigner {campaigner_id}")
        return settings

    def create_analysis_session(
        self,
        campaigner_id: int,
        customer_id: Optional[int],
        analysis_type: str,
        trigger_source: str,
        thread_id: Optional[str] = None,
        previous_session_id: Optional[str] = None
    ) -> CustomerAnalysisSession:
        """
        Create a new customer analysis session.

        Args:
            campaigner_id: The campaigner ID
            customer_id: Optional customer ID for customer-specific analysis
            analysis_type: Type of analysis (initial, quarterly, manual)
            trigger_source: How it was triggered (auto_onboarding, scheduled, manual)
            thread_id: Optional chat thread ID for tracing
            previous_session_id: Optional previous session ID for comparison

        Returns:
            Created CustomerAnalysisSession instance
        """
        session_id = f"ca_{uuid.uuid4().hex[:12]}"

        session = CustomerAnalysisSession(
            session_id=session_id,
            campaigner_id=campaigner_id,
            customer_id=customer_id,
            analysis_type=analysis_type,
            trigger_source=trigger_source,
            status="pending",
            previous_session_id=previous_session_id,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

        # Set scheduling for next reviews/analysis
        if analysis_type in ["initial", "quarterly"]:
            # Schedule next quarterly analysis in 3 months
            session.next_quarterly_analysis_at = datetime.utcnow() + timedelta(days=90)

            # Schedule first weekly review in 1 week
            session.next_weekly_review_at = datetime.utcnow() + timedelta(days=7)

        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)

        logger.info(
            f"Created analysis session {session_id} for campaigner {campaigner_id}, "
            f"type={analysis_type}, trigger={trigger_source}"
        )

        return session

    async def conduct_analysis(
        self,
        campaigner_id: int,
        customer_id: Optional[int],
        analysis_type: str = "initial",
        trigger_source: str = "manual",
        thread_id: Optional[str] = None,
        custom_config: Optional[Dict[str, Any]] = None,
        streaming: bool = False
    ) -> Dict[str, Any]:
        """
        Conduct comprehensive customer analysis.

        This is the main entry point for customer analysis. It orchestrates:
        1. Client Brief Generation
        2. Website Research
        3. Market Research
        4. Campaign Analysis
        5. Recommendations & Work Plan

        Args:
            campaigner_id: The campaigner ID
            customer_id: Optional customer ID
            analysis_type: Type of analysis (initial, quarterly, manual)
            trigger_source: How triggered (auto_onboarding, scheduled, manual)
            thread_id: Optional chat thread ID for tracing
            custom_config: Optional custom configuration
            streaming: Whether to stream progress updates

        Returns:
            Dict with analysis results and metadata

        Raises:
            ValueError: If customer_id is invalid or campaigner doesn't have access
        """
        logger.info(
            f"Starting customer analysis: campaigner={campaigner_id}, "
            f"customer={customer_id}, type={analysis_type}, trigger={trigger_source}"
        )

        # Validate customer access
        if customer_id:
            customer = self.db.get(Customer, customer_id)
            if not customer or customer.campaigner_id != campaigner_id:
                raise ValueError(f"Customer {customer_id} not found or access denied")

        # Get campaigner
        campaigner = self.db.get(Campaigner, campaigner_id)
        if not campaigner:
            raise ValueError(f"Campaigner {campaigner_id} not found")

        # Get previous session for comparison (quarterly re-analysis)
        previous_session_id = None
        if analysis_type == "quarterly" and customer_id:
            previous_session = self.db.exec(
                select(CustomerAnalysisSession)
                .where(CustomerAnalysisSession.customer_id == customer_id)
                .where(CustomerAnalysisSession.status == "completed")
                .order_by(CustomerAnalysisSession.completed_at.desc())
            ).first()
            if previous_session:
                previous_session_id = previous_session.session_id

        # Create analysis session
        session = self.create_analysis_session(
            campaigner_id=campaigner_id,
            customer_id=customer_id,
            analysis_type=analysis_type,
            trigger_source=trigger_source,
            thread_id=thread_id,
            previous_session_id=previous_session_id
        )

        try:
            # Update status to running
            session.status = "running"
            session.updated_at = datetime.utcnow()
            self.db.add(session)
            self.db.commit()

            # Execute analysis workflow
            start_time = datetime.utcnow()

            if streaming:
                # TODO: Implement streaming execution
                raise NotImplementedError("Streaming not yet implemented")
            else:
                result = await self._execute_analysis_workflow(
                    session=session,
                    campaigner=campaigner,
                    customer=customer if customer_id else None,
                    custom_config=custom_config
                )

            execution_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

            # Update session with results
            session.status = "completed"
            session.completed_at = datetime.utcnow()
            session.updated_at = datetime.utcnow()
            session.total_execution_time_ms = execution_time_ms
            session.tokens_used = result.get("tokens_used", 0)
            session.api_calls_made = result.get("api_calls_made", 0)

            # Store phase results
            session.client_brief_json = result.get("client_brief", {})
            session.website_analysis_json = result.get("website_analysis", {})
            session.market_research_json = result.get("market_research", {})
            session.campaign_analysis_json = result.get("campaign_analysis", {})
            session.recommendations_json = result.get("recommendations", {})
            session.work_plan_json = result.get("work_plan", {})
            session.full_report_markdown = result.get("full_report_markdown", "")

            self.db.add(session)
            self.db.commit()
            self.db.refresh(session)

            # Create work plan if included in results
            if result.get("work_plan"):
                work_plan = self._create_work_plan_from_result(
                    session=session,
                    work_plan_data=result["work_plan"]
                )
                result["work_plan_id"] = work_plan.plan_id

            # Record to chat traces if thread_id provided
            if thread_id:
                self._record_to_chat_traces(
                    thread_id=thread_id,
                    session=session,
                    result=result
                )

            logger.info(
                f"Completed analysis session {session.session_id} in {execution_time_ms}ms"
            )

            return {
                "success": True,
                "session_id": session.session_id,
                "status": session.status,
                "result": result,
                "execution_time_ms": execution_time_ms,
                "tokens_used": session.tokens_used,
                "api_calls_made": session.api_calls_made
            }

        except Exception as e:
            logger.error(f"Error in analysis session {session.session_id}: {str(e)}", exc_info=True)

            # Update session to error status
            session.status = "error"
            session.updated_at = datetime.utcnow()
            self.db.add(session)
            self.db.commit()

            return {
                "success": False,
                "session_id": session.session_id,
                "status": "error",
                "error": str(e)
            }

    async def _execute_analysis_workflow(
        self,
        session: CustomerAnalysisSession,
        campaigner: Campaigner,
        customer: Optional[Customer],
        custom_config: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Execute the multi-phase analysis workflow using LangGraph.

        Args:
            session: The analysis session
            campaigner: The campaigner
            customer: Optional customer
            custom_config: Optional custom configuration

        Returns:
            Dict with analysis results
        """
        logger.info(f"Executing analysis workflow for session {session.session_id}")

        from app.workflows.customer_analysis_workflow import get_workflow

        # Get workflow instance
        workflow = get_workflow(
            model_name=custom_config.get("analysis_model", "gpt-4o") if custom_config else "gpt-4o",
            summarization_model_name=custom_config.get("summarization_model", "gpt-4o-mini") if custom_config else "gpt-4o-mini"
        )

        # Execute workflow
        result = await workflow.execute(
            campaigner_id=campaigner.id,
            campaigner_name=campaigner.name,
            customer_id=customer.id if customer else None,
            customer_name=customer.full_name if customer else None,
            website_url=customer.website_url if customer else None,
            business_description=customer.narrative_report if customer else None
        )

        return result

    def _create_work_plan_from_result(
        self,
        session: CustomerAnalysisSession,
        work_plan_data: Dict[str, Any]
    ) -> WorkPlan:
        """
        Create a work plan from analysis results.

        Args:
            session: The analysis session
            work_plan_data: Work plan data from analysis

        Returns:
            Created WorkPlan instance
        """
        plan_id = f"wp_{uuid.uuid4().hex[:12]}"

        work_plan = WorkPlan(
            plan_id=plan_id,
            analysis_session_id=session.id,
            campaigner_id=session.campaigner_id,
            status="active",
            plan_period_weeks=work_plan_data.get("period_weeks", 8),
            current_week=1,
            total_tasks=0,
            completed_tasks=0,
            blocked_tasks=0,
            in_progress_tasks=0,
            progress_percent=0.0,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

        self.db.add(work_plan)
        self.db.commit()
        self.db.refresh(work_plan)

        # Create tasks from work_plan_data
        tasks_by_week = work_plan_data.get("tasks_by_week", {})
        for week_str, tasks in tasks_by_week.items():
            week_number = int(week_str.replace("week_", ""))
            for task_data in tasks:
                self._create_work_plan_task(
                    work_plan=work_plan,
                    week_number=week_number,
                    task_data=task_data
                )

        # Update task counts
        work_plan.total_tasks = len(self.db.exec(
            select(WorkPlanTask).where(WorkPlanTask.work_plan_id == work_plan.id)
        ).all())

        self.db.add(work_plan)
        self.db.commit()
        self.db.refresh(work_plan)

        logger.info(f"Created work plan {plan_id} with {work_plan.total_tasks} tasks")
        return work_plan

    def _create_work_plan_task(
        self,
        work_plan: WorkPlan,
        week_number: int,
        task_data: Dict[str, Any]
    ) -> WorkPlanTask:
        """
        Create a work plan task.

        Args:
            work_plan: The work plan
            week_number: Week number for the task
            task_data: Task data

        Returns:
            Created WorkPlanTask instance
        """
        task_id = f"task_{uuid.uuid4().hex[:12]}"

        task = WorkPlanTask(
            task_id=task_id,
            work_plan_id=work_plan.id,
            week_number=week_number,
            category=task_data.get("category", "general"),
            title=task_data.get("title", ""),
            description=task_data.get("description", ""),
            priority=task_data.get("priority", "medium"),
            impact=task_data.get("impact", "medium"),
            effort=task_data.get("effort", "medium"),
            status="pending",
            dependencies=task_data.get("dependencies", []),
            review_notes=[],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)

        return task

    def _record_to_chat_traces(
        self,
        thread_id: str,
        session: CustomerAnalysisSession,
        result: Dict[str, Any]
    ) -> None:
        """
        Record analysis to chat traces.

        Args:
            thread_id: The chat thread ID
            session: The analysis session
            result: The analysis result
        """
        try:
            from app.models.chat_traces import ChatTrace

            # Create a chat trace record for the customer analysis
            trace = ChatTrace(
                thread_id=thread_id,
                record_type=RecordType.DEEP_RESEARCH,
                campaigner_id=session.campaigner_id,
                customer_id=session.customer_id,
                data={
                    "analysis_type": session.analysis_type,
                    "trigger_source": session.trigger_source,
                    "session_id": session.session_id,
                    "status": session.status,
                    "execution_time_ms": session.total_execution_time_ms,
                    "tokens_used": session.tokens_used,
                    "success": result.get("success", False),
                    "report": session.full_report_markdown[:500] if session.full_report_markdown else None
                },
                langfuse_trace_id=session.langfuse_trace_id,
                langfuse_trace_url=session.langfuse_trace_url,
                created_at=datetime.utcnow()
            )
            self.db.add(trace)
            self.db.commit()
        except Exception as e:
            logger.error(f"Error recording to chat traces: {str(e)}", exc_info=True)

    def get_analysis_session(
        self,
        session_id: str,
        campaigner_id: int
    ) -> Optional[CustomerAnalysisSession]:
        """
        Get an analysis session by ID.

        Args:
            session_id: The session ID
            campaigner_id: The campaigner ID (for access control)

        Returns:
            CustomerAnalysisSession if found, None otherwise
        """
        return self.db.exec(
            select(CustomerAnalysisSession)
            .where(CustomerAnalysisSession.session_id == session_id)
            .where(CustomerAnalysisSession.campaigner_id == campaigner_id)
        ).first()

    def list_analysis_sessions(
        self,
        campaigner_id: int,
        customer_id: Optional[int] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[CustomerAnalysisSession]:
        """
        List analysis sessions for a campaigner.

        Args:
            campaigner_id: The campaigner ID
            customer_id: Optional customer ID filter
            status: Optional status filter
            limit: Maximum number of sessions to return
            offset: Offset for pagination

        Returns:
            List of CustomerAnalysisSession instances
        """
        query = select(CustomerAnalysisSession).where(
            CustomerAnalysisSession.campaigner_id == campaigner_id
        )

        if customer_id:
            query = query.where(CustomerAnalysisSession.customer_id == customer_id)

        if status:
            query = query.where(CustomerAnalysisSession.status == status)

        query = query.order_by(CustomerAnalysisSession.created_at.desc())
        query = query.limit(limit).offset(offset)

        return self.db.exec(query).all()

    def get_active_work_plan(
        self,
        campaigner_id: int,
        customer_id: Optional[int] = None
    ) -> Optional[WorkPlan]:
        """
        Get the active work plan for a campaigner/customer.

        Args:
            campaigner_id: The campaigner ID
            customer_id: Optional customer ID

        Returns:
            Active WorkPlan if found, None otherwise
        """
        query = (
            select(WorkPlan)
            .join(CustomerAnalysisSession)
            .where(WorkPlan.campaigner_id == campaigner_id)
            .where(WorkPlan.status == "active")
        )

        if customer_id:
            query = query.where(CustomerAnalysisSession.customer_id == customer_id)

        return self.db.exec(query).first()

    def get_work_plan_tasks(
        self,
        work_plan_id: int,
        week_number: Optional[int] = None,
        status: Optional[str] = None
    ) -> List[WorkPlanTask]:
        """
        Get tasks for a work plan.

        Args:
            work_plan_id: The work plan ID
            week_number: Optional week number filter
            status: Optional status filter

        Returns:
            List of WorkPlanTask instances
        """
        query = select(WorkPlanTask).where(WorkPlanTask.work_plan_id == work_plan_id)

        if week_number is not None:
            query = query.where(WorkPlanTask.week_number == week_number)

        if status:
            query = query.where(WorkPlanTask.status == status)

        query = query.order_by(WorkPlanTask.week_number, WorkPlanTask.priority)

        return self.db.exec(query).all()

    def update_task_status(
        self,
        task_id: str,
        status: str,
        note: Optional[str] = None
    ) -> WorkPlanTask:
        """
        Update a work plan task status.

        Args:
            task_id: The task ID
            status: New status
            note: Optional note about the status change

        Returns:
            Updated WorkPlanTask instance
        """
        task = self.db.exec(
            select(WorkPlanTask).where(WorkPlanTask.task_id == task_id)
        ).first()

        if not task:
            raise ValueError(f"Task {task_id} not found")

        old_status = task.status
        task.status = status
        task.updated_at = datetime.utcnow()

        # Update timestamps
        if status == "in_progress" and not task.started_at:
            task.started_at = datetime.utcnow()
        elif status == "completed" and not task.completed_at:
            task.completed_at = datetime.utcnow()

        # Add note to review_notes
        if note:
            task.review_notes.append({
                "timestamp": datetime.utcnow().isoformat(),
                "status_change": f"{old_status} -> {status}",
                "note": note
            })

        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)

        # Update work plan progress
        self._update_work_plan_progress(task.work_plan_id)

        logger.info(f"Updated task {task_id} status: {old_status} -> {status}")
        return task

    def _update_work_plan_progress(self, work_plan_id: int) -> None:
        """
        Update work plan progress metrics.

        Args:
            work_plan_id: The work plan ID
        """
        work_plan = self.db.get(WorkPlan, work_plan_id)
        if not work_plan:
            return

        tasks = self.get_work_plan_tasks(work_plan_id)

        work_plan.total_tasks = len(tasks)
        work_plan.completed_tasks = len([t for t in tasks if t.status == "completed"])
        work_plan.blocked_tasks = len([t for t in tasks if t.status == "blocked"])
        work_plan.in_progress_tasks = len([t for t in tasks if t.status == "in_progress"])

        if work_plan.total_tasks > 0:
            work_plan.progress_percent = (work_plan.completed_tasks / work_plan.total_tasks) * 100

        work_plan.updated_at = datetime.utcnow()
        self.db.add(work_plan)
        self.db.commit()

    async def conduct_weekly_review(
        self,
        analysis_session_id: int,
        work_plan_id: int,
        week_number: int
    ) -> WeeklyReview:
        """
        Conduct a weekly review of work plan progress.

        Args:
            analysis_session_id: The analysis session ID
            work_plan_id: The work plan ID
            week_number: The week number

        Returns:
            Created WeeklyReview instance
        """
        logger.info(f"Conducting weekly review for week {week_number}")

        from app.workflows.weekly_review_workflow import get_weekly_review_workflow

        # Get analysis session and work plan
        analysis_session = self.db.get(CustomerAnalysisSession, analysis_session_id)
        work_plan = self.db.get(WorkPlan, work_plan_id)

        if not analysis_session or not work_plan:
            raise ValueError("Analysis session or work plan not found")

        # Get tasks for the current week and previous weeks
        tasks = self.get_work_plan_tasks(
            work_plan_id=work_plan_id,
            week_number=week_number
        )

        # Get metrics snapshot
        metrics_snapshot = {
            "total_tasks": work_plan.total_tasks,
            "completed_tasks": work_plan.completed_tasks,
            "in_progress_tasks": work_plan.in_progress_tasks,
            "blocked_tasks": work_plan.blocked_tasks,
            "progress_percent": work_plan.progress_percent,
            "overall_health_score": work_plan.overall_health_score or 0
        }

        # Format tasks for workflow
        tasks_data = [
            {
                "title": t.title,
                "description": t.description,
                "status": t.status,
                "priority": t.priority,
                "impact": t.impact,
                "effort": t.effort,
                "week_number": t.week_number
            }
            for t in tasks
        ]

        # Execute weekly review workflow
        workflow = get_weekly_review_workflow()
        start_time = datetime.utcnow()

        result = await workflow.execute(
            week_number=week_number,
            tasks=tasks_data,
            metrics_snapshot=metrics_snapshot
        )

        execution_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

        # Create weekly review record
        review_id = f"rev_{uuid.uuid4().hex[:12]}"

        weekly_review = WeeklyReview(
            review_id=review_id,
            analysis_session_id=analysis_session.id,
            work_plan_id=work_plan.id,
            campaigner_id=analysis_session.campaigner_id,
            week_number=week_number,
            status="completed",
            metrics_snapshot=metrics_snapshot,
            achievements=result.get("achievements", []),
            blockers=result.get("blockers", []),
            risks=result.get("risks", []),
            opportunities=result.get("opportunities", []),
            new_recommendations=result.get("new_recommendations", []),
            task_adjustments=result.get("task_adjustments", []),
            overall_health_score=result.get("overall_health_score", 50.0),
            progress_velocity=result.get("progress_velocity"),
            full_review_markdown=result.get("full_review_markdown", ""),
            execution_time_ms=execution_time_ms,
            created_at=datetime.utcnow(),
            completed_at=datetime.utcnow()
        )

        self.db.add(weekly_review)
        self.db.commit()
        self.db.refresh(weekly_review)

        logger.info(f"Created weekly review {review_id} for week {week_number}")

        return weekly_review
