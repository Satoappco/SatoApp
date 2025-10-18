"""add_assigned_campaigner_id_to_customers

Revision ID: 39b5f759b84e
Revises: 7e837187a740
Create Date: 2025-10-16 10:37:55.029888

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision = '39b5f759b84e'
down_revision = '7e837187a740'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Add assigned_campaigner_id to customers table.
    This tracks which campaigner is assigned to each customer for highlighting purposes.
    """
    print("🔗 Adding assigned_campaigner_id to customers table...")
    op.add_column('customers', sa.Column('assigned_campaigner_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_customers_assigned_campaigner_id',
        'customers', 'campaigners',
        ['assigned_campaigner_id'], ['id'],
        ondelete='SET NULL'
    )
    print("✅ Successfully added assigned_campaigner_id to customers table")


def downgrade() -> None:
    """
    Remove assigned_campaigner_id from customers table.
    """
    print("🔄 Removing assigned_campaigner_id from customers table...")
    op.drop_constraint('fk_customers_assigned_campaigner_id', 'customers', type_='foreignkey')
    op.drop_column('customers', 'assigned_campaigner_id')
    print("🔄 Successfully removed assigned_campaigner_id from customers table")
