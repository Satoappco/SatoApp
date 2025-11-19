"""Langfuse configuration and initialization."""

import os
from typing import Optional
from langfuse import Langfuse
import logging

logger = logging.getLogger(__name__)

# Initialize CrewAI and LiteLLM instrumentation for Langfuse
_instrumentation_initialized = False

def _initialize_instrumentation():
    """Initialize OpenInference instrumentation for CrewAI and LiteLLM."""
    global _instrumentation_initialized
    if _instrumentation_initialized:
        return

    crewai_instrumented = False
    litellm_instrumented = False

    # Try to instrument CrewAI
    try:
        from openinference.instrumentation.crewai import CrewAIInstrumentor
        CrewAIInstrumentor().instrument(skip_dep_check=True)
        crewai_instrumented = True
        logger.info("✅ CrewAI instrumentation initialized for Langfuse")
    except ImportError as e:
        logger.warning(f"⚠️  CrewAI instrumentation not available: {e}")
    except Exception as e:
        logger.error(f"❌ Failed to initialize CrewAI instrumentation: {e}")

    # Try to instrument LiteLLM (may not be available)
    try:
        from openinference.instrumentation.litellm import LiteLLMInstrumentor
        LiteLLMInstrumentor().instrument()
        litellm_instrumented = True
        logger.info("✅ LiteLLM instrumentation initialized for Langfuse")
    except ImportError as e:
        logger.debug(f"LiteLLM instrumentation not available (not using LiteLLM): {e}")
    except Exception as e:
        logger.warning(f"⚠️  Failed to initialize LiteLLM instrumentation: {e}")

    if crewai_instrumented or litellm_instrumented:
        _instrumentation_initialized = True


class LangfuseConfig:
    """Langfuse configuration and client management."""

    _instance: Optional[Langfuse] = None
    _enabled: bool = False

    @classmethod
    def initialize(cls) -> Optional[Langfuse]:
        """Initialize Langfuse client.

        Returns:
            Langfuse client instance if enabled, None otherwise
        """
        if cls._instance is not None:
            return cls._instance

        # Initialize instrumentation first
        _initialize_instrumentation()

        # Try to get settings from database first, fall back to environment variables
        enabled = False
        public_key = None
        secret_key = None
        host = "https://cloud.langfuse.com"

        try:
            from app.config.database import get_session
            from app.models.settings import AppSettings
            from sqlmodel import select

            with get_session() as session:
                # Get Langfuse enabled setting
                enabled_setting = session.exec(
                    select(AppSettings).where(AppSettings.key == "langfuse_enabled")
                ).first()
                if enabled_setting:
                    enabled = enabled_setting.value.lower() == "true"

                # Get public key
                public_key_setting = session.exec(
                    select(AppSettings).where(AppSettings.key == "langfuse_public_key")
                ).first()
                if public_key_setting and public_key_setting.value:
                    public_key = public_key_setting.value

                # Get secret key
                secret_key_setting = session.exec(
                    select(AppSettings).where(AppSettings.key == "langfuse_secret_key")
                ).first()
                if secret_key_setting and secret_key_setting.value:
                    secret_key = secret_key_setting.value

                # Get host
                host_setting = session.exec(
                    select(AppSettings).where(AppSettings.key == "langfuse_host")
                ).first()
                if host_setting and host_setting.value:
                    host = host_setting.value

        except Exception as e:
            logger.debug(f"Could not load Langfuse settings from database: {e}. Falling back to environment variables.")

        # Fall back to environment variables if database settings not available
        if not enabled:
            enabled = os.getenv("LANGFUSE_ENABLED", "false").lower() == "true"
        if not public_key:
            public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
        if not secret_key:
            secret_key = os.getenv("LANGFUSE_SECRET_KEY")
        if host == "https://cloud.langfuse.com":
            host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")

        if not public_key or not secret_key:
            logger.warning(
                "Langfuse is enabled but LANGFUSE_PUBLIC_KEY or LANGFUSE_SECRET_KEY not set. "
                "Observability will be disabled."
            )
            cls._enabled = False
            return None

        try:
            cls._instance = Langfuse(
                public_key=public_key,
                secret_key=secret_key,
                host=host
            )
            cls._enabled = True
            logger.info(f"✅ Langfuse initialized successfully (host: {host})")
            return cls._instance
        except Exception as e:
            logger.error(f"❌ Failed to initialize Langfuse: {e}")
            cls._enabled = False
            return None

    @classmethod
    def get_client(cls) -> Optional[Langfuse]:
        """Get Langfuse client instance.

        Returns:
            Langfuse client if initialized and enabled, None otherwise
        """
        if cls._instance is None:
            cls.initialize()
        return cls._instance

    @classmethod
    def is_enabled(cls) -> bool:
        """Check if Langfuse is enabled.

        Returns:
            True if Langfuse is enabled and initialized
        """
        if cls._instance is None:
            cls.initialize()
        return cls._enabled

    @classmethod
    def flush(cls):
        """Flush any pending traces to Langfuse."""
        if cls._instance and cls._enabled:
            try:
                cls._instance.flush()
            except Exception as e:
                logger.error(f"❌ Failed to flush Langfuse traces: {e}")


# Initialize on module import
langfuse_client = LangfuseConfig.get_client()
