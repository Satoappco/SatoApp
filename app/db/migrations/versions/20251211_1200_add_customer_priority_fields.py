"""Add priority fields to customers table

Revision ID: 20251211_priority_fields
Revises: 20251208_failure_tracking
Create Date: 2025-12-11

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20251211_priority_fields'
down_revision = '20251208_failure_tracking'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add priority calculation fields to customers table."""
    # Add importance column (1-5, default 3)
    op.add_column(
        'customers',
        sa.Column('importance', sa.Integer(), nullable=False, server_default='3')
    )

    # Add budget column (default 0.0)
    op.add_column(
        'customers',
        sa.Column('budget', sa.Float(), nullable=False, server_default='0.0')
    )

    # Add campaign_health column (1-5, default 3)
    op.add_column(
        'customers',
        sa.Column('campaign_health', sa.Integer(), nullable=False, server_default='3')
    )

    # Add last_work_date column (nullable datetime)
    op.add_column(
        'customers',
        sa.Column('last_work_date', sa.DateTime(), nullable=True)
    )

    print("✅ Added priority fields (importance, budget, campaign_health, last_work_date) to customers table")


def downgrade() -> None:
    """Remove priority calculation fields from customers table."""
    # Remove columns in reverse order
    op.drop_column('customers', 'last_work_date')
    op.drop_column('customers', 'campaign_health')
    op.drop_column('customers', 'budget')
    op.drop_column('customers', 'importance')

    print("✅ Removed priority fields from customers table")
