"""
GOLDMINE STATE - The brain of the autonomous sales machine.

Uses LangGraph's TypedDict state with Annotated reducers for:
- Parallel task aggregation
- Message history management
- Evidence accumulation
"""

from typing import TypedDict, Annotated, Optional, List, Dict, Any, Union
from datetime import datetime
from enum import Enum
import operator


class ProspectTier(str, Enum):
    """Prospect qualification tier."""
    GOLDMINE = "goldmine"      # Score 80+, immediate pitch
    HOT = "hot"                # Score 60-79, warm outreach
    WARM = "warm"              # Score 40-59, nurture sequence
    COLD = "cold"              # Score < 40, skip or long-term nurture


class OutreachChannel(str, Enum):
    """Outreach channels."""
    EMAIL = "email"
    LINKEDIN = "linkedin"
    PHONE = "phone"
    SMS = "sms"
    VIDEO = "video"


class MysteryShopResult(TypedDict):
    """Result from mystery shopping a business."""
    lead_id: str
    business_name: str
    
    # Contact form test
    form_submitted: bool
    form_submission_time: Optional[datetime]
    form_response_time_hours: Optional[float]
    form_response_received: bool
    form_response_quality: Optional[str]  # "excellent", "good", "poor", "none"
    
    # Phone test
    phone_called: bool
    phone_call_time: Optional[datetime]
    phone_answered: bool
    phone_voicemail_left: bool
    phone_callback_received: bool
    phone_callback_time_hours: Optional[float]
    
    # After-hours test
    after_hours_tested: bool
    after_hours_response: Optional[str]
    
    # Evidence
    screenshots: List[bytes]
    recordings: List[str]  # URLs to call recordings
    
    # Calculated
    response_score: int  # 0-100
    money_leak_detected: bool


class CompetitorAnalysis(TypedDict):
    """Competitor comparison data."""
    competitor_name: str
    competitor_url: str
    has_online_booking: bool
    has_chat_widget: bool
    response_time_hours: Optional[float]
    google_rating: Optional[float]
    review_count: Optional[int]
    tech_stack: List[str]
    advantages: List[str]  # What they do better


class ReviewEvidence(TypedDict):
    """Evidence from review mining."""
    source: str  # "google", "yelp", "facebook"
    review_text: str
    rating: int
    date: str
    sentiment: str  # "negative_response", "slow_response", "positive"
    quote: str  # The damning quote


class ProofDeck(TypedDict):
    """Generated proof deck for a prospect."""
    lead_id: str
    business_name: str
    
    # The hook
    headline: str  # "You're losing $X,XXX/month"
    
    # Evidence sections
    mystery_shop_evidence: Dict[str, Any]
    competitor_comparison: List[CompetitorAnalysis]
    review_evidence: List[ReviewEvidence]
    
    # The numbers
    estimated_monthly_loss: float
    estimated_annual_loss: float
    loss_breakdown: Dict[str, float]  # {"missed_calls": 5000, "slow_response": 3000}
    
    # Screenshots
    their_website_screenshot: Optional[bytes]
    competitor_screenshot: Optional[bytes]
    
    # Generated assets
    pdf_url: Optional[str]
    video_url: Optional[str]  # Loom-style walkthrough
    
    # Metadata
    generated_at: datetime
    confidence_score: float


class OutreachMessage(TypedDict):
    """An outreach message in the sequence."""
    channel: OutreachChannel
    subject: Optional[str]
    body: str
    personalization_tokens: Dict[str, str]
    scheduled_at: Optional[datetime]
    sent_at: Optional[datetime]
    opened_at: Optional[datetime]
    replied_at: Optional[datetime]
    status: str  # "draft", "scheduled", "sent", "opened", "replied", "bounced"


def _last_value_reducer(existing: Any, new: Any) -> Any:
    """Reducer that keeps the last non-None value."""
    return new if new is not None else existing


def _stages_reducer(existing: List[str], new: str) -> List[str]:
    """Reducer that accumulates stages into a list."""
    if existing is None:
        existing = []
    if isinstance(new, str):
        return existing + [new]
    elif isinstance(new, list):
        return existing + new
    return existing


class GoldmineState(TypedDict):
    """
    The master state for the Goldmine autonomous sales machine.
    
    Uses Annotated types with reducers for parallel task aggregation.
    """
    # Identity
    lead_id: str
    thread_id: str
    
    # Lead data (from discovery)
    lead: Dict[str, Any]
    enrichment: Dict[str, Any]
    
    # Mystery shopping results (parallel aggregation)
    mystery_shop_results: Annotated[List[MysteryShopResult], operator.add]
    
    # Competitor analysis (parallel aggregation)
    competitor_analyses: Annotated[List[CompetitorAnalysis], operator.add]
    
    # Review evidence (parallel aggregation)
    review_evidence: Annotated[List[ReviewEvidence], operator.add]
    
    # Calculated scores
    response_score: int  # 0-100, how fast they respond
    leak_score: int      # 0-100, how much money they're losing
    competitor_gap: int  # 0-100, how far behind competitors
    goldmine_score: int  # 0-100, overall opportunity score
    
    # Revenue calculations
    estimated_monthly_loss: float
    estimated_annual_loss: float
    loss_breakdown: Dict[str, float]
    
    # Proof deck
    proof_deck: Optional[ProofDeck]
    
    # Outreach
    outreach_sequence: List[OutreachMessage]
    current_outreach_step: int
    outreach_status: str  # "not_started", "in_progress", "responded", "meeting_booked", "closed"
    
    # Meeting/Deal
    meeting_booked: bool
    meeting_time: Optional[datetime]
    deal_value: Optional[float]
    deal_status: str  # "prospect", "qualified", "proposal", "negotiation", "closed_won", "closed_lost"
    
    # Workflow control - use list reducer for parallel updates
    completed_stages: Annotated[List[str], operator.add]
    errors: Annotated[List[str], operator.add]
    
    # Human-in-the-loop
    requires_approval: bool
    approval_reason: Optional[str]
    human_feedback: Optional[str]
    
    # Metadata
    created_at: datetime
    updated_at: datetime
    
    # Messages for LLM context
    messages: Annotated[List[Dict[str, Any]], operator.add]


def create_initial_state(lead: Dict[str, Any], enrichment: Dict[str, Any] = None) -> GoldmineState:
    """Create initial state for a new goldmine prospect."""
    from uuid import uuid4
    
    return GoldmineState(
        lead_id=str(lead.get("lead_id", uuid4())),
        thread_id=f"goldmine-{uuid4()}",
        lead=lead,
        enrichment=enrichment or {},
        mystery_shop_results=[],
        competitor_analyses=[],
        review_evidence=[],
        response_score=0,
        leak_score=0,
        competitor_gap=0,
        goldmine_score=0,
        estimated_monthly_loss=0.0,
        estimated_annual_loss=0.0,
        loss_breakdown={},
        proof_deck=None,
        outreach_sequence=[],
        current_outreach_step=0,
        outreach_status="not_started",
        meeting_booked=False,
        meeting_time=None,
        deal_value=None,
        deal_status="prospect",
        completed_stages=["discovery"],
        errors=[],
        requires_approval=False,
        approval_reason=None,
        human_feedback=None,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        messages=[],
    )
