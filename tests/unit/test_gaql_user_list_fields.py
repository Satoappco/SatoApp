"""
Test for GAQL User List Field Names Fix

This test validates that the SingleAnalyticsAgent has correct documentation about
accessing audience/user list fields in Google Ads GAQL queries.

Bug: Agent was generating queries with 'ad_group_criterion.user_list.name' which doesn't exist
Fix: Added documentation about correct field paths for user lists
"""

import pytest
import os


class TestGAQLUserListFields:
    """Test that user list field documentation is present in system prompt."""

    def test_system_prompt_contains_user_list_documentation(self):
        """Test that the system prompt includes user list field documentation."""
        # Read the agent file
        agent_file = os.path.join(
            os.path.dirname(__file__),
            "../../app/core/agents/graph/single_analytics_agent.py"
        )
        with open(agent_file, 'r') as f:
            source = f.read()

        # Verify documentation about user list fields exists
        assert "Audience/User List Fields" in source, \
            "Should have section about audience/user list fields"
        assert "ad_group_criterion.user_list" in source, \
            "Should document ad_group_criterion.user_list field"

    def test_warns_against_invalid_user_list_name_field(self):
        """Test that the prompt explicitly warns against .name suffix on user_list."""
        agent_file = os.path.join(
            os.path.dirname(__file__),
            "../../app/core/agents/graph/single_analytics_agent.py"
        )
        with open(agent_file, 'r') as f:
            source = f.read()

        # Should explicitly say .name is wrong
        assert "user_list.name" in source, \
            "Should mention the incorrect .name field"
        assert any(keyword in source for keyword in ["WRONG", "NOT exist", "will cause errors"]), \
            "Should warn that .name doesn't exist"

    def test_provides_correct_user_list_query_pattern(self):
        """Test that correct query patterns for user lists are documented."""
        agent_file = os.path.join(
            os.path.dirname(__file__),
            "../../app/core/agents/graph/single_analytics_agent.py"
        )
        with open(agent_file, 'r') as f:
            source = f.read()

        # Should provide correct pattern
        assert "CORRECT: ad_group_criterion.user_list" in source, \
            "Should show correct field path without .name"

    def test_suggests_alternative_for_audience_names(self):
        """Test that the prompt suggests how to get audience names properly."""
        agent_file = os.path.join(
            os.path.dirname(__file__),
            "../../app/core/agents/graph/single_analytics_agent.py"
        )
        with open(agent_file, 'r') as f:
            source = f.read()

        # Should suggest querying user_list directly for names
        assert "FROM user_list" in source, \
            "Should suggest querying user_list table directly for names"
        assert "user_list.name" in source, \
            "Should show that user_list.name is available when querying FROM user_list"

    def test_provides_criterion_type_filter(self):
        """Test that the prompt shows how to filter for user list criteria."""
        agent_file = os.path.join(
            os.path.dirname(__file__),
            "../../app/core/agents/graph/single_analytics_agent.py"
        )
        with open(agent_file, 'r') as f:
            source = f.read()

        # Should mention USER_LIST criterion type
        assert "USER_LIST" in source or "user_list" in source.lower(), \
            "Should reference user list criterion type"
        assert "ad_group_criterion.type" in source or "criterion" in source, \
            "Should mention how to filter by criterion type"


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
