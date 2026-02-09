#!/usr/bin/env python
"""Test Steel API with correct header"""
import requests
import os
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("STEEL_API_KEY")
print(f"Testing Steel API...")
print(f"Key: {api_key[:15]}...{api_key[-8:]}")

url = "https://api.steel.dev/v1/sessions"
headers = {
    "steel-api-key": api_key,
    "Content-Type": "application/json"
}
payload = {"useProxy": False, "solveCaptcha": True}

response = requests.post(url, json=payload, headers=headers, timeout=15)
print(f"Status: {response.status_code}")
print(f"Response: {response.text}")

if response.status_code in [200, 201]:
    print("\n✅ SUCCESS! Steel is working!")
else:
    print(f"\n❌ Failed: {response.status_code}")
