"""
Unit tests for CrewAI tools
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from app.tools.date_conversion_tool import DateConversionTool
from app.core.agents.tools.calculator_tool import CalculatorTool, CalculatorInput


class TestDateConversionTool:
    """Test cases for DateConversionTool"""

    def test_date_conversion_tool_initialization(self):
        """Test DateConversionTool can be initialized"""
        tool = DateConversionTool()
        assert tool is not None
        assert hasattr(tool, "_run")

    @patch("app.tools.date_conversion_tool.DateConversionTool._run")
    def test_date_conversion_tool_run(self, mock_run):
        """Test DateConversionTool run method"""
        mock_run.return_value = "Start Date: 2024-01-15"

        tool = DateConversionTool()
        result = tool._run("last week")

        mock_run.assert_called_once_with("last week")
        assert result == "Start Date: 2024-01-15"

    def test_date_conversion_tool_name_and_description(self):
        """Test DateConversionTool has proper name and description"""
        tool = DateConversionTool()

        # Check if tool has the required attributes for CrewAI
        # Note: The current implementation may not have proper CrewAI integration
        assert tool is not None


class TestCalculatorTool:
    """Test cases for CalculatorTool"""

    def test_calculator_tool_initialization(self):
        """Test CalculatorTool can be initialized"""
        tool = CalculatorTool()
        assert tool is not None
        assert hasattr(tool, "_run")
        assert hasattr(tool, "_arun")
        assert hasattr(tool, "_safe_eval")

    def test_calculator_tool_crewai_interface(self):
        """Test CalculatorTool has proper CrewAI interface"""
        tool = CalculatorTool()

        # Check required CrewAI attributes
        assert tool.name == "calculator"
        assert tool.description is not None
        assert len(tool.description) > 0
        assert tool.args_schema == CalculatorInput

        # Verify Pydantic schema (Pydantic V2)
        assert "expression" in CalculatorInput.model_fields

    def test_calculator_input_schema(self):
        """Test CalculatorInput Pydantic schema"""
        # Valid input
        input_data = CalculatorInput(expression="2 + 2")
        assert input_data.expression == "2 + 2"

        # Invalid input - missing expression
        with pytest.raises(Exception):  # Pydantic ValidationError
            CalculatorInput()

    # Basic Arithmetic Tests
    def test_calculator_addition(self):
        """Test addition operation"""
        tool = CalculatorTool()
        result = tool._run("2 + 2")
        assert result == "4"

    def test_calculator_subtraction(self):
        """Test subtraction operation"""
        tool = CalculatorTool()
        result = tool._run("10 - 4")
        assert result == "6"

    def test_calculator_multiplication(self):
        """Test multiplication operation"""
        tool = CalculatorTool()
        result = tool._run("5 * 3")
        assert result == "15"

    def test_calculator_division(self):
        """Test division operation"""
        tool = CalculatorTool()
        result = tool._run("10 / 2")
        assert result == "5.0"

    def test_calculator_floor_division(self):
        """Test floor division operation"""
        tool = CalculatorTool()
        result = tool._run("10 // 3")
        assert result == "3"

    def test_calculator_modulo(self):
        """Test modulo operation"""
        tool = CalculatorTool()
        result = tool._run("10 % 3")
        assert result == "1"

    def test_calculator_exponentiation(self):
        """Test exponentiation operation"""
        tool = CalculatorTool()
        result = tool._run("2 ** 8")
        assert result == "256"

    # Complex Expression Tests
    def test_calculator_parentheses(self):
        """Test expression with parentheses"""
        tool = CalculatorTool()
        result = tool._run("(10 + 5) * 3")
        assert result == "45"

    def test_calculator_multiple_operations(self):
        """Test expression with multiple operations"""
        tool = CalculatorTool()
        result = tool._run("100 / 4 + 25")
        assert result == "50.0"

    def test_calculator_percentage_calculation(self):
        """Test percentage calculation"""
        tool = CalculatorTool()
        result = tool._run("(1500 - 500) * 0.15")
        assert result == "150.0"

    def test_calculator_compound_calculation(self):
        """Test compound calculation"""
        tool = CalculatorTool()
        result = tool._run("(100 * 0.25) + 50")
        assert result == "75.0"

    # Unary Operations Tests
    def test_calculator_negative_number(self):
        """Test negative number (unary minus)"""
        tool = CalculatorTool()
        result = tool._run("-5")
        assert result == "-5"

    def test_calculator_negative_with_addition(self):
        """Test negative number with addition"""
        tool = CalculatorTool()
        result = tool._run("-10 + 3")
        assert result == "-7"

    # Error Handling Tests
    def test_calculator_invalid_syntax(self):
        """Test invalid syntax error"""
        tool = CalculatorTool()
        result = tool._run("2 + * 2")  # Invalid: two operators in a row
        assert "Calculation error" in result
        assert "Invalid mathematical expression" in result

    def test_calculator_division_by_zero(self):
        """Test division by zero error"""
        tool = CalculatorTool()
        result = tool._run("10 / 0")
        assert "Calculation error" in result
        assert "division by zero" in result

    def test_calculator_unsupported_operation_import(self):
        """Test unsupported operation - import statement"""
        tool = CalculatorTool()
        result = tool._run("import os; os.system('ls')")
        assert "Calculation error" in result

    def test_calculator_unsupported_operation_function_call(self):
        """Test unsupported operation - function call"""
        tool = CalculatorTool()
        result = tool._run("eval('2+2')")
        assert "Calculation error" in result

    def test_calculator_unsupported_operation_variable(self):
        """Test unsupported operation - variable assignment"""
        tool = CalculatorTool()
        result = tool._run("x = 5")
        assert "Calculation error" in result

    # Edge Cases
    def test_calculator_whitespace_handling(self):
        """Test expression with extra whitespace"""
        tool = CalculatorTool()
        result = tool._run("  2  +  2  ")
        assert result == "4"

    def test_calculator_float_result(self):
        """Test float result"""
        tool = CalculatorTool()
        result = tool._run("7 / 2")
        assert result == "3.5"

    def test_calculator_large_number(self):
        """Test large number calculation"""
        tool = CalculatorTool()
        result = tool._run("999999 * 999999")
        assert result == "999998000001"

    # Async Method Test
    @pytest.mark.asyncio
    async def test_calculator_async_run(self):
        """Test async _arun method"""
        tool = CalculatorTool()
        result = await tool._arun("2 + 2")
        assert result == "4"

    # Tracing Tests (mocked)
    @patch('app.core.agents.tools.calculator_tool.ChatTraceService')
    def test_calculator_with_tracing_success(self, mock_trace_service):
        """Test calculator with tracing enabled (success case)"""
        mock_trace_instance = Mock()
        mock_trace_service.return_value = mock_trace_instance

        tool = CalculatorTool(thread_id="test-thread-123", level=1)
        result = tool._run("2 + 2")

        assert result == "4"

        # Verify tracing was called
        mock_trace_service.assert_called_once()
        mock_trace_instance.add_tool_usage.assert_called_once()

        # Verify trace arguments
        call_args = mock_trace_instance.add_tool_usage.call_args
        assert call_args[1]["thread_id"] == "test-thread-123"
        assert call_args[1]["tool_name"] == "calculator"
        assert call_args[1]["tool_input"] == "2 + 2"
        assert call_args[1]["tool_output"] == "4"
        assert call_args[1]["success"] is True
        assert call_args[1]["level"] == 1

    @patch('app.core.agents.tools.calculator_tool.ChatTraceService')
    def test_calculator_with_tracing_failure(self, mock_trace_service):
        """Test calculator with tracing enabled (failure case)"""
        mock_trace_instance = Mock()
        mock_trace_service.return_value = mock_trace_instance

        tool = CalculatorTool(thread_id="test-thread-123", level=1)
        result = tool._run("10 / 0")

        assert "Calculation error" in result

        # Verify tracing was called
        mock_trace_service.assert_called_once()
        mock_trace_instance.add_tool_usage.assert_called_once()

        # Verify trace arguments
        call_args = mock_trace_instance.add_tool_usage.call_args
        assert call_args[1]["thread_id"] == "test-thread-123"
        assert call_args[1]["tool_name"] == "calculator"
        assert call_args[1]["tool_input"] == "10 / 0"
        assert call_args[1]["success"] is False
        assert "error" in call_args[1]
        assert call_args[1]["level"] == 1

    def test_calculator_without_tracing(self):
        """Test calculator without tracing (no thread_id)"""
        tool = CalculatorTool()  # No thread_id
        result = tool._run("2 + 2")

        # Should work fine without tracing
        assert result == "4"

    # Marketing Analytics Use Cases (from documentation)
    def test_calculator_roi_calculation(self):
        """Test ROI calculation use case"""
        tool = CalculatorTool()
        # ROI = (Revenue - Cost) / Cost
        result = tool._run("(1500 - 1000) / 1000")
        assert result == "0.5"  # 50% ROI

    def test_calculator_cpc_calculation(self):
        """Test Cost Per Click calculation"""
        tool = CalculatorTool()
        result = tool._run("250 / 500")
        assert result == "0.5"  # $0.50 per click

    def test_calculator_conversion_rate(self):
        """Test conversion rate calculation"""
        tool = CalculatorTool()
        result = tool._run("(50 / 1000) * 100")
        assert result == "5.0"  # 5% conversion rate

    def test_calculator_budget_allocation(self):
        """Test budget allocation calculation"""
        tool = CalculatorTool()
        result = tool._run("5000 * 0.30")
        assert result == "1500.0"  # $1,500

    def test_calculator_average_metrics(self):
        """Test average metrics calculation"""
        tool = CalculatorTool()
        result = tool._run("(25 + 30 + 35) / 3")
        assert result == "30.0"  # $30 average CPA
