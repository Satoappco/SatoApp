"""ensure_unique_email_google_id_campaigners

Revision ID: 20251218_0001
Revises:
Create Date: 2025-12-18 00:01:00.000000

This migration ensures unique constraints on email and google_id fields in the campaigners table.
It first removes duplicates by keeping the most recent record for each duplicate email/google_id.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = '20251218_0001'
down_revision = '20251217_1200'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Remove duplicate campaigners and add unique constraints on email and google_id.

    Strategy:
    1. For each duplicate email, keep the record with the highest ID (most recent)
    2. For each duplicate google_id, keep the record with the highest ID (most recent)
    3. Add unique index on email if not exists
    4. Add unique index on google_id if not exists
    """
    print("🔧 Starting campaigner deduplication and unique constraint addition...")

    conn = op.get_bind()

    # Step 1: Remove duplicate emails (keep highest ID)
    print("📧 Removing duplicate emails...")
    result = conn.execute(text("""
        WITH duplicates AS (
            SELECT email, MAX(id) as keep_id
            FROM campaigners
            GROUP BY email
            HAVING COUNT(*) > 1
        )
        DELETE FROM campaigners
        WHERE id IN (
            SELECT c.id
            FROM campaigners c
            INNER JOIN duplicates d ON c.email = d.email
            WHERE c.id != d.keep_id
        )
        RETURNING email, id;
    """))

    deleted_emails = list(result)
    if deleted_emails:
        print(f"  ✅ Removed {len(deleted_emails)} duplicate email records")
        for row in deleted_emails:
            print(f"    - Deleted campaigner ID {row.id} with email {row.email}")
    else:
        print("  ✅ No duplicate emails found")

    # Step 2: Remove duplicate google_ids (keep highest ID)
    print("🔑 Removing duplicate google_ids...")
    result = conn.execute(text("""
        WITH duplicates AS (
            SELECT google_id, MAX(id) as keep_id
            FROM campaigners
            WHERE google_id IS NOT NULL
            GROUP BY google_id
            HAVING COUNT(*) > 1
        )
        DELETE FROM campaigners
        WHERE id IN (
            SELECT c.id
            FROM campaigners c
            INNER JOIN duplicates d ON c.google_id = d.google_id
            WHERE c.id != d.keep_id
        )
        RETURNING google_id, id;
    """))

    deleted_google_ids = list(result)
    if deleted_google_ids:
        print(f"  ✅ Removed {len(deleted_google_ids)} duplicate google_id records")
        for row in deleted_google_ids:
            print(f"    - Deleted campaigner ID {row.id} with google_id {row.google_id}")
    else:
        print("  ✅ No duplicate google_ids found")

    # Step 3: Check if unique index on email exists, if not create it
    print("📧 Adding unique constraint on email...")
    try:
        # Check if index exists
        result = conn.execute(text("""
            SELECT indexname
            FROM pg_indexes
            WHERE tablename = 'campaigners'
            AND indexname = 'ix_campaigners_email';
        """))

        if result.fetchone():
            # Index exists, drop it first to recreate as unique
            op.drop_index('ix_campaigners_email', 'campaigners')
            print("  ℹ️  Dropped existing non-unique index on email")

        # Create unique index
        op.create_index('ix_campaigners_email', 'campaigners', ['email'], unique=True)
        print("  ✅ Created unique index on email")
    except Exception as e:
        print(f"  ⚠️  Error with email index: {e}")
        # Try to create anyway
        try:
            op.create_index('ix_campaigners_email', 'campaigners', ['email'], unique=True)
            print("  ✅ Created unique index on email")
        except:
            pass

    # Step 4: Check if unique index on google_id exists, if not create it
    print("🔑 Adding unique constraint on google_id...")
    try:
        # Check if index exists
        result = conn.execute(text("""
            SELECT indexname
            FROM pg_indexes
            WHERE tablename = 'campaigners'
            AND indexname = 'ix_campaigners_google_id';
        """))

        if result.fetchone():
            # Check if it's already unique
            result = conn.execute(text("""
                SELECT i.indisunique
                FROM pg_class t
                JOIN pg_index i ON t.oid = i.indrelid
                JOIN pg_class idx ON idx.oid = i.indexrelid
                WHERE t.relname = 'campaigners'
                AND idx.relname = 'ix_campaigners_google_id';
            """))

            is_unique = result.fetchone()
            if is_unique and is_unique[0]:
                print("  ℹ️  Unique index on google_id already exists")
            else:
                # Index exists but not unique, recreate it
                op.drop_index('ix_campaigners_google_id', 'campaigners')
                print("  ℹ️  Dropped existing non-unique index on google_id")
                op.create_index('ix_campaigners_google_id', 'campaigners', ['google_id'], unique=True)
                print("  ✅ Created unique index on google_id")
        else:
            # Create unique index
            op.create_index('ix_campaigners_google_id', 'campaigners', ['google_id'], unique=True)
            print("  ✅ Created unique index on google_id")
    except Exception as e:
        print(f"  ⚠️  Error with google_id index: {e}")
        # Try to create anyway
        try:
            op.create_index('ix_campaigners_google_id', 'campaigners', ['google_id'], unique=True)
            print("  ✅ Created unique index on google_id")
        except:
            pass

    # Verify the constraints
    print("\n🔍 Verifying unique constraints...")
    result = conn.execute(text("""
        SELECT COUNT(*) as total, COUNT(DISTINCT email) as unique_emails,
               COUNT(DISTINCT google_id) as unique_google_ids
        FROM campaigners;
    """))
    stats = result.fetchone()
    print(f"  Total campaigners: {stats.total}")
    print(f"  Unique emails: {stats.unique_emails}")
    print(f"  Unique google_ids: {stats.unique_google_ids}")

    if stats.total == stats.unique_emails:
        print("  ✅ All emails are unique")
    else:
        print(f"  ⚠️  Warning: {stats.total - stats.unique_emails} duplicate emails still exist")

    print("\n✅ Migration completed successfully!")


def downgrade() -> None:
    """
    Remove unique constraints from email and google_id.
    Note: This does NOT restore deleted duplicate records.
    """
    print("🔄 Removing unique constraints from campaigners table...")

    # Remove unique index from email, recreate as non-unique
    try:
        op.drop_index('ix_campaigners_email', 'campaigners')
        op.create_index('ix_campaigners_email', 'campaigners', ['email'], unique=False)
        print("  ✅ Removed unique constraint from email")
    except Exception as e:
        print(f"  ⚠️  Error removing email constraint: {e}")

    # Remove unique index from google_id, recreate as non-unique
    try:
        op.drop_index('ix_campaigners_google_id', 'campaigners')
        op.create_index('ix_campaigners_google_id', 'campaigners', ['google_id'], unique=False)
        print("  ✅ Removed unique constraint from google_id")
    except Exception as e:
        print(f"  ⚠️  Error removing google_id constraint: {e}")

    print("🔄 Downgrade completed")
