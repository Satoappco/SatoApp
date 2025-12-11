#!/usr/bin/env python3
"""
Script to create the tasks table in the database.

This script creates the tasks table using the SQLModel metadata.
Run from the sato-be directory with: python scripts/create_tasks_table.py
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlmodel import SQLModel
from app.config.database import get_engine
from app.models.tasks import Task, TaskPriority, TaskStatus
from app.models.users import Campaigner, Customer
from app.models.base import BaseModel


def create_tasks_table():
    """Create the tasks table if it doesn't exist."""
    engine = get_engine()

    print("📊 Creating tasks table...")
    print(f"   Database: {engine.url.database}")
    print(f"   Host: {engine.url.host}")

    try:
        # Create only the tasks table
        Task.__table__.create(engine, checkfirst=True)
        print("✅ Tasks table created successfully!")

        # Show table info
        from sqlalchemy import inspect
        inspector = inspect(engine)

        if inspector.has_table("tasks"):
            print("\n📋 Table structure:")
            columns = inspector.get_columns("tasks")
            for col in columns:
                nullable = "NULL" if col['nullable'] else "NOT NULL"
                print(f"   - {col['name']}: {col['type']} {nullable}")

            # Show foreign keys
            foreign_keys = inspector.get_foreign_keys("tasks")
            if foreign_keys:
                print("\n🔗 Foreign keys:")
                for fk in foreign_keys:
                    print(f"   - {fk['constrained_columns']} -> {fk['referred_table']}.{fk['referred_columns']}")

            # Show indexes
            indexes = inspector.get_indexes("tasks")
            if indexes:
                print("\n📇 Indexes:")
                for idx in indexes:
                    print(f"   - {idx['name']}: {idx['column_names']}")
        else:
            print("⚠️  Warning: Table was not created")

    except Exception as e:
        print(f"❌ Error creating tasks table: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    create_tasks_table()
