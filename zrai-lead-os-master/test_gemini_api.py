#!/usr/bin/env python3
"""
Test script to verify Gemini API key is working correctly.
"""
import os
import sys

# Your Gemini API key from AI Studio
GEMINI_API_KEY = "AIzaSyA8NpB7JajJupGHYxx-q-Py9WwodSpIwnk"

def test_with_requests():
    """Test using direct HTTP requests (no dependencies needed)"""
    import json
    try:
        import urllib.request
        
        url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
        
        headers = {
            'Content-Type': 'application/json',
            'x-goog-api-key': GEMINI_API_KEY
        }
        
        data = {
            "contents": [{
                "parts": [{
                    "text": "Say 'Hello! The Gemini API is working!' in exactly those words."
                }]
            }]
        }
        
        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode('utf-8'),
            headers=headers,
            method='POST'
        )
        
        print("🔍 Testing Gemini API key...")
        print(f"📡 Endpoint: {url}")
        print(f"🔑 API Key: {GEMINI_API_KEY[:20]}...{GEMINI_API_KEY[-4:]}")
        print()
        
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode('utf-8'))
            
            if 'candidates' in result and len(result['candidates']) > 0:
                text = result['candidates'][0]['content']['parts'][0]['text']
                print("✅ SUCCESS! Gemini API is working!")
                print(f"📝 Response: {text}")
                print()
                print("✨ Your API key is valid and ready to use!")
                return True
            else:
                print("❌ Unexpected response format")
                print(json.dumps(result, indent=2))
                return False
                
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        print(f"❌ HTTP Error {e.code}: {e.reason}")
        print(f"📄 Error details: {error_body}")
        
        if e.code == 400:
            print("\n💡 This might mean:")
            print("   - The API key format is correct but may be invalid/expired")
            print("   - The model name might be incorrect")
        elif e.code == 403:
            print("\n💡 This means:")
            print("   - The API key is invalid or doesn't have permission")
            print("   - You may need to enable the Gemini API in your Google Cloud project")
        
        return False
        
    except Exception as e:
        print(f"❌ Error: {type(e).__name__}: {e}")
        return False

def test_with_google_genai():
    """Test using the official Google GenAI library (if available)"""
    try:
        from google import genai
        
        print("🔍 Testing with official google-genai library...")
        client = genai.Client(api_key=GEMINI_API_KEY)
        
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents="Say 'Hello! The Gemini API is working!' in exactly those words."
        )
        
        print("✅ SUCCESS with google-genai library!")
        print(f"📝 Response: {response.text}")
        return True
        
    except ImportError:
        print("ℹ️  google-genai library not installed (that's okay, using HTTP instead)")
        return None
    except Exception as e:
        print(f"❌ Error with google-genai: {type(e).__name__}: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("🧪 GEMINI API KEY TEST")
    print("=" * 60)
    print()
    
    # Try with official library first
    result = test_with_google_genai()
    
    # If library not available or failed, try with HTTP
    if result is None or result is False:
        print()
        print("-" * 60)
        print()
        result = test_with_requests()
    
    print()
    print("=" * 60)
    
    if result:
        print("🎉 TEST PASSED - Your Gemini API key is working!")
        print()
        print("📋 Configuration for .env file:")
        print(f"   GOOGLE_API_KEY={GEMINI_API_KEY}")
        print(f"   DEFAULT_LLM_PROVIDER=google")
        print(f"   DEFAULT_LLM_MODEL=gemini-2.5-flash")
        sys.exit(0)
    else:
        print("❌ TEST FAILED - Please check your API key")
        sys.exit(1)
