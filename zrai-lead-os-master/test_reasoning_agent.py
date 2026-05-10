#!/usr/bin/env python
"""
Quick test of AI Reasoning Agent
"""

import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

from src.agents.reasoning import ReasoningAgent
from src.tools.llm import get_llm_client


async def test_reasoning():
    """Test the reasoning agent with sample leads"""
    
    llm = get_llm_client()
    reasoning_agent = ReasoningAgent(llm)
    
    # Test Case 1: GOOD lead (real data, reachable, opportunity)
    good_lead = {
        "business_name": "Lotus Diagnostic Centre",
        "website": "http://lotusdiagnostic.com/",
        "phone": "+91 90993 90993",
        "emails": ["lotusdiagnostic@gmail.com"],
        "status": "firecrawl_success",
        "has_booking_system": True,
        "has_whatsapp": True,
        "has_lead_form": True,
        "reviews_count": 150,
        "rating": 4.5
    }
    
    # Test Case 2: BAD lead (fallback data, no contact info)
    bad_lead = {
        "business_name": "Redcliffe Labs",
        "website": "https://redcliffelabs.com/",
        "phone": "+91 89889 88787",
        "emails": [],
        "status": "fallback",
        "has_booking_system": False,
        "has_whatsapp": False,
        "has_lead_form": True,
        "reviews_count": None,
        "rating": None
    }
    
    # Test Case 3: UNREACHABLE lead (no website, no contact)
    unreachable_lead = {
        "business_name": "Acclin Path Labs",
        "website": None,
        "phone": None,
        "emails": [],
        "status": "no_website",
        "has_booking_system": False,
        "has_whatsapp": False,
        "has_lead_form": False,
        "reviews_count": None,
        "rating": None
    }
    
    print("\n" + "="*80)
    print("TEST 1: GOOD LEAD (Real data + Reachable + Opportunity)")
    print("="*80)
    result1 = await reasoning_agent.validate_lead(good_lead)
    print(reasoning_agent.explain_decision(result1))
    
    print("\n" + "="*80)
    print("TEST 2: BAD LEAD (Fallback data + No contact info)")
    print("="*80)
    result2 = await reasoning_agent.validate_lead(bad_lead)
    print(reasoning_agent.explain_decision(result2))
    
    print("\n" + "="*80)
    print("TEST 3: UNREACHABLE LEAD (No website + No contact)")
    print("="*80)
    result3 = await reasoning_agent.validate_lead(unreachable_lead)
    print(reasoning_agent.explain_decision(result3))
    
    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"Test 1 (GOOD): {result1.final_verdict} - Score: {result1.corrections['leak_score']}/100")
    print(f"Test 2 (BAD): {result2.final_verdict} - Score: {result2.corrections['leak_score']}/100")
    print(f"Test 3 (UNREACHABLE): {result3.final_verdict} - Score: {result3.corrections['leak_score']}/100")


if __name__ == "__main__":
    asyncio.run(test_reasoning())
