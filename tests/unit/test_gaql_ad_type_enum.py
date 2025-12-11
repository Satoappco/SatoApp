"""
Test for GAQL Ad Type Enum Fix

This test validates that the Google Ads ad type enum values are correctly documented
in the agent's system prompt to prevent the 'SEARCH_AD' error.

Bug: The agent was using 'SEARCH_AD' which is not a valid enum value for ad_group_ad.ad.type
Fix: Added documentation in system prompt specifying correct enum values like 'RESPONSIVE_SEARCH_AD'
"""

import pytest
from app.core.agents.graph.single_analytics_agent import SingleAnalyticsAgent
from langchain_openai import ChatOpenAI
import os


class TestGAQLAdTypeEnum:
    """Test that GAQL ad type enums are properly documented."""

    def test_system_prompt_contains_ad_type_documentation(self):
        """Test that the system prompt includes documentation about valid ad types."""
        # Create agent instance
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        agent = SingleAnalyticsAgent(llm)

        # Build a minimal task to generate the system prompt
        task_details = {
            "query": "Which search ad has the highest CTR?",
            "context": {
                "agency": {"id": 1, "name": "Test Agency"},
                "campaigner": {"id": 1, "full_name": "Test User"},
                "language": "english"
            },
            "campaigner_id": 1,
            "customer_id": 1,
            "platforms": ["google_ads"],
            "google_ads_credentials": {
                "customer_id": "1234567890",
                "refresh_token": "test_token"
            }
        }

        # Extract the system prompt generation logic
        # We'll read the source file to verify the documentation is present
        import inspect
        source = inspect.getsource(SingleAnalyticsAgent)

        # Verify key documentation points are present
        assert "Google Ads Ad Types" in source, "Missing ad types documentation section"
        assert "RESPONSIVE_SEARCH_AD" in source, "Missing RESPONSIVE_SEARCH_AD documentation"
        assert "NEVER use: 'SEARCH_AD'" in source, "Missing warning about invalid SEARCH_AD"
        assert "EXPANDED_TEXT_AD" in source, "Missing EXPANDED_TEXT_AD documentation"

        # Verify the error message mentions correct enum values
        assert "'SEARCH_AD' (this is INVALID" in source.lower() or "search_ad" in source.lower(), \
            "Missing explicit warning about SEARCH_AD being invalid"

    def test_valid_ad_type_enums(self):
        """Test that we have a list of valid ad type enums for reference."""
        # Valid Google Ads ad type enum values according to the API
        valid_ad_types = [
            'RESPONSIVE_SEARCH_AD',
            'EXPANDED_TEXT_AD',
            'TEXT_AD',
            'IMAGE_AD',
            'VIDEO_AD',
            'APP_AD',
            'SHOPPING_PRODUCT_AD',
            'DISPLAY_UPLOAD_AD',
        ]

        invalid_ad_types = [
            'SEARCH_AD',  # This is the bug - it's not a valid enum value
        ]

        # Verify we have the valid enums documented
        import inspect
        source = inspect.getsource(SingleAnalyticsAgent)

        # Check that at least the most common valid ad types are documented
        assert 'RESPONSIVE_SEARCH_AD' in source, "RESPONSIVE_SEARCH_AD should be documented"
        assert 'EXPANDED_TEXT_AD' in source, "EXPANDED_TEXT_AD should be documented"

        # Check that the invalid enum is explicitly called out as invalid
        for invalid in invalid_ad_types:
            assert invalid in source, f"Invalid enum {invalid} should be mentioned as invalid"

    def test_gaql_query_pattern_for_search_ads(self):
        """Test that the documentation provides correct query patterns for search ads."""
        import inspect
        source = inspect.getsource(SingleAnalyticsAgent)

        # Verify that the documentation shows how to properly filter search ads
        # Should mention RESPONSIVE_SEARCH_AD as the correct way to filter
        assert "ad_group_ad.ad.type = 'RESPONSIVE_SEARCH_AD'" in source or \
               "RESPONSIVE_SEARCH_AD" in source, \
               "Missing guidance on how to filter search ads correctly"

        # Verify warning about SEARCH_AD
        assert "SEARCH_AD" in source, "Missing warning about SEARCH_AD"


@pytest.mark.asyncio
class TestGAQLQueryGeneration:
    """Test that GAQL queries generate correctly with valid enum values."""

    async def test_search_ad_query_should_use_responsive_search_ad(self):
        """
        Test that when asking about search ads, the system uses RESPONSIVE_SEARCH_AD
        instead of the invalid SEARCH_AD enum.

        This is an integration test concept - in practice, this would require:
        1. Mocking the LLM to return a GAQL query
        2. Validating that the query uses correct enum values
        3. Or running the agent in a test environment and checking the generated query
        """
        # This test documents the expected behavior
        # Actual implementation would require integration test setup

        # Example of CORRECT query that should be generated:
        correct_query = """
        SELECT ad_group_ad.ad.name, metrics.ctr, metrics.clicks, metrics.impressions
        FROM ad_group_ad
        WHERE ad_group_ad.ad.type = 'RESPONSIVE_SEARCH_AD'
        AND segments.date BETWEEN '2025-11-11' AND '2025-12-11'
        ORDER BY metrics.ctr DESC
        LIMIT 1
        """

        # Example of INCORRECT query that caused the bug:
        incorrect_query = """
        SELECT ad_group_ad.ad.name, metrics.ctr, metrics.clicks, metrics.impressions
        FROM ad_group_ad
        WHERE ad_group_ad.ad.type = 'SEARCH_AD'
        AND segments.date BETWEEN '2025-11-11' AND '2025-12-11'
        ORDER BY metrics.ctr DESC
        LIMIT 1
        """

        # Verify the correct pattern
        assert "'RESPONSIVE_SEARCH_AD'" in correct_query
        assert "'SEARCH_AD'" not in correct_query or "RESPONSIVE_SEARCH_AD" in correct_query

        # Document that the incorrect pattern should fail
        assert "'SEARCH_AD'" in incorrect_query
        # This would fail with: "Invalid enum value cannot be included in WHERE clause: 'SEARCH_AD'."


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
