#!/usr/bin/env python3
"""
Comprehensive error scenario testing for Sato AI Platform
Tests various error conditions and edge cases before deployment
"""

import asyncio
import httpx
import json
import os
from typing import Dict, Any

# Test configuration
BASE_URL = "https://localhost:8000"
JWT_TOKEN = os.getenv("TEST_JWT_TOKEN", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjo1LCJlbWFpbCI6InNhdG9hcHBjb0BnbWFpbC5jb20iLCJyb2xlIjoidmlld2VyIiwicHJpbWFyeV9jdXN0b21lcl9pZCI6NSwiZXhwIjoxNzU5MTY1NjM4LCJ0eXBlIjoiYWNjZXNzIn0.cbT9HnysgrHG_ni6k4BDS0ir7sUrBOyyH_loexvDZTU")  # Use env var or test token

class ErrorTester:
    def __init__(self, base_url: str, jwt_token: str):
        self.base_url = base_url
        self.jwt_token = jwt_token
        self.results = []
    
    async def test_scenario(self, name: str, endpoint: str, payload: Dict[str, Any], expected_status: int = None):
        """Test a specific error scenario"""
        print(f"\n🧪 Testing: {name}")
        print(f"   Endpoint: {endpoint}")
        print(f"   Payload: {json.dumps(payload, indent=2)}")
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}{endpoint}",
                    json=payload,
                    headers={"Authorization": f"Bearer {self.jwt_token}"},
                    timeout=30.0
                )
                
                print(f"   Status: {response.status_code}")
                print(f"   Response: {response.text[:200]}...")
                
                result = {
                    "name": name,
                    "endpoint": endpoint,
                    "expected_status": expected_status,
                    "actual_status": response.status_code,
                    "success": expected_status is None or response.status_code == expected_status,
                    "response": response.text
                }
                
                self.results.append(result)
                return result
                
        except Exception as e:
            print(f"   Error: {str(e)}")
            result = {
                "name": name,
                "endpoint": endpoint,
                "expected_status": expected_status,
                "actual_status": "ERROR",
                "success": False,
                "error": str(e)
            }
            self.results.append(result)
            return result
    
    async def run_all_tests(self):
        """Run all error scenario tests"""
        print("🚀 Starting comprehensive error scenario testing...")
        
        # Test 1: Missing session_id
        await self.test_scenario(
            "Missing session_id",
            "/api/v1/webhooks/dialogcx",
            {
                "user_id": 5,
                "customer_id": 5,
                "user_question": "test question",
                "user_intent": "test_intent",
                "parameters": {"data_source": ["ga4"]}
            },
            expected_status=400
        )
        
        # Test 2: Empty user_question
        await self.test_scenario(
            "Empty user_question",
            "/api/v1/webhooks/dialogcx",
            {
                "user_id": 5,
                "customer_id": 5,
                "session_id": "test8b85770d-d851-47cd-85d6-992cc041e6df",
                "user_question": "",
                "user_intent": "test_intent",
                "parameters": {"data_source": ["ga4"]}
            },
            expected_status=400
        )
        
        # Test 3: Invalid user_id range
        await self.test_scenario(
            "Invalid user_id range",
            "/api/v1/webhooks/dialogcx",
            {
                "user_id": 9999999,
                "customer_id": 5,
                "session_id": "test8b85770d-d851-47cd-85d6-992cc041e6df",
                "user_question": "test question",
                "user_intent": "test_intent",
                "parameters": {"data_source": ["ga4"]}
            },
            expected_status=400
        )
        
        # Test 4: Invalid data sources
        await self.test_scenario(
            "Invalid data sources",
            "/api/v1/webhooks/dialogcx",
            {
                "user_id": 5,
                "customer_id": 5,
                "session_id": "test8b85770d-d851-47cd-85d6-992cc041e6df",
                "user_question": "test question",
                "user_intent": "test_intent",
                "parameters": {"data_source": ["invalid_source", "another_invalid"]}
            },
            expected_status=400
        )
        
        # Test 5: Non-list data_sources
        await self.test_scenario(
            "Non-list data_sources",
            "/api/v1/webhooks/dialogcx",
            {
                "user_id": 5,
                "customer_id": 5,
                "session_id": "test8b85770d-d851-47cd-85d6-992cc041e6df",
                "user_question": "test question",
                "user_intent": "test_intent",
                "parameters": {"data_source": "ga4"}
            },
            expected_status=400
        )
        
        # Test 6: CrewAI Test - Missing user_question
        await self.test_scenario(
            "CrewAI Test - Missing user_question",
            "/api/v1/crewai-test",
            {
                "user_id": 5,
                "customer_id": 5,
                "session_id": "test8b85770d-d851-47cd-85d6-992cc041e6df",
                "user_question": "",
                "user_intent": "test_intent",
                "parameters": {"data_source": ["ga4"]},
                "data_sources": ["ga4"]
            },
            expected_status=200  # Should return fulfillment_response with error message
        )
        
        # Test 7: CrewAI Test - Invalid user_id
        await self.test_scenario(
            "CrewAI Test - Invalid user_id",
            "/api/v1/crewai-test",
            {
                "user_id": 0,
                "customer_id": 5,
                "session_id": "test8b85770d-d851-47cd-85d6-992cc041e6df",
                "user_question": "test question",
                "user_intent": "test_intent",
                "parameters": {"data_source": ["ga4"]},
                "data_sources": ["ga4"]
            },
            expected_status=200  # Should return fulfillment_response with error message
        )
        
        # Test 8: CrewAI Test - Invalid data sources
        await self.test_scenario(
            "CrewAI Test - Invalid data sources",
            "/api/v1/crewai-test",
            {
                "user_id": 5,
                "customer_id": 5,
                "session_id": "test8b85770d-d851-47cd-85d6-992cc041e6df",
                "user_question": "test question",
                "user_intent": "test_intent",
                "parameters": {"data_source": ["ga4"]},
                "data_sources": ["invalid_source"]
            },
            expected_status=200  # Should return fulfillment_response with error message
        )
        
        # Test 9: Valid request (should succeed)
        await self.test_scenario(
            "Valid request",
            "/api/v1/crewai-test",
            {
                "user_id": 5,
                "customer_id": 5,
                "session_id": "test8b85770d-d851-47cd-85d6-992cc041e6df",
                "user_question": "What is my best performing day of the week?",
                "user_intent": "analytics.performance_analysis",
                "parameters": {"data_source": ["ga4"]},
                "data_sources": ["ga4"]
            },
            expected_status=200
        )
        
        # Test 10: No data sources (should use fallback)
        await self.test_scenario(
            "No data sources (fallback test)",
            "/api/v1/webhooks/dialogcx",
            {
                "user_id": 5,
                "customer_id": 5,
                "session_id": "test8b85770d-d851-47cd-85d6-992cc041e6df",
                "user_question": "test question",
                "user_intent": "test_intent",
                "parameters": {"data_source": []}
            },
            expected_status=200  # Should succeed with fallback
        )
        
        # Print summary
        self.print_summary()
    
    def print_summary(self):
        """Print test results summary"""
        print("\n" + "="*60)
        print("📊 ERROR SCENARIO TEST SUMMARY")
        print("="*60)
        
        total_tests = len(self.results)
        passed_tests = sum(1 for r in self.results if r["success"])
        failed_tests = total_tests - passed_tests
        
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests} ✅")
        print(f"Failed: {failed_tests} ❌")
        print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        
        if failed_tests > 0:
            print("\n❌ FAILED TESTS:")
            for result in self.results:
                if not result["success"]:
                    print(f"  - {result['name']}: Expected {result['expected_status']}, got {result['actual_status']}")
        
        print("\n" + "="*60)

async def main():
    """Main test runner"""
    print("🔧 Sato AI Platform - Error Scenario Testing")
    print("=" * 50)
    
    if JWT_TOKEN == "YOUR_JWT_TOKEN_HERE":
        print("❌ Please update JWT_TOKEN in the script with a valid token")
        print("   You can get a token from the frontend debug panel")
        return
    
    tester = ErrorTester(BASE_URL, JWT_TOKEN)
    await tester.run_all_tests()

if __name__ == "__main__":
    asyncio.run(main())
