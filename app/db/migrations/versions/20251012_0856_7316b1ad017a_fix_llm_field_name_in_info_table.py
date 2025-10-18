"""fix_llm_field_name_in_info_table

Revision ID: 7316b1ad017a
Revises: c8e4ef2da1b2
Create Date: 2025-10-12 08:56:52.748110

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision = '7316b1ad017a'
down_revision = 'c8e4ef2da1b2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Fix the LLM field name in info_table from llm_chat_context to llm_engine_preference.
    """
    
    print("Renaming llm_chat_context to llm_engine_preference in info_table...")
    
    # Rename the column
    op.alter_column('info_table', 'llm_chat_context', new_column_name='llm_engine_preference')
    
    print("✅ LLM field name updated successfully!")


def downgrade() -> None:
    """
    Revert the LLM field name back to llm_chat_context.
    """
    
    print("Reverting llm_engine_preference back to llm_chat_context in info_table...")
    
    # Rename the column back
    op.alter_column('info_table', 'llm_engine_preference', new_column_name='llm_chat_context')
    
    print("✅ LLM field name reverted successfully!")
