"""add_campaign_kpi_table

Revision ID: 20250129_1200
Revises: 20250918_122
Create Date: 2025-01-29 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20250129_1200'
down_revision = '20250918_122'
branch_labels = None
depends_on = None


def upgrade():
    # Create campaign_kpis table
    op.create_table('campaign_kpis',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.Column('subcustomer_id', sa.Integer(), nullable=False),
    sa.Column('date', sa.DateTime(), nullable=False),
    sa.Column('campaign_num', sa.Integer(), nullable=False),
    sa.Column('campaign_id', sa.String(length=50), nullable=False),
    sa.Column('advertising_channel', sa.String(length=100), nullable=False),
    sa.Column('campaign_name', sa.String(length=255), nullable=False),
    sa.Column('campaign_objective', sa.String(length=100), nullable=False),
    sa.Column('daily_budget', sa.Float(), nullable=True),
    sa.Column('weekly_budget', sa.Float(), nullable=True),
    sa.Column('target_audience', sa.String(length=255), nullable=False),
    sa.Column('primary_kpi_1', sa.String(length=255), nullable=True),
    sa.Column('secondary_kpi_1', sa.String(length=255), nullable=True),
    sa.Column('secondary_kpi_2', sa.String(length=255), nullable=True),
    sa.Column('secondary_kpi_3', sa.String(length=255), nullable=True),
    sa.Column('landing_page', sa.String(length=500), nullable=True),
    sa.Column('summary_text', sa.Text(), nullable=True),
    sa.Column('actual_primary_kpi_1', sa.Float(), nullable=True),
    sa.Column('actual_secondary_kpi_1', sa.Float(), nullable=True),
    sa.Column('actual_secondary_kpi_2', sa.Float(), nullable=True),
    sa.Column('actual_secondary_kpi_3', sa.Float(), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['subcustomer_id'], ['sub_customers.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_campaign_kpis_subcustomer_id'), 'campaign_kpis', ['subcustomer_id'], unique=False)
    op.create_index(op.f('ix_campaign_kpis_date'), 'campaign_kpis', ['date'], unique=False)
    op.create_index(op.f('ix_campaign_kpis_campaign_id'), 'campaign_kpis', ['campaign_id'], unique=False)


def downgrade():
    # Drop campaign_kpis table
    op.drop_index(op.f('ix_campaign_kpis_campaign_id'), table_name='campaign_kpis')
    op.drop_index(op.f('ix_campaign_kpis_date'), table_name='campaign_kpis')
    op.drop_index(op.f('ix_campaign_kpis_subcustomer_id'), table_name='campaign_kpis')
    op.drop_table('campaign_kpis')
