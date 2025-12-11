#!/usr/bin/env python3
"""
Test that changing database settings actually affects the application runtime.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config.settings_loader import get_setting_value_simple
from app.config.database import get_session
from app.models.settings import AppSettings
from sqlmodel import select


def test_dynamic_change():
    """Test that changing DB value is reflected immediately."""

    print("=" * 60)
    print("DYNAMIC DATABASE SETTINGS TEST")
    print("=" * 60)

    # Get initial value
    print("\n1. Initial value:")
    initial_value = get_setting_value_simple("use_database_config")
    print(f"   use_database_config = {initial_value}")

    # Change the value in database
    print("\n2. Changing value in database to opposite...")
    new_value = "false" if initial_value else "true"

    with get_session() as session:
        setting = session.exec(
            select(AppSettings).where(AppSettings.key == "use_database_config")
        ).first()

        if setting:
            old_value = setting.value
            setting.value = new_value
            session.add(setting)
            session.commit()
            print(f"   Changed from '{old_value}' to '{new_value}'")
        else:
            print("   ❌ Setting not found in database!")
            return

    # Read again to verify change
    print("\n3. Reading value again (should reflect database change):")
    updated_value = get_setting_value_simple("use_database_config")
    print(f"   use_database_config = {updated_value}")

    # Restore original value
    print(f"\n4. Restoring original value ('{initial_value}')...")
    with get_session() as session:
        setting = session.exec(
            select(AppSettings).where(AppSettings.key == "use_database_config")
        ).first()

        if setting:
            setting.value = "true" if initial_value else "false"
            session.add(setting)
            session.commit()
            print(f"   ✅ Restored to original value")

    # Verify restoration
    final_value = get_setting_value_simple("use_database_config")
    print(f"\n5. Final verification:")
    print(f"   use_database_config = {final_value}")

    if final_value == initial_value:
        print(f"   ✅ Successfully restored to initial value!")
    else:
        print(f"   ⚠️  Value mismatch!")

    print("\n" + "=" * 60)
    if updated_value != initial_value and final_value == initial_value:
        print("✅ TEST PASSED: Database changes are reflected in real-time!")
    else:
        print("❌ TEST FAILED: Database changes not reflected properly")
    print("=" * 60)


if __name__ == "__main__":
    test_dynamic_change()
