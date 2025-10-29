#!/usr/bin/env python3
"""
Test the pattern matching logic
"""
import os
import sys
from sqlmodel import create_engine, text

# Add the app directory to the path
sys.path.append('/Users/amit_ashdot/Desktop/שיעורי בית/לקוחות/eyal/sato-think/SatoApp')

# Database URL
DATABASE_URL = "postgresql://sato_dev_user:SatoDev_92vN!fG7kAq4hRzLwYx2!PmE@34.165.111.32:5432/sato_dev"

def test_patterns():
    engine = create_engine(DATABASE_URL)
    
    with engine.connect() as conn:
        print("=== TESTING PATTERNS FOR CUSTOMER ID 1 ===")
        
        # Test the pattern I'm using
        result = conn.execute(text("SELECT * FROM questions_table WHERE composite_id LIKE '%_1'"))
        rows = result.fetchall()
        print(f"Pattern '%_1' found {len(rows)} rows:")
        for row in rows:
            print(f"  {row}")
        
        # Test exact match
        result = conn.execute(text("SELECT * FROM questions_table WHERE composite_id = '5_5_1'"))
        rows = result.fetchall()
        print(f"\nExact match '5_5_1' found {len(rows)} rows:")
        for row in rows:
            print(f"  {row}")
        
        print("\n=== TESTING PATTERNS FOR CUSTOMER ID 5 ===")
        
        # Test the pattern I'm using
        result = conn.execute(text("SELECT * FROM rtm_table WHERE composite_id LIKE '%_5'"))
        rows = result.fetchall()
        print(f"Pattern '%_5' found {len(rows)} rows:")
        for row in rows:
            print(f"  {row}")

if __name__ == "__main__":
    test_patterns()
