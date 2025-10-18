"""add_avatar_url_to_campaigners

Revision ID: 7e837187a740
Revises: d9c03005c3e5
Create Date: 2025-10-16 10:07:05.556546

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision = '7e837187a740'
down_revision = 'd9c03005c3e5'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Add avatar_url field to campaigners table.
    This stores the Google profile picture URL.
    """
    print("🖼️ Adding avatar_url field to campaigners table...")
    op.add_column('campaigners', sa.Column('avatar_url', sa.String(500), nullable=True))
    print("✅ Successfully added avatar_url field to campaigners table")


def downgrade() -> None:
    """
    Remove avatar_url field from campaigners table.
    """
    print("🔄 Removing avatar_url field from campaigners table...")
    op.drop_column('campaigners', 'avatar_url')
    print("🔄 Successfully removed avatar_url field from campaigners table")
