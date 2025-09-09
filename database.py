"""
Database configuration and models using SQLModel for PostgreSQL
"""
import os
from datetime import datetime
from typing import Optional

from sqlmodel import SQLModel, Field, create_engine, Session, select
from sqlalchemy.engine import Engine


class WebhookEntry(SQLModel, table=True):
    """Model for webhook entries table"""
    __tablename__ = "webhook_entries"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user_name: Optional[str] = Field(default=None, max_length=255)
    user_choice: Optional[str] = Field(default=None, max_length=255)
    raw_payload: str = Field(description="JSON payload as string")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class DatabaseManager:
    """Database connection and session management"""
    
    def __init__(self):
        self.engine: Optional[Engine] = None
        self._setup_engine()
    
    def _setup_engine(self):
        """Setup database engine from environment variables"""
        # For Google Cloud SQL, you can use either:
        # 1. Connection string format
        # 2. Individual components
        
        database_url = os.getenv("DATABASE_URL")
        
        if not database_url:
            # Build from individual components
            db_host = os.getenv("DB_HOST", "localhost")
            db_port = os.getenv("DB_PORT", "5432")
            db_name = os.getenv("DB_NAME", "sato_db")
            db_user = os.getenv("DB_USER", "postgres")
            db_password = os.getenv("DB_PASSWORD", "")
            
            # For Google Cloud SQL with private IP
            if os.getenv("GOOGLE_CLOUD_SQL"):
                database_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
            else:
                database_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
        
        print(f"Connecting to database: {database_url.split('@')[0]}@***")
        
        # Create engine with connection pooling for production
        self.engine = create_engine(
            database_url,
            echo=os.getenv("DB_ECHO", "false").lower() == "true",  # Enable SQL logging if needed
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,  # Verify connections before use
            pool_recycle=300,    # Recycle connections every 5 minutes
        )
    
    def create_tables(self):
        """Create all tables"""
        if self.engine:
            SQLModel.metadata.create_all(self.engine)
            print("Database tables created successfully")
    
    def get_session(self) -> Session:
        """Get database session"""
        if not self.engine:
            raise RuntimeError("Database engine not initialized")
        return Session(self.engine)
    
    def save_webhook_entry(self, user_name: Optional[str], user_choice: Optional[str], raw_payload: str) -> WebhookEntry:
        """Save a webhook entry to the database"""
        with self.get_session() as session:
            entry = WebhookEntry(
                user_name=user_name,
                user_choice=user_choice,
                raw_payload=raw_payload
            )
            session.add(entry)
            session.commit()
            session.refresh(entry)
            return entry
    
    def get_recent_entries(self, limit: int = 10) -> list[WebhookEntry]:
        """Get recent webhook entries"""
        with self.get_session() as session:
            statement = select(WebhookEntry).order_by(WebhookEntry.created_at.desc()).limit(limit)
            return session.exec(statement).all()


# Global database manager instance
db_manager = DatabaseManager()


def init_database():
    """Initialize database tables"""
    try:
        db_manager.create_tables()
        print("Database initialization completed")
    except Exception as e:
        print(f"Database initialization failed: {e}")
        raise


def get_db_session() -> Session:
    """Dependency function to get database session"""
    return db_manager.get_session()
