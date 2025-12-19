"""
Customer Analysis Scheduler Service.

Handles automated scheduling of:
- Weekly reviews (every Monday at 9 AM)
- Quarterly re-analysis (every 3 months)
- Custom schedules per campaigner settings
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from sqlmodel import Session, select, create_engine

from app.models.customer_analysis import (
    CustomerAnalysisSession,
    WorkPlan,
    AnalysisSettings
)
from app.services.customer_analysis_service import CustomerAnalysisService
from app.config.settings import get_settings

logger = logging.getLogger(__name__)


class CustomerAnalysisScheduler:
    """Service for scheduling automated customer analysis tasks."""

    def __init__(self):
        """Initialize the scheduler."""
        self.scheduler = AsyncIOScheduler()
        self.settings = get_settings()
        self._running = False

    def start(self):
        """Start the scheduler."""
        if self._running:
            logger.warning("Scheduler is already running")
            return

        logger.info("Starting Customer Analysis Scheduler")

        # Schedule weekly reviews (every Monday at 9 AM)
        self.scheduler.add_job(
            self.run_weekly_reviews,
            CronTrigger(day_of_week="mon", hour=9, minute=0),
            id="weekly_reviews",
            replace_existing=True
        )

        # Schedule quarterly analysis checks (daily at 1 AM)
        self.scheduler.add_job(
            self.run_quarterly_checks,
            CronTrigger(hour=1, minute=0),
            id="quarterly_checks",
            replace_existing=True
        )

        self.scheduler.start()
        self._running = True

        logger.info("Customer Analysis Scheduler started successfully")

    def stop(self):
        """Stop the scheduler."""
        if not self._running:
            return

        logger.info("Stopping Customer Analysis Scheduler")
        self.scheduler.shutdown(wait=False)
        self._running = False

    async def run_weekly_reviews(self):
        """
        Run weekly reviews for all active work plans.

        This is executed every Monday at 9 AM.
        """
        logger.info("Running scheduled weekly reviews")

        try:
            # Create database session
            engine = create_engine(self.settings.database_url)
            with Session(engine) as db:
                # Get all active work plans that need weekly reviews
                active_plans = db.exec(
                    select(WorkPlan)
                    .join(CustomerAnalysisSession)
                    .where(WorkPlan.status == "active")
                    .where(CustomerAnalysisSession.next_weekly_review_at <= datetime.utcnow())
                ).all()

                logger.info(f"Found {len(active_plans)} work plans for weekly review")

                for work_plan in active_plans:
                    try:
                        await self._conduct_weekly_review_for_plan(db, work_plan)
                    except Exception as e:
                        logger.error(
                            f"Error conducting weekly review for plan {work_plan.plan_id}: {str(e)}",
                            exc_info=True
                        )

        except Exception as e:
            logger.error(f"Error in run_weekly_reviews: {str(e)}", exc_info=True)

    async def _conduct_weekly_review_for_plan(self, db: Session, work_plan: WorkPlan):
        """Conduct a weekly review for a specific work plan."""
        from app.models.customer_analysis import CustomerAnalysisSession

        # Get analysis session
        analysis_session = db.exec(
            select(CustomerAnalysisSession)
            .where(CustomerAnalysisSession.id == work_plan.analysis_session_id)
        ).first()

        if not analysis_session:
            logger.warning(f"Analysis session not found for work plan {work_plan.plan_id}")
            return

        # Check if campaigner has weekly reviews enabled
        settings = db.exec(
            select(AnalysisSettings)
            .where(AnalysisSettings.campaigner_id == work_plan.campaigner_id)
        ).first()

        if settings and not settings.auto_weekly_reviews:
            logger.info(f"Weekly reviews disabled for campaigner {work_plan.campaigner_id}")
            return

        # Increment current week
        current_week = work_plan.current_week
        if current_week >= work_plan.plan_period_weeks:
            logger.info(f"Work plan {work_plan.plan_id} has completed all weeks")
            # Mark as completed
            work_plan.status = "completed"
            work_plan.updated_at = datetime.utcnow()
            db.add(work_plan)
            db.commit()
            return

        # Conduct weekly review
        service = CustomerAnalysisService(db)

        try:
            weekly_review = await service.conduct_weekly_review(
                analysis_session_id=analysis_session.id,
                work_plan_id=work_plan.id,
                week_number=current_week
            )

            logger.info(f"Completed weekly review {weekly_review.review_id} for week {current_week}")

            # Update work plan
            work_plan.current_week = current_week + 1
            work_plan.updated_at = datetime.utcnow()
            db.add(work_plan)

            # Update next weekly review time
            analysis_session.next_weekly_review_at = datetime.utcnow() + timedelta(days=7)
            analysis_session.updated_at = datetime.utcnow()
            db.add(analysis_session)

            db.commit()

            # Send notification if enabled
            if settings and settings.notify_on_weekly_review:
                await self._send_weekly_review_notification(
                    db=db,
                    campaigner_id=work_plan.campaigner_id,
                    review=weekly_review,
                    settings=settings
                )

        except Exception as e:
            logger.error(f"Error conducting weekly review: {str(e)}", exc_info=True)
            db.rollback()

    async def run_quarterly_checks(self):
        """
        Check for analysis sessions that need quarterly re-analysis.

        This is executed daily at 1 AM.
        """
        logger.info("Running quarterly re-analysis checks")

        try:
            engine = create_engine(self.settings.database_url)
            with Session(engine) as db:
                # Get analysis sessions that need quarterly re-analysis
                sessions_due = db.exec(
                    select(CustomerAnalysisSession)
                    .where(CustomerAnalysisSession.status == "completed")
                    .where(CustomerAnalysisSession.next_quarterly_analysis_at <= datetime.utcnow())
                ).all()

                logger.info(f"Found {len(sessions_due)} sessions due for quarterly re-analysis")

                for session in sessions_due:
                    try:
                        await self._conduct_quarterly_reanalysis(db, session)
                    except Exception as e:
                        logger.error(
                            f"Error conducting quarterly re-analysis for session {session.session_id}: {str(e)}",
                            exc_info=True
                        )

        except Exception as e:
            logger.error(f"Error in run_quarterly_checks: {str(e)}", exc_info=True)

    async def _conduct_quarterly_reanalysis(self, db: Session, session: CustomerAnalysisSession):
        """Conduct quarterly re-analysis for a session."""
        # Check if campaigner has quarterly re-analysis enabled
        settings = db.exec(
            select(AnalysisSettings)
            .where(AnalysisSettings.campaigner_id == session.campaigner_id)
        ).first()

        if settings and not settings.auto_quarterly_reanalysis:
            logger.info(f"Quarterly re-analysis disabled for campaigner {session.campaigner_id}")
            # Update next quarterly time anyway
            session.next_quarterly_analysis_at = datetime.utcnow() + timedelta(days=90)
            session.updated_at = datetime.utcnow()
            db.add(session)
            db.commit()
            return

        logger.info(f"Conducting quarterly re-analysis for session {session.session_id}")

        # Trigger new analysis
        service = CustomerAnalysisService(db)

        try:
            result = await service.conduct_analysis(
                campaigner_id=session.campaigner_id,
                customer_id=session.customer_id,
                analysis_type="quarterly",
                trigger_source="scheduled",
                previous_session_id=session.session_id,
                streaming=False
            )

            logger.info(f"Completed quarterly re-analysis: {result.get('session_id')}")

            # Update original session's next quarterly time
            session.next_quarterly_analysis_at = datetime.utcnow() + timedelta(days=90)
            session.updated_at = datetime.utcnow()
            db.add(session)
            db.commit()

            # Send notification if enabled
            if settings and settings.notify_on_quarterly_reanalysis:
                await self._send_quarterly_notification(
                    db=db,
                    campaigner_id=session.campaigner_id,
                    new_session_id=result.get("session_id"),
                    settings=settings
                )

        except Exception as e:
            logger.error(f"Error conducting quarterly re-analysis: {str(e)}", exc_info=True)
            db.rollback()

    async def _send_weekly_review_notification(
        self,
        db: Session,
        campaigner_id: int,
        review,
        settings: AnalysisSettings
    ):
        """Send weekly review notification email."""
        # TODO: Implement email notification
        logger.info(f"Sending weekly review notification for review {review.review_id}")

        # Placeholder for email service integration
        # from app.services.email_service import send_email
        # send_email(
        #     to=settings.notification_emails,
        #     subject=f"Weekly Review - Week {review.week_number}",
        #     body=review.full_review_markdown
        # )

    async def _send_quarterly_notification(
        self,
        db: Session,
        campaigner_id: int,
        new_session_id: str,
        settings: AnalysisSettings
    ):
        """Send quarterly re-analysis notification email."""
        # TODO: Implement email notification
        logger.info(f"Sending quarterly re-analysis notification for session {new_session_id}")

        # Placeholder for email service integration

    def schedule_analysis_on_date(
        self,
        campaigner_id: int,
        customer_id: Optional[int],
        scheduled_date: datetime,
        analysis_type: str = "manual"
    ):
        """
        Schedule a customer analysis for a specific date.

        Args:
            campaigner_id: The campaigner ID
            customer_id: Optional customer ID
            scheduled_date: When to run the analysis
            analysis_type: Type of analysis
        """
        job_id = f"scheduled_analysis_{campaigner_id}_{customer_id}_{scheduled_date.isoformat()}"

        self.scheduler.add_job(
            self._run_scheduled_analysis,
            DateTrigger(run_date=scheduled_date),
            args=[campaigner_id, customer_id, analysis_type],
            id=job_id,
            replace_existing=True
        )

        logger.info(
            f"Scheduled analysis for campaigner {campaigner_id}, "
            f"customer {customer_id} at {scheduled_date}"
        )

    async def _run_scheduled_analysis(
        self,
        campaigner_id: int,
        customer_id: Optional[int],
        analysis_type: str
    ):
        """Run a scheduled analysis."""
        logger.info(f"Running scheduled analysis for campaigner {campaigner_id}")

        try:
            engine = create_engine(self.settings.database_url)
            with Session(engine) as db:
                service = CustomerAnalysisService(db)

                await service.conduct_analysis(
                    campaigner_id=campaigner_id,
                    customer_id=customer_id,
                    analysis_type=analysis_type,
                    trigger_source="scheduled",
                    streaming=False
                )

        except Exception as e:
            logger.error(f"Error in scheduled analysis: {str(e)}", exc_info=True)


# Global scheduler instance
_scheduler_instance: Optional[CustomerAnalysisScheduler] = None


def get_scheduler() -> CustomerAnalysisScheduler:
    """Get or create the global scheduler instance."""
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = CustomerAnalysisScheduler()
    return _scheduler_instance


def start_scheduler():
    """Start the global scheduler."""
    scheduler = get_scheduler()
    scheduler.start()


def stop_scheduler():
    """Stop the global scheduler."""
    scheduler = get_scheduler()
    scheduler.stop()
