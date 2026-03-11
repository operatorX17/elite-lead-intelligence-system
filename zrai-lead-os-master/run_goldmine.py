"""
🏆 GOLDMINE RUNNER - Run the autonomous sales machine on real leads.

This script:
1. Gets top-scoring leads from the database
2. Runs them through the Goldmine pipeline
3. Generates proof decks with dollar amounts
4. Prepares outreach sequences

Usage:
    python run_goldmine.py              # Process top 5 leads
    python run_goldmine.py --all        # Process all Tier A/B leads
    python run_goldmine.py --lead ID    # Process specific lead
"""

import os
import sys
import argparse
from datetime import datetime
import logging

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_top_leads(limit: int = 5):
    """Get top-scoring leads from database."""
    from src.db.client import get_supabase_client
    
    db = get_supabase_client()
    
    # Get leads with scoring data
    leads = db.get_leads(limit=100)
    
    # Get scoring results
    try:
        scoring = db._client.table("scoring_results").select("*").execute()
        scoring_map = {s["lead_id"]: s for s in (scoring.data or [])}
    except:
        scoring_map = {}
    
    # Get enrichment data
    try:
        enrichment = db._client.table("enrichment_data").select("*").execute()
        enrichment_map = {e["lead_id"]: e for e in (enrichment.data or [])}
    except:
        enrichment_map = {}
    
    # Combine and sort by score
    combined = []
    for lead in leads:
        lead_id = lead.get("lead_id")
        score_data = scoring_map.get(lead_id, {})
        enrich_data = enrichment_map.get(lead_id, {})
        
        combined.append({
            "lead": lead,
            "enrichment": enrich_data,
            "final_score": score_data.get("final_score", 0),
            "tier": score_data.get("lead_tier", "C"),
        })
    
    # Sort by score descending
    combined.sort(key=lambda x: x["final_score"], reverse=True)
    
    # Filter to Tier A and B only
    top_leads = [c for c in combined if c["tier"] in ["A", "B"]][:limit]
    
    return top_leads


def run_goldmine_on_lead(lead_data: dict, enrichment: dict):
    """Run Goldmine pipeline on a single lead."""
    from src.goldmine.graph import run_goldmine_pipeline
    
    business_name = lead_data.get("business_name", "Unknown")
    
    print(f"\n{'='*60}")
    print(f"🏆 GOLDMINE PROCESSING: {business_name}")
    print(f"{'='*60}")
    
    try:
        # Run pipeline with streaming - accumulate all state updates
        accumulated_state = {}
        for update in run_goldmine_pipeline(lead_data, enrichment, stream=True):
            # Print progress
            for node_name, node_output in update.items():
                stages = node_output.get("completed_stages", [])
                stage_str = ", ".join(stages) if stages else ""
                print(f"  ✓ {node_name}: {stage_str}")
                
                # Accumulate state updates
                for key, value in node_output.items():
                    if key == "completed_stages":
                        # Append to list
                        if key not in accumulated_state:
                            accumulated_state[key] = []
                        accumulated_state[key].extend(value)
                    elif key in ["mystery_shop_results", "competitor_analyses", "review_evidence", "messages", "errors"]:
                        # Append to list
                        if key not in accumulated_state:
                            accumulated_state[key] = []
                        if isinstance(value, list):
                            accumulated_state[key].extend(value)
                        else:
                            accumulated_state[key].append(value)
                    else:
                        # Overwrite
                        accumulated_state[key] = value
        
        # Extract results from accumulated state
        monthly_loss = accumulated_state.get("estimated_monthly_loss", 0)
        goldmine_score = accumulated_state.get("goldmine_score", 0)
        proof_deck = accumulated_state.get("proof_deck")
        
        print(f"\n📊 RESULTS:")
        print(f"  💰 Estimated Monthly Loss: ${monthly_loss:,.0f}")
        print(f"  🎯 Goldmine Score: {goldmine_score}")
        
        if proof_deck:
            print(f"  📄 Proof Deck: Generated")
            print(f"  📝 Headline: {proof_deck.get('headline', 'N/A')}")
        
        # Show loss breakdown
        loss_breakdown = accumulated_state.get("loss_breakdown", {})
        if loss_breakdown:
            print(f"\n  💸 LOSS BREAKDOWN:")
            for category, amount in loss_breakdown.items():
                print(f"     • {category}: ${amount:,.0f}")
        
        return {
            "business_name": business_name,
            "monthly_loss": monthly_loss,
            "goldmine_score": goldmine_score,
            "success": True,
        }
        
    except Exception as e:
        logger.error(f"Goldmine error for {business_name}: {e}")
        import traceback
        traceback.print_exc()
        return {
            "business_name": business_name,
            "error": str(e),
            "success": False,
        }


def main():
    parser = argparse.ArgumentParser(description="Run Goldmine autonomous sales machine")
    parser.add_argument("--all", action="store_true", help="Process all Tier A/B leads")
    parser.add_argument("--lead", type=str, help="Process specific lead by ID")
    parser.add_argument("--limit", type=int, default=5, help="Number of leads to process")
    parser.add_argument("--dry-run", action="store_true", help="Show leads without processing")
    
    args = parser.parse_args()
    
    print("=" * 70)
    print("  🏆 ZRAI GOLDMINE - AUTONOMOUS SALES MACHINE")
    print("=" * 70)
    print(f"\nStarted at: {datetime.now().isoformat()}\n")
    
    # Get leads
    if args.lead:
        # Get specific lead
        from src.db.client import get_supabase_client
        db = get_supabase_client()
        
        leads_data = db._client.table("leads").select("*").eq("lead_id", args.lead).execute()
        if not leads_data.data:
            print(f"❌ Lead not found: {args.lead}")
            return
        
        enrichment_data = db._client.table("enrichment_data").select("*").eq("lead_id", args.lead).execute()
        
        leads = [{
            "lead": leads_data.data[0],
            "enrichment": enrichment_data.data[0] if enrichment_data.data else {},
            "final_score": 0,
            "tier": "A",
        }]
    else:
        # Get top leads
        limit = 100 if args.all else args.limit
        leads = get_top_leads(limit)
    
    print(f"📋 Found {len(leads)} leads to process\n")
    
    if args.dry_run:
        print("DRY RUN - Showing leads without processing:\n")
        for i, lead_info in enumerate(leads, 1):
            lead = lead_info["lead"]
            print(f"  {i}. {lead.get('business_name')}")
            print(f"     Category: {lead.get('category')}")
            print(f"     Score: {lead_info['final_score']} (Tier {lead_info['tier']})")
            print()
        return
    
    # Process leads
    results = []
    for i, lead_info in enumerate(leads, 1):
        print(f"\n[{i}/{len(leads)}] Processing...")
        
        result = run_goldmine_on_lead(
            lead_info["lead"],
            lead_info["enrichment"],
        )
        results.append(result)
    
    # Summary
    print("\n" + "=" * 70)
    print("  🏆 GOLDMINE PROCESSING COMPLETE")
    print("=" * 70)
    
    successful = [r for r in results if r.get("success")]
    failed = [r for r in results if not r.get("success")]
    
    print(f"\nTotal processed: {len(results)}")
    print(f"Successful: {len(successful)}")
    print(f"Failed: {len(failed)}")
    
    if successful:
        total_loss = sum(r.get("monthly_loss", 0) for r in successful)
        avg_score = sum(r.get("goldmine_score", 0) for r in successful) / len(successful)
        
        print(f"\n💰 TOTAL MONTHLY LOSS IDENTIFIED: ${total_loss:,.0f}")
        print(f"📊 AVERAGE GOLDMINE SCORE: {avg_score:.0f}")
        
        print(f"\n🏆 TOP GOLDMINE PROSPECTS:")
        top = sorted(successful, key=lambda x: x.get("goldmine_score", 0), reverse=True)[:5]
        for i, r in enumerate(top, 1):
            print(f"  {i}. {r['business_name']}")
            print(f"     Score: {r.get('goldmine_score', 0)} | Loss: ${r.get('monthly_loss', 0):,.0f}/mo")
    
    print(f"\nCompleted at: {datetime.now().isoformat()}")


if __name__ == "__main__":
    main()
