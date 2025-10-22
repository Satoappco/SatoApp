"""Database connection management."""

import os
import logging
from typing import Optional
from sqlalchemy import create_engine, Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

logger = logging.getLogger(__name__)


def get_database_url() -> str:
    """
    Get database URL from environment variables.

    Supports both DATABASE_URL (full URL) or individual components.

    Returns:
        Database connection URL

    Raises:
        ValueError: If required environment variables are missing
    """
    # Option 1: Use DATABASE_URL if provided
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        logger.debug("Using DATABASE_URL from environment")
        return database_url

    # Option 2: Build from components
    db_user = os.getenv("DB_USER")
    db_password = os.getenv("DB_PASSWORD")
    db_host = os.getenv("DB_HOST")
    db_port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_NAME")

    if not all([db_user, db_password, db_host, db_name]):
        missing = []
        if not db_user:
            missing.append("DB_USER")
        if not db_password:
            missing.append("DB_PASSWORD")
        if not db_host:
            missing.append("DB_HOST")
        if not db_name:
            missing.append("DB_NAME")

        raise ValueError(
            f"Missing required database environment variables: {', '.join(missing)}. "
            "Please set DATABASE_URL or (DB_USER, DB_PASSWORD, DB_HOST, DB_NAME)"
        )

    database_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    logger.debug(f"Built database URL from components: {db_user}@{db_host}:{db_port}/{db_name}")

    return database_url


# Global engine instance (singleton)
_engine: Optional[Engine] = None


def get_db_engine(pooling: bool = True) -> Engine:
    """
    Get or create the database engine.

    Args:
        pooling: Whether to use connection pooling (default: True)

    Returns:
        SQLAlchemy engine instance
    """
    global _engine

    if _engine is None:
        database_url = get_database_url()

        engine_kwargs = {
            "echo": os.getenv("SQL_ECHO", "false").lower() == "true",
        }

        # Disable pooling if requested (useful for serverless environments)
        if not pooling:
            engine_kwargs["poolclass"] = NullPool

        logger.info(f"🔌 [Database] Creating database engine (pooling={pooling})")
        _engine = create_engine(database_url, **engine_kwargs)
        logger.info("✅ [Database] Database engine created successfully")

    return _engine


def get_db_connection() -> Session:
    """
    Get a database session.

    Returns:
        SQLAlchemy session instance

    Usage:
        ```python
        with get_db_connection() as session:
            result = session.execute(query)
        ```
    """
    engine = get_db_engine()
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    logger.debug("📊 [Database] Creating new database session")
    return SessionLocal()


def close_db_engine():
    """Close the global database engine."""
    global _engine
    if _engine:
        logger.info("🔌 [Database] Closing database engine")
        _engine.dispose()
        _engine = None
