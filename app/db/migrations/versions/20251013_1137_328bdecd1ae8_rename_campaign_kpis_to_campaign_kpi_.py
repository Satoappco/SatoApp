"""rename_campaign_kpis_to_campaign_kpi_goals_and_add_missing_columns

Revision ID: 328bdecd1ae8
Revises: 4cb05293588c
Create Date: 2025-10-13 11:37:34.927222

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision = '328bdecd1ae8'
down_revision = '4cb05293588c'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Rename campaign_kpis to campaign_kpi_goals and add missing columns"""
    print("🔄 Starting campaign_kpis table transformation...")
    
    # Step 1: Rename the table
    print("📝 Renaming campaign_kpis to campaign_kpi_goals...")
    op.rename_table('campaign_kpis', 'campaign_kpi_goals')
    
    # Step 2: Rename subcustomer_id to customer_id
    print("📝 Renaming subcustomer_id to customer_id...")
    op.alter_column('campaign_kpi_goals', 'subcustomer_id', new_column_name='customer_id')
    
    # Step 3: Add missing columns
    print("📝 Adding missing columns...")
    
    # Campaign status (ACTIVE/PAUSED)
    op.add_column('campaign_kpi_goals', sa.Column('campaign_status', sa.String(50), nullable=True))
    
    # Ad score (numerical score like 99)
    op.add_column('campaign_kpi_goals', sa.Column('ad_score', sa.Integer(), nullable=True))
    
    # Ad Group fields
    op.add_column('campaign_kpi_goals', sa.Column('ad_group_id', sa.Integer(), nullable=True))
    op.add_column('campaign_kpi_goals', sa.Column('ad_group_name', sa.String(255), nullable=True))
    op.add_column('campaign_kpi_goals', sa.Column('ad_group_status', sa.String(50), nullable=True))
    
    # Ad fields
    op.add_column('campaign_kpi_goals', sa.Column('ad_id', sa.Integer(), nullable=True))
    op.add_column('campaign_kpi_goals', sa.Column('ad_name', sa.String(255), nullable=True))
    op.add_column('campaign_kpi_goals', sa.Column('ad_status', sa.String(50), nullable=True))
    op.add_column('campaign_kpi_goals', sa.Column('ad_headline', sa.String(500), nullable=True))
    
    # Step 4: Update existing data with default values
    print("📊 Setting default values for existing records...")
    op.execute("""
        UPDATE campaign_kpi_goals SET 
            campaign_status = 'ACTIVE/PAUSED',
            ad_score = 99,
            ad_group_status = 'ACTIVE/PAUSED',
            ad_status = 'ACTIVE/PAUSED'
        WHERE campaign_status IS NULL
    """)
    
    print("✅ Successfully transformed campaign_kpis to campaign_kpi_goals!")


def downgrade() -> None:
    """Reverse the campaign_kpi_goals transformation"""
    print("🔄 Reversing campaign_kpi_goals transformation...")
    
    # Step 1: Remove added columns
    print("🗑️ Removing added columns...")
    op.drop_column('campaign_kpi_goals', 'ad_headline')
    op.drop_column('campaign_kpi_goals', 'ad_status')
    op.drop_column('campaign_kpi_goals', 'ad_name')
    op.drop_column('campaign_kpi_goals', 'ad_id')
    op.drop_column('campaign_kpi_goals', 'ad_group_status')
    op.drop_column('campaign_kpi_goals', 'ad_group_name')
    op.drop_column('campaign_kpi_goals', 'ad_group_id')
    op.drop_column('campaign_kpi_goals', 'ad_score')
    op.drop_column('campaign_kpi_goals', 'campaign_status')
    
    # Step 2: Rename customer_id back to subcustomer_id
    print("📝 Renaming customer_id back to subcustomer_id...")
    op.alter_column('campaign_kpi_goals', 'customer_id', new_column_name='subcustomer_id')
    
    # Step 3: Rename table back
    print("📝 Renaming campaign_kpi_goals back to campaign_kpis...")
    op.rename_table('campaign_kpi_goals', 'campaign_kpis')
    
    print("✅ Successfully reversed campaign_kpi_goals transformation!")
