"""remove_agent_type_use_name_as_identifier

Revision ID: 886ed1524679
Revises: 3dcbe868a648
Create Date: 2025-10-28 14:48:49.618003

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel
import logging


# revision identifiers, used by Alembic.
revision = '886ed1524679'
down_revision = '3dcbe868a648'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add unique constraint on name (dropping agent_type was done manually)
    try:
        op.create_unique_constraint('uq_agent_configs_name', 'agent_configs', ['name'])
    except Exception:
        # Constraint might already exist
        pass


def downgrade() -> None:
    # Add agent_type column back
    op.add_column('agent_configs', sa.Column('agent_type', sa.String(length=50), nullable=True))
    
    # Remove unique constraint
    try:
        op.drop_constraint('uq_agent_configs_name', 'agent_configs', type_='unique')
    except Exception:
        pass
