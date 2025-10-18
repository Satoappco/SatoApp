"""remove_unused_execution_timings_table

Revision ID: 7c66761a3fa8
Revises: 185377f6c1fd
Create Date: 2025-10-15 10:00:55.770223

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision = '7c66761a3fa8'
down_revision = '185377f6c1fd'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Remove unused execution_timings table and related code.
    This table is marked as deprecated and customer_logs already contains timing data.
    """
    print("🔄 Removing unused execution_timings table...")
    
    # Drop execution_timings table
    try:
        op.drop_table('execution_timings')
        print("✅ Removed execution_timings table")
    except Exception as e:
        print(f"⚠️  Could not remove execution_timings table: {e}")
    
    print("✅ Execution timings cleanup completed!")


def downgrade() -> None:
    """
    Recreate execution_timings table (for rollback purposes)
    """
    print("🔄 Recreating execution_timings table...")
    
    # Recreate execution_timings table
    try:
        op.create_table('execution_timings',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('session_id', sa.String(length=255), nullable=False),
            sa.Column('analysis_id', sa.String(length=255), nullable=True),
            sa.Column('component_type', sa.String(length=100), nullable=False),
            sa.Column('component_name', sa.String(length=255), nullable=False),
            sa.Column('start_time', sa.DateTime(), nullable=False),
            sa.Column('end_time', sa.DateTime(), nullable=True),
            sa.Column('duration_ms', sa.Integer(), nullable=True),
            sa.Column('status', sa.String(length=50), nullable=False),
            sa.Column('input_data', sa.Text(), nullable=True),
            sa.Column('output_data', sa.Text(), nullable=True),
            sa.Column('error_message', sa.Text(), nullable=True),
            sa.Column('parent_session_id', sa.String(length=255), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('updated_at', sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_execution_timings_session_id'), 'execution_timings', ['session_id'], unique=False)
        op.create_index(op.f('ix_execution_timings_analysis_id'), 'execution_timings', ['analysis_id'], unique=False)
        print("✅ Recreated execution_timings table")
    except Exception as e:
        print(f"⚠️  Could not recreate execution_timings table: {e}")
    
    print("✅ Execution timings rollback completed!")
