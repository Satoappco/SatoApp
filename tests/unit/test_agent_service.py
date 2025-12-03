"""
Unit tests for AgentService
"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime
from app.services.agent_service import AgentService


@pytest.fixture
def agent_service():
    """Create AgentService instance."""
    return AgentService()


class TestAgentService:
    """Test AgentService functionality."""

    def test_init(self, agent_service):
        """Test AgentService initialization."""
        assert agent_service.db_manager is not None

    def test_convert_datetime_to_string_none_input(self, agent_service):
        """Test _convert_datetime_to_string with None input."""
        result = agent_service._convert_datetime_to_string(None)
        assert result == {}

    def test_convert_datetime_to_string_with_datetimes(self, agent_service):
        """Test _convert_datetime_to_string with datetime fields."""
        test_datetime = datetime(2023, 1, 1, 12, 0, 0)
        data = {
            "created_at": test_datetime,
            "updated_at": test_datetime,
            "name": "test_agent",
            "capabilities": '{"test": "value"}',
            "tools": '["tool1", "tool2"]',
        }

        result = agent_service._convert_datetime_to_string(data)

        assert result["created_at"] == "2023-01-01T12:00:00"
        assert result["updated_at"] == "2023-01-01T12:00:00"
        assert result["name"] == "test_agent"
        assert result["capabilities"] == {"test": "value"}
        assert result["tools"] == ["tool1", "tool2"]

    def test_convert_datetime_to_string_invalid_json(self, agent_service):
        """Test _convert_datetime_to_string with invalid JSON."""
        data = {"capabilities": "invalid json", "tools": "also invalid"}

        result = agent_service._convert_datetime_to_string(data)

        assert result["capabilities"] == {}
        assert result["tools"] == []

    @patch("app.services.agent_service.db_manager")
    def test_get_all_agents_success(self, mock_db_manager, agent_service):
        """Test successful get_all_agents."""
        mock_agents = [
            {
                "name": "master_agent",
                "is_active": True,
                "created_at": datetime(2023, 1, 1),
                "capabilities": '{"role": "master"}',
                "tools": '["tool1"]',
            },
            {
                "name": "worker_agent",
                "is_active": False,
                "created_at": datetime(2023, 1, 2),
                "capabilities": '{"role": "worker"}',
                "tools": '["tool2"]',
            },
        ]

        mock_db_manager.get_all_specialist_agents.return_value = mock_agents

        result = agent_service.get_all_agents()

        assert result["master_agent"] is not None
        assert len(result["specialist_agents"]) == 2
        assert result["total_agents"] == 2

        # Verify master agent identification
        master_agent = result["master_agent"]
        assert master_agent["name"] == "master_agent"

        mock_db_manager.get_all_specialist_agents.assert_called_once()

    @patch("app.services.agent_service.db_manager")
    def test_get_all_agents_empty_result(self, mock_db_manager, agent_service):
        """Test get_all_agents with no agents."""
        mock_db_manager.get_all_specialist_agents.return_value = []

        result = agent_service.get_all_agents()

        assert result["master_agent"] is None
        assert result["specialist_agents"] == []
        assert result["total_agents"] == 0
        mock_db_manager.get_all_specialist_agents.assert_called_once()

    @patch("app.services.agent_service.db_manager")
    def test_get_agent_config_found(self, mock_db_manager, agent_service):
        """Test get_agent_config when agent exists."""
        mock_agent = {
            "name": "test_agent",
            "is_active": True,
            "created_at": datetime(2023, 1, 1),
            "capabilities": '{"role": "test"}',
            "tools": '["tool1"]',
        }

        mock_db_manager.get_agent_config.return_value = mock_agent

        result = agent_service.get_agent_config("test_agent")

        assert result is not None
        assert result["name"] == "test_agent"
        assert result["is_active"] is True
        assert result["capabilities"] == {"role": "test"}
        assert result["tools"] == ["tool1"]

        mock_db_manager.get_agent_config.assert_called_once_with("test_agent")

    @patch("app.services.agent_service.db_manager")
    def test_get_agent_config_not_found(self, mock_db_manager, agent_service):
        """Test get_agent_config when agent doesn't exist."""
        from app.core.exceptions import AgentException

        mock_db_manager.get_agent_config.side_effect = Exception("Agent not found")

        with pytest.raises(AgentException):
            agent_service.get_agent_config("nonexistent_agent")

        mock_db_manager.get_agent_config.assert_called_once_with("nonexistent_agent")

    def test_validate_task_template_valid(self, agent_service):
        """Test _validate_task_template with valid template."""
        valid_template = """
        You are an AI assistant.
        Your task is to: {objective}
        Context: {customer_name}
        """

        is_valid, message = agent_service._validate_task_template(valid_template)

        assert is_valid is True
        assert message == ""

    def test_validate_task_template_invalid_placeholders(self, agent_service):
        """Test _validate_task_template with invalid placeholders."""
        invalid_template = "You are an AI assistant. Task: {task_description}"

        is_valid, message = agent_service._validate_task_template(invalid_template)

        assert is_valid is False
        assert "Invalid placeholders" in message

    def test_validate_task_template_empty(self, agent_service):
        """Test _validate_task_template with empty template."""
        is_valid, message = agent_service._validate_task_template("")

        assert is_valid is True
        assert message == ""

    @patch("app.services.agent_service.db_manager")
    def test_create_or_update_agent_new_agent(self, mock_db_manager, agent_service):
        """Test create_or_update_agent for new agent."""
        config_data = {
            "name": "new_agent",
            "role": "assistant",
            "goal": "Help users with tasks",
            "backstory": "Test agent backstory",
            "capabilities": {"role": "test"},
            "tools": ["tool1", "tool2"],
            "task": "You are {objective}. Help with {customer_name}",
            "is_active": True,
        }

        # Mock the upsert_agent_config method
        mock_db_manager.upsert_agent_config.return_value = {
            "id": 1,
            "name": "new_agent",
            "role": "assistant",
            "goal": "Help users with tasks",
            "backstory": "Test agent backstory",
            "capabilities": '{"role": "test"}',
            "tools": '["tool1", "tool2"]',
            "task": "You are {objective}. Help with {customer_name}",
            "is_active": True,
            "created_at": "2023-01-01T00:00:00",
            "updated_at": "2023-01-01T00:00:00",
        }

        result = agent_service.create_or_update_agent(config_data)

        assert result["name"] == "new_agent"
        assert result["role"] == "assistant"
        assert result["goal"] == "Help users with tasks"

        # Verify database operations
        mock_db_manager.upsert_agent_config.assert_called_once()
        call_args = mock_db_manager.upsert_agent_config.call_args
        assert call_args[0][0]["name"] == "new_agent"

    @patch("app.services.agent_service.db_manager")
    def test_create_or_update_agent_update_existing(
        self, mock_db_manager, agent_service
    ):
        """Test create_or_update_agent for updating existing agent."""
        config_data = {
            "name": "existing_agent",
            "role": "analyst",
            "goal": "Analyze data",
            "backstory": "Updated agent backstory",
            "capabilities": {"role": "updated"},
            "tools": ["tool1"],
            "task": "Updated template: {objective}",
            "is_active": False,
        }

        # Mock the upsert_agent_config method
        mock_db_manager.upsert_agent_config.return_value = {
            "id": 1,
            "name": "existing_agent",
            "role": "analyst",
            "goal": "Analyze data",
            "backstory": "Updated agent backstory",
            "capabilities": '{"role": "updated"}',
            "tools": '["tool1"]',
            "task": "Updated template: {objective}",
            "is_active": False,
            "created_at": "2023-01-01T00:00:00",
            "updated_at": "2023-01-01T00:00:00",
        }

        result = agent_service.create_or_update_agent(config_data)

        assert result["name"] == "existing_agent"
        assert result["role"] == "analyst"
        assert result["goal"] == "Analyze data"

        # Verify database operations
        mock_db_manager.upsert_agent_config.assert_called_once()
        call_args = mock_db_manager.upsert_agent_config.call_args
        assert call_args[0][0]["name"] == "existing_agent"

    @patch("app.services.agent_service.db_manager")
    def test_create_or_update_agent_invalid_template(
        self, mock_db_manager, agent_service
    ):
        """Test create_or_update_agent with invalid task template."""
        from app.core.exceptions import AgentException

        config_data = {
            "name": "test_agent",
            "role": "assistant",
            "goal": "Help users",
            "backstory": "Test backstory",
            "task": "Invalid template {invalid_placeholder}",
        }

        with pytest.raises(AgentException) as exc_info:
            agent_service.create_or_update_agent(config_data)

        assert "template validation failed" in str(exc_info.value)

        # Should not execute database operations
        mock_db_manager.upsert_agent_config.assert_not_called()

    @patch("app.services.agent_service.db_manager")
    def test_deactivate_agent_success(self, mock_db_manager, agent_service):
        """Test successful agent deactivation."""
        # Mock that agent exists and is active
        mock_agent = {"name": "test_agent", "is_active": True}
        mock_db_manager.get_agent_config.return_value = mock_agent
        mock_db_manager.upsert_agent_config.return_value = None

        result = agent_service.deactivate_agent("test_agent")

        assert result is True
        mock_db_manager.get_agent_config.assert_called_once_with("test_agent")
        mock_db_manager.upsert_agent_config.assert_called_once()

    @patch("app.services.agent_service.db_manager")
    def test_deactivate_agent_not_found(self, mock_db_manager, agent_service):
        """Test deactivate_agent when agent doesn't exist."""
        mock_db_manager.get_agent_config.side_effect = Exception("Agent not found")

        with pytest.raises(Exception):
            agent_service.deactivate_agent("nonexistent_agent")

    @patch("app.services.agent_service.db_manager")
    def test_deactivate_agent_already_inactive(self, mock_db_manager, agent_service):
        """Test deactivate_agent when agent is already inactive."""
        mock_agent = {"name": "test_agent", "is_active": False}
        mock_db_manager.get_agent_config.return_value = mock_agent
        mock_db_manager.upsert_agent_config.return_value = None

        result = agent_service.deactivate_agent("test_agent")

        assert result is True  # Still succeeds even if already inactive
        mock_db_manager.get_agent_config.assert_called_once_with("test_agent")
        mock_db_manager.upsert_agent_config.assert_called_once()

    @patch("app.services.agent_service.db_manager")
    def test_toggle_agent_status_activate(self, mock_db_manager, agent_service):
        """Test toggle_agent_status to activate agent."""
        mock_agent = {"name": "test_agent", "is_active": False}
        mock_db_manager.get_agent_config_by_name.return_value = mock_agent
        mock_db_manager.upsert_agent_config.return_value = None

        result = agent_service.toggle_agent_status("test_agent", True)

        assert result is True
        mock_db_manager.get_agent_config_by_name.assert_called_once_with(
            "test_agent", include_inactive=True
        )
        mock_db_manager.upsert_agent_config.assert_called_once()

    @patch("app.services.agent_service.db_manager")
    def test_toggle_agent_status_deactivate(self, mock_db_manager, agent_service):
        """Test toggle_agent_status to deactivate agent."""
        mock_agent = {"name": "test_agent", "is_active": True}
        mock_db_manager.get_agent_config_by_name.return_value = mock_agent
        mock_db_manager.upsert_agent_config.return_value = None

        result = agent_service.toggle_agent_status("test_agent", False)

        assert result is True
        mock_db_manager.get_agent_config_by_name.assert_called_once_with(
            "test_agent", include_inactive=True
        )
        mock_db_manager.upsert_agent_config.assert_called_once()

    @patch("app.services.agent_service.db_manager")
    def test_toggle_agent_status_no_change(self, mock_db_manager, agent_service):
        """Test toggle_agent_status when status is already correct."""
        mock_agent = {"name": "test_agent", "is_active": True}
        mock_db_manager.get_agent_config_by_name.return_value = mock_agent
        mock_db_manager.upsert_agent_config.return_value = None

        result = agent_service.toggle_agent_status("test_agent", True)

        assert result is True  # Still succeeds even if status is same
        mock_db_manager.get_agent_config_by_name.assert_called_once_with(
            "test_agent", include_inactive=True
        )
        mock_db_manager.upsert_agent_config.assert_called_once()

    @patch("app.services.agent_service.db_manager")
    def test_permanent_delete_agent_success(self, mock_db_manager, agent_service):
        """Test successful permanent agent deletion."""
        mock_db_manager.get_agent_config_by_name.return_value = {"name": "test_agent"}
        mock_db_manager.delete_agent_config.return_value = True

        result = agent_service.permanent_delete_agent("test_agent")

        assert result is True
        mock_db_manager.get_agent_config_by_name.assert_called_once_with(
            "test_agent", include_inactive=True
        )
        mock_db_manager.delete_agent_config.assert_called_once_with("test_agent")

    @patch("app.services.agent_service.db_manager")
    def test_permanent_delete_agent_not_found(self, mock_db_manager, agent_service):
        """Test permanent_delete_agent when agent doesn't exist."""
        from app.core.exceptions import AgentException

        mock_db_manager.get_agent_config_by_name.return_value = None

        with pytest.raises(AgentException) as exc_info:
            agent_service.permanent_delete_agent("nonexistent_agent")

        assert "not found" in str(exc_info.value)
        mock_db_manager.delete_agent_config.assert_not_called()
