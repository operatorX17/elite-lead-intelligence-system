import sys
sys.path.append('src')

from src.agents.discovery import DiscoveryAgent
from src.db.client import SupabaseClient

print("=" * 80)
print("FULL PIPELINE TEST - Discovery + Enrichment + Intent + Scoring")
print("=" * 80)

agent = DiscoveryAgent()
client = SupabaseClient()

print("\nRunning discovery with auto_process=True...")
leads = agent.discover_from_google_maps(
    keywords=['HK Hospital Hyderabad'],
    geo={'city': 'Hyderabad', 'state': 'Telangana', 'country': 'India'},
    limit=1,
    auto_process=True,  # Run full pipeline
    skip_duplicate_check=True
)

print(f"\nDiscovery complete: {len(leads)} leads")

if leads:
    lead = leads[0]
    print(f"\nLead: {lead.business_name}")
    print(f"Lead ID: {lead.lead_id}")
    
    # Check enrichment
    print("\nChecking enrichment...")
    enrichment = client.get_enrichment_data(lead.lead_id)
    if enrichment:
        print(f"  Peak busyness: {enrichment.get('peak_busyness')}")
        print(f"  Busy hours: {enrichment.get('busy_hours_count')}")
        print(f"  Visit duration: {enrichment.get('avg_visit_duration_min')} min")
        print(f"  Contact quality: {enrichment.get('contact_quality_score')}/100")
    else:
        print("  NO ENRICHMENT DATA")
    
    # Check intent
    print("\nChecking intent...")
    intent = client.get_intent_data(lead.lead_id)
    if intent:
        print(f"  Volume score: {intent.get('volume_score')}/100")
        print(f"  Intent score: {intent.get('intent_score')}/100")
        print(f"  Leak score: {intent.get('leak_score')}/100")
    else:
        print("  NO INTENT DATA")
    
    # Check scoring
    print("\nChecking scoring...")
    scoring = client.get_scoring_result(lead.lead_id)
    if scoring:
        print(f"  Final score: {scoring.get('final_score')}/100")
        print(f"  Tier: {scoring.get('lead_tier')}")
        breakdown = scoring.get('score_breakdown', {})
        if breakdown:
            print(f"\n  Score breakdown:")
            print(f"    Volume: {breakdown.get('volume')}/100 (15% weight)")
            print(f"    Intent: {breakdown.get('intent')}/100 (30% weight)")
            print(f"    Leak: {breakdown.get('leak')}/100 (25% weight)")
    else:
        print("  NO SCORING DATA")
    
    print("\n" + "=" * 80)
    if enrichment and intent and scoring:
        print("SUCCESS - Full pipeline works!")
    else:
        print("PARTIAL - Some agents failed")
    print("=" * 80)
else:
    print("No leads found")
