"""add_facebook_ads_asset_type

Revision ID: 9213373eb0b4
Revises: 38af7d1d67c4
Create Date: 2025-10-01 08:18:44.963258

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision = '9213373eb0b4'
down_revision = '38af7d1d67c4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new enum value for Facebook Ads
    # PostgreSQL requires ALTER TYPE ... ADD VALUE for adding enum values
    op.execute("ALTER TYPE assettype ADD VALUE IF NOT EXISTS 'facebook_ads'")


def downgrade() -> None:
    # Note: PostgreSQL does not support removing enum values directly
    # If you need to downgrade, you would need to:
    # 1. Create a new enum type without the value
    # 2. Alter the column to use the new type
    # 3. Drop the old type
    # This is complex and risky, so we leave it as a no-op
    # Make sure no data uses 'facebook_ads' before attempting to downgrade
    pass
