"""remove_is_active_from_questions_and_rtm_tables

Revision ID: 0bd2156f83dd
Revises: 2748cb7d19bc
Create Date: 2025-10-15 21:21:50.377006

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision = '0bd2156f83dd'
down_revision = '2748cb7d19bc'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Remove is_active columns from questions_table and rtm_table.
    These fields are not used in the application logic and add unnecessary complexity.
    """
    print("🧹 Removing unused is_active columns from questions and RTM tables...")
    print("📊 These fields are not used in frontend or backend logic...")
    
    # Remove is_active from questions_table
    try:
        print("🗑️  Dropping is_active from questions_table...")
        op.drop_column('questions_table', 'is_active')
        print("✅ Successfully dropped is_active from questions_table")
    except Exception as e:
        print(f"⚠️  Could not drop is_active from questions_table: {e}")
    
    # Remove is_active from rtm_table
    try:
        print("🗑️  Dropping is_active from rtm_table...")
        op.drop_column('rtm_table', 'is_active')
        print("✅ Successfully dropped is_active from rtm_table")
    except Exception as e:
        print(f"⚠️  Could not drop is_active from rtm_table: {e}")
    
    print("🎉 Cleanup completed!")
    print("📊 Tables are now focused on their core purpose without unused fields")


def downgrade() -> None:
    """
    Add back is_active columns to questions_table and rtm_table.
    """
    print("🔄 Adding back is_active columns...")
    print("⚠️  WARNING: This will add empty columns - data will be lost!")
    
    # Add is_active back to questions_table
    try:
        print("➕ Adding is_active to questions_table...")
        op.add_column('questions_table', sa.Column('is_active', sa.Boolean(), nullable=True, default=True))
        print("✅ Successfully added is_active to questions_table")
    except Exception as e:
        print(f"⚠️  Could not add is_active to questions_table: {e}")
    
    # Add is_active back to rtm_table
    try:
        print("➕ Adding is_active to rtm_table...")
        op.add_column('rtm_table', sa.Column('is_active', sa.Boolean(), nullable=True, default=True))
        print("✅ Successfully added is_active to rtm_table")
    except Exception as e:
        print(f"⚠️  Could not add is_active to rtm_table: {e}")
    
    print("🔄 is_active columns restored!")
