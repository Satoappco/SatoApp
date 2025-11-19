"""add unique constraint to digital_assets

Revision ID: asset001_2025
Revises: trace001_2025
Create Date: 2025-11-18 17:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'asset001_2025'
down_revision: Union[str, None] = 'trace001_2025'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add unique constraint to digital_assets table to prevent duplicate assets.

    Constraint: (customer_id, external_id, asset_type) must be unique.
    This ensures one asset per customer per external platform ID per asset type.
    """
    # First, update any foreign key references from duplicates to the one we're keeping (MIN id)
    op.execute("""
        UPDATE connections c
        SET digital_asset_id = (
            SELECT MIN(id)
            FROM digital_assets da2
            WHERE da2.customer_id = da.customer_id
            AND da2.external_id = da.external_id
            AND da2.asset_type = da.asset_type
        )
        FROM digital_assets da
        WHERE c.digital_asset_id = da.id
        AND da.id NOT IN (
            SELECT MIN(id)
            FROM digital_assets
            GROUP BY customer_id, external_id, asset_type
        )
    """)

    # Now delete any duplicate rows (keep the one with MIN id)
    op.execute("""
        DELETE FROM digital_assets a
        WHERE a.id NOT IN (
            SELECT MIN(id)
            FROM digital_assets
            GROUP BY customer_id, external_id, asset_type
        )
    """)

    # Add the unique constraint
    op.create_unique_constraint(
        'uq_digital_asset_customer_external_type',
        'digital_assets',
        ['customer_id', 'external_id', 'asset_type']
    )


def downgrade() -> None:
    """Remove the unique constraint."""
    op.drop_constraint(
        'uq_digital_asset_customer_external_type',
        'digital_assets',
        type_='unique'
    )
