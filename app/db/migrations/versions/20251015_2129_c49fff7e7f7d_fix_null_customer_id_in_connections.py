"""fix_null_customer_id_in_connections

Revision ID: c49fff7e7f7d
Revises: 0bd2156f83dd
Create Date: 2025-10-15 21:29:17.481463

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision = 'c49fff7e7f7d'
down_revision = '0bd2156f83dd'
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
