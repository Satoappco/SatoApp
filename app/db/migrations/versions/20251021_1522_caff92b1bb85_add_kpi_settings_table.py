"""add_kpi_settings_table

Revision ID: caff92b1bb85
Revises: 4f308021f600
Create Date: 2025-10-21 15:22:40.927974

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel
from datetime import datetime


# revision identifiers, used by Alembic.
revision = 'caff92b1bb85'
down_revision = '4f308021f600'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create kpi_settings table
    op.create_table('kpi_settings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('campaign_objective', sa.String(length=100), nullable=False),
        sa.Column('kpi_name', sa.String(length=255), nullable=False),
        sa.Column('kpi_type', sa.String(length=20), nullable=False),
        sa.Column('direction', sa.String(length=10), nullable=False),
        sa.Column('default_value', sa.Float(), nullable=False),
        sa.Column('unit', sa.String(length=50), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Insert seed data - one row per KPI
    kpi_settings_table = sa.table('kpi_settings',
        sa.column('campaign_objective', sa.String),
        sa.column('kpi_name', sa.String),
        sa.column('kpi_type', sa.String),
        sa.column('direction', sa.String),
        sa.column('default_value', sa.Float),
        sa.column('unit', sa.String),
        sa.column('created_at', sa.DateTime),
        sa.column('updated_at', sa.DateTime)
    )
    
    now = datetime.utcnow()
    
    # Seed data based on the KPI settings table from the image
    # Each row represents ONE KPI
    seed_data = [
        # Sales & Profitability (4 rows)
        {'campaign_objective': 'Sales & Profitability', 'kpi_name': 'CPA (Cost Per Acquisition)', 'kpi_type': 'Primary', 'direction': '<', 'default_value': 133.0, 'unit': '₪', 'created_at': now, 'updated_at': now},
        {'campaign_objective': 'Sales & Profitability', 'kpi_name': 'CVR (Conversion Rate)', 'kpi_type': 'Secondary', 'direction': '>', 'default_value': 3.0, 'unit': '%', 'created_at': now, 'updated_at': now},
        {'campaign_objective': 'Sales & Profitability', 'kpi_name': 'Convval (Conversion Value)', 'kpi_type': 'Secondary', 'direction': '>', 'default_value': 300000.0, 'unit': '₪', 'created_at': now, 'updated_at': now},
        {'campaign_objective': 'Sales & Profitability', 'kpi_name': 'CTR (Click-Through Rate)', 'kpi_type': 'Secondary', 'direction': '>', 'default_value': 4.0, 'unit': '%', 'created_at': now, 'updated_at': now},
        
        # Increasing Traffic (4 rows)
        {'campaign_objective': 'Increasing Traffic', 'kpi_name': 'CPC (Cost Per Click)', 'kpi_type': 'Primary', 'direction': '<', 'default_value': 4.0, 'unit': '₪', 'created_at': now, 'updated_at': now},
        {'campaign_objective': 'Increasing Traffic', 'kpi_name': 'Clicks', 'kpi_type': 'Secondary', 'direction': '>', 'default_value': 5000.0, 'unit': 'Count', 'created_at': now, 'updated_at': now},
        {'campaign_objective': 'Increasing Traffic', 'kpi_name': 'Impressions', 'kpi_type': 'Secondary', 'direction': '>', 'default_value': 125000.0, 'unit': 'Count', 'created_at': now, 'updated_at': now},
        {'campaign_objective': 'Increasing Traffic', 'kpi_name': 'CTR (Click-Through Rate)', 'kpi_type': 'Secondary', 'direction': '>', 'default_value': 4.0, 'unit': '%', 'created_at': now, 'updated_at': now},
        
        # Increasing Awareness (4 rows)
        {'campaign_objective': 'Increasing Awareness', 'kpi_name': 'CPM (Cost Per Mille)', 'kpi_type': 'Primary', 'direction': '<', 'default_value': 30.0, 'unit': '₪', 'created_at': now, 'updated_at': now},
        {'campaign_objective': 'Increasing Awareness', 'kpi_name': 'Impressions', 'kpi_type': 'Secondary', 'direction': '>', 'default_value': 125000.0, 'unit': 'Count', 'created_at': now, 'updated_at': now},
        {'campaign_objective': 'Increasing Awareness', 'kpi_name': 'Reach', 'kpi_type': 'Secondary', 'direction': '>', 'default_value': 41667.0, 'unit': 'Count', 'created_at': now, 'updated_at': now},
        {'campaign_objective': 'Increasing Awareness', 'kpi_name': 'Frequency', 'kpi_type': 'Secondary', 'direction': '<', 'default_value': 2.5, 'unit': 'Count', 'created_at': now, 'updated_at': now},
        
        # Lead Generation (4 rows)
        {'campaign_objective': 'Lead Generation', 'kpi_name': 'CPL (Cost Per Lead)', 'kpi_type': 'Primary', 'direction': '<', 'default_value': 13.3, 'unit': '₪', 'created_at': now, 'updated_at': now},
        {'campaign_objective': 'Lead Generation', 'kpi_name': 'Leads (Total)', 'kpi_type': 'Secondary', 'direction': '<', 'default_value': 1500.0, 'unit': 'Count', 'created_at': now, 'updated_at': now},
        {'campaign_objective': 'Lead Generation', 'kpi_name': 'CVR (Conversion Rate)', 'kpi_type': 'Secondary', 'direction': '<', 'default_value': 20.0, 'unit': '%', 'created_at': now, 'updated_at': now},
        {'campaign_objective': 'Lead Generation', 'kpi_name': 'CTR (Click-Through Rate)', 'kpi_type': 'Secondary', 'direction': '<', 'default_value': 4.0, 'unit': '%', 'created_at': now, 'updated_at': now},
    ]
    
    op.bulk_insert(kpi_settings_table, seed_data)


def downgrade() -> None:
    # Drop the kpi_settings table
    op.drop_table('kpi_settings')
