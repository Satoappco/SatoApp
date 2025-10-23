"""add_customer_fields_to_kpi_settings

Revision ID: ccdc94026d58
Revises: f038ec1a2597
Create Date: 2025-10-23 12:56:19.383933

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel
from datetime import datetime


# revision identifiers, used by Alembic.
revision = 'ccdc94026d58'
down_revision = 'f038ec1a2597'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Add customer relationship fields to kpi_settings table.
    Migrate existing admin-only settings to customer-specific settings.
    """
    
    # Step 1: Add new columns (nullable initially)
    op.add_column('kpi_settings', sa.Column('composite_id', sa.String(length=100), nullable=True))
    op.add_column('kpi_settings', sa.Column('customer_id', sa.Integer(), nullable=True))
    
    # Step 2: Create index on composite_id
    op.create_index('ix_kpi_settings_composite_id', 'kpi_settings', ['composite_id'])
    
    # Step 3: Add foreign key constraint
    op.create_foreign_key('fk_kpi_settings_customer_id', 'kpi_settings', 'customers', ['customer_id'], ['id'])
    
    # Step 4: Get all existing customers and their agency/campaigner info
    connection = op.get_bind()
    
    # Fetch all customers with their agency and campaigner info
    customers_result = connection.execute(sa.text("""
        SELECT c.id as customer_id, c.agency_id, c.assigned_campaigner_id
        FROM customers c
        WHERE c.is_active = true
    """))
    
    customers = customers_result.fetchall()
    
    # Step 5: Get all existing KPI settings
    kpi_settings_result = connection.execute(sa.text("""
        SELECT id, campaign_objective, kpi_name, kpi_type, direction, default_value, unit, created_at, updated_at
        FROM kpi_settings
        WHERE composite_id IS NULL
    """))
    
    existing_settings = kpi_settings_result.fetchall()
    
    # Step 6: For each customer, duplicate all existing KPI settings
    for customer in customers:
        customer_id = customer.customer_id
        agency_id = customer.agency_id
        campaigner_id = customer.assigned_campaigner_id
        
        # Skip if no assigned campaigner
        if not campaigner_id:
            continue
            
        # Create composite_id for this customer
        composite_id = f"{agency_id}_{campaigner_id}_{customer_id}"
        
        for setting in existing_settings:
            # Insert new row for this customer
            connection.execute(sa.text("""
                INSERT INTO kpi_settings (
                    composite_id, customer_id, campaign_objective, kpi_name, kpi_type, 
                    direction, default_value, unit, created_at, updated_at
                ) VALUES (
                    :composite_id, :customer_id, :campaign_objective, :kpi_name, :kpi_type,
                    :direction, :default_value, :unit, :created_at, :updated_at
                )
            """), {
                'composite_id': composite_id,
                'customer_id': customer_id,
                'campaign_objective': setting.campaign_objective,
                'kpi_name': setting.kpi_name,
                'kpi_type': setting.kpi_type,
                'direction': setting.direction,
                'default_value': setting.default_value,
                'unit': setting.unit,
                'created_at': setting.created_at,
                'updated_at': setting.updated_at
            })
    
    # Step 7: Delete original admin-only rows
    connection.execute(sa.text("DELETE FROM kpi_settings WHERE composite_id IS NULL"))
    
    # Step 8: Make columns NOT NULL
    op.alter_column('kpi_settings', 'composite_id', nullable=False)
    op.alter_column('kpi_settings', 'customer_id', nullable=False)


def downgrade() -> None:
    """
    Revert customer-specific KPI settings back to admin-only.
    This will lose all customer customizations!
    """
    
    # Step 1: Remove foreign key constraint
    op.drop_constraint('fk_kpi_settings_customer_id', 'kpi_settings', type_='foreignkey')
    
    # Step 2: Drop index
    op.drop_index('ix_kpi_settings_composite_id', 'kpi_settings')
    
    # Step 3: Remove customer-specific columns
    op.drop_column('kpi_settings', 'customer_id')
    op.drop_column('kpi_settings', 'composite_id')