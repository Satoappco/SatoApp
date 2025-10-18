#!/usr/bin/env python3
"""
Test Facebook token exchange to debug why we're getting short-lived tokens
"""

import os
import sys
import requests
import json
from datetime import datetime, timezone

# Add the app directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

def test_facebook_token_exchange():
    """Test Facebook token exchange process"""
    
    print("🔍 Testing Facebook Token Exchange Process")
    print("=" * 60)
    
    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv('.env.local')
    
    facebook_app_id = os.getenv('FACEBOOK_APP_ID')
    facebook_app_secret = os.getenv('FACEBOOK_APP_SECRET')
    
    if not facebook_app_id or not facebook_app_secret:
        print("❌ Facebook App ID or Secret not found in environment")
        return
    
    print(f"✅ Facebook App ID: {facebook_app_id}")
    print(f"✅ Facebook App Secret: {'*' * len(facebook_app_secret) if facebook_app_secret else 'NOT SET'}")
    print()
    
    # Test the token exchange endpoint
    base_url = "https://graph.facebook.com/v18.0"
    url = f"{base_url}/oauth/access_token"
    
    print("🔍 Testing Facebook Token Exchange API...")
    print(f"URL: {url}")
    print()
    
    # Test with a dummy token to see what error we get
    test_params = {
        'grant_type': 'fb_exchange_token',
        'client_id': facebook_app_id,
        'client_secret': facebook_app_secret,
        'fb_exchange_token': 'test_token'
    }
    
    try:
        response = requests.get(url, params=test_params)
        print(f"Response Status: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        print(f"Response Body: {response.text}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Token exchange successful: {data}")
        else:
            error_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else {}
            print(f"❌ Token exchange failed: {error_data}")
            
    except Exception as e:
        print(f"❌ Error testing token exchange: {e}")
    
    print()
    print("🔍 Checking Facebook App Configuration...")
    
    # Check app info
    app_info_url = f"{base_url}/{facebook_app_id}"
    app_params = {
        'access_token': f"{facebook_app_id}|{facebook_app_secret}"
    }
    
    try:
        response = requests.get(app_info_url, params=app_params)
        print(f"App Info Status: {response.status_code}")
        
        if response.status_code == 200:
            app_data = response.json()
            print(f"✅ App Info: {json.dumps(app_data, indent=2)}")
        else:
            print(f"❌ Failed to get app info: {response.text}")
            
    except Exception as e:
        print(f"❌ Error getting app info: {e}")

def check_facebook_permissions():
    """Check what permissions are available for the Facebook app"""
    
    print("\n🔍 Checking Facebook App Permissions...")
    print("=" * 60)
    
    from dotenv import load_dotenv
    load_dotenv('.env.local')
    
    facebook_app_id = os.getenv('FACEBOOK_APP_ID')
    facebook_app_secret = os.getenv('FACEBOOK_APP_SECRET')
    
    if not facebook_app_id or not facebook_app_secret:
        print("❌ Facebook App ID or Secret not found")
        return
    
    # Get app permissions
    base_url = "https://graph.facebook.com/v18.0"
    permissions_url = f"{base_url}/{facebook_app_id}/permissions"
    params = {
        'access_token': f"{facebook_app_id}|{facebook_app_secret}"
    }
    
    try:
        response = requests.get(permissions_url, params=params)
        print(f"Permissions Status: {response.status_code}")
        
        if response.status_code == 200:
            permissions_data = response.json()
            print(f"✅ App Permissions: {json.dumps(permissions_data, indent=2)}")
        else:
            print(f"❌ Failed to get permissions: {response.text}")
            
    except Exception as e:
        print(f"❌ Error getting permissions: {e}")

if __name__ == "__main__":
    test_facebook_token_exchange()
    check_facebook_permissions()


