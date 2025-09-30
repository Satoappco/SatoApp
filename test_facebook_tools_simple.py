#!/usr/bin/env python3
"""
Simple Facebook Tools Test
Tests Facebook tools integration without external dependencies
"""

import sys
import os
import json
from datetime import datetime

# Add current directory to path
sys.path.append(os.path.dirname(__file__))

def test_facebook_connections():
    """Test if Facebook connections exist in the database"""
    print("🔍 Testing Facebook connections...")
    
    try:
        from app.config.database import get_session
        from app.models.analytics import Connection, DigitalAsset, AssetType
        from sqlmodel import select, and_
        
        with get_session() as session:
            # Check for social media connections
            social_statement = select(Connection, DigitalAsset).join(
                DigitalAsset, Connection.digital_asset_id == DigitalAsset.id
            ).where(
                and_(
                    DigitalAsset.provider == "Facebook",
                    DigitalAsset.asset_type == AssetType.SOCIAL_MEDIA,
                    Connection.revoked == False
                )
            )
            social_connections = session.exec(social_statement).all()
            
            # Check for advertising connections
            ad_statement = select(Connection, DigitalAsset).join(
                DigitalAsset, Connection.digital_asset_id == DigitalAsset.id
            ).where(
                and_(
                    DigitalAsset.provider == "Facebook",
                    DigitalAsset.asset_type == AssetType.ADVERTISING,
                    Connection.revoked == False
                )
            )
            ad_connections = session.exec(ad_statement).all()
            
            print(f"✅ Found {len(social_connections)} Facebook social media connections")
            print(f"✅ Found {len(ad_connections)} Facebook advertising connections")
            
            if social_connections:
                print("📱 Social Media Assets:")
                for conn, asset in social_connections:
                    print(f"  - {asset.name} (ID: {asset.external_id}) - User: {conn.user_id}")
            
            if ad_connections:
                print("📊 Advertising Assets:")
                for conn, asset in ad_connections:
                    print(f"  - {asset.name} (ID: {asset.external_id}) - User: {conn.user_id}")
            
            return len(social_connections) > 0 or len(ad_connections) > 0
            
    except Exception as e:
        print(f"❌ Database connection test failed: {str(e)}")
        return False


def test_tool_imports():
    """Test that all Facebook tools can be imported"""
    print("🔧 Testing tool imports...")
    
    success = True
    
    try:
        from app.tools.facebook_analytics_tool import FacebookAnalyticsTool
        print("  ✅ FacebookAnalyticsTool imported successfully")
    except ImportError as e:
        print(f"  ❌ Failed to import FacebookAnalyticsTool: {e}")
        success = False
    
    try:
        from app.tools.facebook_ads_tool import FacebookAdsTool
        print("  ✅ FacebookAdsTool imported successfully")
    except ImportError as e:
        print(f"  ❌ Failed to import FacebookAdsTool: {e}")
        success = False
    
    try:
        from app.tools.facebook_marketing_tool import FacebookMarketingTool
        print("  ✅ FacebookMarketingTool imported successfully")
    except ImportError as e:
        print(f"  ❌ Failed to import FacebookMarketingTool: {e}")
        success = False
    
    return success


def test_facebook_service():
    """Test Facebook service availability"""
    print("🔧 Testing Facebook service...")
    
    try:
        from app.services.facebook_service import FacebookService
        service = FacebookService()
        print("  ✅ FacebookService imported and instantiated successfully")
        print(f"  📡 API Version: {service.api_version}")
        print(f"  🔐 Scopes: {len(service.FACEBOOK_SCOPES)} permissions")
        return True
    except Exception as e:
        print(f"  ❌ FacebookService test failed: {e}")
        return False


def test_webhook_tool_mapping():
    """Test that webhook tool mapping includes Facebook tools"""
    print("🔧 Testing webhook tool mapping...")
    
    try:
        # Read the webhooks.py file and check for Facebook tools
        webhook_file = "app/api/v1/routes/webhooks.py"
        with open(webhook_file, 'r') as f:
            content = f.read()
        
        facebook_tools = [
            "FacebookAnalyticsTool",
            "FacebookAdsTool", 
            "FacebookMarketingTool"
        ]
        
        found_tools = []
        for tool in facebook_tools:
            if tool in content:
                found_tools.append(tool)
                print(f"  ✅ {tool} found in webhook mapping")
            else:
                print(f"  ❌ {tool} NOT found in webhook mapping")
        
        return len(found_tools) == len(facebook_tools)
        
    except Exception as e:
        print(f"  ❌ Webhook mapping test failed: {e}")
        return False


def main():
    """Run all Facebook tool tests"""
    print("🚀 Starting Facebook Tools Integration Test")
    print("=" * 60)
    
    tests = [
        ("Tool Imports", test_tool_imports),
        ("Facebook Service", test_facebook_service),
        ("Webhook Mapping", test_webhook_tool_mapping),
        ("Database Connections", test_facebook_connections),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n🧪 Running {test_name} test...")
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} test failed with exception: {e}")
            results.append((test_name, False))
    
    print("\n" + "=" * 60)
    print("📊 Test Results Summary:")
    print("=" * 60)
    
    passed = 0
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status} - {test_name}")
        if result:
            passed += 1
    
    print(f"\n🎯 Overall: {passed}/{len(results)} tests passed")
    
    if passed == len(results):
        print("\n🎉 All tests passed! Facebook tools are ready to use.")
        print("\n📋 Available Facebook Tools:")
        print("  - FacebookAnalyticsTool: Page insights and social media data")
        print("  - FacebookAdsTool: Advertising and campaign data") 
        print("  - FacebookMarketingTool: Comprehensive tool with auto-detection")
        print("\n🎯 Next Steps:")
        print("  1. Connect Facebook accounts via the Connections tab")
        print("  2. Test with real agents in the CrewAI system")
        print("  3. Monitor logs for any issues")
    else:
        print(f"\n⚠️  {len(results) - passed} tests failed. Please check the errors above.")
        print("\n🔧 Common fixes:")
        print("  - Ensure all dependencies are installed")
        print("  - Check database connection")
        print("  - Verify Facebook OAuth setup")


if __name__ == "__main__":
    main()
