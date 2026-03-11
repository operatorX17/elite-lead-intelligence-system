"""
REAL PIPELINE TEST - No mock data
Tests: Discovery → Enrichment → Intent → Scoring
"""

import sys
sys.path.append('src')

from src.agents.discovery import DiscoveryAgent
from src.db.client import SupabaseClient
import json

def main():
    print("=" * 80)
    print("REAL PIPELINE TEST - HKC Hospital Hyderabad")
    print("=" * 80)
    
    # Step 1: Discovery (Apify Google Maps scraper)
    print("\n1. DISCOVERY - Running Apify Google Maps scraper...")
    print("-" * 80)
    
    try:
        agent = DiscoveryAgent()
        leads = agent.discover_from_google_maps(
            keywords=['HKC Hospital Hyderabad'],
            geo={'city': 'Hyderabad', 'state': 'Telangana', 'country': 'India'},
            limit=1,
            auto_process=True  # This runs enrichment + intent + scoring automatically
        )
        
        if not leads:
            print("❌ No leads found!")
            return
        
        lead = leads[0]
        print(f"✅ Discovery complete: {len(leads)} lead(s) found")
        print(f"\nLead Details:")
        print(f"  Business: {lead.business_name}")
        print(f"  Category: {lead.category}")
        print(f"  Location: {lead.location}")
        print(f"  Phone: {lead.phone}")
        print(f"  Website: {lead.website}")
        print(f"  Lead ID: {lead.lead_id}")
        
    except Exception as e:
        print(f"❌ Discovery failed: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Step 2: Check what Apify returned (RAW DATA)
    print("\n2. RAW APIFY DATA - What did Google Maps provide?")
    print("-" * 80)
    
    try:
        client = SupabaseClient()
        db_lead = client.get_lead(lead.lead_id)
        
        if db_lead:
            print("Raw lead data from Apify:")
            # Check for Google Maps specific fields
            gm_fields = [
                'reviews_count', 'reviewsCount', 'review_count',
                'rating', 'review_rating',
                'popularTimesHistogram', 'popular_times_histogram',
                'peopleTypicallySpendHere', 'people_typically_spend_here',
                'openingHours', 'opening_hours',
                'reviewsDistribution', 'reviews_distribution'
            ]
            
            for field in gm_fields:
                if field in db_lead:
                    value = db_lead[field]
                    if value:
                        print(f"  ✅ {field}: {str(value)[:100]}")
                    else:
                        print(f"  ⚠️  {field}: NULL")
        
    except Exception as e:
        print(f"❌ Error checking raw data: {e}")
    
    # Step 3: Check Enrichment Data
    print("\n3. ENRICHMENT - Volume signals extracted?")
    print("-" * 80)
    
    try:
        enrichment = client.get_enrichment_data(lead.lead_id)
        
        if enrichment:
            print("✅ Enrichment data exists")
            
            volume_fields = {
                'peak_busyness': 'Peak Busyness (0-100)',
                'avg_busyness': 'Avg Busyness (0-100)',
                'busy_hours_count': 'Busy Hours/Week',
                'avg_visit_duration_min': 'Avg Visit Duration (min)',
                'is_peak_busy': 'Is Peak Busy',
                'is_above_average': 'Is Above Average',
                'popular_times_histogram': 'Popular Times Data',
                'opening_hours': 'Opening Hours',
                'reviews_distribution': 'Reviews Distribution'
            }
            
            print("\nVolume Signals:")
            for field, label in volume_fields.items():
                value = enrichment.get(field)
                if value is not None:
                    if isinstance(value, (dict, list)):
                        print(f"  ✅ {label}: {len(value)} items")
                    else:
                        print(f"  ✅ {label}: {value}")
                else:
                    print(f"  ❌ {label}: NOT EXTRACTED")
            
            # Tech signals
            print("\nTech Signals:")
            print(f"  Booking provider: {enrichment.get('booking_provider') or 'None'}")
            print(f"  CRM hint: {enrichment.get('crm_hint') or 'None'}")
            print(f"  Chat widget: {enrichment.get('chat_widget') or 'None'}")
            print(f"  Contact quality: {enrichment.get('contact_quality_score')}/100")
            
        else:
            print("❌ No enrichment data found!")
            
    except Exception as e:
        print(f"❌ Error checking enrichment: {e}")
        import traceback
        traceback.print_exc()
    
    # Step 4: Check Intent Data
    print("\n4. INTENT - Volume score calculated?")
    print("-" * 80)
    
    try:
        intent = client.get_intent_data(lead.lead_id)
        
        if intent:
            print("✅ Intent data exists")
            print(f"\nScores:")
            print(f"  Volume score: {intent.get('volume_score')}/100")
            print(f"  Intent score: {intent.get('intent_score')}/100")
            print(f"  Leak score: {intent.get('leak_score')}/100")
            print(f"  Reactivation fit: {intent.get('reactivation_fit')}/100")
            print(f"\nSpeed to lead risk: {intent.get('speed_to_lead_risk')}")
            print(f"\nWhy this lead:")
            print(f"  {intent.get('why_this_lead')}")
        else:
            print("❌ No intent data found!")
            
    except Exception as e:
        print(f"❌ Error checking intent: {e}")
        import traceback
        traceback.print_exc()
    
    # Step 5: Check Scoring Results
    print("\n5. SCORING - Final score with volume weight?")
    print("-" * 80)
    
    try:
        scoring = client.get_scoring_result(lead.lead_id)
        
        if scoring:
            print("✅ Scoring data exists")
            print(f"\nFinal Results:")
            print(f"  Final score: {scoring.get('final_score')}/100")
            print(f"  Lead tier: {scoring.get('lead_tier')}")
            print(f"  Do not contact: {scoring.get('do_not_contact')}")
            
            breakdown = scoring.get('score_breakdown', {})
            if breakdown:
                print(f"\nScore Breakdown:")
                print(f"  Ad activity: {breakdown.get('ad_activity')}/100 (weight: 5%)")
                print(f"  Intent: {breakdown.get('intent')}/100 (weight: 30%)")
                print(f"  Leak: {breakdown.get('leak')}/100 (weight: 25%)")
                print(f"  Volume: {breakdown.get('volume')}/100 (weight: 15%) ← NEW")
                print(f"  Reactivation: {breakdown.get('reactivation')}/100 (weight: 15%)")
                print(f"  Contact quality: {breakdown.get('contact_quality')}/100 (weight: 10%)")
                
                # Calculate weighted contribution
                print(f"\nWeighted Contributions:")
                print(f"  Ad activity: {breakdown.get('ad_activity', 0) * 0.05:.1f}")
                print(f"  Intent: {breakdown.get('intent', 0) * 0.30:.1f}")
                print(f"  Leak: {breakdown.get('leak', 0) * 0.25:.1f}")
                print(f"  Volume: {breakdown.get('volume', 0) * 0.15:.1f} ← NEW")
                print(f"  Reactivation: {breakdown.get('reactivation', 0) * 0.15:.1f}")
                print(f"  Contact quality: {breakdown.get('contact_quality', 0) * 0.10:.1f}")
        else:
            print("❌ No scoring data found!")
            
    except Exception as e:
        print(f"❌ Error checking scoring: {e}")
        import traceback
        traceback.print_exc()
    
    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    has_enrichment = enrichment is not None
    has_intent = intent is not None
    has_scoring = scoring is not None
    
    has_volume_signals = False
    if enrichment:
        has_volume_signals = any([
            enrichment.get('peak_busyness'),
            enrichment.get('busy_hours_count'),
            enrichment.get('avg_visit_duration_min')
        ])
    
    has_volume_score = False
    if intent:
        has_volume_score = intent.get('volume_score') is not None and intent.get('volume_score') > 0
    
    print(f"\n✅ Discovery: PASSED")
    print(f"{'✅' if has_enrichment else '❌'} Enrichment: {'PASSED' if has_enrichment else 'FAILED'}")
    print(f"{'✅' if has_volume_signals else '❌'} Volume Signals: {'EXTRACTED' if has_volume_signals else 'NOT EXTRACTED'}")
    print(f"{'✅' if has_intent else '❌'} Intent: {'PASSED' if has_intent else 'FAILED'}")
    print(f"{'✅' if has_volume_score else '❌'} Volume Score: {'CALCULATED' if has_volume_score else 'NOT CALCULATED'}")
    print(f"{'✅' if has_scoring else '❌'} Scoring: {'PASSED' if has_scoring else 'FAILED'}")
    
    if has_scoring and scoring:
        final_score = scoring.get('final_score', 0)
        tier = scoring.get('lead_tier', 'C')
        print(f"\n🎯 FINAL RESULT: {final_score}/100 (Tier {tier})")
        
        if has_volume_score and intent:
            volume_contribution = intent.get('volume_score', 0) * 0.15
            print(f"   Volume contributed: {volume_contribution:.1f} points")

if __name__ == "__main__":
    main()
