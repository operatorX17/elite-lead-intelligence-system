#!/usr/bin/env python
"""
Test Firecrawl REST API directly
"""

import asyncio
import os
from dotenv import load_dotenv
load_dotenv()

from src.tools.firecrawl_enrichment import FirecrawlEnrichment


async def test_firecrawl():
    """Test Firecrawl scraping"""
    
    print("=" * 60)
    print("FIRECRAWL REST API TEST")
    print("=" * 60)
    
    # Check API key
    api_key = os.getenv("FIRECRAWL_API_KEY")
    if not api_key or api_key == "your-firecrawl-api-key-here":
        print("\n❌ FIRECRAWL_API_KEY not set in .env")
        print("\nTo get your API key:")
        print("1. Go to https://firecrawl.dev")
        print("2. Sign up for free account")
        print("3. Copy your API key")
        print("4. Add to .env: FIRECRAWL_API_KEY=fc-xxx")
        return
    
    print(f"\n✓ API key found: {api_key[:20]}...")
    
    # Test websites
    test_sites = [
        ("https://www.redcliffelabs.com/", "Redcliffe Labs"),
        ("https://www.orangehealth.in/", "Orange Health"),
        ("https://www.aarthiscan.com/", "Aarthi Scans")
    ]
    
    firecrawl = FirecrawlEnrichment()
    
    for url, name in test_sites:
        print(f"\n{'=' * 60}")
        print(f"Testing: {name}")
        print(f"URL: {url}")
        print(f"{'=' * 60}")
        
        try:
            signals = await firecrawl.analyze_website(url, name)
            
            print(f"\nStatus: {signals.get('status')}")
            print(f"Booking System: {signals.get('has_booking_system')}")
            print(f"WhatsApp: {signals.get('has_whatsapp')}")
            print(f"Lead Form: {signals.get('has_lead_form')}")
            print(f"Click-to-Call: {signals.get('has_click_to_call')}")
            print(f"Chat Widget: {signals.get('has_chat_widget')}")
            print(f"Emails: {signals.get('emails', [])}")
            print(f"Phones: {signals.get('phones', [])}")
            
            if signals.get('status') == 'firecrawl_success':
                print("\n✅ FIRECRAWL WORKING!")
            else:
                print(f"\n⚠️  Using fallback mode")
                
        except Exception as e:
            print(f"\n❌ Error: {e}")
    
    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_firecrawl())
