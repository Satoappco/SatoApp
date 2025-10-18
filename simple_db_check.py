#!/usr/bin/env python3
"""
Simple database check without full app configuration
"""

import os
import sys
from datetime import datetime, timezone
import psycopg2
from psycopg2.extras import RealDictCursor

def check_facebook_connections():
    """Check Facebook connections directly from database"""
    
    # Get database URL from environment
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("❌ DATABASE_URL not found in environment")
        return
    
    print("🔍 Checking Facebook connections in database...")
    print("=" * 60)
    
    try:
        # Connect to database
        conn = psycopg2.connect(database_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Query Facebook connections
        query = """
        SELECT 
            c.id as connection_id,
            c.user_id,
            c.created_at,
            c.last_used_at,
            c.expires_at,
            c.revoked,
            c.access_token_enc IS NOT NULL as has_access_token,
            c.refresh_token_enc IS NOT NULL as has_refresh_token,
            da.name as asset_name,
            da.asset_type,
            da.external_id,
            da.is_active,
            u.email as user_email
        FROM connections c
        JOIN digital_assets da ON c.digital_asset_id = da.id
        JOIN users u ON c.user_id = u.id
        WHERE da.provider = 'Facebook'
        AND c.revoked = false
        ORDER BY c.created_at DESC
        """
        
        cur.execute(query)
        results = cur.fetchall()
        
        if not results:
            print("❌ No Facebook connections found in database")
            return
        
        print(f"✅ Found {len(results)} Facebook connections:")
        print()
        
        for i, row in enumerate(results, 1):
            print(f"🔗 Connection #{i} (ID: {row['connection_id']})")
            print(f"   User: {row['user_email']} (ID: {row['user_id']})")
            print(f"   Asset: {row['asset_name']} (Type: {row['asset_type']})")
            print(f"   External ID: {row['external_id']}")
            print(f"   Created: {row['created_at']}")
            print(f"   Last Used: {row['last_used_at']}")
            print(f"   Expires At: {row['expires_at']}")
            
            # Check if token is expired
            if row['expires_at']:
                now = datetime.utcnow().replace(tzinfo=timezone.utc)
                expires_at = row['expires_at'].replace(tzinfo=timezone.utc) if row['expires_at'].tzinfo is None else row['expires_at']
                
                if expires_at < now:
                    days_expired = (now - expires_at).days
                    print(f"   ❌ TOKEN EXPIRED! (expired {days_expired} days ago)")
                else:
                    time_until_expiry = expires_at - now
                    print(f"   ✅ Token valid (expires in {time_until_expiry.days} days)")
            else:
                print(f"   ⚠️  No expiry date set")
            
            print(f"   Has Access Token: {'Yes' if row['has_access_token'] else 'No'}")
            print(f"   Has Refresh Token: {'Yes' if row['has_refresh_token'] else 'No'}")
            print(f"   Is Active: {row['is_active']}")
            print(f"   Revoked: {row['revoked']}")
            print()
            
        # Check recent activity (last 7 days)
        print("🔍 Checking recent Facebook activity (last 7 days)...")
        print("=" * 60)
        
        recent_query = """
        SELECT 
            c.id as connection_id,
            c.created_at,
            c.last_used_at,
            u.email as user_email
        FROM connections c
        JOIN digital_assets da ON c.digital_asset_id = da.id
        JOIN users u ON c.user_id = u.id
        WHERE da.provider = 'Facebook'
        AND c.created_at >= NOW() - INTERVAL '7 days'
        ORDER BY c.created_at DESC
        """
        
        cur.execute(recent_query)
        recent_results = cur.fetchall()
        
        if not recent_results:
            print("❌ No Facebook connections created in the last 7 days")
        else:
            print(f"✅ Found {len(recent_results)} Facebook connections created in last 7 days:")
            print()
            
            for row in recent_results:
                print(f"🔗 Connection ID: {row['connection_id']}")
                print(f"   User: {row['user_email']}")
                print(f"   Created: {row['created_at']}")
                print(f"   Last Used: {row['last_used_at']}")
                print()
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Error checking connections: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("Facebook Connection Debug Tool")
    print("=" * 60)
    print()
    
    check_facebook_connections()


