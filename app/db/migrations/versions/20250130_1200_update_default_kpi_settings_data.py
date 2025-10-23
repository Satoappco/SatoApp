"""update_default_kpi_settings_data

Revision ID: update_default_kpi_settings_data
Revises: f2af16b64a54
Create Date: 2025-01-30 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime


# revision identifiers, used by Alembic.
revision = 'update_default_kpi_settings_data'
down_revision = 'f2af16b64a54'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Clear existing default KPI settings data
    op.execute("DELETE FROM default_kpi_settings")
    
    # Insert updated data matching the image
    default_kpi_settings_table = sa.table('default_kpi_settings',
        sa.column('campaign_objective', sa.String),
        sa.column('kpi_name', sa.String),
        sa.column('kpi_type', sa.String),
        sa.column('direction', sa.String),
        sa.column('default_value', sa.Float),
        sa.column('unit', sa.String),
        sa.column('is_active', sa.Boolean),
        sa.column('display_order', sa.Integer),
        sa.column('created_at', sa.DateTime),
        sa.column('updated_at', sa.DateTime)
    )
    
    now = datetime.utcnow()
    
    # Updated seed data matching the image exactly
    seed_data = [
        # Sales & Profitability KPIs
        {'campaign_objective': 'Sales & Profitability', 'kpi_name': 'CPA (Cost Per Acquisition)', 'kpi_type': 'Primary', 'direction': '<', 'default_value': 133.0, 'unit': 'ש"ח', 'is_active': True, 'display_order': 1},
        {'campaign_objective': 'Sales & Profitability', 'kpi_name': 'CVR (Conversion Rate)', 'kpi_type': 'Secondary', 'direction': '>', 'default_value': 3.0, 'unit': '%', 'is_active': True, 'display_order': 2},
        {'campaign_objective': 'Sales & Profitability', 'kpi_name': 'Conv.val (Conversion Value)', 'kpi_type': 'Secondary', 'direction': '>', 'default_value': 300000.0, 'unit': 'ש"ח', 'is_active': True, 'display_order': 3},
        {'campaign_objective': 'Sales & Profitability', 'kpi_name': 'CTR (Click-Through Rate)', 'kpi_type': 'Secondary', 'direction': '>', 'default_value': 4.0, 'unit': '%', 'is_active': True, 'display_order': 4},
        
        # Increasing Traffic KPIs
        {'campaign_objective': 'Increasing Traffic', 'kpi_name': 'CPC (Cost Per Click)', 'kpi_type': 'Primary', 'direction': '<', 'default_value': 4.0, 'unit': 'ש"ח', 'is_active': True, 'display_order': 10},
        {'campaign_objective': 'Increasing Traffic', 'kpi_name': 'Clicks', 'kpi_type': 'Secondary', 'direction': '>', 'default_value': 5000.0, 'unit': 'Count', 'is_active': True, 'display_order': 11},
        {'campaign_objective': 'Increasing Traffic', 'kpi_name': 'Impressions', 'kpi_type': 'Secondary', 'direction': '>', 'default_value': 125000.0, 'unit': 'Count', 'is_active': True, 'display_order': 12},
        {'campaign_objective': 'Increasing Traffic', 'kpi_name': 'CTR (Click-Through Rate)', 'kpi_type': 'Secondary', 'direction': '>', 'default_value': 4.0, 'unit': '%', 'is_active': True, 'display_order': 13},
        
        # Increasing Awareness KPIs
        {'campaign_objective': 'Increasing Awareness', 'kpi_name': 'CPM (Cost Per Mille)', 'kpi_type': 'Primary', 'direction': '<', 'default_value': 30.0, 'unit': 'ש"ח', 'is_active': True, 'display_order': 20},
        {'campaign_objective': 'Increasing Awareness', 'kpi_name': 'Impressions', 'kpi_type': 'Secondary', 'direction': '>', 'default_value': 125000.0, 'unit': 'Count', 'is_active': True, 'display_order': 21},
        {'campaign_objective': 'Increasing Awareness', 'kpi_name': 'Reach', 'kpi_type': 'Secondary', 'direction': '>', 'default_value': 41667.0, 'unit': 'Count', 'is_active': True, 'display_order': 22},
        {'campaign_objective': 'Increasing Awareness', 'kpi_name': 'Frequency', 'kpi_type': 'Secondary', 'direction': '<', 'default_value': 2.5, 'unit': 'Count', 'is_active': True, 'display_order': 23},
        
        # Lead Generation KPIs
        {'campaign_objective': 'Lead Generation', 'kpi_name': 'CPL (Cost Per Lead)', 'kpi_type': 'Primary', 'direction': '<', 'default_value': 13.3, 'unit': 'ש"ח', 'is_active': True, 'display_order': 30},
        {'campaign_objective': 'Lead Generation', 'kpi_name': 'Leads (Total)', 'kpi_type': 'Secondary', 'direction': '<', 'default_value': 1500.0, 'unit': 'Count', 'is_active': True, 'display_order': 31},
        {'campaign_objective': 'Lead Generation', 'kpi_name': 'CVR (Conversion Rate)', 'kpi_type': 'Secondary', 'direction': '<', 'default_value': 20.0, 'unit': '%', 'is_active': True, 'display_order': 32},
        {'campaign_objective': 'Lead Generation', 'kpi_name': 'CTR (Click-Through Rate)', 'kpi_type': 'Secondary', 'direction': '<', 'default_value': 4.0, 'unit': '%', 'is_active': True, 'display_order': 33},
    ]
    
    # Insert all updated seed data
    for data in seed_data:
        op.bulk_insert(default_kpi_settings_table, [{
            'campaign_objective': data['campaign_objective'],
            'kpi_name': data['kpi_name'],
            'kpi_type': data['kpi_type'],
            'direction': data['direction'],
            'default_value': data['default_value'],
            'unit': data['unit'],
            'is_active': data['is_active'],
            'display_order': data['display_order'],
            'created_at': now,
            'updated_at': now
        }])


def downgrade() -> None:
    # Restore the old data (if needed)
    pass
