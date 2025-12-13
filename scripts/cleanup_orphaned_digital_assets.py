#!/usr/bin/env python3
"""
Script to clean up orphaned digital assets.
Orphaned assets are active digital assets that have no associated connections.
This can happen when digital asset creation succeeds but connection creation fails.

This script will:
1. Find all active digital assets without any connections
2. Deactivate them (set is_active = False)
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.config.database import get_session
from app.models.analytics import DigitalAsset, Connection
from sqlmodel import select


def cleanup_orphaned_assets(dry_run=True):
    """
    Deactivate orphaned digital assets.

    Args:
        dry_run: If True, only report what would be done without making changes
    """

    with get_session() as session:
        # Find active assets without any connections
        # Using a NOT EXISTS subquery
        orphaned_assets = session.exec(
            select(DigitalAsset).where(
                DigitalAsset.is_active == True,
                ~DigitalAsset.id.in_(
                    select(Connection.digital_asset_id).distinct()
                )
            ).order_by(DigitalAsset.created_at.desc())
        ).all()

        if not orphaned_assets:
            print("✅ No orphaned digital assets found!")
            return 0

        print(f"🔍 Found {len(orphaned_assets)} orphaned digital assets:\n")

        for asset in orphaned_assets:
            print(f"   Asset {asset.id}: {asset.asset_type.value} - {asset.name}")
            print(f"      Customer: {asset.customer_id}")
            print(f"      External ID: {asset.external_id}")
            print(f"      Created: {asset.created_at}")
            print()

        if dry_run:
            print("=" * 80)
            print("DRY RUN MODE - No changes made")
            print(f"Would deactivate {len(orphaned_assets)} orphaned assets")
            print("Run with --execute to actually deactivate these assets")
            print("=" * 80)
            return len(orphaned_assets)

        # Actually deactivate the assets
        print("=" * 80)
        print(f"Deactivating {len(orphaned_assets)} orphaned assets...")
        print("=" * 80)

        for asset in orphaned_assets:
            asset.is_active = False
            session.add(asset)
            print(f"✅ Deactivated asset {asset.id}: {asset.name}")

        session.commit()
        print(f"\n✅ Successfully deactivated {len(orphaned_assets)} orphaned assets")

        return len(orphaned_assets)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Clean up orphaned digital assets")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually deactivate orphaned assets (default is dry-run mode)"
    )

    args = parser.parse_args()

    print("=" * 80)
    print("ORPHANED DIGITAL ASSETS CLEANUP")
    print("=" * 80)
    print()

    if not args.execute:
        print("⚠️  Running in DRY RUN mode - no changes will be made")
        print()

    count = cleanup_orphaned_assets(dry_run=not args.execute)

    print()
    print("=" * 80)
    print("CLEANUP COMPLETE")
    print("=" * 80)
