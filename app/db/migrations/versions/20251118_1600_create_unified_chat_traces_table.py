"""create_unified_chat_traces_table

Revision ID: trace001_2025
Revises: conv001_2025
Create Date: 2025-11-18 16:00:00.000000

Consolidates conversations, messages, agent_steps, and tool_usages
into a single chat_traces table with JSON data field.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'trace001_2025'
down_revision = 'conv001_2025'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Create unified chat_traces table and drop old separate tables.
    """
    print("📋 Creating unified chat_traces table...")

    # Create chat_traces table
    op.create_table(
        'chat_traces',
        sa.Column('id', sa.Integer(), nullable=False),

        # Core identification
        sa.Column('thread_id', sa.String(length=255), nullable=False),
        sa.Column('record_type', sa.String(length=50), nullable=False),

        # Ownership
        sa.Column('campaigner_id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.Integer(), nullable=True),

        # Type-specific data as JSONB
        sa.Column('data', postgresql.JSONB(astext_type=sa.Text()), nullable=False),

        # Langfuse integration
        sa.Column('langfuse_trace_id', sa.String(length=255), nullable=True),
        sa.Column('langfuse_trace_url', sa.Text(), nullable=True),
        sa.Column('langfuse_span_id', sa.String(length=255), nullable=True),

        # Session tracking
        sa.Column('session_id', sa.String(length=255), nullable=True),

        # Ordering
        sa.Column('sequence_number', sa.Integer(), nullable=True),

        # Timestamps (BaseModel)
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),

        # Primary key
        sa.PrimaryKeyConstraint('id'),

        # Foreign keys
        sa.ForeignKeyConstraint(['campaigner_id'], ['campaigners.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ondelete='SET NULL'),
    )

    # Create indexes
    print("  Creating indexes for 'chat_traces'...")
    op.create_index('idx_chat_traces_thread_id', 'chat_traces', ['thread_id'])
    op.create_index('idx_chat_traces_record_type', 'chat_traces', ['record_type'])
    op.create_index('idx_chat_traces_campaigner_id', 'chat_traces', ['campaigner_id'])
    op.create_index('idx_chat_traces_customer_id', 'chat_traces', ['customer_id'])
    op.create_index('idx_chat_traces_session_id', 'chat_traces', ['session_id'])
    op.create_index('idx_chat_traces_created_at', 'chat_traces', ['created_at'], postgresql_using='btree', postgresql_ops={'created_at': 'DESC'})
    op.create_index('idx_chat_traces_thread_record', 'chat_traces', ['thread_id', 'record_type'])

    # GIN index for JSONB data field (allows efficient querying of JSON fields)
    op.create_index('idx_chat_traces_data_gin', 'chat_traces', ['data'], postgresql_using='gin')

    print("✅ Created unified chat_traces table with indexes")

    # Drop old tables (in reverse order due to foreign keys)
    print("🗑️  Dropping old conversation tables...")

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

    print("✅ Successfully dropped old conversation tables")
    print("✅ Migration complete: All chat data now in single unified table")


def downgrade() -> None:
    """
    Recreate separate tables and drop chat_traces table.
    WARNING: This will lose all conversation history data!
    """
    print("🔄 Rolling back to separate conversation tables...")

    # Drop chat_traces table
    print("  Dropping 'chat_traces' table...")
    op.drop_index('idx_chat_traces_data_gin', table_name='chat_traces')
    op.drop_index('idx_chat_traces_thread_record', table_name='chat_traces')
    op.drop_index('idx_chat_traces_created_at', table_name='chat_traces')
    op.drop_index('idx_chat_traces_session_id', table_name='chat_traces')
    op.drop_index('idx_chat_traces_customer_id', table_name='chat_traces')
    op.drop_index('idx_chat_traces_campaigner_id', table_name='chat_traces')
    op.drop_index('idx_chat_traces_record_type', table_name='chat_traces')
    op.drop_index('idx_chat_traces_thread_id', table_name='chat_traces')
    op.drop_table('chat_traces')

    # Recreate old tables (same as previous migration)
    print("  Recreating 'conversations' table...")
    op.create_table(
        'conversations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('thread_id', sa.String(length=255), nullable=False),
        sa.Column('campaigner_id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.Integer(), nullable=True),
        sa.Column('langfuse_trace_id', sa.String(length=255), nullable=True),
        sa.Column('langfuse_trace_url', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='active'),
        sa.Column('intent', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('needs_clarification', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('ready_for_analysis', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('message_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('agent_step_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('tool_usage_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('duration_seconds', sa.Numeric(), nullable=True),
        sa.Column('extra_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('thread_id', name='uq_conversations_thread_id'),
        sa.ForeignKeyConstraint(['campaigner_id'], ['campaigners.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ondelete='SET NULL'),
    )
    op.create_index('idx_conversations_thread_id', 'conversations', ['thread_id'])
    op.create_index('idx_conversations_campaigner_id', 'conversations', ['campaigner_id'])
    op.create_index('idx_conversations_customer_id', 'conversations', ['customer_id'])
    op.create_index('idx_conversations_status', 'conversations', ['status'])
    op.create_index('idx_conversations_started_at', 'conversations', ['started_at'])

    print("  Recreating 'messages' table...")
    op.create_table(
        'messages',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('conversation_id', sa.Integer(), nullable=False),
        sa.Column('role', sa.String(length=50), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('langfuse_generation_id', sa.String(length=255), nullable=True),
        sa.Column('model', sa.String(length=100), nullable=True),
        sa.Column('tokens_used', sa.Integer(), nullable=True),
        sa.Column('latency_ms', sa.Integer(), nullable=True),
        sa.Column('extra_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='CASCADE'),
    )
    op.create_index('idx_messages_conversation_id', 'messages', ['conversation_id'])
    op.create_index('idx_messages_created_at', 'messages', ['created_at'])
    op.create_index('idx_messages_role', 'messages', ['role'])

    print("  Recreating 'agent_steps' table...")
    op.create_table(
        'agent_steps',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('conversation_id', sa.Integer(), nullable=False),
        sa.Column('step_type', sa.String(length=100), nullable=False),
        sa.Column('agent_name', sa.String(length=255), nullable=True),
        sa.Column('agent_role', sa.String(length=255), nullable=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('task_index', sa.Integer(), nullable=True),
        sa.Column('task_description', sa.Text(), nullable=True),
        sa.Column('langfuse_span_id', sa.String(length=255), nullable=True),
        sa.Column('extra_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='CASCADE'),
    )
    op.create_index('idx_agent_steps_conversation_id', 'agent_steps', ['conversation_id'])
    op.create_index('idx_agent_steps_step_type', 'agent_steps', ['step_type'])
    op.create_index('idx_agent_steps_created_at', 'agent_steps', ['created_at'])

    print("  Recreating 'tool_usages' table...")
    op.create_table(
        'tool_usages',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('conversation_id', sa.Integer(), nullable=False),
        sa.Column('agent_step_id', sa.Integer(), nullable=True),
        sa.Column('tool_name', sa.String(length=255), nullable=False),
        sa.Column('tool_input', sa.Text(), nullable=True),
        sa.Column('tool_output', sa.Text(), nullable=True),
        sa.Column('success', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('latency_ms', sa.Integer(), nullable=True),
        sa.Column('langfuse_span_id', sa.String(length=255), nullable=True),
        sa.Column('extra_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['agent_step_id'], ['agent_steps.id'], ondelete='SET NULL'),
    )
    op.create_index('idx_tool_usages_conversation_id', 'tool_usages', ['conversation_id'])
    op.create_index('idx_tool_usages_tool_name', 'tool_usages', ['tool_name'])
    op.create_index('idx_tool_usages_success', 'tool_usages', ['success'])
    op.create_index('idx_tool_usages_created_at', 'tool_usages', ['created_at'])

    print("✅ Successfully recreated separate conversation tables")
