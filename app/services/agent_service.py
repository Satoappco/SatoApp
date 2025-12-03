"""
Agent management business logic service
"""

import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from app.core.database import db_manager
from app.core.exceptions import AgentException
from app.config.logging import get_logger

logger = get_logger("services.agent")


class AgentService:
    """Service for managing AI agent configurations"""

    def __init__(self):
        self._db_manager = None

    @property
    def db_manager(self):
        if self._db_manager is None:
            self._db_manager = db_manager
        return self._db_manager

    def _convert_datetime_to_string(
        self, data: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Convert datetime objects to ISO string format and deserialize JSON fields"""
        if data is None:
            return {}

        # Create a copy to avoid modifying the original
        converted_data = data.copy()

        # Convert datetime fields to strings
        for field in ["created_at", "updated_at"]:
            if field in converted_data and isinstance(converted_data[field], datetime):
                converted_data[field] = converted_data[field].isoformat()

        # Deserialize JSON fields for API response
        for field in ["capabilities", "tools"]:
            if field in converted_data and isinstance(converted_data[field], str):
                try:
                    converted_data[field] = json.loads(converted_data[field])
                except (json.JSONDecodeError, TypeError):
                    # If it's not valid JSON, keep as is or set default
                    if field == "capabilities":
                        converted_data[field] = {}
                    elif field == "tools":
                        converted_data[field] = []

        return converted_data

    def get_all_agents(self) -> Dict[str, Any]:
        """Get all agent configurations

        The master agent is identified by having 'master' in its name (case-insensitive).
        Falls back to first active agent if no master agent is found.
        """
        try:
            # Get all agents
            all_agents = self.db_manager.get_all_specialist_agents()
            agents = [self._convert_datetime_to_string(agent) for agent in all_agents]

            # Find agent with "master" in name (case-insensitive)
            master_agent = None
            for agent in agents:
                agent_name = agent.get("name", "").lower()
                if "master" in agent_name:
                    master_agent = agent
                    logger.info(f"Found master agent: {agent.get('name')}")
                    break

            # If no "master" agent found, use first active agent as fallback
            if not master_agent:
                for agent in agents:
                    if agent.get("is_active", True):
                        master_agent = agent
                        logger.info(
                            f"No master agent found, using first active agent: {agent.get('name')}"
                        )
                        break

            return {
                "master_agent": master_agent,  # Agent with "master" in name
                "specialist_agents": agents,  # All agents (including the master if found)
                "total_agents": len(agents),
            }

        except Exception as e:
            logger.error(f"Failed to get all agents: {str(e)}")
            raise AgentException(f"Failed to get all agents: {str(e)}")

    def get_agent_config(self, agent_name: str) -> Optional[Dict[str, Any]]:
        """Get specific agent configuration"""
        try:
            agent_config = self.db_manager.get_agent_config(agent_name)
            return self._convert_datetime_to_string(agent_config)

        except Exception as e:
            logger.error(f"Failed to get agent config for {agent_name}: {str(e)}")
            raise AgentException(f"Failed to get agent config: {str(e)}")

    def _validate_task_template(self, task: str) -> tuple[bool, str]:
        """Validate task template and return detailed error information"""
        if not task:
            return True, ""

        # Define all valid placeholders that can be used in task templates
        valid_placeholders = {
            "objective",
            "campaigner_id",
            "customer_id",
            "customer_name",
            "intent_name",
            "data_sources",
            "data_source",
            "available_specialists",
            "date_range",
            "timezone",
            "currency",
            "attribution_window",
            "current_date",
        }

        try:
            import re

            # Extract all placeholders from the template using regex
            placeholder_pattern = r"\{([^}]+)\}"
            found_placeholders = set(re.findall(placeholder_pattern, task))

            # Check for invalid placeholders
            invalid_placeholders = found_placeholders - valid_placeholders
            if invalid_placeholders:
                return (
                    False,
                    f"❌ Invalid placeholders found: {', '.join(sorted(invalid_placeholders))}. Valid placeholders are: {', '.join(sorted(valid_placeholders))}",
                )

            # Check for syntax errors (unclosed braces, etc.)
            open_braces = task.count("{")
            close_braces = task.count("}")
            if open_braces != close_braces:
                return (
                    False,
                    "❌ Mismatched braces found. Make sure all placeholders are properly opened with { and closed with }",
                )

            # Check for empty placeholders
            if "{}" in task:
                return (
                    False,
                    "❌ Empty placeholders {} found. Please specify the placeholder name.",
                )

            # Test with minimal dummy data only for found placeholders to catch format errors
            if found_placeholders:
                dummy_data = {
                    placeholder: f"test_{placeholder}"
                    for placeholder in found_placeholders
                }
                task.format(**dummy_data)

            return True, ""

        except (KeyError, ValueError) as e:
            return False, f"❌ Template formatting error: {str(e)}"

    def create_or_update_agent(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create or update agent configuration - agent_type is no longer used"""
        try:
            # Validate required fields
            required_fields = ["name", "role", "goal"]
            for field in required_fields:
                if not config_data.get(field):
                    raise AgentException(f"Missing required field: {field}")

            # Validate task template if provided
            if config_data.get("task"):
                is_valid, error_message = self._validate_task_template(
                    config_data["task"]
                )
                if not is_valid:
                    raise AgentException(
                        f"Task template validation failed: {error_message}"
                    )

            # No longer auto-assigning tools/data sources based on agent_type
            # Tools and data sources should be manually configured per agent
            # This gives users more flexibility in agent configuration

            # Set default values
            config_data.setdefault("capabilities", {})
            config_data.setdefault("tools", [])
            config_data.setdefault("max_iterations", 3)
            config_data.setdefault("is_active", True)
            config_data.setdefault("created_by_user_id", 7001)  # Default user

            # Serialize capabilities and tools to JSON strings for database storage
            if isinstance(config_data.get("capabilities"), dict):
                config_data["capabilities"] = json.dumps(config_data["capabilities"])
            if isinstance(config_data.get("tools"), list):
                config_data["tools"] = json.dumps(config_data["tools"])

            # Store in database
            result = self.db_manager.upsert_agent_config(config_data)

            # Convert back to objects for response
            return self._convert_datetime_to_string(result)

        except AgentException:
            raise
        except Exception as e:
            logger.error(f"Failed to create/update agent: {str(e)}")
            raise AgentException(f"Failed to create/update agent: {str(e)}")

    def deactivate_agent(self, agent_name: str) -> bool:
        """Deactivate an agent configuration"""
        try:
            # Check if agent exists
            existing_agent = self.get_agent_config(agent_name)
            if not existing_agent:
                raise AgentException(f"Agent type '{agent_name}' not found")

            # Deactivate agent
            config_data = {"agent_name": agent_name, "is_active": False}

            self.db_manager.upsert_agent_config(config_data)
            return True

        except AgentException:
            raise
        except Exception as e:
            logger.error(f"Failed to deactivate agent {agent_name}: {str(e)}")
            raise AgentException(f"Failed to deactivate agent: {str(e)}")

    def toggle_agent_status(self, agent_name: str, is_active: bool) -> bool:
        """Toggle agent active/inactive status by name"""
        try:
            # Check if agent exists (including inactive ones)
            existing_agent = self.db_manager.get_agent_config_by_name(
                agent_name, include_inactive=True
            )
            if not existing_agent:
                raise AgentException(f"Agent with name '{agent_name}' not found")

            # Toggle status
            config_data = {"name": agent_name, "is_active": is_active}

            self.db_manager.upsert_agent_config(config_data)
            return True

        except AgentException:
            raise
        except Exception as e:
            logger.error(f"Failed to toggle agent status {agent_name}: {str(e)}")
            raise AgentException(f"Failed to toggle agent status: {str(e)}")

    def permanent_delete_agent(self, agent_name: str) -> bool:
        """Permanently delete an agent configuration from database by name"""
        try:
            logger.info(f"Attempting to permanently delete agent: {agent_name}")

            # Check if agent exists (including inactive ones)
            existing_agent = self.db_manager.get_agent_config_by_name(
                agent_name, include_inactive=True
            )
            logger.info(f"Agent lookup result: {existing_agent is not None}")

            if not existing_agent:
                logger.error(f"Agent with name '{agent_name}' not found in database")
                raise AgentException(f"Agent with name '{agent_name}' not found")

            logger.info(
                f"Found agent: {existing_agent.get('name', 'Unknown')} (ID: {existing_agent.get('id', 'Unknown')})"
            )

            # Permanently delete from database
            success = self.db_manager.delete_agent_config(agent_name)
            logger.info(f"Delete operation result: {success}")

            if not success:
                raise AgentException(
                    f"Failed to delete agent {agent_name} from database"
                )

            logger.info(f"Successfully deleted agent {agent_name}")
            return True

        except AgentException as e:
            logger.error(f"AgentException in permanent_delete_agent: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in permanent_delete_agent: {str(e)}")
            raise AgentException(f"Failed to permanently delete agent: {str(e)}")

    # def validate_agent_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
    #     """Validate agent configuration"""
    #     errors = []

    #     # Required field validation
    #     required_fields = {
    #         'role': 'Role is required',
    #         'goal': 'Goal is required',
    #         'backstory': 'Backstory is required',
    #         'name': 'Name is required',
    #     }

    #     for field, error_msg in required_fields.items():
    #         if not config.get(field):
    #             errors.append(error_msg)

    #     # Max iterations validation
    #     max_iterations = config.get('max_iterations', 3)
    #     if not isinstance(max_iterations, int) or max_iterations < 1 or max_iterations > 10:
    #         errors.append('Max iterations must be between 1 and 10')

    #     # Agent type validation
    #     valid_agent_types = ['master', 'google_analytics', 'facebook_ads', 'content_analysis']
    #     if config.get('name', '') not in valid_agent_types:
    #         errors.append(f"Agent type must be one of: {', '.join(valid_agent_types)}")

    #     return {
    #         'valid': len(errors) == 0,
    #         'errors': errors
    #     }
