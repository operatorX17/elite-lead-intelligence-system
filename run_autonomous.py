#!/usr/bin/env python
"""
ZRAI Lead OS - Autonomous Runner
Runs the full pipeline: Discovery → Enrichment → Intent → Scoring → Outreach

Usage:
    python run_autonomous.py --niche "HVAC" --geo "Texas" --limit 50
    python run_autonomous.py --process-existing --limit 100
"""

import sys
import logging
import argparse
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("zrai.autonomous")


def discover_and_process(niche: str, geo: str, limit: int = 50, source: str = "google_maps"):
    """Discover new leads and auto-process them through the pipeline."""
    from src.agents.discovery import DiscoveryAgent
    from src.db.client import get_supabase_client
    
    logger.info(f"🔍 Discovering {limit} leads for '{niche}' in '{geo}'...")
    
    discovery = DiscoveryAgent()
    db = get_supabase_client()
    
    # Get current lead count
    before_count = db.count_leads()
    
    if source == "google_maps":
        leads = discovery.discover_from_google_maps(
            keywords=[niche],
            geo={"city": geo} if "," not in geo else {"state": geo.split(",")[1].strip()},
            limit=limit,
            auto_process=True,  # This runs enrichment → intent → scoring automatically
        )
    else:
        leads = discovery.discover_from_meta_ads(
            keywords=[niche],
            geo={"country": "US"},
            limit=limit,
            auto_process=True,
        )
    
    after_count = db.count_leads()
    new_leads = after_count - before_count
    
    logger.info(f"✅ Discovered {new_leads} new leads (skipped {limit - new_leads} duplicates)")
    
    # Get tier breakdown
    tier_a = sum(1 for l in leads if hasattr(l, 'tier') and l.tier == 'A')
    tier_b = sum(1 for l in leads if hasattr(l, 'tier') and l.tier == 'B')
    
    return {
        "discovered": len(leads),
        "new": new_leads,
        "tier_a": tier_a,
        "tier_b": tier_b,
    }


def process_existing_leads(limit: int = 100, niche: str = None):
    """Process existing leads that haven't been scored yet."""
    from src.graph.orchestrator import create_orchestrator
    from src.db.client import get_supabase_client
    from uuid import UUID
    
    logger.info(f"⚙️ Processing up to {limit} existing leads...")
    
    db = get_supabase_client()
    orchestrator = create_orchestrator()
    
    # Get unprocessed leads
    leads = db.get_leads_for_processing(limit=limit, niche=niche)
    
    if not leads:
        logger.info("No leads to process")
        return {"processed": 0, "success": 0, "failed": 0}
    
    logger.info(f"Found {len(leads)} leads to process")
    
    success = 0
    failed = 0
    results = []
    
    for i, lead in enumerate(leads, 1):
        lead_id = lead.get("lead_id")
        business = lead.get("business_name", "Unknown")
        
        try:
            logger.info(f"[{i}/{len(leads)}] Processing: {business}")
            result = orchestrator.process_lead(UUID(lead_id))
            
            # Get scoring result
            scoring = result.get("scoring", {})
            tier = scoring.get("lead_tier", "?")
            score = scoring.get("final_score", 0)
            
            logger.info(f"  → Tier {tier}, Score {score}")
            
            results.append({
                "lead_id": lead_id,
                "business": business,
                "tier": tier,
                "score": score,
            })
            success += 1
            
        except Exception as e:
            logger.error(f"  → Failed: {e}")
            failed += 1
    
    # Summary
    tier_a = sum(1 for r in results if r.get("tier") == "A")
    tier_b = sum(1 for r in results if r.get("tier") == "B")
    tier_c = sum(1 for r in results if r.get("tier") == "C")
    
    logger.info(f"\n📊 Results: {success} success, {failed} failed")
    logger.info(f"   Tier A: {tier_a} | Tier B: {tier_b} | Tier C: {tier_c}")
    
    return {
        "processed": len(leads),
        "success": success,
        "failed": failed,
        "tier_a": tier_a,
        "tier_b": tier_b,
        "tier_c": tier_c,
    }


def generate_outreach_for_top_leads(limit: int = 10):
    """Generate outreach messages for top-tier leads."""
    from src.agents.outreach import OutreachAgent
    from src.db.client import get_supabase_client
    from uuid import UUID
    
    logger.info(f"📧 Generating outreach for top {limit} leads...")
    
    db = get_supabase_client()
    outreach = OutreachAgent()
    
    # Get Tier A leads first, then B
    tier_a_leads = db.get_leads_by_tier("A", limit=limit)
    tier_b_leads = db.get_leads_by_tier("B", limit=limit - len(tier_a_leads))
    
    leads = tier_a_leads + tier_b_leads
    
    if not leads:
        logger.info("No qualified leads for outreach")
        return {"generated": 0}
    
    generated = 0
    for lead in leads[:limit]:
        lead_id = lead.get("lead_id")
        try:
            # Create minimal state for outreach
            state = {
                "lead_id": lead_id,
                "lead": db.get_lead(UUID(lead_id)),
                "scoring": lead,
                "proof": db.get_proof_artifact(UUID(lead_id)) or {},
            }
            
            result = outreach.process(state)
            messages = result.get("outreach_messages", [])
            
            if messages:
                logger.info(f"  ✉️ Generated {len(messages)} messages for {lead.get('business_name', lead_id)}")
                generated += len(messages)
                
        except Exception as e:
            logger.error(f"  Failed for {lead_id}: {e}")
    
    return {"generated": generated}


def show_pipeline_status():
    """Show current pipeline status."""
    from src.db.client import get_supabase_client
    
    db = get_supabase_client()
    counts = db.get_lead_counts_by_state()
    
    print("\n" + "=" * 50)
    print("ZRAI LEAD OS - PIPELINE STATUS")
    print("=" * 50)
    print(f"📥 NEW leads:        {counts.get('NEW', 0)}")
    print(f"🔄 ENGAGED:          {counts.get('ENGAGED', 0)}")
    print(f"✅ QUALIFIED:        {counts.get('QUALIFIED', 0)}")
    print(f"💰 CLOSED_WON:       {counts.get('CLOSED_WON', 0)}")
    print(f"❌ CLOSED_LOST:      {counts.get('CLOSED_LOST', 0)}")
    print("=" * 50)
    
    # Get tier breakdown from scoring
    tier_a = len(db.get_leads_by_tier("A", limit=1000))
    tier_b = len(db.get_leads_by_tier("B", limit=1000))
    tier_c = len(db.get_leads_by_tier("C", limit=1000))
    
    print(f"\n🎯 LEAD QUALITY:")
    print(f"   Tier A (Hot):     {tier_a}")
    print(f"   Tier B (Warm):    {tier_b}")
    print(f"   Tier C (Cold):    {tier_c}")
    print("=" * 50 + "\n")


def main():
    parser = argparse.ArgumentParser(description="ZRAI Lead OS Autonomous Runner")
    parser.add_argument("--discover", action="store_true", help="Discover new leads")
    parser.add_argument("--process-existing", action="store_true", help="Process existing leads")
    parser.add_argument("--generate-outreach", action="store_true", help="Generate outreach for top leads")
    parser.add_argument("--status", action="store_true", help="Show pipeline status")
    parser.add_argument("--niche", type=str, default="HVAC", help="Niche to target")
    parser.add_argument("--geo", type=str, default="Texas", help="Geographic area")
    parser.add_argument("--limit", type=int, default=50, help="Max leads to process")
    parser.add_argument("--source", type=str, default="google_maps", choices=["google_maps", "meta_ads"])
    
    args = parser.parse_args()
    
    print("\n🚀 ZRAI LEAD OS - AUTONOMOUS MODE")
    print(f"   Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50 + "\n")
    
    if args.status or not any([args.discover, args.process_existing, args.generate_outreach]):
        show_pipeline_status()
    
    if args.discover:
        result = discover_and_process(args.niche, args.geo, args.limit, args.source)
        print(f"\n📊 Discovery Results: {result}")
    
    if args.process_existing:
        result = process_existing_leads(args.limit, args.niche if args.niche != "HVAC" else None)
        print(f"\n📊 Processing Results: {result}")
    
    if args.generate_outreach:
        result = generate_outreach_for_top_leads(args.limit)
        print(f"\n📊 Outreach Results: {result}")
    
    print(f"\n✅ Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
