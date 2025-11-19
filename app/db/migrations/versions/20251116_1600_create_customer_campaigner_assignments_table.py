"""create_customer_campaigner_assignments_table

Revision ID: abc123456789
Revises: f3e9abe63d49
Create Date: 2025-11-16 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'abc123456789'
down_revision = 'app_settings_001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Create customer_campaigner_assignments junction table for many-to-many relationship.
    This allows multiple campaigners to be assigned to a single customer.
    """
    print("📋 Creating customer_campaigner_assignments table...")

    # Create the junction table
    op.create_table(
        'customer_campaigner_assignments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.Integer(), nullable=False),
        sa.Column('campaigner_id', sa.Integer(), nullable=False),

        # Assignment metadata
        sa.Column('role', sa.String(length=50), nullable=False, server_default='assigned'),
        sa.Column('is_primary', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('assigned_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('assigned_by_campaigner_id', sa.Integer(), nullable=True),

        # Status tracking
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('unassigned_at', sa.DateTime(), nullable=True),
        sa.Column('unassigned_by_campaigner_id', sa.Integer(), nullable=True),

        # Audit fields
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),

        # Primary key
        sa.PrimaryKeyConstraint('id'),

        # Foreign keys
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['campaigner_id'], ['campaigners.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['assigned_by_campaigner_id'], ['campaigners.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['unassigned_by_campaigner_id'], ['campaigners.id'], ondelete='SET NULL'),

        # Unique constraint: one active assignment per customer-campaigner pair
        sa.UniqueConstraint('customer_id', 'campaigner_id', 'is_active',
                          name='unique_customer_campaigner_active')
    )

    # Create indexes for performance
    print("📊 Creating indexes...")
    op.create_index('idx_cca_customer_id', 'customer_campaigner_assignments', ['customer_id'])
    op.create_index('idx_cca_campaigner_id', 'customer_campaigner_assignments', ['campaigner_id'])
    op.create_index('idx_cca_is_active', 'customer_campaigner_assignments', ['is_active'])
    op.create_index('idx_cca_is_primary', 'customer_campaigner_assignments', ['is_primary'])
    op.create_index('idx_cca_customer_active', 'customer_campaigner_assignments', ['customer_id', 'is_active'])

    print("✅ Successfully created customer_campaigner_assignments table with indexes")


def downgrade() -> None:
    """
    Remove customer_campaigner_assignments table.
    WARNING: This will lose all assignment data!
    """
    print("🔄 Dropping customer_campaigner_assignments table...")

    # Drop indexes first
    op.drop_index('idx_cca_customer_active', table_name='customer_campaigner_assignments')
    op.drop_index('idx_cca_is_primary', table_name='customer_campaigner_assignments')
    op.drop_index('idx_cca_is_active', table_name='customer_campaigner_assignments')
    op.drop_index('idx_cca_campaigner_id', table_name='customer_campaigner_assignments')
    op.drop_index('idx_cca_customer_id', table_name='customer_campaigner_assignments')

    # Drop table
    op.drop_table('customer_campaigner_assignments')

    print("🔄 Successfully dropped customer_campaigner_assignments table")
