#!/usr/bin/env python3
"""
Test script to verify the API integration works correctly
This tests the FastAPI server with the actual Sato crew
"""
import os
import requests
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_fastapi_server():
    """Test the FastAPI server endpoints"""
    base_url = "http://localhost:8000"  # Default FastAPI port
    
    print("🧪 Testing FastAPI Server Integration")
    print("=" * 50)
    
    # Test 1: Health check
    print("1. Testing health check...")
    try:
        response = requests.get(f"{base_url}/")
        if response.status_code == 200:
            print("✅ Health check passed")
            print(f"   Response: {response.json()}")
        else:
            print(f"❌ Health check failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Health check failed: {e}")
    
    print()
    
    # Test 2: Crew endpoint with simple topic
    print("2. Testing crew endpoint...")
    try:
        payload = {
            "topic": "AI testing",
            "current_year": "2025"
        }
        
        response = requests.post(
            f"{base_url}/crew/simple", 
            json=payload,
            timeout=120  # Crew execution can take time
        )
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Crew execution successful")
            print(f"   Topic: {payload['topic']}")
            print(f"   Result length: {len(result.get('result', ''))}")
            print(f"   Result preview: {result.get('result', '')[:200]}...")
        else:
            print(f"❌ Crew execution failed: {response.status_code}")
            print(f"   Error: {response.text}")
            
    except Exception as e:
        print(f"❌ Crew execution failed: {e}")
    
    print()

def test_webhook_server():
    """Test the Flask webhook server endpoints"""
    base_url = "http://localhost:8080"  # Default Flask port
    headers = {"Authorization": "Bearer SatoLogos"}
    
    print("🧪 Testing Webhook Server Integration")
    print("=" * 50)
    
    # Test 1: Health check
    print("1. Testing webhook health check...")
    try:
        response = requests.get(f"{base_url}/health", headers=headers)
        if response.status_code == 200:
            print("✅ Webhook health check passed")
            print(f"   Response: {response.json()}")
        else:
            print(f"❌ Webhook health check failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Webhook health check failed: {e}")
    
    print()
    
    # Test 2: Webhook + Crew trigger
    print("2. Testing webhook crew trigger...")
    try:
        payload = {
            "user_name": "Test User",
            "user_choice": "API Test",
            "topic": "Testing integration"
        }
        
        response = requests.post(
            f"{base_url}/webhook/trigger-crew", 
            json=payload,
            headers=headers,
            timeout=120
        )
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Webhook crew trigger successful")
            print(f"   Entry ID: {result.get('entry_id')}")
            print(f"   Topic: {result.get('topic')}")
            print(f"   Crew result preview: {result.get('crew_result', '')[:200]}...")
        else:
            print(f"❌ Webhook crew trigger failed: {response.status_code}")
            print(f"   Error: {response.text}")
            
    except Exception as e:
        print(f"❌ Webhook crew trigger failed: {e}")

def run_local_server_test():
    """Test the crew directly without server"""
    print("🧪 Testing Direct Crew Integration")
    print("=" * 50)
    
    try:
        from src.sato.crew import Sato
        from datetime import datetime
        
        print("1. Importing Sato crew...")
        sato_crew = Sato()
        print("✅ Sato crew imported successfully")
        
        print("2. Running crew with test inputs...")
        inputs = {
            'topic': 'API Integration Test',
            'current_year': str(datetime.now().year)
        }
        
        result = sato_crew.crew().kickoff(inputs=inputs)
        
        print("✅ Crew execution successful")
        print(f"   Result type: {type(result)}")
        print(f"   Result length: {len(str(result))}")
        print(f"   Result preview: {str(result)[:200]}...")
        
        return True
        
    except Exception as e:
        print(f"❌ Direct crew test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("🚀 Sato API Integration Test Suite")
    print("=" * 60)
    
    # Check environment
    print(f"OpenAI API Key set: {'Yes' if os.getenv('OPENAI_API_KEY') and os.getenv('OPENAI_API_KEY') != 'your_openai_api_key_here' else 'No'}")
    print(f"Database configured: {'Yes' if os.getenv('DB_HOST') else 'No'}")
    print()
    
    # Test 1: Direct crew (no server)
    success = run_local_server_test()
    
    if success:
        print("\n" + "=" * 60)
        print("🎉 Direct crew integration works!")
        print("You can now:")
        print("1. Start FastAPI server: uvicorn server:app --host 0.0.0.0 --port 8000")
        print("2. Start Flask webhook: python webhook_server.py")
        print("3. Deploy to Google Cloud Run")
    else:
        print("\n" + "=" * 60)
        print("❌ Fix the direct crew integration first before testing servers")
        
    print("\n" + "=" * 60)
    print("📚 For deployment instructions, see API_DOCUMENTATION.md")

if __name__ == "__main__":
    main()
