"""
Migration script to move data from SQLite to PostgreSQL
Run this script after setting up your PostgreSQL database
"""
import os
import json
import sqlite3
from datetime import datetime
from database import db_manager, init_database, WebhookEntry


def migrate_sqlite_to_postgresql():
    """Migrate existing SQLite data to PostgreSQL"""
    
    # Check if SQLite database exists
    sqlite_db_path = os.environ.get("DB_PATH", "data.db")
    if not os.path.exists(sqlite_db_path):
        print("No SQLite database found. Starting fresh with PostgreSQL.")
        return
    
    print(f"Found SQLite database: {sqlite_db_path}")
    print("Starting migration to PostgreSQL...")
    
    # Initialize PostgreSQL database
    init_database()
    
    # Connect to SQLite and read existing data
    sqlite_conn = sqlite3.connect(sqlite_db_path)
    sqlite_cursor = sqlite_conn.cursor()
    
    try:
        # Check if the old table exists
        sqlite_cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='entries'")
        if not sqlite_cursor.fetchone():
            print("No 'entries' table found in SQLite database.")
            return
        
        # Fetch all entries from SQLite
        sqlite_cursor.execute("SELECT user_name, user_choice, raw_payload, created_at FROM entries ORDER BY id")
        sqlite_entries = sqlite_cursor.fetchall()
        
        if not sqlite_entries:
            print("No entries found in SQLite database.")
            return
        
        print(f"Found {len(sqlite_entries)} entries to migrate")
        
        # Migrate each entry to PostgreSQL
        migrated_count = 0
        failed_count = 0
        
        for entry in sqlite_entries:
            user_name, user_choice, raw_payload, created_at = entry
            
            try:
                # Parse the created_at timestamp
                if created_at:
                    # SQLite stores timestamps as strings, try to parse
                    try:
                        created_at_dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    except:
                        created_at_dt = datetime.utcnow()
                else:
                    created_at_dt = datetime.utcnow()
                
                # Create new entry in PostgreSQL
                with db_manager.get_session() as session:
                    new_entry = WebhookEntry(
                        user_name=user_name,
                        user_choice=user_choice,
                        raw_payload=raw_payload or "{}",
                        created_at=created_at_dt
                    )
                    session.add(new_entry)
                    session.commit()
                
                migrated_count += 1
                
            except Exception as e:
                print(f"Failed to migrate entry: {entry[:2]} - Error: {e}")
                failed_count += 1
        
        print(f"\nMigration completed!")
        print(f"Successfully migrated: {migrated_count} entries")
        print(f"Failed migrations: {failed_count} entries")
        
        if migrated_count > 0:
            print(f"\nYou can now safely remove the SQLite database: {sqlite_db_path}")
            print("Or keep it as a backup.")
        
    except Exception as e:
        print(f"Migration failed: {e}")
        raise
    
    finally:
        sqlite_conn.close()


def verify_migration():
    """Verify the migration by checking PostgreSQL data"""
    try:
        entries = db_manager.get_recent_entries(limit=100)
        print(f"\nVerification: Found {len(entries)} entries in PostgreSQL")
        
        if entries:
            print("Sample entries:")
            for i, entry in enumerate(entries[:3]):
                print(f"  {i+1}. ID: {entry.id}, User: {entry.user_name}, Choice: {entry.user_choice}, Time: {entry.created_at}")
        
        return True
    except Exception as e:
        print(f"Verification failed: {e}")
        return False


if __name__ == "__main__":
    print("🚀 Starting SQLite to PostgreSQL migration...")
    print("Make sure you have set the correct PostgreSQL environment variables!")
    print()
    
    # Check if required environment variables are set
    required_vars = ["DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD"]
    missing_vars = [var for var in required_vars if not os.getenv(var) and not os.getenv("DATABASE_URL")]
    
    if missing_vars and not os.getenv("DATABASE_URL"):
        print("❌ Missing required environment variables:")
        for var in missing_vars:
            print(f"   - {var}")
        print("\nPlease set these variables or provide a DATABASE_URL")
        exit(1)
    
    try:
        migrate_sqlite_to_postgresql()
        verify_migration()
        print("\n✅ Migration completed successfully!")
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        exit(1)
