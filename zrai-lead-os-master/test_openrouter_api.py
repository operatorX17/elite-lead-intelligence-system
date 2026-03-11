#!/usr/bin/env python3
"""
Test OpenRouter API connection and DeepSeek model.
"""

import os
import sys
import json
import urllib.request
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_openrouter_api():
    """Test OpenRouter API with DeepSeek model."""
    print("=" * 60)
    print("🧪 OPENROUTER API TEST")
    print("=" * 60)
    print()
    
    # Get API key
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("❌ OPENROUTER_API_KEY not found in environment")
        return False
    
    print(f"🔑 API Key: {api_key[:20]}...{api_key[-4:]}")
    print(f"🤖 Model: nex-agi/deepseek-v3.1-nex-n1:free")
    print()
    
    # Test request
    url = "https://openrouter.ai/api/v1/chat/completions"
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": "https://zrai-lead-os.com",
        "X-Title": "ZRAI Lead OS",
    }
    
    data = {
        "model": "nex-agi/deepseek-v3.1-nex-n1:free",
        "messages": [
            {
                "role": "system",
                "content": "You are a helpful AI assistant for lead intelligence."
            },
            {
                "role": "user",
                "content": "Hello! Can you help me analyze business leads? Please respond with a brief confirmation."
            }
        ],
        "temperature": 0.7,
        "max_tokens": 100
    }
    
    try:
        print("🔍 Testing OpenRouter API connection...")
        
        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode(),
            headers=headers,
            method="POST",
        )
        
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode())
        
        if "choices" in result and result["choices"]:
            response_text = result["choices"][0]["message"]["content"]
            print("✅ SUCCESS! OpenRouter API is working!")
            print()
            print("🤖 Model Response:")
            print(f"   {response_text}")
            print()
            
            # Show usage info if available
            if "usage" in result:
                usage = result["usage"]
                print("📊 Token Usage:")
                print(f"   Prompt tokens: {usage.get('prompt_tokens', 'N/A')}")
                print(f"   Completion tokens: {usage.get('completion_tokens', 'N/A')}")
                print(f"   Total tokens: {usage.get('total_tokens', 'N/A')}")
            
            return True
        else:
            print("❌ No response from model")
            print(f"📄 Full response: {result}")
            return False
            
    except urllib.error.HTTPError as e:
        print(f"❌ HTTP Error {e.code}: {e.reason}")
        try:
            error_body = e.read().decode()
            error_data = json.loads(error_body)
            print(f"📄 Error details: {json.dumps(error_data, indent=2)}")
        except:
            print(f"📄 Raw error: {error_body}")
        return False
        
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False

if __name__ == "__main__":
    success = test_openrouter_api()
    
    print()
    print("=" * 60)
    if success:
        print("✅ TEST PASSED - OpenRouter is ready!")
        print()
        print("🎉 You can now use OpenRouter with DeepSeek in ZRAI Lead OS!")
    else:
        print("❌ TEST FAILED - Please check your API key")
    print()
    
    sys.exit(0 if success else 1)