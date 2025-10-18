"""add_customer_data_tables_info_rtm_questions

Revision ID: c8e4ef2da1b2
Revises: abdeaa4327f4
Create Date: 2025-10-12 08:54:34.529132

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision = 'c8e4ef2da1b2'
down_revision = 'abdeaa4327f4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Add three customer data tables: info_table, rtm_table, and questions_table.
    
    Each table uses a composite_id (concatenation of Agency ID, Campaigner ID, Customer ID)
    and stores data specific to each sub-customer.
    """
    
    print("Creating info_table...")
    # Create info_table
    op.create_table('info_table',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('composite_id', sa.String(length=100), nullable=False),
        sa.Column('subclient_id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('full_name', sa.String(length=255), nullable=False),
        sa.Column('login_email', sa.String(length=255), nullable=False),
        sa.Column('phone', sa.String(length=50), nullable=True),
        sa.Column('address', sa.String(length=500), nullable=True),
        sa.Column('opening_hours', sa.String(length=255), nullable=True),
        sa.Column('narrative_report', sa.String(), nullable=True),
        sa.Column('website_url', sa.String(length=500), nullable=True),
        sa.Column('facebook_page_url', sa.String(length=500), nullable=True),
        sa.Column('instagram_page_url', sa.String(length=500), nullable=True),
        sa.Column('llm_chat_context', sa.String(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['subclient_id'], ['sub_customers.id'], ),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_info_table_composite_id', 'info_table', ['composite_id'], unique=True)
    print("✅ info_table created!")
    
    print("Creating rtm_table...")
    # Create rtm_table (Real-Time Monitoring links)
    op.create_table('rtm_table',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('composite_id', sa.String(length=100), nullable=False),
        sa.Column('subclient_id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('link_1', sa.String(length=500), nullable=True),
        sa.Column('link_2', sa.String(length=500), nullable=True),
        sa.Column('link_3', sa.String(length=500), nullable=True),
        sa.Column('link_4', sa.String(length=500), nullable=True),
        sa.Column('link_5', sa.String(length=500), nullable=True),
        sa.Column('link_6', sa.String(length=500), nullable=True),
        sa.Column('link_7', sa.String(length=500), nullable=True),
        sa.Column('link_8', sa.String(length=500), nullable=True),
        sa.Column('link_9', sa.String(length=500), nullable=True),
        sa.Column('link_10', sa.String(length=500), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['subclient_id'], ['sub_customers.id'], ),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_rtm_table_composite_id', 'rtm_table', ['composite_id'], unique=False)
    print("✅ rtm_table created!")
    
    print("Creating questions_table...")
    # Create questions_table
    op.create_table('questions_table',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('composite_id', sa.String(length=100), nullable=False),
        sa.Column('subclient_id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('q1', sa.String(length=500), nullable=True),
        sa.Column('q2', sa.String(length=500), nullable=True),
        sa.Column('q3', sa.String(length=500), nullable=True),
        sa.Column('q4', sa.String(length=500), nullable=True),
        sa.Column('q5', sa.String(length=500), nullable=True),
        sa.Column('q6', sa.String(length=500), nullable=True),
        sa.Column('q7', sa.String(length=500), nullable=True),
        sa.Column('q8', sa.String(length=500), nullable=True),
        sa.Column('q9', sa.String(length=500), nullable=True),
        sa.Column('q10', sa.String(length=500), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['subclient_id'], ['sub_customers.id'], ),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_questions_table_composite_id', 'questions_table', ['composite_id'], unique=False)
    print("✅ questions_table created!")
    
    print("✅ All three customer data tables created successfully!")


def downgrade() -> None:
    """
    Remove the three customer data tables.
    """
    
    print("Dropping customer data tables...")
    op.drop_index('ix_questions_table_composite_id', table_name='questions_table')
    op.drop_table('questions_table')
    
    op.drop_index('ix_rtm_table_composite_id', table_name='rtm_table')
    op.drop_table('rtm_table')
    
    op.drop_index('ix_info_table_composite_id', table_name='info_table')
    op.drop_table('info_table')
    
    print("✅ Customer data tables dropped successfully!")
