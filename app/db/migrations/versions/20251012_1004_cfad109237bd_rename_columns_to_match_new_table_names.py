"""rename_columns_to_match_new_table_names

Revision ID: cfad109237bd
Revises: eff2f4dfb2f7
Create Date: 2025-10-12 10:04:03.419960

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision = 'cfad109237bd'
down_revision = 'eff2f4dfb2f7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Rename columns to match the new table names and structure:
    - campaigners table: primary_customer_id -> primary_agency_id, additional_customer_ids -> additional_agency_ids
    - agencies table: primary_contact_user_id -> primary_contact_campaigner_id
    - customers table: customer_id -> agency_id
    - client_info table: subclient_id -> customer_id, customer_id -> agency_id, user_id -> campaigner_id
    - campaigner_sessions table: user_id -> campaigner_id
    """
    
    print("Renaming columns to match new table structure...")
    
    # Rename columns in campaigners table
    op.alter_column('campaigners', 'primary_customer_id', new_column_name='primary_agency_id')
    op.alter_column('campaigners', 'additional_customer_ids', new_column_name='additional_agency_ids')
    
    # Rename columns in agencies table
    op.alter_column('agencies', 'primary_contact_user_id', new_column_name='primary_contact_campaigner_id')
    
    # Rename columns in customers table
    op.alter_column('customers', 'customer_id', new_column_name='agency_id')
    
    # Rename columns in client_info table
    # First rename customer_id to agency_id, then rename subclient_id to customer_id
    op.alter_column('client_info', 'customer_id', new_column_name='agency_id')
    op.alter_column('client_info', 'subclient_id', new_column_name='customer_id')
    op.alter_column('client_info', 'user_id', new_column_name='campaigner_id')
    
    # Rename columns in campaigner_sessions table
    op.alter_column('campaigner_sessions', 'user_id', new_column_name='campaigner_id')
    
    print("✅ All columns renamed successfully!")


def downgrade() -> None:
    """
    Revert column names back to original names.
    """
    
    print("Reverting column names to original names...")
    
    # Revert columns in campaigners table
    op.alter_column('campaigners', 'primary_agency_id', new_column_name='primary_customer_id')
    op.alter_column('campaigners', 'additional_agency_ids', new_column_name='additional_customer_ids')
    
    # Revert columns in agencies table
    op.alter_column('agencies', 'primary_contact_campaigner_id', new_column_name='primary_contact_user_id')
    
    # Revert columns in customers table
    op.alter_column('customers', 'agency_id', new_column_name='customer_id')
    
    # Revert columns in client_info table
    # First revert customer_id to subclient_id, then revert agency_id to customer_id
    op.alter_column('client_info', 'customer_id', new_column_name='subclient_id')
    op.alter_column('client_info', 'agency_id', new_column_name='customer_id')
    op.alter_column('client_info', 'campaigner_id', new_column_name='user_id')
    
    # Revert columns in campaigner_sessions table
    op.alter_column('campaigner_sessions', 'campaigner_id', new_column_name='user_id')
    
    print("✅ All column names reverted successfully!")
