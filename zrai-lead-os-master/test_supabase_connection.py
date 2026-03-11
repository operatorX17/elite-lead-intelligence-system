"""
Test Supabase connection and verify database setup.
Run this after setting up Supabase to verify everything works.
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_supabase_connection():
    """Test connection to Supabase."""
    print("=" * 60)
    print("ZRAI Lead OS - Supabase Connection Test")
    print("=" * 60)
    
    # Check environment variables
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    
    print("\n1. Checking environment variables...")
    
    if not supabase_url or supabase_url == "https://your-project.supabase.co":
        print("   ❌ SUPABASE_URL not configured!")
        print("   → Please update your .env file with your Supabase project URL")
        return False
    else:
        print(f"   ✅ SUPABASE_URL: {supabase_url[:40]}...")
    
    if not supabase_key or supabase_key == "your-service-role-key":
        print("   ❌ SUPABASE_SERVICE_ROLE_KEY not configured!")
        print("   → Please update your .env file with your service role key")
        return False
    else:
        print(f"   ✅ SUPABASE_SERVICE_ROLE_KEY: {supabase_key[:20]}...")
    
    # Try to import supabase
    print("\n2. Checking supabase package...")
    try:
        from supabase import create_client, Client
        print("   ✅ supabase package installed")
    except ImportError:
        print("   ❌ supabase package not installed!")
        print("   → Run: pip install supabase")
        return False
    
    # Try to connect
    print("\n3. Connecting to Supabase...")
    try:
        client: Client = create_client(supabase_url, supabase_key)
        print("   ✅ Client created successfully")
    except Exception as e:
        print(f"   ❌ Failed to create client: {e}")
        return False
    
    # Test database query
    print("\n4. Testing database connection...")
    try:
        # Try to query the leads table
        result = client.table("leads").select("lead_id").limit(1).execute()
        print(f"   ✅ Database query successful!")
        print(f"   → Found {len(result.data)} leads in database")
    except Exception as e:
        error_msg = str(e)
        if "relation" in error_msg and "does not exist" in error_msg:
            print("   ❌ Tables not created yet!")
            print("   → Run the migration SQL in Supabase SQL Editor")
            print("   → See SUPABASE_SETUP_GUIDE.md for instructions")
        else:
            print(f"   ❌ Database query failed: {e}")
        return False
    
    # Check all required tables
    print("\n5. Checking required tables...")
    required_tables = [
        "leads", "lead_state", "enrichment_data", "intent_data",
        "proof_artifacts", "scoring_results", "outreach_queue",
        "conversations", "negative_signals", "do_not_contact",
        "audit_log", "usage_metrics", "playbooks", "circuit_breakers"
    ]
    
    missing_tables = []
    for table in required_tables:
        try:
            result = client.table(table).select("*").limit(1).execute()
            print(f"   ✅ {table}")
        except Exception as e:
            print(f"   ❌ {table} - missing or error")
            missing_tables.append(table)
    
    if missing_tables:
        print(f"\n   ⚠️  Missing tables: {', '.join(missing_tables)}")
        print("   → Run the migration SQL to create all tables")
        return False
    
    # Test insert and delete (to verify write permissions)
    print("\n6. Testing write permissions...")
    try:
        # Insert a test record
        test_data = {
            "business_name": "ZRAI Test Business",
            "category": "test",
            "location": "Test Location"
        }
        insert_result = client.table("leads").insert(test_data).execute()
        test_lead_id = insert_result.data[0]["lead_id"]
        print(f"   ✅ Insert successful (lead_id: {test_lead_id[:8]}...)")
        
        # Delete the test record
        client.table("leads").delete().eq("lead_id", test_lead_id).execute()
        print("   ✅ Delete successful")
    except Exception as e:
        print(f"   ❌ Write test failed: {e}")
        return False
    
    print("\n" + "=" * 60)
    print("✅ ALL TESTS PASSED - Supabase is ready!")
    print("=" * 60)
    print("\nNext steps:")
    print("  1. Run: python -m src.cli status")
    print("  2. Run: python -m src.cli dry_run --limit 1")
    print("  3. Run: python -m src.cli run_daily --limit 5")
    
    return True


def check_other_services():
    """Check other configured services."""
    print("\n" + "=" * 60)
    print("Checking Other Services")
    print("=" * 60)
    
    # Gemini
    gemini_key = os.getenv("GOOGLE_API_KEY")
    if gemini_key and gemini_key != "your-gemini-key":
        print(f"✅ Gemini API Key configured")
    else:
        print("⚠️  Gemini API Key not configured")
    
    # Apify
    apify_key = os.getenv("APIFY_API_TOKEN")
    if apify_key and "apify_api" in apify_key:
        print(f"✅ Apify API Token configured")
    else:
        print("⚠️  Apify API Token not configured")
    
    # Steel
    steel_key = os.getenv("STEEL_API_KEY")
    if steel_key and steel_key.startswith("ste-"):
        print(f"✅ Steel API Key configured")
    else:
        print("⚠️  Steel API Key not configured")
    
    # Pinecone
    pinecone_key = os.getenv("PINECONE_API_KEY")
    if pinecone_key and pinecone_key.startswith("pcsk_"):
        print(f"✅ Pinecone API Key configured")
    else:
        print("⚠️  Pinecone API Key not configured")


if __name__ == "__main__":
    success = test_supabase_connection()
    check_other_services()
    
    if not success:
        print("\n❌ Setup incomplete. Please follow SUPABASE_SETUP_GUIDE.md")
        exit(1)
