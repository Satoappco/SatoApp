"""Update user roles to uppercase

Revision ID: 91efe70a49bb
Revises: b4e58ca1a040
Create Date: 2025-10-19 13:39:25.054588

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision = '91efe70a49bb'
down_revision = 'b4e58ca1a040'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Update existing enum values to uppercase
    op.execute("ALTER TYPE userrole RENAME TO userrole_old")
    op.execute("CREATE TYPE userrole AS ENUM ('OWNER', 'ADMIN', 'CAMPAIGNER', 'VIEWER')")
    
    # Update campaigners table
    op.execute("ALTER TABLE campaigners ALTER COLUMN role TYPE userrole USING role::text::userrole")
    
    # Update invite_tokens table - first remove default, then change type, then add default
    op.execute("ALTER TABLE invite_tokens ALTER COLUMN role DROP DEFAULT")
    op.execute("ALTER TABLE invite_tokens ALTER COLUMN role TYPE userrole USING role::text::userrole")
    op.execute("ALTER TABLE invite_tokens ALTER COLUMN role SET DEFAULT 'CAMPAIGNER'")
    
    # Drop the old enum
    op.execute("DROP TYPE userrole_old")


def downgrade() -> None:
    # Revert to lowercase enum values
    op.execute("ALTER TYPE userrole RENAME TO userrole_old")
    op.execute("CREATE TYPE userrole AS ENUM ('owner', 'admin', 'campaigner', 'viewer')")
    
    # Update all tables that use the userrole enum
    op.execute("ALTER TABLE campaigners ALTER COLUMN role TYPE userrole USING role::text::userrole")
    op.execute("ALTER TABLE invite_tokens ALTER COLUMN role TYPE userrole USING role::text::userrole")
    
    # Drop the old enum
    op.execute("DROP TYPE userrole_old")
