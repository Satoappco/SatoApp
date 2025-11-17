"""merge_heads

Revision ID: jkl012345678
Revises: app_settings_001, ghi789012345
Create Date: 2025-11-16 16:50:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'jkl012345678'
down_revision = ('app_settings_001', 'ghi789012345')
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Merge migration heads - no changes needed"""
    print("✅ Merged migration heads")
    pass


def downgrade() -> None:
    """Downgrade merge - no changes needed"""
    pass
