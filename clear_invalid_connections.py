#!/usr/bin/env python3
"""
Clear invalid OAuth connections that have mixed scopes
This fixes the OAuth scope mismatch issue
"""

import os
import sys
from sqlmodel import select, and_

# Add the app directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

from app.config.database import get_session
from app.models.analytics import Connection, DigitalAsset, AssetType

def clear_invalid_connections():
    """Clear connections with invalid scopes"""
    
    with get_session() as session:
        # Find all OAuth connections
        statement = select(Connection).where(Connection.auth_type == "oauth2")
        connections = session.exec(statement).all()
        
        invalid_connections = []
        for conn in connections:
            if conn.scopes and any(scope in conn.scopes for scope in [
                'https://www.googleapis.com/auth/adwords',
                'https://www.googleapis.com/auth/adsdatahub'
            ]):
                invalid_connections.append(conn)
        
        print(f"Found {len(invalid_connections)} connections with Google Ads scopes")
        
        # Revoke invalid connections
        for conn in invalid_connections:
            print(f"Revoking connection {conn.id} with scopes: {conn.scopes}")
            conn.revoked = True
            conn.access_token_enc = None
            conn.refresh_token_enc = None
            conn.token_hash = None
            session.add(conn)
        
        session.commit()
        
        print(f"Successfully revoked {len(invalid_connections)} connections with invalid scopes")
        
        return len(invalid_connections)

if __name__ == "__main__":
    try:
        count = clear_invalid_connections()
        print(f"✅ Cleared {count} invalid connections")
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
