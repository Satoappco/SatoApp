#!/usr/bin/env python3
"""
Script to find and report duplicate digital assets in the database.
Digital assets should be unique per (customer_id, external_id, asset_type).
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.config.database import get_session
from app.models.analytics import DigitalPlatform, Connection
from sqlmodel import select, func
from sqlalchemy import and_


def find_duplicates():
    """Find all duplicate digital assets grouped by (customer_id, external_id, asset_type)"""

    with get_session() as session:
        # Find groups that have more than one asset
        query = select(
            DigitalPlatform.customer_id,
            DigitalPlatform.external_id,
            DigitalPlatform.asset_type,
            func.count(DigitalPlatform.id).label('count')
        ).group_by(
            DigitalPlatform.customer_id,
            DigitalPlatform.external_id,
            DigitalPlatform.asset_type
        ).having(
            func.count(DigitalPlatform.id) > 1
        )

        duplicate_groups = session.exec(query).all()

        if not duplicate_groups:
            print("✅ No duplicate digital assets found!")
            return []

        print(f"🔍 Found {len(duplicate_groups)} groups with duplicates:\n")

        all_duplicates = []

        for customer_id, external_id, asset_type, count in duplicate_groups:
            print(f"📦 Customer {customer_id}, {asset_type}, External ID: {external_id} ({count} duplicates)")

            # Get all assets in this group
            assets = session.exec(
                select(DigitalPlatform).where(
                    and_(
                        DigitalPlatform.customer_id == customer_id,
                        DigitalPlatform.external_id == external_id,
                        DigitalPlatform.asset_type == asset_type
                    )
                ).order_by(DigitalPlatform.created_at)
            ).all()

            for asset in assets:
                # Check if this asset has connections
                connection_count = session.exec(
                    select(func.count(Connection.id)).where(
                        Connection.digital_platform_id == asset.id
                    )
                ).first()

                status = "✅ HAS CONNECTION" if connection_count > 0 else "❌ NO CONNECTION"
                active_status = "🟢 ACTIVE" if asset.is_active else "🔴 INACTIVE"

                print(f"   - Asset {asset.id}: {asset.name} | {status} ({connection_count} connections) | {active_status} | Created: {asset.created_at}")

            all_duplicates.append({
                'customer_id': customer_id,
                'external_id': external_id,
                'asset_type': asset_type,
                'assets': assets
            })
            print()

        return all_duplicates


if __name__ == "__main__":
    print("=" * 80)
    print("DUPLICATE DIGITAL ASSETS REPORT")
    print("=" * 80)
    print()

    duplicates = find_duplicates()

    if duplicates:
        print("=" * 80)
        print(f"SUMMARY: Found {len(duplicates)} groups with duplicate digital assets")
        print("=" * 80)
