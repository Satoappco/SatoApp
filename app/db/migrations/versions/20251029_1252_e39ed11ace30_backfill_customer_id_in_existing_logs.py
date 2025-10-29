"""backfill_customer_id_in_existing_logs

Revision ID: e39ed11ace30
Revises: add_customer_id_20251029
Create Date: 2025-10-29 12:52:25.228998

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision = 'e39ed11ace30'
down_revision = 'add_customer_id_20251029'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Distribute existing logs with NULL customer_id to all customers.
    Since these are fake/test logs, we'll split them evenly across all customers.
    """
    print("🔄 Distributing logs with NULL customer_id to all customers...")
    
    try:
        connection = op.get_bind()
        
        # Get all customer IDs
        result = connection.execute(sa.text("SELECT id FROM customers WHERE is_active = true ORDER BY id"))
        all_customers = [row[0] for row in result.fetchall()]
        
        if not all_customers:
            print("⚠️  No active customers found - skipping backfill")
            return
        
        print(f"   Found {len(all_customers)} active customers: {all_customers}")
        
        # Get all logs with NULL customer_id
        result = connection.execute(sa.text("SELECT id FROM customer_logs WHERE customer_id IS NULL ORDER BY id"))
        logs_without_customer = [row[0] for row in result.fetchall()]
        
        if not logs_without_customer:
            print("   ✅ No logs with NULL customer_id found - nothing to backfill")
            return
        
        print(f"   Found {len(logs_without_customer)} logs with NULL customer_id")
        
        # Distribute logs evenly across customers using modulo
        customer_count = len(all_customers)
        updated_count = 0
        
        for i, log_id in enumerate(logs_without_customer):
            # Round-robin assignment: assign log to customer based on log ID
            customer_id = all_customers[i % customer_count]
            
            connection.execute(
                sa.text("UPDATE customer_logs SET customer_id = :customer_id WHERE id = :log_id"),
                {"customer_id": customer_id, "log_id": log_id}
            )
            updated_count += 1
        
        print(f"   ✅ Distributed {updated_count} logs across {customer_count} customers")
        
    except Exception as e:
        print(f"⚠️  Could not backfill customer_id: {e}")
        raise


def downgrade() -> None:
    """
    Set customer_id back to NULL for logs that were backfilled.
    This is a simple revert - sets all customer_id to NULL (can't distinguish backfilled logs)
    """
    print("🔄 Reverting customer_id backfill...")
    
    try:
        connection = op.get_bind()
        # Note: This will set ALL customer_id to NULL, not just backfilled ones
        # For a proper revert, we'd need to track which logs were backfilled
        print("   ⚠️  Warning: This will set all customer_id to NULL")
        # connection.execute(sa.text("UPDATE customer_logs SET customer_id = NULL WHERE ..."))
        print("   Skipping revert (not implemented - would affect all logs)")
        
    except Exception as e:
        print(f"⚠️  Could not revert customer_id backfill: {e}")
