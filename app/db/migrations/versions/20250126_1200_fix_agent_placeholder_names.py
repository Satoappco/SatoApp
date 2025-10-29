"""Fix agent placeholder names - subcustomer_id to customer_id, user_id to campaigner_id

Revision ID: 20250126_1200
Revises: 
Create Date: 2025-01-26 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20250126_1200'
down_revision = '4a7747777f49'
branch_labels = None
depends_on = None


def upgrade():
    """Update all agent task templates to use new naming convention"""
    connection = op.get_bind()
    
    # Update subcustomer_id to customer_id in agent task templates
    connection.execute(sa.text("""
        UPDATE agent_configs 
        SET task = REPLACE(task, '{subcustomer_id}', '{customer_id}')
        WHERE task LIKE '%{subcustomer_id}%'
    """))
    
    # Update user_id to campaigner_id in agent task templates  
    connection.execute(sa.text("""
        UPDATE agent_configs 
        SET task = REPLACE(task, '{user_id}', '{campaigner_id}')
        WHERE task LIKE '%{user_id}%'
    """))
    
    print("✓ Fixed agent placeholder names: subcustomer_id -> customer_id, user_id -> campaigner_id")


def downgrade():
    """Revert to old naming convention (not recommended)"""
    connection = op.get_bind()
    
    connection.execute(sa.text("""
        UPDATE agent_configs 
        SET task = REPLACE(task, '{customer_id}', '{subcustomer_id}')
        WHERE task LIKE '%{customer_id}%'
    """))
    
    connection.execute(sa.text("""
        UPDATE agent_configs 
        SET task = REPLACE(task, '{campaigner_id}', '{user_id}')
        WHERE task LIKE '%{campaigner_id}%'
    """))
    
    print("✓ Reverted agent placeholder names to old convention")

