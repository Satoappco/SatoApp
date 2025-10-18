"""add_is_active_to_customers_table

Revision ID: fa85c21c1802
Revises: 1202f505453d
Create Date: 2025-10-13 11:09:49.063040

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision = 'fa85c21c1802'
down_revision = '1202f505453d'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add is_active column to customers table"""
    print("🔄 Adding is_active column to customers table...")
    
    # Add is_active column with default value True
    op.add_column('customers', sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'))
    
    print("✅ Successfully added is_active column to customers table")


def downgrade() -> None:
    """Remove is_active column from customers table"""
    print("🔄 Removing is_active column from customers table...")
    
    op.drop_column('customers', 'is_active')
    
    print("✅ Successfully removed is_active column from customers table")
