"""Add failure tracking fields to connections table

Revision ID: 20251208_failure_tracking
Revises: 20251127_oauth_validation
Create Date: 2025-12-08

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20251208_failure_tracking'
down_revision = '20251127_oauth_validation'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add failure tracking fields to connections table."""
    # Add last_failure_at column
    op.add_column(
        'connections',
        sa.Column('last_failure_at', sa.DateTime(), nullable=True)
    )

    # Add failure_count column
    op.add_column(
        'connections',
        sa.Column('failure_count', sa.Integer(), nullable=False, server_default='0')
    )

    # Add failure_reason column
    op.add_column(
        'connections',
        sa.Column('failure_reason', sa.String(length=255), nullable=True)
    )

    print("✅ Added failure tracking fields (last_failure_at, failure_count, failure_reason) to connections table")


def downgrade() -> None:
    """Remove failure tracking fields from connections table."""
    # Remove columns
    op.drop_column('connections', 'failure_reason')
    op.drop_column('connections', 'failure_count')
    op.drop_column('connections', 'last_failure_at')

    print("✅ Removed failure tracking fields from connections table")
