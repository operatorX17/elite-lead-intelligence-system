#!/usr/bin/env python3
"""
Script to create and configure Pinecone index for ZRAI Lead OS playbooks.
This script will create the index if it doesn't exist.
"""
import os
import sys

# Configuration
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY", "your-pinecone-key-here")
INDEX_NAME = "zrai-playbooks"
DIMENSION = 768  # For Google text-embedding-004 model
METRIC = "cosine"
CLOUD = "aws"
REGION = "us-east-1"

def check_pinecone_installation():
    """Check if pinecone library is installed"""
    try:
        import pinecone
        return True
    except ImportError:
        print("❌ Pinecone library not installed")
        print("\n📦 Install it with:")
        print("   pip install pinecone-client")
        print("   or")
        print("   pip install 'pinecone-client[grpc]'")
        return False

def create_index_with_pinecone():
    """Create index using Pinecone library"""
    try:
        from pinecone import Pinecone, ServerlessSpec
        
        print("🔍 Initializing Pinecone client...")
        pc = Pinecone(api_key=PINECONE_API_KEY)
        
        # List existing indexes
        existing_indexes = pc.list_indexes()
        index_names = [idx.name for idx in existing_indexes]
        
        print(f"\n📋 Existing indexes: {index_names if index_names else 'None'}")
        
        if INDEX_NAME in index_names:
            print(f"\n✅ Index '{INDEX_NAME}' already exists!")
            
            # Get index info
            index = pc.Index(INDEX_NAME)
            stats = index.describe_index_stats()
            print(f"\n📊 Index Stats:")
            print(f"   - Total vectors: {stats.get('total_vector_count', 0)}")
            print(f"   - Dimension: {stats.get('dimension', 'N/A')}")
            print(f"   - Index fullness: {stats.get('index_fullness', 0)}")
            
            return True
        
        print(f"\n🔨 Creating index '{INDEX_NAME}'...")
        print(f"   - Dimension: {DIMENSION}")
        print(f"   - Metric: {METRIC}")
        print(f"   - Cloud: {CLOUD}")
        print(f"   - Region: {REGION}")
        
        pc.create_index(
            name=INDEX_NAME,
            dimension=DIMENSION,
            metric=METRIC,
            spec=ServerlessSpec(
                cloud=CLOUD,
                region=REGION
            )
        )
        
        print(f"\n✅ Index '{INDEX_NAME}' created successfully!")
        print("\n⏳ Note: It may take a few moments for the index to be fully ready.")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {type(e).__name__}: {e}")
        return False

def create_index_with_http():
    """Create index using direct HTTP API (fallback)"""
    import json
    try:
        import urllib.request
        
        print("🔍 Creating index via HTTP API...")
        
        url = "https://api.pinecone.io/indexes"
        
        headers = {
            'Api-Key': PINECONE_API_KEY,
            'Content-Type': 'application/json'
        }
        
        data = {
            "name": INDEX_NAME,
            "dimension": DIMENSION,
            "metric": METRIC,
            "spec": {
                "serverless": {
                    "cloud": CLOUD,
                    "region": REGION
                }
            }
        }
        
        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode('utf-8'),
            headers=headers,
            method='POST'
        )
        
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode('utf-8'))
            print(f"\n✅ Index created successfully!")
            print(json.dumps(result, indent=2))
            return True
            
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        print(f"\n❌ HTTP Error {e.code}: {e.reason}")
        print(f"📄 Error details: {error_body}")
        
        if e.code == 409:
            print("\n💡 Index already exists!")
            return True
        elif e.code == 401:
            print("\n💡 Invalid API key. Please check your PINECONE_API_KEY")
        
        return False
        
    except Exception as e:
        print(f"\n❌ Error: {type(e).__name__}: {e}")
        return False

def print_manual_instructions():
    """Print manual setup instructions"""
    print("\n" + "="*60)
    print("📖 MANUAL SETUP INSTRUCTIONS")
    print("="*60)
    print("\nIf you prefer to create the index manually in the Pinecone UI:")
    print("\n1. Go to: https://app.pinecone.io/")
    print("2. Click 'Create Index'")
    print(f"3. Index name: {INDEX_NAME}")
    print(f"4. Dimensions: {DIMENSION}")
    print(f"5. Metric: {METRIC}")
    print("6. Capacity mode: Serverless")
    print(f"7. Cloud provider: {CLOUD.upper()}")
    print(f"8. Region: {REGION}")
    print("\n9. Click 'Create Index'")
    print("\n" + "="*60)
    print("\n💡 Embedding Model Dimensions:")
    print("   - Google text-embedding-004: 768")
    print("   - OpenAI text-embedding-3-small: 1536")
    print("   - OpenAI text-embedding-3-large: 3072")
    print("   - OpenAI text-embedding-ada-002: 1536")
    print("\n⚠️  Make sure the dimension matches your embedding model!")

def main():
    print("="*60)
    print("🚀 PINECONE INDEX SETUP FOR ZRAI LEAD OS")
    print("="*60)
    print()
    
    if PINECONE_API_KEY == "your-pinecone-key-here":
        print("❌ Please set your PINECONE_API_KEY")
        print("\nOptions:")
        print("1. Set environment variable:")
        print("   export PINECONE_API_KEY=your-actual-key")
        print("\n2. Or edit this script and replace the API key")
        print_manual_instructions()
        sys.exit(1)
    
    print(f"🔑 API Key: {PINECONE_API_KEY[:20]}...{PINECONE_API_KEY[-4:]}")
    print(f"📦 Index Name: {INDEX_NAME}")
    print()
    
    # Try with library first
    if check_pinecone_installation():
        success = create_index_with_pinecone()
    else:
        print("\n⚠️  Pinecone library not available, trying HTTP API...")
        success = create_index_with_http()
    
    if success:
        print("\n" + "="*60)
        print("✅ SETUP COMPLETE!")
        print("="*60)
        print("\n📋 Add to your .env file:")
        print(f"   PINECONE_API_KEY={PINECONE_API_KEY}")
        print(f"   PINECONE_INDEX_NAME={INDEX_NAME}")
        print(f"   PINECONE_ENVIRONMENT={REGION}")
        print("\n🎉 Your Pinecone index is ready for ZRAI Lead OS!")
    else:
        print_manual_instructions()
        sys.exit(1)

if __name__ == "__main__":
    main()
