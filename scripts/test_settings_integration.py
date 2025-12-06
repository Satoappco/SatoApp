#!/usr/bin/env python3
"""
Test script to verify settings integration between environment and database.
"""

import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config.settings import get_settings
from app.config.settings_loader import get_setting_value_simple
from app.config.database import get_session
from app.models.settings import AppSettings
from sqlmodel import select


def test_settings_integration():
    """Test that database settings override environment settings."""

    print("=" * 60)
    print("SETTINGS INTEGRATION TEST")
    print("=" * 60)

    # Test 1: Environment setting
    print("\n1. Testing environment-only settings:")
    print("-" * 60)
    env_settings = get_settings()
    print(f"   app_name (env): {env_settings.app_name}")
    print(f"   debug (env): {env_settings.debug}")

    # Test 2: Database setting
    print("\n2. Testing database setting (use_database_config):")
    print("-" * 60)

    with get_session() as session:
        db_setting = session.exec(
            select(AppSettings).where(AppSettings.key == "use_database_config")
        ).first()

        if db_setting:
            print(f"   ✅ Database value: {db_setting.value}")
            print(f"   ✅ Database type: {db_setting.value_type}")
        else:
            print(f"   ❌ Not found in database")

    # Test 3: Unified setting (should use database value)
    print("\n3. Testing unified settings loader:")
    print("-" * 60)
    env_value = env_settings.use_database_config if hasattr(env_settings, 'use_database_config') else "NOT SET"
    unified_value = get_setting_value_simple("use_database_config", False)

    print(f"   Environment value: {env_value}")
    print(f"   Unified value (DB override): {unified_value}")

    if unified_value != env_value:
        print(f"   ✅ Database successfully overrides environment!")
    else:
        print(f"   ℹ️  Values are the same (database and env match)")

    # Test 4: Setting that only exists in env
    print("\n4. Testing fallback to environment:")
    print("-" * 60)
    app_name = get_setting_value_simple("app_name", "default")
    print(f"   app_name (should fall back to env): {app_name}")

    # Test 5: Non-existent setting with default
    print("\n5. Testing default value:")
    print("-" * 60)
    non_existent = get_setting_value_simple("non_existent_setting", "DEFAULT_VALUE")
    print(f"   non_existent_setting: {non_existent}")

    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    test_settings_integration()
