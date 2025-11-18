"""
Test MCP debug logging functionality.

This test verifies that MCP calls are properly logged with detailed information
about the call, response, and any errors.
"""
import pytest
import logging
from unittest.mock import Mock, AsyncMock, MagicMock
from app.core.agents.mcp_clients.base import BaseMCPClient


class MockMCPClient(BaseMCPClient):
    """Mock MCP client for testing."""

    def get_server_command(self):
        return ["python", "-m", "mock_server"]

    def get_tools(self):
        return []


@pytest.mark.asyncio
async def test_mcp_call_logging(caplog):
    """Test that MCP calls are logged with detailed information."""
    # Set up logging capture
    caplog.set_level(logging.INFO)

    # Create mock client and session
    client = MockMCPClient(server_path="/mock/path")
    client.session = AsyncMock()

    # Mock response with content
    mock_result = Mock()
    mock_result.content = [Mock(text="Test response content")]
    client.session.call_tool = AsyncMock(return_value=mock_result)

    # Call the tool
    result = await client.call_tool(
        tool_name="test_tool",
        arguments={"param1": "value1", "param2": 123}
    )

    # Verify the call was made
    assert result == mock_result

    # Verify logging output
    log_output = caplog.text

    # Check for call logging
    assert "[MCP CALL] Tool: test_tool" in log_output
    assert "[MCP CALL] Client: MockMCPClient" in log_output
    assert "[MCP CALL] Arguments:" in log_output
    assert "param1: value1" in log_output
    assert "param2: 123" in log_output

    # Check for response logging
    assert "[MCP RESPONSE] Tool: test_tool" in log_output
    assert "[MCP RESPONSE] Duration:" in log_output
    assert "[MCP RESPONSE] Result type:" in log_output
    assert "[MCP RESPONSE] Content:" in log_output
    assert "Text: Test response content" in log_output


@pytest.mark.asyncio
async def test_mcp_error_logging(caplog):
    """Test that MCP errors are logged with detailed information."""
    # Set up logging capture
    caplog.set_level(logging.ERROR)

    # Create mock client and session
    client = MockMCPClient(server_path="/mock/path")
    client.session = AsyncMock()

    # Mock error response
    error_message = "Test error message"
    client.session.call_tool = AsyncMock(side_effect=ValueError(error_message))

    # Call the tool and expect error
    with pytest.raises(ValueError, match=error_message):
        await client.call_tool(
            tool_name="failing_tool",
            arguments={"param": "value"}
        )

    # Verify error logging
    log_output = caplog.text

    assert "[MCP ERROR] Tool: failing_tool" in log_output
    assert "[MCP ERROR] Duration:" in log_output
    assert "[MCP ERROR] Error type: ValueError" in log_output
    assert f"[MCP ERROR] Error message: {error_message}" in log_output


@pytest.mark.asyncio
async def test_mcp_sensitive_data_redaction(caplog):
    """Test that sensitive data is redacted from logs."""
    # Set up logging capture
    caplog.set_level(logging.INFO)

    # Create mock client and session
    client = MockMCPClient(server_path="/mock/path")
    client.session = AsyncMock()

    # Mock response
    mock_result = Mock()
    mock_result.content = [Mock(text="Response")]
    client.session.call_tool = AsyncMock(return_value=mock_result)

    # Call with sensitive arguments
    await client.call_tool(
        tool_name="test_tool",
        arguments={
            "access_token": "secret_token_12345",
            "api_key": "api_key_67890",
            "normal_param": "normal_value"
        }
    )

    # Verify sensitive data is redacted
    log_output = caplog.text

    assert "secret_token_12345" not in log_output
    assert "api_key_67890" not in log_output
    assert "***REDACTED***" in log_output
    assert "normal_param: normal_value" in log_output


@pytest.mark.asyncio
async def test_mcp_long_content_truncation(caplog):
    """Test that long content is truncated in logs."""
    # Set up logging capture
    caplog.set_level(logging.INFO)

    # Create mock client and session
    client = MockMCPClient(server_path="/mock/path")
    client.session = AsyncMock()

    # Create long text response
    long_text = "A" * 600  # More than 500 characters
    mock_result = Mock()
    mock_result.content = [Mock(text=long_text)]
    client.session.call_tool = AsyncMock(return_value=mock_result)

    # Call the tool
    await client.call_tool(
        tool_name="test_tool",
        arguments={"param": "value"}
    )

    # Verify content is truncated
    log_output = caplog.text

    assert "Text (first 500 chars):" in log_output
    assert "..." in log_output
    # Should show first 500 chars + "..."
    assert long_text not in log_output  # Full text should not be present


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
