"""
Quick test for mock discover mode.
"""

import requests
import json

print("Testing Mock Discover Mode")
print("=" * 60)

payload = {
    "niche": "saas",
    "geo": "us",
    "limit": 10,
    "mock": True  # Use mock data for instant response
}

try:
    response = requests.post(
        "http://localhost:8000/api/v1/discover",
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=10  # Should be instant
    )
    
    print(f"Status: {response.status_code}")
    data = response.json()
    
    if response.status_code == 200:
        print(f"✅ SUCCESS!")
        print(f"Leads returned: {data['count']}")
        print(f"Run ID: {data['run_id']}")
        print(f"\nFirst lead:")
        if data['leads']:
            lead = data['leads'][0]
            print(f"  - Company: {lead['company_name']}")
            print(f"  - Domain: {lead['domain']}")
            print(f"  - Niche: {lead['niche']}")
            print(f"  - Geo: {lead['geo']}")
    else:
        print(f"❌ ERROR: {data}")
        
except Exception as e:
    print(f"❌ EXCEPTION: {e}")
