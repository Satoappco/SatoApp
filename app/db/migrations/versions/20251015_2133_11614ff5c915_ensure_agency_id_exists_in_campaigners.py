"""ensure_agency_id_exists_in_campaigners

Revision ID: 11614ff5c915
Revises: c49fff7e7f7d
Create Date: 2025-10-15 21:33:XX.XXXXXX

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = '11614ff5c915'
down_revision = 'c49fff7e7f7d'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Ensure agency_id column exists in campaigners table.
    This fixes an issue where the column might be missing or named incorrectly.
    """
    print("🔍 Checking campaigners table for agency_id column...")
    
    # Get connection
    conn = op.get_bind()
    inspector = inspect(conn)
    
    # Get existing columns
    columns = [col['name'] for col in inspector.get_columns('campaigners')]
    print(f"📊 Found columns in campaigners: {columns}")
    
    # Check if agency_id exists
    if 'agency_id' in columns:
        print("✅ agency_id column already exists")
        return
    
    # Check if primary_agency_id exists (old name)
    if 'primary_agency_id' in columns:
        print("🔄 Found primary_agency_id, renaming to agency_id...")
        try:
            op.alter_column('campaigners', 'primary_agency_id', new_column_name='agency_id')
            print("✅ Successfully renamed primary_agency_id to agency_id")
            return
        except Exception as e:
            print(f"⚠️  Could not rename column: {e}")
    
    # If neither exists, create agency_id from scratch
    print("➕ Creating agency_id column...")
    try:
        op.add_column('campaigners', sa.Column('agency_id', sa.Integer(), nullable=True))
        print("✅ Successfully added agency_id column")
        
        # Add foreign key constraint
        try:
            op.create_foreign_key(
                'fk_campaigners_agency_id',
                'campaigners', 'agencies',
                ['agency_id'], ['id']
            )
            print("✅ Successfully added foreign key constraint")
        except Exception as e:
            print(f"⚠️  Could not add foreign key: {e}")
            
    except Exception as e:
        print(f"❌ Could not create agency_id column: {e}")


def downgrade() -> None:
    """
    This migration should not be reversed as it fixes a critical issue.
    """
    print("⚠️  This migration cannot be reversed - it fixes a critical database issue")
    pass
