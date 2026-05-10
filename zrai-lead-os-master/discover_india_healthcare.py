#!/usr/bin/env python
"""
Discover Indian Healthcare & Insurance leads
Target: Hospitals, Diagnostic centers, Insurance companies needing claim automation
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from src.agents.discovery import DiscoveryAgent
from src.db.client import get_supabase_client
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("india_discovery")

def discover_healthcare_leads():
    """Discover hospitals, diagnostic centers, insurance companies in India"""
    
    discovery = DiscoveryAgent()
    db = get_supabase_client()
    
    # Target cities (Tier 1 & 2)
    cities = [
        "Hyderabad",
        "Bangalore",
        "Mumbai",
        "Delhi",
        "Pune",
        "Chennai",
        "Kolkata",
        "Ahmedabad",
    ]
    
    # Target categories
    targets = [
        {
            "keywords": ["hospital", "multi-specialty hospital", "super specialty hospital"],
            "category": "Hospital",
            "limit": 30,
        },
        {
            "keywords": ["diagnostic center", "pathology lab", "imaging center"],
            "category": "Diagnostic Center",
            "limit": 30,
        },
        {
            "keywords": ["health insurance", "insurance broker", "TPA"],
            "category": "Insurance",
            "limit": 20,
        },
        {
            "keywords": ["clinic", "polyclinic", "medical center"],
            "category": "Clinic",
            "limit": 20,
        },
    ]
    
    all_leads = []
    
    for city in cities:
        logger.info(f"\n{'='*60}")
        logger.info(f"🏙️  Discovering leads in {city}")
        logger.info(f"{'='*60}")
        
        for target in targets:
            logger.info(f"\n📍 Searching: {target['category']} in {city}")
            
            try:
                leads = discovery.discover_from_google_maps(
                    keywords=target["keywords"],
                    geo={"city": city, "country": "India"},
                    limit=target["limit"],
                    auto_process=True,  # Auto-score them
                )
                
                logger.info(f"   ✅ Found {len(leads)} {target['category']} leads")
                all_leads.extend(leads)
                
            except Exception as e:
                logger.error(f"   ❌ Error: {e}")
    
    # Summary
    logger.info(f"\n{'='*60}")
    logger.info(f"📊 DISCOVERY COMPLETE")
    logger.info(f"{'='*60}")
    logger.info(f"Total leads discovered: {len(all_leads)}")
    
    # Get tier breakdown
    tier_counts = db.get_lead_counts_by_state()
    logger.info(f"\n🎯 Lead Quality:")
    
    tier_a = len(db.get_leads_by_tier("A", limit=1000))
    tier_b = len(db.get_leads_by_tier("B", limit=1000))
    tier_c = len(db.get_leads_by_tier("C", limit=1000))
    
    logger.info(f"   Tier A (Hot):  {tier_a}")
    logger.info(f"   Tier B (Warm): {tier_b}")
    logger.info(f"   Tier C (Cold): {tier_c}")
    
    return all_leads


if __name__ == "__main__":
    print("\n🇮🇳 INDIA HEALTHCARE & INSURANCE LEAD DISCOVERY")
    print("=" * 60)
    print("Targeting:")
    print("  • Hospitals (multi-specialty, super-specialty)")
    print("  • Diagnostic Centers (pathology, imaging)")
    print("  • Insurance Companies (health insurance, TPAs)")
    print("  • Clinics (polyclinics, medical centers)")
    print("\nCities: Hyderabad, Bangalore, Mumbai, Delhi, Pune, Chennai, Kolkata, Ahmedabad")
    print("=" * 60)
    
    input("\nPress ENTER to start discovery (will use Apify credits)...")
    
    leads = discover_healthcare_leads()
    
    print(f"\n✅ Discovery complete! Found {len(leads)} leads")
    print("\nNext steps:")
    print("  1. Review leads: python show_database.py")
    print("  2. Generate outreach: python run_autonomous.py --generate-outreach --limit 20")
