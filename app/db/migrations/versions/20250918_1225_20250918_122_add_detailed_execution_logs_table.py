"""add_detailed_execution_logs_table

Revision ID: 20250918_122
Revises: 20250917_103
Create Date: 2025-09-18 12:25:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20250918_122'
down_revision = '20250917_103'
branch_labels = None
depends_on = None


def upgrade():
    # Create detailed_execution_logs table
    op.create_table('detailed_execution_logs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.Column('session_id', sa.String(length=255), nullable=False),
    sa.Column('analysis_id', sa.String(length=255), nullable=True),
    sa.Column('timestamp', sa.DateTime(), nullable=False),
    sa.Column('sequence_number', sa.Integer(), nullable=False),
    sa.Column('log_type', sa.String(), nullable=False),
    sa.Column('parent_log_id', sa.Integer(), nullable=True),
    sa.Column('depth_level', sa.Integer(), nullable=False),
    sa.Column('crew_id', sa.String(), nullable=True),
    sa.Column('task_id', sa.String(), nullable=True),
    sa.Column('agent_name', sa.String(), nullable=True),
    sa.Column('tool_name', sa.String(), nullable=True),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('duration_ms', sa.Integer(), nullable=True),
    sa.Column('title', sa.String(), nullable=False),
    sa.Column('content', sa.Text(), nullable=True),
    sa.Column('input_data', sa.Text(), nullable=True),
    sa.Column('output_data', sa.Text(), nullable=True),
    sa.Column('error_details', sa.Text(), nullable=True),
    sa.Column('log_metadata', sa.Text(), nullable=True),
    sa.Column('icon', sa.String(), nullable=True),
    sa.Column('color', sa.String(), nullable=True),
    sa.Column('is_collapsible', sa.Boolean(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_detailed_execution_logs_session_id'), 'detailed_execution_logs', ['session_id'], unique=False)
    op.create_index(op.f('ix_detailed_execution_logs_analysis_id'), 'detailed_execution_logs', ['analysis_id'], unique=False)
    op.create_index(op.f('ix_detailed_execution_logs_timestamp'), 'detailed_execution_logs', ['timestamp'], unique=False)


def downgrade():
    # Drop detailed_execution_logs table
    op.drop_index(op.f('ix_detailed_execution_logs_timestamp'), table_name='detailed_execution_logs')
    op.drop_index(op.f('ix_detailed_execution_logs_analysis_id'), table_name='detailed_execution_logs')
    op.drop_index(op.f('ix_detailed_execution_logs_session_id'), table_name='detailed_execution_logs')
    op.drop_table('detailed_execution_logs')
