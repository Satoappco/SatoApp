"""drop_client_info_table

Revision ID: 4cb05293588c
Revises: fa85c21c1802
Create Date: 2025-10-13 11:21:43.963439

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision = '4cb05293588c'
down_revision = 'fa85c21c1802'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Drop client_info table as it has been merged into customers table"""
    print("🔄 Checking if client_info table exists...")
    
    # Check if the table exists before trying to drop it
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    
    if 'client_info' in inspector.get_table_names():
        print("🔄 Dropping client_info table...")
        op.drop_table('client_info')
        print("✅ Successfully dropped client_info table")
    else:
        print("✅ client_info table does not exist (already dropped)")


def downgrade() -> None:
    """Recreate client_info table (with potential data loss)"""
    print("🔄 Recreating client_info table...")
    
    # Recreate the client_info table structure
    op.create_table('client_info',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('composite_id', sa.String(), nullable=False),
        sa.Column('customer_id', sa.Integer(), nullable=False),
        sa.Column('agency_id', sa.Integer(), nullable=False),
        sa.Column('campaigner_id', sa.Integer(), nullable=False),
        sa.Column('full_name', sa.String(), nullable=False),
        sa.Column('login_email', sa.String(), nullable=False),
        sa.Column('phone', sa.String(), nullable=True),
        sa.Column('address', sa.String(), nullable=True),
        sa.Column('opening_hours', sa.String(), nullable=True),
        sa.Column('narrative_report', sa.Text(), nullable=True),
        sa.Column('website_url', sa.String(), nullable=True),
        sa.Column('facebook_page_url', sa.String(), nullable=True),
        sa.Column('instagram_page_url', sa.String(), nullable=True),
        sa.Column('llm_engine_preference', sa.String(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('composite_id')
    )
    
    print("✅ Successfully recreated client_info table (empty - data lost)")
