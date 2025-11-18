"""
Manual test for type coercion logic - can be run without pytest.

Run with: python3 tests/test_type_coercion_manual.py
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from unittest.mock import Mock
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
    if not isinstance(match_type, int):
        raise TypeError(f"match_type should be int, got {type(match_type)}")
    return {"match_type": match_type, "value": value, "type": type(match_type).__name__}


async def test_type_coercion():
    """Test that float values are coerced to int for integer parameters."""
    print("🧪 Testing type coercion logic...")

    # Create mock LLM
    llm = Mock()
    llm.model_name = "test-model"
    llm._lc_kwargs = {}

    # Create agent
    agent = SingleAnalyticsAgent(llm=llm)

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
    print(f"📋 Schema: {schema_dict}")

    # Wrap the tool
    wrapped_tool = agent._wrap_tool_with_type_coercion(original_tool, schema_dict)
    print(f"✅ Tool wrapped: {wrapped_tool.name}")

    # Test 1: Call with float value (simulating Gemini's behavior)
    print("\n🔍 Test 1: Calling with match_type=1.0 (float)")
    try:
        result = await wrapped_tool.coroutine(match_type=1.0, value="test")
        print(f"   ✅ SUCCESS: {result}")
        assert result["match_type"] == 1, "match_type should be 1"
        assert result["type"] == "int", "match_type should be converted to int"
        print("   ✅ Type coercion worked! Float 1.0 was converted to int 1")
    except Exception as e:
        print(f"   ❌ FAILED: {e}")
        return False

    # Test 2: Call with int value
    print("\n🔍 Test 2: Calling with match_type=2 (int)")
    try:
        result = await wrapped_tool.coroutine(match_type=2, value="test")
        print(f"   ✅ SUCCESS: {result}")
        assert result["match_type"] == 2, "match_type should be 2"
        assert result["type"] == "int", "match_type should remain int"
        print("   ✅ Integer values preserved correctly")
    except Exception as e:
        print(f"   ❌ FAILED: {e}")
        return False

    # Test 3: Verify nested dict coercion
    print("\n🔍 Test 3: Testing nested dict coercion")

    class NestedInput(BaseModel):
        """Schema with nested match_type."""
        filter_config: dict = Field(description="Nested filter")

    async def nested_tool(filter_config: dict) -> dict:
        """Tool with nested params."""
        if 'match_type' in filter_config:
            if not isinstance(filter_config['match_type'], int):
                raise TypeError(f"Nested match_type should be int, got {type(filter_config['match_type'])}")
        return filter_config

    nested_original = StructuredTool(
        name="nested_tool",
        description="Tool with nested params",
        func=nested_tool,
        args_schema=NestedInput,
        coroutine=nested_tool
    )

    # Schema with nested integer
    nested_schema = {
        'properties': {
            'filter_config': {
                'type': 'object',
                'properties': {
                    'match_type': {'type': 'integer'}
                }
            }
        }
    }

    wrapped_nested = agent._wrap_tool_with_type_coercion(nested_original, nested_schema)

    try:
        result = await wrapped_nested.coroutine(
            filter_config={'match_type': 3.0, 'value': 'nested_test'}
        )
        print(f"   ✅ SUCCESS: {result}")
        assert result['match_type'] == 3, "Nested match_type should be 3"
        assert isinstance(result['match_type'], int), "Nested match_type should be int"
        print("   ✅ Nested dict coercion worked! Float 3.0 was converted to int 3")
    except Exception as e:
        print(f"   ❌ FAILED: {e}")
        return False

    print("\n" + "=" * 60)
    print("🎉 All tests passed!")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = asyncio.run(test_type_coercion())
    sys.exit(0 if success else 1)
