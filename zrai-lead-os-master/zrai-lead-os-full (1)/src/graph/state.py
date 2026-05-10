"""
LangGraph state definitions for ZRAI Lead OS.
Requirements: 1.2, 4.1
"""

from typing import Optional, List, Dict, Any, Annotated
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field
from langgraph.graph import add_messages

from src.db.models import (
    Lead,
    EnrichmentData,
    IntentData,
    ProofArtifact,
    ScoringResult,
    OutreachQueue,
    Conversation,
    LeadTier,
    LeadLifecycleState,
)


class LeadGraphState(BaseModel):
    """
    Main state object for lead processing graph.
    Requirements: 1.2
    
    This state flows through all nodes in the graph and accumulates
    data as the lead progresses through the pipeline.
    """
    
    # Core lead data
    lead_id: UUID
    lead: Optional[Lead] = None
    
    # Stage tracking
    current_stage: str = "discovery"
    last_node: str = "start"
    
    # Enrichment data
    enrichment: Optional[EnrichmentData] = None
    
    # Intent and scoring
    intent: Optional[IntentData] = None
    scoring: Optional[ScoringResult] = None
    
    # Proof artifacts
    proof: Optional[ProofArtifact] = None
    
    # Outreach
    outreach_messages: List[OutreachQueue] = Field(default_factory=list)
    
    # Conversation
    conversation: Optional[Conversation] = None
    
    # Processing metadata
    retry_count: int = 0
    last_error: Optional[str] = None
    next_run_at: Optional[datetime] = None
    
    # Flags
    should_skip_audit: bool = False
    should_skip_outreach: bool = False
    is_disqualified: bool = False
    is_escalated: bool = False
    is_complete: bool = False
    
    # Messages for LangGraph (if using message-based nodes)
    messages: Annotated[List[Dict[str, Any]], add_messages] = Field(default_factory=list)
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        arbitrary_types_allowed = True


class DiscoveryState(BaseModel):
    """State for discovery node."""
    niche_keywords: List[str] = Field(default_factory=list)
    geo_filters: List[str] = Field(default_factory=list)
    platform_toggles: Dict[str, bool] = Field(default_factory=lambda: {
        "meta_ads": True,
        "google_maps": True,
        "websites": True,
        "social": True,
    })
    raw_leads: List[Dict[str, Any]] = Field(default_factory=list)
    processed_count: int = 0
    error_count: int = 0


class EnrichmentState(BaseModel):
    """State for enrichment node."""
    lead_id: UUID
    tech_signals: Dict[str, Any] = Field(default_factory=dict)
    contacts: List[Dict[str, Any]] = Field(default_factory=list)
    decision_makers: List[Dict[str, Any]] = Field(default_factory=list)


class AuditState(BaseModel):
    """State for audit node (Steel.dev)."""
    lead_id: UUID
    landing_page_url: str
    screenshots: List[str] = Field(default_factory=list)
    extraction_data: Dict[str, Any] = Field(default_factory=dict)
    audit_bullets: List[Dict[str, str]] = Field(default_factory=list)


class OutreachState(BaseModel):
    """State for outreach generation node."""
    lead_id: UUID
    tier: LeadTier
    proof_pack: Optional[ProofArtifact] = None
    generated_messages: List[OutreachQueue] = Field(default_factory=list)
    
    class Config:
        use_enum_values = True


class ConversationState(BaseModel):
    """State for conversation node."""
    lead_id: UUID
    conversation_id: Optional[UUID] = None
    transcript: List[Dict[str, Any]] = Field(default_factory=list)
    entities: Dict[str, Any] = Field(default_factory=dict)
    is_qualified: bool = False
    should_escalate: bool = False
