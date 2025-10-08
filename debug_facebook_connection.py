#!/usr/bin/env python3
"""
Debug script to check Facebook connection status in the database
"""

import os
import sys
from datetime import datetime, timezone
from sqlmodel import select, and_

# Add the app directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

from app.config.database import get_session
from app.models.analytics import Connection, DigitalAsset, AssetType
from app.models.users import User

def check_facebook_connections():
    """Check all Facebook connections in the database"""
    
    print("🔍 Checking Facebook connections in database...")
    print("=" * 60)
    
    try:
        with get_session() as session:
            # Get all Facebook connections
            statement = select(Connection, DigitalAsset, User).join(
                DigitalAsset, Connection.digital_asset_id == DigitalAsset.id
            ).join(
                User, Connection.user_id == User.id
            ).where(
                and_(
                    DigitalAsset.provider == "Facebook",
                    Connection.revoked == False
                )
            )
            
            results = session.exec(statement).all()
            
            if not results:
                print("❌ No Facebook connections found in database")
                return
            
            print(f"✅ Found {len(results)} Facebook connections:")
            print()
            
            for i, (connection, digital_asset, user) in enumerate(results, 1):
                print(f"🔗 Connection #{i} (ID: {connection.id})")
                print(f"   User: {user.email} (ID: {user.id})")
                print(f"   Asset: {digital_asset.name} (Type: {digital_asset.asset_type})")
                print(f"   External ID: {digital_asset.external_id}")
                print(f"   Created: {connection.created_at}")
                print(f"   Last Used: {connection.last_used_at}")
                print(f"   Expires At: {connection.expires_at}")
                
                # Check if token is expired
                now = datetime.utcnow().replace(tzinfo=timezone.utc)
                if connection.expires_at:
                    if connection.expires_at < now:
                        print(f"   ❌ TOKEN EXPIRED! (expired {(now - connection.expires_at).days} days ago)")
                    else:
                        time_until_expiry = connection.expires_at - now
                        print(f"   ✅ Token valid (expires in {time_until_expiry.days} days)")
                else:
                    print(f"   ⚠️  No expiry date set")
                
                print(f"   Has Access Token: {'Yes' if connection.access_token_enc else 'No'}")
                print(f"   Has Refresh Token: {'Yes' if connection.refresh_token_enc else 'No'}")
                print(f"   Is Active: {digital_asset.is_active}")
                print(f"   Revoked: {connection.revoked}")
                print()
                
    except Exception as e:
        print(f"❌ Error checking connections: {e}")
        import traceback
        traceback.print_exc()

def check_recent_facebook_activity():
    """Check recent Facebook connection activity"""
    
    print("🔍 Checking recent Facebook activity...")
    print("=" * 60)
    
    try:
        with get_session() as session:
            # Get Facebook connections created in the last 7 days
            from datetime import timedelta
            week_ago = datetime.utcnow() - timedelta(days=7)
            
            statement = select(Connection, DigitalAsset, User).join(
                DigitalAsset, Connection.digital_asset_id == DigitalAsset.id
            ).join(
                User, Connection.user_id == User.id
            ).where(
                and_(
                    DigitalAsset.provider == "Facebook",
                    Connection.created_at >= week_ago
                )
            ).order_by(Connection.created_at.desc())
            
            results = session.exec(statement).all()
            
            if not results:
                print("❌ No Facebook connections created in the last 7 days")
                return
            
            print(f"✅ Found {len(results)} Facebook connections created in last 7 days:")
            print()
            
            for connection, digital_asset, user in results:
                print(f"🔗 Connection ID: {connection.id}")
                print(f"   User: {user.email}")
                print(f"   Created: {connection.created_at}")
                print(f"   Last Used: {connection.last_used_at}")
                print(f"   Expires: {connection.expires_at}")
                print()
                
    except Exception as e:
        print(f"❌ Error checking recent activity: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("Facebook Connection Debug Tool")
    print("=" * 60)
    print()
    
    check_facebook_connections()
    print()
    check_recent_facebook_activity()
