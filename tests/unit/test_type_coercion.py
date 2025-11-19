"""
Test type coercion in SingleAnalyticsAgent tool wrapper.

This test verifies that the agent correctly coerces float values to integers
when the tool schema expects integer parameters.
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from app.core.agents.graph.agents import SingleAnalyticsAgent
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field


class MockToolInput(BaseModel):
    """Mock tool input schema with integer parameter."""
    match_type: int = Field(description="Match type as integer")
    value: str = Field(description="String value")


async def mock_tool_func(match_type: int, value: str) -> dict:
    """Mock tool function that expects integer match_type."""
    # Verify match_type is actually an integer
    assert isinstance(match_type, int), f"match_type should be int, got {type(match_type)}"
    return {"match_type": match_type, "value": value, "type": type(match_type).__name__}


@pytest.fixture
def mock_llm():
    """Create a mock LLM."""
    llm = Mock()
    llm.model_name = "test-model"
    llm._lc_kwargs = {}
    return llm


@pytest.fixture
def agent(mock_llm):
    """Create a SingleAnalyticsAgent instance."""
    return SingleAnalyticsAgent(llm=mock_llm)


def test_wrap_tool_with_type_coercion_basic(agent):
    """Test that _wrap_tool_with_type_coercion correctly wraps a tool."""
    # Create a mock tool with integer parameter
    original_tool = StructuredTool(
        name="test_tool",
        description="Test tool with integer parameter",
        func=mock_tool_func,
        args_schema=MockToolInput,
        coroutine=mock_tool_func
    )

    # Get the schema
    schema_dict = MockToolInput.model_json_schema()

    # Wrap the tool
    wrapped_tool = agent._wrap_tool_with_type_coercion(original_tool, schema_dict)

    # Verify the wrapped tool has the same name and description
    assert wrapped_tool.name == "test_tool"
    assert wrapped_tool.description == "Test tool with integer parameter"


@pytest.mark.asyncio
async def test_type_coercion_float_to_int(agent):
    """Test that float values are coerced to int for integer parameters."""
    # Create a mock tool with integer parameter
    original_tool = StructuredTool(
        name="test_tool",
        description="Test tool with integer parameter",
        func=mock_tool_func,
        args_schema=MockToolInput,
        coroutine=mock_tool_func
    )

    # Get the schema
    schema_dict = MockToolInput.model_json_schema()

    # Wrap the tool
    wrapped_tool = agent._wrap_tool_with_type_coercion(original_tool, schema_dict)

    # Call with float value (simulating Gemini's behavior)
    result = await wrapped_tool.coroutine(match_type=1.0, value="test")

    # Verify the result
    assert result["match_type"] == 1
    assert result["type"] == "int"  # Verify it was actually converted to int


@pytest.mark.asyncio
async def test_type_coercion_preserves_int(agent):
    """Test that integer values remain unchanged."""
    # Create a mock tool with integer parameter
    original_tool = StructuredTool(
        name="test_tool",
        description="Test tool with integer parameter",
        func=mock_tool_func,
        args_schema=MockToolInput,
        coroutine=mock_tool_func
    )

    # Get the schema
    schema_dict = MockToolInput.model_json_schema()

    # Wrap the tool
    wrapped_tool = agent._wrap_tool_with_type_coercion(original_tool, schema_dict)

    # Call with int value
    result = await wrapped_tool.coroutine(match_type=1, value="test")

    # Verify the result
    assert result["match_type"] == 1
    assert result["type"] == "int"


def test_no_wrapping_when_no_int_params(agent):
    """Test that tools without integer parameters are not wrapped."""

    class NoIntParams(BaseModel):
        """Schema with no integer parameters."""
        value: str = Field(description="String value")

    original_tool = StructuredTool(
        name="test_tool",
        description="Test tool without integer parameters",
        func=lambda value: {"value": value},
        args_schema=NoIntParams
    )

    schema_dict = NoIntParams.model_json_schema()

    # Wrap the tool
    wrapped_tool = agent._wrap_tool_with_type_coercion(original_tool, schema_dict)

    # Should return the original tool
    assert wrapped_tool == original_tool


@pytest.mark.asyncio
async def test_nested_dict_coercion(agent):
    """Test type coercion in nested dictionaries."""

    class NestedIntParams(BaseModel):
        """Schema with nested structure containing integers."""
        filter_config: dict = Field(description="Nested filter config")

    async def nested_tool_func(filter_config: dict) -> dict:
        """Tool that accepts nested config with integer."""
        # The match_type inside filter should be coerced to int
        if 'match_type' in filter_config:
            assert isinstance(filter_config['match_type'], int)
        return filter_config

    original_tool = StructuredTool(
        name="nested_tool",
        description="Tool with nested parameters",
        func=nested_tool_func,
        args_schema=NestedIntParams,
        coroutine=nested_tool_func
    )

    # Create schema that marks match_type as integer
    # In real scenario, this would come from the tool's schema
    schema_dict = {
        'properties': {
            'filter_config': {
                'type': 'object',
                'properties': {
                    'match_type': {'type': 'integer'}
                }
            }
        }
    }

    # Wrap the tool
    wrapped_tool = agent._wrap_tool_with_type_coercion(original_tool, schema_dict)

    # Call with nested float
    result = await wrapped_tool.coroutine(
        filter_config={'match_type': 1.0, 'value': 'test'}
    )

    # Verify coercion happened
    assert result['match_type'] == 1
    assert isinstance(result['match_type'], int)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
