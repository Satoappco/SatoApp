"""merge_campaign_kpi_and_customer_logs

Revision ID: aea487572365
Revises: 20250129_1200, add_customer_log_tables_20250917_1549
Create Date: 2025-09-27 20:21:26.794833

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision = 'aea487572365'
down_revision = ('20250129_1200', 'add_customer_log_tables_20250917_1549')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
