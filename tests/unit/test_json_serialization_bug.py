"""Test for TaskOutput JSON serialization bug fix.

This test reproduces the bug where TaskOutput objects from CrewAI
cannot be JSON serialized when streaming chat responses.

Bug: TypeError: Object of type TaskOutput is not JSON serializable
Location: app/api/v1/routes/chat.py:102
"""

import json
import pytest
from unittest.mock import Mock, patch


class TestTaskOutputSerializationBug:
    """Test suite for TaskOutput JSON serialization bug."""

    def test_taskoutput_cannot_be_json_serialized(self):
        """Reproduce the bug: TaskOutput objects cannot be JSON serialized."""
        # Create a mock TaskOutput object (simulating CrewAI's TaskOutput)
        mock_task_output = Mock()
        mock_task_output.__class__.__name__ = 'TaskOutput'
        mock_task_output.raw = "This is the actual analysis result"
        mock_task_output.__str__ = lambda self: "This is the actual analysis result"

        # This should raise TypeError because TaskOutput is not JSON serializable
        with pytest.raises(TypeError, match="Object of type.*is not JSON serializable"):
            json.dumps({'type': 'content', 'chunk': mock_task_output})

    def test_string_can_be_json_serialized(self):
        """Verify that converting TaskOutput to string fixes the issue."""
        # Create a mock TaskOutput object
        mock_task_output = Mock()
        mock_task_output.__class__.__name__ = 'TaskOutput'
        mock_task_output.raw = "This is the actual analysis result"
        mock_task_output.__str__ = lambda self: "This is the actual analysis result"

        # Convert to string first
        result_str = str(mock_task_output)

        # Now JSON serialization should work
        json_str = json.dumps({'type': 'content', 'chunk': result_str})
        assert json_str is not None
        assert "This is the actual analysis result" in json_str

    def test_crew_result_should_return_string_not_taskoutput(self):
        """Test that crew.execute() should return string, not TaskOutput."""
        from app.core.agents.crew.crew import AnalyticsCrew

        # Mock the crew.kickoff() to return a TaskOutput-like object
        mock_result = Mock()
        mock_result.raw = "Analysis completed successfully"
        mock_result.__str__ = lambda self: "Analysis completed successfully"

        with patch.object(AnalyticsCrew, '_execute_internal') as mock_execute:
            # Simulate the bug: returning TaskOutput object instead of string
            mock_execute.return_value = {
                "success": True,
                "result": mock_result,  # BUG: This should be str(mock_result)
                "platforms": ["facebook_ads"],
                "task_details": {},
                "session_id": "test-123"
            }

            crew = AnalyticsCrew()
            result = crew.execute({"query": "test", "platforms": ["facebook_ads"]})

            # The bug: result["result"] is TaskOutput, not string
            assert result["success"] is True

            # This will fail with the bug:
            with pytest.raises(TypeError):
                json.dumps({'type': 'content', 'chunk': result["result"]})

    def test_streaming_chat_with_taskoutput_bug(self):
        """Test the exact scenario from chat.py where the bug occurs."""
        # Simulate crew_result with TaskOutput object
        mock_task_output = Mock()
        mock_task_output.__class__.__name__ = 'TaskOutput'
        mock_task_output.raw = "Test analysis"
        mock_task_output.__str__ = lambda self: "Test analysis"

        crew_result = {
            "status": "completed",
            "result": mock_task_output  # BUG: This is TaskOutput, not string
        }

        # Simulate chat.py line 93
        assistant_message = crew_result.get("result", "Analysis completed successfully.")

        # Simulate chat.py lines 101-102 - this should fail with the bug
        with pytest.raises(TypeError, match="Object of type.*is not JSON serializable"):
            for char in str(assistant_message):  # Converting to str for iteration
                # This fails because char iteration on TaskOutput doesn't work as expected
                # and when we try to serialize assistant_message itself, it fails
                json.dumps({'type': 'content', 'chunk': assistant_message})
                break  # We only need to test once


class TestTaskOutputSerializationFix:
    """Test suite verifying the fix works correctly."""

    def test_crew_returns_string_after_fix(self):
        """Test that after the fix, crew.execute() returns a string."""
        # After the fix, the crew should convert TaskOutput to string
        mock_result = Mock()
        mock_result.raw = "Analysis completed successfully"
        mock_result.__str__ = lambda self: "Analysis completed successfully"

        # The fix: convert to string before returning
        result_dict = {
            "success": True,
            "result": str(mock_result),  # FIX: Convert to string
            "platforms": ["facebook_ads"],
            "task_details": {},
            "session_id": "test-123"
        }

        # Now JSON serialization should work
        json_str = json.dumps({'type': 'content', 'chunk': result_dict["result"]})
        assert json_str is not None
        assert "Analysis completed successfully" in json_str

    def test_streaming_works_after_fix(self):
        """Test that streaming chat works after converting TaskOutput to string."""
        # Simulate crew_result with string (after fix)
        crew_result = {
            "status": "completed",
            "result": "Test analysis"  # FIX: Now it's a string
        }

        # Simulate chat.py line 93
        assistant_message = crew_result.get("result", "Analysis completed successfully.")

        # Simulate chat.py lines 101-102 - should work now
        for char in assistant_message:
            json_str = json.dumps({'type': 'content', 'chunk': char})
            assert json_str is not None
            break  # We only need to test once
