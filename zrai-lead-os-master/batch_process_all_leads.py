"""
BATCH PROCESSOR - Process ALL leads through the full pipeline.

This script:
1. Gets all leads from the database
2. Runs each through enrichment → intent → scoring
3. Reports results

Part of the 100X upgrade.
"""
import os
import sys
from datetime import datetime
from typing import List, Dict, Any
import logging
import time

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def process_lead(lead: Dict[str, Any], agents: Dict) -> Dict[str, Any]:
    """Process a single lead through the pipeline."""
    from src.graph.state import LeadGraphState
    from uuid import uuid4
    
    # Create state
    state: LeadGraphState = {
        "lead_id": lead.get("lead_id"),
        "thread_id": f"batch-{uuid4()}",
        "lead": lead,
        "current_stage": "enrichment",
        "last_node": "discovery",
        "enrichment": {},
        "intent": {},
        "scoring": {},
        "proof": {},
        "outreach_messages": [],
        "conversation_transcript": [],
        "conversation_entities": {},
        "errors": [],
        "retry_count": 0,
        "should_skip_audit": True,  # Skip audit for batch (saves API calls)
        "should_skip_outreach": True,  # Skip outreach for batch
        "is_disqualified": False,
        "is_escalated": False,
        "is_complete": False,
        "requires_approval": False,
        "metadata": {"batch_processed": True},
        "messages": [],
    }
    
    result = {
        "lead_id": lead.get("lead_id"),
        "business_name": lead.get("business_name"),
        "category": lead.get("category"),
        "enrichment_status": "pending",
        "intent_status": "pending",
        "scoring_status": "pending",
        "intent_score": None,
        "leak_score": None,
        "final_score": None,
        "tier": None,
        "errors": [],
    }
    
    # Step 1: Enrichment
    try:
        state = agents["enrichment"].process(state)
        result["enrichment_status"] = "success"
    except Exception as e:
        result["enrichment_status"] = "failed"
        result["errors"].append(f"Enrichment: {str(e)}")
        logger.warning(f"Enrichment failed for {lead.get('business_name')}: {e}")
    
    # Step 2: Intent
    try:
        state = agents["intent"].process(state)
        result["intent_status"] = "success"
        result["intent_score"] = state.get("intent", {}).get("intent_score")
        result["leak_score"] = state.get("intent", {}).get("leak_score")
    except Exception as e:
        result["intent_status"] = "failed"
        result["errors"].append(f"Intent: {str(e)}")
        logger.warning(f"Intent failed for {lead.get('business_name')}: {e}")
    
    # Step 3: Scoring
    try:
        state = agents["scoring"].process(state)
        result["scoring_status"] = "success"
        result["final_score"] = state.get("scoring", {}).get("final_score")
        result["tier"] = state.get("scoring", {}).get("lead_tier")
    except Exception as e:
        result["scoring_status"] = "failed"
        result["errors"].append(f"Scoring: {str(e)}")
        logger.warning(f"Scoring failed for {lead.get('business_name')}: {e}")
    
    return result


def main():
    print("=" * 70)
    print("  ZRAI LEAD OS - BATCH PROCESSOR")
    print("  Processing ALL leads through the pipeline")
    print("=" * 70)
    print(f"\nStarted at: {datetime.now().isoformat()}\n")
    
    # Initialize
    from src.db.client import get_supabase_client
    from src.agents.enrichment import EnrichmentAgent
    from src.agents.intent import IntentAgent
    from src.agents.scoring import ScoringAgent
    
    db = get_supabase_client()
    
    agents = {
        "enrichment": EnrichmentAgent(),
        "intent": IntentAgent(),
        "scoring": ScoringAgent(),
    }
    
    # Get all leads
    print("Fetching all leads from database...")
    all_leads = db.get_leads(limit=1000)
    print(f"Found {len(all_leads)} leads\n")
    
    # Check which leads already have scoring data
    try:
        existing_scores = db._client.table("scoring_results").select("lead_id").execute()
        scored_lead_ids = {r["lead_id"] for r in (existing_scores.data or [])}
        print(f"Already scored: {len(scored_lead_ids)} leads")
    except:
        scored_lead_ids = set()
    
    # Filter to unprocessed leads
    unprocessed = [l for l in all_leads if l.get("lead_id") not in scored_lead_ids]
    print(f"Unprocessed leads: {len(unprocessed)}\n")
    
    if not unprocessed:
        print("All leads already processed!")
        return
    
    # Process each lead
    results = []
    for i, lead in enumerate(unprocessed, 1):
        print(f"[{i}/{len(unprocessed)}] Processing: {lead.get('business_name', 'Unknown')}")
        
        try:
            result = process_lead(lead, agents)
            results.append(result)
            
            # Print quick summary
            status = "✓" if result["tier"] else "✗"
            print(f"  {status} Intent: {result['intent_score']}, Leak: {result['leak_score']}, "
                  f"Final: {result['final_score']}, Tier: {result['tier']}")
            
        except Exception as e:
            logger.error(f"Failed to process {lead.get('business_name')}: {e}")
            results.append({
                "lead_id": lead.get("lead_id"),
                "business_name": lead.get("business_name"),
                "errors": [str(e)],
            })
        
        # Small delay to avoid rate limits
        time.sleep(0.5)
    
    # Summary
    print("\n" + "=" * 70)
    print("  BATCH PROCESSING COMPLETE")
    print("=" * 70)
    
    successful = [r for r in results if r.get("tier")]
    failed = [r for r in results if not r.get("tier")]
    
    print(f"\nTotal processed: {len(results)}")
    print(f"Successful: {len(successful)}")
    print(f"Failed: {len(failed)}")
    
    # Tier breakdown
    tier_counts = {"A": 0, "B": 0, "C": 0}
    for r in successful:
        tier = r.get("tier", "C")
        tier_counts[tier] = tier_counts.get(tier, 0) + 1
    
    print(f"\nTier Breakdown:")
    print(f"  Tier A (Hot): {tier_counts.get('A', 0)}")
    print(f"  Tier B (Warm): {tier_counts.get('B', 0)}")
    print(f"  Tier C (Cold): {tier_counts.get('C', 0)}")
    
    # Top leads
    top_leads = sorted(successful, key=lambda x: x.get("final_score", 0) or 0, reverse=True)[:10]
    if top_leads:
        print(f"\nTop 10 Leads by Score:")
        for i, lead in enumerate(top_leads, 1):
            print(f"  {i}. {lead['business_name']} - Score: {lead['final_score']}, Tier: {lead['tier']}")
    
    print(f"\nCompleted at: {datetime.now().isoformat()}")


if __name__ == "__main__":
    main()
