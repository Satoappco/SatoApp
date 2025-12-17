"""rename digital_assets to digital_platforms

Revision ID: rename_digital_assets_to_platforms
Revises: update_default_kpi_settings_data
Create Date: 2025-12-15 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'rename_digital_assets_to_platforms'
down_revision = 'update_default_kpi_settings_data'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Rename digital_assets table to digital_platforms and update related columns.
    This reflects the updated terminology where digital_assets refers to traditional
    assets (logos, photos, videos) while digital_platforms refers to connected services.
    """

    # Step 1: Rename the table
    op.rename_table('digital_assets', 'digital_platforms')

    # Step 2: Rename the foreign key column in connections table
    op.alter_column('connections', 'digital_asset_id', new_column_name='digital_platform_id')

    # Step 3: Rename the foreign key column in metrics table
    # The metrics.platform_id already references digital_assets.id, just need to update the FK
    op.execute("""
        ALTER TABLE metrics
        DROP CONSTRAINT IF EXISTS metrics_platform_id_fkey;
    """)

    op.execute("""
        ALTER TABLE metrics
        ADD CONSTRAINT metrics_platform_id_fkey
        FOREIGN KEY (platform_id) REFERENCES digital_platforms(id);
    """)

    # Step 4: Update the unique constraint name
    op.drop_constraint('uq_digital_asset_customer_external_type', 'digital_platforms', type_='unique')
    op.create_unique_constraint(
        'uq_digital_platform_customer_external_type',
        'digital_platforms',
        ['customer_id', 'external_id', 'asset_type']
    )


def downgrade() -> None:
    """
    Revert the rename back to digital_assets.
    """

    # Step 1: Revert the unique constraint name
    op.drop_constraint('uq_digital_platform_customer_external_type', 'digital_platforms', type_='unique')
    op.create_unique_constraint(
        'uq_digital_asset_customer_external_type',
        'digital_platforms',
        ['customer_id', 'external_id', 'asset_type']
    )

    # Step 2: Revert the foreign key column in metrics table
    op.execute("""
        ALTER TABLE metrics
        DROP CONSTRAINT IF EXISTS metrics_platform_id_fkey;
    """)

    op.execute("""
        ALTER TABLE metrics
        ADD CONSTRAINT metrics_platform_id_fkey
        FOREIGN KEY (platform_id) REFERENCES digital_assets(id);
    """)

    # Step 3: Revert the foreign key column in connections table
    op.alter_column('connections', 'digital_platform_id', new_column_name='digital_asset_id')

    # Step 4: Revert the table name
    op.rename_table('digital_platforms', 'digital_assets')
