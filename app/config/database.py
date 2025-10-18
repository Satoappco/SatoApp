"""
Database configuration and connection management
"""

from sqlmodel import create_engine, Session
from sqlalchemy.engine import Engine
from typing import Generator
from .settings import get_settings

settings = get_settings()

# Create database engine
engine: Engine = create_engine(
    settings.database_url,
    echo=settings.database_echo,
    pool_pre_ping=True,
    pool_recycle=300,
)


def get_session():
    """Get database session as context manager"""
    return Session(engine)


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
