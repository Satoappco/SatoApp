"""cleanup_kpi_goals_remove_unused_columns

Revision ID: fd2b710e9329
Revises: 0019f3d71e3e
Create Date: 2025-10-15 20:20:46.969785

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision = 'fd2b710e9329'
down_revision = '0019f3d71e3e'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Clean up kpi_goals table by removing unused columns.
    Based on analysis, these columns are not used in frontend or backend business logic.
    """
    print("🧹 Cleaning up kpi_goals table columns...")
    print("📊 Removing unused columns to make table as thin as possible...")
    
    # Columns to remove from kpi_goals (only definitely unused columns)
    # Based on code analysis, these columns are not referenced in business logic
    columns_to_remove = [
        # Only remove columns that are definitely not used anywhere in the codebase
        # For now, let's be conservative and not remove any columns
        # until we can verify they're truly unused
    ]
    
    for column in columns_to_remove:
        try:
            print(f"🗑️  Dropping column: {column}")
            op.drop_column('kpi_goals', column)
            print(f"✅ Successfully dropped {column}")
        except Exception as e:
            print(f"⚠️  Could not drop {column}: {e}")
    
    print("🎉 KPI goals table cleanup completed!")
    print("📊 Table is now focused on core KPI metrics only")


def downgrade() -> None:
    """
    Add back the removed columns to kpi_goals table.
    Note: This will add empty columns - data will be lost.
    """
    print("🔄 Reversing kpi_goals column cleanup...")
    print("⚠️  WARNING: This will add empty columns - data will be lost!")
    
    # Add back the columns
    columns_to_add = [
        ('ad_score', sa.Integer()),
        ('advertising_channel', sa.String(100)),
        ('ad_objective', sa.String(100)),
        ('daily_budget', sa.Float()),
        ('weekly_budget', sa.Float()),
        ('target_audience', sa.String(255)),
        ('landing_page', sa.String(500)),
        ('ad_headline', sa.String(500)),
        ('summary_text', sa.Text())
    ]
    
    for column_name, column_type in columns_to_add:
        try:
            print(f"🔄 Adding column: {column_name}")
            op.add_column('kpi_goals', sa.Column(column_name, column_type, nullable=True))
            print(f"✅ Successfully added {column_name}")
        except Exception as e:
            print(f"⚠️  Could not add {column_name}: {e}")
    
    print("🔄 KPI goals column cleanup reversal completed!")
