#!/usr/bin/env python3
"""
Test script to verify JWT token creation and verification
Run this to debug authentication issues
"""

from datetime import datetime, timedelta, timezone
from app.core.auth import create_access_token, verify_token

# Test data
test_user_data = {
    "campaigner_id": 10,
    "email": "test@example.com",
    "role": "ADMIN",
    "agency_id": 1
}

print("=" * 60)
print("JWT Token Creation & Verification Test")
print("=" * 60)

# Create token
print("\n1. Creating access token...")
token = create_access_token(data=test_user_data)
print(f"✅ Token created: {token[:50]}...")

# Verify token
print("\n2. Verifying token...")
try:
    payload = verify_token(token, "access")
    print(f"✅ Token verified successfully!")
    print(f"   Payload: {payload}")

    # Check expiration
    exp = payload.get("exp")
    if exp:
        exp_time = datetime.fromtimestamp(exp, tz=timezone.utc)
        now = datetime.now(timezone.utc)
        time_left = exp_time - now
        print(f"   Expires at: {exp_time.isoformat()}")
        print(f"   Current time: {now.isoformat()}")
        print(f"   Time until expiry: {time_left}")

except Exception as e:
    print(f"❌ Token verification failed: {e}")

print("\n" + "=" * 60)
print("Test complete!")
print("=" * 60)
