"""
RE-SCORE ALL LEADS - Apply new 100X scoring logic to existing leads.

This script:
1. Gets all leads from the database
2. Re-runs intent + scoring with enhanced logic
3. Reports tier distribution changes

Part of the 100X upgrade.
"""
import os
import sys
from datetime import datetime
from typing import List, Dict, Any
import logging

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def rescore_lead(lead: Dict[str, Any], enrichment: Dict[str, Any], agents: Dict) -> Dict[str, Any]:
    """Re-score a single lead with new logic."""
    from src.graph.state import LeadGraphState
    from uuid import uuid4
    
    # Create state with existing enrichment
    state: LeadGraphState = {
        "lead_id": lead.get("lead_id"),
        "thread_id": f"rescore-{uuid4()}",
        "lead": lead,
        "current_stage": "intent",
        "last_node": "enrichment",
        "enrichment": enrichment or {},
        "intent": {},
        "scoring": {},
        "proof": {},
        "outreach_messages": [],
        "conversation_transcript": [],
        "conversation_entities": {},
        "errors": [],
        "retry_count": 0,
        "should_skip_audit": True,
        "should_skip_outreach": True,
        "is_disqualified": False,
        "is_escalated": False,
        "is_complete": False,
        "requires_approval": False,
        "metadata": {"rescored": True},
        "messages": [],
    }
    
    result = {
        "lead_id": lead.get("lead_id"),
        "business_name": lead.get("business_name"),
        "category": lead.get("category"),
        "intent_score": None,
        "leak_score": None,
        "reactivation_fit": None,
        "final_score": None,
        "tier": None,
    }
    
    # Re-run intent
    try:
        state = agents["intent"].process(state)
        result["intent_score"] = state.get("intent", {}).get("intent_score")
        result["leak_score"] = state.get("intent", {}).get("leak_score")
        result["reactivation_fit"] = state.get("intent", {}).get("reactivation_fit")
    except Exception as e:
        logger.warning(f"Intent failed for {lead.get('business_name')}: {e}")
    
    # Re-run scoring
    try:
        state = agents["scoring"].process(state)
        result["final_score"] = state.get("scoring", {}).get("final_score")
        result["tier"] = state.get("scoring", {}).get("lead_tier")
    except Exception as e:
        logger.warning(f"Scoring failed for {lead.get('business_name')}: {e}")
    
    return result


def main():
    print("=" * 70)
    print("  ZRAI LEAD OS - RE-SCORING ALL LEADS")
    print("  Applying 100X enhanced scoring logic")
    print("=" * 70)
    print(f"\nStarted at: {datetime.now().isoformat()}\n")
    
    # Initialize
    from src.db.client import get_supabase_client
    from src.agents.intent import IntentAgent
    from src.agents.scoring import ScoringAgent
    
    db = get_supabase_client()
    
    agents = {
        "intent": IntentAgent(),
        "scoring": ScoringAgent(),
    }
    
    # Get all leads
    print("Fetching all leads from database...")
    all_leads = db.get_leads(limit=1000)
    print(f"Found {len(all_leads)} leads\n")
    
    # Get existing enrichment data
    print("Fetching enrichment data...")
    try:
        enrichment_data = db._client.table("enrichment_data").select("*").execute()
        enrichment_map = {e["lead_id"]: e for e in (enrichment_data.data or [])}
        print(f"Found {len(enrichment_map)} enrichment records\n")
    except Exception as e:
        print(f"Warning: Could not fetch enrichment data: {e}")
        enrichment_map = {}
    
    # Re-score each lead
    results = []
    for i, lead in enumerate(all_leads, 1):
        lead_id = lead.get("lead_id")
        enrichment = enrichment_map.get(lead_id, {})
        
        print(f"[{i}/{len(all_leads)}] Re-scoring: {lead.get('business_name', 'Unknown')}")
        
        try:
            result = rescore_lead(lead, enrichment, agents)
            results.append(result)
            
            # Print quick summary
            tier_emoji = {"A": "🔥", "B": "✓", "C": "○"}.get(result["tier"], "?")
            print(f"  {tier_emoji} Intent: {result['intent_score']}, Leak: {result['leak_score']}, "
                  f"React: {result['reactivation_fit']}, Final: {result['final_score']}, Tier: {result['tier']}")
            
        except Exception as e:
            logger.error(f"Failed to re-score {lead.get('business_name')}: {e}")
    
    # Summary
    print("\n" + "=" * 70)
    print("  RE-SCORING COMPLETE")
    print("=" * 70)
    
    # Tier breakdown
    tier_counts = {"A": 0, "B": 0, "C": 0}
    for r in results:
        tier = r.get("tier", "C")
        tier_counts[tier] = tier_counts.get(tier, 0) + 1
    
    print(f"\nTotal re-scored: {len(results)}")
    print(f"\nTier Distribution:")
    print(f"  🔥 Tier A (Hot):  {tier_counts.get('A', 0)} leads")
    print(f"  ✓  Tier B (Warm): {tier_counts.get('B', 0)} leads")
    print(f"  ○  Tier C (Cold): {tier_counts.get('C', 0)} leads")
    
    # Top leads
    successful = [r for r in results if r.get("final_score")]
    top_leads = sorted(successful, key=lambda x: x.get("final_score", 0) or 0, reverse=True)[:15]
    
    if top_leads:
        print(f"\n🏆 TOP 15 LEADS BY SCORE:")
        print("-" * 60)
        for i, lead in enumerate(top_leads, 1):
            tier_emoji = {"A": "🔥", "B": "✓", "C": "○"}.get(lead["tier"], "?")
            print(f"  {i:2}. {tier_emoji} {lead['business_name'][:35]:<35} | Score: {lead['final_score']:3} | {lead['tier']}")
            print(f"      Category: {lead['category']}")
            print(f"      Intent: {lead['intent_score']} | Leak: {lead['leak_score']} | Reactivation: {lead['reactivation_fit']}")
    
    # Score distribution
    print(f"\n📊 SCORE DISTRIBUTION:")
    score_ranges = {"0-20": 0, "21-40": 0, "41-60": 0, "61-80": 0, "81-100": 0}
    for r in successful:
        score = r.get("final_score", 0) or 0
        if score <= 20:
            score_ranges["0-20"] += 1
        elif score <= 40:
            score_ranges["21-40"] += 1
        elif score <= 60:
            score_ranges["41-60"] += 1
        elif score <= 80:
            score_ranges["61-80"] += 1
        else:
            score_ranges["81-100"] += 1
    
    for range_name, count in score_ranges.items():
        bar = "█" * (count * 2)
        print(f"  {range_name}: {bar} ({count})")
    
    print(f"\nCompleted at: {datetime.now().isoformat()}")


if __name__ == "__main__":
    main()
