"""
Test SingleAnalyticsAgent MCP debug logging functionality.

This test verifies that MCP calls from SingleAnalyticsAgent are properly logged
with detailed information about the call, response, and any errors.
"""
import pytest
import logging
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from app.core.agents.graph.agents import SingleAnalyticsAgent


@pytest.mark.asyncio
async def test_single_analytics_agent_tool_call_logging(caplog):
    """Test that SingleAnalyticsAgent MCP tool calls are logged."""
    # Set up logging capture
    caplog.set_level(logging.INFO)

    # Create mock LLM
    mock_llm = Mock()
    mock_llm.model_name = "test-model"
    # Mock _lc_kwargs as a dict (not a Mock object)
    mock_llm._lc_kwargs = {}

    # Create agent
    agent = SingleAnalyticsAgent(llm=mock_llm)

    # Create a mock tool with coroutine
    mock_tool = Mock()
    mock_tool.name = "test_mcp_tool"

    # Create mock result
    mock_result = Mock()
    mock_result.content = [Mock(text="Test MCP response")]

    # Create async coroutine
    async def mock_coroutine(*args, **kwargs):
        return mock_result

    mock_tool.coroutine = mock_coroutine

    # Wrap the tool with type coercion (which now includes logging)
    wrapped_tool = agent._wrap_tool_with_type_coercion(mock_tool, {})

    # Call the wrapped coroutine
    result = await wrapped_tool.coroutine(param1="value1", param2=123)

    # Verify the result
    assert result == mock_result

    # Verify logging output
    log_output = caplog.text

    # Check for call logging
    assert "[MCP CALL] Tool: test_mcp_tool" in log_output
    assert "[MCP CALL] Client: MultiServerMCPClient (SingleAnalyticsAgent)" in log_output
    assert "[MCP CALL] Arguments:" in log_output
    assert "param1: value1" in log_output
    assert "param2: 123" in log_output

    # Check for response logging
    assert "[MCP RESPONSE] Tool: test_mcp_tool" in log_output
    assert "[MCP RESPONSE] Duration:" in log_output
    assert "[MCP RESPONSE] Result type:" in log_output
    assert "[MCP RESPONSE] Content:" in log_output


@pytest.mark.asyncio
async def test_single_analytics_agent_tool_error_logging(caplog):
    """Test that SingleAnalyticsAgent MCP tool errors are logged."""
    # Set up logging capture
    caplog.set_level(logging.ERROR)

    # Create mock LLM
    mock_llm = Mock()
    mock_llm.model_name = "test-model"
    # Mock _lc_kwargs as a dict (not a Mock object)
    mock_llm._lc_kwargs = {}

    # Create agent
    agent = SingleAnalyticsAgent(llm=mock_llm)

    # Create a mock tool with coroutine that raises error
    mock_tool = Mock()
    mock_tool.name = "failing_mcp_tool"

    # Create async coroutine that raises error
    error_message = "Test MCP error"
    async def mock_coroutine(*args, **kwargs):
        raise ValueError(error_message)

    mock_tool.coroutine = mock_coroutine

    # Wrap the tool
    wrapped_tool = agent._wrap_tool_with_type_coercion(mock_tool, {})

    # Call the wrapped coroutine and expect error
    with pytest.raises(ValueError, match=error_message):
        await wrapped_tool.coroutine(param="value")

    # Verify error logging
    log_output = caplog.text

    assert "[MCP ERROR] Tool: failing_mcp_tool" in log_output
    assert "[MCP ERROR] Duration:" in log_output
    assert "[MCP ERROR] Error type: ValueError" in log_output
    assert f"[MCP ERROR] Error message: {error_message}" in log_output


@pytest.mark.asyncio
async def test_single_analytics_agent_sensitive_data_redaction(caplog):
    """Test that sensitive data is redacted from SingleAnalyticsAgent logs."""
    # Set up logging capture
    caplog.set_level(logging.INFO)

    # Create mock LLM
    mock_llm = Mock()
    mock_llm.model_name = "test-model"
    # Mock _lc_kwargs as a dict (not a Mock object)
    mock_llm._lc_kwargs = {}

    # Create agent
    agent = SingleAnalyticsAgent(llm=mock_llm)

    # Create a mock tool
    mock_tool = Mock()
    mock_tool.name = "secure_tool"

    # Create mock result
    mock_result = "Success"

    # Create async coroutine
    async def mock_coroutine(*args, **kwargs):
        return mock_result

    mock_tool.coroutine = mock_coroutine

    # Wrap the tool
    wrapped_tool = agent._wrap_tool_with_type_coercion(mock_tool, {})

    # Call with sensitive data
    result = await wrapped_tool.coroutine(
        access_token="secret_token_12345",
        api_key="api_key_67890",
        refresh_token="refresh_token_abc",
        normal_param="normal_value"
    )

    # Verify sensitive data is redacted
    log_output = caplog.text

    assert "secret_token_12345" not in log_output
    assert "api_key_67890" not in log_output
    assert "refresh_token_abc" not in log_output
    assert "***REDACTED***" in log_output
    assert "normal_param: normal_value" in log_output


@pytest.mark.asyncio
async def test_single_analytics_agent_type_coercion_with_logging(caplog):
    """Test that type coercion is logged alongside MCP calls."""
    # Set up logging capture
    caplog.set_level(logging.INFO)

    # Create mock LLM
    mock_llm = Mock()
    mock_llm.model_name = "test-model"
    # Mock _lc_kwargs as a dict (not a Mock object)
    mock_llm._lc_kwargs = {}

    # Create agent
    agent = SingleAnalyticsAgent(llm=mock_llm)

    # Create a mock tool
    mock_tool = Mock()
    mock_tool.name = "coercion_tool"

    # Track what arguments were received
    received_kwargs = {}

    # Create async coroutine that captures kwargs
    async def mock_coroutine(*args, **kwargs):
        received_kwargs.update(kwargs)
        return "Success"

    mock_tool.coroutine = mock_coroutine

    # Wrap the tool
    wrapped_tool = agent._wrap_tool_with_type_coercion(mock_tool, {})

    # Call with float for match_type (should be coerced to int)
    result = await wrapped_tool.coroutine(
        match_type=1.0,  # Should be coerced to int
        limit=10.0,      # Should be coerced to int
        other_param=5.5  # Should NOT be coerced (not in KNOWN_INTEGER_PARAMS)
    )

    # Verify coercion happened
    assert received_kwargs['match_type'] == 1
    assert isinstance(received_kwargs['match_type'], int)
    assert received_kwargs['limit'] == 10
    assert isinstance(received_kwargs['limit'], int)
    assert received_kwargs['other_param'] == 5.5  # Should remain float
    assert isinstance(received_kwargs['other_param'], float)

    # Verify coercion logging
    log_output = caplog.text

    assert "[TypeCoercion] Coerced match_type:" in log_output
    assert "[TypeCoercion] Coerced limit:" in log_output
    # other_param should NOT appear in coercion logs
    assert "[TypeCoercion] Coerced other_param:" not in log_output


@pytest.mark.asyncio
async def test_single_analytics_agent_long_content_truncation(caplog):
    """Test that long response content is truncated in logs."""
    # Set up logging capture
    caplog.set_level(logging.INFO)

    # Create mock LLM
    mock_llm = Mock()
    mock_llm.model_name = "test-model"
    # Mock _lc_kwargs as a dict (not a Mock object)
    mock_llm._lc_kwargs = {}

    # Create agent
    agent = SingleAnalyticsAgent(llm=mock_llm)

    # Create a mock tool
    mock_tool = Mock()
    mock_tool.name = "long_response_tool"

    # Create long response
    long_text = "A" * 600  # More than 500 characters
    mock_result = Mock()
    mock_result.content = [Mock(text=long_text)]

    # Create async coroutine
    async def mock_coroutine(*args, **kwargs):
        return mock_result

    mock_tool.coroutine = mock_coroutine

    # Wrap the tool
    wrapped_tool = agent._wrap_tool_with_type_coercion(mock_tool, {})

    # Call the tool
    result = await wrapped_tool.coroutine(param="value")

    # Verify content is truncated
    log_output = caplog.text

    assert "Text (first 500 chars):" in log_output
    assert "..." in log_output
    # Full text should not be present in logs
    assert long_text not in log_output


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
