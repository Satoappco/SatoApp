"""Rename digital_assets to digital_platforms

Revision ID: 20251217_1200
Revises: 2e18477ba827
Create Date: 2025-12-17 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20251217_1200'
down_revision: Union[str, None] = '2e18477ba827'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Rename the table from digital_assets to digital_platforms
    op.rename_table('digital_assets', 'digital_platforms')

    # Update the foreign key in connections table
    op.drop_constraint('connections_digital_platform_id_fkey', 'connections', type_='foreignkey')
    op.create_foreign_key(
        'connections_digital_platform_id_fkey',
        'connections',
        'digital_platforms',
        ['digital_platform_id'],
        ['id']
    )

    # Update the unique constraint name
    op.drop_constraint('uq_digital_asset_customer_external_type', 'digital_platforms', type_='unique')
    op.create_unique_constraint(
        'uq_digital_platform_customer_external_type',
        'digital_platforms',
        ['customer_id', 'external_id', 'asset_type']
    )


def downgrade() -> None:
    # Reverse the changes
    # Update the unique constraint name back
    op.drop_constraint('uq_digital_platform_customer_external_type', 'digital_platforms', type_='unique')
    op.create_unique_constraint(
        'uq_digital_asset_customer_external_type',
        'digital_platforms',
        ['customer_id', 'external_id', 'asset_type']
    )

    # Update the foreign key back
    op.drop_constraint('connections_digital_platform_id_fkey', 'connections', type_='foreignkey')
    op.create_foreign_key(
        'connections_digital_platform_id_fkey',
        'connections',
        'digital_platforms',
        ['digital_platform_id'],
        ['id']
    )

    # Rename the table back from digital_platforms to digital_assets
    op.rename_table('digital_platforms', 'digital_assets')