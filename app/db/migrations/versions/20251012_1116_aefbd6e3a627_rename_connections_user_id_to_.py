"""rename_connections_user_id_to_campaigner_id

Revision ID: aefbd6e3a627
Revises: cfad109237bd
Create Date: 2025-10-12 11:16:37.661787

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision = 'aefbd6e3a627'
down_revision = 'cfad109237bd'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Rename user_id to campaigner_id in connections table
    op.alter_column('connections', 'user_id', new_column_name='campaigner_id')


def downgrade() -> None:
    # Revert: rename campaigner_id back to user_id in connections table
    op.alter_column('connections', 'campaigner_id', new_column_name='user_id')
