#!/usr/bin/env python
"""Complete Steel API test - verify all functionality"""
import sys
import os
from dotenv import load_dotenv

load_dotenv()

# Test 1: Import Steel client
print("=" * 60)
print("TEST 1: Import Steel Client")
print("=" * 60)
try:
    from src.tools.steel import SteelClient
    print("✅ Steel client imported successfully")
except Exception as e:
    print(f"❌ Failed to import: {e}")
    sys.exit(1)

# Test 2: Initialize client
print("\n" + "=" * 60)
print("TEST 2: Initialize Steel Client")
print("=" * 60)
try:
    client = SteelClient()
    print("✅ Steel client initialized")
except Exception as e:
    print(f"❌ Failed to initialize: {e}")
    sys.exit(1)

# Test 3: Simple scrape
print("\n" + "=" * 60)
print("TEST 3: Simple Scrape (example.com)")
print("=" * 60)
try:
    result = client.scrape("https://example.com", screenshot=True, extract_html=True)
    print(f"✅ Scrape successful!")
    print(f"   - HTML length: {len(result.get('html', ''))}")
    print(f"   - Has screenshot: {bool(result.get('screenshot'))}")
    print(f"   - Screenshot size: {len(result.get('screenshot', '')) // 1024}KB (base64)")
except Exception as e:
    print(f"❌ Scrape failed: {e}")
    sys.exit(1)

# Test 4: Audit landing page (real hospital)
print("\n" + "=" * 60)
print("TEST 4: Audit Landing Page (Real Hospital)")
print("=" * 60)
test_url = "https://www.apollohospitals.com"
try:
    audit_result = client.audit_landing_page(test_url)
    
    if audit_result.get("success"):
        print(f"✅ Audit successful for {test_url}")
        extraction = audit_result.get("extraction_data", {})
        print(f"\n   EXTRACTION RESULTS:")
        print(f"   - Phone numbers found: {len(extraction.get('phone_numbers', []))}")
        print(f"   - Phone visible: {extraction.get('phone_visible')}")
        print(f"   - Form count: {extraction.get('form_count')}")
        print(f"   - Has booking link: {extraction.get('has_booking_link')}")
        print(f"   - Has CTA: {extraction.get('has_cta')}")
        print(f"   - Has business hours: {extraction.get('has_business_hours')}")
        print(f"   - Screenshot captured: {bool(audit_result.get('hero_screenshot'))}")
        
        if extraction.get('phone_numbers'):
            print(f"   - Phone numbers: {extraction['phone_numbers']}")
    else:
        print(f"❌ Audit failed: {audit_result.get('error')}")
        sys.exit(1)
        
except Exception as e:
    print(f"❌ Audit exception: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 5: Session management
print("\n" + "=" * 60)
print("TEST 5: Session Management")
print("=" * 60)
try:
    session = client.create_session()
    session_id = session["session_id"]
    print(f"✅ Session created: {session_id}")
    print(f"   - Status: {session.get('status')}")
    print(f"   - Viewer URL: {session.get('viewer_url')}")
    
    # Release session
    client.close_session(session_id)
    print(f"✅ Session released: {session_id}")
except Exception as e:
    print(f"❌ Session management failed: {e}")
    sys.exit(1)

print("\n" + "=" * 60)
print("🎉 ALL TESTS PASSED! STEEL IS FULLY OPERATIONAL!")
print("=" * 60)
print("\n✅ Steel API key is working correctly")
print("✅ Scraping functionality verified")
print("✅ Landing page audit working")
print("✅ Session management working")
print("\nYou have 5 days left with unlimited credits - USE IT!")
