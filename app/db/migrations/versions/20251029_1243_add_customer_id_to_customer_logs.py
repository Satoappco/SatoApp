"""add_customer_id_to_customer_logs

Revision ID: add_customer_id_20251029
Revises: 886ed1524679
Create Date: 2025-10-29 12:43:00.000000

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision = 'add_customer_id_20251029'
down_revision = '886ed1524679'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Add customer_id column to customer_logs table.
    This allows filtering logs by specific customer.
    """
    print("🔄 Adding customer_id column to customer_logs table...")
    
    try:
        # Add customer_id column as nullable (existing logs won't have customer_id)
        op.add_column('customer_logs', 
            sa.Column('customer_id', sa.Integer(), nullable=True)
        )
        
        # Add foreign key constraint
        op.create_foreign_key(
            'fk_customer_logs_customer_id',
            'customer_logs', 'customers',
            ['customer_id'], ['id']
        )
        
        # Create index for better query performance
        op.create_index('ix_customer_logs_customer_id', 'customer_logs', ['customer_id'])
        
        print("✅ Added customer_id column to customer_logs table")
        
    except Exception as e:
        print(f"⚠️  Could not add customer_id column: {e}")
        raise


def downgrade() -> None:
    """
    Remove customer_id column from customer_logs table.
    """
    print("🔄 Removing customer_id column from customer_logs table...")
    
    try:
        # Drop index first
        op.drop_index('ix_customer_logs_customer_id', table_name='customer_logs')
        
        # Drop foreign key constraint
        op.drop_constraint('fk_customer_logs_customer_id', 'customer_logs', type_='foreignkey')
        
        # Drop column
        op.drop_column('customer_logs', 'customer_id')
        
        print("✅ Removed customer_id column from customer_logs table")
        
    except Exception as e:
        print(f"⚠️  Could not remove customer_id column: {e}")

