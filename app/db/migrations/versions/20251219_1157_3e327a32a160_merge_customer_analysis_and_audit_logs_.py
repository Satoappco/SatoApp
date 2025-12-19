"""merge customer analysis and audit logs branches

Revision ID: 3e327a32a160
Revises: 20251215_audit_logs, 20251219_0001
Create Date: 2025-12-19 11:57:35.015075

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision = '3e327a32a160'
down_revision = ('20251215_audit_logs', '20251219_0001')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
