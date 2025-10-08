"""remove_unused_tables

Revision ID: 9d479ea0f321
Revises: 9213373eb0b4
Create Date: 2025-10-05 15:32:21.056250

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision = '9d479ea0f321'
down_revision = '9213373eb0b4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop unused tables that have no CSV files and no active usage
    op.drop_table('analytics_cache')
    op.drop_table('user_property_selections')
    op.drop_table('user_sessions')
    op.drop_table('chat_messages')
    op.drop_table('webhook_entries')


def downgrade() -> None:
    # Recreate the tables if needed (for rollback)
    # Note: This is a simplified recreation - actual table structures would need to be restored
    pass
