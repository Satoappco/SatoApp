#!/usr/bin/env python3
"""
Script to add the use_database_config setting to the database.
This can be run directly or the settings can be initialized via the API endpoint.
"""

import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlmodel import select
from app.config.database import get_session
from app.models.settings import AppSettings


def add_use_database_config_setting():
    """Add the use_database_config setting to the database."""

    setting_data = {
        "key": "use_database_config",
        "value": "true",
        "value_type": "bool",
        "category": "agent",
        "description": "Load agent configurations from database instead of using fallback prompts",
        "is_editable": True,
        "requires_restart": False
    }

    try:
        with get_session() as session:
            # Check if setting already exists
            existing = session.exec(
                select(AppSettings).where(AppSettings.key == setting_data["key"])
            ).first()

            if existing:
                print(f"⚠️  Setting '{setting_data['key']}' already exists with value: {existing.value}")
                print(f"   Current value_type: {existing.value_type}")
                print(f"   Current description: {existing.description}")

                # Update to ensure it's set to true
                if existing.value != "true":
                    existing.value = "true"
                    session.add(existing)
                    session.commit()
                    print(f"✅ Updated setting value to: true")
                else:
                    print(f"✅ Setting is already set to true")
            else:
                # Create new setting
                new_setting = AppSettings(**setting_data)
                session.add(new_setting)
                session.commit()
                print(f"✅ Successfully added '{setting_data['key']}' setting to database")
                print(f"   Value: {setting_data['value']}")
                print(f"   Type: {setting_data['value_type']}")
                print(f"   Category: {setting_data['category']}")
                print(f"   Description: {setting_data['description']}")

    except Exception as e:
        print(f"❌ Error adding setting to database: {str(e)}")
        raise


if __name__ == "__main__":
    print("🚀 Adding use_database_config setting to database...\n")
    add_use_database_config_setting()
    print("\n✅ Done!")
