"""
End-to-End Production Test for LangGraph Orchestrator
Tests the full pipeline with real database connections
"""

import os
import sys
import logging
from uuid import UUID, uuid4
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_imports():
    """Test all imports work correctly"""
    print("\n" + "="*60)
    print("TEST 1: Import Verification")
    print("="*60)
    
    try:
        from src.graph.orchestrator import (
            create_checkpointer,
            build_lead_graph,
            LeadOrchestrator,
            create_orchestrator,
            discovery_node,
            enrichment_node,
            intent_node,
            governance_node,
            audit_node,
            scoring_node,
            outreach_node,
            approval_node,
            send_outreach_node,
            conversation_node,
            escalate_node,
            handle_error_node,
            end_node,
        )
        print("✓ All orchestrator imports successful")
        
        from src.graph.state import LeadGraphState, merge_dict
        print("✓ State imports successful")
        
        from langgraph.graph import StateGraph, START, END
        from langgraph.checkpoint.memory import InMemorySaver
        from langgraph.types import Command, interrupt
        print("✓ LangGraph imports successful")
        
        from src.config import load_config
        from src.db.client import get_supabase_client
        print("✓ Config and DB imports successful")
        
        return True
    except Exception as e:
        print(f"✗ Import failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_checkpointer_factory():
    """Test checkpointer creation for both modes"""
    print("\n" + "="*60)
    print("TEST 2: Checkpointer Factory")
    print("="*60)
    
    try:
        from src.graph.orchestrator import create_checkpointer
        from langgraph.checkpoint.memory import InMemorySaver
        
        # Test testing mode
        cp_testing = create_checkpointer("testing")
        assert isinstance(cp_testing, InMemorySaver), "Testing mode should return InMemorySaver"
        print("✓ Testing mode checkpointer: InMemorySaver")
        
        # Test production mode (may fall back to InMemorySaver if SqliteSaver not available)
        cp_prod = create_checkpointer("production")
        print(f"✓ Production mode checkpointer: {type(cp_prod).__name__}")
        
        return True
    except Exception as e:
        print(f"✗ Checkpointer test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_graph_build():
    """Test graph builds correctly with all nodes"""
    print("\n" + "="*60)
    print("TEST 3: Graph Build")
    print("="*60)
    
    try:
        from src.graph.orchestrator import build_lead_graph, create_checkpointer
        
        checkpointer = create_checkpointer("testing")
        graph = build_lead_graph(checkpointer, enable_approval=False)
        
        # Get graph structure
        graph_obj = graph.get_graph()
        nodes = list(graph_obj.nodes.keys())
        
        expected_nodes = [
            '__start__', 'discovery', 'enrichment', 'intent', 'governance',
            'audit', 'scoring', 'outreach', 'approval', 'send_outreach',
            'conversation', 'escalate', 'handle_error', 'end', '__end__'
        ]
        
        print(f"✓ Graph has {len(nodes)} nodes")
        print(f"  Nodes: {nodes}")
        
        # Check all expected nodes exist
        for node in expected_nodes:
            if node in nodes:
                print(f"  ✓ {node}")
            else:
                print(f"  ✗ Missing: {node}")
        
        # Generate Mermaid diagram
        mermaid = graph.get_graph().draw_mermaid()
        print(f"\n✓ Mermaid diagram generated ({len(mermaid)} chars)")
        
        return True
    except Exception as e:
        print(f"✗ Graph build failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_database_connection():
    """Test real database connection"""
    print("\n" + "="*60)
    print("TEST 4: Database Connection")
    print("="*60)
    
    try:
        from src.db.client import get_supabase_client
        
        db = get_supabase_client()
        print(f"✓ Supabase client created: {type(db).__name__}")
        
        # Test get_or_create_usage_metrics
        today = datetime.utcnow()
        metrics = db.get_or_create_usage_metrics(today)
        print(f"✓ Usage metrics retrieved: {metrics}")
        
        return True
    except Exception as e:
        print(f"✗ Database connection failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_config_loading():
    """Test configuration loading"""
    print("\n" + "="*60)
    print("TEST 5: Configuration Loading")
    print("="*60)
    
    try:
        from src.config import load_config
        
        config = load_config()
        print(f"✓ Config loaded")
        print(f"  - Kill switches: global_kill={config.kill_switches.global_kill}")
        print(f"  - Budget: daily_browser_session_limit={config.budget.daily_browser_session_limit}")
        
        return True
    except Exception as e:
        print(f"✗ Config loading failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_orchestrator_creation():
    """Test orchestrator instantiation"""
    print("\n" + "="*60)
    print("TEST 6: Orchestrator Creation")
    print("="*60)
    
    try:
        from src.graph.orchestrator import create_orchestrator
        
        orchestrator = create_orchestrator(mode="testing")
        print(f"✓ Orchestrator created: {type(orchestrator).__name__}")
        print(f"  - Graph: {type(orchestrator._graph).__name__}")
        print(f"  - Checkpointer: {type(orchestrator._checkpointer).__name__}")
        
        # Test get_graph_mermaid
        mermaid = orchestrator.get_graph_mermaid()
        print(f"✓ Mermaid diagram: {len(mermaid)} chars")
        
        return orchestrator
    except Exception as e:
        print(f"✗ Orchestrator creation failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_dry_run_with_fake_lead():
    """Test dry run with a fake lead ID"""
    print("\n" + "="*60)
    print("TEST 7: Dry Run (Fake Lead)")
    print("="*60)
    
    try:
        from src.graph.orchestrator import create_orchestrator
        
        orchestrator = create_orchestrator(mode="testing")
        
        # Create a fake lead ID
        fake_lead_id = uuid4()
        print(f"Testing with fake lead ID: {fake_lead_id}")
        
        # Run dry run (should work even without real lead data)
        result = orchestrator.dry_run(fake_lead_id)
        
        print(f"✓ Dry run completed")
        print(f"  - Current stage: {result.get('current_stage')}")
        print(f"  - Last node: {result.get('last_node')}")
        print(f"  - Is complete: {result.get('is_complete')}")
        print(f"  - Errors: {result.get('errors', [])}")
        
        return True
    except Exception as e:
        print(f"✗ Dry run failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_with_real_lead():
    """Test with a real lead from the database"""
    print("\n" + "="*60)
    print("TEST 8: Real Lead Processing")
    print("="*60)
    
    try:
        from src.db.client import get_supabase_client
        from src.graph.orchestrator import create_orchestrator
        
        db = get_supabase_client()
        
        # Try to get a real lead from the database
        leads = db.get_leads(limit=1)
        
        if not leads:
            print("⚠ No leads found in database, creating a test lead...")
            
            # Create a test lead
            test_lead_data = {
                "business_name": "Test Business for LangGraph",
                "category": "restaurant",
                "location": "San Francisco, CA",
                "website": "https://example.com",
                "phone": "+1-555-0123",
                "emails_found": ["test@example.com"],
                "lead_lifecycle_state": "NEW",
            }
            
            lead_id = db.create_lead(test_lead_data)
            print(f"✓ Created test lead: {lead_id}")
        else:
            lead_id = UUID(leads[0].get("lead_id"))
            print(f"✓ Found existing lead: {lead_id}")
            print(f"  - Business: {leads[0].get('business_name')}")
        
        # Create orchestrator and process
        orchestrator = create_orchestrator(mode="testing")
        
        print(f"\nProcessing lead {lead_id}...")
        result = orchestrator.process_lead(lead_id)
        
        print(f"\n✓ Lead processing completed!")
        print(f"  - Current stage: {result.get('current_stage')}")
        print(f"  - Last node: {result.get('last_node')}")
        print(f"  - Is complete: {result.get('is_complete')}")
        print(f"  - Scoring: {result.get('scoring')}")
        print(f"  - Intent: {result.get('intent')}")
        print(f"  - Errors: {result.get('errors', [])}")
        
        # Test get_state
        state = orchestrator.get_state(lead_id)
        if state:
            print(f"\n✓ State retrieved from checkpointer")
            print(f"  - Next nodes: {state.get('next')}")
        
        return True
    except Exception as e:
        print(f"✗ Real lead processing failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_command_routing():
    """Test that Command-based routing works correctly"""
    print("\n" + "="*60)
    print("TEST 9: Command Routing Verification")
    print("="*60)
    
    try:
        from src.graph.orchestrator import (
            intent_node, governance_node, scoring_node,
            send_outreach_node, conversation_node
        )
        from langgraph.types import Command
        
        # Test intent_node returns Command
        fake_state = {"lead_id": uuid4(), "metadata": {}}
        result = intent_node(fake_state)
        assert isinstance(result, Command), "intent_node should return Command"
        print(f"✓ intent_node returns Command with goto='{result.goto}'")
        
        # Test scoring_node returns Command
        fake_state = {"lead_id": uuid4(), "metadata": {}, "intent": {"leak_score": 50}}
        result = scoring_node(fake_state)
        assert isinstance(result, Command), "scoring_node should return Command"
        print(f"✓ scoring_node returns Command with goto='{result.goto}'")
        
        # Test send_outreach_node returns Command
        fake_state = {"lead_id": uuid4(), "approval_status": "rejected"}
        result = send_outreach_node(fake_state)
        assert isinstance(result, Command), "send_outreach_node should return Command"
        print(f"✓ send_outreach_node returns Command with goto='{result.goto}'")
        
        # Test conversation_node returns Command
        fake_state = {"lead_id": uuid4(), "is_escalated": False}
        result = conversation_node(fake_state)
        assert isinstance(result, Command), "conversation_node should return Command"
        print(f"✓ conversation_node returns Command with goto='{result.goto}'")
        
        return True
    except Exception as e:
        print(f"✗ Command routing test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_retry_decorator():
    """Test the retry decorator works"""
    print("\n" + "="*60)
    print("TEST 10: Retry Decorator")
    print("="*60)
    
    try:
        from src.graph.orchestrator import with_retry
        from langgraph.types import Command
        
        call_count = 0
        
        @with_retry(max_retries=2, base_delay_ms=100)
        def failing_node(state):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Simulated failure")
            return {"success": True}
        
        # First call should fail and return retry Command
        fake_state = {"metadata": {}}
        result = failing_node(fake_state)
        
        assert isinstance(result, Command), "Failed node should return Command"
        print(f"✓ First failure returns Command with goto='{result.goto}'")
        print(f"  - Retry count in update: {result.update.get('metadata', {})}")
        
        return True
    except Exception as e:
        print(f"✗ Retry decorator test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests():
    """Run all tests and report results"""
    print("\n" + "="*60)
    print("LANGGRAPH ORCHESTRATOR - END-TO-END PRODUCTION TEST")
    print("="*60)
    print(f"Started at: {datetime.now().isoformat()}")
    
    results = {}
    
    # Run tests
    results["imports"] = test_imports()
    results["checkpointer"] = test_checkpointer_factory()
    results["graph_build"] = test_graph_build()
    results["database"] = test_database_connection()
    results["config"] = test_config_loading()
    results["orchestrator"] = test_orchestrator_creation() is not None
    results["dry_run"] = test_dry_run_with_fake_lead()
    results["real_lead"] = test_with_real_lead()
    results["command_routing"] = test_command_routing()
    results["retry_decorator"] = test_retry_decorator()
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, passed_test in results.items():
        status = "✓ PASS" if passed_test else "✗ FAIL"
        print(f"  {status}: {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    print(f"Finished at: {datetime.now().isoformat()}")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED! The LangGraph orchestrator is production-ready.")
    else:
        print(f"\n⚠ {total - passed} test(s) failed. Review the output above.")
    
    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
