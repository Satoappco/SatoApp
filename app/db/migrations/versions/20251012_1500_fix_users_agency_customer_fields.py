"""Fix users table: rename primary_customer_id to primary_agency_id and add selected_customer_id

Revision ID: a1b2c3d4e5f6
Revises: 74fcd4854ea7
Create Date: 2025-10-12 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = 'dccfef3acf23'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Fix the users table structure:
    1. Rename primary_customer_id to primary_agency_id (the agency the campaigner works for)
    2. Add selected_customer_id (the last customer they worked on)
    """
    
    print("Fixing users table structure...")
    
    # Step 1: Rename primary_customer_id to primary_agency_id
    print("  - Renaming primary_customer_id to primary_agency_id...")
    op.alter_column('users', 'primary_customer_id', new_column_name='primary_agency_id')
    
    # Step 2: Add selected_customer_id column (nullable, for tracking last customer worked on)
    print("  - Adding selected_customer_id column...")
    op.add_column('users', sa.Column('selected_customer_id', sa.Integer(), nullable=True))
    
    # Step 3: Add foreign key constraint for selected_customer_id
    print("  - Adding foreign key constraint for selected_customer_id...")
    op.create_foreign_key(
        'users_selected_customer_id_fkey',
        'users',
        'customers',
        ['selected_customer_id'],
        ['id']
    )
    
    print("✅ Users table structure fixed successfully!")


def downgrade() -> None:
    """
    Rollback the changes
    """
    
    print("Rolling back users table changes...")
    
    # Remove foreign key constraint
    op.drop_constraint('users_selected_customer_id_fkey', 'users', type_='foreignkey')
    
    # Remove selected_customer_id column
    op.drop_column('users', 'selected_customer_id')
    
    # Rename back to primary_customer_id
    op.alter_column('users', 'primary_agency_id', new_column_name='primary_customer_id')
    
    print("✅ Rollback completed!")

