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
    """Initialize database tables"""
    from app.models import (
        BaseModel, User, Customer, SubCustomer, UserSession,
        AgentConfig, RoutingRule, AnalysisExecution,
        DigitalAsset, Connection, PerformanceMetric, AnalyticsCache, KpiCatalog,
        ChatMessage, WebhookEntry, NarrativeReport
    )
    from sqlmodel import SQLModel
    
    SQLModel.metadata.create_all(engine)


def get_database_url():
    """Get database URL for migrations"""
    return settings.database_url
