"""
Database configuration and connection management
"""

from sqlmodel import create_engine, Session
from sqlalchemy.engine import Engine
from typing import Generator, Optional
from .settings import get_settings

settings = get_settings()

# Lazy database engine creation
_engine: Optional[Engine] = None


def get_engine() -> Engine:
    """Get or create database engine (lazy initialization)"""
    global _engine
    if _engine is None:
        if not settings.database_url:
            raise ValueError(
                "DATABASE_URL is not configured. Please set the DATABASE_URL environment variable."
            )
        _engine = create_engine(
            settings.database_url,
            echo=settings.database_echo,
            pool_pre_ping=True,
            pool_recycle=300,
        )
    return _engine


def get_session():
    """Get database session as context manager"""
    return Session(get_engine())


def init_database():
    """Initialize database tables
    
    Note: We use Alembic for migrations, so we don't need to create tables here.
    This function just imports the models to ensure they're registered.
    """
    from app.models import (
        BaseModel, Campaigner, Agency, Customer, CampaignerSession,
        AgentConfig, RoutingRule,
        DigitalAsset, Connection, KpiGoal, UserPropertySelection, KpiCatalog,
        RTMTable, QuestionsTable
    )
    from sqlmodel import SQLModel
    
    # Don't create tables - we use Alembic migrations for that
    # SQLModel.metadata.create_all(engine)
    pass


def get_database_url():
    """Get database URL for migrations"""
    return settings.database_url
