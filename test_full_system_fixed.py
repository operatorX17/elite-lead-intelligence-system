#!/usr/bin/env python
"""
Full system test with Firecrawl + Reasoning Agent + Gemini 3 Flash
Tests 2-3 real healthcare leads end-to-end
"""

import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import os
from dotenv import load_dotenv
load_dotenv()

from src.tools.firecrawl_enrichment import FirecrawlEnrichment
from src.agents.reasoning import ReasoningAgent
from src.tools.llm import get_llm_client
import logging
import json

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def test_full_pipeline():
    """Test full pipeline with real leads"""
    
    # Test leads (real healthcare businesses)
    test_leads = [
        {
            "business_name": "Apollo Diagnostics",
            "website": "https://www.apollodiagnostics.in",
            "phone": "+91 30303 13032",
            "category": "Diagnostics",
            "reviews_count": 500,
            "rating": 4.5
        },
        {
            "business_name": "Practo",
            "website": "https://www.practo.com",
            "phone": "+91 80 6811 8880",
            "category": "Healthcare Platform",
            "reviews_count": 1000,
            "rating": 4.3
        }
    ]
    
    logger.info("="*80)
    logger.info("FULL SYSTEM TEST - Firecrawl + Reasoning Agent + Gemini 3 Flash")
    logger.info("="*80)
    
    # Initialize components
    firecrawl = FirecrawlEnrichment()
    llm = get_llm_client()
    reasoning_agent = ReasoningAgent(llm)
    
    results = []
    
    for i, lead in enumerate(test_leads, 1):
        logger.info(f"\n{'='*80}")
        logger.info(f"LEAD {i}/{len(test_leads)}: {lead['business_name']}")
        logger.info(f"{'='*80}")
        
        # Step 1: Enrich with Firecrawl
        logger.info(f"\n[STEP 1] Enriching with Firecrawl...")
        enrichment = await firecrawl.analyze_website(lead['website'], lead['business_name'])
        
        # Merge enrichment data
        lead.update(enrichment)
        
        logger.info(f"[ENRICHMENT] Status: {enrichment.get('status')}")
        logger.info(f"[ENRICHMENT] Booking: {enrichment.get('has_booking_system')}")
        logger.info(f"[ENRICHMENT] WhatsApp: {enrichment.get('has_whatsapp')}")
        logger.info(f"[ENRICHMENT] Emails: {len(enrichment.get('emails', []))}")
        logger.info(f"[ENRICHMENT] Phones: {len(enrichment.get('phones', []))}")
        
        # Step 2: Validate with Reasoning Agent
        logger.info(f"\n[STEP 2] Validating with AI Reasoning Agent...")
        validation = await reasoning_agent.validate_lead(lead)
        
        # Apply corrections
        lead.update(validation.corrections)
        
        logger.info(f"[REASONING] Verdict: {validation.final_verdict}")
        logger.info(f"[REASONING] Confidence: {validation.confidence:.1%}")
        logger.info(f"[REASONING] Final Score: {validation.corrections.get('leak_score')}/100")
        logger.info(f"[REASONING] Priority: {validation.corrections.get('priority')}")
        logger.info(f"[REASONING] Issues: {len(validation.issues_found)}")
        
        # Print detailed reasoning
        logger.info(f"\n[REASONING DETAILS]")
        logger.info(validation.reasoning)
        
        if validation.issues_found:
            logger.info(f"\n[ISSUES FOUND]")
            for issue in validation.issues_found:
                logger.info(f"  - {issue}")
        
        results.append({
            "business_name": lead['business_name'],
            "enrichment_status": enrichment.get('status'),
            "has_real_data": enrichment.get('status') == 'firecrawl_success',
            "emails_found": len(enrichment.get('emails', [])),
            "phones_found": len(enrichment.get('phones', [])),
            "reasoning_verdict": validation.final_verdict,
            "confidence": validation.confidence,
            "final_score": validation.corrections.get('leak_score'),
            "priority": validation.corrections.get('priority'),
            "issues_count": len(validation.issues_found)
        })
    
    # Summary
    logger.info(f"\n{'='*80}")
    logger.info("SUMMARY")
    logger.info(f"{'='*80}")
    
    for result in results:
        logger.info(f"\n{result['business_name']}:")
        logger.info(f"  Enrichment: {result['enrichment_status']}")
        logger.info(f"  Real Data: {result['has_real_data']}")
        logger.info(f"  Contacts: {result['emails_found']} emails, {result['phones_found']} phones")
        logger.info(f"  Verdict: {result['reasoning_verdict']}")
        logger.info(f"  Score: {result['final_score']}/100")
        logger.info(f"  Priority: {result['priority']}")
    
    # Check success criteria
    success_count = sum(1 for r in results if r['has_real_data'])
    hot_count = sum(1 for r in results if r['priority'] == 'HOT')
    
    logger.info(f"\n{'='*80}")
    logger.info(f"SUCCESS METRICS")
    logger.info(f"{'='*80}")
    logger.info(f"Real Data Extracted: {success_count}/{len(results)}")
    logger.info(f"HOT Leads: {hot_count}/{len(results)}")
    
    if success_count == len(results):
        logger.info(f"\n✅ SUCCESS: All leads enriched with real data!")
        return True
    else:
        logger.error(f"\n❌ FAILED: Only {success_count}/{len(results)} leads enriched")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_full_pipeline())
    sys.exit(0 if success else 1)
