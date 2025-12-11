"""
Unit Tests for MCP Validator Platform Detection

Tests the platform field in MCPValidationResult for simplified error handling.
"""

import pytest
from app.core.agents.mcp_clients.mcp_validator import (
    MCPValidator,
    MCPValidationResult,
    ValidationStatus,
)


class TestPlatformDetection:
    """Tests for platform detection from server names."""

    def test_get_platform_from_google_analytics_server(self):
        """Test that Google Analytics servers are correctly identified."""
        validator = MCPValidator({})

        test_cases = [
            "google_analytics_official",
            "google-analytics-mcp",
            "analytics_mcp",
            "Google_Analytics_Server",
        ]

        for server_name in test_cases:
            platform = validator._get_platform_from_server(server_name)
            assert platform == 'google_analytics', f"Failed for server: {server_name}"

    def test_get_platform_from_google_ads_server(self):
        """Test that Google Ads servers are correctly identified."""
        validator = MCPValidator({})

        test_cases = [
            "google_ads_official",
            "google-ads-mcp",
            "ads_mcp",
            "Google_Ads_Server",
        ]

        for server_name in test_cases:
            platform = validator._get_platform_from_server(server_name)
            assert platform == 'google_ads', f"Failed for server: {server_name}"

    def test_get_platform_from_facebook_server(self):
        """Test that Facebook servers are correctly identified."""
        validator = MCPValidator({})

        test_cases = [
            "facebook_ads_server",
            "facebook-mcp",
            "meta_ads",
            "Facebook_Server",
        ]

        for server_name in test_cases:
            platform = validator._get_platform_from_server(server_name)
            assert platform == 'facebook_ads', f"Failed for server: {server_name}"

    def test_get_platform_from_unknown_server(self):
        """Test that unknown servers return None."""
        validator = MCPValidator({})

        test_cases = [
            "unknown_server",
            "some_other_mcp",
            "twitter_ads",
        ]

        for server_name in test_cases:
            platform = validator._get_platform_from_server(server_name)
            assert platform is None, f"Should return None for: {server_name}"

    def test_get_platform_case_insensitive(self):
        """Test that platform detection is case insensitive."""
        validator = MCPValidator({})

        # Test various casings
        assert validator._get_platform_from_server("GOOGLE_ANALYTICS") == 'google_analytics'
        assert validator._get_platform_from_server("Google_Ads") == 'google_ads'
        assert validator._get_platform_from_server("FaceBook_Ads") == 'facebook_ads'


class TestValidationResultPlatform:
    """Tests for platform field in validation results."""

    @pytest.mark.asyncio
    async def test_validation_result_includes_platform(self):
        """Test that validation results include the platform field."""
        # Create mock client
        class MockClient:
            async def get_tools(self):
                return ['tool1', 'tool2']

        clients = {
            'google_analytics_official': MockClient(),
            'google_ads_official': MockClient(),
            'facebook_ads_server': MockClient(),
        }

        validator = MCPValidator(clients)
        results = await validator.validate_all()

        # Check that all results have platform field
        assert len(results) == 3

        platforms_found = [r.platform for r in results]
        assert 'google_analytics' in platforms_found
        assert 'google_ads' in platforms_found
        assert 'facebook_ads' in platforms_found

    @pytest.mark.asyncio
    async def test_platform_field_set_for_google_analytics(self):
        """Test that Google Analytics validation sets platform field."""
        class MockClient:
            async def get_tools(self):
                return ['run_report', 'get_metadata']

            async def call_tool(self, tool_name, params):
                class MockResult:
                    isError = False
                    content = [type('obj', (), {'text': 'Success'})]
                return MockResult()

        clients = {'google_analytics_mcp': MockClient()}
        validator = MCPValidator(clients)
        results = await validator.validate_all()

        assert len(results) == 1
        assert results[0].platform == 'google_analytics'
        assert results[0].status == ValidationStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_platform_field_set_for_google_ads(self):
        """Test that Google Ads validation sets platform field."""
        class MockClient:
            async def get_tools(self):
                # Updated to use correct HTTP MCP server tool names
                return ['list_accessible_accounts', 'execute_gaql']

            async def call_tool(self, tool_name, params):
                class MockResult:
                    isError = False
                    content = [type('obj', (), {'text': 'Success'})]
                return MockResult()

        clients = {'google_ads_mcp': MockClient()}
        validator = MCPValidator(clients)
        results = await validator.validate_all()

        assert len(results) == 1
        assert results[0].platform == 'google_ads'
        assert results[0].status == ValidationStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_platform_field_set_for_facebook(self):
        """Test that Facebook validation sets platform field."""
        class MockClient:
            async def get_tools(self):
                return ['get_insights', 'get_campaigns']

        clients = {'facebook_ads_server': MockClient()}
        validator = MCPValidator(clients)
        results = await validator.validate_all()

        assert len(results) == 1
        assert results[0].platform == 'facebook_ads'
        assert results[0].status == ValidationStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_platform_field_set_on_failure(self):
        """Test that platform field is set even when validation fails."""
        class MockClient:
            async def get_tools(self):
                return []  # No tools = validation fails

        clients = {'google_analytics_mcp': MockClient()}
        validator = MCPValidator(clients)
        results = await validator.validate_all()

        assert len(results) == 1
        assert results[0].platform == 'google_analytics'
        assert results[0].status == ValidationStatus.FAILED

    @pytest.mark.asyncio
    async def test_platform_field_none_for_unknown_server(self):
        """Test that platform field is None for unknown servers."""
        class MockClient:
            async def get_tools(self):
                return ['some_tool']

        clients = {'unknown_mcp_server': MockClient()}
        validator = MCPValidator(clients)
        results = await validator.validate_all()

        assert len(results) == 1
        assert results[0].platform is None
        assert results[0].server == 'unknown_mcp_server'


class TestConnectionIdMapping:
    """Tests for connection ID mapping."""

    @pytest.mark.asyncio
    async def test_connection_id_mapped_correctly(self):
        """Test that connection IDs are mapped to validation results."""
        class MockClient:
            async def get_tools(self):
                return ['tool1']

        clients = {'google_analytics_mcp': MockClient()}
        connection_ids = {'google_analytics': 123}

        validator = MCPValidator(clients, connection_ids)
        results = await validator.validate_all()

        assert len(results) == 1
        assert results[0].connection_id == 123
        assert results[0].platform == 'google_analytics'

    @pytest.mark.asyncio
    async def test_connection_id_none_when_not_provided(self):
        """Test that connection_id is None when not provided."""
        class MockClient:
            async def get_tools(self):
                return ['tool1']

        clients = {'google_analytics_mcp': MockClient()}

        validator = MCPValidator(clients)  # No connection_ids provided
        results = await validator.validate_all()

        assert len(results) == 1
        assert results[0].connection_id is None


class TestSimplifiedErrorHandling:
    """Tests demonstrating the simplified error handling flow."""

    @pytest.mark.asyncio
    async def test_platform_directly_identifies_failed_platform(self):
        """Test that failed platform can be identified directly from platform field."""
        class MockFailedClient:
            async def get_tools(self):
                raise Exception("Authentication failed")

        clients = {'google_ads_mcp': MockFailedClient()}
        validator = MCPValidator(clients)
        results = await validator.validate_all()

        assert len(results) == 1
        result = results[0]

        # No regex or string parsing needed!
        assert result.platform == 'google_ads'
        assert result.status == ValidationStatus.ERROR

        # Can directly use platform field to remove failed platform
        platform_to_remove = result.platform
        assert platform_to_remove == 'google_ads'

    @pytest.mark.asyncio
    async def test_multiple_platforms_with_mixed_results(self):
        """Test validation with multiple platforms where some fail."""
        class SuccessClient:
            async def get_tools(self):
                return ['tool1', 'tool2']

        class FailedClient:
            async def get_tools(self):
                return []  # No tools = fail

        clients = {
            'google_analytics_mcp': SuccessClient(),
            'google_ads_mcp': FailedClient(),
            'facebook_ads_server': SuccessClient(),
        }

        validator = MCPValidator(clients)
        results = await validator.validate_all()

        # Check results - all results should have platform field set
        assert len(results) == 3

        # Check that all platforms are identified correctly
        platforms_found = {r.server: r.platform for r in results}
        assert platforms_found['google_analytics_mcp'] == 'google_analytics'
        assert platforms_found['google_ads_mcp'] == 'google_ads'
        assert platforms_found['facebook_ads_server'] == 'facebook_ads'

        # Identify failed platforms directly - no parsing needed!
        failed_platforms = [
            r.platform for r in results
            if r.status in [ValidationStatus.FAILED, ValidationStatus.ERROR]
        ]

        # Google Ads should fail (no tools)
        assert 'google_ads' in failed_platforms
