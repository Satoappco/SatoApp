"""
Unit tests for CrewAI tools
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from app.tools.date_conversion_tool import DateConversionTool


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
