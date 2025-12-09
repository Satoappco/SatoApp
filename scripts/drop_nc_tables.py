#!/usr/bin/env python3
"""
Script to drop all tables starting with 'nc_' from the database.

This is typically used to clean up NocoDB or other third-party tables.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config.database import get_engine
from sqlalchemy import text


def find_nc_tables():
    """Find all tables starting with nc_."""
    engine = get_engine()

    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT tablename
            FROM pg_tables
            WHERE schemaname = 'public'
            AND tablename LIKE 'nc_%'
            ORDER BY tablename;
        """))

        tables = [row[0] for row in result]

    return tables


def drop_nc_tables(confirm=True):
    """
    Drop all tables starting with nc_.

    Args:
        confirm: If True, ask for confirmation before dropping
    """
    tables = find_nc_tables()

    if not tables:
        print("✅ No tables found starting with 'nc_'")
        return

    print(f"Found {len(tables)} tables starting with 'nc_':")
    for i, table in enumerate(tables, 1):
        print(f"  {i}. {table}")

    if confirm:
        print("\n⚠️  WARNING: This will permanently delete these tables!")
        response = input("Are you sure you want to drop these tables? (yes/no): ")
        if response.lower() not in ['yes', 'y']:
            print("Cancelled.")
            return

    engine = get_engine()
    dropped = []
    errors = []

    print(f"\nDropping {len(tables)} tables...")

    with engine.connect() as conn:
        # Start transaction
        trans = conn.begin()

        try:
            for table in tables:
                try:
                    # Use CASCADE to drop dependent objects
                    conn.execute(text(f'DROP TABLE IF EXISTS "{table}" CASCADE'))
                    dropped.append(table)
                    print(f"  ✅ Dropped: {table}")
                except Exception as e:
                    errors.append((table, str(e)))
                    print(f"  ❌ Error dropping {table}: {e}")

            # Commit transaction
            trans.commit()
            print(f"\n✅ Successfully dropped {len(dropped)} tables")

            if errors:
                print(f"\n❌ Failed to drop {len(errors)} tables:")
                for table, error in errors:
                    print(f"  - {table}: {error}")

        except Exception as e:
            trans.rollback()
            print(f"\n❌ Transaction failed, rolled back: {e}")
            raise


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Drop all tables starting with 'nc_'")
    parser.add_argument(
        "--yes", "-y",
        action="store_true",
        help="Skip confirmation prompt"
    )

    args = parser.parse_args()

    try:
        drop_nc_tables(confirm=not args.yes)
    except KeyboardInterrupt:
        print("\n\nCancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
