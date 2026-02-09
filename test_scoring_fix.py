#!/usr/bin/env python
"""
Quick test to verify scoring fix works
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import asyncio
from src.agents.reasoning import ReasoningAgent
from src.tools.llm import get_llm_client

# Sample lead data (similar to what we're getting from Firecrawl)
sample_lead = {
    "business_name": "Shree Polyclinic & Lab",
    "website": "https://shreepolycliniclab.com/",
    "phone": "+91 96865 85122",
    "emails": ["info@shreepolycliniclab.com", "shreepolycliniclab@gmail.com"],
    "status": "firecrawl_success",
    "has_booking_system": True,
    "has_whatsapp": True,
    "has_lead_form": True,
    "has_click_to_call": False,
    "has_chat_widget": True,
    "has_slow_response_risk": True,
    "has_after_hours_leak": True,
    "rating": None,
    "reviews_count": None,
    "ads_detected": False,
    "phones": ["9185500019", "2208299999", "7551699999"],
    "booking_links": [],
    "social_links": {}
}

async def test_scoring():
    """Test the scoring with new thresholds"""
    
    print("=" * 80)
    print("TESTING SCORING FIX")
    print("=" * 80)
    
    # Initialize reasoning agent
    llm = get_llm_client()
    reasoning_agent = ReasoningAgent(llm)
    
    # Validate lead
    print(f"\nValidating: {sample_lead['business_name']}")
    print(f"Website: {sample_lead['website']}")
    print(f"Emails: {sample_lead['emails']}")
    print(f"Has booking: {sample_lead['has_booking_system']}")
    print(f"Has WhatsApp: {sample_lead['has_whatsapp']}")
    
    result = await reasoning_agent.validate_lead(sample_lead)
    
    print("\n" + "=" * 80)
    print("RESULT:")
    print("=" * 80)
    print(f"Verdict: {result.final_verdict}")
    print(f"Tier: {result.corrections.get('priority')}")
    print(f"Score: {result.corrections.get('leak_score')}/100")
    print(f"Confidence: {result.confidence:.1%}")
    print(f"\nData Quality: {result.corrections.get('data_quality_score')}/100")
    print(f"Reachability: {result.corrections.get('reachability_score')}/100")
    print(f"Opportunity: {result.corrections.get('opportunity_score')}/100")
    
    if result.issues_found:
        print(f"\nIssues Found ({len(result.issues_found)}):")
        for i, issue in enumerate(result.issues_found, 1):
            print(f"  {i}. {issue}")
    
    print("\n" + "=" * 80)
    print("EXPECTED OUTCOME:")
    print("=" * 80)
    print("With new thresholds (HOT >= 55, WARM >= 35):")
    print(f"- Score {result.corrections.get('leak_score')} should be: ", end="")
    
    score = result.corrections.get('leak_score', 0)
    if score >= 55:
        print("HOT ✅")
    elif score >= 35:
        print("WARM ⚠️")
    else:
        print("COLD ❌")
    
    print("\n" + "=" * 80)

if __name__ == "__main__":
    asyncio.run(test_scoring())
