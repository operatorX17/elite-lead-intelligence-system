ot tested with Steel.dev
       - Outreach: Not tested with real leads
    
    ⚠️  DATA GAP:
       - Your 5 hospitals missing: reviews_count, rating, popularTimesHistogram
       - Need to run Apify Google Maps scraper to get this data
       - Then run enrichment → intent → scoring pipeline
    """)
    
    print("\n" + "=" * 80)
    print("END OF STATUS REPORT")
    print("=" * 80)

if __name__ == "__main__":
    main()
ent Agent (with volume signal extraction)
       - Intent Agent (with volume score calculation)
       - Scoring Agent (with 15% volume weight)
       - Audit Agent (Steel.dev integration)
       - Outreach Agent (LLM-based)
       - Database schema (with volume columns)
    
    ❌ NOT TESTED WITH REAL DATA:
       - Discovery: Not run on your 5 hospitals
       - Enrichment: No Google Maps data scraped
       - Intent: No volume scores calculated
       - Scoring: No real scores with volume
       - Audit: Nting else '❌ MISSING'}")
                print(f"         - Popular Times: {'YES' if has_popular_times else '❌ MISSING'}")
    except Exception as e:
        print(f"   ❌ Error reading hospital file: {e}")
    
    # 8. Pipeline Status Summary
    print("\n8. PIPELINE STATUS SUMMARY")
    print("-" * 80)
    print("""
    FULL PIPELINE: Discovery → Enrichment → Intent → Audit → Scoring → Outreach → Conversation
    
    ✅ IMPLEMENTED (Code exists):
       - Discovery Agent (Apify integration)
       - Enrichmunt' in h['hospital']
                has_rating = 'rating' in h['hospital']
                has_popular_times = 'popularTimesHistogram' in h['hospital']
                
                print(f"\n   Hospital {i}: {name}")
                print(f"      Website: {website}")
                print(f"      Phone: {phone}")
                print(f"      Google Maps Data:")
                print(f"         - Reviews: {'YES' if has_reviews else '❌ MISSING'}")
                print(f"         - Rating: {'YES' if has_ra.json', 'r') as f:
            hospitals = json.load(f)
            print(f"   Total hospitals in file: {len(hospitals)}")
            
            for i, h in enumerate(hospitals, 1):
                name = h['hospital']['business_name'][:50]
                website = h['hospital'].get('website', 'NO WEBSITE')
                phone = h['hospital'].get('phone', 'NO PHONE')
                
                # Check for Google Maps data
                has_reviews = 'reviews_count' in h['hospital'] or 'review_co        try:
            with open(path, 'r') as f:
                content = f.read()
                has_volume = 'volume' in content.lower()
                print(f"   ✅ {agent_name}: Implemented (volume signals: {'YES' if has_volume else 'NO'})")
        except Exception as e:
            print(f"   ❌ {agent_name}: NOT FOUND")
    
    # 7. Hospital Data Analysis
    print("\n7. HOSPITAL DATA ANALYSIS (Your 5 Hospitals)")
    print("-" * 80)
    try:
        with open('ELITE_INTELLIGENCE_Hyderabad_5_hospitals e:
        print(f"   ❌ Error checking volume signals: {e}")
    
    # 6. Agent Implementation Status
    print("\n6. AGENT IMPLEMENTATION STATUS")
    print("-" * 80)
    agents = [
        ('Discovery', 'src/agents/discovery.py'),
        ('Enrichment', 'src/agents/enrichment.py'),
        ('Intent', 'src/agents/intent.py'),
        ('Scoring', 'src/agents/scoring.py'),
        ('Audit', 'src/agents/audit.py'),
        ('Outreach', 'src/agents/outreach.py'),
    ]
    
    for agent_name, path in agents:
      has_volume = any(field in sample for field in volume_fields)
            if has_volume:
                print(f"   ✅ Volume signal columns exist in enrichment_data")
                for field in volume_fields:
                    if field in sample:
                        print(f"      - {field}: {sample[field]}")
            else:
                print(f"   ⚠️  Volume signal columns NOT FOUND in enrichment_data")
        else:
            print(f"   ⚠️  No enrichment data to check")
    except Exception asIMPLEMENTATION")
    print("-" * 80)
    try:
        # Check if enrichment_data table has volume columns
        enrichment = client.client.table('enrichment_data').select('*').limit(1).execute()
        if enrichment.data:
            sample = enrichment.data[0]
            volume_fields = [
                'peak_busyness', 'avg_busyness', 'busy_hours_count',
                'avg_visit_duration_min', 'popular_times_histogram',
                'opening_hours', 'reviews_distribution'
            ]
            
       Sample leads:")
            for lead in leads.data[:5]:
                name = lead.get('business_name', 'Unknown')[:40]
                category = lead.get('category', 'N/A')
                state = lead.get('lead_lifecycle_state', 'N/A')
                print(f"   - {name}: {category} ({state})")
        else:
            print(f"   ⚠️  NO LEADS IN DATABASE")
    except Exception as e:
        print(f"   ❌ Error reading leads: {e}")
    
    # 5. Volume Signals Implementation
    print("\n5. VOLUME SIGNALS ).execute()
        print(f"   Total leads in DB: {len(leads.data)}")
        
        if leads.data:
            print(f"\n  e_metrics', 'circuit_breakers'
    ]
    
    for table in tables:
        try:
            result = client.client.table(table).select('*', count='exact').limit(0).execute()
            count = result.count or 0
            print(f"   ✅ {table}: {count} records")
        except Exception as e:
            print(f"   ❌ {table}: ERROR - {str(e)[:50]}")
    
    # 4. Lead Data Status
    print("\n4. LEAD DATA STATUS")
    print("-" * 80)
    try:
        leads = client.client.table('leads').select('*').limit(10
        print(f"✅ Supabase connected successfully")
        print(f"   Can query tables: YES")
    except Exception as e:
        print(f"❌ Supabase connection failed: {e}")
        return
    
    # 3. Database Tables Status
    print("\n3. DATABASE TABLES STATUS")
    print("-" * 80)
    tables = [
        'leads', 'lead_state', 'enrichment_data', 'intent_data',
        'scoring_results', 'proof_artifacts', 'outreach_queue',
        'conversations', 'negative_signals', 'do_not_contact',
        'audit_log', 'usagfig.database.supabase_url[:40]}...")
        print(f"   Apify token: {'SET' if config.apify.api_token else 'NOT SET'}")
    except Exception as e:
        print(f"❌ Config error: {e}")
    
    # 2. Database Connection
    print("\n2. DATABASE CONNECTION")
    print("-" * 80)
    try:
        client = SupabaseClient()
        result = client.client.table('leads').select('lead_id').limit(1).execute()ort SupabaseClient
from src.config import load_config
import json

def main():
    print("=" * 80)
    print("ZRAI LEAD OS - COMPLETE SYSTEM STATUS")
    print("=" * 80)
    
    # 1. Configuration Check
    print("\n1. CONFIGURATION STATUS")
    print("-" * 80)
    try:
        config = load_config()
        print(f"✅ Config loaded successfully")
        print(f"   Environment: {config.system.environment}")
        print(f"   Kill switches: {config.system.kill_switches}")
        print(f"   Supabase URL: {conem status check for ZRAI Lead OS.
Shows what's working, what's not, and what data we have.
"""

import sys
sys.path.append('src')

from src.db.client imp
Complete syst"""