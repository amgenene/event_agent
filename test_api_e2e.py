#!/usr/bin/env python3
"""End-to-end testing script for EventFinder API."""

import httpx
import json
import time
from typing import Dict, Any

BASE_URL = "http://localhost:8000"


class APITester:
    """Test the EventFinder API endpoints."""
    
    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
        self.client = httpx.Client(timeout=30.0)
    
    def health_check(self) -> bool:
        """Test health check endpoint."""
        print("\n🏥 Testing Health Check Endpoint")
        print("-" * 50)
        
        try:
            response = self.client.get(f"{self.base_url}/health")
            print(f"Status: {response.status_code}")
            print(f"Response: {response.json()}")
            return response.status_code == 200
        except Exception as e:
            print(f"❌ Error: {e}")
            return False
    
    def search_events(self, query: str, preferences: Dict[str, Any] = None) -> Dict:
        """Test search events endpoint."""
        print(f"\n🔍 Testing Search Events Endpoint")
        print(f"Query: {query}")
        print("-" * 50)
        
        payload = {
            "query": query,
            "preferences": preferences or {
                "home_city": "San Francisco",
                "favorite_genres": ["jazz", "music"],
                "radius_miles": 5,
                "max_transit_minutes": 30
            }
        }
        
        try:
            response = self.client.post(
                f"{self.base_url}/search",
                json=payload
            )
            print(f"Status: {response.status_code}")
            result = response.json()
            print(f"Success: {result.get('success')}")
            print(f"Message: {result.get('message')}")
            print(f"Events Found: {len(result.get('events', []))}")
            
            if result.get('events'):
                for event in result['events'][:2]:  # Show first 2
                    print(f"  - {event['title']} at {event['location']}")
            
            return result
        except Exception as e:
            print(f"❌ Error: {e}")
            return {}
    
    def verify_event(self, description: str) -> Dict:
        """Test verify event endpoint."""
        print(f"\n✅ Testing Verify Event Endpoint")
        print(f"Description: {description[:80]}...")
        print("-" * 50)
        
        payload = {"description": description}
        
        try:
            response = self.client.post(
                f"{self.base_url}/verify",
                json=payload
            )
            print(f"Status: {response.status_code}")
            result = response.json()
            print(f"Status: {result.get('status')}")
            
            warnings = result.get('warnings', [])
            if warnings:
                print(f"Warnings ({len(warnings)}):")
                for warning in warnings:
                    print(f"  ⚠️  {warning}")
            else:
                print("No warnings")
            
            return result
        except Exception as e:
            print(f"❌ Error: {e}")
            return {}
    
    def run_full_test_suite(self):
        """Run complete test suite."""
        print("\n" + "=" * 50)
        print("🚀 EventFinder API - End-to-End Test Suite")
        print("=" * 50)
        
        # Test 1: Health Check
        health_ok = self.health_check()
        if not health_ok:
            print("\n❌ API is not running. Start it with:")
            print("   uvicorn src.api:app --reload")
            return
        
        # Test 2: Search with different queries
        test_queries = [
            "Find free jazz events",
            "Live music in the area",
            "Tech meetups"
        ]
        
        search_results = []
        for query in test_queries:
            result = self.search_events(query)
            search_results.append(result)
            time.sleep(0.5)  # Small delay between requests
        
        # Test 3: Verify different event descriptions
        test_descriptions = [
            "Free community jazz night! No tickets required. Everyone welcome.",
            "Live band at the venue. $15 cover charge per person.",
            "Happy hour event - $5 drink minimum per person.",
            "Community fundraiser - suggested donation $10.",
            "Free outdoor concert in the park. Bring a blanket!"
        ]
        
        verify_results = []
        for description in test_descriptions:
            result = self.verify_event(description)
            verify_results.append(result)
            time.sleep(0.3)
        
        # Summary
        print("\n" + "=" * 50)
        print("📊 Test Summary")
        print("=" * 50)
        print(f"✅ Health Check: PASSED")
        print(f"✅ Search Endpoint: {len(search_results)} queries tested")
        print(f"✅ Verify Endpoint: {len(verify_results)} descriptions tested")
        
        # Count free vs paid events
        free_count = sum(1 for r in verify_results if r.get('status') == 'FREE')
        paid_count = sum(1 for r in verify_results if r.get('status') == 'PAID')
        
        print(f"\nVerification Results:")
        print(f"  Free Events: {free_count}")
        print(f"  Paid Events: {paid_count}")
        
        print("\n" + "=" * 50)
        print("✨ All tests completed!")
        print("=" * 50)


if __name__ == "__main__":
    tester = APITester()
    tester.run_full_test_suite()
