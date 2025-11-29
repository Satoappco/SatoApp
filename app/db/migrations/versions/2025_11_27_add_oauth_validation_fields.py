"""Add needs_reauth and last_validated_at to connections table

Revision ID: 20251127_oauth_validation
Revises:
Create Date: 2025-11-27

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20251127_oauth_validation'
down_revision = '2e18477ba827'  # Previous migration (add_metrics_table_for_campaign_sync)
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add OAuth token refresh and validation fields to connections table."""
    # Add needs_reauth column
    op.add_column(
        'connections',
        sa.Column('needs_reauth', sa.Boolean(), nullable=False, server_default='false')
    )

    # Add last_validated_at column
    op.add_column(
        'connections',
        sa.Column('last_validated_at', sa.DateTime(), nullable=True)
    )

    print("✅ Added needs_reauth and last_validated_at columns to connections table")


def downgrade() -> None:
    """Remove OAuth token refresh and validation fields from connections table."""
    # Remove columns
    op.drop_column('connections', 'last_validated_at')
    op.drop_column('connections', 'needs_reauth')

    print("✅ Removed needs_reauth and last_validated_at columns from connections table")
