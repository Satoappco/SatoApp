"""Add customer analysis tables for comprehensive customer profiling and work plan management

Revision ID: 20251219_0001
Revises: 20251218_1400
Create Date: 2025-12-19

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '20251219_0001'
down_revision = '20251218_1400'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create customer analysis tables including sessions, work plans, tasks, reviews, and settings."""

    # Create customer_analysis_sessions table
    op.create_table(
        'customer_analysis_sessions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),

        # Core identification
        sa.Column('session_id', sa.String(length=255), nullable=False),
        sa.Column('campaigner_id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.Integer(), nullable=True),

        # Analysis metadata
        sa.Column('analysis_type', sa.String(length=50), nullable=False),
        sa.Column('trigger_source', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),

        # Scheduling and automation
        sa.Column('next_quarterly_analysis_at', sa.DateTime(), nullable=True),
        sa.Column('next_weekly_review_at', sa.DateTime(), nullable=True),

        # Phase results (JSONB)
        sa.Column('client_brief_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('website_analysis_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('market_research_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('campaign_analysis_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('recommendations_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('work_plan_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),

        # Full report
        sa.Column('full_report_markdown', sa.Text(), nullable=True),

        # Comparison and progress tracking
        sa.Column('previous_session_id', sa.String(length=255), nullable=True),
        sa.Column('progress_since_last_analysis', postgresql.JSONB(astext_type=sa.Text()), nullable=True),

        # Execution metrics
        sa.Column('total_execution_time_ms', sa.Integer(), nullable=True),
        sa.Column('tokens_used', sa.Integer(), nullable=True),
        sa.Column('api_calls_made', sa.Integer(), nullable=True),

        # Tracing
        sa.Column('langfuse_trace_id', sa.String(length=255), nullable=True),
        sa.Column('langfuse_trace_url', sa.String(length=512), nullable=True),

        # Completion timestamp
        sa.Column('completed_at', sa.DateTime(), nullable=True),

        # Primary key and constraints
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['campaigner_id'], ['campaigners.id'], ),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ),
        sa.UniqueConstraint('session_id'),
    )

    # Create indexes for customer_analysis_sessions
    op.create_index('ix_customer_analysis_sessions_session_id', 'customer_analysis_sessions', ['session_id'])
    op.create_index('ix_customer_analysis_sessions_campaigner_id', 'customer_analysis_sessions', ['campaigner_id'])
    op.create_index('ix_customer_analysis_sessions_customer_id', 'customer_analysis_sessions', ['customer_id'])
    op.create_index('ix_customer_analysis_sessions_status', 'customer_analysis_sessions', ['status'])
    op.create_index('idx_analysis_session_campaigner_status', 'customer_analysis_sessions', ['campaigner_id', 'status'])

    print("✅ Created customer_analysis_sessions table with indexes")

    # Create work_plans table
    op.create_table(
        'work_plans',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),

        # Core identification
        sa.Column('plan_id', sa.String(length=255), nullable=False),
        sa.Column('analysis_session_id', sa.Integer(), nullable=False),
        sa.Column('campaigner_id', sa.Integer(), nullable=False),

        # Plan metadata
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('plan_period_weeks', sa.Integer(), nullable=False),
        sa.Column('current_week', sa.Integer(), nullable=False),

        # Progress tracking
        sa.Column('total_tasks', sa.Integer(), nullable=False),
        sa.Column('completed_tasks', sa.Integer(), nullable=False),
        sa.Column('blocked_tasks', sa.Integer(), nullable=False),
        sa.Column('in_progress_tasks', sa.Integer(), nullable=False),
        sa.Column('progress_percent', sa.Float(), nullable=False),

        # Health scoring
        sa.Column('overall_health_score', sa.Float(), nullable=True),

        # Archive timestamp
        sa.Column('archived_at', sa.DateTime(), nullable=True),

        # Primary key and constraints
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['analysis_session_id'], ['customer_analysis_sessions.id'], ),
        sa.ForeignKeyConstraint(['campaigner_id'], ['campaigners.id'], ),
        sa.UniqueConstraint('plan_id'),
    )

    # Create indexes for work_plans
    op.create_index('ix_work_plans_plan_id', 'work_plans', ['plan_id'])
    op.create_index('ix_work_plans_analysis_session_id', 'work_plans', ['analysis_session_id'])
    op.create_index('ix_work_plans_campaigner_id', 'work_plans', ['campaigner_id'])
    op.create_index('idx_work_plan_campaigner_status', 'work_plans', ['campaigner_id', 'status'])

    print("✅ Created work_plans table with indexes")

    # Create work_plan_tasks table
    op.create_table(
        'work_plan_tasks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),

        # Core identification
        sa.Column('task_id', sa.String(length=255), nullable=False),
        sa.Column('work_plan_id', sa.Integer(), nullable=False),

        # Task organization
        sa.Column('week_number', sa.Integer(), nullable=False),
        sa.Column('category', sa.String(length=100), nullable=False),

        # Task details
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),

        # Priority and impact
        sa.Column('priority', sa.String(length=20), nullable=False),
        sa.Column('impact', sa.String(length=20), nullable=False),
        sa.Column('effort', sa.String(length=20), nullable=False),

        # Status tracking
        sa.Column('status', sa.String(length=50), nullable=False),

        # Dependencies and relationships (JSONB)
        sa.Column('dependencies', postgresql.JSONB(astext_type=sa.Text()), nullable=False),

        # Progress notes (JSONB)
        sa.Column('review_notes', postgresql.JSONB(astext_type=sa.Text()), nullable=False),

        # Metrics
        sa.Column('expected_impact_description', sa.Text(), nullable=True),
        sa.Column('actual_impact_notes', sa.Text(), nullable=True),

        # Timestamps
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),

        # Primary key and constraints
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['work_plan_id'], ['work_plans.id'], ),
        sa.UniqueConstraint('task_id'),
    )

    # Create indexes for work_plan_tasks
    op.create_index('ix_work_plan_tasks_task_id', 'work_plan_tasks', ['task_id'])
    op.create_index('ix_work_plan_tasks_work_plan_id', 'work_plan_tasks', ['work_plan_id'])
    op.create_index('ix_work_plan_tasks_week_number', 'work_plan_tasks', ['week_number'])
    op.create_index('ix_work_plan_tasks_status', 'work_plan_tasks', ['status'])
    op.create_index('idx_work_plan_task_status_week', 'work_plan_tasks', ['status', 'week_number'])

    print("✅ Created work_plan_tasks table with indexes")

    # Create weekly_reviews table
    op.create_table(
        'weekly_reviews',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),

        # Core identification
        sa.Column('review_id', sa.String(length=255), nullable=False),
        sa.Column('analysis_session_id', sa.Integer(), nullable=False),
        sa.Column('work_plan_id', sa.Integer(), nullable=False),
        sa.Column('campaigner_id', sa.Integer(), nullable=False),

        # Review metadata
        sa.Column('week_number', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),

        # Metrics snapshot (JSONB)
        sa.Column('metrics_snapshot', postgresql.JSONB(astext_type=sa.Text()), nullable=False),

        # Review content (JSONB arrays)
        sa.Column('achievements', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('blockers', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('risks', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('opportunities', postgresql.JSONB(astext_type=sa.Text()), nullable=False),

        # Recommendations (JSONB arrays)
        sa.Column('new_recommendations', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('task_adjustments', postgresql.JSONB(astext_type=sa.Text()), nullable=False),

        # Health scoring
        sa.Column('overall_health_score', sa.Float(), nullable=False),
        sa.Column('progress_velocity', sa.Float(), nullable=True),

        # Full review report
        sa.Column('full_review_markdown', sa.Text(), nullable=True),

        # Execution metrics
        sa.Column('execution_time_ms', sa.Integer(), nullable=True),
        sa.Column('langfuse_span_id', sa.String(length=255), nullable=True),

        # Timestamps
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('acknowledged_at', sa.DateTime(), nullable=True),

        # Primary key and constraints
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['analysis_session_id'], ['customer_analysis_sessions.id'], ),
        sa.ForeignKeyConstraint(['work_plan_id'], ['work_plans.id'], ),
        sa.ForeignKeyConstraint(['campaigner_id'], ['campaigners.id'], ),
        sa.UniqueConstraint('review_id'),
    )

    # Create indexes for weekly_reviews
    op.create_index('ix_weekly_reviews_review_id', 'weekly_reviews', ['review_id'])
    op.create_index('ix_weekly_reviews_analysis_session_id', 'weekly_reviews', ['analysis_session_id'])
    op.create_index('ix_weekly_reviews_work_plan_id', 'weekly_reviews', ['work_plan_id'])
    op.create_index('ix_weekly_reviews_campaigner_id', 'weekly_reviews', ['campaigner_id'])
    op.create_index('ix_weekly_reviews_week_number', 'weekly_reviews', ['week_number'])
    op.create_index('idx_weekly_review_campaigner_week', 'weekly_reviews', ['campaigner_id', 'week_number'])

    print("✅ Created weekly_reviews table with indexes")

    # Create analysis_settings table
    op.create_table(
        'analysis_settings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),

        # Core identification
        sa.Column('campaigner_id', sa.Integer(), nullable=False),

        # Automation flags
        sa.Column('auto_analysis_on_create', sa.Boolean(), nullable=False),
        sa.Column('auto_weekly_reviews', sa.Boolean(), nullable=False),
        sa.Column('auto_quarterly_reanalysis', sa.Boolean(), nullable=False),

        # Notification preferences (JSONB)
        sa.Column('notification_emails', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('notify_on_analysis_complete', sa.Boolean(), nullable=False),
        sa.Column('notify_on_weekly_review', sa.Boolean(), nullable=False),
        sa.Column('notify_on_quarterly_reanalysis', sa.Boolean(), nullable=False),

        # Scheduling preferences
        sa.Column('weekly_review_day', sa.String(length=20), nullable=False),
        sa.Column('weekly_review_time', sa.String(length=10), nullable=False),

        # LLM configuration preferences
        sa.Column('preferred_analysis_model', sa.String(length=100), nullable=True),
        sa.Column('preferred_summarization_model', sa.String(length=100), nullable=True),

        # Research depth preferences
        sa.Column('default_research_depth', sa.String(length=20), nullable=False),

        # Primary key and constraints
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['campaigner_id'], ['campaigners.id'], ),
        sa.UniqueConstraint('campaigner_id'),
    )

    # Create indexes for analysis_settings
    op.create_index('ix_analysis_settings_campaigner_id', 'analysis_settings', ['campaigner_id'])

    print("✅ Created analysis_settings table with indexes")

    # Create analysis_phase_results table
    op.create_table(
        'analysis_phase_results',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),

        # Core identification
        sa.Column('analysis_session_id', sa.Integer(), nullable=False),

        # Phase metadata
        sa.Column('phase_name', sa.String(length=100), nullable=False),
        sa.Column('phase_index', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),

        # Phase data (JSONB)
        sa.Column('input_data', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('output_data', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),

        # Execution metrics
        sa.Column('execution_time_ms', sa.Integer(), nullable=True),
        sa.Column('tokens_used', sa.Integer(), nullable=True),
        sa.Column('langfuse_span_id', sa.String(length=255), nullable=True),

        # Timestamps
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),

        # Primary key and constraints
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['analysis_session_id'], ['customer_analysis_sessions.id'], ),
    )

    # Create indexes for analysis_phase_results
    op.create_index('ix_analysis_phase_results_analysis_session_id', 'analysis_phase_results', ['analysis_session_id'])
    op.create_index('ix_analysis_phase_results_phase_name', 'analysis_phase_results', ['phase_name'])

    print("✅ Created analysis_phase_results table with indexes")

    # Create analysis_sources table
    op.create_table(
        'analysis_sources',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),

        # Core identification
        sa.Column('analysis_session_id', sa.Integer(), nullable=False),
        sa.Column('phase_result_id', sa.Integer(), nullable=True),

        # Source details
        sa.Column('source_type', sa.String(length=50), nullable=False),
        sa.Column('url', sa.String(length=1024), nullable=True),
        sa.Column('title', sa.String(length=512), nullable=True),
        sa.Column('content_summary', sa.Text(), nullable=True),

        # Relevance and source metadata
        sa.Column('relevance_score', sa.Float(), nullable=True),
        sa.Column('search_query', sa.String(length=512), nullable=True),
        sa.Column('source_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=False),

        # Primary key and constraints
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['analysis_session_id'], ['customer_analysis_sessions.id'], ),
        sa.ForeignKeyConstraint(['phase_result_id'], ['analysis_phase_results.id'], ),
    )

    # Create indexes for analysis_sources
    op.create_index('ix_analysis_sources_analysis_session_id', 'analysis_sources', ['analysis_session_id'])

    print("✅ Created analysis_sources table with indexes")

    # Create analysis_comparisons table
    op.create_table(
        'analysis_comparisons',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),

        # Core identification
        sa.Column('current_session_id', sa.Integer(), nullable=False),
        sa.Column('previous_session_id', sa.Integer(), nullable=False),
        sa.Column('campaigner_id', sa.Integer(), nullable=False),

        # Comparison metadata
        sa.Column('comparison_type', sa.String(length=50), nullable=False),

        # Comparison results (JSONB)
        sa.Column('changes_detected', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('progress_metrics', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('improvement_areas', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('regression_areas', postgresql.JSONB(astext_type=sa.Text()), nullable=False),

        # Summary
        sa.Column('overall_progress_score', sa.Float(), nullable=True),
        sa.Column('comparison_summary_markdown', sa.Text(), nullable=True),

        # Primary key and constraints
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['current_session_id'], ['customer_analysis_sessions.id'], ),
        sa.ForeignKeyConstraint(['previous_session_id'], ['customer_analysis_sessions.id'], ),
        sa.ForeignKeyConstraint(['campaigner_id'], ['campaigners.id'], ),
    )

    # Create indexes for analysis_comparisons
    op.create_index('ix_analysis_comparisons_current_session_id', 'analysis_comparisons', ['current_session_id'])
    op.create_index('ix_analysis_comparisons_campaigner_id', 'analysis_comparisons', ['campaigner_id'])

    print("✅ Created analysis_comparisons table with indexes")
    print("✅ Customer analysis tables created successfully!")


def downgrade() -> None:
    """Drop customer analysis tables."""

    # Drop analysis_comparisons table
    op.drop_index('ix_analysis_comparisons_campaigner_id', 'analysis_comparisons')
    op.drop_index('ix_analysis_comparisons_current_session_id', 'analysis_comparisons')
    op.drop_table('analysis_comparisons')
    print("✅ Dropped analysis_comparisons table")

    # Drop analysis_sources table
    op.drop_index('ix_analysis_sources_analysis_session_id', 'analysis_sources')
    op.drop_table('analysis_sources')
    print("✅ Dropped analysis_sources table")

    # Drop analysis_phase_results table
    op.drop_index('ix_analysis_phase_results_phase_name', 'analysis_phase_results')
    op.drop_index('ix_analysis_phase_results_analysis_session_id', 'analysis_phase_results')
    op.drop_table('analysis_phase_results')
    print("✅ Dropped analysis_phase_results table")

    # Drop analysis_settings table
    op.drop_index('ix_analysis_settings_campaigner_id', 'analysis_settings')
    op.drop_table('analysis_settings')
    print("✅ Dropped analysis_settings table")

    # Drop weekly_reviews table
    op.drop_index('idx_weekly_review_campaigner_week', 'weekly_reviews')
    op.drop_index('ix_weekly_reviews_week_number', 'weekly_reviews')
    op.drop_index('ix_weekly_reviews_campaigner_id', 'weekly_reviews')
    op.drop_index('ix_weekly_reviews_work_plan_id', 'weekly_reviews')
    op.drop_index('ix_weekly_reviews_analysis_session_id', 'weekly_reviews')
    op.drop_index('ix_weekly_reviews_review_id', 'weekly_reviews')
    op.drop_table('weekly_reviews')
    print("✅ Dropped weekly_reviews table")

    # Drop work_plan_tasks table
    op.drop_index('idx_work_plan_task_status_week', 'work_plan_tasks')
    op.drop_index('ix_work_plan_tasks_status', 'work_plan_tasks')
    op.drop_index('ix_work_plan_tasks_week_number', 'work_plan_tasks')
    op.drop_index('ix_work_plan_tasks_work_plan_id', 'work_plan_tasks')
    op.drop_index('ix_work_plan_tasks_task_id', 'work_plan_tasks')
    op.drop_table('work_plan_tasks')
    print("✅ Dropped work_plan_tasks table")

    # Drop work_plans table
    op.drop_index('idx_work_plan_campaigner_status', 'work_plans')
    op.drop_index('ix_work_plans_campaigner_id', 'work_plans')
    op.drop_index('ix_work_plans_analysis_session_id', 'work_plans')
    op.drop_index('ix_work_plans_plan_id', 'work_plans')
    op.drop_table('work_plans')
    print("✅ Dropped work_plans table")

    # Drop customer_analysis_sessions table
    op.drop_index('idx_analysis_session_campaigner_status', 'customer_analysis_sessions')
    op.drop_index('ix_customer_analysis_sessions_status', 'customer_analysis_sessions')
    op.drop_index('ix_customer_analysis_sessions_customer_id', 'customer_analysis_sessions')
    op.drop_index('ix_customer_analysis_sessions_campaigner_id', 'customer_analysis_sessions')
    op.drop_index('ix_customer_analysis_sessions_session_id', 'customer_analysis_sessions')
    op.drop_table('customer_analysis_sessions')
    print("✅ Dropped customer_analysis_sessions table")

    print("✅ Customer analysis tables dropped successfully!")
