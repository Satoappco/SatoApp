"""rename_login_email_to_contact_email

Revision ID: 56c054b308db
Revises: 8d7caaf94b4b
Create Date: 2025-10-19 12:02:50.797517

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision = '56c054b308db'
down_revision = '8d7caaf94b4b'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Rename login_email column to contact_email in customers table
    op.alter_column('customers', 'login_email', new_column_name='contact_email')


def downgrade() -> None:
    # Rename contact_email column back to login_email in customers table
    op.alter_column('customers', 'contact_email', new_column_name='login_email')
