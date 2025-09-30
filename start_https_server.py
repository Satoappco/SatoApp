#!/usr/bin/env python3
"""
HTTPS server startup script for Sato AI backend
This script starts the FastAPI application with HTTPS using SSL certificates
"""

import uvicorn
import ssl
import os
import sys
from pathlib import Path

def start_https_server():
    """Start FastAPI server with HTTPS"""
    
    # Get the directory of this script
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    
    # Certificate paths
    cert_file = project_root / "certs" / "sato-backend.pem"
    key_file = project_root / "certs" / "sato-backend-key.pem"
    
    # Check if certificates exist
    if not cert_file.exists() or not key_file.exists():
        print("❌ SSL certificates not found!")
        print(f"   Certificate file: {cert_file}")
        print(f"   Key file: {key_file}")
        print("🔧 Please run the setup script first:")
        print("   ./setup_mkcert.sh")
        sys.exit(1)
    
    print("🔐 Starting Sato AI backend with HTTPS...")
    print(f"   Certificate: {cert_file}")
    print(f"   Key: {key_file}")
    print("   URL: https://localhost:8000")
    
    # Start the server with SSL
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        ssl_keyfile=str(key_file),
        ssl_certfile=str(cert_file),
        reload=True,
        log_level="info"
    )

if __name__ == "__main__":
    start_https_server()
