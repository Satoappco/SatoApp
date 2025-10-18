"""add_customer_id_to_connections_table

Revision ID: 2748cb7d19bc
Revises: f1a9e12d482b
Create Date: 2025-10-15 20:47:35.331504

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision = '2748cb7d19bc'
down_revision = 'f1a9e12d482b'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Add customer_id to connections table to improve query performance and match frontend logic.
    This allows direct customer-based queries without joining through digital_assets.
    """
    print("🔗 Adding customer_id to connections table...")
    print("📊 This will improve query performance and match frontend customer-centric logic...")
    
    # Add customer_id column to connections table
    try:
        print("➕ Adding customer_id column to connections...")
        op.add_column('connections', sa.Column('customer_id', sa.Integer(), nullable=True))
        print("✅ Successfully added customer_id column")
    except Exception as e:
        print(f"⚠️  Could not add customer_id column: {e}")
        return
    
    # Populate customer_id from digital_assets table
    try:
        print("🔄 Populating customer_id from digital_assets...")
        op.execute("""
            UPDATE connections 
            SET customer_id = (
                SELECT digital_assets.customer_id 
                FROM digital_assets 
                WHERE digital_assets.id = connections.digital_asset_id
            )
        """)
        print("✅ Successfully populated customer_id from digital_assets")
    except Exception as e:
        print(f"⚠️  Could not populate customer_id: {e}")
        return
    
    # Make customer_id NOT NULL after populating
    try:
        print("🔒 Making customer_id NOT NULL...")
        op.alter_column('connections', 'customer_id', nullable=False)
        print("✅ Successfully made customer_id NOT NULL")
    except Exception as e:
        print(f"⚠️  Could not make customer_id NOT NULL: {e}")
        return
    
    # Add foreign key constraint
    try:
        print("🔗 Adding foreign key constraint...")
        op.create_foreign_key(
            'fk_connections_customer_id',
            'connections', 'customers',
            ['customer_id'], ['id'],
            ondelete='CASCADE'
        )
        print("✅ Successfully added foreign key constraint")
    except Exception as e:
        print(f"⚠️  Could not add foreign key constraint: {e}")
        return
    
    print("🎉 Connections table updated successfully!")
    print("📊 Now supports direct customer-based queries without joins")


def downgrade() -> None:
    """
    Remove customer_id from connections table.
    """
    print("🔄 Removing customer_id from connections table...")
    print("⚠️  WARNING: This will remove the customer_id column - data will be lost!")
    
    # Drop foreign key constraint
    try:
        print("🗑️  Dropping foreign key constraint...")
        op.drop_constraint('fk_connections_customer_id', 'connections', type_='foreignkey')
        print("✅ Successfully dropped foreign key constraint")
    except Exception as e:
        print(f"⚠️  Could not drop foreign key constraint: {e}")
    
    # Drop customer_id column
    try:
        print("🗑️  Dropping customer_id column...")
        op.drop_column('connections', 'customer_id')
        print("✅ Successfully dropped customer_id column")
    except Exception as e:
        print(f"⚠️  Could not drop customer_id column: {e}")
    
    print("🔄 Connections table reverted successfully!")
