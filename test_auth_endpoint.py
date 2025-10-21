#!/usr/bin/env python3
"""
Test authentication endpoint to verify existing users can still login
"""

import requests
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get backend URL
BACKEND_URL = "https://localhost:8000"
print(f"Testing backend at: {BACKEND_URL}")

# Test data - using a mock Google token for testing
test_data = {
    "google_token": "mock_token_for_testing",
    "user_info": {
        "email": "sivanliv@gmail.com",  # Existing user from database
        "name": "Sivan Liv",
        "picture": "https://example.com/avatar.jpg"
    }
}

print(f"\n🧪 Testing authentication for existing user: {test_data['user_info']['email']}")

try:
    # Disable SSL verification for local development
    response = requests.post(
        f"{BACKEND_URL}/api/v1/auth/google",
        json=test_data,
        verify=False,
        timeout=10
    )
    
    print(f"Response status: {response.status_code}")
    
    if response.status_code == 200:
        print("✅ SUCCESS: Existing user can still login!")
        data = response.json()
        print(f"   User ID: {data['user']['id']}")
        print(f"   Email: {data['user']['email']}")
        print(f"   Role: {data['user']['role']}")
        print(f"   Agency ID: {data['user']['agency_id']}")
    elif response.status_code == 403:
        print("❌ ERROR: Existing user was blocked!")
        print(f"   Error: {response.text}")
    else:
        print(f"⚠️ Unexpected status: {response.status_code}")
        print(f"   Response: {response.text}")
        
except requests.exceptions.RequestException as e:
    print(f"❌ Request failed: {e}")

# Test with a non-existing user
print(f"\n🧪 Testing authentication for NEW user (should be blocked):")

new_user_data = {
    "google_token": "mock_token_for_testing",
    "user_info": {
        "email": "newuser@example.com",  # Non-existing user
        "name": "New User",
        "picture": "https://example.com/avatar.jpg"
    }
}

try:
    response = requests.post(
        f"{BACKEND_URL}/api/v1/auth/google",
        json=new_user_data,
        verify=False,
        timeout=10
    )
    
    print(f"Response status: {response.status_code}")
    
    if response.status_code == 403:
        print("✅ SUCCESS: New user was correctly blocked!")
        print(f"   Error message: {response.json().get('detail', 'No detail')}")
    elif response.status_code == 200:
        print("❌ ERROR: New user was allowed to sign up!")
        print(f"   This should not happen!")
    else:
        print(f"⚠️ Unexpected status: {response.status_code}")
        print(f"   Response: {response.text}")
        
except requests.exceptions.RequestException as e:
    print(f"❌ Request failed: {e}")

print("\n🏁 Test completed!")
