#!/usr/bin/env python3
"""
Rescore all existing leads with new Google Maps volume signals.
Run this after implementing volume signal extraction.
"""

import os
import sys
from datetime import datetime
from typing import Dict, Any

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.db.supabase_client import get_supabase_client
from src.agents.enrichment import EnrichmentAgent
from src.agents.intent import IntentAgent
from src.agents.scoring import ScoringAgent
from src.graph.state import LeadGraphState


def rescore_all_leads():
    """Rescore all leads with new volume signals."""
    
    print("=" * 80)
    print("RESCORING ALL LEADS WITH VOLUME SIGNALS")
    print("=" * 80)
    
    # Initialize agents
    enrichment_agent = EnrichmentAgent()
    intent_agent = IntentAgent()
    scoring_agent = ScoringAgent()
    
    # Get database client
    db = get_supabase_client()
    
    # Fetch all leads
    print("\n[1/4] Fetching all leads from database...")
    response = db.table("leads").select("*").execute()
    leads = response.data
    print(f"Found {len(leads)} leads to rescore")
    
    # Track results
    results = {
        "total": len(leads),
        "rescored": 0,
        "tier_changes": {"A": 0, "B": 0, "C": 0},
        "score_improvements": [],
    }
    
    print("\n[2/4] Re-enriching leads with volume signals...")
    for i, lead in enumerate(leads, 1):
        lead_id = lead["lead_id"]
        business_name = lead.get("business_name", "Unknown")
        
        print(f"\n[{i}/{len(leads)}] Processing: {business_name}")
        
        try:
            # Create state
            state = LeadGraphState(lead=lead)
            
            # Re-run enrichment (will extract volume signals)
            print(f"  → Extracting volume signals...")
            state = enrichment_agent.process(state)
            enrichment = state.get("enrichment", {})
            
            # Show volume signals
            if enrichment:
                peak = enrichment.get("peak_busyness", 0)
                busy_hours = enrichment.get("busy_hours_count", 0)
                duration = enrichment.get("avg_visit_duration_min", 0)
                print(f"  → Volume: peak={peak}, busy_hours={busy_hours}, duration={duration}min")
            
            # Re-run intent (will calculate volume score)
            print(f"  → Calculating volume score...")
            state = intent_agent.process(state)
            intent = state.get("intent", {})
            volume_score = intent.get("volume_score", 0)
            print(f"  → Volume score: {volume_score}/100")
            
            # Get old score
            old_scoring_response = db.table("scoring_results").select("*").eq("lead_id", lead_id).execute()
            old_score = 0
            old_tier = "C"
            if old_scoring_response.data:
                old_score = old_scoring_response.data[0].get("final_score", 0)
                old_tier = old_scoring_response.data[0].get("lead_tier", "C")
            
            # Re-run scoring (will include volume in weighted score)
            print(f"  → Calculating final score...")
            state = scoring_agent.process(state)
            scoring = state.get("scoring", {})
            new_score = scoring.get("final_score", 0)
            new_tier = scoring.get("lead_tier", "C")
            
            # Show results
            score_change = new_score - old_score
            print(f"  → Score: {old_score} → {new_score} ({score_change:+d})")
            print(f"  → Tier: {old_tier} → {new_tier}")
            
            # Track changes
            results["rescored"] += 1
            if new_tier != old_tier:
                results["tier_changes"][new_tier] += 1
            
            if score_change > 0:
                results["score_improvements"].append({
                    "business_name": business_name,
                    "old_score": old_score,
                    "new_score": new_score,
                    "change": score_change,
                    "old_tier": old_tier,
                    "new_tier": new_tier,
                    "volume_score": volume_score,
                })
        
        except Exception as e:
            print(f"  ✗ Error: {e}")
            continue
    
    print("\n" + "=" * 80)
    print("RESCORING COMPLETE")
    print("=" * 80)
    
    print(f"\nTotal leads: {results['total']}")
    print(f"Successfully rescored: {results['rescored']}")
    print(f"\nTier changes:")
    print(f"  → Tier A: {results['tier_changes']['A']} leads")
    print(f"  → Tier B: {results['tier_changes']['B']} leads")
    print(f"  → Tier C: {results['tier_changes']['C']} leads")
    
    # Show top improvements
    if results["score_improvements"]:
        print(f"\nTop 10 Score Improvements:")
        improvements = sorted(results["score_improvements"], key=lambda x: x["change"], reverse=True)[:10]
        for imp in improvements:
            print(f"\n  {imp['business_name']}")
            print(f"    Score: {imp['old_score']} → {imp['new_score']} ({imp['change']:+d})")
            print(f"    Tier: {imp['old_tier']} → {imp['new_tier']}")
            print(f"    Volume: {imp['volume_score']}/100")
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    rescore_all_leads()
