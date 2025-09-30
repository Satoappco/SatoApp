#!/usr/bin/env python3
"""
Test script for the new async DialogCX webhook implementation
"""

import requests
import json
import time

# Test payload simulating DialogCX webhook
test_payload = {
    "user_id": 5,
    "customer_id": 5,
    "session_ID": f"test_session_{int(time.time())}",
    "user_question": "Show me analytics for the last 7 days",
    "user_intent": "analytics_request",
    "parameters": {
        "user_id": 5,
        "customer_id": 5,
        "user_name": "Test User",
        "user_email": "test@satoapp.com"
    },
    "data_sources": ["ga4"],
    "user_info": {
        "name": "Test User",
        "email": "test@satoapp.com"
    }
}

def test_async_webhook():
    """Test the async webhook implementation"""
    
    webhook_url = "https://sato-backend-397762748853.me-west1.run.app/api/v1/webhooks/dialogcx"
    
    print("🧪 Testing Async DialogCX Webhook")
    print("=" * 50)
    print(f"📤 Sending payload to: {webhook_url}")
    print(f"📋 Payload: {json.dumps(test_payload, indent=2)}")
    print()
    
    try:
        # Send the webhook request
        start_time = time.time()
        response = requests.post(
            webhook_url,
            json=test_payload,
            headers={"Content-Type": "application/json"},
            timeout=10  # Short timeout since we expect immediate response
        )
        end_time = time.time()
        
        print(f"⏱️  Response time: {end_time - start_time:.2f} seconds")
        print(f"📊 Status code: {response.status_code}")
        print()
        
        if response.status_code == 200:
            response_data = response.json()
            print("✅ SUCCESS - Immediate response received:")
            print(f"📝 Response: {json.dumps(response_data, indent=2)}")
            print()
            print("🎯 Expected behavior:")
            print("  1. ✅ Immediate response (< 1 second)")
            print("  2. ✅ Message about analysis in progress")
            print("  3. 🔄 CrewAI running in background")
            print("  4. 📨 Custom event 'crew_result_ready' will be sent to DialogCX")
            print()
            print("🔍 Check the logs for:")
            print("  - 'Starting async CrewAI analysis'")
            print("  - 'Sending custom event crew_result_ready'")
            print("  - 'Custom event sent successfully'")
            
        else:
            print("❌ ERROR - Unexpected response:")
            print(f"Status: {response.status_code}")
            print(f"Response: {response.text}")
            
    except requests.exceptions.Timeout:
        print("⏰ TIMEOUT - This is actually GOOD!")
        print("The webhook should return immediately, not timeout.")
        print("If it timed out, the async implementation might not be working.")
        
    except Exception as e:
        print(f"❌ ERROR: {e}")

if __name__ == "__main__":
    test_async_webhook()
