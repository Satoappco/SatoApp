#!/usr/bin/env python3
"""
Test the API directly without authentication
"""
import os
import sys
from sqlmodel import create_engine, text, select
from app.models.customer_data import RTMTable, QuestionsTable
from app.models.users import Customer, Campaigner

# Add the app directory to the path
sys.path.append('/Users/amit_ashdot/Desktop/שיעורי בית/לקוחות/eyal/sato-think/SatoApp')

# Database URL
DATABASE_URL = "postgresql://sato_dev_user:SatoDev_92vN!fG7kAq4hRzLwYx2!PmE@34.165.111.32:5432/sato_dev"

def test_api_logic():
    engine = create_engine(DATABASE_URL)
    
    with engine.connect() as conn:
        print("=== TESTING API LOGIC FOR CUSTOMER ID 1 ===")
        
        # Simulate the API logic
        customer_id = 1
        
        # Get customer
        result = conn.execute(text("SELECT * FROM customers WHERE id = :customer_id"), {"customer_id": customer_id})
        customer_row = result.fetchone()
        
        if not customer_row:
            print("❌ Customer not found")
            return
        
        print(f"✅ Found customer: {customer_row[1]} (agency_id: {customer_row[6]})")
        
        # Get RTM data using pattern matching
        result = conn.execute(text("SELECT * FROM rtm_table WHERE composite_id LIKE :pattern"), {"pattern": f"%_{customer_id}"})
        rtm_row = result.fetchone()
        
        if rtm_row:
            print(f"✅ Found RTM data: {rtm_row[1]} with links: {rtm_row[2]}, {rtm_row[3]}")
        else:
            print("❌ No RTM data found")
        
        # Get Questions data using pattern matching
        result = conn.execute(text("SELECT * FROM questions_table WHERE composite_id LIKE :pattern"), {"pattern": f"%_{customer_id}"})
        questions_row = result.fetchone()
        
        if questions_row:
            print(f"✅ Found Questions data: {questions_row[1]} with questions: {questions_row[2]}, {questions_row[3]}")
        else:
            print("❌ No Questions data found")
        
        print("\n=== TESTING API LOGIC FOR CUSTOMER ID 5 ===")
        
        # Test with customer 5
        customer_id = 5
        
        # Get customer
        result = conn.execute(text("SELECT * FROM customers WHERE id = :customer_id"), {"customer_id": customer_id})
        customer_row = result.fetchone()
        
        if not customer_row:
            print("❌ Customer not found")
            return
        
        print(f"✅ Found customer: {customer_row[1]} (agency_id: {customer_row[6]})")
        
        # Get RTM data using pattern matching
        result = conn.execute(text("SELECT * FROM rtm_table WHERE composite_id LIKE :pattern"), {"pattern": f"%_{customer_id}"})
        rtm_row = result.fetchone()
        
        if rtm_row:
            print(f"✅ Found RTM data: {rtm_row[1]} with links: {rtm_row[2]}, {rtm_row[3]}")
        else:
            print("❌ No RTM data found")
        
        # Get Questions data using pattern matching
        result = conn.execute(text("SELECT * FROM questions_table WHERE composite_id LIKE :pattern"), {"pattern": f"%_{customer_id}"})
        questions_row = result.fetchone()
        
        if questions_row:
            print(f"✅ Found Questions data: {questions_row[1]} with questions: {questions_row[2]}, {questions_row[3]}")
        else:
            print("❌ No Questions data found")

if __name__ == "__main__":
    test_api_logic()
