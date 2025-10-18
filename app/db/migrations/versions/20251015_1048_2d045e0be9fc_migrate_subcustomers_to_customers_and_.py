"""migrate_subcustomers_to_customers_and_update_logs

Revision ID: 2d045e0be9fc
Revises: 73d1c69d6a9f
Create Date: 2025-10-15 10:48:11.404864

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision = '2d045e0be9fc'
down_revision = '73d1c69d6a9f'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Migrate data from sub_customers to customers table and update customer_logs.
    This migration handles the terminology change:
    - sub_customers → customers (the actual business customers)
    - customers → campaigners (the users who manage customers)
    """
    print("🔄 Starting comprehensive data migration...")
    
    try:
        connection = op.get_bind()
        
        # Step 1: Migrate sub_customers data to customers table
        print("📋 Step 1: Migrating sub_customers to customers...")
        
        # First, let's see what data we have
        sub_customers_count = connection.execute(sa.text("SELECT COUNT(*) FROM sub_customers")).fetchone()[0]
        customers_count = connection.execute(sa.text("SELECT COUNT(*) FROM customers")).fetchone()[0]
        
        print(f"   Found {sub_customers_count} sub_customers and {customers_count} existing customers")
        
        if sub_customers_count > 0:
            # Migrate sub_customers to customers table
            # Map sub_customers fields to customers fields
            connection.execute(sa.text("""
                INSERT INTO customers (
                    agency_id, status, external_ids, full_name, login_email, 
                    phone, address, opening_hours, narrative_report, 
                    website_url, facebook_page_url, instagram_page_url, 
                    llm_engine_preference, is_active, created_at, updated_at
                )
                SELECT 
                    sc.customer_id as agency_id,  -- sub_customers.customer_id maps to customers.agency_id
                    sc.status,
                    sc.external_ids,
                    sc.name as full_name,
                    NULL as login_email,  -- sub_customers doesn't have email
                    NULL as phone,  -- sub_customers doesn't have phone
                    NULL as address,  -- sub_customers doesn't have address
                    NULL as opening_hours,  -- sub_customers doesn't have opening_hours
                    sc.notes as narrative_report,  -- sub_customers.notes maps to customers.narrative_report
                    NULL as website_url,  -- sub_customers doesn't have website_url
                    NULL as facebook_page_url,  -- sub_customers doesn't have facebook_page_url
                    NULL as instagram_page_url,  -- sub_customers doesn't have instagram_page_url
                    NULL as llm_engine_preference,  -- sub_customers doesn't have llm_engine_preference
                    CASE WHEN sc.status = 'active' THEN true ELSE false END as is_active,
                    sc.created_at,
                    sc.updated_at
                FROM sub_customers sc
                WHERE NOT EXISTS (
                    SELECT 1 FROM customers c WHERE c.agency_id = sc.customer_id AND c.full_name = sc.name
                )
            """))
            
            migrated_count = connection.execute(sa.text("SELECT COUNT(*) FROM customers WHERE agency_id IN (SELECT customer_id FROM sub_customers)")).fetchone()[0]
            print(f"   ✅ Migrated {migrated_count} sub_customers to customers table")
        
        # Step 2: Update customer_logs to use campaigner_id
        print("📋 Step 2: Updating customer_logs campaigner_id...")
        
        # Get the first campaigner ID for NULL campaigner_id records
        first_campaigner = connection.execute(sa.text("SELECT id FROM campaigners ORDER BY id LIMIT 1")).fetchone()
        
        if first_campaigner:
            campaigner_id = first_campaigner[0]
            print(f"   Using campaigner_id: {campaigner_id}")
            
            # Update NULL campaigner_id records
            connection.execute(
                sa.text("UPDATE customer_logs SET campaigner_id = :campaigner_id WHERE campaigner_id IS NULL"),
                {"campaigner_id": campaigner_id}
            )
            
            updated_logs = connection.execute(sa.text("SELECT COUNT(*) FROM customer_logs WHERE campaigner_id = :campaigner_id"), {"campaigner_id": campaigner_id}).fetchone()[0]
            print(f"   ✅ Updated {updated_logs} customer_logs records with campaigner_id")
        
        # Step 3: Drop the sub_customers table (with CASCADE to handle foreign key constraints)
        print("📋 Step 3: Dropping sub_customers table...")
        connection.execute(sa.text("DROP TABLE IF EXISTS sub_customers CASCADE"))
        print("   ✅ Dropped sub_customers table and dependent objects")
        
        print("✅ Data migration completed successfully!")
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        raise


def downgrade() -> None:
    """
    Revert the migration by recreating sub_customers table and moving data back.
    """
    print("🔄 Reverting data migration...")
    
    try:
        connection = op.get_bind()
        
        # Step 1: Recreate sub_customers table
        print("📋 Step 1: Recreating sub_customers table...")
        connection.execute(sa.text("""
            CREATE TABLE sub_customers (
                id SERIAL PRIMARY KEY,
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
                customer_id INTEGER NOT NULL,
                name VARCHAR NOT NULL,
                subtype VARCHAR,
                status VARCHAR,
                external_ids JSON,
                timezone VARCHAR,
                markets JSON,
                budget_monthly DOUBLE PRECISION,
                tags JSON,
                notes TEXT
            )
        """))
        print("   ✅ Recreated sub_customers table")
        
        # Step 2: Move data back from customers to sub_customers
        print("📋 Step 2: Moving data back to sub_customers...")
        connection.execute(sa.text("""
            INSERT INTO sub_customers (
                customer_id, name, subtype, status, external_ids, 
                timezone, markets, budget_monthly, tags, notes, 
                created_at, updated_at
            )
            SELECT 
                agency_id as customer_id,
                full_name as name,
                'business' as subtype,
                status,
                external_ids,
                'UTC' as timezone,
                '{}' as markets,
                0.0 as budget_monthly,
                '{}' as tags,
                narrative_report as notes,
                created_at,
                updated_at
            FROM customers
        """))
        
        migrated_back = connection.execute(sa.text("SELECT COUNT(*) FROM sub_customers")).fetchone()[0]
        print(f"   ✅ Moved {migrated_back} records back to sub_customers")
        
        # Step 3: Clear campaigner_id from customer_logs
        print("📋 Step 3: Clearing campaigner_id from customer_logs...")
        connection.execute(sa.text("UPDATE customer_logs SET campaigner_id = NULL"))
        print("   ✅ Cleared campaigner_id from customer_logs")
        
        print("✅ Migration rollback completed!")
        
    except Exception as e:
        print(f"❌ Rollback failed: {e}")
        raise
