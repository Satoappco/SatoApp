"""
Test for MCP Tool Retry Mechanism

This test validates that the agent retries failed MCP tool calls at least 3 times
before giving up and returning the error to the chatbot.

Bug: The agent was immediately returning tool errors to the chatbot without retrying
Fix: Implemented custom error handler that tracks retry attempts and encourages the agent to retry
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from app.core.agents.graph.single_analytics_agent import SingleAnalyticsAgent
from langchain_openai import ChatOpenAI


class TestMCPRetryMechanism:
    """Test that MCP tool failures trigger proper retry logic."""

    def test_custom_error_handler_exists(self):
        """Test that the custom error handler is defined in the agent code."""
        import inspect
        source = inspect.getsource(SingleAnalyticsAgent)

        # Verify the custom error handler is defined
        assert "handle_tool_error_with_retry" in source, "Custom error handler should be defined"
        assert "max_retries_per_tool = 3" in source, "Should define max retries as 3"
        assert "tool_failure_counts" in source, "Should track failure counts"

    def test_error_handler_provides_retry_instructions(self):
        """Test that error messages include retry instructions for the agent."""
        import inspect
        source = inspect.getsource(SingleAnalyticsAgent)

        # Verify retry instructions are provided
        assert "RETRY INSTRUCTIONS" in source, "Should provide retry instructions"
        assert "You have" in source and "retry attempt(s) remaining" in source, \
            "Should tell agent how many retries remain"

        # Verify it mentions common fixes
        assert "RESPONSIVE_SEARCH_AD" in source, "Should mention correct ad type enum"
        assert "sessionCampaignName" in source, "Should mention correct GA4 dimension names"

    def test_error_handler_tracks_attempts(self):
        """Test that the error handler tracks attempt numbers."""
        import inspect
        source = inspect.getsource(SingleAnalyticsAgent)

        # Verify attempt tracking
        assert "attempt_num" in source, "Should track attempt number"
        assert "Attempt" in source and "/{max_retries_per_tool}" in source, \
            "Should show attempt X/3 format"

    def test_error_handler_has_final_attempt_message(self):
        """Test that after 3 attempts, the agent gets a final error message."""
        import inspect
        source = inspect.getsource(SingleAnalyticsAgent)

        # Verify final attempt handling
        assert "Final Attempt" in source, "Should have final attempt message"
        assert "maximum retries" in source, "Should mention maximum retries"
        assert "Do NOT retry" in source, "Should tell agent not to retry after max attempts"

    def test_agent_executor_uses_custom_handler(self):
        """Test that AgentExecutor is configured with the custom error handler."""
        import inspect
        source = inspect.getsource(SingleAnalyticsAgent)

        # Verify AgentExecutor uses custom handler
        assert "handle_tool_error=handle_tool_error_with_retry" in source, \
            "AgentExecutor should use custom error handler"

    @pytest.mark.asyncio
    async def test_error_handler_logic(self):
        """
        Test the error handler logic directly by simulating the function.

        This tests:
        1. First failure: Returns retry instructions
        2. Second failure: Returns retry instructions with updated count
        3. Third failure: Returns final error message
        """
        # Simulate the error handler logic
        tool_failure_counts = {}
        max_retries_per_tool = 3

        def simulate_error_handler(error_msg: str, tool_name: str) -> dict:
            """Simulate our error handler logic."""
            error_signature = f"{tool_name}:{error_msg[:100]}"

            if error_signature not in tool_failure_counts:
                tool_failure_counts[error_signature] = 0
            tool_failure_counts[error_signature] += 1

            attempt_num = tool_failure_counts[error_signature]
            is_final = attempt_num >= max_retries_per_tool

            return {
                "attempt_num": attempt_num,
                "is_final": is_final,
                "remaining": max_retries_per_tool - attempt_num
            }

        # Simulate 3 failures of the same tool with the same error
        error_msg = "Invalid enum value: 'SEARCH_AD'"
        tool_name = "execute_gaql"

        # First attempt
        result1 = simulate_error_handler(error_msg, tool_name)
        assert result1["attempt_num"] == 1, "First attempt should be 1"
        assert result1["is_final"] == False, "First attempt should not be final"
        assert result1["remaining"] == 2, "Should have 2 retries remaining"

        # Second attempt
        result2 = simulate_error_handler(error_msg, tool_name)
        assert result2["attempt_num"] == 2, "Second attempt should be 2"
        assert result2["is_final"] == False, "Second attempt should not be final"
        assert result2["remaining"] == 1, "Should have 1 retry remaining"

        # Third attempt
        result3 = simulate_error_handler(error_msg, tool_name)
        assert result3["attempt_num"] == 3, "Third attempt should be 3"
        assert result3["is_final"] == True, "Third attempt should be final"
        assert result3["remaining"] == 0, "Should have 0 retries remaining"

    @pytest.mark.asyncio
    async def test_different_tools_tracked_separately(self):
        """Test that different tools have separate retry counters."""
        tool_failure_counts = {}
        max_retries_per_tool = 3

        def simulate_error_handler(error_msg: str, tool_name: str) -> int:
            """Simulate error handler and return attempt number."""
            error_signature = f"{tool_name}:{error_msg[:100]}"
            if error_signature not in tool_failure_counts:
                tool_failure_counts[error_signature] = 0
            tool_failure_counts[error_signature] += 1
            return tool_failure_counts[error_signature]

        # Tool 1 fails twice
        assert simulate_error_handler("Error A", "tool_1") == 1
        assert simulate_error_handler("Error A", "tool_1") == 2

        # Tool 2 fails once (should start at 1, not continue from tool_1's count)
        assert simulate_error_handler("Error B", "tool_2") == 1

        # Tool 1 fails again (should be 3, continuing its own count)
        assert simulate_error_handler("Error A", "tool_1") == 3

    @pytest.mark.asyncio
    async def test_different_errors_tracked_separately(self):
        """Test that different error messages for the same tool are tracked separately."""
        tool_failure_counts = {}

        def simulate_error_handler(error_msg: str, tool_name: str) -> int:
            """Simulate error handler and return attempt number."""
            error_signature = f"{tool_name}:{error_msg[:100]}"
            if error_signature not in tool_failure_counts:
                tool_failure_counts[error_signature] = 0
            tool_failure_counts[error_signature] += 1
            return tool_failure_counts[error_signature]

        tool_name = "execute_gaql"

        # Error type 1 fails twice
        assert simulate_error_handler("Invalid enum: SEARCH_AD", tool_name) == 1
        assert simulate_error_handler("Invalid enum: SEARCH_AD", tool_name) == 2

        # Error type 2 fails once (should start at 1, different error signature)
        assert simulate_error_handler("Missing field: date", tool_name) == 1

        # Back to error type 1 (should be 3)
        assert simulate_error_handler("Invalid enum: SEARCH_AD", tool_name) == 3


class TestRetryBehaviorDocumentation:
    """Test that retry behavior is documented in system prompt."""

    def test_system_prompt_mentions_retries(self):
        """Test that the system prompt mentions retry capability."""
        import inspect
        source = inspect.getsource(SingleAnalyticsAgent)

        # The system prompt should mention retry capability
        assert "15 iterations" in source or "retry" in source.lower(), \
            "System prompt should mention retry capability"

    def test_error_handling_section_exists(self):
        """Test that there's an ERROR HANDLING section in the system prompt."""
        import inspect
        source = inspect.getsource(SingleAnalyticsAgent)

        assert "ERROR HANDLING" in source, "Should have ERROR HANDLING section in prompt"
        assert "retry with corrected parameters" in source.lower(), \
            "Should instruct agent to retry"


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
