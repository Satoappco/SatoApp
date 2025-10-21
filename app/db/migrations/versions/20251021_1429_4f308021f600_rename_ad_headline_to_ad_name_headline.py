"""rename_ad_headline_to_ad_name_headline

Revision ID: 4f308021f600
Revises: 51c9b8e46a56
Create Date: 2025-10-21 14:29:16.816647

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision = '4f308021f600'
down_revision = '51c9b8e46a56'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Rename ad_headline column to ad_name_headline in kpi_goals table
    op.alter_column('kpi_goals', 'ad_headline', new_column_name='ad_name_headline')


def downgrade() -> None:
    # Rename ad_name_headline column back to ad_headline in kpi_goals table
    op.alter_column('kpi_goals', 'ad_name_headline', new_column_name='ad_headline')
