"""merge_heads

Revision ID: 7d31ba632789
Revises: b6e4e4f1aa8, update_default_kpi_settings_data
Create Date: 2025-10-23 17:28:27.392476

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision = '7d31ba632789'
down_revision = ('b6e4e4f1aa8', 'update_default_kpi_settings_data')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
