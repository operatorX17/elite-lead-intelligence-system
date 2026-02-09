"""
LangGraph Orchestrator for ZRAI Lead OS.
Requirements: 1 (Graph-Based Orchestration Runtime)
"""

from typing import Dict, Any, Optional, Literal
from datetime import datetime
from uuid import UUID
import logging

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.base import BaseCheckpointSaver

from src.graph.state import LeadGraphState
from src.graph.checkpointer import SupabaseCheckpointer
from src.agents import (
    discovery_node,
    enrichment_node,
    intent_node,
    audit_node,
    scoring_node,
    outreach_node,
    conversation_node,
    governance_node,
    eval_node,
)
from src.config import load_config
from src.db.client import get_supabase_client


logger = logging.getLogger(__name__)


def should_skip_audit(state: LeadGraphState) -> Literal["audit", "scoring"]:
    """
    Conditional routing: skip audit if circuit breaker open or budget exceeded.
    Requirements: 1.4
    """
    if state.should_skip_audit:
        logger.info(f"Skipping audit for lead {state.lead_id}")
        return "scoring"
    
    # Check circuit breaker
    db = get_supabase_client()
    cb = db.get_circuit_breaker("audit")
    if cb and cb.get("state") == "OPEN":
        logger.warning("Audit circuit breaker is OPEN, skipping audit")
        return "scoring"
    
    # Check budget
    config = load_config()
    today = datetime.utcnow()
    metrics = db.get_or_create_usage_metrics(today)
    
    if metrics.get("browser_sessions_used", 0) >= config.budget.daily_browser_session_limit:
        logger.warning("Browser session budget exceeded, skipping audit")
        return "scoring"
    
    return "audit"


def should_skip_outreach(state: LeadGraphState) -> Literal["outreach", "end"]:
    """
    Conditional routing: skip outreach if disqualified or DNC.
    Requirements: 7.6
    """
    if state.is_disqualified:
        logger.info(f"Lead {state.lead_id} is disqualified, skipping outreach")
        return "end"
    
    if state.should_skip_outreach:
        logger.info(f"Lead {state.lead_id} flagged to skip outreach")
        return "end"
    
    # Check scoring tier
    if state.scoring and state.scoring.lead_tier == "C":
        logger.info(f"Lead {state.lead_id} is tier C, skipping outreach")
        return "end"
    
    return "outreach"


def should_escalate(state: LeadGraphState) -> Literal["escalate", "end"]:
    """
    Conditional routing: escalate if qualified.
    Requirements: 10.1
    """
    if state.is_escalated:
        return "escalate"
    
    if state.conversation and state.conversation.escalated:
        return "escalate"
    
    return "end"


def escalate_node(state: LeadGraphState) -> LeadGraphState:
    """
    Escalation node - marks lead for human handoff.
    Requirements: 10.1-10.4
    """
    logger.info(f"Escalating lead {state.lead_id} to human")
    
    db = get_supabase_client()
    
    # Mark lead as human-owned
    db.update_lead(state.lead_id, {
        "lead_lifecycle_state": "QUALIFIED",
        "updated_at": datetime.utcnow().isoformat(),
    })
    
    # Create escalation record
    escalation_data = {
        "lead_id": str(state.lead_id),
        "conversation_id": str(state.conversation.conversation_id) if state.conversation else None,
        "transcript": state.conversation.transcript if state.conversation else [],
        "entities": state.conversation.entities.model_dump() if state.conversation else {},
        "objection_summary": state.conversation.objection_summary if state.conversation else None,
        "suggested_close_angle": state.conversation.suggested_close_angle if state.conversation else None,
        "proof_pack": state.proof.model_dump() if state.proof else None,
        "escalated_at": datetime.utcnow().isoformat(),
    }
    
    db.create_escalation(escalation_data)
    
    state.is_complete = True
    state.current_stage = "escalated"
    
    return state


def end_node(state: LeadGraphState) -> LeadGraphState:
    """
    End node - marks lead processing as complete.
    Requirements: 1.8
    """
    state.is_complete = True
    state.current_stage = "complete"
    return state


def build_lead_graph(checkpointer: Optional[BaseCheckpointSaver] = None) -> StateGraph:
    """
    Build the main lead processing graph.
    Requirements: 1.1, 4
    """
    # Create graph with state schema
    graph = StateGraph(LeadGraphState)
    
    # Add nodes
    graph.add_node("discovery", discovery_node)
    graph.add_node("enrichment", enrichment_node)
    graph.add_node("intent", intent_node)
    graph.add_node("governance", governance_node)
    graph.add_node("audit", audit_node)
    graph.add_node("scoring", scoring_node)
    graph.add_node("outreach", outreach_node)
    graph.add_node("conversation", conversation_node)
    graph.add_node("eval", eval_node)
    graph.add_node("escalate", escalate_node)
    graph.add_node("end", end_node)
    
    # Define edges
    graph.set_entry_point("discovery")
    
    # Discovery -> Enrichment
    graph.add_edge("discovery", "enrichment")
    
    # Enrichment -> Intent
    graph.add_edge("enrichment", "intent")
    
    # Intent -> Governance (check DNC, rate limits)
    graph.add_edge("intent", "governance")
    
    # Governance -> Conditional (audit or scoring)
    graph.add_conditional_edges(
        "governance",
        should_skip_audit,
        {
            "audit": "audit",
            "scoring": "scoring",
        }
    )
    
    # Audit -> Scoring
    graph.add_edge("audit", "scoring")
    
    # Scoring -> Conditional (outreach or end)
    graph.add_conditional_edges(
        "scoring",
        should_skip_outreach,
        {
            "outreach": "outreach",
            "end": "end",
        }
    )
    
    # Outreach -> Eval (for A/B assignment)
    graph.add_edge("outreach", "eval")
    
    # Eval -> Conversation
    graph.add_edge("eval", "conversation")
    
    # Conversation -> Conditional (escalate or end)
    graph.add_conditional_edges(
        "conversation",
        should_escalate,
        {
            "escalate": "escalate",
            "end": "end",
        }
    )
    
    # Escalate -> End
    graph.add_edge("escalate", "end")
    
    # End -> END
    graph.add_edge("end", END)
    
    # Compile with checkpointer
    return graph.compile(checkpointer=checkpointer)


class LeadOrchestrator:
    """
    Main orchestrator for lead processing.
    Requirements: 1
    """
    
    def __init__(self):
        self._config = load_config()
        self._db = get_supabase_client()
        self._checkpointer = SupabaseCheckpointer()
        self._graph = build_lead_graph(self._checkpointer)
        self._logger = logging.getLogger("zrai.orchestrator")
    
    def process_lead(
        self,
        lead_id: UUID,
        config_override: Optional[Dict[str, Any]] = None,
    ) -> LeadGraphState:
        """
        Process a single lead through the graph.
        Requirements: 1.2
        """
        self._logger.info(f"Processing lead {lead_id}")
        
        # Check kill switch
        if self._config.kill_switches.global_kill:
            self._logger.warning("Global kill switch is active")
            raise RuntimeError("Global kill switch is active")
        
        # Initialize state
        initial_state = LeadGraphState(
            lead_id=lead_id,
            current_stage="discovery",
            last_node="start",
        )
        
        # Apply config overrides
        if config_override:
            initial_state.metadata["config_override"] = config_override
        
        # Run graph
        config = {"configurable": {"thread_id": str(lead_id)}}
        
        try:
            result = self._graph.invoke(initial_state, config)
            self._logger.info(f"Lead {lead_id} processing complete")
            return result
        except Exception as e:
            self._logger.error(f"Error processing lead {lead_id}: {e}")
            raise
    
    def resume_lead(self, lead_id: UUID) -> LeadGraphState:
        """
        Resume processing a lead from last checkpoint.
        Requirements: 2.3
        """
        self._logger.info(f"Resuming lead {lead_id}")
        
        config = {"configurable": {"thread_id": str(lead_id)}}
        
        # Get last state from checkpointer
        checkpoint = self._checkpointer.get(config)
        
        if not checkpoint:
            self._logger.warning(f"No checkpoint found for lead {lead_id}")
            return self.process_lead(lead_id)
        
        # Resume from checkpoint
        result = self._graph.invoke(None, config)
        return result
    
    def replay_lead(
        self,
        lead_id: UUID,
        run_id: str,
    ) -> LeadGraphState:
        """
        Replay a historical lead execution.
        Requirements: 2.2
        """
        self._logger.info(f"Replaying lead {lead_id} from run {run_id}")
        
        # Get historical state
        historical_state = self._db.get_historical_state(lead_id, run_id)
        
        if not historical_state:
            raise ValueError(f"No historical state found for lead {lead_id} run {run_id}")
        
        # Create state from historical data
        initial_state = LeadGraphState(
            lead_id=lead_id,
            lead=historical_state.get("lead"),
            current_stage="discovery",
            last_node="start",
            metadata={"replay_run_id": run_id},
        )
        
        # Run with new thread ID for replay
        replay_thread_id = f"{lead_id}_replay_{run_id}"
        config = {"configurable": {"thread_id": replay_thread_id}}
        
        result = self._graph.invoke(initial_state, config)
        return result
    
    def dry_run(
        self,
        lead_id: UUID,
    ) -> LeadGraphState:
        """
        Dry run - simulate without external writes.
        Requirements: 2.4
        """
        self._logger.info(f"Dry run for lead {lead_id}")
        
        # Set dry run flag in state
        initial_state = LeadGraphState(
            lead_id=lead_id,
            current_stage="discovery",
            last_node="start",
            metadata={"dry_run": True},
        )
        
        # Use separate thread for dry run
        config = {"configurable": {"thread_id": f"{lead_id}_dry_run"}}
        
        result = self._graph.invoke(initial_state, config)
        return result


def create_orchestrator() -> LeadOrchestrator:
    """Factory function to create orchestrator."""
    return LeadOrchestrator()
