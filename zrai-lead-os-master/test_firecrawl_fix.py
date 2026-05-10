#!/usr/bin/env python
"""
Quick test to verify Firecrawl fix
"""

import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import os
from dotenv import load_dotenv
load_dotenv()  # Load .env file

from src.tools.firecrawl_enrichment import FirecrawlEnrichment
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_firecrawl():
    """Test Firecrawl with fixed API format"""
    
    firecrawl = FirecrawlEnrichment()
    
    # Test with a real healthcare website
    test_url = "https://www.apollodiagnostics.in"
    business_name = "Apollo Diagnostics"
    
    logger.info(f"Testing Firecrawl with {test_url}")
    
    result = await firecrawl.analyze_website(test_url, business_name)
    
    logger.info(f"\n{'='*60}")
    logger.info(f"FIRECRAWL TEST RESULTS")
    logger.info(f"{'='*60}")
    logger.info(f"Status: {result.get('status')}")
    logger.info(f"Booking System: {result.get('has_booking_system')}")
    logger.info(f"WhatsApp: {result.get('has_whatsapp')}")
    logger.info(f"Lead Form: {result.get('has_lead_form')}")
    logger.info(f"Click to Call: {result.get('has_click_to_call')}")
    logger.info(f"Chat Widget: {result.get('has_chat_widget')}")
    logger.info(f"Emails: {result.get('emails', [])}")
    logger.info(f"Phones: {result.get('phones', [])}")
    logger.info(f"{'='*60}\n")
    
    # Verify it's not fallback
    if result.get('status') == 'firecrawl_success':
        logger.info("✅ SUCCESS: Firecrawl is working!")
        return True
    else:
        logger.error("❌ FAILED: Still using fallback")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_firecrawl())
    sys.exit(0 if success else 1)
