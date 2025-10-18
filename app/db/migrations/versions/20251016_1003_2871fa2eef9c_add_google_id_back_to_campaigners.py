"""add_google_id_back_to_campaigners

Revision ID: 2871fa2eef9c
Revises: 11614ff5c915
Create Date: 2025-10-16 10:03:31.934601

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision = '2871fa2eef9c'
down_revision = '11614ff5c915'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Add google_id column back to campaigners table.
    This is essential for proper Google OAuth authentication.
    """
    print("🔑 Adding google_id column back to campaigners table...")
    op.add_column('campaigners', sa.Column('google_id', sa.String(255), nullable=True))
    op.create_index('ix_campaigners_google_id', 'campaigners', ['google_id'], unique=True)
    print("✅ Successfully added google_id column to campaigners table")


def downgrade() -> None:
    """
    Remove google_id column from campaigners table.
    """
    print("🔄 Removing google_id column from campaigners table...")
    op.drop_index('ix_campaigners_google_id', 'campaigners')
    op.drop_column('campaigners', 'google_id')
    print("🔄 Successfully removed google_id column from campaigners table")
