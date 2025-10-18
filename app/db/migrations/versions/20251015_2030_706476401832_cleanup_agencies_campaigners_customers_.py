"""cleanup_agencies_campaigners_customers_remove_unused_fields

Revision ID: 706476401832
Revises: fd2b710e9329
Create Date: 2025-10-15 20:30:58.719147

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision = '706476401832'
down_revision = 'fd2b710e9329'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Clean up agencies, campaigners, and customers tables by removing unused fields
    and adding missing required fields based on client requirements.
    """
    print("🧹 Cleaning up agencies, campaigners, and customers tables...")
    print("📊 Removing unused fields and adding missing required fields...")
    
    # ===== AGENCIES TABLE CLEANUP =====
    print("🏢 Cleaning up agencies table...")
    
    # Add missing required fields
    try:
        print("➕ Adding email field to agencies...")
        op.add_column('agencies', sa.Column('email', sa.String(255), nullable=True))
        print("✅ Successfully added email field")
    except Exception as e:
        print(f"⚠️  Could not add email field: {e}")
    
    try:
        print("➕ Adding phone field to agencies...")
        op.add_column('agencies', sa.Column('phone', sa.String(50), nullable=True))
        print("✅ Successfully added phone field")
    except Exception as e:
        print(f"⚠️  Could not add phone field: {e}")
    
    # Remove unused fields
    unused_agency_fields = [
        'type', 'plan', 'billing_currency', 'vat_id', 'address',
        'primary_contact_campaigner_id', 'domains', 'tags', 'notes'
    ]
    
    for field in unused_agency_fields:
        try:
            print(f"🗑️  Dropping agencies.{field}...")
            op.drop_column('agencies', field)
            print(f"✅ Successfully dropped agencies.{field}")
        except Exception as e:
            print(f"⚠️  Could not drop agencies.{field}: {e}")
    
    # ===== CAMPAIGNERS TABLE CLEANUP =====
    print("👤 Cleaning up campaigners table...")
    
    # Remove unused fields
    unused_campaigner_fields = [
        'locale', 'timezone', 'google_id', 'avatar_url', 
        'email_verified', 'provider', 'last_login_at', 'selected_customer_id'
    ]
    
    for field in unused_campaigner_fields:
        try:
            print(f"🗑️  Dropping campaigners.{field}...")
            op.drop_column('campaigners', field)
            print(f"✅ Successfully dropped campaigners.{field}")
        except Exception as e:
            print(f"⚠️  Could not drop campaigners.{field}: {e}")
    
    # ===== CUSTOMERS TABLE CLEANUP =====
    print("🏪 Cleaning up customers table...")
    
    # Remove unused fields
    unused_customer_fields = [
        'external_ids', 'login_email', 'opening_hours', 'narrative_report',
        'website_url', 'facebook_page_url', 'instagram_page_url', 'llm_engine_preference'
    ]
    
    for field in unused_customer_fields:
        try:
            print(f"🗑️  Dropping customers.{field}...")
            op.drop_column('customers', field)
            print(f"✅ Successfully dropped customers.{field}")
        except Exception as e:
            print(f"⚠️  Could not drop customers.{field}: {e}")
    
    print("🎉 Agencies, campaigners, and customers cleanup completed!")
    print("📊 Tables now contain only required fields for client needs")


def downgrade() -> None:
    """
    Reverse the cleanup by adding back the removed fields.
    Note: This will add empty fields - data will be lost.
    """
    print("🔄 Reversing agencies, campaigners, and customers cleanup...")
    print("⚠️  WARNING: This will add empty fields - data will be lost!")
    
    # ===== CUSTOMERS TABLE RESTORE =====
    print("🏪 Restoring customers table...")
    customer_fields_to_restore = [
        ('external_ids', sa.JSON()),
        ('login_email', sa.String(255)),
        ('opening_hours', sa.String(255)),
        ('narrative_report', sa.Text()),
        ('website_url', sa.String(500)),
        ('facebook_page_url', sa.String(500)),
        ('instagram_page_url', sa.String(500)),
        ('llm_engine_preference', sa.String(50))
    ]
    
    for field_name, field_type in customer_fields_to_restore:
        try:
            print(f"🔄 Adding back customers.{field_name}...")
            op.add_column('customers', sa.Column(field_name, field_type, nullable=True))
            print(f"✅ Successfully added back customers.{field_name}")
        except Exception as e:
            print(f"⚠️  Could not add back customers.{field_name}: {e}")
    
    # ===== CAMPAIGNERS TABLE RESTORE =====
    print("👤 Restoring campaigners table...")
    campaigner_fields_to_restore = [
        ('locale', sa.String(10)),
        ('timezone', sa.String(50)),
        ('google_id', sa.String(255)),
        ('avatar_url', sa.String(500)),
        ('email_verified', sa.Boolean()),
        ('provider', sa.String(20)),
        ('last_login_at', sa.DateTime()),
        ('selected_customer_id', sa.Integer())
    ]
    
    for field_name, field_type in campaigner_fields_to_restore:
        try:
            print(f"🔄 Adding back campaigners.{field_name}...")
            op.add_column('campaigners', sa.Column(field_name, field_type, nullable=True))
            print(f"✅ Successfully added back campaigners.{field_name}")
        except Exception as e:
            print(f"⚠️  Could not add back campaigners.{field_name}: {e}")
    
    # ===== AGENCIES TABLE RESTORE =====
    print("🏢 Restoring agencies table...")
    agency_fields_to_restore = [
        ('type', sa.String(50)),
        ('plan', sa.String(100)),
        ('billing_currency', sa.String(3)),
        ('vat_id', sa.String(50)),
        ('address', sa.String(500)),
        ('primary_contact_campaigner_id', sa.Integer()),
        ('domains', sa.JSON()),
        ('tags', sa.JSON()),
        ('notes', sa.Text())
    ]
    
    for field_name, field_type in agency_fields_to_restore:
        try:
            print(f"🔄 Adding back agencies.{field_name}...")
            op.add_column('agencies', sa.Column(field_name, field_type, nullable=True))
            print(f"✅ Successfully added back agencies.{field_name}")
        except Exception as e:
            print(f"⚠️  Could not add back agencies.{field_name}: {e}")
    
    # Remove the added required fields
    try:
        print("🗑️  Removing agencies.email...")
        op.drop_column('agencies', 'email')
        print("✅ Successfully removed agencies.email")
    except Exception as e:
        print(f"⚠️  Could not remove agencies.email: {e}")
    
    try:
        print("🗑️  Removing agencies.phone...")
        op.drop_column('agencies', 'phone')
        print("✅ Successfully removed agencies.phone")
    except Exception as e:
        print(f"⚠️  Could not remove agencies.phone: {e}")
    
    print("🔄 Cleanup reversal completed!")
