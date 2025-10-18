"""rename_tables_users_to_campaigners_customers_to_agencies_subcustomers_to_customers_info_to_client_info

Revision ID: eff2f4dfb2f7
Revises: 7316b1ad017a
Create Date: 2025-10-12 09:07:36.686204

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision = 'eff2f4dfb2f7'
down_revision = '7316b1ad017a'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Rename tables to better reflect their purpose:
    - users -> campaigners (agency workers/campaigners)
    - customers -> agencies (marketing agencies)
    - sub_customers -> customers (agency clients)
    - info_table -> client_info (client-specific information)
    - user_sessions -> campaigner_sessions
    """
    
    print("Renaming tables to better reflect their purpose...")
    
    # Rename main tables
    op.rename_table('users', 'campaigners')
    op.rename_table('customers', 'agencies')
    op.rename_table('sub_customers', 'customers')
    op.rename_table('info_table', 'client_info')
    op.rename_table('user_sessions', 'campaigner_sessions')
    
    print("✅ All tables renamed successfully!")


def downgrade() -> None:
    """
    Revert table names back to original names.
    """
    
    print("Reverting table names to original names...")
    
    # Revert table names
    op.rename_table('campaigners', 'users')
    op.rename_table('agencies', 'customers')
    op.rename_table('customers', 'sub_customers')
    op.rename_table('client_info', 'info_table')
    op.rename_table('campaigner_sessions', 'user_sessions')
    
    print("✅ All table names reverted successfully!")
