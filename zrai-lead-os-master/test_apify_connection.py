#!/usr/bin/env python3
"""
Test script to verify Apify API connection is working correctly.
"""
import os
import sys
import json

# Load .env file
def load_env():
    """Load environment variables from .env file"""
    env_path = ".env"
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()

load_env()

APIFY_API_TOKEN = os.getenv("APIFY_API_TOKEN", "your-apify-token-here")

def test_apify_connection():
    """Test Apify API connection"""
    try:
        import urllib.request
        
        print("🔍 Testing Apify API connection...")
        print(f"🔑 API Token: {APIFY_API_TOKEN[:20]}...{APIFY_API_TOKEN[-4:]}")
        print()
        
        # Test API by getting user info
        url = "https://api.apify.com/v2/users/me"
        
        headers = {
            'Authorization': f'Bearer {APIFY_API_TOKEN}',
            'Content-Type': 'application/json'
        }
        
        req = urllib.request.Request(url, headers=headers, method='GET')
        
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode('utf-8'))
            
            if 'data' in result:
                user_data = result['data']
                print("✅ SUCCESS! Apify API is working!")
                print()
                print("👤 Account Info:")
                print(f"   - Username: {user_data.get('username', 'N/A')}")
                print(f"   - Email: {user_data.get('email', 'N/A')}")
                print(f"   - Plan: {user_data.get('plan', {}).get('id', 'N/A')}")
                
                # Get usage info
                usage = user_data.get('limits', {})
                print()
                print("📊 Usage Limits:")
                print(f"   - Monthly usage: ${user_data.get('currentMonthUsage', {}).get('usd', 0):.2f}")
                
                return True
            else:
                print("❌ Unexpected response format")
                print(json.dumps(result, indent=2))
                return False
                
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        print(f"❌ HTTP Error {e.code}: {e.reason}")
        print(f"📄 Error details: {error_body}")
        
        if e.code == 401:
            print("\n💡 This means:")
            print("   - Your API token is invalid or expired")
            print("   - Check your APIFY_API_TOKEN in .env file")
        
        return False
        
    except Exception as e:
        print(f"❌ Error: {type(e).__name__}: {e}")
        return False

def main():
    print("=" * 60)
    print("🧪 APIFY API CONNECTION TEST")
    print("=" * 60)
    print()
    
    if APIFY_API_TOKEN == "your-apify-token-here":
        print("❌ Please set your APIFY_API_TOKEN in .env file")
        sys.exit(1)
    
    result = test_apify_connection()
    
    print()
    print("=" * 60)
    
    if result:
        print("✅ TEST PASSED - Apify is ready!")
        print("\n🎉 You can now use Apify for web scraping in ZRAI Lead OS!")
        sys.exit(0)
    else:
        print("❌ TEST FAILED - Please check your API token")
        sys.exit(1)

if __name__ == "__main__":
    main()
