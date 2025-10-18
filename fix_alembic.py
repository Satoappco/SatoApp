#!/usr/bin/env python3
"""
Fix Alembic state by recreating the alembic_version table
"""

import psycopg2
import os

def main():
    # Database connection
    database_url = "postgresql://postgres:SatoDB_92vN!fG7kAq4hRzLwYx2!PmE@34.165.111.32:5432/sato"
    
    try:
        print("Connecting to database...")
        conn = psycopg2.connect(database_url)
        cur = conn.cursor()
        
        print("Checking current alembic_version table...")
        cur.execute("SELECT * FROM alembic_version")
        result = cur.fetchall()
        print(f"Current contents: {result}")
        
        print("Dropping alembic_version table...")
        cur.execute("DROP TABLE IF EXISTS alembic_version CASCADE")
        
        print("Creating new alembic_version table...")
        cur.execute("""
            CREATE TABLE alembic_version (
                version_num VARCHAR(32) NOT NULL,
                CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
            )
        """)
        
        print("Setting version to remove_only_unused_tables migration...")
        cur.execute("INSERT INTO alembic_version (version_num) VALUES (%s)", ('2201b554a4cc',))
        
        conn.commit()
        print("✅ Successfully fixed alembic_version table")
        
        # Verify
        cur.execute("SELECT version_num FROM alembic_version")
        result = cur.fetchone()
        print(f"Current version: {result[0]}")
        
        cur.close()
        conn.close()
        print("✅ Database connection closed")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
