"""add_google_auth_fields_to_campaigners

Revision ID: d9c03005c3e5
Revises: 2871fa2eef9c
Create Date: 2025-10-16 10:04:59.776185

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision = 'd9c03005c3e5'
down_revision = '2871fa2eef9c'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Add essential Google authentication fields to campaigners table.
    These fields are needed for proper Google OAuth functionality.
    """
    print("🔑 Adding Google authentication fields to campaigners table...")
    
    # Add email_verified field (nullable first, then update, then make not null)
    op.add_column('campaigners', sa.Column('email_verified', sa.Boolean(), nullable=True))
    op.execute("UPDATE campaigners SET email_verified = false WHERE email_verified IS NULL")
    op.alter_column('campaigners', 'email_verified', nullable=False)
    
    # Add locale field (nullable first, then update, then make not null)
    op.add_column('campaigners', sa.Column('locale', sa.String(10), nullable=True))
    op.execute("UPDATE campaigners SET locale = 'he-IL' WHERE locale IS NULL")
    op.alter_column('campaigners', 'locale', nullable=False)
    
    # Add timezone field (nullable first, then update, then make not null)
    op.add_column('campaigners', sa.Column('timezone', sa.String(50), nullable=True))
    op.execute("UPDATE campaigners SET timezone = 'Asia/Jerusalem' WHERE timezone IS NULL")
    op.alter_column('campaigners', 'timezone', nullable=False)
    
    # Add last_login_at field (nullable is fine)
    op.add_column('campaigners', sa.Column('last_login_at', sa.DateTime(), nullable=True))
    
    print("✅ Successfully added Google authentication fields to campaigners table")


def downgrade() -> None:
    """
    Remove Google authentication fields from campaigners table.
    """
    print("🔄 Removing Google authentication fields from campaigners table...")
    
    op.drop_column('campaigners', 'last_login_at')
    op.drop_column('campaigners', 'timezone')
    op.drop_column('campaigners', 'locale')
    op.drop_column('campaigners', 'email_verified')
    
    print("🔄 Successfully removed Google authentication fields from campaigners table")
