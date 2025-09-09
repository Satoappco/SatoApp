#!/usr/bin/env python3
"""
Test script to verify PostgreSQL database connection
Run this before deploying to ensure your database configuration is correct
"""
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def test_database_connection():
    """Test the database connection"""
    print("🔍 Testing database connection...")
    print(f"DB_HOST: {os.getenv('DB_HOST', 'NOT SET')}")
    print(f"DB_PORT: {os.getenv('DB_PORT', 'NOT SET')}")
    print(f"DB_NAME: {os.getenv('DB_NAME', 'NOT SET')}")
    print(f"DB_USER: {os.getenv('DB_USER', 'NOT SET')}")
    print(f"GOOGLE_CLOUD_SQL: {os.getenv('GOOGLE_CLOUD_SQL', 'NOT SET')}")
    print()
    
    try:
        from database import db_manager, init_database
        
        print("📊 Initializing database...")
        init_database()
        print("✅ Database tables created successfully!")
        
        print("🔗 Testing database connection...")
        with db_manager.get_session() as session:
            # Test basic query
            result = session.execute("SELECT 1 as test").fetchone()
            print(f"✅ Database connection successful! Test query result: {result}")
        
        print("📝 Testing webhook entry creation...")
        test_entry = db_manager.save_webhook_entry(
            user_name="test_user",
            user_choice="test_choice", 
            raw_payload='{"test": "data"}'
        )
        print(f"✅ Test entry created with ID: {test_entry.id}")
        
        print("📋 Testing recent entries retrieval...")
        recent_entries = db_manager.get_recent_entries(limit=5)
        print(f"✅ Found {len(recent_entries)} recent entries")
        
        print("\n🎉 All database tests passed! Ready for deployment.")
        return True
        
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        print("\n🔧 Troubleshooting tips:")
        print("1. Check your .env file has correct values")
        print("2. Verify your Google Cloud SQL instance is running")
        print("3. Ensure your IP is whitelisted (if using public IP)")
        print("4. Check your database credentials are correct")
        return False

if __name__ == "__main__":
    print("🚀 Sato Database Connection Test")
    print("=" * 40)
    
    success = test_database_connection()
    
    if success:
        print("\n✅ Ready to deploy to Google Cloud Run!")
    else:
        print("\n❌ Fix database issues before deploying.")
        exit(1)
