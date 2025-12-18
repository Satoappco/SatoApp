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
    # First, drop the existing foreign key constraint if it exists
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    fk_constraints = inspector.get_foreign_keys('connections')

    # Check if the foreign key constraint exists
    fk_exists = any(fk['constrained_columns'] == ['digital_asset_id'] for fk in fk_constraints)
    if fk_exists:
        op.drop_constraint('connections_digital_asset_id_fkey', 'connections', type_='foreignkey')

    # Rename the table from digital_assets to digital_platforms
    op.rename_table('digital_assets', 'digital_platforms')

    # Rename the column from digital_asset_id to digital_platform_id
    op.alter_column('connections', 'digital_asset_id', new_column_name='digital_platform_id')

    # Create the new foreign key constraint
    op.create_foreign_key(
        'connections_digital_platform_id_fkey',
        'connections',
        'digital_platforms',
        ['digital_platform_id'],
        ['id']
    )

    # Update the unique constraint name
    # Check if the constraint exists before dropping it
    constraints = inspector.get_unique_constraints('digital_platforms')
    old_constraint_exists = any(
        c['name'] == 'uq_digital_asset_customer_external_type'
        for c in constraints
    )
    if old_constraint_exists:
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

    # Drop the foreign key constraint
    op.drop_constraint('connections_digital_platform_id_fkey', 'connections', type_='foreignkey')

    # Rename the column back from digital_platform_id to digital_asset_id
    op.alter_column('connections', 'digital_platform_id', new_column_name='digital_asset_id')

    # Create the old foreign key constraint
    op.create_foreign_key(
        'connections_digital_asset_id_fkey',
        'connections',
        'digital_assets',
        ['digital_asset_id'],
        ['id']
    )

    # Rename the table back from digital_platforms to digital_assets
    op.rename_table('digital_platforms', 'digital_assets')