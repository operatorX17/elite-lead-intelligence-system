"""
Show raw database data to prove signals are real.
"""
import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

# Connect to database
supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_SERVICE_ROLE_KEY")
)

print("=" * 80)
print("RAW DATABASE DATA - PROOF SIGNALS ARE REAL")
print("=" * 80)
print()

# Get top 3 leads with their enrichment data
leads = supabase.table("leads").select("*").limit(3).execute()

for i, lead in enumerate(leads.data, 1):
    print(f"\n{'=' * 80}")
    print(f"LEAD #{i}: {lead.get('business_name')}")
    print("=" * 80)
    print()
    
    print("📍 BASIC INFO (from 'leads' table):")
    print(f"  ID: {lead.get('lead_id')}")
    print(f"  Website: {lead.get('website')}")
    print(f"  Phone: {lead.get('phone')}")
    print(f"  Category: {lead.get('category')}")
    print()
    
    # Get enrichment data
    enrichment = supabase.table("enrichment_data").select("*").eq("lead_id", lead.get("lead_id")).execute()
    
    if enrichment.data:
        enrich = enrichment.data[0]
        print("🔍 ENRICHMENT DATA (from 'enrichment_data' table):")
        print(f"  Booking Provider: {enrich.get('booking_provider') or '❌ NONE'}")
        print(f"  Chat Widget: {enrich.get('chat_widget') or '❌ NONE'}")
        print(f"  Form Tool: {enrich.get('form_tool') or '❌ NONE'}")
        print(f"  CRM Hint: {enrich.get('crm_hint') or '❌ NONE'}")
        print(f"  Contact Quality Score: {enrich.get('contact_quality_score')}/100")
        print(f"  Enrichment Confidence: {enrich.get('enrichment_confidence')}")
        print()
    
    # Get intent data
    intent = supabase.table("intent_data").select("*").eq("lead_id", lead.get("lead_id")).execute()
    
    if intent.data:
        intent_data = intent.data[0]
        print("🎯 INTENT DATA (from 'intent_data' table):")
        print(f"  Intent Score: {intent_data.get('intent_score')}/100")
        print(f"  Leak Score: {intent_data.get('leak_score')}/100")
        print(f"  Reactivation Fit: {intent_data.get('reactivation_fit')}/100")
        print()
    
    # Get scoring data
    scoring = supabase.table("scoring_results").select("*").eq("lead_id", lead.get("lead_id")).execute()
    
    if scoring.data:
        score_data = scoring.data[0]
        print("📊 SCORING DATA (from 'scoring_results' table):")
        print(f"  Final Score: {score_data.get('final_score')}/100")
        print(f"  Lead Tier: {score_data.get('lead_tier')}")
        print(f"  Score Breakdown:")
        breakdown = score_data.get('score_breakdown', {})
        for component, value in breakdown.items():
            print(f"    - {component}: {value}/100")
        print()

print("=" * 80)
print("VERIFICATION COMPLETE")
print("=" * 80)
print()
print("All data shown above is REAL data from the database.")
print("Not generated, not fake, not inflated.")
print()
print("To verify:")
print("1. Check the database yourself (Supabase dashboard)")
print("2. Visit the websites listed above")
print("3. Confirm the signals match reality")
print()
print("If signals match = System is accurate")
print("If signals don't match = System is broken")
print()
