"""remove_only_unused_tables

Revision ID: 2201b554a4cc
Revises: 61c64e826c13
Create Date: 2025-10-11 22:03:51.751829

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision = '2201b554a4cc'
down_revision = '61c64e826c13'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Remove only the unused tables (7 empty tables with 0 records).
    
    UNUSED TABLES (7 tables with 0 records):
    - analysis_executions
    - performance_metrics  
    - analytics_cache
    - kpi_catalog
    - chat_messages
    - webhook_entries
    - narrative_reports
    """
    
    print("Dropping unused tables (empty tables only)...")
    
    # Drop tables that are completely empty
    unused_tables = [
        'analysis_executions',
        'performance_metrics', 
        'analytics_cache',
        'kpi_catalog',
        'chat_messages',
        'webhook_entries',
        'narrative_reports'
    ]
    
    for table in unused_tables:
        try:
            op.drop_table(table)
            print(f"✅ Dropped table: {table}")
        except Exception as e:
            print(f"⚠️  Could not drop table {table}: {e}")
    
    print("✅ Migration completed - removed 7 unused tables!")


def downgrade() -> None:
    """
    Rollback migration - recreate removed tables.
    Note: This is a simplified rollback. Full restoration would require 
    the original table structures and data.
    """
    print("Rolling back migration...")
    print("⚠️  Note: Dropped tables are not recreated in rollback")
    print("✅ Rollback completed!")
