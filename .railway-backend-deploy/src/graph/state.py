"""
LangGraph state definitions for ZRAI Lead OS.
Requirements: 1.2, 4.1

Uses TypedDict with Annotated reducers for proper state management.
"""

from typing import Optional, List, Dict, Any, Annotated, Union
from typing_extensions import TypedDict
from datetime import datetime
from uuid import UUID
from operator import add
from langgraph.graph.message import add_messages


def merge_dict(left: Union[Dict, None], right: Union[Dict, None]) -> Dict:
    """
    Reducer for merging dictionaries.
    Combines keys from both dicts, with right taking precedence.
    """
    if left is None:
        left = {}
    if right is None:
        right = {}
    return {**left, **right}


class LeadGraphState(TypedDict, total=False):
    """
    Main state object for lead processing graph.
    
    Uses TypedDict pattern with Annotated reducers:
    - operator.add: Concatenates lists
    - merge_dict: Merges dictionaries
    - No annotation: Overwrites value
    
    This is a TypedDict for LangGraph compatibility.
    """
    # Core identifiers (no reducer - overwrites)
    lead_id: UUID
    thread_id: str
    
    # Lead data (loaded from DB, no reducer)
    lead: Optional[Dict[str, Any]]
    
    # Stage tracking (no reducer - overwrites)
    current_stage: str
    last_node: str
    
    # Accumulated data from agents (merge_dict reducer)
    enrichment: Annotated[Dict[str, Any], merge_dict]
    intent: Annotated[Dict[str, Any], merge_dict]
    scoring: Annotated[Dict[str, Any], merge_dict]
    proof: Annotated[Dict[str, Any], merge_dict]
    
    # Outreach messages (operator.add reducer - appends)
    outreach_messages: Annotated[List[Dict], add]
    
    # Conversation (accumulative)
    conversation_transcript: Annotated[List[Dict], add]
    conversation_entities: Annotated[Dict[str, Any], merge_dict]
    
    # Error tracking (accumulative)
    errors: Annotated[List[Dict], add]
    retry_count: int  # No reducer - managed explicitly
    
    # Flags (no reducer - overwrites)
    should_skip_audit: bool
    should_skip_outreach: bool
    is_disqualified: bool
    is_escalated: bool
    is_complete: bool
    requires_approval: bool
    
    # Human-in-the-loop (no reducer)
    approval_status: Optional[str]  # 'pending', 'approved', 'rejected'
    approval_notes: Optional[str]
    
    # Metadata (merge_dict reducer)
    metadata: Annotated[Dict[str, Any], merge_dict]
    
    # Messages for debugging/logging (add_messages reducer)
    messages: Annotated[List[Dict], add_messages]
    
    # Error tracking
    last_error: Optional[str]


class LeadGraphStateDict(TypedDict, total=False):
    """
    TypedDict version of LeadGraphState for type checking.
    Use this for function signatures and type hints.
    """
    lead_id: UUID
    thread_id: str
    lead: Optional[Dict[str, Any]]
    current_stage: str
    last_node: str
    enrichment: Dict[str, Any]
    intent: Dict[str, Any]
    scoring: Dict[str, Any]
    proof: Dict[str, Any]
    outreach_messages: List[Dict]
    conversation_transcript: List[Dict]
    conversation_entities: Dict[str, Any]
    errors: List[Dict]
    retry_count: int
    should_skip_audit: bool
    should_skip_outreach: bool
    is_disqualified: bool
    is_escalated: bool
    is_complete: bool
    requires_approval: bool
    approval_status: Optional[str]
    approval_notes: Optional[str]
    metadata: Dict[str, Any]
    messages: List[Dict]


# For backward compatibility with existing code
class DiscoveryState(TypedDict, total=False):
    """State for discovery node."""
    niche_keywords: List[str]
    geo_filters: List[str]
    platform_toggles: Dict[str, bool]
    raw_leads: List[Dict[str, Any]]
    processed_count: int
    error_count: int


class EnrichmentState(TypedDict, total=False):
    """State for enrichment node."""
    lead_id: UUID
    tech_signals: Dict[str, Any]
    contacts: List[Dict[str, Any]]
    decision_makers: List[Dict[str, Any]]


class AuditState(TypedDict, total=False):
    """State for audit node (Steel.dev)."""
    lead_id: UUID
    landing_page_url: str
    screenshots: List[str]
    extraction_data: Dict[str, Any]
    audit_bullets: List[Dict[str, str]]


class OutreachState(TypedDict, total=False):
    """State for outreach generation node."""
    lead_id: UUID
    tier: str
    proof_pack: Optional[Dict[str, Any]]
    generated_messages: List[Dict]


class ConversationState(TypedDict, total=False):
    """State for conversation node."""
    lead_id: UUID
    conversation_id: Optional[UUID]
    transcript: List[Dict[str, Any]]
    entities: Dict[str, Any]
    is_qualified: bool
    should_escalate: bool
