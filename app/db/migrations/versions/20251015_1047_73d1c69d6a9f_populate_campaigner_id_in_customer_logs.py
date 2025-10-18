"""populate_campaigner_id_in_customer_logs

Revision ID: 73d1c69d6a9f
Revises: 7c66761a3fa8
Create Date: 2025-10-15 10:47:03.613724

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision = '73d1c69d6a9f'
down_revision = '7c66761a3fa8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Populate campaigner_id in customer_logs table for existing records.
    Since we can't determine which campaigner the old logs belong to,
    we'll assign them to the first campaigner in the system.
    """
    print("🔄 Populating campaigner_id in customer_logs table...")
    
    try:
        # Get the first campaigner ID
        connection = op.get_bind()
        result = connection.execute(sa.text("SELECT id FROM campaigners ORDER BY id LIMIT 1"))
        first_campaigner_id = result.fetchone()
        
        if first_campaigner_id:
            campaigner_id = first_campaigner_id[0]
            print(f"✅ Found first campaigner with ID: {campaigner_id}")
            
            # Update all NULL campaigner_id records
            connection.execute(
                sa.text("UPDATE customer_logs SET campaigner_id = :campaigner_id WHERE campaigner_id IS NULL"),
                {"campaigner_id": campaigner_id}
            )
            
            # Check how many records were updated
            result = connection.execute(sa.text("SELECT COUNT(*) FROM customer_logs WHERE campaigner_id = :campaigner_id"), {"campaigner_id": campaigner_id})
            updated_count = result.fetchone()[0]
            print(f"✅ Updated {updated_count} customer_logs records with campaigner_id = {campaigner_id}")
        else:
            print("⚠️  No campaigners found in the system - skipping population")
            
    except Exception as e:
        print(f"⚠️  Could not populate campaigner_id: {e}")


def downgrade() -> None:
    """
    Set campaigner_id to NULL for all records (revert the population)
    """
    print("🔄 Reverting campaigner_id population...")
    
    try:
        connection = op.get_bind()
        connection.execute(sa.text("UPDATE customer_logs SET campaigner_id = NULL"))
        print("✅ Reverted campaigner_id to NULL for all customer_logs records")
    except Exception as e:
        print(f"⚠️  Could not revert campaigner_id: {e}")
