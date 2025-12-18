"""Add deep research tables for comprehensive research feature

Revision ID: 20251218_deep_research
Revises: 20251218_0001_ensure_unique_email_google_id_campaigners
Create Date: 2025-12-18

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '20251218_deep_research'
down_revision = '20251215_audit_logs'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create research_sessions, research_steps, and research_sources tables."""

    # Create research_sessions table
    op.create_table(
        'research_sessions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),

        # Core identification
        sa.Column('session_id', sa.String(length=255), nullable=False),
        sa.Column('thread_id', sa.String(length=255), nullable=True),

        # Ownership
        sa.Column('campaigner_id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.Integer(), nullable=True),

        # Request
        sa.Column('query', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),

        # Configuration (JSONB)
        sa.Column('config', postgresql.JSONB(astext_type=sa.Text()), nullable=False),

        # Results
        sa.Column('final_report', sa.Text(), nullable=True),
        sa.Column('intermediate_artifacts', postgresql.JSONB(astext_type=sa.Text()), nullable=True),

        # Tracing
        sa.Column('langfuse_trace_id', sa.String(length=255), nullable=True),
        sa.Column('langfuse_trace_url', sa.String(length=1024), nullable=True),

        # Metrics
        sa.Column('total_execution_time_ms', sa.Integer(), nullable=True),
        sa.Column('tokens_used', sa.Integer(), nullable=True),
        sa.Column('api_calls_made', sa.Integer(), nullable=True),

        # Primary key and constraints
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['campaigner_id'], ['campaigners.id'], ),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ),
        sa.UniqueConstraint('session_id'),
    )

    # Create indexes for research_sessions
    op.create_index('ix_research_sessions_session_id', 'research_sessions', ['session_id'])
    op.create_index('ix_research_sessions_thread_id', 'research_sessions', ['thread_id'])
    op.create_index('ix_research_sessions_campaigner_id', 'research_sessions', ['campaigner_id'])
    op.create_index('ix_research_sessions_status', 'research_sessions', ['status'])

    print("✅ Created research_sessions table with indexes")

    # Create research_steps table
    op.create_table(
        'research_steps',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),

        # Core identification
        sa.Column('research_session_id', sa.Integer(), nullable=False),

        # Step details
        sa.Column('step_type', sa.String(length=50), nullable=False),
        sa.Column('step_index', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),

        # Step data (JSONB)
        sa.Column('input_data', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('output_data', postgresql.JSONB(astext_type=sa.Text()), nullable=False),

        # Error handling
        sa.Column('error_message', sa.Text(), nullable=True),

        # Metrics
        sa.Column('execution_time_ms', sa.Integer(), nullable=True),
        sa.Column('tokens_used', sa.Integer(), nullable=True),

        # Tracing
        sa.Column('langfuse_span_id', sa.String(length=255), nullable=True),

        # Primary key and constraints
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['research_session_id'], ['research_sessions.id'], ondelete='CASCADE'),
    )

    # Create indexes for research_steps
    op.create_index('ix_research_steps_research_session_id', 'research_steps', ['research_session_id'])

    print("✅ Created research_steps table with indexes")

    # Create research_sources table
    op.create_table(
        'research_sources',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),

        # Core identification
        sa.Column('research_session_id', sa.Integer(), nullable=False),
        sa.Column('research_step_id', sa.Integer(), nullable=True),

        # Source details
        sa.Column('url', sa.String(length=2048), nullable=False),
        sa.Column('title', sa.String(length=1024), nullable=True),
        sa.Column('content_summary', sa.Text(), nullable=True),
        sa.Column('relevance_score', sa.Float(), nullable=True),
        sa.Column('search_query', sa.String(length=1024), nullable=True),

        # Metadata (JSONB)
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=False),

        # Primary key and constraints
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['research_session_id'], ['research_sessions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['research_step_id'], ['research_steps.id'], ondelete='SET NULL'),
    )

    # Create indexes for research_sources
    op.create_index('ix_research_sources_research_session_id', 'research_sources', ['research_session_id'])

    print("✅ Created research_sources table with indexes")
    print("✅ Deep research tables created successfully!")


def downgrade() -> None:
    """Drop research tables."""

    # Drop research_sources table
    op.drop_index('ix_research_sources_research_session_id', 'research_sources')
    op.drop_table('research_sources')
    print("✅ Dropped research_sources table")

    # Drop research_steps table
    op.drop_index('ix_research_steps_research_session_id', 'research_steps')
    op.drop_table('research_steps')
    print("✅ Dropped research_steps table")

    # Drop research_sessions table
    op.drop_index('ix_research_sessions_status', 'research_sessions')
    op.drop_index('ix_research_sessions_campaigner_id', 'research_sessions')
    op.drop_index('ix_research_sessions_thread_id', 'research_sessions')
    op.drop_index('ix_research_sessions_session_id', 'research_sessions')
    op.drop_table('research_sessions')
    print("✅ Dropped research_sessions table")

    print("✅ Deep research tables dropped successfully!")
