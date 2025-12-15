"""Add audit_logs table for RBAC authorization tracking

Revision ID: 20251215_audit_logs
Revises: 20251211_priority_fields
Create Date: 2025-12-15

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20251215_audit_logs'
down_revision = '20251211_priority_fields'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create audit_logs table for tracking authorization decisions."""
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),

        # Who
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('user_email', sa.String(length=255), nullable=False),
        sa.Column('user_role', sa.String(length=50), nullable=False),
        sa.Column('agency_id', sa.Integer(), nullable=False),

        # What
        sa.Column('action', sa.String(length=100), nullable=False),
        sa.Column('resource_type', sa.String(length=100), nullable=False),
        sa.Column('resource_id', sa.Integer(), nullable=True),

        # Result
        sa.Column('allowed', sa.Boolean(), nullable=False),
        sa.Column('reason', sa.String(), nullable=True),

        # Request metadata
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.String(length=500), nullable=True),
        sa.Column('request_path', sa.String(length=500), nullable=True),
        sa.Column('request_method', sa.String(length=10), nullable=True),

        # Primary key and indexes
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['campaigners.id'], ),
        sa.ForeignKeyConstraint(['agency_id'], ['agencies.id'], ),
    )

    # Create indexes for fast queries
    op.create_index('ix_audit_logs_user_id', 'audit_logs', ['user_id'])
    op.create_index('ix_audit_logs_user_email', 'audit_logs', ['user_email'])
    op.create_index('ix_audit_logs_agency_id', 'audit_logs', ['agency_id'])
    op.create_index('ix_audit_logs_action', 'audit_logs', ['action'])
    op.create_index('ix_audit_logs_resource_type', 'audit_logs', ['resource_type'])
    op.create_index('ix_audit_logs_resource_id', 'audit_logs', ['resource_id'])
    op.create_index('ix_audit_logs_allowed', 'audit_logs', ['allowed'])
    op.create_index('ix_audit_logs_created_at', 'audit_logs', ['created_at'])

    print("✅ Created audit_logs table with indexes for RBAC authorization tracking")


def downgrade() -> None:
    """Drop audit_logs table."""
    # Drop indexes first
    op.drop_index('ix_audit_logs_created_at', 'audit_logs')
    op.drop_index('ix_audit_logs_allowed', 'audit_logs')
    op.drop_index('ix_audit_logs_resource_id', 'audit_logs')
    op.drop_index('ix_audit_logs_resource_type', 'audit_logs')
    op.drop_index('ix_audit_logs_action', 'audit_logs')
    op.drop_index('ix_audit_logs_agency_id', 'audit_logs')
    op.drop_index('ix_audit_logs_user_email', 'audit_logs')
    op.drop_index('ix_audit_logs_user_id', 'audit_logs')

    # Drop table
    op.drop_table('audit_logs')

    print("✅ Dropped audit_logs table")
