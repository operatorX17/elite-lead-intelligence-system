import requests
import os
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("STEEL_API_KEY")
print(f"API Key: {api_key[:15]}...")

url = "https://api.steel.dev/v1/sessions"
headers = {"steel-api-key": api_key, "Content-Type": "application/json"}
payload = {"useProxy": False, "solveCaptcha": True}

print("Making request...")
try:
    response = requests.post(url, json=payload, headers=headers, timeout=10)
    print(f"Status: {response.status_code}")
    if response.status_code in [200, 201]:
        print("✅ SUCCESS!")
        data = response.json()
        print(f"Session ID: {data.get('id')}")
    else:
        print(f"❌ Failed: {response.text}")
except Exception as e:
    print(f"❌ Error: {e}")
