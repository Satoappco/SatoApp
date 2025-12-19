"""
Tests for Customer Analysis Service.
"""

import pytest
from datetime import datetime
from sqlmodel import Session, create_engine, SQLModel
from sqlalchemy.pool import StaticPool

from app.services.customer_analysis_service import CustomerAnalysisService
from app.models.customer_analysis import (
    CustomerAnalysisSession,
    AnalysisSettings,
    WorkPlan,
    WorkPlanTask
)
from app.models.users import Campaigner, Customer


@pytest.fixture(name="engine")
def engine_fixture():
    """Create in-memory SQLite engine for testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture(name="session")
def session_fixture(engine):
    """Create a database session for testing."""
    with Session(engine) as session:
        yield session


@pytest.fixture(name="agency")
def agency_fixture(session: Session):
    """Create a test agency."""
    from app.models.users import Agency
    agency = Agency(
        name="Test Agency",
        email="agency@example.com"
    )
    session.add(agency)
    session.commit()
    session.refresh(agency)
    return agency


@pytest.fixture(name="campaigner")
def campaigner_fixture(session: Session, agency):
    """Create a test campaigner."""
    campaigner = Campaigner(
        email="test@example.com",
        name="Test Campaigner",
        hashed_password="dummy_hash",
        role="admin",
        agency_id=agency.id
    )
    session.add(campaigner)
    session.commit()
    session.refresh(campaigner)
    return campaigner


@pytest.fixture(name="customer")
def customer_fixture(session: Session, campaigner: Campaigner, agency):
    """Create a test customer."""
    customer = Customer(
        full_name="Test Business",
        website_url="https://example.com",
        agency_id=agency.id,
        primary_campaigner_id=campaigner.id
    )
    session.add(customer)
    session.commit()
    session.refresh(customer)
    return customer


@pytest.fixture(name="service")
def service_fixture(session: Session):
    """Create a CustomerAnalysisService instance."""
    return CustomerAnalysisService(session)


class TestAnalysisSettings:
    """Tests for analysis settings management."""

    def test_get_or_create_analysis_settings_creates_new(
        self, service: CustomerAnalysisService, campaigner: Campaigner
    ):
        """Test creating new analysis settings."""
        settings = service.get_or_create_analysis_settings(campaigner.id)

        assert settings.campaigner_id == campaigner.id
        assert settings.auto_analysis_on_create is False
        assert settings.auto_weekly_reviews is True
        assert settings.auto_quarterly_reanalysis is True
        assert settings.weekly_review_day == "monday"
        assert settings.weekly_review_time == "09:00"
        assert settings.default_research_depth == "medium"

    def test_get_or_create_analysis_settings_gets_existing(
        self, service: CustomerAnalysisService, campaigner: Campaigner, session: Session
    ):
        """Test getting existing analysis settings."""
        # Create settings manually
        settings = AnalysisSettings(
            campaigner_id=campaigner.id,
            auto_analysis_on_create=True,
            auto_weekly_reviews=False
        )
        session.add(settings)
        session.commit()

        # Get settings
        retrieved = service.get_or_create_analysis_settings(campaigner.id)

        assert retrieved.id == settings.id
        assert retrieved.auto_analysis_on_create is True
        assert retrieved.auto_weekly_reviews is False

    def test_update_analysis_settings(
        self, service: CustomerAnalysisService, campaigner: Campaigner
    ):
        """Test updating analysis settings."""
        # Create initial settings
        service.get_or_create_analysis_settings(campaigner.id)

        # Update settings
        updated = service.update_analysis_settings(
            campaigner_id=campaigner.id,
            settings_data={
                "auto_analysis_on_create": True,
                "weekly_review_day": "tuesday",
                "default_research_depth": "deep"
            }
        )

        assert updated.auto_analysis_on_create is True
        assert updated.weekly_review_day == "tuesday"
        assert updated.default_research_depth == "deep"
        # Other fields should remain unchanged
        assert updated.auto_weekly_reviews is True


class TestAnalysisSession:
    """Tests for analysis session management."""

    def test_create_analysis_session(
        self, service: CustomerAnalysisService, campaigner: Campaigner, customer: Customer
    ):
        """Test creating an analysis session."""
        session = service.create_analysis_session(
            campaigner_id=campaigner.id,
            customer_id=customer.id,
            analysis_type="initial",
            trigger_source="manual"
        )

        assert session.session_id.startswith("ca_")
        assert session.campaigner_id == campaigner.id
        assert session.customer_id == customer.id
        assert session.analysis_type == "initial"
        assert session.trigger_source == "manual"
        assert session.status == "pending"
        assert session.next_quarterly_analysis_at is not None
        assert session.next_weekly_review_at is not None

    def test_get_analysis_session(
        self, service: CustomerAnalysisService, campaigner: Campaigner, customer: Customer
    ):
        """Test getting an analysis session."""
        created = service.create_analysis_session(
            campaigner_id=campaigner.id,
            customer_id=customer.id,
            analysis_type="manual",
            trigger_source="manual"
        )

        retrieved = service.get_analysis_session(
            session_id=created.session_id,
            campaigner_id=campaigner.id
        )

        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.session_id == created.session_id

    def test_get_analysis_session_wrong_campaigner(
        self, service: CustomerAnalysisService, campaigner: Campaigner, customer: Customer, session: Session
    ):
        """Test that getting session with wrong campaigner returns None."""
        created = service.create_analysis_session(
            campaigner_id=campaigner.id,
            customer_id=customer.id,
            analysis_type="manual",
            trigger_source="manual"
        )

        # Create another campaigner
        other_campaigner = Campaigner(
            email="other@example.com",
            name="Other Campaigner",
            hashed_password="dummy_hash",
            role="user"
        )
        session.add(other_campaigner)
        session.commit()

        # Try to get session with wrong campaigner
        retrieved = service.get_analysis_session(
            session_id=created.session_id,
            campaigner_id=other_campaigner.id
        )

        assert retrieved is None

    def test_list_analysis_sessions(
        self, service: CustomerAnalysisService, campaigner: Campaigner, customer: Customer
    ):
        """Test listing analysis sessions."""
        # Create multiple sessions
        session1 = service.create_analysis_session(
            campaigner_id=campaigner.id,
            customer_id=customer.id,
            analysis_type="initial",
            trigger_source="auto_onboarding"
        )
        session2 = service.create_analysis_session(
            campaigner_id=campaigner.id,
            customer_id=customer.id,
            analysis_type="quarterly",
            trigger_source="scheduled"
        )
        session3 = service.create_analysis_session(
            campaigner_id=campaigner.id,
            customer_id=None,
            analysis_type="manual",
            trigger_source="manual"
        )

        # List all sessions
        sessions = service.list_analysis_sessions(campaigner_id=campaigner.id)
        assert len(sessions) == 3

        # List by customer
        customer_sessions = service.list_analysis_sessions(
            campaigner_id=campaigner.id,
            customer_id=customer.id
        )
        assert len(customer_sessions) == 2

        # List by status
        pending_sessions = service.list_analysis_sessions(
            campaigner_id=campaigner.id,
            status="pending"
        )
        assert len(pending_sessions) == 3


class TestWorkPlan:
    """Tests for work plan management."""

    def test_create_work_plan_from_result(
        self, service: CustomerAnalysisService, campaigner: Campaigner, customer: Customer
    ):
        """Test creating a work plan from analysis results."""
        # Create analysis session
        analysis_session = service.create_analysis_session(
            campaigner_id=campaigner.id,
            customer_id=customer.id,
            analysis_type="initial",
            trigger_source="manual"
        )

        # Create work plan
        work_plan_data = {
            "period_weeks": 8,
            "tasks_by_week": {
                "week_1": [
                    {
                        "category": "campaign_optimization",
                        "title": "Review Google Ads campaigns",
                        "description": "Analyze current Google Ads performance",
                        "priority": "high",
                        "impact": "high",
                        "effort": "medium"
                    }
                ],
                "week_2": [
                    {
                        "category": "content_creation",
                        "title": "Create new ad copy",
                        "description": "Write 5 new ad variations",
                        "priority": "medium",
                        "impact": "medium",
                        "effort": "low"
                    }
                ]
            }
        }

        work_plan = service._create_work_plan_from_result(
            session=analysis_session,
            work_plan_data=work_plan_data
        )

        assert work_plan.plan_id.startswith("wp_")
        assert work_plan.analysis_session_id == analysis_session.id
        assert work_plan.campaigner_id == campaigner.id
        assert work_plan.status == "active"
        assert work_plan.plan_period_weeks == 8
        assert work_plan.total_tasks == 2

    def test_get_active_work_plan(
        self, service: CustomerAnalysisService, campaigner: Campaigner, customer: Customer
    ):
        """Test getting the active work plan."""
        # Create analysis session and work plan
        analysis_session = service.create_analysis_session(
            campaigner_id=campaigner.id,
            customer_id=customer.id,
            analysis_type="initial",
            trigger_source="manual"
        )

        work_plan = service._create_work_plan_from_result(
            session=analysis_session,
            work_plan_data={"period_weeks": 8, "tasks_by_week": {}}
        )

        # Get active work plan
        active_plan = service.get_active_work_plan(
            campaigner_id=campaigner.id,
            customer_id=customer.id
        )

        assert active_plan is not None
        assert active_plan.id == work_plan.id

    def test_get_work_plan_tasks(
        self, service: CustomerAnalysisService, campaigner: Campaigner, customer: Customer
    ):
        """Test getting work plan tasks."""
        # Create work plan with tasks
        analysis_session = service.create_analysis_session(
            campaigner_id=campaigner.id,
            customer_id=customer.id,
            analysis_type="initial",
            trigger_source="manual"
        )

        work_plan_data = {
            "period_weeks": 4,
            "tasks_by_week": {
                "week_1": [{"category": "test", "title": "Task 1", "description": "Test task 1", "priority": "high", "impact": "high", "effort": "low"}],
                "week_2": [{"category": "test", "title": "Task 2", "description": "Test task 2", "priority": "medium", "impact": "medium", "effort": "medium"}],
            }
        }

        work_plan = service._create_work_plan_from_result(
            session=analysis_session,
            work_plan_data=work_plan_data
        )

        # Get all tasks
        all_tasks = service.get_work_plan_tasks(work_plan_id=work_plan.id)
        assert len(all_tasks) == 2

        # Get tasks by week
        week1_tasks = service.get_work_plan_tasks(work_plan_id=work_plan.id, week_number=1)
        assert len(week1_tasks) == 1
        assert week1_tasks[0].title == "Task 1"

    def test_update_task_status(
        self, service: CustomerAnalysisService, campaigner: Campaigner, customer: Customer
    ):
        """Test updating task status."""
        # Create work plan with a task
        analysis_session = service.create_analysis_session(
            campaigner_id=campaigner.id,
            customer_id=customer.id,
            analysis_type="initial",
            trigger_source="manual"
        )

        work_plan_data = {
            "period_weeks": 4,
            "tasks_by_week": {
                "week_1": [{"category": "test", "title": "Task 1", "description": "Test task", "priority": "high", "impact": "high", "effort": "low"}]
            }
        }

        work_plan = service._create_work_plan_from_result(
            session=analysis_session,
            work_plan_data=work_plan_data
        )

        tasks = service.get_work_plan_tasks(work_plan_id=work_plan.id)
        task = tasks[0]

        # Update status to in_progress
        updated = service.update_task_status(
            task_id=task.task_id,
            status="in_progress",
            note="Started working on this"
        )

        assert updated.status == "in_progress"
        assert updated.started_at is not None
        assert len(updated.review_notes) == 1
        assert "Started working on this" in updated.review_notes[0]["note"]

        # Update status to completed
        completed = service.update_task_status(
            task_id=task.task_id,
            status="completed",
            note="Finished the task"
        )

        assert completed.status == "completed"
        assert completed.completed_at is not None
        assert len(completed.review_notes) == 2

        # Check work plan progress was updated
        service.db.refresh(work_plan)
        assert work_plan.completed_tasks == 1
        assert work_plan.progress_percent == 100.0


class TestAsyncAnalysis:
    """Tests for async analysis execution."""

    @pytest.mark.asyncio
    async def test_conduct_analysis_creates_session(
        self, service: CustomerAnalysisService, campaigner: Campaigner, customer: Customer
    ):
        """Test that conducting analysis creates a session."""
        result = await service.conduct_analysis(
            campaigner_id=campaigner.id,
            customer_id=customer.id,
            analysis_type="initial",
            trigger_source="manual",
            streaming=False
        )

        assert result["success"] is True
        assert "session_id" in result
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_conduct_analysis_invalid_customer(
        self, service: CustomerAnalysisService, campaigner: Campaigner
    ):
        """Test that conducting analysis with invalid customer raises error."""
        with pytest.raises(ValueError, match="Customer .* not found"):
            await service.conduct_analysis(
                campaigner_id=campaigner.id,
                customer_id=99999,  # Non-existent customer
                analysis_type="initial",
                trigger_source="manual",
                streaming=False
            )
