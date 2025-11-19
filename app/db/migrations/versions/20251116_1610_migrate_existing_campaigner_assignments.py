"""migrate_existing_campaigner_assignments

Revision ID: def456789012
Revises: abc123456789
Create Date: 2025-11-16 16:10:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table, column, select

# revision identifiers, used by Alembic.
revision = 'def456789012'
down_revision = 'abc123456789'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Migrate existing customer assignments from assigned_campaigner_id
    to customer_campaigner_assignments table.
    """
    print("🔄 Migrating existing campaigner assignments...")

    # Define tables for data migration
    customers = table('customers',
        column('id', sa.Integer),
        column('assigned_campaigner_id', sa.Integer),
        column('created_at', sa.DateTime)
    )

    assignments = table('customer_campaigner_assignments',
        column('customer_id', sa.Integer),
        column('campaigner_id', sa.Integer),
        column('role', sa.String),
        column('is_primary', sa.Boolean),
        column('is_active', sa.Boolean),
        column('assigned_at', sa.DateTime)
    )

    # Get database connection
    connection = op.get_bind()

    # Fetch all customers with assigned campaigners
    result = connection.execute(
        select(customers.c.id, customers.c.assigned_campaigner_id, customers.c.created_at)
        .where(customers.c.assigned_campaigner_id.isnot(None))
    )

    customers_to_migrate = result.fetchall()
    print(f"📊 Found {len(customers_to_migrate)} customers with assigned campaigners")

    # Migrate each customer
    migrated_count = 0
    for customer_id, campaigner_id, created_at in customers_to_migrate:
        try:
            # Insert into customer_campaigner_assignments
            connection.execute(
                assignments.insert().values(
                    customer_id=customer_id,
                    campaigner_id=campaigner_id,
                    role='PRIMARY',
                    is_primary=True,
                    is_active=True,
                    assigned_at=created_at if created_at else sa.text('NOW()')
                )
            )
            migrated_count += 1
        except Exception as e:
            print(f"⚠️  Failed to migrate customer {customer_id}: {e}")
            # Continue with next customer

    print(f"✅ Successfully migrated {migrated_count}/{len(customers_to_migrate)} assignments")

    # Verify migration
    verify_result = connection.execute(
        sa.text("SELECT COUNT(*) FROM customer_campaigner_assignments WHERE is_active = TRUE")
    )
    active_assignments = verify_result.scalar()
    print(f"📊 Total active assignments in new table: {active_assignments}")


def downgrade() -> None:
    """
    Remove migrated assignments from junction table.
    Note: This does NOT restore assigned_campaigner_id as it was not changed.
    """
    print("🔄 Removing migrated assignments from junction table...")

    connection = op.get_bind()

    # Delete all assignments that were created during migration
    result = connection.execute(
        sa.text("DELETE FROM customer_campaigner_assignments WHERE is_primary = TRUE")
    )

    print(f"🔄 Removed {result.rowcount} assignments from junction table")
