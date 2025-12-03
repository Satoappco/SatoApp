"""
E2E test configuration - ensures database tables are created for E2E tests
"""

import pytest
import os
import tempfile
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.models.base import BaseModel


@pytest.fixture(scope="session", autouse=True)
def setup_e2e_database():
    """
    Automatically set up database tables for E2E tests.

    For SQLite in-memory databases, creates a file-based database instead
    to avoid per-connection database issues.

    Runs at session scope to ensure it happens before app imports.
    """
    # Get DATABASE_URL from environment (set by CI or local testing)
    database_url = os.getenv("DATABASE_URL", "sqlite:///:memory:")

    # For SQLite :memory:, use a temporary file instead
    # This avoids the issue where each connection gets a fresh empty database
    temp_db = None
    if database_url == "sqlite:///:memory:":
        temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        database_url = f"sqlite:///{temp_db.name}"
        # Override the environment variable so the app uses the same database
        os.environ["DATABASE_URL"] = database_url

    # Only set up if using SQLite (PostgreSQL would need manual setup)
    if database_url.startswith("sqlite"):
        # Create engine with same settings as the app would use
        engine = create_engine(
            database_url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            echo=False,
        )

        # Create all tables
        BaseModel.metadata.create_all(bind=engine)
        engine.dispose()

        yield

        # Cleanup
        if temp_db:
            try:
                os.unlink(temp_db.name)
            except Exception:
                pass  # Ignore cleanup errors
    else:
        # For non-SQLite databases, assume tables are already set up
        yield
