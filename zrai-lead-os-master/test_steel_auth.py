"""
Test Steel API authentication methods
"""

import os
import asyncio
import aiohttp
from dotenv import load_dotenv

load_dotenv()

STEEL_API_KEY = os.getenv("STEEL_API_KEY")
STEEL_API_URL = "https://api.steel.dev/v1"


async def test_auth_method(method_name: str, headers: dict):
    """Test a specific authentication method"""
    
    print(f"\n{'='*60}")
    print(f"Testing: {method_name}")
    print(f"Headers: {headers}")
    print(f"{'='*60}")
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{STEEL_API_URL}/sessions",
                headers=headers,
                json={
                    "useProxy": True,
                    "solveCaptchas": True,
                    "sessionTimeout": 600000
                },
                timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                status = resp.status
                text = await resp.text()
                
                print(f"Status: {status}")
                print(f"Response: {text[:500]}")
                
                if status in [200, 201]:
                    print(f"✅ SUCCESS with {method_name}!")
                    return True
                else:
                    print(f"❌ FAILED with {method_name}")
                    return False
                    
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False


async def main():
    """Test all authentication methods"""
    
    print(f"Steel API Key: {STEEL_API_KEY[:20]}...")
    print(f"API URL: {STEEL_API_URL}")
    
    # Method 1: Authorization Bearer
    await test_auth_method(
        "Authorization: Bearer",
        {
            "Authorization": f"Bearer {STEEL_API_KEY}",
            "Content-Type": "application/json"
        }
    )
    
    # Method 2: X-API-Key
    await test_auth_method(
        "X-API-Key",
        {
            "X-API-Key": STEEL_API_KEY,
            "Content-Type": "application/json"
        }
    )
    
    # Method 3: steel-api-key
    await test_auth_method(
        "steel-api-key",
        {
            "steel-api-key": STEEL_API_KEY,
            "Content-Type": "application/json"
        }
    )
    
    # Method 4: x-steel-api-key
    await test_auth_method(
        "x-steel-api-key",
        {
            "x-steel-api-key": STEEL_API_KEY,
            "Content-Type": "application/json"
        }
    )
    
    # Method 5: api-key
    await test_auth_method(
        "api-key",
        {
            "api-key": STEEL_API_KEY,
            "Content-Type": "application/json"
        }
    )
    
    # Method 6: apikey
    await test_auth_method(
        "apikey",
        {
            "apikey": STEEL_API_KEY,
            "Content-Type": "application/json"
        }
    )
    
    # Method 7: Steel-API-Key (capitalized)
    await test_auth_method(
        "Steel-API-Key",
        {
            "Steel-API-Key": STEEL_API_KEY,
            "Content-Type": "application/json"
        }
    )
    
    # Method 8: No auth (just to see error message)
    await test_auth_method(
        "No Auth",
        {
            "Content-Type": "application/json"
        }
    )


if __name__ == "__main__":
    asyncio.run(main())
