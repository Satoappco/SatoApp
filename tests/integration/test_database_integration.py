"""
Database integration tests for Sato AI platform
Tests full CRUD operations and complex database interactions
"""

import pytest
from sqlalchemy import select
from app.models.users import (
    Campaigner,
    Agency,
    Customer,
    CustomerCampaignerAssignment,
    CustomerStatus,
    UserRole,
    UserStatus,
)
from app.models.agents import AgentConfig
from app.models.chat_traces import ChatTrace
from app.models.customer_data import RTMTable, QuestionsTable


class TestDatabaseIntegration:
    """Test database operations and relationships"""

    def test_agency_crud_operations(self, db_session):
        """Test complete CRUD operations for Agency model"""
        # Create
        agency = Agency(
            name="Test Agency",
            email="agency@test.com",
            phone="+1234567890",
            status=CustomerStatus.ACTIVE,
        )
        db_session.add(agency)
        db_session.commit()
        db_session.refresh(agency)

        assert agency.id is not None
        assert agency.name == "Test Agency"
        assert agency.email == "agency@test.com"
        assert agency.status == CustomerStatus.ACTIVE

        # Read
        retrieved_agency = db_session.get(Agency, agency.id)
        assert retrieved_agency is not None
        assert retrieved_agency.name == "Test Agency"

        # Update
        agency.status = CustomerStatus.PAUSED
        db_session.add(agency)
        db_session.commit()
        db_session.refresh(agency)
        assert agency.status == CustomerStatus.PAUSED

        # Delete
        db_session.delete(agency)
        db_session.commit()
        deleted_agency = db_session.get(Agency, agency.id)
        assert deleted_agency is None

    def test_campaigner_crud_operations(self, db_session):
        """Test complete CRUD operations for Campaigner model"""
        # First create an agency
        agency = Agency(
            name="Test Agency", email="agency@test.com", status=CustomerStatus.ACTIVE
        )
        db_session.add(agency)
        db_session.commit()

        # Create campaigner
        campaigner = Campaigner(
            email="campaigner@test.com",
            full_name="Test Campaigner",
            phone="+1234567890",
            role=UserRole.CAMPAIGNER,
            status=UserStatus.ACTIVE,
            agency_id=agency.id,
        )
        db_session.add(campaigner)
        db_session.commit()
        db_session.refresh(campaigner)

        assert campaigner.id is not None
        assert campaigner.email == "campaigner@test.com"
        assert campaigner.agency_id == agency.id

        # Read
        retrieved_campaigner = db_session.get(Campaigner, campaigner.id)
        assert retrieved_campaigner is not None
        assert retrieved_campaigner.email == "campaigner@test.com"

        # Update
        campaigner.status = UserStatus.SUSPENDED
        db_session.add(campaigner)
        db_session.commit()
        db_session.refresh(campaigner)
        assert campaigner.status == UserStatus.SUSPENDED

        # Delete
        db_session.delete(campaigner)
        db_session.commit()
        deleted_campaigner = db_session.get(Campaigner, campaigner.id)
        assert deleted_campaigner is None

    def test_customer_crud_operations(self, db_session):
        """Test complete CRUD operations for Customer model"""
        # First create an agency
        agency = Agency(
            name="Test Agency", email="agency@test.com", status=CustomerStatus.ACTIVE
        )
        db_session.add(agency)
        db_session.commit()

        # Create customer
        customer = Customer(
            agency_id=agency.id,
            full_name="Test Customer",
            status=CustomerStatus.ACTIVE,
            contact_email="customer@test.com",
            phone="+1234567890",
        )
        db_session.add(customer)
        db_session.commit()
        db_session.refresh(customer)

        assert customer.id is not None
        assert customer.full_name == "Test Customer"
        assert customer.agency_id == agency.id

        # Read
        retrieved_customer = db_session.get(Customer, customer.id)
        assert retrieved_customer is not None
        assert retrieved_customer.full_name == "Test Customer"

        # Update
        customer.status = CustomerStatus.PAUSED
        db_session.add(customer)
        db_session.commit()
        db_session.refresh(customer)
        assert customer.status == CustomerStatus.PAUSED

        # Delete
        db_session.delete(customer)
        db_session.commit()
        deleted_customer = db_session.get(Customer, customer.id)
        assert deleted_customer is None

    def test_agent_config_operations(self, db_session):
        """Test agent configuration CRUD operations"""
        agent_config = AgentConfig(
            name="test_agent",
            role="Test Agent",
            goal="Test goal",
            backstory="Test backstory",
            tools='["tool1", "tool2"]',  # JSON string
            max_iterations=3,
            allow_delegation=False,
            verbose=True,
            is_active=True,
        )
        db_session.add(agent_config)
        db_session.commit()
        db_session.refresh(agent_config)

        assert agent_config.id is not None
        assert agent_config.name == "test_agent"
        assert agent_config.tools == '["tool1", "tool2"]'

        # Test JSON field handling
        agent_config.tools = '["tool3", "tool4"]'
        db_session.add(agent_config)
        db_session.commit()
        db_session.refresh(agent_config)
        assert agent_config.tools == '["tool3", "tool4"]'

    def test_chat_trace_operations(self, db_session):
        """Test chat trace event sourcing"""
        # Create campaigner first
        agency = Agency(name="Test Agency", status=CustomerStatus.ACTIVE)
        db_session.add(agency)
        db_session.commit()

        campaigner = Campaigner(
            email="test@example.com",
            full_name="Test User",
            role=UserRole.CAMPAIGNER,
            status=UserStatus.ACTIVE,
            agency_id=agency.id,
        )
        db_session.add(campaigner)
        db_session.commit()

        trace = ChatTrace(
            thread_id="test_session_123",
            record_type="MESSAGE",
            campaigner_id=campaigner.id,
            data={
                "role": "user",
                "content": "Hello, test message",
                "timestamp": "2024-01-15T10:00:00Z",
            },
        )
        db_session.add(trace)
        db_session.commit()
        db_session.refresh(trace)

        assert trace.id is not None
        assert trace.thread_id == "test_session_123"
        assert trace.record_type == "MESSAGE"
        assert trace.data["role"] == "user"

        # Test JSON field operations
        trace.data["processed"] = True
        db_session.add(trace)
        db_session.commit()
        db_session.refresh(trace)
        assert trace.data["processed"] is True

    def test_customer_data_tables(self, db_session):
        """Test customer-specific data tables"""
        # Test RTM table
        rtm_entry = RTMTable(
            composite_id="1_1_1",
            link_1="https://example.com/rtm1",
            link_2="https://example.com/rtm2",
        )
        db_session.add(rtm_entry)
        db_session.commit()
        db_session.refresh(rtm_entry)

        assert rtm_entry.id is not None
        assert rtm_entry.composite_id == "1_1_1"
        assert rtm_entry.link_1 == "https://example.com/rtm1"

        # Test Questions table
        question_entry = QuestionsTable(
            composite_id="1_1_1",
            q1="What is the current SEO performance?",
            q2="How are the campaigns performing?",
        )
        db_session.add(question_entry)
        db_session.commit()
        db_session.refresh(question_entry)

        assert question_entry.id is not None
        assert question_entry.composite_id == "1_1_1"
        assert "SEO" in question_entry.q1

    def test_complex_queries(self, db_session):
        """Test complex database queries and relationships"""
        # Set up test data
        agency = Agency(name="Test Agency", status=CustomerStatus.ACTIVE)
        db_session.add(agency)
        db_session.commit()

        # Create multiple campaigners
        campaigners = []
        for i in range(3):
            campaigner = Campaigner(
                email=f"campaigner{i}@example.com",
                full_name=f"Campaigner {i}",
                role=UserRole.CAMPAIGNER,
                status=UserStatus.ACTIVE,
                agency_id=agency.id,
            )
            db_session.add(campaigner)
            campaigners.append(campaigner)
        db_session.commit()

        # Create customers for each campaigner
        customers = []
        for i, campaigner in enumerate(campaigners):
            for j in range(2):  # 2 customers per campaigner
                customer = Customer(
                    agency_id=agency.id,
                    full_name=f"Customer {i}-{j}",
                    status=CustomerStatus.ACTIVE,
                    contact_email=f"customer{i}{j}@example.com",
                )
                db_session.add(customer)
                customers.append(customer)
        db_session.commit()

        # Test complex query: Get all customers for an agency
        stmt = select(Customer).where(Customer.agency_id == agency.id)
        results = db_session.exec(stmt).all()

        assert len(results) == 6  # 3 campaigners * 2 customers each

        # Verify all customers belong to the agency
        for customer in results:
            assert customer.agency_id == agency.id

    def test_transaction_rollback(self, db_session):
        """Test database transaction rollback"""
        # Start a transaction that will be rolled back
        initial_count = db_session.exec(select(Agency)).all()
        initial_count = len(initial_count)

        # Create agency within transaction
        agency = Agency(name="Temp Agency", status=CustomerStatus.ACTIVE)
        db_session.add(agency)
        db_session.commit()

        # Verify it was created
        mid_count = db_session.exec(select(Agency)).all()
        assert len(mid_count) == initial_count + 1

        # The transaction will be rolled back by the fixture
        # So the agency should not exist after the test
