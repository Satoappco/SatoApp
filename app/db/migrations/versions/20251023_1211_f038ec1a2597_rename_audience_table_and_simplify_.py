"""rename_audience_table_and_simplify_schema

Revision ID: f038ec1a2597
Revises: 6de77b28dff6
Create Date: 2025-10-23 12:11:44.392830

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision = 'f038ec1a2597'
down_revision = '6de77b28dff6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Rename table from audience_table to audience
    op.rename_table('audience_table', 'audience')
    
    # Drop description column
    op.drop_column('audience', 'description')
    
    # Drop is_active column
    op.drop_column('audience', 'is_active')


def downgrade() -> None:
    # Add back is_active column
    op.add_column('audience', sa.Column('is_active', sa.Boolean(), nullable=False, default=True))
    
    # Add back description column
    op.add_column('audience', sa.Column('description', sa.String(), nullable=True))
    
    # Rename table back to audience_table
    op.rename_table('audience', 'audience_table')
