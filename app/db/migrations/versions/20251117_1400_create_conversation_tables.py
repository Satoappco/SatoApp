"""create_conversation_tables

Revision ID: conv001_2025
Revises: jkl012345678
Create Date: 2025-11-17 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'conv001_2025'
down_revision = 'jkl012345678'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Create conversation tracking tables for chat trace recording.
    This enables persistent storage of chat messages, agent steps, and tool usages
    for both database queries and Langfuse observability.
    """
    print("📋 Creating conversation tracking tables...")

    # ===== Table 1: conversations =====
    print("  Creating 'conversations' table...")
    op.create_table(
        'conversations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('thread_id', sa.String(length=255), nullable=False),
        sa.Column('campaigner_id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.Integer(), nullable=True),

        # Langfuse integration
        sa.Column('langfuse_trace_id', sa.String(length=255), nullable=True),
        sa.Column('langfuse_trace_url', sa.Text(), nullable=True),

        # Conversation metadata
        sa.Column('started_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='active'),

        # Intent/Goal tracking
        sa.Column('intent', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('needs_clarification', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('ready_for_analysis', sa.Boolean(), nullable=False, server_default='false'),

        # Metrics
        sa.Column('message_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('agent_step_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('tool_usage_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('duration_seconds', sa.Numeric(), nullable=True),

        # Extra metadata
        sa.Column('extra_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),

        # Timestamps (BaseModel)
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),

        # Primary key
        sa.PrimaryKeyConstraint('id'),

        # Unique constraint
        sa.UniqueConstraint('thread_id', name='uq_conversations_thread_id'),

        # Foreign keys
        sa.ForeignKeyConstraint(['campaigner_id'], ['campaigners.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ondelete='SET NULL'),
    )

    # Create indexes for conversations
    print("  Creating indexes for 'conversations'...")
    op.create_index('idx_conversations_thread_id', 'conversations', ['thread_id'])
    op.create_index('idx_conversations_campaigner_id', 'conversations', ['campaigner_id'])
    op.create_index('idx_conversations_customer_id', 'conversations', ['customer_id'])
    op.create_index('idx_conversations_status', 'conversations', ['status'])
    op.create_index('idx_conversations_started_at', 'conversations', ['started_at'], postgresql_using='btree', postgresql_ops={'started_at': 'DESC'})

    # ===== Table 2: messages =====
    print("  Creating 'messages' table...")
    op.create_table(
        'messages',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('conversation_id', sa.Integer(), nullable=False),

        # Message content
        sa.Column('role', sa.String(length=50), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),

        # Langfuse integration
        sa.Column('langfuse_generation_id', sa.String(length=255), nullable=True),

        # Message metadata
        sa.Column('model', sa.String(length=100), nullable=True),
        sa.Column('tokens_used', sa.Integer(), nullable=True),
        sa.Column('latency_ms', sa.Integer(), nullable=True),

        # Additional data
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),

        # Timestamps (BaseModel)
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),

        # Primary key
        sa.PrimaryKeyConstraint('id'),

        # Foreign key
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='CASCADE'),
    )

    # Create indexes for messages
    print("  Creating indexes for 'messages'...")
    op.create_index('idx_messages_conversation_id', 'messages', ['conversation_id'])
    op.create_index('idx_messages_created_at', 'messages', ['created_at'], postgresql_using='btree', postgresql_ops={'created_at': 'DESC'})
    op.create_index('idx_messages_role', 'messages', ['role'])

    # ===== Table 3: agent_steps =====
    print("  Creating 'agent_steps' table...")
    op.create_table(
        'agent_steps',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('conversation_id', sa.Integer(), nullable=False),

        # Step details
        sa.Column('step_type', sa.String(length=100), nullable=False),
        sa.Column('agent_name', sa.String(length=255), nullable=True),
        sa.Column('agent_role', sa.String(length=255), nullable=True),
        sa.Column('content', sa.Text(), nullable=False),

        # Task tracking (for CrewAI)
        sa.Column('task_index', sa.Integer(), nullable=True),
        sa.Column('task_description', sa.Text(), nullable=True),

        # Langfuse integration
        sa.Column('langfuse_span_id', sa.String(length=255), nullable=True),

        # Extra metadata
        sa.Column('extra_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),

        # Timestamps (BaseModel)
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),

        # Primary key
        sa.PrimaryKeyConstraint('id'),

        # Foreign key
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='CASCADE'),
    )

    # Create indexes for agent_steps
    print("  Creating indexes for 'agent_steps'...")
    op.create_index('idx_agent_steps_conversation_id', 'agent_steps', ['conversation_id'])
    op.create_index('idx_agent_steps_step_type', 'agent_steps', ['step_type'])
    op.create_index('idx_agent_steps_created_at', 'agent_steps', ['created_at'], postgresql_using='btree', postgresql_ops={'created_at': 'DESC'})

    # ===== Table 4: tool_usages =====
    print("  Creating 'tool_usages' table...")
    op.create_table(
        'tool_usages',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('conversation_id', sa.Integer(), nullable=False),
        sa.Column('agent_step_id', sa.Integer(), nullable=True),

        # Tool details
        sa.Column('tool_name', sa.String(length=255), nullable=False),
        sa.Column('tool_input', sa.Text(), nullable=True),
        sa.Column('tool_output', sa.Text(), nullable=True),
        sa.Column('success', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('error', sa.Text(), nullable=True),

        # Performance
        sa.Column('latency_ms', sa.Integer(), nullable=True),

        # Langfuse integration
        sa.Column('langfuse_span_id', sa.String(length=255), nullable=True),

        # Extra metadata
        sa.Column('extra_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),

        # Timestamps (BaseModel)
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),

        # Primary key
        sa.PrimaryKeyConstraint('id'),

        # Foreign keys
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['agent_step_id'], ['agent_steps.id'], ondelete='SET NULL'),
    )

    # Create indexes for tool_usages
    print("  Creating indexes for 'tool_usages'...")
    op.create_index('idx_tool_usages_conversation_id', 'tool_usages', ['conversation_id'])
    op.create_index('idx_tool_usages_tool_name', 'tool_usages', ['tool_name'])
    op.create_index('idx_tool_usages_success', 'tool_usages', ['success'])
    op.create_index('idx_tool_usages_created_at', 'tool_usages', ['created_at'], postgresql_using='btree', postgresql_ops={'created_at': 'DESC'})

    print("✅ Successfully created all conversation tracking tables with indexes")


def downgrade() -> None:
    """
    Remove conversation tracking tables.
    WARNING: This will lose all conversation history data!
    """
    print("🔄 Dropping conversation tracking tables...")

    # Drop tables in reverse order (due to foreign keys)
    print("  Dropping 'tool_usages' table...")
    op.drop_index('idx_tool_usages_created_at', table_name='tool_usages')
    op.drop_index('idx_tool_usages_success', table_name='tool_usages')
    op.drop_index('idx_tool_usages_tool_name', table_name='tool_usages')
    op.drop_index('idx_tool_usages_conversation_id', table_name='tool_usages')
    op.drop_table('tool_usages')

    print("  Dropping 'agent_steps' table...")
    op.drop_index('idx_agent_steps_created_at', table_name='agent_steps')
    op.drop_index('idx_agent_steps_step_type', table_name='agent_steps')
    op.drop_index('idx_agent_steps_conversation_id', table_name='agent_steps')
    op.drop_table('agent_steps')

    print("  Dropping 'messages' table...")
    op.drop_index('idx_messages_role', table_name='messages')
    op.drop_index('idx_messages_created_at', table_name='messages')
    op.drop_index('idx_messages_conversation_id', table_name='messages')
    op.drop_table('messages')

    print("  Dropping 'conversations' table...")
    op.drop_index('idx_conversations_started_at', table_name='conversations')
    op.drop_index('idx_conversations_status', table_name='conversations')
    op.drop_index('idx_conversations_customer_id', table_name='conversations')
    op.drop_index('idx_conversations_campaigner_id', table_name='conversations')
    op.drop_index('idx_conversations_thread_id', table_name='conversations')
    op.drop_table('conversations')

    print("✅ Successfully dropped all conversation tracking tables")
