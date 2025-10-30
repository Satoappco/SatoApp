"""
Settings models for managing application configuration
"""

from datetime import datetime
from typing import Optional
from sqlmodel import Field, SQLModel
from app.models.base import BaseModel


class AppSettings(BaseModel, table=True):
    """
    Application settings that can be managed by admins.
    These override environment variables when set.
    """
    __tablename__ = "app_settings"

    key: str = Field(unique=True, index=True, description="Setting key (e.g., 'master_agent_max_iterations')")
    value: str = Field(description="Setting value as string")
    value_type: str = Field(default="string", description="Type of value: string, int, bool, float")
    category: str = Field(default="general", description="Setting category: general, agent, performance, oauth, etc.")
    description: Optional[str] = Field(default=None, description="Human-readable description")
    is_secret: bool = Field(default=False, description="Whether this is a sensitive value (API key, secret, etc.)")
    is_editable: bool = Field(default=True, description="Whether admins can edit this value")
    requires_restart: bool = Field(default=False, description="Whether changing this requires service restart")

    # Audit fields
    updated_by_id: Optional[int] = Field(default=None, foreign_key="campaigners.id")

    class Config:
        json_schema_extra = {
            "example": {
                "key": "master_agent_max_iterations",
                "value": "5",
                "value_type": "int",
                "category": "agent",
                "description": "Maximum number of iterations for master agent",
                "is_secret": False,
                "is_editable": True,
                "requires_restart": False
            }
        }


class SettingCategory(SQLModel):
    """Helper model for grouping settings"""
    name: str
    display_name: str
    description: str
    icon: Optional[str] = None


# Define setting categories
SETTING_CATEGORIES = {
    "general": SettingCategory(
        name="general",
        display_name="General",
        description="General application settings",
        icon="⚙️"
    ),
    "agent": SettingCategory(
        name="agent",
        display_name="AI Agents",
        description="AI agent configuration",
        icon="🤖"
    ),
    "performance": SettingCategory(
        name="performance",
        display_name="Performance",
        description="Performance and resource management",
        icon="⚡"
    ),
    "oauth": SettingCategory(
        name="oauth",
        display_name="OAuth & Authentication",
        description="OAuth provider configuration",
        icon="🔐"
    ),
    "integration": SettingCategory(
        name="integration",
        display_name="Integrations",
        description="Third-party integrations",
        icon="🔗"
    ),
    "monitoring": SettingCategory(
        name="monitoring",
        display_name="Monitoring",
        description="Logging and monitoring",
        icon="📊"
    )
}


# Default settings to be created on first run
DEFAULT_SETTINGS = [
    # General settings
    {
        "key": "app_name",
        "value": "Sato AI SEO Assistant",
        "value_type": "string",
        "category": "general",
        "description": "Application name",
        "is_editable": True,
        "requires_restart": False
    },
    {
        "key": "frontend_url",
        "value": "https://localhost:3000",
        "value_type": "string",
        "category": "general",
        "description": "Frontend application URL",
        "is_editable": True,
        "requires_restart": True
    },

    # Agent settings
    {
        "key": "master_agent_max_iterations",
        "value": "3",
        "value_type": "int",
        "category": "agent",
        "description": "Maximum iterations for master agent",
        "is_editable": True,
        "requires_restart": False
    },
    {
        "key": "master_agent_timeout",
        "value": "120",
        "value_type": "int",
        "category": "agent",
        "description": "Timeout in seconds for master agent operations",
        "is_editable": True,
        "requires_restart": False
    },
    {
        "key": "parallel_specialists",
        "value": "true",
        "value_type": "bool",
        "category": "agent",
        "description": "Enable parallel specialist agent execution",
        "is_editable": True,
        "requires_restart": False
    },
    {
        "key": "cache_specialist_results",
        "value": "true",
        "value_type": "bool",
        "category": "agent",
        "description": "Cache specialist agent results",
        "is_editable": True,
        "requires_restart": False
    },
    {
        "key": "cache_ttl_seconds",
        "value": "3600",
        "value_type": "int",
        "category": "agent",
        "description": "Cache time-to-live in seconds",
        "is_editable": True,
        "requires_restart": False
    },

    # Performance settings
    {
        "key": "max_concurrent_analyses",
        "value": "10",
        "value_type": "int",
        "category": "performance",
        "description": "Maximum concurrent analysis operations",
        "is_editable": True,
        "requires_restart": False
    },
    {
        "key": "request_timeout_seconds",
        "value": "30",
        "value_type": "int",
        "category": "performance",
        "description": "API request timeout in seconds",
        "is_editable": True,
        "requires_restart": False
    },

    # OAuth settings
    {
        "key": "google_client_id",
        "value": "",
        "value_type": "string",
        "category": "oauth",
        "description": "Google OAuth Client ID",
        "is_secret": False,
        "is_editable": True,
        "requires_restart": True
    },
    {
        "key": "google_client_secret",
        "value": "",
        "value_type": "string",
        "category": "oauth",
        "description": "Google OAuth Client Secret",
        "is_secret": True,
        "is_editable": True,
        "requires_restart": True
    },
    {
        "key": "facebook_app_id",
        "value": "",
        "value_type": "string",
        "category": "oauth",
        "description": "Facebook App ID",
        "is_secret": False,
        "is_editable": True,
        "requires_restart": True
    },
    {
        "key": "facebook_app_secret",
        "value": "",
        "value_type": "string",
        "category": "oauth",
        "description": "Facebook App Secret",
        "is_secret": True,
        "is_editable": True,
        "requires_restart": True
    },
    {
        "key": "facebook_api_version",
        "value": "v18.0",
        "value_type": "string",
        "category": "oauth",
        "description": "Facebook API version",
        "is_editable": True,
        "requires_restart": True
    },

    # Integration settings
    {
        "key": "gemini_api_key",
        "value": "",
        "value_type": "string",
        "category": "integration",
        "description": "Google Gemini API Key",
        "is_secret": True,
        "is_editable": True,
        "requires_restart": True
    },
    {
        "key": "chat_provider",
        "value": "backend",
        "value_type": "string",
        "category": "integration",
        "description": "Chat provider (backend, dialogflow, or other)",
        "is_secret": False,
        "is_editable": True,
        "requires_restart": True
    },

    # Monitoring settings
    {
        "key": "log_level",
        "value": "INFO",
        "value_type": "string",
        "category": "monitoring",
        "description": "Logging level (DEBUG, INFO, WARNING, ERROR)",
        "is_editable": True,
        "requires_restart": False
    },
    {
        "key": "sentry_dsn",
        "value": "",
        "value_type": "string",
        "category": "monitoring",
        "description": "Sentry DSN for error tracking",
        "is_secret": True,
        "is_editable": True,
        "requires_restart": True
    }
]
