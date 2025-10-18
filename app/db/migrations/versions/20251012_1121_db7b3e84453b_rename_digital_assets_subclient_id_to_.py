"""rename_digital_assets_subclient_id_to_customer_id

Revision ID: db7b3e84453b
Revises: aefbd6e3a627
Create Date: 2025-10-12 11:21:12.816411

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision = 'db7b3e84453b'
down_revision = 'aefbd6e3a627'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Rename subclient_id to customer_id in digital_assets table
    op.alter_column('digital_assets', 'subclient_id', new_column_name='customer_id')


def downgrade() -> None:
    # Revert: rename customer_id back to subclient_id in digital_assets table
    op.alter_column('digital_assets', 'customer_id', new_column_name='subclient_id')
