"""restore_customer_fields_from_image_requirements

Revision ID: f1a9e12d482b
Revises: 706476401832
Create Date: 2025-10-15 20:37:21.401911

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision = 'f1a9e12d482b'
down_revision = '706476401832'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Restore customer table fields based on client requirements from image.
    The customer table should have all the fields shown in the Info Table image.
    """
    print("🏪 Restoring customer table fields based on client requirements...")
    print("📊 Adding back all required customer fields from Info Table...")
    
    # Add back all the required customer fields
    customer_fields_to_add = [
        ('login_email', sa.String(255), 'Login email address'),
        ('opening_hours', sa.String(255), 'Business opening hours'),
        ('narrative_report', sa.Text(), 'Narrative report text'),
        ('website_url', sa.String(500), 'Website URL'),
        ('facebook_page_url', sa.String(500), 'Facebook page URL'),
        ('instagram_page_url', sa.String(500), 'Instagram page URL'),
        ('llm_engine_preference', sa.String(50), 'Preferred LLM engine: gemini, openai, claude')
    ]
    
    for field_name, field_type, description in customer_fields_to_add:
        try:
            print(f"➕ Adding customers.{field_name}...")
            op.add_column('customers', sa.Column(field_name, field_type, nullable=True))
            print(f"✅ Successfully added customers.{field_name}")
        except Exception as e:
            print(f"⚠️  Could not add customers.{field_name}: {e}")
    
    print("🎉 Customer table fields restored successfully!")
    print("📊 Customer table now matches Info Table requirements from image")


def downgrade() -> None:
    """
    Remove the restored customer fields.
    """
    print("🔄 Removing restored customer fields...")
    print("⚠️  WARNING: This will remove customer fields - data will be lost!")
    
    # Remove the fields we just added
    fields_to_remove = [
        'login_email', 'opening_hours', 'narrative_report',
        'website_url', 'facebook_page_url', 'instagram_page_url', 'llm_engine_preference'
    ]
    
    for field in fields_to_remove:
        try:
            print(f"🗑️  Removing customers.{field}...")
            op.drop_column('customers', field)
            print(f"✅ Successfully removed customers.{field}")
        except Exception as e:
            print(f"⚠️  Could not remove customers.{field}: {e}")
    
    print("🔄 Customer fields removal completed!")
