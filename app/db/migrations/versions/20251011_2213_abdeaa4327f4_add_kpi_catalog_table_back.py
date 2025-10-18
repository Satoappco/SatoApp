"""add_kpi_catalog_table_back

Revision ID: abdeaa4327f4
Revises: 2201b554a4cc
Create Date: 2025-10-11 22:13:00.174916

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision = 'abdeaa4327f4'
down_revision = '2201b554a4cc'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Add kpi_catalog table back to the database.
    
    This table stores standardized KPI definitions for different sub-customer types.
    """
    
    print("Creating kpi_catalog table...")
    
    # Create kpi_catalog table
    op.create_table('kpi_catalog',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('subtype', sa.String(length=50), nullable=False),
        sa.Column('primary_metric', sa.String(length=100), nullable=False),
        sa.Column('primary_submetrics', sa.String(), nullable=False),
        sa.Column('secondary_metric', sa.String(length=100), nullable=False),
        sa.Column('secondary_submetrics', sa.String(), nullable=False),
        sa.Column('lite_primary_metric', sa.String(length=100), nullable=False),
        sa.Column('lite_primary_submetrics', sa.String(), nullable=False),
        sa.Column('lite_secondary_metric', sa.String(length=100), nullable=False),
        sa.Column('lite_secondary_submetrics', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    print("✅ kpi_catalog table created successfully!")


def downgrade() -> None:
    """
    Remove kpi_catalog table from the database.
    """
    
    print("Dropping kpi_catalog table...")
    op.drop_table('kpi_catalog')
    print("✅ kpi_catalog table dropped successfully!")
