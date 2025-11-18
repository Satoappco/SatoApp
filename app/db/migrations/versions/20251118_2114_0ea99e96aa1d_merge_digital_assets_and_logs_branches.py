"""merge_digital_assets_and_logs_branches

Revision ID: 0ea99e96aa1d
Revises: asset001_2025, f3e9abe63d49
Create Date: 2025-11-18 21:14:50.363553

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision = '0ea99e96aa1d'
down_revision = ('asset001_2025', 'f3e9abe63d49')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
