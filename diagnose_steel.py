#!/usr/bin/env python
"""Diagnose Steel API issue - FIXED VERSION"""
import requests
import os
import json
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("STEEL_API_KEY")

print("=" * 60)
print("STEEL API DIAGNOSTIC TEST")
print("=" * 60)
print(f"\nAPI Key: {api_key[:20]}...{api_key[-10:]}")
print(f"Key length: {len(api_key)}")
print(f"Starts with 'ste-': {api_key.startswith('ste-')}")

# Test with CORRECT header (steel-api-key)
print("\n" + "=" * 60)
print("TEST 1: Create Session (CORRECT HEADER)")
print("=" * 60)
url = "https://api.steel.dev/v1/sessions"
headers = {
    "steel-api-key": api_key,
    "Content-Type": "application/json"
}
payload = {
    "useProxy": False,
    "solveCaptcha": True,
    "sessionTimeout": 60000
}

try:
    response = requests.post(url, json=payload, headers=headers, timeout=15)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
    
    if response.status_code == 200 or response.status_code == 201:
        print("\n✅ SUCCESS! Steel API is working!")
        result = response.json()
        session_id = result.get("id") or result.get("sessionId")
        print(f"Session ID: {session_id}")
        
        # Clean up - release session
        if session_id:
            print(f"\nReleasing session {session_id}...")
            release_url = f"https://api.steel.dev/v1/sessions/{session_id}/release"
            release_response = requests.post(release_url, headers=headers, timeout=10)
            print(f"Release status: {release_response.status_code}")
    else:
        print(f"\n❌ FAILED with status {response.status_code}")
        
except Exception as e:
    print(f"❌ Error: {e}")

# Test with wrong headers for comparison
print("\n" + "=" * 60)
print("TEST 2: Wrong Header (Authorization Bearer) - Should Fail")
print("=" * 60)
headers_wrong = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}
try:
    response = requests.post(url, json=payload, headers=headers_wrong, timeout=10)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text[:200]}")
except Exception as e:
    print(f"Error: {e}")

print("\n" + "=" * 60)
print("DIAGNOSTIC COMPLETE")
print("=" * 60)
