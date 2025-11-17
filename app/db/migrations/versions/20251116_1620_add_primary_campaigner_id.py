"""add_primary_campaigner_id

Revision ID: ghi789012345
Revises: def456789012
Create Date: 2025-11-16 16:20:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'ghi789012345'
down_revision = 'def456789012'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Add primary_campaigner_id to customers table for denormalized fast lookups.
    Populate from customer_campaigner_assignments where is_primary = TRUE.
    """
    print("🔗 Adding primary_campaigner_id to customers table...")

    # Add column
    op.add_column('customers', sa.Column('primary_campaigner_id', sa.Integer(), nullable=True))

    # Add foreign key
    op.create_foreign_key(
        'fk_customers_primary_campaigner_id',
        'customers', 'campaigners',
        ['primary_campaigner_id'], ['id'],
        ondelete='SET NULL'
    )

    # Add index
    op.create_index('idx_customers_primary_campaigner_id', 'customers', ['primary_campaigner_id'])

    # Populate from junction table
    print("📊 Populating primary_campaigner_id from assignments...")
    connection = op.get_bind()

    update_sql = """
        UPDATE customers
        SET primary_campaigner_id = cca.campaigner_id
        FROM customer_campaigner_assignments cca
        WHERE customers.id = cca.customer_id
        AND cca.is_primary = TRUE
        AND cca.is_active = TRUE
    """

    result = connection.execute(sa.text(update_sql))
    print(f"✅ Updated {result.rowcount} customers with primary campaigner")

    # Add comment
    connection.execute(sa.text(
        "COMMENT ON COLUMN customers.primary_campaigner_id IS "
        "'Denormalized primary campaigner for fast lookups. Synced from customer_campaigner_assignments.'"
    ))

    # Add comment to deprecated field
    connection.execute(sa.text(
        "COMMENT ON COLUMN customers.assigned_campaigner_id IS "
        "'DEPRECATED: Use customer_campaigner_assignments table instead. Kept for backward compatibility.'"
    ))

    print("✅ Successfully added and populated primary_campaigner_id")


def downgrade() -> None:
    """Remove primary_campaigner_id from customers table."""
    print("🔄 Removing primary_campaigner_id from customers table...")

    op.drop_index('idx_customers_primary_campaigner_id', table_name='customers')
    op.drop_constraint('fk_customers_primary_campaigner_id', 'customers', type_='foreignkey')
    op.drop_column('customers', 'primary_campaigner_id')

    # Remove comments
    connection = op.get_bind()
    connection.execute(sa.text(
        "COMMENT ON COLUMN customers.assigned_campaigner_id IS "
        "'Campaigner assigned to this customer'"
    ))

    print("🔄 Successfully removed primary_campaigner_id")
