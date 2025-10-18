"""rename_primary_agency_id_to_agency_id_and_remove_additional_agency_ids

Revision ID: 185377f6c1fd
Revises: 2df9566b6bcc
Create Date: 2025-10-15 09:51:34.460547

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision = '185377f6c1fd'
down_revision = '2df9566b6bcc'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Rename primary_agency_id to agency_id and remove additional_agency_ids column
    from campaigners table to simplify the agency relationship.
    """
    print("🔄 Renaming primary_agency_id to agency_id and removing additional_agency_ids...")
    
    # Rename primary_agency_id to agency_id in campaigners table
    try:
        op.alter_column('campaigners', 'primary_agency_id', new_column_name='agency_id')
        print("✅ Renamed primary_agency_id to agency_id in campaigners table")
    except Exception as e:
        print(f"⚠️  Could not rename primary_agency_id: {e}")
    
    # Remove additional_agency_ids column from campaigners table
    try:
        op.drop_column('campaigners', 'additional_agency_ids')
        print("✅ Removed additional_agency_ids column from campaigners table")
    except Exception as e:
        print(f"⚠️  Could not remove additional_agency_ids: {e}")
    
    print("✅ Campaigners table structure updated successfully!")


def downgrade() -> None:
    """
    Revert the changes: rename agency_id back to primary_agency_id and add back additional_agency_ids
    """
    print("🔄 Reverting agency column changes...")
    
    # Add back additional_agency_ids column
    try:
        op.add_column('campaigners', sa.Column('additional_agency_ids', sa.JSON(), nullable=True))
        print("✅ Added back additional_agency_ids column to campaigners table")
    except Exception as e:
        print(f"⚠️  Could not add back additional_agency_ids: {e}")
    
    # Rename agency_id back to primary_agency_id
    try:
        op.alter_column('campaigners', 'agency_id', new_column_name='primary_agency_id')
        print("✅ Renamed agency_id back to primary_agency_id in campaigners table")
    except Exception as e:
        print(f"⚠️  Could not rename agency_id back: {e}")
    
    print("✅ Reverted campaigners table structure successfully!")
