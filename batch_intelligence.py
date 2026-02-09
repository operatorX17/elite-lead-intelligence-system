#!/usr/bin/env python3
"""
ZRAI Batch Intelligence Runner
Run intelligence on multiple niches and cities.
"""

import os
import sys
import json
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
load_dotenv('.env')

from ULTIMATE_INTELLIGENCE import UltimateIntelligenceEngine


def run_batch(targets: list, leads_per_target: int = 10):
    """
    Run intelligence on multiple targets.
    
    Args:
        targets: List of {"niche": "...", "city": "..."} dicts
        leads_per_target: Number of leads per target
    """
    engine = UltimateIntelligenceEngine()
    
    all_reports = []
    total_opportunity = 0
    total_leads = 0
    hot_count = 0
    warm_count = 0
    
    print("\n" + "=" * 70)
    print("🚀 ZRAI BATCH INTELLIGENCE RUN")
    print("=" * 70)
    print(f"   Targets: {len(targets)}")
    print(f"   Leads per target: {leads_per_target}")
    print("=" * 70)
    
    for i, target in enumerate(targets, 1):
        niche = target.get("niche")
        city = target.get("city")
        country = target.get("country", "India")
        
        print(f"\n\n{'='*70}")
        print(f"BATCH {i}/{len(targets)}: {niche} in {city}")
        print("=" * 70)
        
        try:
            report = engine.run(
                niche=niche,
                city=city,
                country=country,
                target=leads_per_target
            )
            
            if not report.get("error"):
                all_reports.append(report)
                summary = report.get("summary", {})
                total_opportunity += summary.get("total_opportunity_inr", 0)
                total_leads += summary.get("processed", 0)
                hot_count += summary.get("hot", 0)
                warm_count += summary.get("warm", 0)
        
        except Exception as e:
            print(f"❌ Error processing {niche} in {city}: {e}")
        
        # Rate limiting between targets
        if i < len(targets):
            print("\n⏳ Cooling down (30s)...")
            time.sleep(30)
    
    # Final Summary
    print("\n\n" + "=" * 70)
    print("🏆 BATCH RUN COMPLETE")
    print("=" * 70)
    print(f"\n📊 TOTAL RESULTS:")
    print(f"   Targets Processed: {len(all_reports)}/{len(targets)}")
    print(f"   Total Leads: {total_leads}")
    print(f"   🔥 HOT: {hot_count}")
    print(f"   ☀️ WARM: {warm_count}")
    print(f"   ❄️ COLD: {total_leads - hot_count - warm_count}")
    print(f"\n💰 TOTAL OPPORTUNITY:")
    print(f"   Monthly: ₹{total_opportunity:,}")
    print(f"   Annual: ₹{total_opportunity * 12:,}")
    
    # Save combined report
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    combined_report = {
        "batch_id": timestamp,
        "targets": targets,
        "summary": {
            "total_leads": total_leads,
            "hot": hot_count,
            "warm": warm_count,
            "cold": total_leads - hot_count - warm_count,
            "total_opportunity_inr": total_opportunity,
            "total_opportunity_annual_inr": total_opportunity * 12,
        },
        "reports": all_reports,
    }
    
    output_file = Path("output") / f"batch_{timestamp}.json"
    with open(output_file, 'w') as f:
        json.dump(combined_report, f, indent=2, ensure_ascii=False)
    
    print(f"\n📁 Combined report: {output_file}")
    print("=" * 70)
    
    return combined_report


# Default targets for healthcare focus
DEFAULT_TARGETS = [
    {"niche": "diagnostic center", "city": "Bangalore"},
    {"niche": "diagnostic center", "city": "Mumbai"},
    {"niche": "diagnostic center", "city": "Delhi"},
    {"niche": "dental clinic", "city": "Bangalore"},
    {"niche": "dental clinic", "city": "Mumbai"},
    {"niche": "eye hospital", "city": "Bangalore"},
    {"niche": "dermatology clinic", "city": "Mumbai"},
    {"niche": "physiotherapy center", "city": "Delhi"},
    {"niche": "IVF center", "city": "Bangalore"},
    {"niche": "cosmetic surgery clinic", "city": "Mumbai"},
]


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="ZRAI Batch Intelligence Runner")
    parser.add_argument("--targets", type=str, help="JSON file with targets")
    parser.add_argument("--count", type=int, default=5, help="Leads per target")
    parser.add_argument("--quick", action="store_true", help="Run quick test (3 targets)")
    
    args = parser.parse_args()
    
    if args.targets:
        with open(args.targets) as f:
            targets = json.load(f)
    elif args.quick:
        targets = DEFAULT_TARGETS[:3]
    else:
        targets = DEFAULT_TARGETS
    
    run_batch(targets, args.count)
