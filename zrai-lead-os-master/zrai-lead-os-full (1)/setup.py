"""
Setup script for ZRAI Lead OS.
Helps with initial project setup and verification.
"""

import os
import sys
from pathlib import Path


def check_python_version():
    """Check Python version is 3.11+"""
    if sys.version_info < (3, 11):
        print("❌ Python 3.11+ required")
        print(f"   Current version: {sys.version}")
        return False
    print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor}")
    return True


def check_env_file():
    """Check if .env file exists"""
    if not Path(".env").exists():
        print("❌ .env file not found")
        print("   Run: cp .env.example .env")
        print("   Then edit .env with your API keys")
        return False
    print("✅ .env file exists")
    return True


def check_env_variables():
    """Check required environment variables"""
    from dotenv import load_dotenv
    load_dotenv()
    
    required = [
        "SUPABASE_URL",
        "SUPABASE_SERVICE_ROLE_KEY",
        "GOOGLE_API_KEY",
        "APIFY_API_TOKEN",
        "STEEL_API_KEY",
        "PINECONE_API_KEY",
    ]
    
    missing = []
    for var in required:
        if not os.getenv(var) or os.getenv(var).startswith("your-"):
            missing.append(var)
    
    if missing:
        print(f"❌ Missing or placeholder environment variables:")
        for var in missing:
            print(f"   - {var}")
        return False
    
    print("✅ All required environment variables set")
    return True


def check_dependencies():
    """Check if dependencies are installed"""
    try:
        import langgraph
        import supabase
        import apify_client
        import pinecone
        import click
        print("✅ Core dependencies installed")
        return True
    except ImportError as e:
        print(f"❌ Missing dependencies: {e}")
        print("   Run: pip install -r requirements.txt")
        return False


def check_config_files():
    """Check if config files exist"""
    config_files = [
        "config/niches.yaml",
        "config/policies.yaml",
        "config/agents.yaml",
        "config/budgets.yaml",
    ]
    
    missing = []
    for file in config_files:
        if not Path(file).exists():
            missing.append(file)
    
    if missing:
        print(f"❌ Missing config files:")
        for file in missing:
            print(f"   - {file}")
        return False
    
    print("✅ All config files present")
    return True


def test_supabase_connection():
    """Test Supabase connection"""
    try:
        from src.db.client import get_supabase_client
        client = get_supabase_client()
        # Try a simple query
        result = client.client.table("leads").select("lead_id").limit(1).execute()
        print("✅ Supabase connection successful")
        return True
    except Exception as e:
        print(f"❌ Supabase connection failed: {e}")
        print("   Check your SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY")
        print("   Make sure migrations have been run")
        return False


def test_gemini_api():
    """Test Gemini API"""
    try:
        import google.generativeai as genai
        genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
        model = genai.GenerativeModel("gemini-2.0-flash-exp")
        response = model.generate_content("Hello")
        print("✅ Gemini API working")
        return True
    except Exception as e:
        print(f"❌ Gemini API failed: {e}")
        print("   Check your GOOGLE_API_KEY")
        return False


def test_apify_connection():
    """Test Apify connection"""
    try:
        from apify_client import ApifyClient
        client = ApifyClient(os.getenv("APIFY_API_TOKEN"))
        user = client.user().get()
        print(f"✅ Apify connection successful (user: {user.get('username')})")
        return True
    except Exception as e:
        print(f"❌ Apify connection failed: {e}")
        print("   Check your APIFY_API_TOKEN")
        return False


def test_pinecone_connection():
    """Test Pinecone connection"""
    try:
        from pinecone import Pinecone
        pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
        indexes = pc.list_indexes()
        index_name = os.getenv("PINECONE_INDEX_NAME", "zrai-playbooks")
        
        if index_name in [idx.name for idx in indexes]:
            print(f"✅ Pinecone connection successful (index: {index_name})")
            return True
        else:
            print(f"⚠️  Pinecone connected but index '{index_name}' not found")
            print("   Run: python setup_pinecone_index.py")
            return False
    except Exception as e:
        print(f"❌ Pinecone connection failed: {e}")
        print("   Check your PINECONE_API_KEY")
        return False


def main():
    """Run all setup checks"""
    print("=" * 60)
    print("ZRAI Lead OS - Setup Verification")
    print("=" * 60)
    print()
    
    checks = [
        ("Python Version", check_python_version),
        ("Environment File", check_env_file),
        ("Dependencies", check_dependencies),
        ("Config Files", check_config_files),
    ]
    
    # Run basic checks
    all_passed = True
    for name, check_func in checks:
        print(f"\n{name}:")
        if not check_func():
            all_passed = False
    
    if not all_passed:
        print("\n" + "=" * 60)
        print("❌ Setup incomplete. Please fix the issues above.")
        print("=" * 60)
        sys.exit(1)
    
    # Check environment variables
    print("\nEnvironment Variables:")
    if not check_env_variables():
        print("\n" + "=" * 60)
        print("❌ Environment variables not configured.")
        print("=" * 60)
        sys.exit(1)
    
    # Test connections
    print("\n" + "=" * 60)
    print("Testing Connections...")
    print("=" * 60)
    
    connection_checks = [
        ("Supabase", test_supabase_connection),
        ("Gemini API", test_gemini_api),
        ("Apify", test_apify_connection),
        ("Pinecone", test_pinecone_connection),
    ]
    
    connections_passed = True
    for name, check_func in connection_checks:
        print(f"\n{name}:")
        if not check_func():
            connections_passed = False
    
    print("\n" + "=" * 60)
    if connections_passed:
        print("✅ All checks passed! System ready.")
        print("\nNext steps:")
        print("  1. Run: python -m src.cli status")
        print("  2. Try: python -m src.cli dry_run --limit 5")
        print("  3. Run: python -m src.cli run_daily --limit 10")
    else:
        print("⚠️  Some connection tests failed.")
        print("   Fix the issues above before running the system.")
    print("=" * 60)


if __name__ == "__main__":
    main()
