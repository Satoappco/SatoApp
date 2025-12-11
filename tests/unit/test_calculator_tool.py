"""Tests for CalculatorTool."""

import pytest
from unittest.mock import Mock, patch
from app.core.agents.tools.calculator_tool import CalculatorTool, CalculatorInput


class TestCalculatorTool:
    """Test suite for CalculatorTool."""

    def test_calculator_is_langchain_tool(self):
        """Test that CalculatorTool is a LangChain BaseTool."""
        from langchain.tools import BaseTool

        tool = CalculatorTool()
        assert isinstance(tool, BaseTool), "CalculatorTool must inherit from LangChain BaseTool"

    def test_calculator_is_crewai_tool(self):
        """Test that CalculatorTool is also a CrewAI BaseTool."""
        from crewai.tools import BaseTool as CrewAIBaseTool

        tool = CalculatorTool()
        assert isinstance(tool, CrewAIBaseTool), "CalculatorTool must also inherit from CrewAI BaseTool"

    def test_calculator_has_required_attributes(self):
        """Test that CalculatorTool has required attributes for LangChain."""
        tool = CalculatorTool()

        assert tool.name == "calculator"
        assert "mathematical calculations" in tool.description.lower()
        assert tool.args_schema == CalculatorInput

    def test_calculator_basic_addition(self):
        """Test basic addition."""
        tool = CalculatorTool()
        result = tool._run("2 + 2")
        assert result == "4"

    def test_calculator_complex_expression(self):
        """Test complex mathematical expression."""
        tool = CalculatorTool()
        result = tool._run("(10 + 5) * 3")
        assert result == "45"

    def test_calculator_division(self):
        """Test division."""
        tool = CalculatorTool()
        result = tool._run("100 / 4")
        assert result == "25.0"

    def test_calculator_power(self):
        """Test power operation."""
        tool = CalculatorTool()
        result = tool._run("2 ** 8")
        assert result == "256"

    def test_calculator_negative_numbers(self):
        """Test negative numbers."""
        tool = CalculatorTool()
        result = tool._run("-5 + 10")
        assert result == "5"

    def test_calculator_invalid_expression(self):
        """Test error handling for invalid expressions."""
        tool = CalculatorTool()
        result = tool._run("invalid expression")
        assert "error" in result.lower()

    def test_calculator_with_thread_id_tracing(self):
        """Test that calculator tool can trace operations."""
        with patch('app.core.agents.tools.calculator_tool.ChatTraceService') as mock_service:
            mock_trace = Mock()
            mock_service.return_value = mock_trace

            tool = CalculatorTool(thread_id="test-thread-123", level=2)
            result = tool._run("5 + 5")

            assert result == "10"
            # Verify tracing was called
            mock_trace.add_tool_usage.assert_called_once()
            call_args = mock_trace.add_tool_usage.call_args
            assert call_args[1]["thread_id"] == "test-thread-123"
            assert call_args[1]["tool_name"] == "calculator"
            assert call_args[1]["tool_input"] == "5 + 5"
            assert call_args[1]["tool_output"] == "10"
            assert call_args[1]["success"] is True
            assert call_args[1]["level"] == 2

    def test_calculator_async_run(self):
        """Test async version of calculator."""
        import asyncio

        tool = CalculatorTool()
        result = asyncio.run(tool._arun("3 + 3"))
        assert result == "6"

    def test_calculator_input_schema(self):
        """Test that input schema is properly defined."""
        from pydantic import BaseModel

        assert issubclass(CalculatorInput, BaseModel)

        # Test valid input
        valid_input = CalculatorInput(expression="2 + 2")
        assert valid_input.expression == "2 + 2"

        # Test that expression is required
        with pytest.raises(Exception):  # Pydantic validation error
            CalculatorInput()

    def test_calculator_gemini_compatibility(self):
        """Test that CalculatorTool is compatible with LangChain's tool binding (e.g., for Gemini)."""
        from langchain.tools import BaseTool

        tool = CalculatorTool()

        # Verify it's a LangChain BaseTool
        assert isinstance(tool, BaseTool)

        # Verify it has the required methods
        assert hasattr(tool, '_run')
        assert hasattr(tool, '_arun')
        assert callable(tool._run)
        assert callable(tool._arun)

        # Verify it has the schema
        assert hasattr(tool, 'args_schema')
        assert tool.args_schema is not None

    def test_calculator_safe_eval_prevents_dangerous_operations(self):
        """Test that safe_eval prevents dangerous operations."""
        tool = CalculatorTool()

        # Try to execute dangerous code (should fail safely)
        dangerous_expressions = [
            "__import__('os').system('ls')",
            "exec('print(1)')",
            "eval('2+2')",
        ]

        for expr in dangerous_expressions:
            result = tool._run(expr)
            # Should return an error message, not execute the code
            assert "error" in result.lower()

    def test_calculator_decimal_precision(self):
        """Test calculator handles decimal numbers correctly."""
        tool = CalculatorTool()
        result = tool._run("0.1 + 0.2")
        # Due to floating point precision, we check if it's close
        assert float(result) == pytest.approx(0.3, rel=1e-9)

    def test_calculator_order_of_operations(self):
        """Test that calculator respects order of operations."""
        tool = CalculatorTool()

        # 2 + 3 * 4 should be 14 (not 20)
        result = tool._run("2 + 3 * 4")
        assert result == "14"

        # (2 + 3) * 4 should be 20
        result = tool._run("(2 + 3) * 4")
        assert result == "20"

    def test_calculator_modulo_operation(self):
        """Test modulo operation."""
        tool = CalculatorTool()
        result = tool._run("17 % 5")
        assert result == "2"

    def test_calculator_floor_division(self):
        """Test floor division."""
        tool = CalculatorTool()
        result = tool._run("17 // 5")
        assert result == "3"

    def test_calculator_whitespace_handling(self):
        """Test that calculator handles expressions with various whitespace."""
        tool = CalculatorTool()

        # All these should work
        expressions = [
            "2+2",
            "2 + 2",
            "2  +  2",
            "  2 + 2  ",
        ]

        for expr in expressions:
            result = tool._run(expr)
            assert result == "4"

    @patch('app.core.agents.tools.calculator_tool.ChatTraceService')
    def test_calculator_trace_error_handling(self, mock_service):
        """Test that calculator continues working even if tracing fails."""
        # Make tracing raise an error
        mock_service.side_effect = Exception("Tracing failed")

        tool = CalculatorTool(thread_id="test-thread")
        result = tool._run("10 + 10")

        # Calculator should still work even if tracing fails
        assert result == "20"
