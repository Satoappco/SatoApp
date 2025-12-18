"""
Integration tests for Deep Research feature.

Tests the full integration from API route -> Service -> MCP Server -> Database.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from sqlmodel import SQLModel, create_engine, Session
from app.services.deep_research_service import DeepResearchService
from app.core.agents.graph.deep_research_agent import DeepResearchAgent
from langchain_openai import ChatOpenAI


@pytest.fixture(scope="function")
def test_engine():
    """Create an in-memory SQLite engine for testing."""
    engine = create_engine("sqlite:///:memory:", echo=False)

    # Create all tables
    SQLModel.metadata.create_all(engine)

    yield engine

    # Cleanup
    SQLModel.metadata.drop_all(engine)


@pytest.fixture(scope="function")
def test_session(test_engine):
    """Create a test database session."""
    with Session(test_engine) as session:
        yield session


class TestDeepResearchService:
    """Test DeepResearchService integration with MCP server."""

    @pytest.fixture
    def service(self, test_session):
        """Create DeepResearchService instance with test session."""
        return DeepResearchService(session=test_session)

    @pytest.fixture
    def mock_mcp_response(self):
        """Mock successful MCP server response."""
        return {
            "success": True,
            "report": "# Test Research Report\n\nThis is a test report.",
            "sources": [
                {
                    "url": "https://example.com/source1",
                    "title": "Test Source 1",
                    "relevance_score": 0.95
                }
            ],
            "execution_time_ms": 1500,
            "tokens_used": 500,
            "steps_completed": 3
        }

    def test_create_research_session(self, service):
        """Test creating a research session in database."""
        session = service.create_research_session(
            query="Test research query",
            campaigner_id=1,
            customer_id=1,
            thread_id="test-thread-123",
            config={"search_provider": "tavily", "research_depth": "shallow"}
        )

        assert session is not None
        assert session.session_id.startswith("res_")
        assert session.query == "Test research query"
        assert session.campaigner_id == 1
        assert session.status == "pending"
        assert session.config["search_provider"] == "tavily"

    @patch('httpx.Client')
    def test_conduct_research_success(self, mock_client_class, service, mock_mcp_response):
        """Test successful research execution via MCP server."""
        # Mock MCP client responses
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        # Mock initialize response
        init_response = Mock()
        init_response.json.return_value = {"session_id": "mcp-session-123"}
        init_response.raise_for_status = Mock()
        mock_client.post.return_value = init_response

        # Mock research response
        research_response = Mock()
        research_response.json.return_value = mock_mcp_response
        research_response.raise_for_status = Mock()

        # Setup post to return different responses for different URLs
        def post_side_effect(url, *args, **kwargs):
            if "/initialize" in url:
                return init_response
            elif "/research/" in url:
                return research_response
            return Mock()

        mock_client.post.side_effect = post_side_effect

        # Execute research
        result = service.conduct_research(
            query="What are the latest AI trends?",
            campaigner_id=1,
            customer_id=1,
            thread_id="test-thread-456",
            config={"search_provider": "tavily", "research_depth": "medium"}
        )

        # Verify result
        assert result["success"] is True
        assert "Test Research Report" in result["report"]
        assert len(result["sources"]) == 1
        assert result["sources"][0]["url"] == "https://example.com/source1"
        assert result["tokens_used"] == 500

        # Verify MCP client was called correctly
        assert mock_client.post.call_count >= 2  # initialize + research
        assert mock_client.delete.called  # cleanup

    @patch('httpx.Client')
    def test_conduct_research_mcp_server_error(self, mock_client_class, service):
        """Test handling of MCP server errors."""
        # Mock MCP client that raises error
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.post.side_effect = Exception("MCP server connection failed")

        # Execute research
        result = service.conduct_research(
            query="Test query",
            campaigner_id=1,
            config={}
        )

        # Verify error handling
        assert result["success"] is False
        assert "MCP server connection failed" in result["error"]
        assert result["session_id"].startswith("res_")

    def test_get_research_session(self, test_session):
        """Test retrieving research session by ID."""
        service = DeepResearchService(session=test_session)

        # Create session
        created = service.create_research_session(
            query="Test query",
            campaigner_id=1
        )

        # Retrieve session
        retrieved = service.get_research_session(created.session_id)

        assert retrieved is not None
        assert retrieved.session_id == created.session_id
        assert retrieved.query == "Test query"

    def test_update_research_session(self, test_session):
        """Test updating research session with results."""
        service = DeepResearchService(session=test_session)

        # Create session
        session = service.create_research_session(
            query="Test query",
            campaigner_id=1
        )

        # Update session
        updated = service.update_research_session(
            session_id=session.session_id,
            status="completed",
            final_report="# Final Report\n\nResults here.",
            total_execution_time_ms=2500,
            tokens_used=1000
        )

        assert updated is not None
        assert updated.status == "completed"
        assert updated.final_report == "# Final Report\n\nResults here."
        assert updated.total_execution_time_ms == 2500
        assert updated.tokens_used == 1000


class TestDeepResearchAgent:
    """Test DeepResearchAgent integration."""

    @pytest.fixture
    def agent(self):
        """Create DeepResearchAgent instance."""
        llm = ChatOpenAI(model="gpt-4o-mini")
        return DeepResearchAgent(llm)

    @patch.object(DeepResearchService, 'conduct_research')
    def test_agent_execute_success(self, mock_conduct, agent):
        """Test agent execution with successful research."""
        mock_conduct.return_value = {
            "success": True,
            "session_id": "res_test123",
            "report": "# Research Results\n\nFindings here.",
            "sources": [{"url": "https://example.com", "title": "Example"}],
            "execution_time_ms": 3000,
            "tokens_used": 1500
        }

        # Execute agent
        result = agent.execute({
            "query": "Research AI trends",
            "campaigner_id": 1,
            "customer_id": 1,
            "thread_id": "thread-789",
            "config": {"research_depth": "medium"}
        })

        # Verify result
        assert result["status"] == "completed"
        assert result["agent"] == "deep_research_agent"
        assert "Research Results" in result["report"]
        assert result["session_id"] == "res_test123"
        assert len(result["sources"]) == 1

        # Verify service was called correctly
        mock_conduct.assert_called_once()
        call_kwargs = mock_conduct.call_args[1]
        assert call_kwargs["query"] == "Research AI trends"
        assert call_kwargs["campaigner_id"] == 1

    @patch.object(DeepResearchService, 'conduct_research')
    def test_agent_execute_error(self, mock_conduct, agent):
        """Test agent execution with research error."""
        mock_conduct.return_value = {
            "success": False,
            "session_id": "res_test456",
            "error": "Research execution failed",
            "execution_time_ms": 500
        }

        # Execute agent
        result = agent.execute({
            "query": "Research topic",
            "campaigner_id": 1
        })

        # Verify error handling
        assert result["status"] == "error"
        assert result["agent"] == "deep_research_agent"
        # Check error message in the right field
        error_msg = result.get("error") or result.get("message", "")
        assert "Research execution failed" in error_msg

    def test_agent_execute_missing_query(self, agent):
        """Test agent execution with missing required fields."""
        result = agent.execute({
            "campaigner_id": 1
        })

        assert result["status"] == "error"
        assert "query" in result["error"].lower()

    def test_agent_execute_missing_campaigner_id(self, agent):
        """Test agent execution with missing campaigner_id."""
        result = agent.execute({
            "query": "Test query"
        })

        assert result["status"] == "error"
        assert "campaigner" in result["error"].lower()


class TestDeepResearchIntegration:
    """End-to-end integration tests."""

    @pytest.mark.integration
    @patch('httpx.Client')
    def test_full_research_workflow(self, mock_client_class, test_session):
        """Test complete workflow from agent to database."""
        # Setup mocks
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        init_response = Mock()
        init_response.json.return_value = {"session_id": "mcp-session-xyz"}
        init_response.raise_for_status = Mock()

        research_response = Mock()
        research_response.json.return_value = {
            "success": True,
            "report": "# Full Integration Test Report\n\nComplete results.",
            "sources": [{"url": "https://test.com", "title": "Test Source"}],
            "execution_time_ms": 2000,
            "tokens_used": 800,
            "steps_completed": 5
        }
        research_response.raise_for_status = Mock()

        def post_side_effect(url, *args, **kwargs):
            if "/initialize" in url:
                return init_response
            return research_response

        mock_client.post.side_effect = post_side_effect

        # Execute full workflow with test session
        llm = ChatOpenAI(model="gpt-4o-mini")
        agent = DeepResearchAgent(llm)

        # Patch the service to use test session
        with patch.object(DeepResearchService, '_get_session', return_value=test_session):
            with patch.object(DeepResearchService, '_close_session'):
                result = agent.execute({
                    "query": "Comprehensive AI research",
                    "campaigner_id": 1,
                    "customer_id": 1,
                    "thread_id": "integration-test-thread",
                    "config": {
                        "research_depth": "deep",
                        "search_provider": "tavily",
                        "max_iterations": 7
                    }
                })

                # Verify end-to-end result
                assert result["status"] == "completed"
                assert result["report"] is not None
                assert "Full Integration Test Report" in result["report"]
                assert len(result["sources"]) == 1

                # Verify database session was created
                service = DeepResearchService(session=test_session)
                session = service.get_research_session(result["session_id"])
                assert session is not None
                assert session.status == "completed"
                assert session.final_report is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
