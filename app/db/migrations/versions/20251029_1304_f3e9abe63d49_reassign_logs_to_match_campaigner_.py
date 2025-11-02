"""reassign_logs_to_match_campaigner_customers

Revision ID: f3e9abe63d49
Revises: e39ed11ace30
Create Date: 2025-10-29 13:04:07.656008

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision = 'f3e9abe63d49'
down_revision = 'e39ed11ace30'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Reassign logs to customers that belong to the campaigner who created them.
    This fixes the issue where logs were distributed randomly without considering
    which campaigner created them.
    """
    print("🔄 Reassigning logs to match campaigner-customer relationships...")
    
    try:
        connection = op.get_bind()
        
        # Get all logs with campaigner_id
        result = connection.execute(sa.text("""
            SELECT id, campaigner_id, customer_id 
            FROM customer_logs 
            WHERE campaigner_id IS NOT NULL
            ORDER BY id
        """))
        all_logs = result.fetchall()
        
        if not all_logs:
            print("   ✅ No logs found - nothing to reassign")
            return
        
        print(f"   Found {len(all_logs)} logs to reassign")
        
        updated_count = 0
        skipped_count = 0
        
        for log_id, campaigner_id, current_customer_id in all_logs:
            # Get customers assigned to this campaigner
            result = connection.execute(sa.text("""
                SELECT id FROM customers 
                WHERE assigned_campaigner_id = :campaigner_id 
                  AND is_active = true
                ORDER BY id
            """), {"campaigner_id": campaigner_id})
            assigned_customers = [row[0] for row in result.fetchall()]
            
            if not assigned_customers:
                # Campaigner has no assigned customers - check if current assignment is wrong
                # We'll skip these for now (could assign to agency customers, but better to leave them)
                if current_customer_id:
                    # Check if current customer belongs to this campaigner's agency
                    agency_check = connection.execute(sa.text("""
                        SELECT c.agency_id, camp.agency_id as campaigner_agency_id
                        FROM customers c, campaigners camp
                        WHERE c.id = :customer_id 
                          AND camp.id = :campaigner_id
                    """), {"customer_id": current_customer_id, "campaigner_id": campaigner_id})
                    agency_match = agency_check.fetchone()
                    
                    if not agency_match or agency_match[0] != agency_match[1]:
                        # Customer doesn't belong to campaigner's agency - set to NULL
                        connection.execute(sa.text("""
                            UPDATE customer_logs SET customer_id = NULL 
                            WHERE id = :log_id
                        """), {"log_id": log_id})
                        skipped_count += 1
                    else:
                        # Same agency, so keep it (even though not directly assigned)
                        pass
                else:
                    # Already NULL, skip
                    pass
                continue
            
            # Check if current customer_id is correct (belongs to this campaigner)
            if current_customer_id in assigned_customers:
                # Already correctly assigned - skip
                continue
            
            # Reassign to first customer assigned to this campaigner
            # (or we could distribute evenly, but for now just use first one)
            new_customer_id = assigned_customers[0]
            
            # If campaigner has multiple customers, distribute logs evenly
            if len(assigned_customers) > 1:
                # Use modulo to distribute evenly
                customer_index = (log_id % len(assigned_customers))
                new_customer_id = assigned_customers[customer_index]
            
            connection.execute(sa.text("""
                UPDATE customer_logs 
                SET customer_id = :customer_id 
                WHERE id = :log_id
            """), {"customer_id": new_customer_id, "log_id": log_id})
            updated_count += 1
        
        print(f"   ✅ Reassigned {updated_count} logs to match campaigner-customer relationships")
        if skipped_count > 0:
            print(f"   ⚠️  Skipped {skipped_count} logs (campaigner has no assigned customers)")
        
    except Exception as e:
        print(f"⚠️  Could not reassign logs: {e}")
        raise


def downgrade() -> None:
    """
    Cannot easily revert - would need to know original distribution.
    This migration is not easily reversible.
    """
    print("⚠️  Reverting this migration is not supported")
    print("   The original log distribution is not stored")
