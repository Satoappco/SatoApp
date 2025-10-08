#!/usr/bin/env python3
"""
Test the actual Facebook OAuth flow to see what tokens we get
"""

import os
import sys
import requests
import json
from datetime import datetime, timezone

# Add the app directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

def test_facebook_oauth_flow():
    """Test the complete Facebook OAuth flow"""
    
    print("🔍 Testing Facebook OAuth Flow - What Tokens Do We Actually Get?")
    print("=" * 70)
    
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
    
    # Step 1: Test initial token exchange (what Facebook gives us first)
    print("🔍 Step 1: Testing Initial Token Exchange")
    print("-" * 50)
    
    base_url = "https://graph.facebook.com/v18.0"
    token_url = f"{base_url}/oauth/access_token"
    
    # This simulates what happens when user authorizes
    # We'll use a dummy code to see what error we get
    test_data = {
        'client_id': facebook_app_id,
        'client_secret': facebook_app_secret,
        'redirect_uri': 'https://satoapp.co/auth/facebook/callback',
        'code': 'test_code_123'
    }
    
    try:
        response = requests.post(token_url, data=test_data)
        print(f"Initial Token Exchange Status: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            token_data = response.json()
            print(f"✅ Initial token received: {json.dumps(token_data, indent=2)}")
        else:
            print(f"❌ Initial token exchange failed: {response.text}")
            
    except Exception as e:
        print(f"❌ Error in initial token exchange: {e}")
    
    print()
    
    # Step 2: Test long-lived token exchange
    print("🔍 Step 2: Testing Long-Lived Token Exchange")
    print("-" * 50)
    
    # Test with a dummy short-lived token
    exchange_url = f"{base_url}/oauth/access_token"
    exchange_params = {
        'grant_type': 'fb_exchange_token',
        'client_id': facebook_app_id,
        'client_secret': facebook_app_secret,
        'fb_exchange_token': 'test_short_lived_token'
    }
    
    try:
        response = requests.get(exchange_url, params=exchange_params)
        print(f"Long-Lived Token Exchange Status: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            exchange_data = response.json()
            print(f"✅ Long-lived token exchange successful: {json.dumps(exchange_data, indent=2)}")
        else:
            print(f"❌ Long-lived token exchange failed: {response.text}")
            
    except Exception as e:
        print(f"❌ Error in long-lived token exchange: {e}")
    
    print()
    
    # Step 3: Check what permissions are actually available
    print("🔍 Step 3: Checking Available Permissions")
    print("-" * 50)
    
    permissions_url = f"{base_url}/{facebook_app_id}/permissions"
    permissions_params = {
        'access_token': f"{facebook_app_id}|{facebook_app_secret}"
    }
    
    try:
        response = requests.get(permissions_url, params=permissions_params)
        print(f"Permissions Status: {response.status_code}")
        
        if response.status_code == 200:
            permissions_data = response.json()
            print(f"✅ Available Permissions: {json.dumps(permissions_data, indent=2)}")
        else:
            print(f"❌ Failed to get permissions: {response.text}")
            
    except Exception as e:
        print(f"❌ Error getting permissions: {e}")
    
    print()
    
    # Step 4: Check app configuration
    print("🔍 Step 4: Checking App Configuration")
    print("-" * 50)
    
    app_url = f"{base_url}/{facebook_app_id}"
    app_params = {
        'access_token': f"{facebook_app_id}|{facebook_app_secret}",
        'fields': 'id,name,category,link,privacy_policy_url,terms_of_service_url,data_deletion_url,app_domains,website_url'
    }
    
    try:
        response = requests.get(app_url, params=app_params)
        print(f"App Info Status: {response.status_code}")
        
        if response.status_code == 200:
            app_data = response.json()
            print(f"✅ App Configuration: {json.dumps(app_data, indent=2)}")
        else:
            print(f"❌ Failed to get app info: {response.text}")
            
    except Exception as e:
        print(f"❌ Error getting app info: {e}")

def analyze_facebook_scopes():
    """Analyze what scopes are being requested vs what's available"""
    
    print("\n🔍 Analyzing Facebook Scopes")
    print("=" * 70)
    
    # The scopes your app is requesting
    requested_scopes = [
        'email',
        'public_profile', 
        'pages_read_engagement',
        'pages_manage_metadata',
        'ads_read',
        'ads_management',
        'business_management',
        'pages_show_list',
        'read_insights',
        'pages_read_user_content',
        'pages_manage_posts',
        'pages_manage_engagement'
    ]
    
    print("📋 Scopes Your App Is Requesting:")
    for scope in requested_scopes:
        print(f"  - {scope}")
    
    print("\n📋 Scopes That Require App Review:")
    advanced_scopes = [
        'pages_read_engagement',
        'pages_manage_metadata', 
        'ads_read',
        'ads_management',
        'business_management',
        'pages_show_list',
        'read_insights',
        'pages_read_user_content',
        'pages_manage_posts',
        'pages_manage_engagement'
    ]
    
    for scope in advanced_scopes:
        print(f"  - {scope} (REQUIRES APP REVIEW)")
    
    print("\n📋 Basic Scopes (No Review Required):")
    basic_scopes = ['email', 'public_profile']
    for scope in basic_scopes:
        print(f"  - {scope} (NO REVIEW REQUIRED)")
    
    print("\n🎯 Analysis:")
    print("  - Your app requests 12 scopes")
    print("  - 10 scopes require Facebook App Review")
    print("  - Only 2 scopes are basic (no review required)")
    print("  - Facebook only approves basic scopes initially")
    print("  - Basic scopes = short-lived tokens (1-2 hours)")
    print("  - Advanced scopes = long-lived tokens (60 days)")

if __name__ == "__main__":
    test_facebook_oauth_flow()
    analyze_facebook_scopes()
