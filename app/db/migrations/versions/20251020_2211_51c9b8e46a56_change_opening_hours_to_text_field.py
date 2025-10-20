"""change_opening_hours_to_text_field

Revision ID: 51c9b8e46a56
Revises: 25cf09689f2b
Create Date: 2025-10-20 22:11:12.560379

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision = '51c9b8e46a56'
down_revision = '25cf09689f2b'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Change opening_hours field from VARCHAR(255) to TEXT to support free text input.
    This allows LLM to read and understand opening hours in natural language format.
    """
    print("🔄 Changing opening_hours field from VARCHAR(255) to TEXT...")
    
    # Change opening_hours column type from VARCHAR(255) to TEXT
    op.alter_column('customers', 'opening_hours',
                   existing_type=sa.String(255),
                   type_=sa.Text(),
                   existing_nullable=True)
    
    print("✅ Successfully changed opening_hours to TEXT field")


def downgrade() -> None:
    """
    Revert opening_hours field back to VARCHAR(255).
    """
    print("🔄 Reverting opening_hours field back to VARCHAR(255)...")
    
    # Change opening_hours column type back to VARCHAR(255)
    op.alter_column('customers', 'opening_hours',
                   existing_type=sa.Text(),
                   type_=sa.String(255),
                   existing_nullable=True)
    
    print("✅ Successfully reverted opening_hours to VARCHAR(255)")
