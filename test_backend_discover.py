"""
Test script to diagnose the discover leads issue.
"""

import requests
import json

# Test 1: Check if backend is running
print("=" * 60)
print("TEST 1: Backend Health Check")
print("=" * 60)

try:
    response = requests.get("http://localhost:8000/health", timeout=5)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
except Exception as e:
    print(f"ERROR: {e}")
    print("\n⚠️  Backend is NOT running on port 8000!")
    print("Start it with: python run.py")
    exit(1)

# Test 2: Check metrics endpoint
print("\n" + "=" * 60)
print("TEST 2: Metrics Endpoint")
print("=" * 60)

try:
    response = requests.get("http://localhost:8000/api/v1/metrics", timeout=5)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
except Exception as e:
    print(f"ERROR: {e}")

# Test 3: Try discover endpoint
print("\n" + "=" * 60)
print("TEST 3: Discover Leads Endpoint")
print("=" * 60)

payload = {
    "niche": "saas",
    "geo": "us",
    "limit": 5
}

print(f"Request: POST http://localhost:8000/api/v1/discover")
print(f"Payload: {json.dumps(payload, indent=2)}")

try:
    response = requests.post(
        "http://localhost:8000/api/v1/discover",
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=60
    )
    print(f"\nStatus Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    
    if response.status_code == 200:
        data = response.json()
        if data.get("leads"):
            print(f"\n✅ SUCCESS: Got {len(data['leads'])} leads")
        else:
            print(f"\n⚠️  WARNING: Response OK but no leads returned")
    else:
        print(f"\n❌ ERROR: Backend returned error status")
        
except Exception as e:
    print(f"\n❌ ERROR: {e}")

# Test 4: Check frontend API route
print("\n" + "=" * 60)
print("TEST 4: Frontend API Route (if frontend is running)")
print("=" * 60)

try:
    response = requests.post(
        "http://localhost:3000/api/zrai/discover",
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=60
    )
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    
    if response.status_code == 200:
        data = response.json()
        if data.get("success") and data.get("data", {}).get("leads"):
            print(f"\n✅ SUCCESS: Frontend API working, got {len(data['data']['leads'])} leads")
        else:
            print(f"\n⚠️  WARNING: Frontend API responded but no leads")
    else:
        print(f"\n❌ ERROR: Frontend API returned error")
        
except Exception as e:
    print(f"\n⚠️  Frontend not running or error: {e}")
    print("Start it with: cd frontend && pnpm dev")

print("\n" + "=" * 60)
print("DIAGNOSIS COMPLETE")
print("=" * 60)
