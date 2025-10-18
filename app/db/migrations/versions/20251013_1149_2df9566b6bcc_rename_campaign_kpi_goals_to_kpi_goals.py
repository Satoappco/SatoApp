"""rename_campaign_kpi_goals_to_kpi_goals

Revision ID: 2df9566b6bcc
Revises: 328bdecd1ae8
Create Date: 2025-10-13 11:49:33.114043

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision = '2df9566b6bcc'
down_revision = '328bdecd1ae8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Rename campaign_kpi_goals to kpi_goals"""
    print("🔄 Renaming campaign_kpi_goals to kpi_goals...")
    op.rename_table('campaign_kpi_goals', 'kpi_goals')
    print("✅ Successfully renamed campaign_kpi_goals to kpi_goals!")


def downgrade() -> None:
    """Rename kpi_goals back to campaign_kpi_goals"""
    print("🔄 Renaming kpi_goals back to campaign_kpi_goals...")
    op.rename_table('kpi_goals', 'campaign_kpi_goals')
    print("✅ Successfully renamed kpi_goals back to campaign_kpi_goals!")
