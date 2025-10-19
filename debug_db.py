#!/usr/bin/env python3
"""
Debug script to check database tables and data
"""
import os
import sys
from sqlmodel import create_engine, text

# Add the app directory to the path
sys.path.append('/Users/amit_ashdot/Desktop/שיעורי בית/לקוחות/eyal/sato-think/SatoApp')

# Database URL
DATABASE_URL = "postgresql://sato_dev_user:SatoDev_92vN!fG7kAq4hRzLwYx2!PmE@34.165.111.32:5432/sato_dev"

def check_database():
    engine = create_engine(DATABASE_URL)
    
    with engine.connect() as conn:
        print("=== CHECKING TABLES ===")
        result = conn.execute(text("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND (table_name LIKE '%rtm%' OR table_name LIKE '%questions%' OR table_name LIKE '%customer%')
            ORDER BY table_name;
        """))
        tables = result.fetchall()
        print("Found tables:", [t[0] for t in tables])
        
        print("\n=== RTM TABLE STRUCTURE ===")
        try:
            result = conn.execute(text("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'rtm_table' ORDER BY ordinal_position;"))
            columns = result.fetchall()
            for col in columns:
                print(f"  {col[0]}: {col[1]}")
        except Exception as e:
            print(f"Error getting rtm_table structure: {e}")
        
        print("\n=== QUESTIONS TABLE STRUCTURE ===")
        try:
            result = conn.execute(text("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'questions_table' ORDER BY ordinal_position;"))
            columns = result.fetchall()
            for col in columns:
                print(f"  {col[0]}: {col[1]}")
        except Exception as e:
            print(f"Error getting questions_table structure: {e}")
        
        print("\n=== RTM TABLE DATA ===")
        try:
            result = conn.execute(text("SELECT * FROM rtm_table LIMIT 5;"))
            rows = result.fetchall()
            if rows:
                for row in rows:
                    print(f"  {row}")
            else:
                print("  No data found in rtm_table")
        except Exception as e:
            print(f"Error getting rtm_table data: {e}")
        
        print("\n=== QUESTIONS TABLE DATA ===")
        try:
            result = conn.execute(text("SELECT * FROM questions_table LIMIT 5;"))
            rows = result.fetchall()
            if rows:
                for row in rows:
                    print(f"  {row}")
            else:
                print("  No data found in questions_table")
        except Exception as e:
            print(f"Error getting questions_table data: {e}")
        
        print("\n=== CUSTOMERS TABLE DATA ===")
        try:
            result = conn.execute(text("SELECT id, full_name, agency_id FROM customers LIMIT 5;"))
            rows = result.fetchall()
            if rows:
                for row in rows:
                    print(f"  ID: {row[0]}, Name: {row[1]}, Agency: {row[2]}")
            else:
                print("  No data found in customers table")
        except Exception as e:
            print(f"Error getting customers data: {e}")

if __name__ == "__main__":
    check_database()
