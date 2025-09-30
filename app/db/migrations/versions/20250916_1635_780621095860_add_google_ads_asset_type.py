"""add_google_ads_asset_type

Revision ID: 780621095860
Revises: 27a6d9f5378f
Create Date: 2025-09-16 16:35:09.740735

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision = '780621095860'
down_revision = '27a6d9f5378f'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add GOOGLE_ADS to the assettype enum
    op.execute("ALTER TYPE assettype ADD VALUE 'GOOGLE_ADS'")


def downgrade() -> None:
    # Note: PostgreSQL doesn't support removing enum values directly
    # This would require recreating the enum type and updating all references
    # For now, we'll leave the enum value in place
    pass
