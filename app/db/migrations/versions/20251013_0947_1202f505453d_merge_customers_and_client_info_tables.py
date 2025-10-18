"""merge_customers_and_client_info_tables

Revision ID: 1202f505453d
Revises: 38896479ab67
Create Date: 2025-10-13 09:47:48.873329

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision = '1202f505453d'
down_revision = '38896479ab67'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Merge customers and client_info tables into a single simplified customers table.
    
    This migration:
    1. Adds client_info fields to customers table
    2. Migrates data from client_info to customers
    3. Removes unnecessary fields from customers (subtype, markets, tags, notes, etc.)
    4. Drops the client_info table
    """
    
    print("🔄 Starting customers and client_info table merge...")
    
    # Step 1: Add client_info fields to customers table
    print("📝 Adding client_info fields to customers table...")
    
    op.add_column('customers', sa.Column('full_name', sa.String(length=255), nullable=True))
    op.add_column('customers', sa.Column('login_email', sa.String(length=255), nullable=True))
    op.add_column('customers', sa.Column('phone', sa.String(length=50), nullable=True))
    op.add_column('customers', sa.Column('address', sa.String(length=500), nullable=True))
    op.add_column('customers', sa.Column('opening_hours', sa.String(length=255), nullable=True))
    op.add_column('customers', sa.Column('narrative_report', sa.Text(), nullable=True))
    op.add_column('customers', sa.Column('website_url', sa.String(length=500), nullable=True))
    op.add_column('customers', sa.Column('facebook_page_url', sa.String(length=500), nullable=True))
    op.add_column('customers', sa.Column('instagram_page_url', sa.String(length=500), nullable=True))
    op.add_column('customers', sa.Column('llm_engine_preference', sa.String(length=50), nullable=True))
    
    # Step 2: Migrate data from client_info to customers
    print("📊 Migrating data from client_info to customers...")
    
    # Create a temporary table to store the merged data
    op.execute("""
        CREATE TEMP TABLE temp_customer_merge AS
        SELECT 
            c.id,
            c.agency_id,
            c.name as full_name,  -- Use existing name as full_name
            c.status,
            c.external_ids,
            c.created_at,
            c.updated_at,
            ci.login_email,
            ci.phone,
            ci.address,
            ci.opening_hours,
            ci.narrative_report,
            ci.website_url,
            ci.facebook_page_url,
            ci.instagram_page_url,
            ci.llm_engine_preference,
            ci.is_active
        FROM customers c
        LEFT JOIN client_info ci ON ci.composite_id LIKE '%_' || c.id::text
    """)
    
    # Step 3: Update customers table with merged data
    print("🔄 Updating customers table with merged data...")
    
    op.execute("""
        UPDATE customers 
        SET 
            full_name = COALESCE(tcm.full_name, customers.name),
            login_email = tcm.login_email,
            phone = tcm.phone,
            address = tcm.address,
            opening_hours = tcm.opening_hours,
            narrative_report = tcm.narrative_report,
            website_url = tcm.website_url,
            facebook_page_url = tcm.facebook_page_url,
            instagram_page_url = tcm.instagram_page_url,
            llm_engine_preference = tcm.llm_engine_preference
        FROM temp_customer_merge tcm
        WHERE customers.id = tcm.id
    """)
    
    # Step 4: Make full_name and login_email NOT NULL (they're required)
    print("🔒 Making required fields NOT NULL...")
    
    op.execute("UPDATE customers SET full_name = name WHERE full_name IS NULL")
    op.execute("UPDATE customers SET login_email = 'no-email@example.com' WHERE login_email IS NULL")
    
    op.alter_column('customers', 'full_name', nullable=False)
    op.alter_column('customers', 'login_email', nullable=False)
    
    # Step 5: Remove unnecessary columns from customers table
    print("🗑️ Removing unnecessary columns from customers table...")
    
    op.drop_column('customers', 'subtype')
    op.drop_column('customers', 'markets')
    op.drop_column('customers', 'tags')
    op.drop_column('customers', 'notes')
    op.drop_column('customers', 'budget_monthly')
    op.drop_column('customers', 'timezone')
    op.drop_column('customers', 'name')  # Remove old name field, use full_name
    
    # Step 6: Drop the client_info table
    print("🗑️ Dropping client_info table...")
    
    op.drop_table('client_info')
    
    # Step 7: Clean up temporary table
    op.execute("DROP TABLE temp_customer_merge")
    
    print("✅ Successfully merged customers and client_info tables!")


def downgrade() -> None:
    """
    Rollback the merge by recreating separate tables.
    This is complex and may lose data, so use with caution.
    """
    
    print("⚠️ Rolling back customers and client_info table merge...")
    print("⚠️ WARNING: This rollback may lose data!")
    
    # Step 1: Recreate client_info table
    print("🔄 Recreating client_info table...")
    
    op.create_table('client_info',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('composite_id', sa.String(length=100), nullable=False),
        sa.Column('full_name', sa.String(length=255), nullable=False),
        sa.Column('login_email', sa.String(length=255), nullable=False),
        sa.Column('phone', sa.String(length=50), nullable=True),
        sa.Column('address', sa.String(length=500), nullable=True),
        sa.Column('opening_hours', sa.String(length=255), nullable=True),
        sa.Column('narrative_report', sa.Text(), nullable=True),
        sa.Column('website_url', sa.String(length=500), nullable=True),
        sa.Column('facebook_page_url', sa.String(length=500), nullable=True),
        sa.Column('instagram_page_url', sa.String(length=500), nullable=True),
        sa.Column('llm_engine_preference', sa.String(length=50), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('composite_id')
    )
    
    # Step 2: Add back removed columns to customers
    print("🔄 Adding back removed columns to customers...")
    
    op.add_column('customers', sa.Column('name', sa.String(length=255), nullable=True))
    op.add_column('customers', sa.Column('subtype', sa.String(length=100), nullable=True))
    op.add_column('customers', sa.Column('markets', sa.JSON(), nullable=True))
    op.add_column('customers', sa.Column('tags', sa.JSON(), nullable=True))
    op.add_column('customers', sa.Column('notes', sa.Text(), nullable=True))
    op.add_column('customers', sa.Column('budget_monthly', sa.Float(), nullable=True))
    op.add_column('customers', sa.Column('timezone', sa.String(length=50), nullable=True))
    
    # Step 3: Restore data (this is approximate and may lose data)
    print("📊 Restoring data (approximate)...")
    
    op.execute("UPDATE customers SET name = full_name")
    op.execute("UPDATE customers SET subtype = 'ECOMMERCE'")
    op.execute("UPDATE customers SET markets = '[]'::json")
    op.execute("UPDATE customers SET tags = '[]'::json")
    
    # Step 4: Make name NOT NULL
    op.alter_column('customers', 'name', nullable=False)
    
    # Step 5: Remove client_info fields from customers
    print("🗑️ Removing client_info fields from customers...")
    
    op.drop_column('customers', 'full_name')
    op.drop_column('customers', 'login_email')
    op.drop_column('customers', 'phone')
    op.drop_column('customers', 'address')
    op.drop_column('customers', 'opening_hours')
    op.drop_column('customers', 'narrative_report')
    op.drop_column('customers', 'website_url')
    op.drop_column('customers', 'facebook_page_url')
    op.drop_column('customers', 'instagram_page_url')
    op.drop_column('customers', 'llm_engine_preference')
    
    print("✅ Rollback completed (with potential data loss)!")
