"""
Database models matching the design document schemas.
Requirements: 3.8, 5.1-5.6, 6.7, 7.5, 9.3, 13.1, 14.2, 16.2, 18.2, 20.2, 21.1-21.9, 22.4
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field
from uuid import UUID, uuid4


class CTAType(str, Enum):
    """CTA types detected on landing pages."""
    CALL = "CALL"
    FORM = "FORM"
    BOOK = "BOOK"
    OTHER = "OTHER"


class LeadLifecycleState(str, Enum):
    """Lead lifecycle states.
    Requirements: 21.1, 21.3, 21.4, 21.7, 21.8, 21.9
    """
    NEW = "NEW"
    STALE = "STALE"
    REACTIVATABLE = "REACTIVATABLE"
    ENGAGED = "ENGAGED"
    QUALIFIED = "QUALIFIED"
    CLOSED_WON = "CLOSED_WON"
    CLOSED_LOST = "CLOSED_LOST"


class SpeedToLeadRisk(str, Enum):
    """Speed-to-lead risk classification.
    Requirements: 5.5
    """
    LOW = "LOW"
    MED = "MED"
    HIGH = "HIGH"


class LeadTier(str, Enum):
    """Lead tier classification.
    Requirements: 7.5
    """
    A = "A"  # Pitch now
    B = "B"  # Soft pitch
    C = "C"  # Skip


class OutreachChannel(str, Enum):
    """Outreach channels."""
    EMAIL = "email"
    DM = "dm"
    FORM = "form"


class OutreachVariant(str, Enum):
    """A/B test variants."""
    A = "A"
    B = "B"


class OutreachStatus(str, Enum):
    """Outreach message status."""
    PENDING = "pending"
    APPROVED = "approved"
    SENT = "sent"
    REJECTED = "rejected"


class NegativeSignalType(str, Enum):
    """Types of negative signals.
    Requirements: 22.4
    """
    OPT_OUT = "opt_out"
    ANGRY_REPLY = "angry_reply"
    BOUNCE = "bounce"
    SPAM_COMPLAINT = "spam_complaint"


class CircuitBreakerState(str, Enum):
    """Circuit breaker states.
    Requirements: 1.4, 20.2
    """
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class Lead(BaseModel):
    """Canonical lead record.
    Requirements: 3.7, 3.8, 18.2
    """
    lead_id: UUID = Field(default_factory=uuid4)
    business_name: str
    category: Optional[str] = None
    location: Optional[str] = None
    geo_tags: List[str] = Field(default_factory=list)
    website: Optional[str] = None
    landing_page_url: Optional[str] = None
    phone: Optional[str] = None
    emails_found: List[str] = Field(default_factory=list)
    facebook_page: Optional[str] = None
    instagram: Optional[str] = None
    ads_active: bool = False
    ad_start_date: Optional[datetime] = None
    ad_last_seen: Optional[datetime] = None
    cta_type: Optional[CTAType] = None
    lead_form_detected: bool = False
    lead_lifecycle_state: LeadLifecycleState = LeadLifecycleState.NEW
    last_contacted_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        use_enum_values = True


class LeadState(BaseModel):
    """LangGraph checkpointer state.
    Requirements: 1.2, 18.2
    """
    lead_id: UUID
    current_stage: str
    last_node: str
    last_error: Optional[str] = None
    retry_count: int = 0
    next_run_at: Optional[datetime] = None
    locks: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class EnrichmentData(BaseModel):
    """Contact and context enrichment data.
    Requirements: 4.1-4.6
    """
    lead_id: UUID
    enrichment_confidence: float = Field(ge=0, le=1)
    booking_provider: Optional[str] = None
    crm_hint: Optional[str] = None
    chat_widget: Optional[str] = None
    form_tool: Optional[str] = None
    decision_maker_name: Optional[str] = None
    decision_maker_linkedin: Optional[str] = None
    contact_quality_score: int = Field(ge=0, le=100)
    normalized_phone: Optional[str] = None
    validated_emails: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ReviewEvidence(BaseModel):
    """Review evidence snippet."""
    snippet: str
    source_url: str
    sentiment: str = "negative"


class IntentData(BaseModel):
    """Intent and revenue leak scores.
    Requirements: 5.1-5.6
    """
    lead_id: UUID
    intent_score: int = Field(ge=0, le=100)
    leak_score: int = Field(ge=0, le=100)
    reactivation_fit: int = Field(ge=0, le=100)
    why_this_lead: str
    speed_to_lead_risk: SpeedToLeadRisk
    review_evidence: List[ReviewEvidence] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        use_enum_values = True


class AuditBullet(BaseModel):
    """Proof pack audit bullet."""
    type: str  # 'leak', 'fix', 'upside'
    evidence: Optional[str] = None
    specific: Optional[str] = None
    estimate: Optional[str] = None


class ProofArtifact(BaseModel):
    """Proof artifacts from Steel.dev audit.
    Requirements: 6.5, 6.6, 6.7
    """
    lead_id: UUID
    hero_screenshot_url: Optional[str] = None
    cta_screenshot_url: Optional[str] = None
    audit_bullets: List[AuditBullet] = Field(default_factory=list)
    extraction_data: Dict[str, Any] = Field(default_factory=dict)
    generated_at: datetime = Field(default_factory=datetime.utcnow)


class ScoreBreakdown(BaseModel):
    """Score breakdown by component."""
    ad_activity: float = 0
    intent: float = 0
    leak: float = 0
    reactivation: float = 0
    contact_quality: float = 0
    business_size: float = 0


class ScoringResult(BaseModel):
    """Weighted scoring results.
    Requirements: 7.1-7.6
    """
    lead_id: UUID
    final_score: int = Field(ge=0, le=100)
    score_breakdown: ScoreBreakdown
    lead_tier: LeadTier
    do_not_contact: bool = False
    do_not_contact_reason: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        use_enum_values = True


class Personalization(BaseModel):
    """Outreach personalization data."""
    decision_maker_name: Optional[str] = None
    business_name: str
    category: Optional[str] = None
    evidence: Optional[str] = None


class OutreachQueue(BaseModel):
    """Outreach message queue.
    Requirements: 8.1-8.8
    """
    outreach_id: UUID = Field(default_factory=uuid4)
    lead_id: UUID
    channel: OutreachChannel
    variant: OutreachVariant
    subject: Optional[str] = None
    body: str
    attachments: List[str] = Field(default_factory=list)
    personalization: Personalization
    status: OutreachStatus = OutreachStatus.PENDING
    requires_approval: bool = True
    sent_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        use_enum_values = True


class ConversationMessage(BaseModel):
    """Single conversation message."""
    role: str  # 'ai' or 'prospect'
    message: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ConversationEntities(BaseModel):
    """Extracted conversation entities.
    Requirements: 9.4
    """
    budget_range: Optional[Dict[str, int]] = None  # {'min': x, 'max': y}
    role: Optional[str] = None
    timeline: Optional[str] = None
    objections: List[str] = Field(default_factory=list)
    pain_confirmed: bool = False
    interest_level: str = "medium"  # 'high', 'medium', 'low'


class Conversation(BaseModel):
    """Conversation record.
    Requirements: 9.1-9.7
    """
    conversation_id: UUID = Field(default_factory=uuid4)
    lead_id: UUID
    transcript: List[ConversationMessage] = Field(default_factory=list)
    entities: ConversationEntities = Field(default_factory=ConversationEntities)
    objection_summary: Optional[str] = None
    suggested_close_angle: Optional[str] = None
    escalated: bool = False
    escalated_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class NegativeSignal(BaseModel):
    """Negative signal record.
    Requirements: 22.3, 22.4, 22.7, 22.8
    """
    signal_id: UUID = Field(default_factory=uuid4)
    lead_id: UUID
    signal_type: NegativeSignalType
    channel: Optional[str] = None
    sentiment_score: Optional[float] = Field(default=None, ge=-1, le=1)
    message_content: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        use_enum_values = True


class DoNotContact(BaseModel):
    """Do not contact list entry.
    Requirements: 22.2, 22.9
    """
    lead_id: UUID
    reason: str
    added_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None


class AuditLog(BaseModel):
    """Audit log entry.
    Requirements: 13.1, 13.2
    """
    log_id: UUID = Field(default_factory=uuid4)
    actor: str
    action: str
    resource: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    payload_hash: Optional[str] = None
    idempotency_key: Optional[str] = None
    result: str  # 'success' or 'failure'
    error_message: Optional[str] = None


class UsageMetrics(BaseModel):
    """Daily usage metrics.
    Requirements: 14.2, 23.2-23.9
    """
    metric_date: datetime
    llm_tokens_used: int = 0
    browser_sessions_used: int = 0
    scraper_runs_used: int = 0
    llm_cost_usd: float = 0.0
    browser_cost_usd: float = 0.0
    scraper_cost_usd: float = 0.0
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Playbook(BaseModel):
    """Playbook knowledge artifact.
    Requirements: 16.1-16.3
    """
    playbook_id: UUID = Field(default_factory=uuid4)
    name: str
    version: int = 1
    niche: Optional[str] = None
    tier: Optional[str] = None
    channel: Optional[str] = None
    content_type: str  # 'outreach_example', 'objection_handling', 'compliance_rule', 'niche_note'
    content: str
    embedding: Optional[List[float]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class CircuitBreaker(BaseModel):
    """Circuit breaker state.
    Requirements: 1.4, 20.2
    """
    node_name: str
    failure_count: int = 0
    failure_threshold: int = 5
    timeout_seconds: int = 300
    state: CircuitBreakerState = CircuitBreakerState.CLOSED
    last_failure_at: Optional[datetime] = None
    last_success_at: Optional[datetime] = None
    
    class Config:
        use_enum_values = True
