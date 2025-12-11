"""
Unified settings loader that merges environment variables with database settings.
Database settings override environment variables when present.
"""

from typing import Any, Optional
from functools import lru_cache
from sqlmodel import Session, select
import logging

from app.config.settings import Settings, get_settings as get_env_settings
from app.models.settings import AppSettings

logger = logging.getLogger(__name__)


class UnifiedSettings:
    """
    Unified settings that combines environment variables and database settings.
    Database settings take precedence over environment variables.
    """

    def __init__(self, env_settings: Settings, db_settings: dict):
        self._env_settings = env_settings
        self._db_settings = db_settings

    def _convert_value(self, value: str, value_type: str) -> Any:
        """Convert string value to appropriate type."""
        if value_type == "bool":
            return value.lower() in ("true", "1", "yes", "on")
        elif value_type == "int":
            return int(value)
        elif value_type == "float":
            return float(value)
        return value

    def __getattr__(self, name: str) -> Any:
        """
        Get setting value. Database settings override environment settings.
        Falls back to environment settings if not in database.
        """
        # Check database settings first
        if name in self._db_settings:
            db_value, db_type = self._db_settings[name]
            return self._convert_value(db_value, db_type)

        # Fall back to environment settings
        if hasattr(self._env_settings, name):
            return getattr(self._env_settings, name)

        raise AttributeError(f"Setting '{name}' not found in database or environment")

    def get(self, name: str, default: Any = None) -> Any:
        """Get setting with default value if not found."""
        try:
            return self.__getattr__(name)
        except AttributeError:
            return default


def load_db_settings(session: Session) -> dict:
    """Load all settings from database into a dictionary."""
    db_settings = {}
    try:
        stmt = select(AppSettings)
        settings = session.exec(stmt).all()

        for setting in settings:
            db_settings[setting.key] = (setting.value, setting.value_type)

        logger.debug(f"📊 Loaded {len(db_settings)} settings from database")
    except Exception as e:
        logger.warning(f"⚠️  Failed to load database settings: {str(e)}")

    return db_settings


def get_unified_settings(session: Session) -> UnifiedSettings:
    """
    Get unified settings that merge environment and database settings.
    Database settings take precedence.

    Args:
        session: Database session

    Returns:
        UnifiedSettings object with merged settings
    """
    env_settings = get_env_settings()
    db_settings = load_db_settings(session)

    return UnifiedSettings(env_settings, db_settings)


def get_setting_value(session: Session, key: str, default: Any = None) -> Any:
    """
    Get a single setting value from database or environment.

    Args:
        session: Database session
        key: Setting key
        default: Default value if not found

    Returns:
        Setting value or default
    """
    # Try database first
    stmt = select(AppSettings).where(AppSettings.key == key)
    setting = session.exec(stmt).first()

    if setting:
        # Convert value based on type
        if setting.value_type == "bool":
            return setting.value.lower() in ("true", "1", "yes", "on")
        elif setting.value_type == "int":
            return int(setting.value)
        elif setting.value_type == "float":
            return float(setting.value)
        return setting.value

    # Fall back to environment settings
    env_settings = get_env_settings()
    if hasattr(env_settings, key):
        return getattr(env_settings, key)

    return default


def get_setting_value_simple(key: str, default: Any = None) -> Any:
    """
    Get a single setting value from database or environment.
    Creates its own database session.

    WARNING: This creates a new database session on each call.
    For multiple settings, use get_unified_settings() or get_setting_value() with a shared session.

    Args:
        key: Setting key
        default: Default value if not found

    Returns:
        Setting value or default
    """
    try:
        from app.config.database import get_session

        with get_session() as session:
            return get_setting_value(session, key, default)
    except Exception as e:
        logger.warning(f"⚠️  Failed to get setting '{key}' from database: {str(e)}")
        # Fall back to environment settings
        env_settings = get_env_settings()
        if hasattr(env_settings, key):
            return getattr(env_settings, key)
        return default
