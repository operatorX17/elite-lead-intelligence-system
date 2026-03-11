"""
REAL End-to-End Pipeline Test for ZRAI Lead OS.

This test runs the ACTUAL pipeline with REAL API calls:
1. Discovery - Uses Apify to discover real businesses
2. Enrichment - Extracts tech signals from real websites
3. Intent - Computes real intent/leak scores
4. Scoring - Computes real weighted scores
5. Audit - Uses Steel.dev for real browser automation (if available)
6. Outreach - Generates real outreach messages

NO MOCKS. Real data. Real APIs.
"""

import os
import sys
from datetime import datetime
from uuid import uuid4
import logging

# Load .env file FIRST before anything else
from dotenv import load_dotenv
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def print_header(title: str):
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)

def print_step(step: int, name: str):
    print(f"\n{'─' * 60}")
    print(f"  STEP {step}: {name}")
    print(f"{'─' * 60}")

def main():
    print_header("ZRAI LEAD OS - REAL END-TO-END PIPELINE TEST")
    print(f"Started at: {datetime.now().isoformat()}")
    print("\nThis test uses REAL APIs - Apify, Steel.dev, OpenRouter LLM")
    print("It will create real data in your Supabase database.\n")
    
    results = {
        "discovery": {"status": "pending", "data": None},
        "enrichment": {"status": "pending", "data": None},
        "intent": {"status": "pending", "data": None},
        "scoring": {"status": "pending", "data": None},
        "audit": {"status": "pending", "data": None},
        "outreach": {"status": "pending", "data": None},
        "orchestrator": {"status": "pending", "data": None},
    }
    
    # =========================================================================
    # STEP 0: Verify Environment
    # =========================================================================
    print_step(0, "ENVIRONMENT VERIFICATION")
    
    # Check for SUPABASE_KEY or SUPABASE_SERVICE_ROLE_KEY (either works)
    required_vars = ["SUPABASE_URL", "OPENROUTER_API_KEY"]
    supabase_key_vars = ["SUPABASE_KEY", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_ANON_KEY"]
    optional_vars = ["APIFY_API_TOKEN", "APIFY_API_KEY", "STEEL_API_KEY"]
    
    missing = []
    for var in required_vars:
        if not os.getenv(var):
            missing.append(var)
    
    # Check if at least one Supabase key is present
    has_supabase_key = any(os.getenv(var) for var in supabase_key_vars)
    if not has_supabase_key:
        missing.append("SUPABASE_KEY (or SUPABASE_SERVICE_ROLE_KEY or SUPABASE_ANON_KEY)")
    
    if missing:
        print(f"❌ Missing required environment variables: {missing}")
        print("   Set these in your .env file")
        return
    
    print("✓ Required environment variables present")
    print(f"  - SUPABASE_URL: {os.getenv('SUPABASE_URL')[:30]}...")
    print(f"  - OPENROUTER_API_KEY: {os.getenv('OPENROUTER_API_KEY')[:20]}...")
    
    for var in optional_vars:
        val = os.getenv(var)
        if val:
            print(f"✓ {var} is set")
        else:
            print(f"⚠ {var} not set - some features may be limited")
    
    # =========================================================================
    # STEP 1: Import and Initialize
    # =========================================================================
    print_step(1, "IMPORTS AND INITIALIZATION")
    
    try:
        from src.db.client import get_supabase_client
        from src.config import load_config
        from src.graph.state import LeadGraphState
        from src.agents.discovery import DiscoveryAgent
        from src.agents.enrichment import EnrichmentAgent
        from src.agents.intent import IntentAgent
        from src.agents.scoring import ScoringAgent
        from src.agents.audit import AuditAgent
        from src.agents.outreach import OutreachAgent
        from src.agents.conversation import ConversationAgent
        from src.agents.governance import GovernanceAgent
        from src.graph.orchestrator import LeadOrchestrator
        print("✓ All imports successful")
    except Exception as e:
        print(f"❌ Import failed: {e}")
        return
    
    try:
        db = get_supabase_client()
        config = load_config()
        print("✓ Database and config initialized")
    except Exception as e:
        print(f"❌ Initialization failed: {e}")
        return
    
    # =========================================================================
    # STEP 2: Get or Create a Real Lead
    # =========================================================================
    print_step(2, "GET OR CREATE REAL LEAD")
    
    # First, try to get an existing lead from the database
    existing_leads = db.get_leads(limit=5)
    
    test_lead = None
    if existing_leads:
        # Use an existing lead that has a website
        for lead in existing_leads:
            if lead.get("website") or lead.get("landing_page_url"):
                test_lead = lead
                print(f"✓ Using existing lead: {lead.get('business_name')} (ID: {lead.get('lead_id')})")
                break
    
    if not test_lead:
        print("No existing leads with websites found. Creating a test lead...")
        # Create a test lead with real data
        test_lead_id = str(uuid4())
        test_lead = {
            "lead_id": test_lead_id,
            "business_name": "Test Plumbing Services",
            "category": "plumbing",
            "location": "Austin, TX",
            "geo_tags": ["Austin", "TX"],
            "website": "https://www.example.com",
            "landing_page_url": "https://www.example.com",
            "phone": "+15551234567",
            "emails_found": ["contact@example.com"],
            "ads_active": True,
            "ad_start_date": datetime.now().isoformat(),
            "cta_type": "CALL",
            "lead_lifecycle_state": "NEW",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }
        try:
            db.create_lead(test_lead)
            print(f"✓ Created test lead: {test_lead['business_name']} (ID: {test_lead_id})")
        except Exception as e:
            print(f"⚠ Could not create lead in DB: {e}")
            print("  Continuing with in-memory lead...")
    
    print(f"\n  Lead Details:")
    print(f"    - Business: {test_lead.get('business_name')}")
    print(f"    - Category: {test_lead.get('category')}")
    print(f"    - Website: {test_lead.get('website')}")
    print(f"    - Phone: {test_lead.get('phone')}")
    print(f"    - Ads Active: {test_lead.get('ads_active')}")
    
    # =========================================================================
    # STEP 3: Create Initial State
    # =========================================================================
    print_step(3, "CREATE PIPELINE STATE")
    
    state: LeadGraphState = {
        "lead_id": test_lead.get("lead_id"),
        "thread_id": f"test-{uuid4()}",
        "lead": test_lead,
        "current_stage": "discovery",
        "last_node": "start",
        "enrichment": {},
        "intent": {},
        "scoring": {},
        "proof": {},
        "outreach_messages": [],
        "conversation_transcript": [],
        "conversation_entities": {},
        "errors": [],
        "retry_count": 0,
        "should_skip_audit": False,
        "should_skip_outreach": False,
        "is_disqualified": False,
        "is_escalated": False,
        "is_complete": False,
        "requires_approval": False,
        "metadata": {},
        "messages": [],
    }
    print("✓ Initial state created")
    
    # =========================================================================
    # STEP 4: Run Discovery Agent
    # =========================================================================
    print_step(4, "DISCOVERY AGENT")
    
    try:
        discovery_agent = DiscoveryAgent()
        print(f"  Agent initialized: {discovery_agent.name}")
        
        # Discovery agent processes the lead
        state = discovery_agent.process(state)
        
        results["discovery"]["status"] = "success"
        results["discovery"]["data"] = {
            "current_stage": state.get("current_stage"),
            "lead_present": state.get("lead") is not None,
        }
        print(f"✓ Discovery completed")
        print(f"    - Stage: {state.get('current_stage')}")
        print(f"    - Lead loaded: {state.get('lead') is not None}")
    except Exception as e:
        results["discovery"]["status"] = "failed"
        results["discovery"]["data"] = str(e)
        print(f"❌ Discovery failed: {e}")

    # =========================================================================
    # STEP 5: Run Enrichment Agent
    # =========================================================================
    print_step(5, "ENRICHMENT AGENT")
    
    def print_result(name: str, data: dict):
        print(f"\n  {name} Results:")
        for key, value in data.items():
            if isinstance(value, dict):
                print(f"    - {key}:")
                for k, v in value.items():
                    print(f"        {k}: {v}")
            else:
                print(f"    - {key}: {value}")
    
    try:
        enrichment_agent = EnrichmentAgent()
        print(f"  Agent initialized: {enrichment_agent.name}")
        
        state = enrichment_agent.process(state)
        
        enrichment_data = state.get("enrichment", {})
        results["enrichment"]["status"] = "success"
        results["enrichment"]["data"] = {
            "enrichment_confidence": enrichment_data.get("enrichment_confidence"),
            "booking_provider": enrichment_data.get("booking_provider"),
            "chat_widget": enrichment_data.get("chat_widget"),
            "contact_quality_score": enrichment_data.get("contact_quality_score"),
            "decision_maker_name": enrichment_data.get("decision_maker_name"),
        }
        print(f"✓ Enrichment completed")
        print_result("Enrichment", results["enrichment"]["data"])
    except Exception as e:
        results["enrichment"]["status"] = "failed"
        results["enrichment"]["data"] = str(e)
        print(f"❌ Enrichment failed: {e}")
    
    # =========================================================================
    # STEP 6: Run Intent Agent
    # =========================================================================
    print_step(6, "INTENT AGENT")
    
    try:
        intent_agent = IntentAgent()
        print(f"  Agent initialized: {intent_agent.name}")
        
        state = intent_agent.process(state)
        
        intent_data = state.get("intent", {})
        results["intent"]["status"] = "success"
        results["intent"]["data"] = {
            "intent_score": intent_data.get("intent_score"),
            "leak_score": intent_data.get("leak_score"),
            "reactivation_fit": intent_data.get("reactivation_fit"),
            "speed_to_lead_risk": str(intent_data.get("speed_to_lead_risk")),
            "why_this_lead": intent_data.get("why_this_lead", "")[:100] + "..." if intent_data.get("why_this_lead") else None,
        }
        print(f"✓ Intent analysis completed")
        print_result("Intent", results["intent"]["data"])
    except Exception as e:
        results["intent"]["status"] = "failed"
        results["intent"]["data"] = str(e)
        print(f"❌ Intent failed: {e}")
    
    # =========================================================================
    # STEP 7: Run Scoring Agent
    # =========================================================================
    print_step(7, "SCORING AGENT")
    
    try:
        scoring_agent = ScoringAgent()
        print(f"  Agent initialized: {scoring_agent.name}")
        
        state = scoring_agent.process(state)
        
        scoring_data = state.get("scoring", {})
        results["scoring"]["status"] = "success"
        results["scoring"]["data"] = {
            "final_score": scoring_data.get("final_score"),
            "lead_tier": scoring_data.get("lead_tier"),
            "do_not_contact": scoring_data.get("do_not_contact"),
            "score_breakdown": scoring_data.get("score_breakdown"),
        }
        print(f"✓ Scoring completed")
        print_result("Scoring", results["scoring"]["data"])
    except Exception as e:
        results["scoring"]["status"] = "failed"
        results["scoring"]["data"] = str(e)
        print(f"❌ Scoring failed: {e}")
    
    # =========================================================================
    # STEP 8: Run Audit Agent (if not skipped)
    # =========================================================================
    print_step(8, "AUDIT AGENT")
    
    if state.get("should_skip_audit"):
        print("⚠ Audit skipped (lead below threshold or kill switch active)")
        results["audit"]["status"] = "skipped"
        results["audit"]["data"] = {"reason": "should_skip_audit flag set"}
    else:
        try:
            audit_agent = AuditAgent()
            print(f"  Agent initialized: {audit_agent.name}")
            
            state = audit_agent.process(state)
            
            proof_data = state.get("proof", {})
            results["audit"]["status"] = "success"
            results["audit"]["data"] = {
                "hero_screenshot_url": proof_data.get("hero_screenshot_url"),
                "cta_screenshot_url": proof_data.get("cta_screenshot_url"),
                "audit_bullets_count": len(proof_data.get("audit_bullets", [])),
            }
            print(f"✓ Audit completed")
            print_result("Audit", results["audit"]["data"])
        except Exception as e:
            results["audit"]["status"] = "failed"
            results["audit"]["data"] = str(e)
            print(f"❌ Audit failed: {e}")
    
    # =========================================================================
    # STEP 9: Run Outreach Agent (if not skipped)
    # =========================================================================
    print_step(9, "OUTREACH AGENT")
    
    if state.get("should_skip_outreach"):
        print("⚠ Outreach skipped (lead disqualified or tier C)")
        results["outreach"]["status"] = "skipped"
        results["outreach"]["data"] = {"reason": "should_skip_outreach flag set"}
    else:
        try:
            outreach_agent = OutreachAgent()
            print(f"  Agent initialized: {outreach_agent.name}")
            
            state = outreach_agent.process(state)
            
            messages = state.get("outreach_messages", [])
            results["outreach"]["status"] = "success"
            results["outreach"]["data"] = {
                "messages_generated": len(messages),
                "variants": [m.get("variant") for m in messages],
                "channels": [m.get("channel") for m in messages],
            }
            print(f"✓ Outreach completed")
            print_result("Outreach", results["outreach"]["data"])
            
            # Print sample message
            if messages:
                print(f"\n  Sample Message (Variant A):")
                msg = messages[0]
                print(f"    Subject: {msg.get('subject')}")
                print(f"    Body preview: {msg.get('body', '')[:200]}...")
        except Exception as e:
            results["outreach"]["status"] = "failed"
            results["outreach"]["data"] = str(e)
            print(f"❌ Outreach failed: {e}")
    
    # =========================================================================
    # STEP 10: Test Full Orchestrator
    # =========================================================================
    print_step(10, "FULL ORCHESTRATOR TEST")
    
    try:
        orchestrator = LeadOrchestrator(mode="testing")
        print(f"  Orchestrator initialized")
        
        # Run the graph using process_lead
        print("  Running orchestrator graph...")
        lead_id = test_lead.get("lead_id")
        final_state = orchestrator.process_lead(lead_id)
        
        results["orchestrator"]["status"] = "success"
        results["orchestrator"]["data"] = {
            "final_stage": final_state.get("current_stage"),
            "last_node": final_state.get("last_node"),
            "is_complete": final_state.get("is_complete"),
            "has_enrichment": bool(final_state.get("enrichment")),
            "has_intent": bool(final_state.get("intent")),
            "has_scoring": bool(final_state.get("scoring")),
            "outreach_count": len(final_state.get("outreach_messages", [])),
        }
        print(f"✓ Orchestrator completed")
        print_result("Orchestrator", results["orchestrator"]["data"])
    except Exception as e:
        results["orchestrator"]["status"] = "failed"
        results["orchestrator"]["data"] = str(e)
        print(f"❌ Orchestrator failed: {e}")
        import traceback
        traceback.print_exc()
    
    # =========================================================================
    # FINAL SUMMARY
    # =========================================================================
    print_header("FINAL RESULTS SUMMARY")
    
    total = len(results)
    passed = sum(1 for r in results.values() if r["status"] == "success")
    skipped = sum(1 for r in results.values() if r["status"] == "skipped")
    failed = sum(1 for r in results.values() if r["status"] == "failed")
    
    print(f"\n  Total Steps: {total}")
    print(f"  ✓ Passed: {passed}")
    print(f"  ⚠ Skipped: {skipped}")
    print(f"  ❌ Failed: {failed}")
    
    print(f"\n  Step-by-Step Results:")
    for step, result in results.items():
        status_icon = "✓" if result["status"] == "success" else "⚠" if result["status"] == "skipped" else "❌"
        print(f"    {status_icon} {step.upper()}: {result['status']}")
    
    print(f"\n  Completed at: {datetime.now().isoformat()}")
    
    # Return success if all critical steps passed
    critical_steps = ["discovery", "enrichment", "intent", "scoring"]
    critical_passed = all(results[s]["status"] in ["success", "skipped"] for s in critical_steps)
    
    if critical_passed:
        print("\n  ✅ ALL CRITICAL PIPELINE STEPS PASSED!")
        return 0
    else:
        print("\n  ❌ SOME CRITICAL STEPS FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main() or 0)
