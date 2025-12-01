#!/usr/bin/env python3
"""
Generate a JWT token for QA testing
"""

import sys

sys.path.insert(0, "/home/yashar/projects/sato-be/sato/sato-be")

from app.core.auth import create_access_token

# Create a token for a test user (using the same data as in tests)
token = create_access_token(data={"sub": "dor.yashar@gmail.com", "user_id": 10})

print(f"JWT_TOKEN={token}")
