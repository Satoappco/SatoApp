"""Tests for CustomerCredentialManager integration with agents."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from app.core.agents.customer_credentials import CustomerCredentialManager
from app.core.agents.graph.agents import AnalyticsCrewPlaceholder, SingleAnalyticsAgent


class TestCredentialManagerIntegration:
    """Test that agents use CustomerCredentialManager correctly."""

    def test_analytics_crew_placeholder_uses_credential_manager(self):
        """Test AnalyticsCrewPlaceholder has credential_manager instance."""
        llm = Mock()
        agent = AnalyticsCrewPlaceholder(llm)

        # Should have credential_manager
        assert hasattr(agent, 'credential_manager')
        assert isinstance(agent.credential_manager, CustomerCredentialManager)

    def test_single_analytics_agent_uses_credential_manager(self):
        """Test SingleAnalyticsAgent has credential_manager instance."""
        llm = Mock()
        agent = SingleAnalyticsAgent(llm)

        # Should have credential_manager
        assert hasattr(agent, 'credential_manager')
        assert isinstance(agent.credential_manager, CustomerCredentialManager)

    @patch('app.core.agents.customer_credentials.get_session')
    def test_analytics_crew_fetch_platforms_delegates_to_manager(self, mock_get_session):
        """Test AnalyticsCrewPlaceholder._fetch_customer_platforms delegates to credential_manager."""
        # Setup mock
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__.return_value = mock_session
        mock_session.exec.return_value.all.return_value = []

        llm = Mock()
        agent = AnalyticsCrewPlaceholder(llm)

        # Spy on credential_manager
        original_method = agent.credential_manager.fetch_customer_platforms
        with patch.object(agent.credential_manager, 'fetch_customer_platforms', wraps=original_method) as spy:
            result = agent._fetch_customer_platforms(4)

            # Should have called credential_manager method
            spy.assert_called_once_with(4)

    @patch('app.core.agents.customer_credentials.get_session')
    def test_single_agent_fetch_platforms_delegates_to_manager(self, mock_get_session):
        """Test SingleAnalyticsAgent._fetch_customer_platforms delegates to credential_manager."""
        # Setup mock
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__.return_value = mock_session
        mock_session.exec.return_value.all.return_value = []

        llm = Mock()
        agent = SingleAnalyticsAgent(llm)

        # Spy on credential_manager
        original_method = agent.credential_manager.fetch_customer_platforms
        with patch.object(agent.credential_manager, 'fetch_customer_platforms', wraps=original_method) as spy:
            result = agent._fetch_customer_platforms(4)

            # Should have called credential_manager method
            spy.assert_called_once_with(4)

    @patch('app.core.agents.customer_credentials.get_session')
    @patch('app.core.agents.customer_credentials.GoogleAdsService')
    def test_analytics_crew_fetch_ga_token_delegates_to_manager(self, mock_service_class, mock_get_session):
        """Test AnalyticsCrewPlaceholder._fetch_google_analytics_token delegates to credential_manager."""
        # Setup mocks
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__.return_value = mock_session
        mock_session.exec.return_value.first.return_value = None

        llm = Mock()
        agent = AnalyticsCrewPlaceholder(llm)

        # Spy on credential_manager
        original_method = agent.credential_manager.fetch_google_analytics_credentials
        with patch.object(agent.credential_manager, 'fetch_google_analytics_credentials', wraps=original_method) as spy:
            result = agent._fetch_google_analytics_token(4, 1)

            # Should have called credential_manager method
            spy.assert_called_once_with(4, 1)

    @patch('app.core.agents.customer_credentials.get_session')
    @patch('app.core.agents.customer_credentials.GoogleAdsService')
    def test_single_agent_fetch_ga_token_delegates_to_manager(self, mock_service_class, mock_get_session):
        """Test SingleAnalyticsAgent._fetch_google_analytics_token delegates to credential_manager."""
        # Setup mocks
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__.return_value = mock_session
        mock_session.exec.return_value.first.return_value = None

        llm = Mock()
        agent = SingleAnalyticsAgent(llm)

        # Spy on credential_manager
        original_method = agent.credential_manager.fetch_google_analytics_credentials
        with patch.object(agent.credential_manager, 'fetch_google_analytics_credentials', wraps=original_method) as spy:
            result = agent._fetch_google_analytics_token(4, 1)

            # Should have called credential_manager method
            spy.assert_called_once_with(4, 1)

    def test_both_agents_share_same_credential_logic(self):
        """Test that both agents use identical credential fetching logic."""
        llm = Mock()
        crew_agent = AnalyticsCrewPlaceholder(llm)
        single_agent = SingleAnalyticsAgent(llm)

        # Both should use CustomerCredentialManager
        assert type(crew_agent.credential_manager) == type(single_agent.credential_manager)

        # Both should have all four credential fetch methods
        for agent in [crew_agent, single_agent]:
            assert hasattr(agent, '_fetch_customer_platforms')
            assert hasattr(agent, '_fetch_google_analytics_token')
            assert hasattr(agent, '_fetch_google_ads_token')
            assert hasattr(agent, '_fetch_meta_ads_token')

        # Both should have access to credential manager methods
        assert hasattr(crew_agent.credential_manager, 'fetch_customer_platforms')
        assert hasattr(single_agent.credential_manager, 'fetch_customer_platforms')
        assert hasattr(crew_agent.credential_manager, 'fetch_google_analytics_credentials')
        assert hasattr(single_agent.credential_manager, 'fetch_google_analytics_credentials')
        assert hasattr(crew_agent.credential_manager, 'fetch_google_ads_credentials')
        assert hasattr(single_agent.credential_manager, 'fetch_google_ads_credentials')
        assert hasattr(crew_agent.credential_manager, 'fetch_meta_ads_credentials')
        assert hasattr(single_agent.credential_manager, 'fetch_meta_ads_credentials')


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
