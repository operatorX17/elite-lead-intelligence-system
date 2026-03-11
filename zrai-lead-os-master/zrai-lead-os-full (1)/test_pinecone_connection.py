#!/usr/bin/env python3
"""
Test script to verify Pinecone connection is working correctly.
"""
import os
import sys

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

# Configuration from .env
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY", "your-pinecone-api-key-here")
INDEX_NAME = "zrai-playbooks"

def test_with_pinecone_library():
    """Test using Pinecone library"""
    try:
        from pinecone import Pinecone
        
        print("🔍 Testing Pinecone connection...")
        print(f"📦 Index: {INDEX_NAME}")
        print(f"🔑 API Key: {PINECONE_API_KEY[:20]}...{PINECONE_API_KEY[-4:]}")
        print()
        
        # Initialize Pinecone
        pc = Pinecone(api_key=PINECONE_API_KEY)
        
        # List indexes
        print("📋 Listing all indexes...")
        indexes = pc.list_indexes()
        index_names = [idx.name for idx in indexes]
        print(f"   Found indexes: {index_names}")
        print()
        
        if INDEX_NAME not in index_names:
            print(f"❌ Index '{INDEX_NAME}' not found!")
            print(f"   Available indexes: {index_names}")
            return False
        
        # Connect to index
        print(f"🔌 Connecting to index '{INDEX_NAME}'...")
        index = pc.Index(INDEX_NAME)
        
        # Get stats
        print("📊 Fetching index statistics...")
        stats = index.describe_index_stats()
        
        print("\n✅ SUCCESS! Pinecone connection is working!")
        print("\n📊 Index Statistics:")
        print(f"   - Total vectors: {stats.get('total_vector_count', 0)}")
        print(f"   - Dimension: {stats.get('dimension', 'N/A')}")
        print(f"   - Index fullness: {stats.get('index_fullness', 0)}")
        print(f"   - Namespaces: {list(stats.get('namespaces', {}).keys()) or ['default']}")
        
        # Test upsert (optional - commented out to avoid adding test data)
        # print("\n🧪 Testing vector upsert...")
        # test_vector = [0.1] * 768  # 768-dimensional test vector
        # index.upsert(vectors=[("test-id", test_vector, {"test": "true"})])
        # print("   ✅ Upsert successful!")
        
        return True
        
    except ImportError:
        print("❌ Pinecone library not installed")
        print("\n📦 Install it with:")
        print("   pip install pinecone-client")
        return None
        
    except Exception as e:
        print(f"\n❌ Error: {type(e).__name__}: {e}")
        
        if "Unauthorized" in str(e) or "401" in str(e):
            print("\n💡 This means:")
            print("   - Your API key is invalid or expired")
            print("   - Check your PINECONE_API_KEY in .env file")
        elif "404" in str(e) or "not found" in str(e).lower():
            print("\n💡 This means:")
            print("   - The index name might be incorrect")
            print("   - Or the index hasn't finished initializing")
        
        return False

def test_with_http():
    """Test using HTTP API (fallback)"""
    import json
    try:
        import urllib.request
        
        print("🔍 Testing Pinecone connection via HTTP API...")
        
        url = "https://api.pinecone.io/indexes"
        
        headers = {
            'Api-Key': PINECONE_API_KEY,
            'Content-Type': 'application/json'
        }
        
        req = urllib.request.Request(url, headers=headers, method='GET')
        
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode('utf-8'))
            
            print("\n✅ API connection successful!")
            print("\n📋 Available indexes:")
            
            if 'indexes' in result:
                for idx in result['indexes']:
                    name = idx.get('name', 'unknown')
                    status = idx.get('status', {}).get('state', 'unknown')
                    print(f"   - {name} (status: {status})")
                    
                    if name == INDEX_NAME:
                        print(f"\n✅ Found '{INDEX_NAME}' index!")
                        print(f"   Status: {status}")
                        print(f"   Dimension: {idx.get('dimension', 'N/A')}")
                        print(f"   Metric: {idx.get('metric', 'N/A')}")
                        return True
            
            print(f"\n⚠️  Index '{INDEX_NAME}' not found in list")
            return False
            
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        print(f"\n❌ HTTP Error {e.code}: {e.reason}")
        print(f"📄 Error details: {error_body}")
        return False
        
    except Exception as e:
        print(f"\n❌ Error: {type(e).__name__}: {e}")
        return False

def main():
    print("=" * 60)
    print("🧪 PINECONE CONNECTION TEST")
    print("=" * 60)
    print()
    
    if PINECONE_API_KEY == "your-pinecone-api-key-here":
        print("❌ Please set your PINECONE_API_KEY")
        print("\nOptions:")
        print("1. Set environment variable:")
        print("   export PINECONE_API_KEY=your-actual-key")
        print("\n2. Or update the .env file with your actual API key")
        sys.exit(1)
    
    # Try with library first
    result = test_with_pinecone_library()
    
    # If library not available, try HTTP
    if result is None:
        print("\n" + "-" * 60)
        print()
        result = test_with_http()
    
    print("\n" + "=" * 60)
    
    if result:
        print("✅ TEST PASSED - Pinecone is ready!")
        print("\n📋 Your configuration:")
        print(f"   PINECONE_API_KEY={PINECONE_API_KEY[:20]}...{PINECONE_API_KEY[-4:]}")
        print(f"   PINECONE_INDEX_NAME={INDEX_NAME}")
        print(f"   PINECONE_ENVIRONMENT=us-east-1")
        print("\n🎉 You can now use Pinecone in ZRAI Lead OS!")
        sys.exit(0)
    else:
        print("❌ TEST FAILED - Please check your configuration")
        sys.exit(1)

if __name__ == "__main__":
    main()
