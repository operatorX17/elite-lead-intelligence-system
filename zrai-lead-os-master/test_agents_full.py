#!/usr/bin/env python3
"""
COMPREHENSIVE AGENT FUNCTIONALITY TEST
Tests all agents actually processing data through the pipeline.
"""

import os
import sys
from uuid import uuid4, UUID
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 70)
print("ZRAI LEAD-OS AGENT FUNCTIONALITY TEST")
print("=" * 70)
print(f"Started at: {datetime.now().isoformat()}\n")

passed = 0
failed = 0
results = []

def test(name, func):
    global passed, failed
    try:
        result = func()
        if result:
            print(f"✓ {name}")
            passed += 1
            results.append((name, "PASS", None))
            return True
        else:
            print(f"✗ {name} - returned False")
            failed += 1
            results.append((name, "FAIL", "returned False"))
            return False
    except Exception as e:
        print(f"✗ {name} - {e}")
        failed += 1
        results.append((name, "FAIL", str(e)))
        return False

def section(title):
    print(f"\n{'=' * 70}")
    print(f"TEST: {title}")
    print("=" * 70)

# ============================================================================
# 1. TEST IMPORTS AND BASIC SETUP
# ============================================================================
section("1. IMPORTS AND SETUP")

def test_imports():
    from src.db.models import Lead, LeadLifecycleState
    from src.graph.state import LeadGraphState
    from src.config import load_config
    return True

test("Core imports", test_imports)

def test_config():
    from src.config import load_config
    config = load_config()
    return config is not None and hasattr(config, 'budget')

test("Config loading", test_config)

# ============================================================================
# 2. CREATE TEST LEAD DATA
# ============================================================================
section("2. TEST DATA CREATION")

# Create a test lead for all agents to process
TEST_LEAD_ID = uuid4()
TEST_LEAD = None
TEST_LEAD_DATA = None

def create_test_lead():
    global TEST_LEAD, TEST_LEAD_DATA
    from src.db.models import Lead, LeadLifecycleState
    
    TEST_LEAD = Lead(
        lead_id=TEST_LEAD_ID,
        business_name="Test Restaurant ABC",
        category="restaurants",
        location="San Francisco, CA",
        geo_tags=["us", "california", "san-francisco"],
        website="https://testrestaurant.com",
        landing_page_url="https://testrestaurant.com",
        phone="+1-555-123-4567",
        emails_found=["contact@testrestaurant.com", "info@testrestaurant.com"],
        facebook_page="https://facebook.com/testrestaurant",
        instagram="@testrestaurant",
        ads_active=True,
        lead_lifecycle_state=LeadLifecycleState.NEW,
    )
    
    # Create dict version for state
    TEST_LEAD_DATA = {
        "lead_id": str(TEST_LEAD_ID),
        "business_name": "Test Restaurant ABC",
        "category": "restaurants",
        "location": "San Francisco, CA",
        "website": "https://testrestaurant.com",
        "phone": "+1-555-123-4567",
        "emails_found": ["contact@testrestaurant.com"],
        "lead_lifecycle_state": "NEW",
    }
    
    return TEST_LEAD is not None

test("Create test Lead model", create_test_lead)

def create_test_state():
    """Create state as a dict (how LangGraph uses it)"""
    state = {
        "lead_id": TEST_LEAD_ID,
        "thread_id": str(TEST_LEAD_ID),
        "lead": TEST_LEAD_DATA,
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
        "approval_status": None,
        "approval_notes": None,
        "metadata": {},
        "messages": [],
    }
    return state is not None and state["lead_id"] == TEST_LEAD_ID

test("Create state dict", create_test_state)

# Helper to create state dict
def make_state(stage="discovery", last_node="start"):
    return {
        "lead_id": TEST_LEAD_ID,
        "thread_id": str(TEST_LEAD_ID),
        "lead": TEST_LEAD_DATA,
        "current_stage": stage,
        "last_node": last_node,
        "enrichment": {},
        "intent": {"intent_score": 80, "leak_score": 75},
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
        "approval_status": None,
        "approval_notes": None,
        "metadata": {},
        "messages": [],
    }

# ============================================================================
# 3. DISCOVERY AGENT
# ============================================================================
section("3. DISCOVERY AGENT")

def test_discovery_agent_init():
    from src.agents.discovery import DiscoveryAgent
    agent = DiscoveryAgent()
    return agent is not None and hasattr(agent, 'process')

test("DiscoveryAgent initialization", test_discovery_agent_init)

def test_discovery_agent_process():
    from src.agents.discovery import DiscoveryAgent
    
    agent = DiscoveryAgent()
    state = make_state("discovery", "start")
    
    # Process the state
    result = agent.process(state)
    
    # Check result is valid
    return result is not None

test("DiscoveryAgent.process()", test_discovery_agent_process)

# ============================================================================
# 4. ENRICHMENT AGENT
# ============================================================================
section("4. ENRICHMENT AGENT")

def test_enrichment_agent_init():
    from src.agents.enrichment import EnrichmentAgent
    agent = EnrichmentAgent()
    return agent is not None and hasattr(agent, 'process')

test("EnrichmentAgent initialization", test_enrichment_agent_init)

def test_enrichment_agent_process():
    from src.agents.enrichment import EnrichmentAgent
    
    agent = EnrichmentAgent()
    state = make_state("enrichment", "discovery")
    
    result = agent.process(state)
    return result is not None

test("EnrichmentAgent.process()", test_enrichment_agent_process)

# ============================================================================
# 5. INTENT AGENT
# ============================================================================
section("5. INTENT AGENT")

def test_intent_agent_init():
    from src.agents.intent import IntentAgent
    agent = IntentAgent()
    return agent is not None and hasattr(agent, 'process')

test("IntentAgent initialization", test_intent_agent_init)

def test_intent_agent_process():
    from src.agents.intent import IntentAgent
    
    agent = IntentAgent()
    state = make_state("intent", "enrichment")
    
    result = agent.process(state)
    return result is not None

test("IntentAgent.process()", test_intent_agent_process)

# ============================================================================
# 6. AUDIT AGENT
# ============================================================================
section("6. AUDIT AGENT")

def test_audit_agent_init():
    from src.agents.audit import AuditAgent
    agent = AuditAgent()
    return agent is not None and hasattr(agent, 'process')

test("AuditAgent initialization", test_audit_agent_init)

def test_audit_agent_process():
    from src.agents.audit import AuditAgent
    
    agent = AuditAgent()
    state = make_state("audit", "governance")
    
    result = agent.process(state)
    return result is not None

test("AuditAgent.process()", test_audit_agent_process)

# ============================================================================
# 7. SCORING AGENT
# ============================================================================
section("7. SCORING AGENT")

def test_scoring_agent_init():
    from src.agents.scoring import ScoringAgent
    agent = ScoringAgent()
    return agent is not None and hasattr(agent, 'process')

test("ScoringAgent initialization", test_scoring_agent_init)

def test_scoring_agent_process():
    from src.agents.scoring import ScoringAgent
    
    agent = ScoringAgent()
    state = make_state("scoring", "audit")
    
    result = agent.process(state)
    return result is not None

test("ScoringAgent.process()", test_scoring_agent_process)

# ============================================================================
# 8. OUTREACH AGENT
# ============================================================================
section("8. OUTREACH AGENT")

def test_outreach_agent_init():
    from src.agents.outreach import OutreachAgent
    agent = OutreachAgent()
    return agent is not None and hasattr(agent, 'process')

test("OutreachAgent initialization", test_outreach_agent_init)

def test_outreach_agent_process():
    from src.agents.outreach import OutreachAgent
    
    agent = OutreachAgent()
    state = make_state("outreach", "scoring")
    
    result = agent.process(state)
    return result is not None

test("OutreachAgent.process()", test_outreach_agent_process)

# ============================================================================
# 9. CONVERSATION AGENT
# ============================================================================
section("9. CONVERSATION AGENT")

def test_conversation_agent_init():
    from src.agents.conversation import ConversationAgent
    agent = ConversationAgent()
    return agent is not None and hasattr(agent, 'process')

test("ConversationAgent initialization", test_conversation_agent_init)

def test_conversation_agent_process():
    from src.agents.conversation import ConversationAgent
    
    agent = ConversationAgent()
    state = make_state("conversation", "outreach")
    state["metadata"] = {"incoming_message": "Hi, I'm interested", "channel": "email"}
    
    result = agent.process(state)
    return result is not None

test("ConversationAgent.process()", test_conversation_agent_process)

# ============================================================================
# 10. GOVERNANCE AGENT
# ============================================================================
section("10. GOVERNANCE AGENT")

def test_governance_agent_init():
    from src.agents.governance import GovernanceAgent
    agent = GovernanceAgent()
    return agent is not None and hasattr(agent, 'process')

test("GovernanceAgent initialization", test_governance_agent_init)

def test_governance_agent_process():
    from src.agents.governance import GovernanceAgent
    
    agent = GovernanceAgent()
    state = make_state("governance", "intent")
    
    result = agent.process(state)
    return result is not None

test("GovernanceAgent.process()", test_governance_agent_process)

# ============================================================================
# 11. LANGGRAPH ORCHESTRATOR
# ============================================================================
section("11. LANGGRAPH ORCHESTRATOR")

def test_orchestrator_init():
    from src.graph.orchestrator import LeadOrchestrator
    orchestrator = LeadOrchestrator(mode="testing")
    return orchestrator is not None and hasattr(orchestrator, '_graph')

test("LeadOrchestrator initialization", test_orchestrator_init)

def test_orchestrator_graph_structure():
    from src.graph.orchestrator import LeadOrchestrator
    orchestrator = LeadOrchestrator(mode="testing")
    
    # Check graph has expected nodes via mermaid
    mermaid = orchestrator.get_graph_mermaid()
    expected_nodes = ["discovery", "enrichment", "intent", "governance", "audit", "scoring", "outreach"]
    
    for node in expected_nodes:
        if node not in mermaid:
            print(f"  Missing node: {node}")
            return False
    
    return True

test("Graph structure (all nodes present)", test_orchestrator_graph_structure)

def test_graph_nodes():
    """Test individual graph node functions"""
    from src.graph.orchestrator import (
        discovery_node, enrichment_node, intent_node, 
        governance_node, scoring_node, outreach_node
    )
    
    state = make_state()
    
    # Test discovery node
    result = discovery_node(state)
    if not result or result.get("current_stage") != "discovery":
        return False
    
    # Test enrichment node
    result = enrichment_node(state)
    if not result or result.get("current_stage") != "enrichment":
        return False
    
    return True

test("Graph node functions", test_graph_nodes)

def test_orchestrator_dry_run():
    from src.graph.orchestrator import LeadOrchestrator
    from src.db.client import get_supabase_client
    
    orchestrator = LeadOrchestrator(mode="testing")
    db = get_supabase_client()
    
    # Get a real lead from DB for dry run
    leads = db.get_leads(limit=1)
    if not leads:
        print("  No leads in DB for dry run test")
        return True  # Skip if no leads
    
    lead_id = UUID(leads[0]["lead_id"])
    result = orchestrator.dry_run(lead_id)
    return result is not None

test("Orchestrator dry_run()", test_orchestrator_dry_run)

# ============================================================================
# 12. EXTERNAL TOOLS
# ============================================================================
section("12. EXTERNAL TOOLS")

def test_llm_client():
    from src.tools.llm import LLMClient
    client = LLMClient()
    return client is not None and hasattr(client, 'generate')

test("LLMClient initialization", test_llm_client)

def test_llm_actual_call():
    from src.tools.llm import LLMClient
    client = LLMClient()
    response = client.generate("Say 'test' and nothing else")
    return response is not None and len(response) > 0

test("LLMClient actual API call", test_llm_actual_call)

def test_apify_client():
    from src.tools.apify import ApifyClient
    client = ApifyClient()
    return client is not None

test("ApifyClient initialization", test_apify_client)

def test_steel_client():
    from src.tools.steel import SteelClient
    client = SteelClient()
    return client is not None

test("SteelClient initialization", test_steel_client)

# ============================================================================
# 13. DATABASE CLIENT
# ============================================================================
section("13. DATABASE CLIENT")

def test_db_client():
    from src.db.client import get_supabase_client
    client = get_supabase_client()
    return client is not None

test("SupabaseClient initialization", test_db_client)

def test_db_get_leads():
    from src.db.client import get_supabase_client
    client = get_supabase_client()
    leads = client.get_leads(limit=5)
    print(f"  Found {len(leads)} leads in database")
    return isinstance(leads, list)

test("Database get_leads()", test_db_get_leads)

def test_db_usage_metrics():
    from src.db.client import get_supabase_client
    from datetime import datetime
    client = get_supabase_client()
    metrics = client.get_or_create_usage_metrics(datetime.utcnow())
    return metrics is not None and "llm_tokens_used" in metrics

test("Database usage metrics", test_db_usage_metrics)

# ============================================================================
# 14. API ENDPOINTS WITH AGENTS
# ============================================================================
section("14. API ENDPOINTS (Agent Integration)")

def test_api_discover_mock():
    from src.api.server import app
    from fastapi.testclient import TestClient
    
    client = TestClient(app)
    r = client.post('/api/v1/discover', json={
        'niche': 'restaurants',
        'geo': 'us',
        'limit': 3,
        'mock': True
    })
    
    if r.status_code == 200:
        data = r.json()
        return data.get('count', 0) == 3
    return False

test("POST /api/v1/discover (mock mode)", test_api_discover_mock)

def test_api_governance():
    from src.api.server import app
    from fastapi.testclient import TestClient
    
    client = TestClient(app)
    r = client.get('/api/v1/governance')
    
    if r.status_code == 200:
        data = r.json()
        return 'budget' in data and 'kill_switches' in data
    return False

test("GET /api/v1/governance", test_api_governance)

def test_api_metrics():
    from src.api.server import app
    from fastapi.testclient import TestClient
    
    client = TestClient(app)
    r = client.get('/api/v1/metrics')
    
    if r.status_code == 200:
        data = r.json()
        return 'usage' in data and 'leads' in data
    return False

test("GET /api/v1/metrics", test_api_metrics)

def test_api_leads():
    from src.api.server import app
    from fastapi.testclient import TestClient
    
    client = TestClient(app)
    r = client.get('/api/v1/leads?page=1&page_size=5')
    
    if r.status_code == 200:
        data = r.json()
        return 'leads' in data and 'pagination' in data
    return False

test("GET /api/v1/leads", test_api_leads)

# ============================================================================
# 15. PROPERTY-BASED TESTS
# ============================================================================
section("15. PROPERTY-BASED TESTS")

def test_property_tests_exist():
    import os
    test_dir = "tests"
    if not os.path.exists(test_dir):
        return False
    
    property_tests = [f for f in os.listdir(test_dir) if f.startswith("test_property_")]
    print(f"  Found {len(property_tests)} property test files")
    return len(property_tests) >= 10

test("Property test files exist (>=10)", test_property_tests_exist)

# ============================================================================
# SUMMARY
# ============================================================================
print("\n" + "=" * 70)
print("TEST SUMMARY")
print("=" * 70)
print(f"\nTotal: {passed}/{passed + failed} tests passed")
print(f"Failed: {failed}")

if failed > 0:
    print("\nFailed tests:")
    for name, status, error in results:
        if status == "FAIL":
            print(f"  - {name}: {error}")

print(f"\nFinished at: {datetime.now().isoformat()}")

if failed == 0:
    print("\n🎉 ALL AGENT FUNCTIONALITY TESTS PASSED!")
else:
    print(f"\n⚠️  {failed} test(s) failed - review above for details")
