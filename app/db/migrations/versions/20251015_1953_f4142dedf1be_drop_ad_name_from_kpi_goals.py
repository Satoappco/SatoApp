"""drop_ad_name_from_kpi_goals

Revision ID: f4142dedf1be
Revises: 2d045e0be9fc
Create Date: 2025-10-15 19:53:22.920669

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision = 'f4142dedf1be'
down_revision = '2d045e0be9fc'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Drop the ad_name column from kpi_goals table.
    This column is not being used in the frontend and appears to be unused.
    """
    print("Dropping ad_name column from kpi_goals table...")
    op.drop_column('kpi_goals', 'ad_name')
    print("✅ Successfully dropped ad_name column from kpi_goals table")


def downgrade() -> None:
    """
    Add back the ad_name column to kpi_goals table.
    """
    print("Adding ad_name column back to kpi_goals table...")
    op.add_column('kpi_goals', sa.Column('ad_name', sa.String(255), nullable=True))
    print("✅ Successfully added ad_name column back to kpi_goals table")
