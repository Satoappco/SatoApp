"""Tests for SingleAnalyticsAgent event loop handling."""

import pytest
import asyncio
from unittest.mock import Mock, patch, MagicMock
from app.core.agents.graph.agents import SingleAnalyticsAgent


class TestSingleAnalyticsAgentEventLoop:
    """Test that SingleAnalyticsAgent handles event loops correctly."""

    @patch('app.core.agents.customer_credentials.get_session')
    def test_execute_without_event_loop(self, mock_get_session):
        """Test execute() works when there's no running event loop."""
        # Setup mock
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__.return_value = mock_session
        mock_session.exec.return_value.all.return_value = []

        llm = Mock()
        agent = SingleAnalyticsAgent(llm)

        # Mock _execute_async to avoid MCP initialization
        async def mock_execute_async(task):
            return {
                "status": "success",
                "result": "Test result",
                "error": None
            }

        with patch.object(agent, '_execute_async', side_effect=mock_execute_async):
            # Should not raise RuntimeError
            result = agent.execute({"query": "test", "customer_id": 4, "campaigner_id": 1})

            assert result["status"] == "success"
            assert result["result"] == "Test result"

    @pytest.mark.asyncio
    @patch('app.core.agents.customer_credentials.get_session')
    async def test_execute_with_running_event_loop(self, mock_get_session):
        """Test execute() works when called from within a running event loop."""
        # Setup mock
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__.return_value = mock_session
        mock_session.exec.return_value.all.return_value = []

        llm = Mock()
        agent = SingleAnalyticsAgent(llm)

        # Mock _execute_async to avoid MCP initialization
        async def mock_execute_async(task):
            return {
                "status": "success",
                "result": "Test result from async context",
                "error": None
            }

        with patch.object(agent, '_execute_async', side_effect=mock_execute_async):
            # Call execute() from within an async context (running event loop)
            # This should use ThreadPoolExecutor to avoid RuntimeError
            result = agent.execute({"query": "test", "customer_id": 4, "campaigner_id": 1})

            assert result["status"] == "success"
            assert result["result"] == "Test result from async context"

    @pytest.mark.asyncio
    @patch('app.core.agents.customer_credentials.get_session')
    async def test_execute_in_async_function(self, mock_get_session):
        """Test execute() can be called from within an async function."""
        # Setup mock
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__.return_value = mock_session
        mock_session.exec.return_value.all.return_value = []

        llm = Mock()
        agent = SingleAnalyticsAgent(llm)

        # Mock _execute_async
        async def mock_execute_async(task):
            await asyncio.sleep(0.01)  # Simulate async work
            return {
                "status": "success",
                "result": "Async result",
                "error": None
            }

        with patch.object(agent, '_execute_async', side_effect=mock_execute_async):
            # This mimics how the graph node calls agent.execute()
            # The node itself might be in an async context
            result = agent.execute({"query": "test", "customer_id": 4, "campaigner_id": 1})

            assert result["status"] == "success"
            assert result["result"] == "Async result"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
