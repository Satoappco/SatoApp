#!/usr/bin/env python3
"""
Check actual database tables
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor

def check_database_tables():
    """Check what tables actually exist in the database"""
    
    # Try different database URLs
    database_urls = [
        os.getenv('DATABASE_URL'),
        'postgresql://postgres:password@localhost:5432/sato_dev',
        'postgresql://postgres:password@127.0.0.1:5432/sato_dev',
    ]
    
    for db_url in database_urls:
        if not db_url:
            continue
            
        print(f"🔍 Trying database URL: {db_url}")
        print("=" * 80)
        
        try:
            # Connect to database
            conn = psycopg2.connect(db_url)
            cur = conn.cursor(cursor_factory=RealDictCursor)
            
            # Get all tables
            cur.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                ORDER BY table_name;
            """)
            
            tables = [row['table_name'] for row in cur.fetchall()]
            
            print(f"✅ Connected successfully! Found {len(tables)} tables:")
            print()
            
            for table in tables:
                print(f"  - {table}")
            
            print()
            print("🔍 Checking table structures...")
            print("=" * 80)
            
            # Check structure of key tables
            key_tables = ['campaigners', 'agencies', 'customers', 'users', 'sub_customers']
            
            for table_name in key_tables:
                if table_name in tables:
                    print(f"\n📋 Table: {table_name}")
                    cur.execute(f"""
                        SELECT column_name, data_type, is_nullable, column_default
                        FROM information_schema.columns 
                        WHERE table_name = '{table_name}' 
                        ORDER BY ordinal_position;
                    """)
                    
                    columns = cur.fetchall()
                    for col in columns:
                        nullable = "NULL" if col['is_nullable'] == 'YES' else "NOT NULL"
                        default = f" DEFAULT {col['column_default']}" if col['column_default'] else ""
                        print(f"    {col['column_name']}: {col['data_type']} {nullable}{default}")
            
            cur.close()
            conn.close()
            
            print("\n✅ Database check completed successfully!")
            return tables
            
        except Exception as e:
            print(f"❌ Error connecting to {db_url}: {e}")
            continue
    
    print("❌ Could not connect to any database")
    return []

if __name__ == "__main__":
    print("Database Tables Check")
    print("=" * 80)
    print()
    
    tables = check_database_tables()
    
    if tables:
        print(f"\n📊 Summary: Found {len(tables)} tables in database")
        print("Tables:", ", ".join(tables))
