"""
Show all data in the ZRAI Lead OS Supabase database.
"""
from dotenv import load_dotenv
load_dotenv()

import json
from src.db.client import get_supabase_client

def main():
    db = get_supabase_client()
    
    print("=" * 80)
    print("  ZRAI LEAD OS - DATABASE CONTENTS")
    print("=" * 80)
    
    # 1. LEADS
    print("\n" + "─" * 60)
    print("  LEADS TABLE")
    print("─" * 60)
    leads = db.get_leads(limit=100)
    print(f"Total leads: {len(leads)}")
    for i, lead in enumerate(leads, 1):
        print(f"\n  [{i}] {lead.get('business_name', 'Unknown')}")
        print(f"      ID: {lead.get('lead_id')}")
        print(f"      Category: {lead.get('category')}")
        print(f"      Location: {lead.get('location')}")
        print(f"      Website: {lead.get('website')}")
        print(f"      Phone: {lead.get('phone')}")
        print(f"      Emails: {lead.get('emails_found', [])}")
        print(f"      Lifecycle: {lead.get('lead_lifecycle_state')}")
        print(f"      Ads Active: {lead.get('ads_active')}")
        print(f"      Created: {lead.get('created_at')}")
    
    # 2. ENRICHMENT DATA
    print("\n" + "─" * 60)
    print("  ENRICHMENT DATA TABLE")
    print("─" * 60)
    try:
        result = db._client.table("enrichment_data").select("*").execute()
        enrichments = result.data if result.data else []
        print(f"Total enrichment records: {len(enrichments)}")
        for i, e in enumerate(enrichments, 1):
            print(f"\n  [{i}] Lead: {e.get('lead_id')}")
            print(f"      Confidence: {e.get('enrichment_confidence')}")
            print(f"      Booking Provider: {e.get('booking_provider')}")
            print(f"      Chat Widget: {e.get('chat_widget')}")
            print(f"      Contact Quality: {e.get('contact_quality_score')}")
            print(f"      Decision Maker: {e.get('decision_maker_name')}")
    except Exception as ex:
        print(f"  Error: {ex}")
    
    # 3. INTENT DATA
    print("\n" + "─" * 60)
    print("  INTENT DATA TABLE")
    print("─" * 60)
    try:
        result = db._client.table("intent_data").select("*").execute()
        intents = result.data if result.data else []
        print(f"Total intent records: {len(intents)}")
        for i, intent in enumerate(intents, 1):
            print(f"\n  [{i}] Lead: {intent.get('lead_id')}")
            print(f"      Intent Score: {intent.get('intent_score')}")
            print(f"      Leak Score: {intent.get('leak_score')}")
            print(f"      Reactivation Fit: {intent.get('reactivation_fit')}")
            print(f"      Speed to Lead Risk: {intent.get('speed_to_lead_risk')}")
            why = intent.get("why_this_lead", "")
            if why:
                print(f"      Why: {why[:150]}...")
    except Exception as ex:
        print(f"  Error: {ex}")
    
    # 4. SCORING RESULTS
    print("\n" + "─" * 60)
    print("  SCORING RESULTS TABLE")
    print("─" * 60)
    try:
        result = db._client.table("scoring_results").select("*").execute()
        scores = result.data if result.data else []
        print(f"Total scoring records: {len(scores)}")
        for i, s in enumerate(scores, 1):
            print(f"\n  [{i}] Lead: {s.get('lead_id')}")
            print(f"      Final Score: {s.get('final_score')}")
            print(f"      Lead Tier: {s.get('lead_tier')}")
            print(f"      Do Not Contact: {s.get('do_not_contact')}")
    except Exception as ex:
        print(f"  Error: {ex}")
    
    # 5. PROOF/AUDIT DATA
    print("\n" + "─" * 60)
    print("  PROOF DATA TABLE")
    print("─" * 60)
    try:
        result = db._client.table("proof_data").select("*").execute()
        proofs = result.data if result.data else []
        print(f"Total proof records: {len(proofs)}")
        for i, p in enumerate(proofs, 1):
            print(f"\n  [{i}] Lead: {p.get('lead_id')}")
            print(f"      Hero Screenshot: {p.get('hero_screenshot_url')}")
            print(f"      CTA Screenshot: {p.get('cta_screenshot_url')}")
            bullets = p.get("audit_bullets", [])
            print(f"      Audit Bullets: {len(bullets) if bullets else 0}")
    except Exception as ex:
        print(f"  Error/No table: {ex}")
    
    # 6. OUTREACH MESSAGES
    print("\n" + "─" * 60)
    print("  OUTREACH MESSAGES TABLE")
    print("─" * 60)
    try:
        result = db._client.table("outreach_messages").select("*").execute()
        messages = result.data if result.data else []
        print(f"Total outreach messages: {len(messages)}")
        for i, m in enumerate(messages, 1):
            print(f"\n  [{i}] Lead: {m.get('lead_id')}")
            print(f"      Channel: {m.get('channel')}")
            print(f"      Variant: {m.get('variant')}")
            print(f"      Subject: {m.get('subject')}")
            body = m.get("body", "")
            if body:
                print(f"      Body: {body[:100]}...")
            print(f"      Status: {m.get('status')}")
    except Exception as ex:
        print(f"  Error/No table: {ex}")
    
    # 7. USAGE METRICS
    print("\n" + "─" * 60)
    print("  USAGE METRICS TABLE")
    print("─" * 60)
    try:
        result = db._client.table("usage_metrics").select("*").execute()
        metrics = result.data if result.data else []
        print(f"Total metric records: {len(metrics)}")
        for i, m in enumerate(metrics, 1):
            print(f"\n  [{i}] Date: {m.get('metric_date')}")
            print(f"      LLM Tokens: {m.get('llm_tokens_used')}")
            print(f"      Browser Sessions: {m.get('browser_sessions_used')}")
            print(f"      Scraper Runs: {m.get('scraper_runs_used')}")
            print(f"      Emails Sent: {m.get('emails_sent')}")
    except Exception as ex:
        print(f"  Error: {ex}")
    
    # 8. CIRCUIT BREAKERS
    print("\n" + "─" * 60)
    print("  CIRCUIT BREAKERS TABLE")
    print("─" * 60)
    try:
        result = db._client.table("circuit_breakers").select("*").execute()
        breakers = result.data if result.data else []
        print(f"Total circuit breaker records: {len(breakers)}")
        for i, b in enumerate(breakers, 1):
            print(f"\n  [{i}] Node: {b.get('node_name')}")
            print(f"      State: {b.get('state')}")
            print(f"      Failure Count: {b.get('failure_count')}")
            print(f"      Last Failure: {b.get('last_failure_at')}")
    except Exception as ex:
        print(f"  Error: {ex}")
    
    print("\n" + "=" * 80)
    print("  END OF DATABASE DUMP")
    print("=" * 80)

if __name__ == "__main__":
    main()
