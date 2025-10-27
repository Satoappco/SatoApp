"""add_agency_and_campaigner_name_to_customers

Revision ID: 20250124_1200_add_agency_and_campaigner_name
Revises: 4649b62cd83f
Create Date: 2025-01-24 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision = '4a7747777f49'
down_revision = '4649b62cd83f'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Add agency_name and campaigner_name denormalized columns to customers table.
    These fields store duplicated data from agencies and campaigners tables for fast read access.
    """
    print("🔗 Adding agency_name and campaigner_name to customers table...")
    
    # Add new columns as nullable first
    op.add_column('customers', sa.Column('agency_name', sa.String(length=255), nullable=True))
    op.add_column('customers', sa.Column('campaigner_name', sa.String(length=255), nullable=True))
    
    # Backfill existing data by joining with agencies and campaigners tables
    print("📊 Backfilling agency_name from agencies table...")
    op.execute("""
        UPDATE customers 
        SET agency_name = (
            SELECT name FROM agencies WHERE agencies.id = customers.agency_id
        )
    """)
    
    print("📊 Backfilling campaigner_name from campaigners table...")
    op.execute("""
        UPDATE customers 
        SET campaigner_name = (
            SELECT full_name FROM campaigners WHERE campaigners.id = customers.assigned_campaigner_id
        )
        WHERE assigned_campaigner_id IS NOT NULL
    """)
    
    print("✅ Successfully added agency_name and campaigner_name to customers table")


def downgrade() -> None:
    """
    Remove agency_name and campaigner_name columns from customers table.
    """
    print("🔄 Removing agency_name and campaigner_name from customers table...")
    op.drop_column('customers', 'campaigner_name')
    op.drop_column('customers', 'agency_name')
    print("🔄 Successfully removed agency_name and campaigner_name from customers table")
