"""
ZRAI Lead OS - FastAPI Server

Exposes the LangGraph pipeline via REST API for the frontend.
"""

import os
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from typing import Optional, List, Dict, Any, Callable
from contextlib import asynccontextmanager
from uuid import uuid4, UUID
from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs, unquote
import re
from functools import lru_cache
from difflib import SequenceMatcher

import requests
from bs4 import BeautifulSoup

from fastapi import FastAPI, HTTPException, Header, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.db.models import (
    Conversation,
    ConversationMessage,
    Lead,
    LeadLifecycleState,
)
from src.agents.contact_intelligence import build_contact_intelligence
from src.agents.sales_playbook import (
    build_sales_fallback_response,
    classify_sales_signals,
    infer_sales_stage,
    normalize_channel,
)
from src.graph.state import LeadGraphState

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

FAST_ANALYZE_AGENT_TIMEOUTS = {
    "enrichment": 45,
    "intent": 25,
    "audit": 30,
    "scoring": 20,
    "outreach": 30,
}

FULL_ANALYZE_AGENT_TIMEOUTS = {
    "enrichment": 120,
    "intent": 35,
    "audit": 45,
    "scoring": 25,
    "outreach": 30,
}

WHATSAPP_POLICY_LIMITS = {
    "per_user_hour": 3,
    "global_per_minute": 20,
    "freeform_window_ms": 24 * 60 * 60 * 1000,
    "duplicate_window_ms": 10 * 60 * 1000,
    "runtime_kill_switch_ms": 15 * 60 * 1000,
}

_whatsapp_policy_runtime_state = {
    "kill_switch_until": None,
    "last_reason": None,
}

WHATSAPP_AUTOMATION_DISCLOSURE_PATTERNS = [
    re.compile(r"\bzrai\b", re.IGNORECASE),
    re.compile(r"\bautomated\b", re.IGNORECASE),
    re.compile(r"\bassistant\b", re.IGNORECASE),
]

WHATSAPP_AUTOMATION_IMPERSONATION_PATTERNS = [
    re.compile(r"\breal operator\b", re.IGNORECASE),
    re.compile(r"\bhuman[- ]?sounding\b", re.IGNORECASE),
    re.compile(r"\bi(?:'m| am)\s+(?:the\s+)?(?:owner|founder|doctor|receptionist|front desk|staff)\b", re.IGNORECASE),
    re.compile(r"\bfrom (?:the )?(?:clinic|front desk|reception|doctor(?:'s)? office)\b", re.IGNORECASE),
]


def _build_cors_origins() -> List[str]:
    """Build the allowed CORS origin list for local + deployed frontends."""
    default_origins = {
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
        "https://zrai-lead-os.vercel.app",
    }

    for env_key in (
        "NEXTAUTH_URL",
        "APP_URL",
        "FRONTEND_URL",
        "VERCEL_URL",
    ):
        value = os.getenv(env_key, "").strip()
        if not value:
            continue

        if env_key == "VERCEL_URL" and not value.startswith("http"):
            value = f"https://{value}"

        default_origins.add(value.rstrip("/"))

    return sorted(default_origins)


def _build_cors_origin_regex() -> str:
    """Allow deployed frontend hosts without brittle per-deployment edits."""
    return (
        r"^https://([a-z0-9-]+\.)?vercel\.app$|"
        r"^https://[a-z0-9-]+-metasaiprakash-gmailcoms-projects\.vercel\.app$"
    )

BROKEN_PROXY_VALUE = "http://127.0.0.1:9"
BROKEN_PROXY_KEYS = [
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
]

COUNTRY_ALIASES = {
    "us": "United States",
    "usa": "United States",
    "uk": "United Kingdom",
    "gb": "United Kingdom",
    "in": "India",
    "india": "India",
    "ca": "Canada",
    "canada": "Canada",
    "au": "Australia",
    "australia": "Australia",
    "uae": "United Arab Emirates",
}

CITY_ALIASES = {
    "bangalore": ["bangalore", "bengaluru"],
    "bengaluru": ["bangalore", "bengaluru"],
}

BRANCH_LOCALITY_ALIASES = {
    "jp nagar": "JP Nagar",
    "j.p. nagar": "JP Nagar",
    "koramangala": "Koramangala",
    "jayanagar": "Jayanagar",
    "indiranagar": "Indiranagar",
    "whitefield": "Whitefield",
    "hsr layout": "HSR Layout",
    "hsr": "HSR Layout",
    "electronic city": "Electronic City",
    "sarjapur": "Sarjapur",
    "sarjapur road": "Sarjapur",
    "thanisandra": "Thanisandra",
    "thannisandra": "Thanisandra",
    "thanisandra main road": "Thanisandra",
    "chikkabellandur": "Chikkabellandur",
    "nagawara": "Nagawara",
    "nagwara": "Nagawara",
    "uttarahalli": "Uttarahalli",
    "bilekahalli": "Bilekahalli",
    "btm layout": "BTM Layout",
    "hebbal": "Hebbal",
    "rajajinagar": "Rajajinagar",
    "malleshwaram": "Malleshwaram",
    "marathahalli": "Marathahalli",
    "banashankari": "Banashankari",
    "basavanagudi": "Basavanagudi",
    "rt nagar": "RT Nagar",
    "yelahanka": "Yelahanka",
}

DISCOVERY_KEYWORD_VARIANTS = {
    "saas": ["saas company", "b2b saas", "saas platform", "cloud software"],
    "software": ["software company", "software services", "b2b software"],
    "agency": ["agency", "digital agency", "marketing agency"],
    "ecommerce": ["ecommerce company", "online store", "ecommerce services"],
    "fintech": ["fintech company", "financial software", "payments software"],
    "aesthetic clinic": [
        "skin clinic",
        "laser clinic",
        "cosmetic clinic",
        "hair clinic",
    ],
    "aesthetic clinics": [
        "skin clinic",
        "laser clinic",
        "cosmetic clinic",
        "hair clinic",
    ],
    "premium skin and aesthetic clinics": [
        "skin clinic",
        "aesthetic clinic",
        "dermatology clinic",
        "cosmetic clinic",
        "laser clinic",
        "medspa",
    ],
}

NICHE_RELEVANCE_HINTS = {
    "saas": {
        "include": ["saas", "b2b", "platform", "cloud", "crm", "erp", "automation"],
        "exclude": [
            "agency",
            "services",
            "consulting",
            "outsourcing",
            "marketing",
            "design",
            "it services",
            "custom software",
            "development company",
            "mobile app development",
            "web development",
        ],
    },
}

DISCOVERY_HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    )
}

OSINT_FIRST_NICHES = {"saas", "software", "fintech", "ecommerce"}
OSINT_BLOCKED_DOMAINS = {
    "duckduckgo.com",
    "linkedin.com",
    "in.linkedin.com",
    "www.linkedin.com",
    "facebook.com",
    "www.facebook.com",
    "instagram.com",
    "x.com",
    "twitter.com",
    "youtube.com",
    "medium.com",
    "clutch.co",
    "g2.com",
    "capterra.com",
    "apify.com",
}
OSINT_RESULT_BLOCKLIST = {
    "reddit.com",
    "www.reddit.com",
    "builtin.com",
    "www.builtin.com",
    "builtinbengaluru.in",
    "f6s.com",
    "www.f6s.com",
    "beststartup.in",
    "www.beststartup.in",
    "saastartups.pro",
    "www.saastartups.pro",
    "glassdoor.co.in",
    "www.glassdoor.co.in",
    "wikipedia.org",
    "en.wikipedia.org",
    "softwaresuggest.com",
    "www.softwaresuggest.com",
    "techjockey.com",
    "www.techjockey.com",
    "ambitionbox.com",
    "www.ambitionbox.com",
    "justdial.com",
    "www.justdial.com",
    "facebook.com",
    "www.facebook.com",
    "chrome.google.com",
    "pitchbook.com",
    "www.pitchbook.com",
}
OSINT_EXPANDABLE_SOURCE_DOMAINS = {
    "tracxn.com",
    "www.tracxn.com",
}
OSINT_LISTICLE_TERMS = {
    "top ",
    "best ",
    "examples",
    "companies in",
    "companies to know",
    "startups in",
    "seo companies",
    "directory",
    "list of",
    "community",
    "reddit",
    "vs ",
    "comparison",
}
BRAVE_SEARCH_API_URL = "https://api.search.brave.com/res/v1/web/search"
FIRECRAWL_SEARCH_API_URL = "https://api.firecrawl.dev/v1/search"
SIGNALS_VERSION = "clinic_intel_v1"


def clear_lead_analysis_cache_safe(db: Any, lead_id: UUID) -> None:
    """Clear persisted analysis artifacts without assuming a newer DB client interface.

    Production can momentarily serve a mixed build during rollout. Fall back to the
    raw Supabase tables and lead_state update if the wrapper method is unavailable.
    """
    clear_cache = getattr(db, "clear_lead_analysis_cache", None)
    if callable(clear_cache):
        clear_cache(lead_id)
        return

    client = getattr(db, "client", None)
    lead_id_str = str(lead_id)
    if client is not None:
        for table_name in ("enrichment_data", "intent_data", "proof_artifacts", "scoring_results"):
            try:
                client.table(table_name).delete().eq("lead_id", lead_id_str).execute()
            except Exception:
                logger.exception("Failed clearing %s for lead %s", table_name, lead_id_str)

    get_lead_state = getattr(db, "get_lead_state", None)
    save_lead_state = getattr(db, "save_lead_state", None)
    if not callable(get_lead_state) or not callable(save_lead_state):
        return

    lead_state = get_lead_state(lead_id) or {}
    if not lead_state:
        return

    metadata = dict(lead_state.get("metadata") or {})
    for key in [
        "analysis_state",
        "analysis_updated_at",
        "signals_version",
        "signal_facts",
        "analysis_bundle",
        "intelligence",
        "people_intelligence",
        "contact_intelligence",
        "site_truth_summary",
        "why_this_lead",
        "top_issue",
        "next_best_action",
        "refresh_requested_at",
    ]:
        metadata.pop(key, None)

    lead_state["metadata"] = metadata
    lead_state["updated_at"] = datetime.utcnow().isoformat()
    save_lead_state(lead_state)

# ============================================================================
# Request/Response Models
# ============================================================================

class DiscoverRequest(BaseModel):
    niche: str = Field(..., description="Industry niche to search")
    geo: str = Field(..., min_length=1, description="Geographic region")
    limit: int = Field(default=50, ge=1, le=200, description="Max leads to discover")
    mock: bool = Field(default=False, description="Use mock data for testing (fast)")

class LeadResponse(BaseModel):
    id: str
    company_name: str
    domain: Optional[str] = None
    niche: Optional[str] = None
    geo: Optional[str] = None
    status: str = "discovered"
    score: Optional[float] = None
    contacts: List[dict] = []
    intent_signals: List[dict] = []
    verified_fit: Optional[str] = None
    source: Optional[str] = None
    source_label: Optional[str] = None
    score_kind: Optional[str] = None
    preview_summary: Optional[str] = None
    contact_paths: List[str] = []
    preview_match_score: Optional[float] = None
    final_score: Optional[float] = None
    analysis_state: Optional[str] = None
    analysis_updated_at: Optional[str] = None
    signals_version: Optional[str] = None
    signal_facts: Optional[Dict[str, Any]] = None


class ProcessLeadsRequest(BaseModel):
    lead_ids: List[str] = Field(..., min_length=1, max_length=10)
    include_outreach: bool = True
    force_refresh: bool = True


class AnalyzeLeadRequest(BaseModel):
    lead_id: str = Field(..., description="Lead ID to analyze")
    include_outreach: bool = True
    force_refresh: bool = True

class DiscoverResponse(BaseModel):
    leads: List[LeadResponse]
    count: int
    run_id: str


def normalize_lead_id_value(lead_id: str | UUID) -> str:
    """Normalize lead IDs so API handlers always talk to the DB consistently."""
    if isinstance(lead_id, UUID):
        return str(lead_id)
    return str(UUID(str(lead_id)))

class EnrichRequest(BaseModel):
    lead_id: str

class IntentRequest(BaseModel):
    lead_id: str

class ProofRequest(BaseModel):
    lead_id: str
    proof_type: str = "screenshot"

class ScoreRequest(BaseModel):
    niche: Optional[str] = None
    geo: Optional[str] = None
    min_score: Optional[float] = None
    lead_ids: Optional[List[str]] = None

class OutreachRequest(BaseModel):
    lead_id: str
    channel: str = "email"
    action: str = "draft"
    message: Optional[str] = None

class ConversationRequest(BaseModel):
    lead_id: str
    message: str
    channel: Optional[str] = "email"


class ProspectConversationMessage(BaseModel):
    role: str = Field(..., pattern="^(prospect|ai|assistant|human)$")
    message: str = Field(..., min_length=1)


class ProspectConversationRequest(BaseModel):
    message: str = Field(..., min_length=1)
    channel: Optional[str] = "whatsapp"
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    business_phone: Optional[str] = None
    transcript: List[ProspectConversationMessage] = Field(default_factory=list, max_length=8)
    entities: Dict[str, Any] = Field(default_factory=dict)
    lead_context: Dict[str, Any] = Field(default_factory=dict)
    ops_state: Dict[str, Any] = Field(default_factory=dict)


class ResolveContactRequest(BaseModel):
    contact_phone: Optional[str] = None
    contact_name: Optional[str] = None
    max_candidates: int = Field(default=150, ge=10, le=500)


class ConversationSyncRequest(BaseModel):
    lead_id: str
    role: str = Field(..., pattern="^(human|prospect|ai)$")
    message: str = Field(..., min_length=1)
    channel: Optional[str] = "whatsapp"
    conversation_id: Optional[str] = None


class WhatsAppPolicyGuardRequest(BaseModel):
    conversation_id: Optional[str] = None
    contact_phone: Optional[str] = None
    business_phone: Optional[str] = None
    body: str
    message_style: str = Field(default="freeform", pattern="^(freeform|template)$")
    automation_kind: str = Field(default="manual", pattern="^(manual|bot_reply|campaign)$")

class RunPipelineRequest(BaseModel):
    mode: str = "full"
    config: Optional[dict] = None
    run_id: Optional[str] = None
    limit: Optional[int] = None

class ErrorResponse(BaseModel):
    success: bool = False
    error: dict

# ============================================================================
# Lifespan and App Setup
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize resources on startup, cleanup on shutdown."""
    logger.info("Starting ZRAI Lead OS API Server...")

    removed_proxy_keys = []
    for key in BROKEN_PROXY_KEYS:
        value = os.environ.get(key)
        if value and value.strip().lower() == BROKEN_PROXY_VALUE:
            os.environ.pop(key, None)
            removed_proxy_keys.append(key)

    if removed_proxy_keys:
        logger.warning(
            "Removed broken local proxy settings for backend process: %s",
            ", ".join(removed_proxy_keys),
        )
    
    # Keep startup lightweight so healthchecks do not depend on every external
    # service credential being present. Agents are initialized lazily.
    app.state.orchestrator = None
    app.state.discovery_agent = None
    app.state.enrichment_agent = None
    app.state.intent_agent = None
    app.state.audit_agent = None
    app.state.scoring_agent = None
    app.state.outreach_agent = None
    app.state.conversation_agent = None
    app.state.governance_agent = None

    try:
        from src.db.client import get_supabase_client
        app.state.db = get_supabase_client()
        logger.info("Database initialized; agents will be loaded lazily")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        import traceback
        traceback.print_exc()
        app.state.db = None
        app.state.orchestrator = None
    
    yield
    
    logger.info("Shutting down ZRAI Lead OS API Server...")

app = FastAPI(
    title="ZRAI Lead OS API",
    description="REST API for the ZRAI Lead OS LangGraph pipeline",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=_build_cors_origins(),
    allow_origin_regex=_build_cors_origin_regex(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# Dependencies
# ============================================================================

def lead_data_to_model(lead_data: Dict[str, Any]) -> Lead:
    """Convert lead_data dict from database to Lead model."""
    return Lead(
        lead_id=UUID(lead_data.get("lead_id")),
        business_name=lead_data.get("business_name", "Unknown"),
        category=lead_data.get("category"),
        location=lead_data.get("location"),
        geo_tags=lead_data.get("geo_tags", []),
        website=lead_data.get("website"),
        landing_page_url=lead_data.get("landing_page_url") or lead_data.get("website"),
        phone=lead_data.get("phone"),
        emails_found=lead_data.get("emails_found", []),
        facebook_page=lead_data.get("facebook_page"),
        instagram=lead_data.get("instagram"),
        ads_active=lead_data.get("ads_active", False),
        reviews_count=_coerce_int(lead_data.get("reviews_count")),
        rating=_coerce_float(lead_data.get("rating")),
        lead_lifecycle_state=LeadLifecycleState(lead_data.get("lead_lifecycle_state", "NEW")),
    )

async def get_user_id(x_user_id: Optional[str] = Header(None)) -> Optional[str]:
    """Extract user ID from header."""
    return x_user_id

def get_db():
    """Get the database client with lazy initialization for test mode."""
    if not hasattr(app.state, 'db') or app.state.db is None:
        # Lazy initialization - useful for TestClient which may not trigger lifespan
        try:
            from src.db.client import get_supabase_client
            app.state.db = get_supabase_client()
            logger.info("Database client lazily initialized")
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise HTTPException(status_code=503, detail=f"Database not initialized: {e}")
    return app.state.db


def _normalize_whatsapp_body(body: str) -> str:
    return re.sub(r"\s+", " ", (body or "").strip())


def _whatsapp_manual_kill_switch_enabled() -> bool:
    value = str(os.getenv("WHATSAPP_OUTBOUND_KILL_SWITCH", "")).strip().lower()
    return value in {"1", "true", "yes", "on"}


def _whatsapp_cold_outbound_override_enabled() -> bool:
    value = str(os.getenv("WHATSAPP_ALLOW_COLD_OUTBOUND", "")).strip().lower()
    return value in {"1", "true", "yes", "on"}


def _whatsapp_trip_runtime_kill_switch(reason: str) -> None:
    _whatsapp_policy_runtime_state["kill_switch_until"] = (
        datetime.utcnow().timestamp()
        + (WHATSAPP_POLICY_LIMITS["runtime_kill_switch_ms"] / 1000)
    )
    _whatsapp_policy_runtime_state["last_reason"] = reason


def _whatsapp_get_runtime_kill_switch_reason() -> Optional[str]:
    kill_until = _whatsapp_policy_runtime_state.get("kill_switch_until")
    if not kill_until:
        return None
    if datetime.utcnow().timestamp() >= kill_until:
        _whatsapp_policy_runtime_state["kill_switch_until"] = None
        _whatsapp_policy_runtime_state["last_reason"] = None
        return None
    return _whatsapp_policy_runtime_state.get("last_reason") or "runtime_kill_switch_active"


def _whatsapp_has_disclosure(body: str) -> bool:
    return all(pattern.search(body) for pattern in WHATSAPP_AUTOMATION_DISCLOSURE_PATTERNS)


def _whatsapp_has_impersonation_risk(body: str) -> bool:
    return any(pattern.search(body) for pattern in WHATSAPP_AUTOMATION_IMPERSONATION_PATTERNS)


def _whatsapp_get_conversation(db, *, conversation_id: Optional[str], contact_phone: Optional[str], business_phone: Optional[str]) -> Optional[Dict[str, Any]]:
    if conversation_id:
        result = (
            db.client.table("WhatsAppConversation")
            .select("*")
            .eq("id", conversation_id)
            .limit(1)
            .execute()
        )
        if result.data:
            return result.data[0]

    if contact_phone:
        query = (
            db.client.table("WhatsAppConversation")
            .select("*")
            .eq("contactPhone", contact_phone)
        )
        if business_phone:
            query = query.eq("businessPhone", business_phone)
        result = query.limit(1).execute()
        if result.data:
            return result.data[0]

    return None


def _whatsapp_count_recent_outbound_global(db, *, since: datetime) -> int:
    response = (
        db.client.table("WhatsAppMessage")
        .select("id", count="exact")
        .eq("direction", "outgoing")
        .gte("createdAt", since.isoformat())
        .execute()
    )
    if response.count is not None:
        return int(response.count)
    return len(response.data or [])


def _whatsapp_count_recent_outbound_for_contact(db, *, contact_phone: str, since: datetime) -> int:
    conversations = (
        db.client.table("WhatsAppConversation")
        .select("id")
        .eq("contactPhone", contact_phone)
        .execute()
    ).data or []
    conversation_ids = [row.get("id") for row in conversations if row.get("id")]
    if not conversation_ids:
        return 0
    response = (
        db.client.table("WhatsAppMessage")
        .select("id", count="exact")
        .in_("conversationId", conversation_ids)
        .eq("direction", "outgoing")
        .gte("createdAt", since.isoformat())
        .execute()
    )
    if response.count is not None:
        return int(response.count)
    return len(response.data or [])


def _whatsapp_find_recent_duplicate(db, *, conversation_id: str, body: str, since: datetime) -> Optional[Dict[str, Any]]:
    response = (
        db.client.table("WhatsAppMessage")
        .select("*")
        .eq("conversationId", conversation_id)
        .eq("direction", "outgoing")
        .eq("body", body)
        .gte("createdAt", since.isoformat())
        .order("createdAt", desc=True)
        .limit(1)
        .execute()
    )
    if response.data:
        return response.data[0]
    return None


def _whatsapp_latest_inbound_at(db, *, conversation_id: str) -> Optional[datetime]:
    response = (
        db.client.table("WhatsAppMessage")
        .select("createdAt")
        .eq("conversationId", conversation_id)
        .eq("direction", "incoming")
        .order("createdAt", desc=True)
        .limit(1)
        .execute()
    )
    if not response.data:
        return None
    raw_value = response.data[0].get("createdAt")
    if not raw_value:
        return None
    try:
        return datetime.fromisoformat(str(raw_value).replace("Z", "+00:00"))
    except Exception:
        return None

def get_discovery_agent():
    """Get the discovery agent with lazy initialization for test mode."""
    if not hasattr(app.state, 'discovery_agent') or app.state.discovery_agent is None:
        # Lazy initialization - useful for TestClient which may not trigger lifespan
        try:
            from src.agents.discovery import DiscoveryAgent
            app.state.discovery_agent = DiscoveryAgent()
            logger.info("Discovery agent lazily initialized")
        except Exception as e:
            logger.error(f"Failed to initialize discovery agent: {e}")
            raise HTTPException(status_code=503, detail=f"Discovery agent not initialized: {e}")
    return app.state.discovery_agent


def get_audit_agent():
    """Get the audit agent with lazy initialization for test mode."""
    if not hasattr(app.state, 'audit_agent') or app.state.audit_agent is None:
        try:
            from src.agents.audit import AuditAgent
            app.state.audit_agent = AuditAgent()
            logger.info("Audit agent lazily initialized")
        except Exception as e:
            logger.error(f"Failed to initialize audit agent: {e}")
            raise HTTPException(status_code=503, detail=f"Audit agent not initialized: {e}")
    return app.state.audit_agent


def get_enrichment_agent():
    """Get the enrichment agent with lazy initialization."""
    if not hasattr(app.state, 'enrichment_agent') or app.state.enrichment_agent is None:
        try:
            from src.agents.enrichment import EnrichmentAgent
            app.state.enrichment_agent = EnrichmentAgent()
            logger.info("Enrichment agent lazily initialized")
        except Exception as e:
            logger.error(f"Failed to initialize enrichment agent: {e}")
            raise HTTPException(status_code=503, detail=f"Enrichment agent not initialized: {e}")
    return app.state.enrichment_agent


def get_intent_agent():
    """Get the intent agent with lazy initialization."""
    if not hasattr(app.state, 'intent_agent') or app.state.intent_agent is None:
        try:
            from src.agents.intent import IntentAgent
            app.state.intent_agent = IntentAgent()
            logger.info("Intent agent lazily initialized")
        except Exception as e:
            logger.error(f"Failed to initialize intent agent: {e}")
            raise HTTPException(status_code=503, detail=f"Intent agent not initialized: {e}")
    return app.state.intent_agent


def get_scoring_agent():
    """Get the scoring agent with lazy initialization."""
    if not hasattr(app.state, 'scoring_agent') or app.state.scoring_agent is None:
        try:
            from src.agents.scoring import ScoringAgent
            app.state.scoring_agent = ScoringAgent()
            logger.info("Scoring agent lazily initialized")
        except Exception as e:
            logger.error(f"Failed to initialize scoring agent: {e}")
            raise HTTPException(status_code=503, detail=f"Scoring agent not initialized: {e}")
    return app.state.scoring_agent


def get_outreach_agent():
    """Get the outreach agent with lazy initialization."""
    if not hasattr(app.state, 'outreach_agent') or app.state.outreach_agent is None:
        try:
            from src.agents.outreach import OutreachAgent
            app.state.outreach_agent = OutreachAgent()
            logger.info("Outreach agent lazily initialized")
        except Exception as e:
            logger.error(f"Failed to initialize outreach agent: {e}")
            raise HTTPException(status_code=503, detail=f"Outreach agent not initialized: {e}")
    return app.state.outreach_agent


def get_conversation_agent():
    """Get the conversation agent with lazy initialization."""
    if not hasattr(app.state, 'conversation_agent') or app.state.conversation_agent is None:
        try:
            from src.agents.conversation import ConversationAgent
            app.state.conversation_agent = ConversationAgent()
            logger.info("Conversation agent lazily initialized")
        except Exception as e:
            logger.error(f"Failed to initialize conversation agent: {e}")
            raise HTTPException(status_code=503, detail=f"Conversation agent not initialized: {e}")
    return app.state.conversation_agent


def get_governance_agent():
    """Get the governance agent with lazy initialization."""
    if not hasattr(app.state, 'governance_agent') or app.state.governance_agent is None:
        try:
            from src.agents.governance import GovernanceAgent
            app.state.governance_agent = GovernanceAgent()
            logger.info("Governance agent lazily initialized")
        except Exception as e:
            logger.error(f"Failed to initialize governance agent: {e}")
            raise HTTPException(status_code=503, detail=f"Governance agent not initialized: {e}")
    return app.state.governance_agent


def get_orchestrator():
    """Get the orchestrator with lazy initialization."""
    if not hasattr(app.state, 'orchestrator') or app.state.orchestrator is None:
        try:
            from src.graph.orchestrator import LeadOrchestrator
            app.state.orchestrator = LeadOrchestrator()
            logger.info("Orchestrator lazily initialized")
        except Exception as e:
            logger.error(f"Failed to initialize orchestrator: {e}")
            raise HTTPException(status_code=503, detail=f"Orchestrator not initialized: {e}")
    return app.state.orchestrator


def normalize_lead_status(raw_status: Optional[str]) -> str:
    """Map backend lifecycle states into the frontend-facing lead statuses."""
    status = (raw_status or "").strip().upper()
    status_map = {
        "NEW": "discovered",
        "STALE": "discovered",
        "REACTIVATABLE": "discovered",
        "ENGAGED": "replied",
        "QUALIFIED": "qualified",
        "CLOSED_WON": "qualified",
        "CLOSED_LOST": "disqualified",
    }
    return status_map.get(status, "discovered")


def extract_domain(value: Optional[str]) -> Optional[str]:
    """Return a display-safe website/domain string."""
    if not value:
        return None

    parsed = urlparse(value if "://" in value else f"https://{value}")
    return parsed.netloc or parsed.path or value


def _normalized_domain(value: Optional[str]) -> Optional[str]:
    domain = (extract_domain(value) or "").strip().lower()
    if not domain:
        return None
    return domain.removeprefix("www.")


def _domain_truth_score(row: Dict[str, Any]) -> int:
    score = 0
    if row.get("reviews_count") is not None:
        score += 50
    if row.get("rating") is not None:
        score += 30
    if row.get("instagram"):
        score += 12
    if row.get("facebook_page"):
        score += 6
    if row.get("phone"):
        score += 6
    if row.get("emails_found"):
        score += 6
    if row.get("website") or row.get("landing_page_url"):
        score += 2
    return score


def _fetch_domain_sibling_rows(db, domain: Optional[str]) -> List[Dict[str, Any]]:
    normalized_domain = _normalized_domain(domain)
    if not normalized_domain:
        return []
    try:
        result = (
            db.client.table("leads")
            .select("*")
            .or_(f"website.ilike.%{normalized_domain}%,landing_page_url.ilike.%{normalized_domain}%")
            .limit(30)
            .execute()
        )
    except Exception:
        return []
    rows = list(result.data or [])
    return [
        row
        for row in rows
        if _normalized_domain(row.get("website") or row.get("landing_page_url")) == normalized_domain
    ]


def _hydrate_lead_truth_from_domain_siblings(db, lead_data: Dict[str, Any]) -> Dict[str, Any]:
    lead_uuid = UUID(str(lead_data.get("lead_id")))
    domain = _normalized_domain(lead_data.get("website") or lead_data.get("landing_page_url"))
    if not domain:
        return lead_data

    sibling_rows = _fetch_domain_sibling_rows(db, domain)
    if len(sibling_rows) <= 1:
        return lead_data

    best_truth_row = max(sibling_rows, key=_domain_truth_score)
    current_row = next(
        (row for row in sibling_rows if str(row.get("lead_id")) == str(lead_uuid)),
        lead_data,
    )
    updates: Dict[str, Any] = {}

    for field in ("reviews_count", "rating", "instagram", "facebook_page", "phone", "category"):
        if current_row.get(field) in (None, "", [], {}) and best_truth_row.get(field) not in (None, "", [], {}):
            updates[field] = best_truth_row.get(field)

    current_emails = list(current_row.get("emails_found") or [])
    best_emails = list(best_truth_row.get("emails_found") or [])
    merged_emails = _dedupe_strings(current_emails + best_emails)
    if merged_emails and merged_emails != current_emails:
        updates["emails_found"] = merged_emails

    best_name = str(best_truth_row.get("business_name") or "").strip()
    current_name = str(current_row.get("business_name") or "").strip()
    if best_name and (
        not current_name
        or _looks_like_seo_brand_noise(current_name)
        or _is_generic_company_title(
            current_name,
            raw_geo=str(current_row.get("location") or lead_data.get("location") or ""),
            brand_hint=_domain_brand_hint(str(current_row.get("website") or current_row.get("landing_page_url") or "")),
        )
        or _looks_like_search_query_name(current_name)
    ):
        updates["business_name"] = best_name

    if updates:
        db.update_lead(lead_uuid, updates)

    current_state = db.get_lead_state(lead_uuid) or {}
    current_metadata = dict(current_state.get("metadata") or {})
    if not _has_verified_maps_truth(dict(current_metadata.get("raw_apify_data") or {})):
        for sibling in sibling_rows:
            if str(sibling.get("lead_id")) == str(lead_uuid):
                continue
            sibling_state = db.get_lead_state(UUID(str(sibling.get("lead_id")))) or {}
            sibling_metadata = dict(sibling_state.get("metadata") or {})
            sibling_maps_truth = dict(sibling_metadata.get("raw_apify_data") or {})
            if _has_verified_maps_truth(sibling_maps_truth):
                metadata_updates = dict(current_metadata)
                metadata_updates["raw_apify_data"] = sibling_maps_truth
                if sibling_metadata.get("ads_verification") and not metadata_updates.get("ads_verification"):
                    metadata_updates["ads_verification"] = sibling_metadata.get("ads_verification")
                if sibling_metadata.get("people_intelligence") and not metadata_updates.get("people_intelligence"):
                    metadata_updates["people_intelligence"] = sibling_metadata.get("people_intelligence")
                db.save_lead_state(
                    {
                        **current_state,
                        "lead_id": str(lead_uuid),
                        "metadata": metadata_updates,
                    }
                )
                break

    return db.get_lead(lead_uuid) or {**lead_data, **updates}


def _coerce_int(value: Any) -> Optional[int]:
    """Best-effort integer coercion for backend signal facts."""
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)

    raw = str(value).strip()
    if not raw:
        return None

    digits = re.sub(r"[^\d-]", "", raw)
    if digits in {"", "-"}:
        return None

    try:
        return int(digits)
    except ValueError:
        return None


def _coerce_float(value: Any) -> Optional[float]:
    """Best-effort float coercion for backend signal facts."""
    if value is None:
        return None
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)

    raw = str(value).strip()
    if not raw:
        return None

    normalized = re.sub(r"[^0-9.\-]", "", raw)
    if normalized in {"", "-", ".", "-."}:
        return None

    try:
        return float(normalized)
    except ValueError:
        return None


def build_contact_rows(lead_data: Dict[str, Any], enrichment: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Build lightweight frontend contact rows from lead/enrichment data."""
    contact_intelligence = (enrichment or {}).get("contact_intelligence") or {}
    contact_points = list(contact_intelligence.get("contact_points") or [])
    contacts_by_identity: Dict[tuple[str, str], Dict[str, Any]] = {}

    def _contact_row_quality(row: Dict[str, Any]) -> int:
        score = 0
        if row.get("phone"):
            score += 5
        if row.get("email"):
            score += 4 if not _is_generic_email(str(row.get("email"))) else 2
        if row.get("linkedin_url"):
            score += 3
        if _is_plausible_person_name(str(row.get("name") or "")):
            score += 2
        if row.get("title"):
            score += 1
        return score

    for index, point in enumerate(contact_points):
        if not isinstance(point, dict):
            continue
        contact_type = str(point.get("contact_type") or "").strip().lower()
        point_confidence = _coerce_float(point.get("confidence"))
        email = point.get("email")
        if _is_junk_contact_email(email):
            email = None
        phone = _normalize_contact_phone(point.get("phone"))
        linkedin_url = str(point.get("linkedin") or "").strip() or None
        if not any([email, phone, linkedin_url]):
            continue
        has_direct_path = bool(email or phone or linkedin_url)
        is_frontend_worthy = contact_type in {"founder_direct", "doctor_direct", "actual_contact"} or point_confidence >= 85
        if not has_direct_path or not is_frontend_worthy:
            continue
        point_name = str(point.get("name") or "").strip()
        point_owner_scope = str(point.get("owner_scope") or "").strip().lower()
        use_person_name = _is_plausible_person_name(point_name) and point_owner_scope == "person"
        point_role = str(point.get("role") or "").strip() or None
        row = {
            "id": f"{lead_data.get('lead_id')}-ci-contact-{index}",
            "lead_id": str(lead_data.get("lead_id")),
            "name": point_name if use_person_name else (lead_data.get("business_name") or "Clinic contact"),
            "title": point_role if use_person_name else "Clinic contact",
            "email": email,
            "phone": phone,
            "linkedin_url": linkedin_url,
            "is_primary": index == 0,
            "created_at": lead_data.get("created_at") or datetime.utcnow().isoformat(),
        }
        contact_key = (
            ("linkedin", str(linkedin_url).strip().lower())
            if linkedin_url
            else ("phone", str(phone or ""))
            if phone
            else ("email", str(email or "").strip().lower())
        )
        existing = contacts_by_identity.get(contact_key)
        if not existing or _contact_row_quality(row) > _contact_row_quality(existing):
            contacts_by_identity[contact_key] = row
    if contacts_by_identity:
        return list(contacts_by_identity.values())

    emails = []
    if enrichment:
        emails = enrichment.get("validated_emails") or []
    if not emails:
        emails = lead_data.get("emails_found") or []
    emails = [email for email in _dedupe_strings(emails) if not _is_junk_contact_email(email)]

    contact_name = enrichment.get("decision_maker_name") if enrichment else None
    try:
        decision_maker_confidence = float((enrichment or {}).get("decision_maker_confidence") or 0)
    except (TypeError, ValueError):
        decision_maker_confidence = 0.0
    if not _is_plausible_person_name(contact_name) or decision_maker_confidence < 85:
        contact_name = None
    decision_maker_role = str((enrichment or {}).get("decision_maker_role") or "").strip() or None
    fallback_contact_title = None
    if contact_name:
        if decision_maker_confidence >= 85:
            fallback_contact_title = decision_maker_role or "Decision maker"
        else:
            fallback_contact_title = decision_maker_role or "Likely contact"
    phone = _normalize_contact_phone((enrichment or {}).get("normalized_phone") or lead_data.get("phone"))

    contacts_by_identity = {}
    for index, email in enumerate(emails):
        row = {
            "id": f"{lead_data.get('lead_id')}-contact-{index}",
            "lead_id": str(lead_data.get("lead_id")),
            "name": contact_name or lead_data.get("business_name") or "Primary contact",
            "title": fallback_contact_title,
            "email": email,
            "phone": phone,
            "linkedin_url": (enrichment or {}).get("decision_maker_linkedin") if contact_name else None,
            "is_primary": index == 0,
            "created_at": lead_data.get("created_at") or datetime.utcnow().isoformat(),
        }
        identity = ("phone", str(phone)) if phone else ("email", str(email).strip().lower())
        existing = contacts_by_identity.get(identity)
        if not existing or _contact_row_quality(row) > _contact_row_quality(existing):
            contacts_by_identity[identity] = row

    if not contacts_by_identity and phone:
        contacts_by_identity[("phone", str(phone))] = {
            "id": f"{lead_data.get('lead_id')}-phone",
            "lead_id": str(lead_data.get("lead_id")),
            "name": contact_name or lead_data.get("business_name") or "Primary contact",
            "title": "Phone contact",
            "email": None,
            "phone": phone,
            "linkedin_url": (enrichment or {}).get("decision_maker_linkedin") if contact_name else None,
            "is_primary": True,
            "created_at": lead_data.get("created_at") or datetime.utcnow().isoformat(),
        }

    return list(contacts_by_identity.values())


def build_intent_signals(intent: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Convert backend intent data into UI signal rows."""
    if not intent:
        return []

    detected_at = intent.get("created_at") or datetime.utcnow().isoformat()
    why_this_lead = intent.get("why_this_lead")
    speed_risk = intent.get("speed_to_lead_risk")
    review_evidence = intent.get("review_evidence") or []

    signals: List[Dict[str, Any]] = [
        {
            "id": f"{intent.get('lead_id')}-intent-score",
            "lead_id": str(intent.get("lead_id")),
            "signal_type": "intent_score",
            "signal_value": str(intent.get("intent_score", 0)),
            "confidence": max(min(intent.get("intent_score", 0) / 100, 1), 0),
            "source": "intent_agent",
            "detected_at": detected_at,
        },
        {
            "id": f"{intent.get('lead_id')}-leak-score",
            "lead_id": str(intent.get("lead_id")),
            "signal_type": "revenue_leak",
            "signal_value": str(intent.get("leak_score", 0)),
            "confidence": max(min(intent.get("leak_score", 0) / 100, 1), 0),
            "source": "intent_agent",
            "detected_at": detected_at,
        },
    ]

    if speed_risk:
        signals.append(
            {
                "id": f"{intent.get('lead_id')}-speed-risk",
                "lead_id": str(intent.get("lead_id")),
                "signal_type": "speed_to_lead_risk",
                "signal_value": speed_risk,
                "confidence": 0.7 if speed_risk == "HIGH" else 0.5,
                "source": "intent_agent",
                "detected_at": detected_at,
            }
        )

    if why_this_lead:
        signals.append(
            {
                "id": f"{intent.get('lead_id')}-summary",
                "lead_id": str(intent.get("lead_id")),
                "signal_type": "why_this_lead",
                "signal_value": why_this_lead,
                "confidence": 0.8,
                "source": "intent_agent",
                "detected_at": detected_at,
            }
        )

    for index, evidence in enumerate(review_evidence):
        snippet = evidence.get("snippet") if isinstance(evidence, dict) else None
        source_url = evidence.get("source_url") if isinstance(evidence, dict) else None
        if not snippet:
            continue
        signals.append(
            {
                "id": f"{intent.get('lead_id')}-review-{index}",
                "lead_id": str(intent.get("lead_id")),
                "signal_type": "review_evidence",
                "signal_value": snippet,
                "confidence": 0.7,
                "source": source_url or "reviews",
                "detected_at": detected_at,
            }
        )

    return signals


def _dedupe_strings(values: List[Any]) -> List[str]:
    deduped: List[str] = []
    seen = set()
    for value in values:
        if value is None:
            continue
        normalized = str(value).strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped


def _parse_iso_datetime(value: Any) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


GENERIC_EMAIL_DOMAINS = {
    "gmail.com",
    "googlemail.com",
    "yahoo.com",
    "yahoo.co.in",
    "outlook.com",
    "hotmail.com",
    "live.com",
    "icloud.com",
    "proton.me",
    "protonmail.com",
    "rediffmail.com",
}


def _is_generic_email(email: str) -> bool:
    if "@" not in email:
        return True
    return email.split("@", 1)[1].strip().lower() in GENERIC_EMAIL_DOMAINS


def _is_junk_contact_email(email: Optional[str]) -> bool:
    lowered = str(email or "").strip().lower()
    if not lowered or "@" not in lowered:
        return True
    if lowered.startswith("frame-"):
        return True
    if any(token in lowered for token in ("@mht", "@mhtml", ".mht", ".mhtml", "cid:", "content-id")):
        return True
    if lowered.endswith("@example.com") or lowered.endswith("@example.org"):
        return True
    local_part = lowered.split("@", 1)[0]
    if len(local_part) > 48 and any(char.isdigit() for char in local_part):
        return True
    return False


def _normalize_contact_phone(phone: Optional[str]) -> Optional[str]:
    digits = re.sub(r"\D", "", str(phone or ""))
    if len(digits) < 7:
        return None
    core = digits[-10:]
    if len(set(core)) == 1:
        return None
    if core in {"0123456789", "1234567890", "0987654321", "9876543210"}:
        return None
    if core.endswith("123456789") or core.endswith("987654321"):
        return None
    return f"+{digits}" if str(phone or "").strip().startswith("+") else digits


def _normalize_branch_label(value: Optional[str]) -> Optional[str]:
    text = re.sub(r"\s+", " ", str(value or "")).strip(" -,:;")
    if not text:
        return None
    if len(text) > 180:
        return None
    if text.startswith("![") or "!(" in text or "](" in text:
        return None
    lowered = text.lower()
    for alias, canonical in BRANCH_LOCALITY_ALIASES.items():
        if alias in lowered:
            return canonical
    if re.search(r"\b\d{5,6}\b", lowered):
        return None
    if re.search(r"\b(?:bangalore|bengaluru)\b", lowered) and not any(
        token in lowered for token in BRANCH_LOCALITY_ALIASES
    ):
        return None
    blocked_terms = {
        "about us",
        "contact us",
        "book appointment",
        "book your appointment",
        "treatments",
        "treatment",
        "gallery",
        "offers",
        "offer",
        "popular treatments",
        "latest offers",
        "chemical peel",
        "photo facial",
        "microdermabrasion",
        "laser hair",
        "prp",
        "consultant",
        "dermatologist",
        "specialist",
        "doctor",
        "physician",
        "surgeon",
        "receptionist",
        "manager",
        "admin",
        "call",
        "phone",
        "email",
    }
    if "@" in lowered or lowered.startswith("http"):
        return None
    if ("," in text or "#" in text) and len(text) > 30:
        return None
    if any(term in lowered for term in blocked_terms):
        return None
    location_tokens = (
        "nagar",
        "layout",
        "road",
        "rd",
        "block",
        "phase",
        "cross",
        "main",
        "koramangala",
        "jayanagar",
        "indiranagar",
        "whitefield",
        "hsr",
        "jp",
        "bengaluru",
        "bangalore",
        "branch",
        "sarjapur",
        "thanisandra",
        "chikkabellandur",
    )
    if not any(token in lowered for token in location_tokens):
        return None
    if any(token in lowered for token in ("road", "rd", "cross", "main", "block", "phase")):
        return None
    return text


def _extract_business_tokens(*values: Any) -> List[str]:
    blocked = {
        "clinic",
        "clinics",
        "skin",
        "hair",
        "laser",
        "care",
        "center",
        "centre",
        "hospital",
        "dermatology",
        "aesthetic",
        "aesthetics",
        "cosmetic",
        "doctor",
        "doctors",
        "specialist",
        "specialists",
        "best",
        "top",
        "premium",
        "beauty",
        "weight",
        "loss",
        "bangalore",
        "bengaluru",
    }
    tokens: List[str] = []
    seen = set()
    for value in values:
        for token in re.findall(r"[a-z0-9]+", str(value or "").lower()):
            if len(token) < 3 or token in blocked or token in seen:
                continue
            seen.add(token)
            tokens.append(token)
    return tokens


def _maps_candidate_matches_business(
    candidate: Dict[str, Any],
    *,
    business_name: Optional[str],
    website: Optional[str],
) -> bool:
    haystack = " ".join(
        [
            str(candidate.get("title") or candidate.get("name") or ""),
            str(candidate.get("website") or ""),
            str(candidate.get("url") or ""),
            str(candidate.get("address") or ""),
        ]
    ).lower()
    if not haystack.strip():
        return False

    brand_hint = _domain_brand_hint(str(website or "")) if website else ""
    business_tokens = _extract_business_tokens(business_name, brand_hint)
    if not business_tokens:
        return True

    matched = sum(1 for token in business_tokens if token in haystack)
    required = 1 if len(business_tokens) <= 2 else 2
    return matched >= required


def _extract_maps_branch_names(
    raw_apify_data: Dict[str, Any],
    *,
    business_name: Optional[str],
    website: Optional[str],
) -> List[str]:
    if not isinstance(raw_apify_data, dict):
        return []

    branch_names: List[str] = []
    seen = set()

    def _append_candidate(value: Any) -> None:
        normalized = _normalize_branch_label(value)
        if not normalized:
            return
        key = normalized.lower()
        if key in seen:
            return
        seen.add(key)
        branch_names.append(normalized)

    related_places = list(raw_apify_data.get("relatedPlaces") or [])
    for place in related_places:
        if not isinstance(place, dict):
            continue
        if not _maps_candidate_matches_business(
            place,
            business_name=business_name,
            website=website,
        ):
            continue
        _append_candidate(place.get("address"))

    if not branch_names:
        title_candidate = {
            "title": raw_apify_data.get("maps_title"),
            "address": raw_apify_data.get("maps_address"),
            "website": raw_apify_data.get("maps_website") or website,
        }
        if _maps_candidate_matches_business(
            title_candidate,
            business_name=business_name,
            website=website,
        ):
            _append_candidate(raw_apify_data.get("maps_address"))

    return branch_names[:4]


def _is_strong_doctor_profile(profile: Dict[str, Any]) -> bool:
    if not isinstance(profile, dict):
        return False
    role = str(profile.get("role") or "").strip().lower()
    source = str(profile.get("source") or "").strip().lower()
    if role in {"doctor_named_brand", "business_name"} or source == "business_name":
        return False
    if any(token in role for token in ("founder", "director", "senior doctor", "senior_doctor")):
        return True
    if any(token in source for token in ("doctor roster", "doctor_roster")):
        return True
    specialty = str(profile.get("specialty") or "").lower()
    experience = str(profile.get("experience") or "").lower()
    context = " ".join(
        [
            specialty,
            experience,
            str(profile.get("title") or "").lower(),
            str(profile.get("bio") or "").lower(),
        ]
    )
    has_medical_evidence = bool(
        re.search(
            r"\b(?:mbbs|md|ms|dnb|dvd|mch|dermatologist|cosmetologist|plastic surgeon|trichologist|consultant)\b",
            context,
        )
    )
    if bool(profile.get("explicit_dr_prefix")) and (
        has_medical_evidence or source in {"website_asset", "website_page", "website_copy", "people_search"}
    ):
        return True
    if has_medical_evidence and source in {"website_asset", "website_page", "website_copy", "people_search"}:
        return True
    return False


def _sanitize_branch_contacts(values: List[Any]) -> List[Dict[str, Any]]:
    deduped: List[Dict[str, Any]] = []
    seen = set()
    for value in values:
        if not isinstance(value, dict):
            continue
        raw_name = str(value.get("name") or "").strip()
        name = _normalize_branch_label(raw_name)
        if raw_name and not name:
            continue
        phone = _normalize_contact_phone(value.get("phone"))
        if not name and not phone:
            continue
        key = ("name", str(name or "").lower()) if name else ("phone", phone or "")
        if key in seen:
            continue
        seen.add(key)
        cleaned = dict(value)
        cleaned["name"] = name
        cleaned["phone"] = phone
        deduped.append(cleaned)
    return deduped


def _sanitize_doctor_profiles(values: List[Any]) -> List[Dict[str, Any]]:
    deduped: List[Dict[str, Any]] = []
    seen = set()
    for value in values:
        if not isinstance(value, dict):
            continue
        name = str(value.get("name") or "").strip()
        if not _is_plausible_person_name(name):
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned = dict(value)
        cleaned["name"] = name
        emails = [
            email
            for email in _dedupe_strings(list(value.get("emails") or []))
            if not _is_junk_contact_email(email)
        ]
        phones = [
            phone
            for phone in (_normalize_contact_phone(item) for item in list(value.get("phones") or []))
            if phone
        ]
        cleaned["emails"] = emails
        cleaned["phones"] = _dedupe_strings(phones)
        deduped.append(cleaned)
    return deduped


def _sanitize_decision_maker_candidates(values: List[Any]) -> List[Dict[str, Any]]:
    cleaned_candidates: List[Dict[str, Any]] = []
    seen = set()
    for value in values:
        if not isinstance(value, dict):
            continue
        name = str(value.get("name") or "").strip()
        if not _is_plausible_person_name(name):
            continue
        emails = [
            email
            for email in _dedupe_strings(list(value.get("emails") or []))
            if not _is_junk_contact_email(email)
        ]
        phones = [
            phone
            for phone in (_normalize_contact_phone(item) for item in list(value.get("phones") or []))
            if phone
        ]
        has_direct_evidence = bool(emails or phones or value.get("linkedin"))
        if not has_direct_evidence:
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned = dict(value)
        cleaned["name"] = name
        cleaned["emails"] = emails
        cleaned["phones"] = _dedupe_strings(phones)
        cleaned_candidates.append(cleaned)
    cleaned_candidates.sort(key=lambda item: int(item.get("score") or 0), reverse=True)
    return cleaned_candidates


def _pick_best_email(emails: List[Any], website: Optional[str]) -> Optional[str]:
    deduped = [email for email in _dedupe_strings(emails) if not _is_junk_contact_email(email)]
    if not deduped:
        return None

    website_host = ""
    if website:
        parsed = urlparse(str(website) if "://" in str(website) else f"https://{website}")
        website_host = parsed.netloc.lower().removeprefix("www.")

    exact_domain_matches: List[str] = []
    custom_domain_emails: List[str] = []
    generic_emails: List[str] = []

    for email in deduped:
        if "@" not in email:
            continue
        domain = email.split("@", 1)[1].strip().lower()
        if website_host and domain == website_host:
            exact_domain_matches.append(email)
        elif not _is_generic_email(email):
            custom_domain_emails.append(email)
        else:
            generic_emails.append(email)

    return (exact_domain_matches or custom_domain_emails or generic_emails or deduped)[0]


def _is_plausible_person_name(value: Optional[str]) -> bool:
    if not value:
        return False

    blocked_tokens = {
        "clinic",
        "skin",
        "hair",
        "laser",
        "care",
        "center",
        "centre",
        "hospital",
        "dermatology",
        "aesthetic",
        "aesthetics",
        "cosmetic",
        "cosmetology",
        "consultant",
        "dermatologist",
        "doctor",
        "specialist",
        "surgeon",
        "physician",
        "receptionist",
        "admin",
        "manager",
    }
    tokens = [token.lower() for token in re.findall(r"[A-Za-z]+", str(value))]
    significant_tokens = [token for token in tokens if len(token) > 1]
    if len(significant_tokens) < 2 and not (
        len(significant_tokens) == 1
        and len(tokens) >= 2
        and len(tokens[0]) > 1
    ):
        return False
    if any(token in blocked_tokens for token in significant_tokens):
        return False
    return True


def _derive_best_contact_channel(
    *,
    phone_numbers: List[str],
    best_contact_email: Optional[str],
    whatsapp_detected: bool,
    whatsapp_target: Optional[str],
    decision_maker_linkedin: Optional[str],
) -> tuple[Optional[str], Optional[str]]:
    if whatsapp_detected:
        if whatsapp_target:
            return "whatsapp", "An explicit WhatsApp entry path is visible and can be used as the fastest response route."
    if best_contact_email:
        if _is_generic_email(best_contact_email):
            return "email", "Email is available, but it looks generic, so keep the opener tight and specific."
        return "email", "A direct business email is available for a cleaner decision-maker outreach path."
    if phone_numbers:
        return "phone", "Direct phone is available and can be used for receptionist bypass or operator follow-up."
    if decision_maker_linkedin:
        return "linkedin", "LinkedIn is the cleanest available path to the likely decision maker."
    return None, None


def _build_social_profiles(lead_data: Dict[str, Any]) -> Dict[str, str]:
    profiles: Dict[str, str] = {}
    if lead_data.get("facebook_page"):
        profiles["facebook"] = str(lead_data["facebook_page"])
    if lead_data.get("instagram"):
        profiles["instagram"] = str(lead_data["instagram"])
    return profiles


def _merge_social_profiles(*payloads: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    merged: Dict[str, Any] = {}
    for payload in payloads:
        if not payload:
            continue
        for key, value in payload.items():
            if value in (None, "", [], {}):
                continue
            if isinstance(value, list):
                # Guard: if existing value was stored as a string by a previous
                # payload, wrap it in a list - never call list(string) which
                # explodes it into individual characters.
                existing_val = merged.get(key)
                if isinstance(existing_val, list):
                    existing = list(existing_val)
                elif isinstance(existing_val, str) and existing_val.strip():
                    existing = [existing_val.strip()]
                else:
                    existing = []
                # Filter incoming list to strings only (drop accidental char fragments).
                incoming = [v for v in value if isinstance(v, str) and v.strip()]
                combined = _dedupe_strings(existing + incoming)
                if key in _SOCIAL_URL_LIST_KEYS:
                    combined = _filter_social_url_list(key, combined)
                merged[key] = combined
            elif isinstance(value, str):
                stripped = value.strip()
                if not stripped:
                    continue
                existing_val = merged.get(key)
                if isinstance(existing_val, list):
                    if stripped not in existing_val:
                        existing_val = existing_val + [stripped]
                    if key in _SOCIAL_URL_LIST_KEYS:
                        merged[key] = _filter_social_url_list(key, existing_val)
                    else:
                        merged[key] = _dedupe_strings(existing_val)
                else:
                    merged[key] = stripped
            else:
                merged[key] = value
    return merged


def _sanitize_social_metric(value: Any) -> Optional[int]:
    if value in (None, "", [], {}):
        return None
    try:
        normalized = int(float(value))
    except (TypeError, ValueError):
        digits = re.sub(r"[^\d]", "", str(value or ""))
        if not digits:
            return None
        normalized = int(digits)
    if normalized < 0:
        return None
    return normalized


def _normalize_instagram_profile_url(url: Any) -> Optional[str]:
    raw = str(url or "").strip()
    if not raw:
        return None
    parsed = urlparse(raw if raw.startswith(("http://", "https://")) else f"https://{raw}")
    hostname = parsed.netloc.lower().replace("www.", "")
    if hostname != "instagram.com":
        return None
    segments = [segment.strip() for segment in parsed.path.split("/") if segment.strip()]
    if not segments:
        return None
    username = segments[0].lstrip("@")
    if username.lower() in {"accounts", "developer", "directory", "explore", "p", "reel", "reels", "share", "stories", "tv"}:
        return None
    if not re.fullmatch(r"[A-Za-z0-9._]{1,30}", username):
        return None
    # Reject pure-numeric / decimal handles like GPS coords (e.g. "13.0533989")
    # and any handle that doesn't contain at least 2 letters.
    if re.fullmatch(r"\d+(?:\.\d+)?", username):
        return None
    if len(re.findall(r"[A-Za-z]", username)) < 2:
        return None
    return f"https://www.instagram.com/{username}/"


# Map of social-network keys that hold *lists of profile URLs* in social_profiles.
# These need re-filtering at merge time to drop garbage from cached/persisted state.
_SOCIAL_URL_LIST_KEYS = {"instagram", "youtube", "facebook", "linkedin"}


def _filter_social_url_list(network: str, urls: List[str]) -> List[str]:
    """Re-normalize/validate a list of social URLs for a given network.

    Used inside _merge_social_profiles so any junk left in cached/persisted
    `social_profiles[*]` (e.g. exploded URL characters, GPS-coordinate-shaped
    Instagram handles) is filtered out on every read."""
    cleaned: List[str] = []
    seen: set = set()
    for raw in urls:
        if not isinstance(raw, str):
            continue
        candidate = raw.strip()
        if not candidate:
            continue
        # Drop single-character fragments left over from a previous broken merge.
        if len(candidate) <= 2 and "/" not in candidate and "." not in candidate:
            continue
        if network == "instagram":
            normalized = _normalize_instagram_profile_url(candidate)
        elif network == "youtube":
            normalized = _normalize_youtube_channel_url(candidate)
        elif network == "facebook":
            normalized = candidate if "facebook.com" in candidate.lower() else None
        elif network == "linkedin":
            normalized = candidate if "linkedin.com" in candidate.lower() else None
        else:
            normalized = candidate
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        cleaned.append(normalized)
    return cleaned


def _normalize_youtube_channel_url(url: Any) -> Optional[str]:
    raw = str(url or "").strip()
    if not raw:
        return None
    parsed = urlparse(raw if raw.startswith(("http://", "https://")) else f"https://{raw}")
    hostname = parsed.netloc.lower().replace("www.", "").replace("m.", "")
    if hostname != "youtube.com":
        return None
    segments = [segment.strip() for segment in parsed.path.split("/") if segment.strip()]
    if not segments:
        return None
    first = segments[0]
    if first.lower() in {"embed", "feed", "hashtag", "live", "playlist", "results", "shorts", "watch"}:
        return None
    if first.startswith("@") and len(first) > 1:
        return f"https://www.youtube.com/{first}"
    if first in {"c", "channel", "user"} and len(segments) > 1 and segments[1]:
        return f"https://www.youtube.com/{first}/{segments[1]}"
    return None


def _sanitize_instagram_profile(profile: Dict[str, Any]) -> Dict[str, Any]:
    if not profile:
        return {}
    username = str(profile.get("username") or "").strip().lstrip("@")
    if username and not re.fullmatch(r"[A-Za-z0-9._]{1,30}", username):
        username = ""
    profile_url = _normalize_instagram_profile_url(profile.get("profile_url"))
    if not username and profile_url:
        username = profile_url.rstrip("/").split("/")[-1]
    sanitized = {
        "username": username or None,
        "profile_url": profile_url,
        "full_name": str(profile.get("full_name") or "").strip() or None,
        "bio": str(profile.get("bio") or "").strip() or None,
        "external_url": str(profile.get("external_url") or "").strip() or None,
        "followers_count": _sanitize_social_metric(profile.get("followers_count")),
        "following_count": _sanitize_social_metric(profile.get("following_count")),
        "verified": bool(profile.get("verified")) if profile.get("verified") is not None else None,
        "email": str(profile.get("email") or "").strip().lower() or None,
        "is_business_account": bool(profile.get("is_business_account")) if profile.get("is_business_account") is not None else None,
        "business_category": str(profile.get("business_category") or "").strip() or None,
        "posts_count": _sanitize_social_metric(profile.get("posts_count")),
        "latest_post_count": _sanitize_social_metric(profile.get("latest_post_count")),
        "profile_pic_url": str(profile.get("profile_pic_url") or "").strip() or None,
        "source": str(profile.get("source") or "").strip() or None,
    }
    if not sanitized["username"] and not sanitized["profile_url"]:
        return {}
    return {key: value for key, value in sanitized.items() if value not in (None, "", [], {})}


def _sanitize_youtube_channel(channel: Dict[str, Any]) -> Dict[str, Any]:
    if not channel:
        return {}
    channel_url = _normalize_youtube_channel_url(channel.get("channel_url"))
    sanitized = {
        "channel_name": str(channel.get("channel_name") or "").strip() or None,
        "channel_url": channel_url,
        "subscriber_count": _sanitize_social_metric(channel.get("subscriber_count")),
        "total_views": _sanitize_social_metric(channel.get("total_views")),
        "total_videos": _sanitize_social_metric(channel.get("total_videos")),
        "recent_video_count": _sanitize_social_metric(channel.get("recent_video_count")),
        "avg_recent_views": _sanitize_social_metric(channel.get("avg_recent_views")),
        "latest_video_date": str(channel.get("latest_video_date") or "").strip() or None,
        "source": str(channel.get("source") or "").strip() or None,
    }
    if not sanitized["channel_url"] and not sanitized["channel_name"]:
        return {}
    return {key: value for key, value in sanitized.items() if value not in (None, "", [], {})}


def derive_analysis_updated_at(
    enrichment: Optional[Dict[str, Any]],
    intent: Optional[Dict[str, Any]],
    proof: Optional[Dict[str, Any]],
    scoring: Optional[Dict[str, Any]],
    outreach: Optional[List[Dict[str, Any]]],
    lead_state: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    candidates = [
        _parse_iso_datetime((enrichment or {}).get("created_at")),
        _parse_iso_datetime((intent or {}).get("created_at")),
        _parse_iso_datetime((proof or {}).get("generated_at")),
        _parse_iso_datetime((scoring or {}).get("created_at")),
        _parse_iso_datetime((lead_state or {}).get("updated_at")),
    ]

    for item in outreach or []:
        candidates.append(_parse_iso_datetime(item.get("created_at")))

    valid_candidates = [candidate for candidate in candidates if candidate is not None]
    if not valid_candidates:
        return None

    return max(valid_candidates).isoformat()


def derive_analysis_state(
    *,
    enrichment: Optional[Dict[str, Any]],
    intent: Optional[Dict[str, Any]],
    proof: Optional[Dict[str, Any]],
    scoring: Optional[Dict[str, Any]],
    outreach: Optional[List[Dict[str, Any]]],
    lead_state: Optional[Dict[str, Any]] = None,
) -> str:
    if lead_state and lead_state.get("last_error") and not any([enrichment, intent, proof, scoring, outreach]):
        return "failed"

    if any([enrichment, intent, proof, scoring, outreach]):
        return "analyzed"

    if lead_state and lead_state.get("current_stage") in {
        "analysis",
        "enrichment",
        "intent",
        "audit",
        "scoring",
        "outreach",
    }:
        return "analyzing"

    return "preview"


def build_signal_facts(
    lead_data: Dict[str, Any],
    enrichment: Optional[Dict[str, Any]] = None,
    intent: Optional[Dict[str, Any]] = None,
    proof: Optional[Dict[str, Any]] = None,
    scoring: Optional[Dict[str, Any]] = None,
    lead_state: Optional[Dict[str, Any]] = None,
    runtime_metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    enrichment_payload = enrichment or {}
    intent_payload = intent or {}
    proof_extraction = (proof or {}).get("extraction_data") or {}
    lead_state_metadata = {
        **dict((lead_state or {}).get("metadata") or {}),
        **dict(runtime_metadata or {}),
    }
    stored_analysis_bundle = (
        lead_state_metadata.get("analysis_bundle")
        or lead_state_metadata.get("intelligence")
        or {}
    )
    stored_signal_facts = dict(stored_analysis_bundle.get("facts") or {})
    raw_apify_data = dict(lead_state_metadata.get("raw_apify_data") or {})
    has_verified_maps_truth = _has_verified_maps_truth(raw_apify_data)
    ads_verification = lead_state_metadata.get("ads_verification") or {}
    people_intelligence = dict(lead_state_metadata.get("people_intelligence") or {})
    allow_stored_signal_fallback = not any(
        [
            enrichment_payload,
            intent_payload,
            proof_extraction,
            raw_apify_data,
            people_intelligence,
        ]
    )
    instagram_profile = _sanitize_instagram_profile(dict(
        people_intelligence.get("instagram_profile")
        or stored_signal_facts.get("instagram_profile")
        or {}
    ))
    youtube_channel = _sanitize_youtube_channel(dict(
        people_intelligence.get("youtube_channel")
        or stored_signal_facts.get("youtube_channel")
        or {}
    ))

    phone_numbers = _dedupe_strings(
        [
            phone
            for phone in (
                _normalize_contact_phone(value)
                for value in (
                    list(proof_extraction.get("phone_numbers") or [])
                    + ([enrichment_payload.get("normalized_phone")] if enrichment_payload.get("normalized_phone") else [])
                    + ([lead_data.get("phone")] if lead_data.get("phone") else [])
                    + list(people_intelligence.get("phone_numbers") or [])
                    + [
                        contact.get("phone")
                        for contact in list(people_intelligence.get("branch_contacts") or [])
                        if isinstance(contact, dict)
                    ]
                )
            )
            if phone
        ]
    )
    phone_visible = (
        str(proof_extraction.get("phone_visibility") or "").lower()
        in {"hero", "visible", "above_fold", "below_fold"}
    ) or bool(phone_numbers)

    booking_target = (
        proof_extraction.get("booking_link")
        or enrichment_payload.get("booking_link")
        or lead_state_metadata.get("booking_target")
    )
    contact_paths = _dedupe_strings(
        list(enrichment_payload.get("contact_paths") or [])
        + list(lead_state_metadata.get("contact_paths") or [])
        + list(lead_state_metadata.get("preview_contact_paths") or [])
    )
    booking_detected = bool(
        booking_target
        or enrichment_payload.get("booking_provider")
        or proof_extraction.get("booking_detected")
        or "booking" in contact_paths
        or "booking link" in contact_paths
    )
    contact_form_detected = bool(
        proof_extraction.get("contact_form_detected")
        or
        enrichment_payload.get("form_tool")
        or "contact form" in contact_paths
        or "form" in contact_paths
    )

    whatsapp_target = proof_extraction.get("whatsapp_target")
    whatsapp_widget_detected = bool(
        proof_extraction.get("chat_widget") == "whatsapp"
        or enrichment_payload.get("chat_widget") == "whatsapp"
    )
    whatsapp_detected = bool(whatsapp_target)
    chat_widget_type = proof_extraction.get("chat_widget") or enrichment_payload.get("chat_widget")

    if ads_verification.get("status") in {"yes", "no", "not_checked"}:
        ads_status = ads_verification.get("status")
    elif lead_data.get("ad_last_seen") or lead_data.get("ad_start_date"):
        ads_status = "yes" if lead_data.get("ads_active") else "not_checked"
    else:
        ads_status = "not_checked"

    ads_channels = _dedupe_strings(list(ads_verification.get("channels") or []))
    ads_last_seen = ads_verification.get("last_seen") or lead_data.get("ad_last_seen")
    ads_active_count = ads_verification.get("active_ads_count")
    ads_creative_hints = _dedupe_strings(list(ads_verification.get("creative_hints") or []))
    ads_page_names = _dedupe_strings(list(ads_verification.get("page_names") or []))

    services = _dedupe_strings(
        list(enrichment_payload.get("key_services") or [])
        + list(proof_extraction.get("services") or [])
        + ([lead_data.get("category")] if lead_data.get("category") else [])
    )
    social_profiles = _merge_social_profiles(
        _build_social_profiles(lead_data),
        enrichment_payload.get("social_profiles") or {},
        proof_extraction.get("social_profiles") or {},
        people_intelligence.get("social_profiles") or {},
        stored_signal_facts.get("social_profiles") or {},
    )
    instagram_urls = social_profiles.get("instagram") if isinstance(social_profiles.get("instagram"), list) else (
        [social_profiles.get("instagram")] if social_profiles.get("instagram") else []
    )
    youtube_urls = social_profiles.get("youtube") if isinstance(social_profiles.get("youtube"), list) else (
        [social_profiles.get("youtube")] if social_profiles.get("youtube") else []
    )
    if not instagram_profile:
        normalized_instagram_url = next(
            (
                normalized
                for normalized in (
                    _normalize_instagram_profile_url(candidate)
                    for candidate in instagram_urls
                )
                if normalized
            ),
            None,
        )
        if normalized_instagram_url:
            instagram_profile = _sanitize_instagram_profile(
                {
                    "profile_url": normalized_instagram_url,
                    "source": "website_instagram_link",
                }
            )
    if not youtube_channel:
        normalized_youtube_url = next(
            (
                normalized
                for normalized in (
                    _normalize_youtube_channel_url(candidate)
                    for candidate in youtube_urls
                )
                if normalized
            ),
            None,
        )
        if normalized_youtube_url:
            youtube_channel = _sanitize_youtube_channel(
                {
                    "channel_url": normalized_youtube_url,
                    "source": "website_youtube_link",
                }
            )
    if instagram_profile and not social_profiles.get("instagram_profile"):
        social_profiles["instagram_profile"] = instagram_profile
    if youtube_channel and not social_profiles.get("youtube_channel"):
        social_profiles["youtube_channel"] = youtube_channel
    fresh_doctor_profiles = [
        profile
        for profile in _sanitize_doctor_profiles(list(people_intelligence.get("doctor_profiles") or []))
        if _is_strong_doctor_profile(profile)
    ]
    fresh_decision_maker_candidates = _sanitize_decision_maker_candidates(
        list(people_intelligence.get("decision_maker_candidates") or [])
    )
    fresh_branch_contacts = _sanitize_branch_contacts(list(people_intelligence.get("branch_contacts") or []))
    fresh_contact_evidence = list(people_intelligence.get("contact_evidence") or [])
    maps_branch_names = _extract_maps_branch_names(
        raw_apify_data,
        business_name=lead_data.get("business_name"),
        website=lead_data.get("website") or lead_data.get("landing_page_url"),
    )
    fresh_branch_name_values = (
        list(proof_extraction.get("branch_names") or [])
        + list(people_intelligence.get("branch_names") or [])
    )
    fresh_doctor_name_values = (
        list(proof_extraction.get("doctor_names") or [])
        + list(people_intelligence.get("doctor_names") or [])
    )
    sanitized_fresh_branch_names = _dedupe_strings(
        [
            normalized
            for normalized in (_normalize_branch_label(name) for name in fresh_branch_name_values)
            if normalized
        ]
    )
    sanitized_fresh_doctor_names = _dedupe_strings(
        [
            str(name).strip()
            for name in fresh_doctor_name_values
            if _is_plausible_person_name(str(name).strip())
        ]
    )
    has_fresh_branch_evidence = bool(fresh_branch_contacts or sanitized_fresh_branch_names)
    has_fresh_doctor_evidence = bool(fresh_doctor_profiles or sanitized_fresh_doctor_names)
    has_fresh_decision_maker_evidence = bool(
        (
            enrichment_payload.get("decision_maker_name")
            if _is_plausible_person_name(str(enrichment_payload.get("decision_maker_name") or "").strip())
            else None
        )
        or people_intelligence.get("decision_maker_name")
        or people_intelligence.get("decision_maker_linkedin")
        or people_intelligence.get("best_contact_linkedin")
        or fresh_decision_maker_candidates
    )
    doctor_profiles = (
        fresh_doctor_profiles
        or (
            []
            if (has_fresh_doctor_evidence or not allow_stored_signal_fallback)
            else list(stored_signal_facts.get("doctor_profiles") or [])
        )
    )
    if doctor_profiles and doctor_profiles is not fresh_doctor_profiles:
        doctor_profiles = [
            profile
            for profile in _sanitize_doctor_profiles(doctor_profiles)
            if _is_strong_doctor_profile(profile)
        ]
    decision_maker_candidates = (
        fresh_decision_maker_candidates
        or (
            []
            if (has_fresh_decision_maker_evidence or not allow_stored_signal_fallback)
            else list(stored_signal_facts.get("decision_maker_candidates") or [])
        )
    )
    if decision_maker_candidates and decision_maker_candidates is not fresh_decision_maker_candidates:
        decision_maker_candidates = _sanitize_decision_maker_candidates(decision_maker_candidates)
    branch_contacts = (
        fresh_branch_contacts
        or (
            []
            if (has_fresh_branch_evidence or not allow_stored_signal_fallback)
            else list(stored_signal_facts.get("branch_contacts") or [])
        )
    )
    if branch_contacts and branch_contacts is not fresh_branch_contacts:
        branch_contacts = _sanitize_branch_contacts(branch_contacts)
    contact_evidence = _dedupe_strings(
        fresh_contact_evidence
        + (
            []
            if (
                has_fresh_branch_evidence
                or has_fresh_doctor_evidence
                or has_fresh_decision_maker_evidence
                or not allow_stored_signal_fallback
            )
            else list(stored_signal_facts.get("contact_evidence") or [])
        )
    )
    branch_contact_names = _dedupe_strings(
        [
            contact.get("name")
            for contact in branch_contacts
            if isinstance(contact, dict) and contact.get("name")
        ]
    )
    stored_branch_names = [
        normalized
        for normalized in (
            _normalize_branch_label(name)
            for name in list(stored_signal_facts.get("branch_names") or [])
        )
        if normalized
    ]
    corroborated_fresh_branch_names = [
        name
        for name in sanitized_fresh_branch_names
        if name in set(branch_contact_names or maps_branch_names)
    ]
    verified_branch_names = branch_contact_names or corroborated_fresh_branch_names
    branch_names = (
        verified_branch_names
        or sanitized_fresh_branch_names
        or maps_branch_names
        or (
            []
            if (has_fresh_branch_evidence or not allow_stored_signal_fallback)
            else _dedupe_strings(stored_branch_names)
        )
    )
    verified_doctor_names = _dedupe_strings(
        [
            profile.get("name")
            for profile in doctor_profiles
            if isinstance(profile, dict) and profile.get("name")
        ]
    )
    stored_verified_doctor_names = (
        []
        if (has_fresh_doctor_evidence or not allow_stored_signal_fallback)
        else [
            str(name).strip()
            for name in list(stored_signal_facts.get("doctor_names") or [])
            if _is_plausible_person_name(str(name).strip())
        ]
    )
    doctor_names = verified_doctor_names or sanitized_fresh_doctor_names or _dedupe_strings(stored_verified_doctor_names)
    branch_count = len(branch_names)
    doctor_count = len(doctor_profiles) if doctor_profiles else len(doctor_names)
    multi_clinic = bool(branch_count > 1)
    cached_reviews_count = _coerce_int(
        lead_data.get("reviews_count")
        if lead_data.get("reviews_count") is not None
        else stored_signal_facts.get("reviews_count")
    )
    cached_rating = _coerce_float(
        lead_data.get("rating")
        if lead_data.get("rating") is not None
        else stored_signal_facts.get("rating")
    )
    reviews_count = raw_apify_data.get("reviewsCount") if has_verified_maps_truth else cached_reviews_count
    rating = raw_apify_data.get("totalScore") if has_verified_maps_truth else cached_rating
    fact_sources = {
        "reviews": "google_maps" if has_verified_maps_truth and reviews_count is not None else "google_maps_cached" if reviews_count is not None else "not_verified",
        "rating": "google_maps" if has_verified_maps_truth and rating is not None else "google_maps_cached" if rating is not None else "not_verified",
        "locations": (
            "website_contact_page"
            if branch_contact_names
            else "website_corroborated"
            if corroborated_fresh_branch_names
            else "website_text"
            if sanitized_fresh_branch_names
            else "google_maps"
            if maps_branch_names
            else "not_verified"
        ),
        "doctors": (
            "website_doctor_profile"
            if doctor_profiles
            else "website_text"
            if doctor_names
            else "not_verified"
        ),
        "phone": "website_or_maps" if phone_numbers else "not_verified",
        "booking": "website" if booking_target or booking_detected else "not_verified",
        "whatsapp": "website" if whatsapp_target else "not_verified",
        "instagram": (
            str(instagram_profile.get("source") or "").strip()
            if instagram_profile
            else "website_instagram_link"
            if social_profiles.get("instagram") or lead_data.get("instagram")
            else "website_social_presence"
            if social_profiles.get("instagram_present")
            else "not_verified"
        ),
        "youtube": (
            str(youtube_channel.get("source") or "").strip()
            if youtube_channel
            else "website_youtube_link"
            if social_profiles.get("youtube")
            else "website_social_presence"
            if social_profiles.get("youtube_present")
            else "not_verified"
        ),
    }
    instagram_present = bool(
        proof_extraction.get("instagram_present")
        or instagram_profile
        or social_profiles.get("instagram")
        or social_profiles.get("instagram_present")
        or lead_data.get("instagram")
    )
    youtube_present = bool(
        proof_extraction.get("youtube_present")
        or youtube_channel
        or social_profiles.get("youtube")
        or social_profiles.get("youtube_present")
    )
    testimonials_present = bool(proof_extraction.get("testimonials_present"))
    gallery_present = bool(proof_extraction.get("gallery_present"))
    after_hours_capture = bool(proof_extraction.get("after_hours_capture"))
    raw_booking_flow_quality = str(proof_extraction.get("booking_flow_quality") or "").strip().lower()
    if booking_detected and raw_booking_flow_quality in {"", "none", "unknown", "n/a"}:
        booking_flow_quality = "basic" if contact_form_detected else "weak"
    elif raw_booking_flow_quality in {"strong", "basic", "weak", "none"}:
        booking_flow_quality = raw_booking_flow_quality
    else:
        booking_flow_quality = (
            "basic" if booking_detected and contact_form_detected else "weak" if booking_detected else "none"
        )
    instant_response_path = bool(
        proof_extraction.get("instant_response_path")
        or whatsapp_detected
        or chat_widget_type in {"whatsapp", "intercom", "drift", "livechat", "crisp", "tawk", "tawk.to", "zendesk"}
        or (booking_detected and contact_form_detected and booking_flow_quality == "strong")
    )
    content_ready_score = proof_extraction.get("content_ready_score")

    email_contacts = _dedupe_strings(
        list(lead_data.get("emails_found") or [])
        + list(enrichment_payload.get("validated_emails") or [])
        + list(people_intelligence.get("emails") or [])
        + [
            email
            for candidate in decision_maker_candidates
            if isinstance(candidate, dict)
            for email in list(candidate.get("emails") or [])
        ]
        + (
            [stored_signal_facts.get("best_contact_email")]
            if allow_stored_signal_fallback and stored_signal_facts.get("best_contact_email")
            else []
        )
    )
    email_contacts = [email for email in email_contacts if not _is_junk_contact_email(email)]
    ranked_candidate = next(
        (
            candidate
            for candidate in decision_maker_candidates
            if isinstance(candidate, dict) and candidate.get("name")
        ),
        {},
    )
    decision_maker_name = (
        enrichment_payload.get("decision_maker_name")
        or people_intelligence.get("decision_maker_name")
        or ranked_candidate.get("name")
        or (
            None
            if (has_fresh_decision_maker_evidence or not allow_stored_signal_fallback)
            else stored_signal_facts.get("decision_maker_name")
        )
    )
    decision_maker_linkedin = (
        enrichment_payload.get("decision_maker_linkedin")
        or people_intelligence.get("decision_maker_linkedin")
        or people_intelligence.get("best_contact_linkedin")
        or ranked_candidate.get("linkedin")
        or (
            None
            if (has_fresh_decision_maker_evidence or not allow_stored_signal_fallback)
            else stored_signal_facts.get("decision_maker_linkedin")
        )
    )
    decision_maker_role = (
        enrichment_payload.get("decision_maker_role")
        or people_intelligence.get("decision_maker_role")
        or ranked_candidate.get("role")
        or (
            None
            if (has_fresh_decision_maker_evidence or not allow_stored_signal_fallback)
            else stored_signal_facts.get("decision_maker_role")
        )
    )
    decision_maker_source = (
        enrichment_payload.get("decision_maker_source")
        or ranked_candidate.get("source")
        or (
            None
            if (has_fresh_decision_maker_evidence or not allow_stored_signal_fallback)
            else stored_signal_facts.get("decision_maker_source")
        )
    )
    decision_maker_confidence = (
        enrichment_payload.get("decision_maker_confidence")
        or (min(float(ranked_candidate.get("score", 0)) / 100.0, 0.98) if ranked_candidate else None)
        or (
            None
            if (has_fresh_decision_maker_evidence or not allow_stored_signal_fallback)
            else stored_signal_facts.get("decision_maker_confidence")
        )
    )
    if decision_maker_name and not _is_plausible_person_name(str(decision_maker_name)):
        decision_maker_name = None
        decision_maker_role = None
        decision_maker_source = None
        decision_maker_confidence = None
    best_contact_phone = (
        people_intelligence.get("best_contact_phone")
        or (phone_numbers[0] if phone_numbers else None)
        or (
            None
            if (people_intelligence.get("best_contact_phone") or phone_numbers or not allow_stored_signal_fallback)
            else stored_signal_facts.get("best_contact_phone")
        )
    )
    best_contact_phone = _normalize_contact_phone(best_contact_phone)
    best_contact_email = (
        people_intelligence.get("best_contact_email")
        or _pick_best_email(
            email_contacts,
            lead_data.get("website") or lead_data.get("landing_page_url"),
        )
        or (
            None
            if (people_intelligence.get("best_contact_email") or email_contacts or not allow_stored_signal_fallback)
            else stored_signal_facts.get("best_contact_email")
        )
    )
    if _is_junk_contact_email(best_contact_email):
        best_contact_email = None
    best_contact_linkedin = (
        people_intelligence.get("best_contact_linkedin")
        or ranked_candidate.get("linkedin")
        or decision_maker_linkedin
        or (
            None
            if (
                people_intelligence.get("best_contact_linkedin")
                or ranked_candidate.get("linkedin")
                or decision_maker_linkedin
                or not allow_stored_signal_fallback
            )
            else stored_signal_facts.get("best_contact_linkedin")
        )
    )
    decision_maker_evidence_level = _confidence_to_evidence_level(decision_maker_confidence)
    decision_maker_status = "unverified"
    decision_maker_candidate_name = None
    if decision_maker_name and decision_maker_evidence_level == "verified":
        decision_maker_status = "verified"
    elif decision_maker_name:
        decision_maker_candidate_name = str(decision_maker_name)
        decision_maker_name = None
        decision_maker_linkedin = None
        decision_maker_role = None
        decision_maker_source = None
        decision_maker_status = "candidate"

    recommended_channel, best_contact_reason = _derive_best_contact_channel(
        phone_numbers=phone_numbers,
        best_contact_email=best_contact_email,
        whatsapp_detected=whatsapp_detected,
        whatsapp_target=str(whatsapp_target) if whatsapp_target else None,
        decision_maker_linkedin=str(best_contact_linkedin or decision_maker_linkedin) if (best_contact_linkedin or decision_maker_linkedin) else None,
    )
    if not recommended_channel:
        recommended_channel = stored_signal_facts.get("best_contact_channel") if allow_stored_signal_fallback else None
    if not best_contact_reason:
        best_contact_reason = stored_signal_facts.get("best_contact_reason") if allow_stored_signal_fallback else None

    confidence_by_signal = {
        "phone": 1.0 if phone_numbers else 0.0,
        "booking": 0.95 if booking_target else 0.7 if booking_detected else 0.0,
        "contact_form": 0.8 if contact_form_detected else 0.0,
        "whatsapp": 0.95 if whatsapp_target else 0.35 if whatsapp_widget_detected else 0.0,
        "ads": 1.0 if ads_status in {"yes", "no"} else 0.25,
        "reviews": 0.95 if reviews_count is not None else 0.0,
        "rating": 0.95 if rating is not None else 0.0,
        "services": 0.8 if services else 0.0,
        "multi_clinic": 0.98 if branch_contact_names else 0.91 if corroborated_fresh_branch_names else 0.82 if sanitized_fresh_branch_names else 0.74 if maps_branch_names else 0.0,
        "doctors": 0.95 if doctor_profiles else 0.82 if doctor_names else 0.0,
        "social": 0.75 if social_profiles else 0.0,
        "decision_maker": float(decision_maker_confidence) if decision_maker_confidence is not None else 0.0,
    }
    capture_path_kind = _classify_capture_path(
        {
            "whatsapp_target": whatsapp_target,
            "chat_widget_type": chat_widget_type,
            "instant_response_path": instant_response_path,
            "booking_detected": booking_detected,
            "contact_form_detected": contact_form_detected,
        }
    )
    after_hours_status = _classify_after_hours_capture(
        {
            "after_hours_capture": after_hours_capture,
            "whatsapp_target": whatsapp_target,
            "chat_widget_type": chat_widget_type,
            "booking_detected": booking_detected,
            "contact_form_detected": contact_form_detected,
        }
    )
    evidence_levels = {
        "phone": _confidence_to_evidence_level(confidence_by_signal["phone"]),
        "booking": _confidence_to_evidence_level(confidence_by_signal["booking"]),
        "contact_form": _confidence_to_evidence_level(confidence_by_signal["contact_form"]),
        "whatsapp": _confidence_to_evidence_level(confidence_by_signal["whatsapp"]),
        "multi_clinic": _confidence_to_evidence_level(confidence_by_signal["multi_clinic"]),
        "locations": _confidence_to_evidence_level(confidence_by_signal["multi_clinic"]),
        "doctors": _confidence_to_evidence_level(confidence_by_signal["doctors"]),
        "reviews": _confidence_to_evidence_level(confidence_by_signal["reviews"]),
        "rating": _confidence_to_evidence_level(confidence_by_signal["rating"]),
        "instagram": "verified" if instagram_profile else "confirmed" if social_profiles.get("instagram") or lead_data.get("instagram") else "unknown",
        "youtube": "verified" if youtube_channel else "confirmed" if social_profiles.get("youtube") else "unknown",
        "decision_maker": decision_maker_evidence_level,
        "instant_response": "verified" if capture_path_kind == "instant" else "derived" if capture_path_kind == "delayed" else "unknown",
        "after_hours_capture": "verified" if after_hours_status == "verified" else "derived" if after_hours_status == "likely" else "unknown",
    }

    _signal_facts_payload = {
        "phone_visible": phone_visible,
        "phone_numbers": phone_numbers,
        "booking_detected": booking_detected,
        "booking_target": str(booking_target) if booking_target else None,
        "contact_form_detected": contact_form_detected,
        "whatsapp_detected": whatsapp_detected,
        "whatsapp_widget_detected": whatsapp_widget_detected,
        "whatsapp_target": str(whatsapp_target) if whatsapp_target else None,
        "chat_widget_type": str(chat_widget_type) if chat_widget_type else None,
        "ads_status": ads_status,
        "ads_channels": ads_channels,
        "ads_last_seen": str(ads_last_seen) if ads_last_seen else None,
        "ads_active_count": int(ads_active_count) if isinstance(ads_active_count, (int, float)) else None,
        "ads_creative_hints": ads_creative_hints,
        "ads_page_names": ads_page_names,
        "paid_acquisition_active": ads_status == "yes",
        "reviews_count": reviews_count,
        "rating": rating,
        "fact_sources": fact_sources,
        "maps_place_id": raw_apify_data.get("placeId") if has_verified_maps_truth else None,
        "maps_match_score": raw_apify_data.get("maps_match_score") if has_verified_maps_truth else None,
        "maps_refreshed_at": raw_apify_data.get("maps_refreshed_at") if has_verified_maps_truth else None,
        "volume_score_inputs": {
            "volume_score": intent_payload.get("volume_score"),
            "peak_busyness": enrichment_payload.get("peak_busyness"),
            "avg_busyness": enrichment_payload.get("avg_busyness"),
            "busy_hours_count": enrichment_payload.get("busy_hours_count"),
            "avg_visit_duration_min": enrichment_payload.get("avg_visit_duration_min"),
        },
        "services": services,
        "social_profiles": social_profiles,
        "multi_clinic": multi_clinic,
        "branch_count": branch_count,
        "branch_names": branch_names,
        "maps_branch_names": maps_branch_names,
        "doctor_count": doctor_count,
        "doctor_names": doctor_names,
        "doctor_profiles": doctor_profiles,
        "instagram_present": instagram_present,
        "instagram_profile": instagram_profile,
        "youtube_present": youtube_present,
        "youtube_channel": youtube_channel,
        "testimonials_present": testimonials_present,
        "gallery_present": gallery_present,
        "content_ready_score": content_ready_score,
        "booking_flow_quality": booking_flow_quality,
        "after_hours_capture": after_hours_capture,
        "instant_response_path": instant_response_path,
        "confidence_by_signal": confidence_by_signal,
        "evidence_levels": evidence_levels,
        "capture_path_kind": capture_path_kind,
        "after_hours_capture_status": after_hours_status,
        "decision_maker_name": str(decision_maker_name) if decision_maker_name else None,
        "decision_maker_status": decision_maker_status,
        "decision_maker_candidate_name": decision_maker_candidate_name,
        "decision_maker_linkedin": str(decision_maker_linkedin) if decision_maker_linkedin else None,
        "decision_maker_role": str(decision_maker_role) if decision_maker_role else None,
        "decision_maker_source": str(decision_maker_source) if decision_maker_source else None,
        "decision_maker_confidence": float(decision_maker_confidence) if decision_maker_confidence is not None else None,
        "best_contact_phone": str(best_contact_phone) if best_contact_phone else None,
        "best_contact_email": str(best_contact_email) if best_contact_email else None,
        "best_contact_linkedin": str(best_contact_linkedin) if best_contact_linkedin else None,
        "best_contact_channel": recommended_channel,
        "best_contact_reason": str(best_contact_reason) if best_contact_reason else None,
        "decision_maker_candidates": decision_maker_candidates,
        "branch_contacts": branch_contacts,
        "contact_evidence": contact_evidence,
        "contact_intelligence": build_contact_intelligence(
            {
                "business_name": lead_data.get("business_name"),
                "decision_maker_name": decision_maker_name,
                "decision_maker_linkedin": decision_maker_linkedin,
                "decision_maker_role": decision_maker_role,
                "decision_maker_source": decision_maker_source,
                "decision_maker_confidence": decision_maker_confidence,
                "best_contact_phone": best_contact_phone,
                "best_contact_email": best_contact_email,
                "best_contact_linkedin": best_contact_linkedin,
                "best_contact_channel": recommended_channel,
                "best_contact_reason": best_contact_reason,
                "decision_maker_candidates": decision_maker_candidates,
                "branch_contacts": branch_contacts,
                "doctor_profiles": doctor_profiles,
                "contact_evidence": contact_evidence,
                "contact_quality_score": enrichment_payload.get("contact_quality_score"),
            }
        ),
        "recommended_channel": recommended_channel,
        "recommended_message_type": "consultative_outreach" if recommended_channel else None,
        "draft_template_key": "clinic_conversion_audit",
        "requires_operator_approval": True,
        "top_issue": build_top_issue_from_signal_facts({
            "phone_visible": phone_visible,
            "whatsapp_detected": whatsapp_detected,
            "booking_detected": booking_detected,
            "booking_flow_quality": booking_flow_quality,
            "contact_form_detected": contact_form_detected,
            "after_hours_capture": after_hours_capture,
            "instant_response_path": instant_response_path,
            "reviews_count": reviews_count,
            "rating": rating,
            "content_ready_score": content_ready_score,
            "branch_count": branch_count,
        }),
        "next_best_action": build_next_best_action_from_signal_facts({
            "phone_visible": phone_visible,
            "whatsapp_detected": whatsapp_detected,
            "booking_detected": booking_detected,
            "booking_flow_quality": booking_flow_quality,
            "contact_form_detected": contact_form_detected,
            "after_hours_capture": after_hours_capture,
            "instant_response_path": instant_response_path,
            "reviews_count": reviews_count,
            "rating": rating,
            "content_ready_score": content_ready_score,
            "branch_count": branch_count,
        }),
        "scoring_context": {
            "final_score": (scoring or {}).get("final_score"),
            "lead_tier": (scoring or {}).get("lead_tier"),
            "contact_quality_score": enrichment_payload.get("contact_quality_score"),
        },
    }
    # Canonical truth state for the inspector - derived from the same payload we just built.
    _ts = _derive_truth_state(_signal_facts_payload)
    _signal_facts_payload["truth_state"] = _ts
    _signal_facts_payload["truth_state_label"] = _truth_state_label(_ts)
    _signal_facts_payload["commercial_truth_coverage"] = _commercial_truth_coverage(_signal_facts_payload)
    return _signal_facts_payload


def _confidence_to_evidence_level(confidence: Any) -> str:
    try:
        value = float(confidence)
    except (TypeError, ValueError):
        return "unknown"

    if value >= 0.85:
        return "verified"
    if value >= 0.55:
        return "derived"
    if value > 0:
        return "inferred"
    return "unknown"


def _get_signal_confidence(signal_facts: Optional[Dict[str, Any]], key: str) -> float:
    confidence_map = (signal_facts or {}).get("confidence_by_signal") or {}
    try:
        return float(confidence_map.get(key) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _classify_capture_path(signal_facts: Optional[Dict[str, Any]]) -> str:
    if not signal_facts:
        return "unknown"
    if signal_facts.get("whatsapp_target") or signal_facts.get("chat_widget_type") or signal_facts.get("instant_response_path"):
        return "instant"
    if signal_facts.get("booking_detected") or signal_facts.get("contact_form_detected"):
        return "delayed"
    return "missing"


def _classify_after_hours_capture(signal_facts: Optional[Dict[str, Any]]) -> str:
    if not signal_facts:
        return "unknown"
    if signal_facts.get("after_hours_capture"):
        return "verified"
    if signal_facts.get("whatsapp_target") or signal_facts.get("chat_widget_type"):
        return "likely"
    if signal_facts.get("booking_detected") or signal_facts.get("contact_form_detected"):
        return "not_proven"
    return "missing"


def _count_fact(label_singular: str, label_plural: str, count: Any, confidence: float) -> Optional[str]:
    try:
        value = int(count or 0)
    except (TypeError, ValueError):
        return None

    if value <= 0:
        return None
    if confidence >= 0.85:
        noun = label_singular if value == 1 else label_plural
        return f"{value} {noun} detected"
    if value > 1:
        return f"multiple {label_plural} referenced"
    return f"{label_singular} referenced"


def _has_meaningful_verified_social(signal_facts: Optional[Dict[str, Any]]) -> bool:
    signal_facts = signal_facts or {}
    instagram_profile = signal_facts.get("instagram_profile") or {}
    youtube_channel = signal_facts.get("youtube_channel") or {}
    if instagram_profile.get("followers_count") is not None or instagram_profile.get("posts_count") is not None:
        return True
    if youtube_channel.get("subscriber_count") is not None or youtube_channel.get("total_videos") is not None:
        return True
    return False


def _commercial_truth_coverage(signal_facts: Optional[Dict[str, Any]]) -> int:
    signal_facts = signal_facts or {}
    coverage = 0
    if _coerce_int(signal_facts.get("reviews_count")) is not None:
        coverage += 1
    if _coerce_float(signal_facts.get("rating")) is not None:
        coverage += 1
    if _coerce_int(signal_facts.get("branch_count")):
        coverage += 1
    if _coerce_int(signal_facts.get("doctor_count")):
        coverage += 1
    if _has_meaningful_verified_social(signal_facts):
        coverage += 1
    return coverage


def _has_sparse_commercial_truth(signal_facts: Optional[Dict[str, Any]]) -> bool:
    return _commercial_truth_coverage(signal_facts) <= 1


def _derive_truth_state(signal_facts: Optional[Dict[str, Any]]) -> str:
    """Compute a single canonical verification state for the frontend.

    Hierarchy (strongest first):
      - verified_maps          : live Google Maps truth on this lead
      - cached_maps            : Maps reviews/rating present from cache or sibling hydration
      - website_proof          : strong website-derived facts (doctors / branches / booking / phone)
      - social_presence_only   : only social signals (no Maps, no doctors/branches)
      - incomplete_verification: nothing meaningful surfaced yet
    Frontend should render score/judgment confidently only for verified_maps / cached_maps /
    strong website_proof; for social_presence_only and incomplete_verification it should show
    a 'Needs verification' label instead of a confident commercial judgment.
    """
    facts = signal_facts or {}
    fact_sources = facts.get("fact_sources") or {}
    reviews_source = fact_sources.get("reviews")
    rating_source = fact_sources.get("rating")

    if reviews_source == "google_maps" or rating_source == "google_maps":
        return "verified_maps"
    if reviews_source == "google_maps_cached" or rating_source == "google_maps_cached":
        return "cached_maps"

    has_doctor = bool(facts.get("doctor_count"))
    has_branch = bool(facts.get("branch_count"))
    has_booking = bool(facts.get("booking_detected"))
    has_phone = bool(facts.get("phone_visible"))

    website_strength = sum([has_doctor, has_branch, has_booking, has_phone])
    if website_strength >= 2:
        return "website_proof"

    social_profiles = facts.get("social_profiles") or {}
    has_any_social_url = any(
        isinstance(social_profiles.get(net), list) and len(social_profiles.get(net) or []) > 0
        for net in ("instagram", "youtube", "facebook", "linkedin")
    )
    has_presence_flag = any(
        bool(facts.get(f"{net}_present"))
        for net in ("instagram", "youtube", "facebook")
    )
    if has_any_social_url or has_presence_flag or _has_meaningful_verified_social(facts):
        if website_strength == 0:
            return "social_presence_only"
        return "website_proof"

    return "incomplete_verification"


def _truth_state_label(state: str) -> str:
    return {
        "verified_maps": "Verified",
        "cached_maps": "Cached verification",
        "website_proof": "Website-verified",
        "social_presence_only": "Social presence only",
        "incomplete_verification": "Needs verification",
        "failed": "Verification failed",
    }.get(state, "Needs verification")


def build_site_truth_summary_from_signal_facts(signal_facts: Optional[Dict[str, Any]]) -> Optional[str]:
    if not signal_facts:
        return None

    facts: List[str] = []
    facts.append("phone visible" if signal_facts.get("phone_visible") else "phone not detected")
    facts.append("booking path detected" if signal_facts.get("booking_detected") else "no booking path detected")

    whatsapp_target = signal_facts.get("whatsapp_target")
    whatsapp_widget_detected = bool(signal_facts.get("whatsapp_widget_detected"))
    if whatsapp_target:
        facts.append(f"WhatsApp detected ({whatsapp_target})")
    elif whatsapp_widget_detected:
        facts.append("WhatsApp widget detected; exact target not extracted")
    elif signal_facts.get("whatsapp_detected"):
        facts.append("WhatsApp detected")
    else:
        facts.append("no WhatsApp detected")

    contact_form_detected = signal_facts.get("contact_form_detected")
    if contact_form_detected:
        facts.append("contact form detected")
    after_hours_status = _classify_after_hours_capture(signal_facts)
    if after_hours_status == "verified":
        facts.append("after-hours capture present")
    elif after_hours_status == "likely":
        facts.append("after-hours capture likely")
    elif after_hours_status == "not_proven":
        facts.append("after-hours capture not proven")
    else:
        facts.append("no after-hours capture")

    capture_path = _classify_capture_path(signal_facts)
    if capture_path == "instant":
        facts.append("instant response path detected")
    elif capture_path == "delayed":
        facts.append("delayed capture path detected")
    else:
        facts.append("no instant capture path proven")

    ads_status = signal_facts.get("ads_status")
    if ads_status == "yes":
        channels = ", ".join(signal_facts.get("ads_channels") or [])
        facts.append(f"ads detected{f' on {channels}' if channels else ''}")
    elif ads_status == "no":
        facts.append("ads verified absent")
    elif ads_status == "not_checked":
        facts.append("ads not checked")

    reviews_count = signal_facts.get("reviews_count")
    if isinstance(reviews_count, int):
        facts.append(f"{reviews_count} reviews detected")

    branch_fact = _count_fact(
        "location",
        "locations",
        signal_facts.get("branch_count"),
        _get_signal_confidence(signal_facts, "multi_clinic"),
    )
    if signal_facts.get("multi_clinic") and branch_fact:
        facts.append(branch_fact)

    doctor_fact = _count_fact(
        "doctor",
        "doctors",
        signal_facts.get("doctor_count"),
        _get_signal_confidence(signal_facts, "doctors"),
    )
    if doctor_fact:
        facts.append(doctor_fact)

    return "Site truth: " + ", ".join(facts) + "."


def build_commercial_reason_from_signal_facts(
    signal_facts: Optional[Dict[str, Any]],
    intent: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    if not signal_facts:
        return None

    positives: List[str] = []
    problems: List[str] = []

    reviews_count = signal_facts.get("reviews_count")
    if isinstance(reviews_count, int):
        if reviews_count >= 200:
            positives.append(f"very strong demand ({reviews_count}+ reviews)")
        elif reviews_count >= 50:
            positives.append(f"real market demand ({reviews_count}+ reviews)")

    if signal_facts.get("multi_clinic"):
        branch_fact = _count_fact(
            "location",
            "locations",
            signal_facts.get("branch_count"),
            _get_signal_confidence(signal_facts, "multi_clinic"),
        )
        positives.append(branch_fact or "multi-location footprint")

    doctor_fact = _count_fact(
        "doctor",
        "doctors",
        signal_facts.get("doctor_count"),
        _get_signal_confidence(signal_facts, "doctors"),
    )
    if doctor_fact:
        positives.append(f"visible doctor-led trust ({doctor_fact})")

    content_ready_score = signal_facts.get("content_ready_score")
    sparse_truth = _has_sparse_commercial_truth(signal_facts)
    decision_maker_name = signal_facts.get("decision_maker_name")
    decision_maker_linkedin = signal_facts.get("decision_maker_linkedin")
    decision_maker_role = signal_facts.get("decision_maker_role")
    decision_maker_source = signal_facts.get("decision_maker_source")
    decision_maker_confidence = signal_facts.get("decision_maker_confidence")
    best_contact_phone = signal_facts.get("best_contact_phone")
    best_contact_email = signal_facts.get("best_contact_email")
    best_contact_linkedin = signal_facts.get("best_contact_linkedin")
    best_contact_channel = signal_facts.get("best_contact_channel")
    best_contact_reason = signal_facts.get("best_contact_reason")
    decision_maker_candidates = signal_facts.get("decision_maker_candidates") or []
    doctor_profiles = signal_facts.get("doctor_profiles") or []
    branch_contacts = signal_facts.get("branch_contacts") or []
    contact_evidence = signal_facts.get("contact_evidence") or []
    if isinstance(content_ready_score, int) and content_ready_score >= 50:
        positives.append("content-ready brand")
    contact_intelligence = signal_facts.get("contact_intelligence") or {}
    top_contact = contact_intelligence.get("top_contact") or {}
    top_contact_name = _clean_company_name_candidate(str(top_contact.get("name") or "")).strip() or None
    if top_contact.get("name") and (
        top_contact.get("contact_type") in {"founder_direct", "doctor_direct", "actual_contact"}
        or float(top_contact.get("confidence") or 0) >= 70
    ):
        contact_label = str(top_contact.get("contact_type") or top_contact.get("owner_scope") or "contact").replace("_", " ")
        positives.append(f"{top_contact_name or top_contact.get('name')} ({contact_label})")
    contact_quality_score = signal_facts.get("contact_quality_score")
    if contact_quality_score is not None:
        try:
            positives.append(f"contact quality {int(float(contact_quality_score))}/100")
        except (TypeError, ValueError):
            pass

    if not signal_facts.get("phone_visible"):
        problems.append("phone is not prominent")
    capture_path = _classify_capture_path(signal_facts)
    after_hours_status = _classify_after_hours_capture(signal_facts)

    if not signal_facts.get("whatsapp_detected") and capture_path == "delayed":
        problems.append("no instant messaging capture path")
    elif not signal_facts.get("whatsapp_detected"):
        problems.append("no WhatsApp capture path")
    elif signal_facts.get("whatsapp_widget_detected") and not signal_facts.get("whatsapp_target"):
        problems.append("WhatsApp widget is visible, but the exact target was not extracted")
    booking_quality = str(signal_facts.get("booking_flow_quality") or "none").lower()
    if booking_quality in {"none", "weak"}:
        problems.append("booking path is weak")
    if after_hours_status == "missing":
        problems.append("no after-hours capture")
    elif after_hours_status == "not_proven":
        problems.append("after-hours capture is not proven")
    if capture_path == "missing":
        problems.append("no instant response path")
    elif capture_path == "delayed":
        problems.append("high-intent visitors likely fall into delayed follow-up")

    volume_score = ((signal_facts.get("volume_score_inputs") or {}).get("volume_score"))
    summary_parts: List[str] = []
    if sparse_truth:
        summary_parts.append(
            "Verified demand and trust data is still incomplete, so this is an operator snapshot rather than a final commercial judgment."
        )
    if positives and not sparse_truth:
        summary_parts.append("This clinic looks commercially strong because it has " + ", ".join(positives[:3]) + ".")
    elif positives:
        summary_parts.append("Current positives include " + ", ".join(positives[:3]) + ".")
    if problems:
        summary_parts.append("The main conversion leaks are " + ", ".join(problems[:3]) + ".")
    if isinstance(volume_score, int) and volume_score >= 70:
        summary_parts.append(f"Volume signals are strong ({volume_score}/100).")

    if summary_parts:
        return " ".join(summary_parts)

    prior = str((intent or {}).get("why_this_lead") or "").strip()
    return prior or None


def build_top_issue_from_signal_facts(signal_facts: Optional[Dict[str, Any]]) -> Optional[str]:
    if not signal_facts:
        return None

    if _has_sparse_commercial_truth(signal_facts):
        return "Verified demand and trust data is incomplete"

    reviews = signal_facts.get("reviews_count") or 0
    rating = signal_facts.get("rating") or 0
    content_ready_score = signal_facts.get("content_ready_score") or 0
    branch_count = signal_facts.get("branch_count") or 0
    capture_path = _classify_capture_path(signal_facts)
    after_hours_status = _classify_after_hours_capture(signal_facts)

    if not signal_facts.get("phone_visible"):
        return "Phone is not prominent"
    booking_quality = str(signal_facts.get("booking_flow_quality") or "none").lower()
    if not signal_facts.get("booking_detected") and not signal_facts.get("contact_form_detected"):
        return "No digital capture path detected"
    if signal_facts.get("booking_detected") and booking_quality in {"none", "weak"}:
        return "Booking flow is weak"
    if capture_path == "delayed":
        return "High-intent visitors likely hit delayed follow-up"
    if capture_path == "missing":
        return "No instant conversational capture path"
    if signal_facts.get("whatsapp_widget_detected") and not signal_facts.get("whatsapp_target"):
        return "WhatsApp widget target is not cleanly extracted"
    if not signal_facts.get("whatsapp_detected") and capture_path != "missing":
        return "WhatsApp capture is missing"
    if after_hours_status == "missing":
        return "No after-hours capture"
    if (
        signal_facts.get("contact_form_detected") is False
        and (reviews >= 200 or branch_count > 1 or content_ready_score >= 70)
    ):
        return "No form fallback for high-intent visitors"
    if branch_count > 1:
        return "Multi-branch lead handling can be standardized"
    if reviews >= 500 and rating >= 4.5:
        return "High-demand clinic with conversion follow-up upside"
    return "Conversion follow-up system can be sharpened"


def build_next_best_action_from_signal_facts(signal_facts: Optional[Dict[str, Any]]) -> Optional[str]:
    if not signal_facts:
        return None

    if _has_sparse_commercial_truth(signal_facts):
        return "Refresh Maps truth and enrich doctors, locations, and social demand signals before final judgment"

    reviews = signal_facts.get("reviews_count") or 0
    rating = signal_facts.get("rating") or 0
    content_ready_score = signal_facts.get("content_ready_score") or 0
    branch_count = signal_facts.get("branch_count") or 0
    capture_path = _classify_capture_path(signal_facts)
    after_hours_status = _classify_after_hours_capture(signal_facts)

    if not signal_facts.get("phone_visible"):
        return "Make phone visible in header and hero"
    booking_quality = str(signal_facts.get("booking_flow_quality") or "none").lower()
    if not signal_facts.get("booking_detected") and not signal_facts.get("contact_form_detected"):
        return "Add a digital booking or callback path"
    if signal_facts.get("booking_detected") and booking_quality in {"none", "weak"}:
        return "Fix booking flow and confirmation path"
    if capture_path == "delayed":
        return "Layer instant messaging on top of the existing booking and callback flow"
    if capture_path == "missing":
        return "Add instant response automation"
    if signal_facts.get("whatsapp_widget_detected") and not signal_facts.get("whatsapp_target"):
        return "Clarify the chat widget target and extract the exact WhatsApp entry path"
    if not signal_facts.get("whatsapp_detected") and capture_path != "missing":
        return "Add WhatsApp entry path and autoresponse"
    if after_hours_status == "not_proven":
        return "Verify or add after-hours capture instead of relying on callback delay"
    if (
        signal_facts.get("contact_form_detected") is False
        and (reviews >= 200 or branch_count > 1 or content_ready_score >= 70)
    ):
        return "Add a high-intent fallback form and route it into instant follow-up"
    if branch_count > 1:
        return "Pitch centralized AI lead handling across branches"
    if reviews >= 500 and rating >= 4.5:
        return "Pitch AI follow-up, no-show reduction, and conversion plumbing upgrade"
    return "Pitch AI conversion plumbing upgrade"


INTENT_DATA_ALLOWED_FIELDS = {
    "lead_id",
    "intent_score",
    "leak_score",
    "volume_score",
    "why_this_lead",
    "speed_to_lead_risk",
    "review_evidence",
    "reactivation_fit",
    "created_at",
}


def persist_harmonized_intent(db, intent: Optional[Dict[str, Any]]) -> None:
    """Persist the canonical post-proof intent narrative so future reads stay consistent."""
    if not intent or not intent.get("lead_id"):
        return

    payload = {
        key: value
        for key, value in dict(intent).items()
        if key in INTENT_DATA_ALLOWED_FIELDS
    }
    if not payload.get("lead_id"):
        return
    payload["lead_id"] = str(payload.get("lead_id"))
    payload["created_at"] = payload.get("created_at") or datetime.utcnow().isoformat()
    db.save_intent_data(payload)


def build_frontend_lead(
    lead_data: Dict[str, Any],
    enrichment: Optional[Dict[str, Any]] = None,
    intent: Optional[Dict[str, Any]] = None,
    scoring: Optional[Dict[str, Any]] = None,
    signal_facts: Optional[Dict[str, Any]] = None,
    analysis_state: Optional[str] = None,
    analysis_updated_at: Optional[str] = None,
) -> Dict[str, Any]:
    """Normalize a raw lead row and related agent outputs into the frontend lead shape."""
    created_at = lead_data.get("created_at") or datetime.utcnow().isoformat()
    updated_at = lead_data.get("updated_at") or created_at
    website = lead_data.get("website") or lead_data.get("landing_page_url")
    company_name = str(lead_data.get("business_name") or "").strip() or "Unknown"
    company_name = _clean_company_name_candidate(company_name) or company_name
    if website:
        brand_hint = _domain_brand_hint(str(website)) or infer_company_name_from_url(str(website))
        if _looks_like_seo_brand_noise(company_name) or _is_generic_company_title(
            company_name,
            raw_geo=str(lead_data.get("location") or ""),
            brand_hint=brand_hint,
        ):
            company_name = brand_hint or infer_company_name_from_title(str(website), company_name) or company_name
        elif (
            brand_hint
            and _normalize_brand_token(company_name) == _normalize_brand_token(brand_hint)
            and " " not in company_name
            and " " in brand_hint
        ):
            company_name = brand_hint
    if _looks_like_search_query_name(company_name):
        company_name = (
            _domain_brand_hint(str(website or ""))
            or infer_company_name_from_url(str(website or ""))
            or "Unverified Maps candidate"
        )
    company_name = _clean_company_name_candidate(company_name) or company_name

    return {
        "id": str(lead_data.get("lead_id")),
        "company_name": company_name,
        "business_name": company_name,
        "domain": extract_domain(lead_data.get("website") or lead_data.get("landing_page_url")) or "",
        "website": lead_data.get("website") or None,
        "landing_page_url": lead_data.get("landing_page_url") or None,
        "source_url": lead_data.get("source_url") or lead_data.get("landing_page_url") or lead_data.get("website") or None,
        "url": lead_data.get("landing_page_url") or lead_data.get("website") or None,
        "niche": lead_data.get("category") or "",
        "geo": lead_data.get("location") or "",
        "status": normalize_lead_status(lead_data.get("lead_lifecycle_state")),
        "score": (scoring or {}).get("final_score"),
        "final_score": (scoring or {}).get("final_score"),
        "score_breakdown": (scoring or {}).get("score_breakdown"),
        "analysis_state": analysis_state,
        "analysis_updated_at": analysis_updated_at,
        "signals_version": SIGNALS_VERSION,
        "signal_facts": signal_facts or {},
        "site_truth_summary": (intent or {}).get("site_truth_summary"),
        "why_this_lead": (intent or {}).get("why_this_lead"),
        "contacts": build_contact_rows(lead_data, enrichment),
        "intent_signals": build_intent_signals(intent),
        "enrichment_data": enrichment,
        "created_at": created_at,
        "updated_at": updated_at,
    }


def build_discovery_metadata(
    *,
    verified_fit: Optional[str],
    discovery_source: str,
    preview_score: Optional[float],
    preview_summary: Optional[str],
    contact_paths: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Build explicit preview metadata so the UI can distinguish preview from final lead state."""
    source_label_map = {
        "google_maps": "Google Maps",
        "osint": "OSINT web discovery",
    }
    return {
        "verified_fit": verified_fit,
        "source": discovery_source,
        "source_label": source_label_map.get(discovery_source, discovery_source.replace("_", " ").title()),
        "score_kind": "preview_match",
        "score": preview_score,
        "preview_match_score": preview_score,
        "preview_summary": preview_summary,
        "contact_paths": contact_paths or [],
        "analysis_state": "preview",
        "signals_version": SIGNALS_VERSION,
    }


def attach_preview_metadata(
    lead_payload: Dict[str, Any],
    *,
    verified_fit: Optional[str],
    discovery_source: str,
    preview_score: Optional[float],
    preview_summary: Optional[str],
    contact_paths: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Attach discovery-stage metadata to a frontend lead payload."""
    payload = dict(lead_payload)
    payload.update(
        build_discovery_metadata(
            verified_fit=verified_fit,
            discovery_source=discovery_source,
            preview_score=preview_score,
            preview_summary=preview_summary,
            contact_paths=contact_paths,
        )
    )
    return payload


def attach_final_metadata(
    lead_payload: Dict[str, Any],
    *,
    discovery_source: Optional[str] = None,
    verified_fit: Optional[str] = None,
    preview_score: Optional[float] = None,
    preview_summary: Optional[str] = None,
    contact_paths: Optional[List[str]] = None,
    proof: Optional[Dict[str, Any]] = None,
    analysis_state: Optional[str] = None,
    analysis_updated_at: Optional[str] = None,
    signal_facts: Optional[Dict[str, Any]] = None,
    intent: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Attach final-stage metadata after enrich -> intent -> proof -> score."""
    payload = dict(lead_payload)
    final_score = payload.get("score")
    if final_score is None:
        score_breakdown = payload.get("score_breakdown") or {}
        final_score = score_breakdown.get("total_score")
        if final_score is not None:
            payload["score"] = final_score
    if final_score is not None:
        payload["final_score"] = final_score
    if preview_score is not None:
        payload["preview_match_score"] = preview_score

    if discovery_source:
        payload["source"] = discovery_source
        payload["source_label"] = {
            "google_maps": "Google Maps",
            "osint": "OSINT web discovery",
        }.get(discovery_source, discovery_source.replace("_", " ").title())

    if verified_fit:
        payload["verified_fit"] = verified_fit

    if preview_summary:
        payload["preview_summary"] = preview_summary

    merged_contact_paths = list(contact_paths or [])
    proof_extraction = (proof or {}).get("extraction_data") or {}
    if payload.get("contacts"):
        merged_contact_paths.append("phone")
    if proof_extraction.get("booking_link"):
        merged_contact_paths.append("booking")
    if proof_extraction.get("whatsapp_target"):
        merged_contact_paths.append("whatsapp")

    if contact_paths is not None or proof_extraction:
        deduped_paths: List[str] = []
        seen_paths = set()
        for path in merged_contact_paths:
            if not path or path in seen_paths:
                continue
            seen_paths.add(path)
            deduped_paths.append(path)
        payload["contact_paths"] = deduped_paths

    payload["score_kind"] = "final_score"
    payload["analysis_state"] = analysis_state or payload.get("analysis_state") or "analyzed"
    if analysis_updated_at:
        payload["analysis_updated_at"] = analysis_updated_at
    computed_site_truth_summary = build_site_truth_summary_from_signal_facts(signal_facts)
    computed_why_this_lead = build_commercial_reason_from_signal_facts(signal_facts, intent)

    if signal_facts is not None:
        payload["signal_facts"] = signal_facts
        payload["signals_version"] = SIGNALS_VERSION
    if computed_site_truth_summary is not None:
        payload["site_truth_summary"] = computed_site_truth_summary
    elif intent and intent.get("site_truth_summary") is not None:
        payload["site_truth_summary"] = intent.get("site_truth_summary")
    if computed_why_this_lead is not None:
        payload["why_this_lead"] = computed_why_this_lead
    elif intent and intent.get("why_this_lead") is not None:
        payload["why_this_lead"] = intent.get("why_this_lead")
    if payload.get("status") in {"qualified_preview", "candidate_preview", "discovered"}:
        payload["status"] = "outreach_pending" if payload.get("contacts") else "enriched"
    return payload


def build_analysis_bundle(
    *,
    lead: Optional[Dict[str, Any]] = None,
    signal_facts: Optional[Dict[str, Any]] = None,
    intent: Optional[Dict[str, Any]] = None,
    scoring: Optional[Dict[str, Any]] = None,
    proof: Optional[Dict[str, Any]] = None,
    analysis_state: Optional[str] = None,
    analysis_updated_at: Optional[str] = None,
    preview_match_score: Optional[float] = None,
) -> Dict[str, Any]:
    signal_facts = dict(signal_facts or {})
    intent = dict(intent or {})
    scoring = dict(scoring or {})
    proof = dict(proof or {})
    score_breakdown = dict(scoring.get("score_breakdown") or {})
    site_truth_summary = build_site_truth_summary_from_signal_facts(signal_facts) or intent.get("site_truth_summary")
    commercial_reason = build_commercial_reason_from_signal_facts(signal_facts, intent) or intent.get("why_this_lead")

    reviews = signal_facts.get("reviews_count")
    rating = signal_facts.get("rating")
    ads_status = signal_facts.get("ads_status")
    ads_active_count = signal_facts.get("ads_active_count")
    ads_channels = signal_facts.get("ads_channels") or []
    instagram_profile = signal_facts.get("instagram_profile") or {}
    youtube_channel = signal_facts.get("youtube_channel") or {}
    branch_count = signal_facts.get("branch_count")
    doctor_count = signal_facts.get("doctor_count")
    phone_visible = bool(signal_facts.get("phone_visible"))
    booking_detected = bool(signal_facts.get("booking_detected"))
    whatsapp_detected = bool(signal_facts.get("whatsapp_detected"))
    after_hours_capture = bool(signal_facts.get("after_hours_capture"))
    instant_response_path = bool(signal_facts.get("instant_response_path"))
    content_ready_score = signal_facts.get("content_ready_score")
    decision_maker_name = signal_facts.get("decision_maker_name")
    decision_maker_linkedin = signal_facts.get("decision_maker_linkedin")
    decision_maker_role = signal_facts.get("decision_maker_role")
    decision_maker_source = signal_facts.get("decision_maker_source")
    decision_maker_confidence = signal_facts.get("decision_maker_confidence")
    best_contact_phone = signal_facts.get("best_contact_phone")
    best_contact_email = signal_facts.get("best_contact_email")
    best_contact_linkedin = signal_facts.get("best_contact_linkedin")
    best_contact_channel = signal_facts.get("best_contact_channel")
    best_contact_reason = signal_facts.get("best_contact_reason")
    decision_maker_candidates = signal_facts.get("decision_maker_candidates") or []
    doctor_profiles = signal_facts.get("doctor_profiles") or []
    branch_contacts = signal_facts.get("branch_contacts") or []
    contact_evidence = signal_facts.get("contact_evidence") or []
    contact_intelligence = signal_facts.get("contact_intelligence") or {}
    top_contact = contact_intelligence.get("top_contact") or {}
    top_contact_name = _clean_company_name_candidate(str(top_contact.get("name") or "")).strip() or None
    capture_path_kind = _classify_capture_path(signal_facts)
    after_hours_status = _classify_after_hours_capture(signal_facts)
    decision_maker_status = signal_facts.get("decision_maker_status")
    decision_maker_candidate_name = signal_facts.get("decision_maker_candidate_name")

    trust_markers: List[str] = []
    pain_points: List[str] = []
    if isinstance(reviews, (int, float)) and reviews:
        trust_markers.append(f"{int(reviews)} reviews")
    if isinstance(rating, (int, float)) and rating:
        trust_markers.append(f"{float(rating):.1f} rating")
    if ads_status == "yes":
        if isinstance(ads_active_count, (int, float)) and ads_active_count:
            trust_markers.append(f"{int(ads_active_count)} active Meta ads")
        else:
            trust_markers.append("active Meta ads")
    branch_fact = _count_fact("location", "locations", branch_count, _get_signal_confidence(signal_facts, "multi_clinic"))
    if branch_fact:
        trust_markers.append(branch_fact)
    doctor_fact = _count_fact("doctor", "doctors", doctor_count, _get_signal_confidence(signal_facts, "doctors"))
    if doctor_fact:
        trust_markers.append(doctor_fact)
    if isinstance(content_ready_score, int) and content_ready_score >= 70:
        trust_markers.append("strong content readiness")
    if top_contact.get("name") and (
        top_contact.get("contact_type") in {"founder_direct", "doctor_direct", "actual_contact"}
        or float(top_contact.get("confidence") or 0) >= 70
    ):
        contact_label = str(top_contact.get("contact_type") or top_contact.get("owner_scope") or "contact").replace("_", " ")
        trust_markers.append(f"{top_contact_name or top_contact.get('name')} ({contact_label})")
    contact_quality_score = signal_facts.get("contact_quality_score")
    if contact_quality_score is not None:
        try:
            trust_markers.append(f"contact quality {int(float(contact_quality_score))}/100")
        except (TypeError, ValueError):
            pass
    instagram_followers = instagram_profile.get("followers_count")
    if isinstance(instagram_followers, (int, float)) and instagram_followers:
        trust_markers.append(f"Instagram {int(instagram_followers)} followers")
    youtube_subscribers = youtube_channel.get("subscriber_count")
    if isinstance(youtube_subscribers, (int, float)) and youtube_subscribers:
        trust_markers.append(f"YouTube {int(youtube_subscribers)} subscribers")

    if capture_path_kind == "delayed":
        pain_points.append("delayed follow-up instead of instant capture")
    elif capture_path_kind == "missing":
        pain_points.append("no instant capture path")
    if not booking_detected and not signal_facts.get("contact_form_detected"):
        pain_points.append("weak booking conversion")
    if signal_facts.get("contact_form_detected") is False and (
        (isinstance(reviews, (int, float)) and reviews >= 200)
        or (isinstance(content_ready_score, int) and content_ready_score >= 70)
        or (isinstance(branch_count, int) and branch_count > 1)
    ):
        pain_points.append("no fallback form for high-intent visitors")
    if not phone_visible:
        pain_points.append("phone not prominent")
    if after_hours_status == "missing":
        pain_points.append("after-hours response gap")
    if ads_status == "yes" and capture_path_kind != "instant":
        pain_points.append("paid traffic likely hits delayed follow-up")
    if ads_status == "yes" and not whatsapp_detected:
        pain_points.append("no instant messaging path for paid traffic")

    if ads_status == "yes" and capture_path_kind != "instant":
        recommended_offer = "Paid Traffic Recovery + Instant Follow-up System"
    elif capture_path_kind == "delayed" and not whatsapp_detected:
        recommended_offer = "WhatsApp Lead Recovery + Instant Booking Layer"
    elif not whatsapp_detected:
        recommended_offer = "WhatsApp Lead Recovery + Booking Conversion"
    elif signal_facts.get("contact_form_detected") is False and (
        (isinstance(reviews, (int, float)) and reviews >= 200)
        or (isinstance(content_ready_score, int) and content_ready_score >= 70)
        or (isinstance(branch_count, int) and branch_count > 1)
    ):
        recommended_offer = "Lead Capture Fallback + Instant Follow-up"
    elif isinstance(branch_count, int) and branch_count > 1:
        recommended_offer = "Multi-Branch Lead Handling + Follow-up Automation"
    elif pain_points:
        recommended_offer = "Lead Recovery + Booking Conversion"
    elif trust_markers:
        recommended_offer = "Conversion Optimization + Follow-up Automation"
    else:
        recommended_offer = "Lead Conversion Audit"

    business_name = (lead or {}).get("business_name") or "This clinic"
    trust_summary = ", ".join(trust_markers[:4]) if trust_markers else "limited trust data"
    pain_summary = ", ".join(pain_points[:4]) if pain_points else "conversion optimization opportunity"

    return {
        "version": SIGNALS_VERSION,
        "state": analysis_state or "preview",
        "updated_at": analysis_updated_at,
        "qualification": {
            "final_score": scoring.get("final_score"),
            "lead_tier": scoring.get("lead_tier"),
            "do_not_contact": scoring.get("do_not_contact"),
            "do_not_contact_reason": scoring.get("do_not_contact_reason"),
        },
        "facts": signal_facts,
        "scores": {
            "preview_match_score": preview_match_score,
            "final_score": scoring.get("final_score"),
            "lead_tier": scoring.get("lead_tier"),
            "demand_score": score_breakdown.get("demand_score"),
            "trust_score": score_breakdown.get("trust_score"),
            "leak_score": score_breakdown.get("leak_score"),
            "serviceability_score": score_breakdown.get("serviceability_score"),
            "offer_fit_score": score_breakdown.get("offer_fit_score"),
            "total_score": score_breakdown.get("total_score") or scoring.get("final_score"),
        },
        "guidance": {
            "site_truth_summary": site_truth_summary,
            "why_this_lead": commercial_reason,
            "top_issue": signal_facts.get("top_issue"),
            "next_best_action": signal_facts.get("next_best_action"),
            "recommended_channel": signal_facts.get("recommended_channel"),
            "recommended_message_type": signal_facts.get("recommended_message_type"),
            "draft_template_key": signal_facts.get("draft_template_key"),
            "requires_operator_approval": signal_facts.get("requires_operator_approval"),
        },
        "evidence": {
            "hero_screenshot_url": proof.get("hero_screenshot_url"),
            "cta_screenshot_url": proof.get("cta_screenshot_url"),
            "proof_mode": (proof.get("extraction_data") or {}).get("proof_mode"),
            "audit_bullets": proof.get("audit_bullets") or [],
        },
        "lead": {
            "id": str((lead or {}).get("lead_id")) if (lead or {}).get("lead_id") else None,
            "business_name": (lead or {}).get("business_name"),
            "website": (lead or {}).get("website") or (lead or {}).get("landing_page_url"),
            "category": (lead or {}).get("category"),
            "location": (lead or {}).get("location"),
        },
        "contact_intelligence": contact_intelligence,
        "agent_context": {
            "business_summary": f"{business_name} looks commercially credible with {trust_summary}.",
            "conversion_summary": f"Primary opportunity: {pain_summary}.",
            "known_pain_points": pain_points,
            "trust_markers": trust_markers,
            "decision_maker_name": decision_maker_name,
            "decision_maker_status": decision_maker_status,
            "decision_maker_candidate_name": decision_maker_candidate_name,
            "decision_maker_linkedin": decision_maker_linkedin,
            "decision_maker_role": decision_maker_role,
            "decision_maker_source": decision_maker_source,
            "decision_maker_confidence": decision_maker_confidence,
            "best_contact_phone": best_contact_phone,
            "best_contact_email": best_contact_email,
            "best_contact_linkedin": best_contact_linkedin,
            "best_contact_channel": best_contact_channel,
            "best_contact_reason": best_contact_reason,
            "decision_maker_candidates": decision_maker_candidates,
            "doctor_profiles": doctor_profiles,
            "branch_contacts": branch_contacts,
            "contact_evidence": contact_evidence,
            "recommended_offer": recommended_offer,
            "recommended_channel": signal_facts.get("recommended_channel"),
            "recommended_next_step": signal_facts.get("next_best_action"),
            "contact_intelligence": contact_intelligence,
            "ads_status": ads_status,
            "ads_active_count": ads_active_count,
            "ads_channels": ads_channels,
            "instagram_profile": instagram_profile,
            "youtube_channel": youtube_channel,
        },
    }


def build_site_truth_summary(
    proof: Optional[Dict[str, Any]],
    signal_facts: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """Turn proof extraction facts into a short operator-facing site truth summary."""
    signal_summary = build_site_truth_summary_from_signal_facts(signal_facts)
    if signal_summary:
        return signal_summary

    extraction = (proof or {}).get("extraction_data") or {}
    if not extraction:
        return None

    facts: List[str] = []
    phone_visible = ["hero", "visible", "above_fold", "below_fold"].count(
        str(extraction.get("phone_visibility") or "")
    ) > 0 or bool(extraction.get("phone_numbers"))
    facts.append("phone visible" if phone_visible else "phone not detected")
    facts.append("booking detected" if extraction.get("booking_link") else "no booking detected")

    chat_widget = extraction.get("chat_widget")
    whatsapp_target = extraction.get("whatsapp_target")
    whatsapp_widget_detected = chat_widget == "whatsapp"
    if whatsapp_target:
        facts.append(f"WhatsApp detected ({whatsapp_target})")
    elif whatsapp_widget_detected:
        facts.append("WhatsApp widget detected; exact target not extracted")
    else:
        facts.append("no WhatsApp detected")

    form_fields = extraction.get("form_field_count")
    if isinstance(form_fields, int) and form_fields > 0:
        facts.append(f"{form_fields} form fields detected")

    return "Site truth: " + ", ".join(facts) + "."


def strip_contradicted_site_claims(
    summary: str,
    proof: Optional[Dict[str, Any]],
) -> str:
    """Remove stale site-fact claims from intent text when proof says otherwise."""
    if not summary:
        return summary

    extraction = (proof or {}).get("extraction_data") or {}
    cleaned = summary

    phone_visible = ["hero", "visible", "above_fold", "below_fold"].count(
        str(extraction.get("phone_visibility") or "")
    ) > 0 or bool(extraction.get("phone_numbers"))
    has_booking = bool(extraction.get("booking_link"))
    has_whatsapp = extraction.get("chat_widget") == "whatsapp" or bool(
        extraction.get("whatsapp_target")
    )
    has_chat = bool(extraction.get("chat_widget"))

    replacements: List[str] = []
    if phone_visible:
        replacements.extend(
            [
                "no visible phone number on landing page",
                "phone visibility not detected",
                "no visible phone number",
            ]
        )
    if has_booking:
        replacements.extend(
            [
                "no online booking system detected",
                "no booking system detected",
                "no booking detected",
            ]
        )
    if has_chat or has_whatsapp:
        replacements.extend(
            [
                "no chat widget for after-hours capture",
                "no chat widget",
                "no chat/whatsapp detected",
                "no whatsapp detected",
            ]
        )

    for phrase in replacements:
        cleaned = re.sub(re.escape(phrase), "", cleaned, flags=re.IGNORECASE)

    cleaned = re.sub(r"\s+,", ",", cleaned)
    cleaned = re.sub(r",\s*,", ", ", cleaned)
    cleaned = re.sub(r"\.\s*\.", ".", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    cleaned = re.sub(r"\s+([,.])", r"\1", cleaned)
    cleaned = re.sub(r",\s*\.", ".", cleaned)
    return cleaned.strip(" ,.")


def harmonize_intent_with_proof(
    intent: Optional[Dict[str, Any]],
    proof: Optional[Dict[str, Any]],
    signal_facts: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Keep commercial reasoning from intent, while exposing site facts separately."""
    intent_payload = dict(intent or {})
    site_truth = build_site_truth_summary(proof, signal_facts)
    if not site_truth:
        return intent_payload

    prior_summary = build_commercial_reason_from_signal_facts(
        signal_facts,
        intent_payload,
    )
    if not prior_summary:
        prior_summary = strip_contradicted_site_claims(
            str(intent_payload.get("why_this_lead") or ""),
            proof,
        )
    if prior_summary:
        intent_payload["why_this_lead"] = prior_summary
    else:
        intent_payload["why_this_lead"] = site_truth
    intent_payload["site_truth_summary"] = site_truth
    return intent_payload


def persist_processed_lead_state(
    db,
    lead_id: str,
    frontend_lead: Dict[str, Any],
    enrichment: Optional[Dict[str, Any]] = None,
    signal_facts: Optional[Dict[str, Any]] = None,
) -> None:
    """Persist the useful end state of a processed lead back into the canonical leads row."""
    updates: Dict[str, Any] = {
        "lead_lifecycle_state": "QUALIFIED"
        if frontend_lead.get("status") in {"qualified", "outreach_pending", "outreach_sent"}
        else "REACTIVATABLE",
    }

    contacts = frontend_lead.get("contacts") or []
    if contacts:
        primary_phone = next((contact.get("phone") for contact in contacts if contact.get("phone")), None)
        if primary_phone:
            updates["phone"] = primary_phone

    validated_emails = (enrichment or {}).get("validated_emails") or []
    if validated_emails:
        updates["emails_found"] = validated_emails

    signal_facts = signal_facts or {}
    reviews_count = _coerce_int(signal_facts.get("reviews_count"))
    rating = _coerce_float(signal_facts.get("rating"))
    if reviews_count is not None:
        updates["reviews_count"] = reviews_count
    if rating is not None:
        updates["rating"] = rating

    instagram_profile = signal_facts.get("instagram_profile") or {}
    instagram_profile_url = instagram_profile.get("profile_url")
    if instagram_profile_url:
        updates["instagram"] = instagram_profile_url

    db.update_lead(UUID(lead_id), updates)


def verify_clinic_ads(
    lead_data: Dict[str, Any],
    lead_state: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Best-effort clinic ad verification with explicit unknown state."""
    existing = dict(((lead_state or {}).get("metadata") or {}).get("ads_verification") or {})
    if existing.get("status") in {"yes", "no"}:
        return existing

    facebook_page = lead_data.get("facebook_page")
    if not facebook_page:
        return {
            "status": "not_checked",
            "channels": [],
            "last_seen": None,
            "evidence_url": None,
            "source": "unavailable",
        }

    try:
        items = get_discovery_agent()._apify.run_facebook_page_ads_scraper(
            [str(facebook_page)],
            count=25,
            country_code="ALL",
        )
        if items:
            first_item = items[0]
            platform_values = _dedupe_strings(
                [
                    platform
                    for item in items
                    if isinstance(item, dict)
                    for platform in (
                        list(item.get("publisherPlatform") or [])
                        + list(item.get("publisherPlatforms") or [])
                    )
                ]
            )
            creative_hints = _dedupe_strings(
                [
                    value
                    for item in items
                    if isinstance(item, dict)
                    for value in [
                        item.get("adCreativeType"),
                        item.get("collationCount"),
                        item.get("snapshot", {}).get("body", {}).get("text")
                        if isinstance(item.get("snapshot"), dict)
                        else None,
                    ]
                    if value
                ]
            )
            page_names = _dedupe_strings(
                [
                    item.get("pageName") or item.get("advertiserName") or item.get("page_name")
                    for item in items
                    if isinstance(item, dict)
                ]
            )
            return {
                "status": "yes",
                "channels": platform_values or ["meta"],
                "last_seen": first_item.get("adSnapshotUrl")
                or first_item.get("startDate")
                or lead_data.get("ad_last_seen"),
                "evidence_url": first_item.get("adSnapshotUrl") or str(facebook_page),
                "source": "facebook_page_ads_scraper",
                "active_ads_count": len(items),
                "page_names": page_names[:3],
                "creative_hints": creative_hints[:5],
            }
        return {
            "status": "no",
            "channels": ["meta"],
            "last_seen": None,
            "evidence_url": str(facebook_page),
            "source": "facebook_page_ads_scraper",
            "active_ads_count": 0,
        }
    except Exception as exc:
        logger.warning("Clinic ads verification failed for %s: %s", lead_data.get("business_name"), exc)
        return {
            "status": "not_checked",
            "channels": [],
            "last_seen": None,
            "evidence_url": str(facebook_page),
            "source": "facebook_page_ads_scraper_failed",
            "active_ads_count": None,
        }


def persist_analysis_snapshot(
    db,
    lead_id: str,
    *,
    analysis_state: str,
    signal_facts: Dict[str, Any],
    analysis_updated_at: Optional[str],
    ads_verification: Optional[Dict[str, Any]] = None,
    analysis_bundle: Optional[Dict[str, Any]] = None,
) -> None:
    """Persist lightweight analysis metadata without introducing a new table."""
    existing_state = db.get_lead_state(UUID(lead_id)) or {}
    metadata = dict(existing_state.get("metadata") or {})
    metadata.update(
        {
            "analysis_state": analysis_state,
            "analysis_updated_at": analysis_updated_at,
            "signals_version": SIGNALS_VERSION,
            "signal_facts": signal_facts,
        }
    )
    if analysis_bundle:
        metadata["analysis_bundle"] = analysis_bundle
        metadata["intelligence"] = analysis_bundle
    if ads_verification:
        metadata["ads_verification"] = ads_verification

    db.save_lead_state(
        {
            "lead_id": lead_id,
            "current_stage": existing_state.get("current_stage") or "analysis",
            "last_node": existing_state.get("last_node") or "analysis",
            "last_error": existing_state.get("last_error"),
            "retry_count": existing_state.get("retry_count", 0),
            "next_run_at": existing_state.get("next_run_at"),
            "locks": existing_state.get("locks") or [],
            "metadata": metadata,
        }
    )


def get_processed_details_for_lead(db, lead_id: str) -> Dict[str, Any]:
    """Collect the latest processed bundle for a lead detail view."""
    lead_uuid = UUID(lead_id)
    lead_data = db.get_lead(lead_uuid) or {}
    lead_state = db.get_lead_state(lead_uuid) or {}
    intent = db.get_intent_data(lead_uuid) or {}
    proof = db.get_proof_artifact(lead_uuid) or {}
    scoring = db.get_scoring_result(lead_uuid) or {}
    enrichment = db.get_enrichment_data(lead_uuid) or {}
    outreach_rows = db.get_outreach_for_lead(lead_uuid, limit=10) or []
    lead_state_metadata = dict((lead_state or {}).get("metadata") or {})
    has_persisted_truth = bool(
        lead_state_metadata.get("signal_facts")
        or lead_state_metadata.get("analysis_bundle")
        or lead_state_metadata.get("intelligence")
    )
    has_analysis_inputs = bool(enrichment) or bool(intent) or bool(proof) or bool(scoring) or has_persisted_truth

    def _score_breakdown_is_zero(payload: Dict[str, Any]) -> bool:
        breakdown = (payload or {}).get("score_breakdown") or {}
        if not breakdown:
            return True
        numeric_values = [
            value for value in breakdown.values() if isinstance(value, (int, float))
        ]
        if not numeric_values:
            return True
        return all(value == 0 for value in numeric_values)

    def _needs_scoring_refresh() -> bool:
        has_upstream_signal = bool(intent) or bool(enrichment) or bool(proof)
        if not scoring:
            return has_upstream_signal

        scoring_dt = _parse_iso_datetime(scoring.get("created_at"))
        upstream_times = [
            dt
            for dt in [
                _parse_iso_datetime(intent.get("created_at")),
                _parse_iso_datetime(enrichment.get("created_at")),
                _parse_iso_datetime((proof or {}).get("generated_at")),
            ]
            if dt is not None
        ]

        if scoring_dt and upstream_times and scoring_dt < max(upstream_times):
            return True

        if has_upstream_signal and (
            scoring.get("final_score") in {None, 0}
            and _score_breakdown_is_zero(scoring)
        ):
            return True

        return False

    if _needs_scoring_refresh():
        if lead_data:
            refreshed_state = build_graph_state(
                db,
                lead_data,
                current_stage="scoring",
                last_node="audit",
            )
            refreshed_state = get_scoring_agent()(refreshed_state)
            scoring = refreshed_state.get("scoring") or scoring

    signal_facts = (
        build_signal_facts(
            lead_data,
            enrichment=enrichment,
            intent=intent,
            proof=proof,
            scoring=scoring,
            lead_state=lead_state,
        )
        if has_analysis_inputs
        else {}
    )
    if has_analysis_inputs and (intent or proof or scoring or has_persisted_truth):
        intent = harmonize_intent_with_proof(intent, proof, signal_facts)
        persist_harmonized_intent(db, intent)

    outreach = [
        {
            "outreach_id": item.get("outreach_id"),
            "lead_id": item.get("lead_id"),
            "channel": item.get("channel"),
            "variant": item.get("variant"),
            "subject": item.get("subject"),
            "body": item.get("body"),
            "attachments": item.get("attachments") or [],
            "personalization": item.get("personalization") or {},
            "status": item.get("status"),
            "requires_approval": item.get("requires_approval"),
        }
        for item in outreach_rows
    ]

    analysis_state = derive_analysis_state(
        enrichment=enrichment,
        intent=intent,
        proof=proof,
        scoring=scoring,
        outreach=outreach,
        lead_state=lead_state,
    )
    analysis_updated_at = derive_analysis_updated_at(
        enrichment,
        intent,
        proof,
        scoring,
        outreach,
        lead_state,
    )
    preview_match_score = (((lead_state or {}).get("metadata") or {}).get("preview_match_score"))
    analysis_bundle = build_analysis_bundle(
        lead=lead_data,
        signal_facts=signal_facts,
        intent=intent,
        scoring=scoring,
        proof=proof,
        analysis_state=analysis_state,
        analysis_updated_at=analysis_updated_at,
        preview_match_score=preview_match_score,
    )

    return {
        "enrichment": enrichment,
        "intent": intent,
        "proof": proof,
        "scoring": scoring,
        "outreach": outreach,
        "signal_facts": signal_facts,
        "analysis_state": analysis_state,
        "analysis_updated_at": analysis_updated_at,
        "signals_version": SIGNALS_VERSION,
        "analysis_bundle": analysis_bundle,
    }


def _normalize_contact_phone(value: Any) -> Optional[str]:
    digits = re.sub(r"\D", "", str(value or ""))
    if len(digits) < 7:
        return None
    core = digits[-10:]
    if len(set(core)) == 1:
        return None
    if core in {"0123456789", "1234567890", "0987654321", "9876543210"}:
        return None
    if core.endswith("123456789") or core.endswith("987654321"):
        return None
    if len(digits) > 10:
        return core
    return digits


def _tokenize_contact_name(value: Any) -> List[str]:
    tokens = re.findall(r"[a-z0-9]+", str(value or "").lower())
    return [token for token in tokens if len(token) > 1]


def _phone_match_score(contact_phone: Optional[str], candidates: List[str]) -> tuple[float, Optional[str]]:
    normalized_input = _normalize_contact_phone(contact_phone)
    if not normalized_input:
        return 0.0, None

    best_score = 0.0
    best_match = None
    for candidate in candidates:
        normalized_candidate = _normalize_contact_phone(candidate)
        if not normalized_candidate:
            continue
        if normalized_candidate == normalized_input:
            return 1.0, candidate
        if normalized_candidate.endswith(normalized_input) or normalized_input.endswith(normalized_candidate):
            if 0.96 > best_score:
                best_score = 0.96
                best_match = candidate
            continue
        if len(normalized_input) >= 8 and len(normalized_candidate) >= 8:
            if normalized_candidate[-8:] == normalized_input[-8:] and 0.82 > best_score:
                best_score = 0.82
                best_match = candidate
    return best_score, best_match


def _name_match_score(contact_name: Optional[str], candidates: List[str]) -> tuple[float, Optional[str]]:
    normalized_input = str(contact_name or "").strip()
    input_tokens = set(_tokenize_contact_name(contact_name))
    if not normalized_input and not input_tokens:
        return 0.0, None

    best_score = 0.0
    best_match = None
    for candidate in candidates:
        normalized_candidate = str(candidate or "").strip()
        if not normalized_candidate:
            continue
        candidate_tokens = set(_tokenize_contact_name(normalized_candidate))
        token_score = 0.0
        if input_tokens and candidate_tokens:
            overlap = len(input_tokens & candidate_tokens)
            token_score = overlap / max(len(input_tokens), len(candidate_tokens))
        sequence_score = SequenceMatcher(
            None,
            normalized_input.lower(),
            normalized_candidate.lower(),
        ).ratio()
        score = max(token_score, sequence_score)
        if score > best_score:
            best_score = score
            best_match = normalized_candidate
    return best_score, best_match


def _collect_signal_contact_values(
    lead_data: Dict[str, Any],
    signal_facts: Dict[str, Any],
) -> tuple[List[str], List[str]]:
    phones = _dedupe_strings(
        [
            lead_data.get("phone"),
            signal_facts.get("best_contact_phone"),
            *(signal_facts.get("phone_numbers") or []),
            *[
                candidate.get("phone")
                for candidate in (signal_facts.get("decision_maker_candidates") or [])
            ],
            *[
                phone
                for candidate in (signal_facts.get("decision_maker_candidates") or [])
                for phone in (candidate.get("phones") or [])
            ],
            *[
                branch.get("phone")
                for branch in (signal_facts.get("branch_contacts") or [])
            ],
            *[
                phone
                for doctor in (signal_facts.get("doctor_profiles") or [])
                for phone in (doctor.get("phones") or [])
            ],
        ]
    )

    names = _dedupe_strings(
        [
            lead_data.get("business_name"),
            signal_facts.get("decision_maker_name"),
            *(signal_facts.get("doctor_names") or []),
            *[
                candidate.get("name")
                for candidate in (signal_facts.get("decision_maker_candidates") or [])
            ],
            *[
                doctor.get("name")
                for doctor in (signal_facts.get("doctor_profiles") or [])
            ],
        ]
    )

    return phones, names


def resolve_contact_to_lead(
    db,
    *,
    contact_phone: Optional[str],
    contact_name: Optional[str],
    max_candidates: int = 150,
) -> Optional[Dict[str, Any]]:
    leads = db.get_leads(limit=max_candidates)
    best_match: Optional[Dict[str, Any]] = None
    best_score = 0.0

    for lead_data in leads:
        lead_id = lead_data.get("lead_id")
        if not lead_id:
            continue

        lead_uuid = UUID(str(lead_id))
        enrichment = db.get_enrichment_data(lead_uuid) or {}
        intent = db.get_intent_data(lead_uuid) or {}
        proof = db.get_proof_artifact(lead_uuid) or {}
        scoring = db.get_scoring_result(lead_uuid) or {}
        lead_state = db.get_lead_state(lead_uuid) or {}
        signal_facts = build_signal_facts(
            lead_data,
            enrichment=enrichment,
            intent=intent,
            proof=proof,
            scoring=scoring,
            lead_state=lead_state,
        )
        phones, names = _collect_signal_contact_values(lead_data, signal_facts)
        phone_score, matched_phone = _phone_match_score(contact_phone, phones)
        name_score, matched_name = _name_match_score(contact_name, names)

        combined_score = phone_score * 0.78 + name_score * 0.35
        if not contact_phone:
            combined_score = name_score

        if matched_phone:
            combined_score += 0.08
        if matched_name and matched_name.lower() == str(contact_name or "").strip().lower():
            combined_score += 0.04

        if combined_score <= best_score:
            continue

        threshold = 0.68 if contact_phone else 0.72
        if combined_score < threshold:
            continue

        reasons: List[str] = []
        if matched_phone:
            reasons.append(f"Matched phone {matched_phone}")
        if matched_name:
            reasons.append(f"Matched name {matched_name}")
        decision_maker_reference = (
            signal_facts.get("decision_maker_name")
            if signal_facts.get("decision_maker_status") == "verified"
            else signal_facts.get("decision_maker_candidate_name")
        )
        if decision_maker_reference:
            reasons.append(
                f"Likely contact {decision_maker_reference}"
            )

        best_score = combined_score
        best_match = {
            "lead_id": str(lead_id),
            "business_name": lead_data.get("business_name"),
            "confidence": round(min(combined_score, 1.0), 3),
            "reasons": reasons,
            "matched_phone": matched_phone,
            "matched_name": matched_name,
        }

    return best_match


def sync_conversation_message(
    db,
    *,
    lead_id: str,
    role: str,
    message: str,
    channel: Optional[str] = None,
    conversation_id: Optional[str] = None,
) -> Dict[str, Any]:
    lead_uuid = UUID(lead_id)
    existing_conversations = db.get_conversations_for_lead(lead_uuid) or []
    selected_conversation = None

    if conversation_id:
        selected_conversation = next(
            (
                item
                for item in existing_conversations
                if str(item.get("conversation_id")) == str(conversation_id)
            ),
            None,
        )

    if not selected_conversation and existing_conversations:
        selected_conversation = max(
            existing_conversations,
            key=lambda item: item.get("updated_at") or item.get("created_at") or "",
        )

    now_iso = datetime.utcnow().isoformat()
    transcript = list((selected_conversation or {}).get("transcript") or [])
    transcript.append(
        {
            "role": role,
            "message": message,
            "timestamp": now_iso,
        }
    )

    entities = dict((selected_conversation or {}).get("entities") or {})
    channel_history = _dedupe_strings([*(entities.get("channel_history") or []), channel])
    entities["current_channel"] = channel or entities.get("current_channel")
    entities["channel_history"] = channel_history
    if role in {"human", "ai"}:
        entities["current_reply_owner"] = role

    payload = {
        "lead_id": lead_id,
        "transcript": transcript,
        "entities": entities,
        "objection_summary": (selected_conversation or {}).get("objection_summary"),
        "suggested_close_angle": (selected_conversation or {}).get("suggested_close_angle"),
        "escalated": bool((selected_conversation or {}).get("escalated")),
        "escalated_at": (selected_conversation or {}).get("escalated_at"),
    }

    if selected_conversation and selected_conversation.get("conversation_id"):
        updated = db.update_conversation(
            UUID(str(selected_conversation.get("conversation_id"))),
            payload,
        )
        return updated or selected_conversation

    created = db.create_conversation(
        {
            "conversation_id": str(uuid4()),
            **payload,
            "created_at": now_iso,
            "updated_at": now_iso,
        }
    )
    return created


def serialize_lead_for_storage(lead: Lead, raw_niche: str) -> Dict[str, Any]:
    """Convert a discovered Lead model into a DB-ready lead row."""
    return {
        "lead_id": str(lead.lead_id),
        "business_name": lead.business_name,
        "category": lead.category or raw_niche,
        "location": lead.location,
        "geo_tags": lead.geo_tags or [raw_niche],
        "website": lead.website,
        "landing_page_url": lead.landing_page_url or lead.website,
        "phone": lead.phone,
        "emails_found": lead.emails_found or [],
        "facebook_page": lead.facebook_page,
        "instagram": lead.instagram,
        "ads_active": bool(lead.ads_active),
        "ad_start_date": lead.ad_start_date.isoformat() if lead.ad_start_date else None,
        "ad_last_seen": lead.ad_last_seen.isoformat() if lead.ad_last_seen else None,
        "cta_type": lead.cta_type.value if hasattr(lead.cta_type, "value") else lead.cta_type,
        "lead_form_detected": bool(lead.lead_form_detected),
        "lead_lifecycle_state": (
            lead.lead_lifecycle_state.value
            if hasattr(lead.lead_lifecycle_state, "value")
            else str(lead.lead_lifecycle_state or "NEW")
        ),
        "reviews_count": lead.reviews_count,
        "rating": lead.rating,
    }


def get_or_create_discovered_lead(db, lead: Lead, raw_niche: str) -> Dict[str, Any]:
    """Persist a discovered lead or return the existing canonical row."""
    serialized = serialize_lead_for_storage(lead, raw_niche)
    canonical_website = canonicalize_company_website(str(lead.website or "")).strip() or None
    canonical_domain = _normalized_domain(canonical_website or lead.website)

    existing_row: Optional[Dict[str, Any]] = None
    if canonical_website:
        for field in ("website", "landing_page_url"):
            existing_result = (
                db.client.table("leads")
                .select("*")
                .eq(field, canonical_website)
                .limit(1)
                .execute()
            )
            if existing_result.data:
                existing_row = existing_result.data[0]
                break

    if existing_row is None and canonical_domain:
        domain_rows = _fetch_domain_sibling_rows(db, canonical_domain)
        if domain_rows:
            existing_row = max(domain_rows, key=_domain_truth_score)

    if existing_row is None:
        existing_result = (
            db.client.table("leads")
            .select("*")
            .eq("business_name", lead.business_name)
            .eq("location", lead.location or "")
            .limit(1)
            .execute()
        )
        if existing_result.data:
            existing_row = existing_result.data[0]

    if existing_row:
        current_name = str(existing_row.get("business_name") or "").strip()
        current_website = str(existing_row.get("website") or existing_row.get("landing_page_url") or "").strip()
        current_brand_hint = _domain_brand_hint(current_website)
        incoming_brand = _clean_company_name_candidate(
            (_domain_brand_hint(str(canonical_website or lead.website or "")) or "")
            or infer_company_name_from_title(
                str(canonical_website or lead.website or ""),
                str(lead.business_name or ""),
            )
            or infer_company_name_from_url(str(canonical_website or lead.website or ""))
        )

        updates: Dict[str, Any] = {}
        if canonical_website and not current_website:
            updates["website"] = canonical_website
            updates["landing_page_url"] = canonical_website

        if incoming_brand and (
            _looks_like_seo_brand_noise(current_name)
            or _is_generic_company_title(
                current_name,
                raw_geo=str(existing_row.get("location") or lead.location or ""),
                brand_hint=current_brand_hint,
            )
            or _looks_like_search_query_name(current_name)
            or current_name.lower() in GENERIC_BRAND_TITLES
            or (
                current_brand_hint
                and _normalize_brand_token(current_name) == _normalize_brand_token(current_brand_hint)
                and " " not in current_name
                and " " in current_brand_hint
            )
        ):
            updates["business_name"] = incoming_brand

        if lead.phone and not existing_row.get("phone"):
            updates["phone"] = lead.phone
        if lead.location and not existing_row.get("location"):
            updates["location"] = lead.location
        if lead.category and not existing_row.get("category"):
            updates["category"] = lead.category
        if lead.reviews_count is not None and existing_row.get("reviews_count") is None:
            updates["reviews_count"] = lead.reviews_count
        if lead.rating is not None and existing_row.get("rating") is None:
            updates["rating"] = lead.rating
        if lead.emails_found and not existing_row.get("emails_found"):
            updates["emails_found"] = lead.emails_found
        if lead.instagram and not existing_row.get("instagram"):
            updates["instagram"] = lead.instagram
        if lead.facebook_page and not existing_row.get("facebook_page"):
            updates["facebook_page"] = lead.facebook_page

        if updates:
            updated = db.update_lead(UUID(str(existing_row["lead_id"])), updates)
            return _hydrate_lead_truth_from_domain_siblings(db, updated or {**existing_row, **updates})
        return _hydrate_lead_truth_from_domain_siblings(db, existing_row)

    return db.create_lead(serialized)


def run_discovery_followup_pipeline(db, lead_data: Dict[str, Any]) -> Dict[str, Any]:
    """Run enrichment -> intent -> scoring for a discovered lead."""
    state = build_graph_state(
        db,
        lead_data,
        current_stage="enrichment",
        last_node="discovery",
    )

    enrichment_agent = get_enrichment_agent()
    intent_agent = get_intent_agent()
    scoring_agent = get_scoring_agent()

    state = enrichment_agent(state)
    state = intent_agent(state)
    state = scoring_agent(state)

    return {
        "enrichment": state.get("enrichment") or {},
        "intent": state.get("intent") or {},
        "scoring": state.get("scoring") or {},
    }


def run_selected_lead_pipeline(
    db,
    lead_data: Dict[str, Any],
    *,
    include_outreach: bool = True,
    include_audit: bool = True,
    force_refresh: bool = False,
    fast_mode: bool = True,
) -> Dict[str, Any]:
    """Run the heavy operator chain for a selected lead preview."""
    def run_agent_step(
        step_name: str,
        agent_callable,
        current_state: Dict[str, Any],
        *,
        required: bool,
    ) -> Dict[str, Any]:
        timeout_seconds = (
            FAST_ANALYZE_AGENT_TIMEOUTS.get(step_name, 20)
            if fast_mode
            else FULL_ANALYZE_AGENT_TIMEOUTS.get(step_name, 30)
        )
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(agent_callable, current_state)
            try:
                return future.result(timeout=timeout_seconds)
            except FuturesTimeoutError as exc:
                future.cancel()
                message = (
                    f"{step_name} timed out after {timeout_seconds}s for lead "
                    f"{lead_data.get('lead_id')}"
                )
                logger.warning(message)
                if required:
                    raise RuntimeError(message) from exc

                metadata = dict((current_state.get("metadata") or {}))
                warnings = list(metadata.get("analysis_warnings") or [])
                warnings.append(message)
                return {
                    **current_state,
                    "metadata": {
                        **metadata,
                        "analysis_warnings": warnings,
                    },
                    "errors": list(current_state.get("errors") or []) + [message],
                }

    lead_payload = _hydrate_lead_truth_from_domain_siblings(db, dict(lead_data))
    lead_uuid = UUID(str(lead_data.get("lead_id")))
    maps_truth = refresh_google_maps_truth(db, lead_payload, force_refresh=force_refresh)
    refreshed_lead = db.get_lead(lead_uuid) or {}
    if refreshed_lead:
        lead_payload = {**lead_payload, **refreshed_lead}
    lead_state = db.get_lead_state(lead_uuid) or {}
    ads_verification = verify_clinic_ads(lead_payload, lead_state)
    if ads_verification.get("status") == "yes":
        lead_payload["ads_active"] = True
        if ads_verification.get("last_seen"):
            lead_payload["ad_last_seen"] = ads_verification.get("last_seen")
    elif ads_verification.get("status") == "no":
        lead_payload["ads_active"] = False

    state = build_graph_state(
        db,
        lead_payload,
        current_stage="enrichment",
        last_node="discovery",
        metadata={
            "ads_verification": ads_verification,
            "fast_mode": fast_mode,
            "force_audit": include_audit,
            "raw_apify_data": maps_truth or dict((lead_state.get("metadata") or {}).get("raw_apify_data") or {}),
        },
        use_persisted_state=True,
    )

    enrichment_agent = get_enrichment_agent()
    intent_agent = get_intent_agent()
    audit_agent = get_audit_agent()
    scoring_agent = get_scoring_agent()
    outreach_agent = get_outreach_agent()

    has_cached_enrichment = bool(
        state.get("enrichment")
        or state.get("intelligence")
        or state.get("signal_facts")
    )
    state = run_agent_step("enrichment", enrichment_agent, state, required=not has_cached_enrichment)
    state = run_agent_step("intent", intent_agent, state, required=True)
    if include_audit:
        state = run_agent_step("audit", audit_agent, state, required=False)

    signal_facts = build_signal_facts(
        lead_payload,
        enrichment=state.get("enrichment") or {},
        intent=state.get("intent") or {},
        proof=state.get("proof") or {},
        lead_state={"metadata": {"ads_verification": ads_verification}},
        runtime_metadata=state.get("metadata") or {},
    )
    state["metadata"] = {
        **(state.get("metadata") or {}),
        "ads_verification": ads_verification,
        "signal_facts": signal_facts,
    }
    state["intent"] = harmonize_intent_with_proof(
        state.get("intent") or {},
        state.get("proof") or {},
        signal_facts,
    )
    persist_harmonized_intent(db, state.get("intent") or {})
    state = scoring_agent(state)
    signal_facts = build_signal_facts(
        lead_payload,
        enrichment=state.get("enrichment") or {},
        intent=state.get("intent") or {},
        proof=state.get("proof") or {},
        scoring=state.get("scoring") or {},
        lead_state={"metadata": {"ads_verification": ads_verification}},
        runtime_metadata=state.get("metadata") or {},
    )
    state["metadata"] = {
        **(state.get("metadata") or {}),
        "signal_facts": signal_facts,
    }
    analysis_bundle = build_analysis_bundle(
        lead=lead_payload,
        signal_facts=signal_facts,
        intent=state.get("intent") or {},
        scoring=state.get("scoring") or {},
        proof=state.get("proof") or {},
        analysis_state="analyzed",
        analysis_updated_at=derive_analysis_updated_at(
            state.get("enrichment") or {},
            state.get("intent") or {},
            state.get("proof") or {},
            state.get("scoring") or {},
            state.get("outreach_messages") or [],
            {"metadata": {"ads_verification": ads_verification}},
        ),
    )
    state["metadata"] = {
        **(state.get("metadata") or {}),
        "analysis_bundle": analysis_bundle,
    }

    if include_outreach:
        state["metadata"] = {
            **(state.get("metadata") or {}),
            "channel": "email",
            "action": "draft",
            "signal_facts": signal_facts,
            "analysis_bundle": analysis_bundle,
        }
        state = run_agent_step("outreach", outreach_agent, state, required=False)

    return {
        "enrichment": state.get("enrichment") or {},
        "intent": state.get("intent") or {},
        "proof": state.get("proof") or {},
        "scoring": state.get("scoring") or {},
        "outreach": state.get("outreach_messages") or [],
        "ads_verification": ads_verification,
        "signal_facts": signal_facts,
        "analysis_bundle": analysis_bundle,
    }


def build_graph_state(
    db,
    lead_data: Dict[str, Any],
    *,
    current_stage: str,
    last_node: str,
    metadata: Optional[Dict[str, Any]] = None,
    use_persisted_state: bool = True,
) -> Dict[str, Any]:
    """Build a dict-based graph state with persisted related data."""
    lead_id = UUID(str(lead_data.get("lead_id")))
    lead_state = (db.get_lead_state(lead_id) or {}) if use_persisted_state else {}
    enrichment = (db.get_enrichment_data(lead_id) or {}) if use_persisted_state else {}
    intent = (db.get_intent_data(lead_id) or {}) if use_persisted_state else {}
    scoring = (db.get_scoring_result(lead_id) or {}) if use_persisted_state else {}
    proof = (db.get_proof_artifact(lead_id) or {}) if use_persisted_state else {}
    conversations = db.get_conversations_for_lead(lead_id) if use_persisted_state else []
    latest_conversation = None

    if conversations:
        latest_conversation = max(
            conversations,
            key=lambda item: item.get("updated_at") or item.get("created_at") or "",
        )

    graph_metadata = dict((lead_state.get("metadata") or {}))
    graph_metadata.update(dict(metadata or {}))
    if graph_metadata.get("analysis_bundle") and not graph_metadata.get("intelligence"):
        graph_metadata["intelligence"] = graph_metadata.get("analysis_bundle")
    if latest_conversation:
        graph_metadata["conversation_id"] = latest_conversation.get("conversation_id")
        graph_metadata["conversation_status"] = (
            "escalated" if latest_conversation.get("escalated") else "active"
        )

    return LeadGraphState(
        lead_id=lead_id,
        thread_id=str(lead_id),
        lead=dict(lead_data),
        current_stage=current_stage,
        last_node=last_node,
        enrichment=enrichment,
        intent=intent,
        scoring=scoring,
        proof=proof,
        outreach_messages=[],
        conversation_transcript=(latest_conversation or {}).get("transcript") or [],
        conversation_entities=(latest_conversation or {}).get("entities") or {},
        errors=[],
        retry_count=0,
        should_skip_audit=False,
        should_skip_outreach=False,
        is_disqualified=bool(scoring.get("do_not_contact")) if scoring else False,
        is_escalated=bool((latest_conversation or {}).get("escalated")),
        is_complete=False,
        requires_approval=False,
        approval_status=None,
        approval_notes=None,
        metadata=graph_metadata,
        messages=[],
        last_error=None,
    )


def latest_assistant_message(transcript: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Return the latest AI/assistant message from a conversation transcript."""
    for item in reversed(transcript):
        role = (item.get("role") or "").lower()
        if role in {"ai", "assistant"}:
            return item
    return None


def _digits_only(value: Optional[str]) -> str:
    return re.sub(r"\D+", "", str(value or ""))


def _maps_truth_missing(lead_data: Dict[str, Any], lead_state: Optional[Dict[str, Any]]) -> bool:
    metadata = dict((lead_state or {}).get("metadata") or {})
    raw_apify_data = dict(metadata.get("raw_apify_data") or {})
    return not _has_verified_maps_truth(raw_apify_data)


def _has_verified_maps_truth(raw_apify_data: Dict[str, Any]) -> bool:
    """Only treat Maps metrics as truth when they came from a matched place."""
    return bool(
        isinstance(raw_apify_data, dict)
        and raw_apify_data.get("placeId")
        and raw_apify_data.get("maps_source")
        and (
            raw_apify_data.get("reviewsCount") is not None
            or raw_apify_data.get("totalScore") is not None
        )
    )


def _score_google_maps_candidate(lead_data: Dict[str, Any], candidate: Dict[str, Any]) -> float:
    score = 0.0

    lead_domain = extract_domain(lead_data.get("website") or lead_data.get("landing_page_url"))
    candidate_domain = extract_domain(candidate.get("website"))
    if lead_domain and candidate_domain:
        if lead_domain == candidate_domain:
            score += 120
        elif lead_domain in candidate_domain or candidate_domain in lead_domain:
            score += 80

    lead_name = _clean_company_name_candidate(str(lead_data.get("business_name") or "").strip())
    candidate_name = str(candidate.get("title") or candidate.get("name") or "").strip()
    if lead_name and candidate_name:
        score += SequenceMatcher(None, lead_name.lower(), candidate_name.lower()).ratio() * 60

    lead_phone = _digits_only(lead_data.get("phone"))
    candidate_phone = _digits_only(candidate.get("phone"))
    if lead_phone and candidate_phone:
        if lead_phone == candidate_phone:
            score += 40
        elif lead_phone[-8:] and lead_phone[-8:] == candidate_phone[-8:]:
            score += 25

    lead_location = str(lead_data.get("location") or "").lower()
    candidate_location_parts = " ".join(
        [
            str(candidate.get("city") or ""),
            str(candidate.get("state") or ""),
            str(candidate.get("country") or ""),
            str(candidate.get("address") or ""),
        ]
    ).lower()
    if lead_location and candidate_location_parts:
        location_tokens = [token for token in re.findall(r"[a-z]+", lead_location) if len(token) > 2]
        token_overlap = sum(1 for token in location_tokens if token in candidate_location_parts)
        score += min(token_overlap, 3) * 8

    if candidate.get("placeId"):
        score += 2
    if candidate.get("reviewsCount") is not None:
        score += 3
    if candidate.get("totalScore") is not None:
        score += 2

    return score


def _select_best_google_maps_match(
    lead_data: Dict[str, Any],
    candidates: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    if not candidates:
        return None

    scored = [
        (_score_google_maps_candidate(lead_data, candidate), candidate)
        for candidate in candidates
        if isinstance(candidate, dict)
    ]
    scored.sort(key=lambda item: item[0], reverse=True)
    best_score, best_candidate = scored[0]
    if best_score < 45:
        logger.warning(
            "No strong Google Maps match for %s; best score=%s",
            lead_data.get("business_name"),
            round(best_score, 2),
        )
        return None
    return best_candidate


def _select_branch_landing_page(
    lead_data: Dict[str, Any],
    matched: Dict[str, Any],
) -> Optional[str]:
    current_url = str(lead_data.get("landing_page_url") or lead_data.get("website") or "").strip()
    current_domain = (extract_domain(current_url) or "").lower().replace("www.", "")
    location_tokens = [
        token for token in re.findall(r"[a-z]+", str(lead_data.get("location") or "").lower()) if len(token) > 2
    ]

    best_url: Optional[str] = None
    best_score = 0
    for result in list(matched.get("webResults") or []):
        if not isinstance(result, dict):
            continue
        url = str(result.get("url") or "").strip()
        if not url:
            continue
        parsed = urlparse(url if "://" in url else f"https://{url}")
        domain = (parsed.netloc or "").lower().replace("www.", "")
        if current_domain and domain and domain != current_domain:
            continue
        if not parsed.path or parsed.path == "/":
            continue

        haystack = f"{url} {result.get('title') or ''} {result.get('description') or ''}".lower()
        path_depth = len([segment for segment in parsed.path.split("/") if segment])
        score = path_depth * 10
        score += sum(6 for token in location_tokens if token in haystack)
        if any(marker in haystack for marker in ("near-me", "/locations", "/clinics", "clinic-")):
            score += 10
        if current_url and url.rstrip("/") == current_url.rstrip("/"):
            score -= 20
        if score > best_score:
            best_url = url
            best_score = score

    return best_url if best_score >= 16 else None


def _collect_related_google_maps_places(
    lead_data: Dict[str, Any],
    candidates: List[Dict[str, Any]],
    matched: Dict[str, Any],
) -> List[Dict[str, Any]]:
    matched_place_id = str(matched.get("placeId") or "")
    related: List[Tuple[float, Dict[str, Any]]] = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        if str(candidate.get("placeId") or "") == matched_place_id:
            continue
        score = _score_google_maps_candidate(lead_data, candidate)
        if score < 45:
            continue
        related.append(
            (
                score,
                {
                    "title": candidate.get("title") or candidate.get("name"),
                    "url": candidate.get("url"),
                    "address": candidate.get("address"),
                    "website": candidate.get("website"),
                    "phone": candidate.get("phone"),
                    "placeId": candidate.get("placeId"),
                },
            )
        )

    related.sort(key=lambda item: item[0], reverse=True)
    deduped: List[Dict[str, Any]] = []
    seen = set()
    for _, candidate in related:
        key = (
            str(candidate.get("title") or "").lower(),
            str(candidate.get("placeId") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)
    return deduped[:8]


def refresh_google_maps_truth(
    db,
    lead_data: Dict[str, Any],
    *,
    force_refresh: bool = False,
) -> Dict[str, Any]:
    """Refresh Google Maps truth for a lead and persist it for later scoring/enrichment."""
    lead_uuid = UUID(str(lead_data.get("lead_id")))
    lead_state = db.get_lead_state(lead_uuid) or {}
    existing_metadata = dict(lead_state.get("metadata") or {})

    if not force_refresh and not _maps_truth_missing(lead_data, lead_state):
        return existing_metadata.get("raw_apify_data") or {}

    business_name = _clean_company_name_candidate(str(lead_data.get("business_name") or "").strip())
    if not business_name:
        return existing_metadata.get("raw_apify_data") or {}

    geo_filter = build_discovery_geo(str(lead_data.get("location") or ""))
    website = lead_data.get("website") or lead_data.get("landing_page_url")
    brand_hint = _clean_company_name_candidate(infer_company_name_from_url(str(website))) if website else ""
    keywords: List[str] = [business_name]
    if brand_hint and brand_hint.lower() != business_name.lower():
        keywords.append(brand_hint)

    if business_name and business_name != str(lead_data.get("business_name") or "").strip():
        try:
            db.update_lead(lead_uuid, {"business_name": business_name})
        except Exception:
            logger.warning("Failed to persist cleaned business name for %s", lead_data.get("lead_id"))

    try:
        logger.info(
            "Refreshing Google Maps truth for lead_id=%s business=%s geo=%s",
            lead_data.get("lead_id"),
            business_name,
            lead_data.get("location"),
        )
        items = get_discovery_agent()._apify.run_google_maps_scraper(
            keywords=keywords[:2],
            geo=geo_filter,
            limit=6,
            detailed=True,
        )
    except Exception as exc:
        logger.warning("Google Maps truth refresh failed for %s: %s", business_name, exc)
        return existing_metadata.get("raw_apify_data") or {}

    matched = _select_best_google_maps_match(lead_data, items)
    if not matched:
        logger.warning("Google Maps truth refresh found no acceptable match for %s", business_name)
        return existing_metadata.get("raw_apify_data") or {}

    maps_match_score = _score_google_maps_candidate(lead_data, matched)
    related_places = _collect_related_google_maps_places(lead_data, items, matched)
    matched_website = matched.get("website") or website
    matched_title = matched.get("title") or matched.get("name") or business_name
    raw_apify_data = {
        "reviewsCount": matched.get("reviewsCount"),
        "totalScore": matched.get("totalScore") or matched.get("rating"),
        "reviewsDistribution": matched.get("reviewsDistribution"),
        "openingHours": matched.get("openingHours"),
        "reviews": matched.get("reviews", []),
        "questionsAndAnswers": matched.get("questionsAndAnswers"),
        "peopleAlsoSearch": matched.get("peopleAlsoSearch"),
        "imageCategories": matched.get("imageCategories"),
        "webResults": matched.get("webResults"),
        "tableReservationLinks": matched.get("tableReservationLinks"),
        "placeId": matched.get("placeId"),
        "maps_url": matched.get("url"),
        "maps_title": matched_title,
        "maps_address": matched.get("address"),
        "maps_phone": matched.get("phone"),
        "maps_website": matched_website,
        "maps_category": matched.get("categoryName") or matched.get("category"),
        "relatedPlaces": related_places,
        "maps_refreshed_at": datetime.utcnow().isoformat(),
        "maps_source": "apify_google_maps_scraper",
        "maps_match_score": round(maps_match_score, 2),
    }
    branch_landing_page = _select_branch_landing_page(lead_data, matched)
    if branch_landing_page:
        raw_apify_data["branchLandingPage"] = branch_landing_page

    existing_raw_apify_data = dict(existing_metadata.get("raw_apify_data") or {})
    maps_truth_changed = any(
        str(existing_raw_apify_data.get(key) or "").strip() != str(raw_apify_data.get(key) or "").strip()
        for key in ["placeId", "maps_title", "maps_address", "maps_phone", "maps_website", "branchLandingPage"]
    ) or len(existing_raw_apify_data.get("relatedPlaces") or []) != len(raw_apify_data.get("relatedPlaces") or [])
    if maps_truth_changed and any(existing_metadata.get(key) for key in ["analysis_bundle", "signal_facts", "analysis_state"]):
        db.clear_lead_analysis_cache(lead_uuid)
        lead_state = db.get_lead_state(lead_uuid) or {}
        existing_metadata = dict(lead_state.get("metadata") or {})

    metadata = dict(existing_metadata)
    metadata["raw_apify_data"] = raw_apify_data
    db.save_lead_state(
        {
            "lead_id": str(lead_uuid),
            "current_stage": lead_state.get("current_stage") or "analysis",
            "last_node": lead_state.get("last_node") or "analysis",
            "last_error": None,
            "retry_count": lead_state.get("retry_count", 0),
            "next_run_at": lead_state.get("next_run_at"),
            "locks": lead_state.get("locks") or [],
            "metadata": metadata,
        }
    )

    lead_updates: Dict[str, Any] = {}
    current_brand_hint = _domain_brand_hint(str(website)) if website else None
    canonical_maps_name = (
        _domain_brand_hint(str(matched_website or website or ""))
        or infer_company_name_from_title(str(matched_website or website or ""), str(matched_title))
        or infer_company_name_from_url(str(matched_website or website or ""))
        or business_name
    )
    if raw_apify_data.get("reviewsCount") is not None:
        lead_updates["reviews_count"] = raw_apify_data.get("reviewsCount")
    if raw_apify_data.get("totalScore") is not None:
        lead_updates["rating"] = raw_apify_data.get("totalScore")
    if canonical_maps_name and (
        _looks_like_seo_brand_noise(business_name)
        or _is_generic_company_title(
            business_name,
            raw_geo=str(lead_data.get("location") or ""),
            brand_hint=current_brand_hint,
        )
    ):
        lead_updates["business_name"] = canonical_maps_name
    if matched.get("phone") and not lead_data.get("phone"):
        lead_updates["phone"] = matched.get("phone")
    if matched.get("website") and not lead_data.get("website"):
        lead_updates["website"] = matched.get("website")
        lead_updates["landing_page_url"] = matched.get("website")
    if branch_landing_page:
        lead_updates["landing_page_url"] = branch_landing_page
    if lead_updates:
        updated_lead = db.update_lead(lead_uuid, lead_updates)
        lead_data.update(updated_lead or {})
    logger.info(
        "Google Maps truth refreshed for lead_id=%s reviews=%s rating=%s",
        lead_data.get("lead_id"),
        raw_apify_data.get("reviewsCount"),
        raw_apify_data.get("totalScore"),
    )

    return raw_apify_data


def build_discovery_geo(raw_geo: str) -> Dict[str, str]:
    """
    Convert the user-facing geo string into the Google Maps actor filter shape.

    City searches like "Bangalore" should stay city searches. Only short known
    region aliases such as "us" or "in" should be coerced to countries.
    """
    geo_text = (raw_geo or "").strip()
    if not geo_text:
        return {}

    pieces = [piece.strip() for piece in geo_text.split(",") if piece.strip()]
    normalized_last = pieces[-1].lower() if pieces else ""

    if len(pieces) >= 3:
        return {
            "city": pieces[0],
            "state": pieces[1],
            "country": COUNTRY_ALIASES.get(normalized_last, pieces[2]),
        }

    if len(pieces) == 2:
        tail = COUNTRY_ALIASES.get(normalized_last, pieces[1])
        return {
            "city": pieces[0],
            "country": tail,
        }

    token = pieces[0]
    lowered = token.lower()

    if lowered in COUNTRY_ALIASES:
        return {"country": COUNTRY_ALIASES[lowered]}

    return {"city": token}


def build_discovery_keywords(raw_niche: str, requested_limit: int) -> List[str]:
    """
    Expand a niche into a few pragmatic search variants.

    The Google Maps actor performs better with a small set of related search
    strings than with a single niche token. We keep the expansion tight so the
    result set stays relevant and the run remains fast.
    """
    niche = (raw_niche or "").strip()
    if not niche:
        return []

    lowered = niche.lower()
    if "clinic" in lowered and any(
        token in lowered for token in ["aesthetic", "skin", "laser", "hair", "cosmetic", "derma"]
    ):
        candidates = [
            "aesthetic clinic",
            "skin clinic",
            "laser clinic",
            "hair clinic",
            "cosmetic clinic",
            "dermatology clinic",
        ]
    else:
        candidates = [niche]
    candidates.extend(DISCOVERY_KEYWORD_VARIANTS.get(lowered, []))

    if "company" not in lowered and "clinic" not in lowered and "salon" not in lowered:
        candidates.append(f"{niche} company")

    unique_candidates: List[str] = []
    seen = set()
    max_keywords = max(1, min(4, requested_limit))

    for candidate in candidates:
        normalized = candidate.strip().lower()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        unique_candidates.append(candidate.strip())
        if len(unique_candidates) >= max_keywords:
            break

    return unique_candidates


def is_clinic_style_niche(raw_niche: str) -> bool:
    niche = (raw_niche or "").strip().lower()
    return "clinic" in niche or any(
        token in niche for token in ["aesthetic", "skin", "laser", "cosmetic", "hair transplant", "derma"]
    )


def should_use_osint_discovery(raw_niche: str) -> bool:
    """Return true when a niche should use public-web company discovery."""
    niche = (raw_niche or "").strip().lower()
    if niche in OSINT_FIRST_NICHES:
        return True
    if niche in {"saas", "fintech"}:
        return True
    return False


def build_osint_queries(raw_niche: str, raw_geo: str, requested_limit: int) -> List[str]:
    """Build high-signal public-web queries for company discovery."""
    niche = (raw_niche or "").strip().lower()
    geo = (raw_geo or "").strip()

    if niche == "saas":
        candidates = [
            f"site:tracxn.com/d/explore saas startups {geo}",
            f"site:tracxn.com/d/explore global saas startups {geo}",
            f'"{geo}" ("request a demo" OR "book a demo") (saas OR "software platform") -agency -services -"development company"',
            f'"{geo}" ("free trial" OR pricing) (saas OR "b2b software") -agency -services -jobs',
            f'"{geo}" (crm OR erp OR automation OR analytics) ("request demo" OR pricing) -consulting -outsourcing',
            f'site:.com "{geo}" ("start free" OR "free trial") (platform OR saas) -agency -services',
            f'"{geo}" "software platform" customers pricing -"development company" -agency',
        ]
    elif niche == "fintech":
        candidates = [
            f"{geo} fintech companies",
            f'{geo} payments platform "pricing"',
            f'{geo} fintech software "request a demo"',
        ]
    elif is_clinic_style_niche(niche):
        premium_tokens = ["premium", "luxury", "high end", "high-end", "elite", "upscale"]
        premium_hint = any(token in niche for token in premium_tokens)
        clinic_core = '("aesthetic clinic" OR "skin clinic" OR "dermatology clinic" OR "cosmetic clinic" OR medspa OR "laser clinic")'
        premium_clause = '("premium" OR luxury OR upscale OR elite OR "high-end") ' if premium_hint else ""
        candidates = [
            f'"{geo}" {premium_clause}{clinic_core} ("book appointment" OR "book consultation" OR whatsapp)',
            f'"{geo}" {premium_clause}{clinic_core} ("consultation" OR "treatment" OR "skin" OR "laser")',
            f'site:.com "{geo}" {premium_clause}{clinic_core} -jobs -supplier -wholesale -training',
            f'"{geo}" ("skin clinic" OR "aesthetic clinic") ("lavelle road" OR indiranagar OR koramangala OR jayanagar OR "mg road" OR whitefield)',
            f'"{geo}" ("dermatologist" OR "cosmetic dermatologist") ("clinic" OR consultation) -hospital -college',
            f'"{geo}" ("premium skin clinic" OR "premium aesthetic clinic" OR "premium dermatology clinic")',
            f'"{geo}" ("indiranagar" OR "koramangala" OR "whitefield" OR "jayanagar" OR "lavelle road" OR "mg road") ("skin clinic" OR "aesthetic clinic" OR "cosmetic clinic")',
            f'site:.com "{geo}" ("anti aging clinic" OR "facial aesthetics" OR "skin treatment clinic") -hospital -college -jobs',
        ]
    else:
        candidates = [
            f"{geo} {raw_niche} companies",
            f'{geo} "{raw_niche}" software platform',
            f'{geo} "{raw_niche}" "request a demo"',
        ]

    max_queries = max(3, min(5, requested_limit))
    return candidates[:max_queries]


def build_clinic_fallback_niches(raw_niche: str) -> List[str]:
    """Generate broader clinic niche retries when the first discovery pass returns nothing."""
    lowered = (raw_niche or "").strip().lower()
    candidates = [
        raw_niche,
        "premium skin and aesthetic clinics",
        "skin clinics",
        "aesthetic clinics",
        "dermatology clinics",
        "cosmetic clinics",
        "laser clinics",
    ]
    if "premium" not in lowered:
        candidates.insert(1, f"premium {raw_niche}".strip())

    deduped: List[str] = []
    seen = set()
    for candidate in candidates:
        normalized = str(candidate or "").strip().lower()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(str(candidate).strip())
    return deduped


def build_firecrawl_clinic_queries(raw_niche: str, raw_geo: str) -> List[str]:
    """Build high-signal Firecrawl search queries for clinic discovery."""
    niche = (raw_niche or "").strip().lower()
    geo = (raw_geo or "").strip()

    if any(token in niche for token in ["skin", "aesthetic", "derma", "dermatology", "cosmetic", "laser", "medspa"]):
        return [
            f'site:.in {geo} "skin clinic" "book appointment"',
            f'{geo} premium dermatology clinic',
            f'{geo} "aesthetic clinic" whatsapp',
            f'{geo} "cosmetic clinic" consultation',
        ]

    if any(token in niche for token in ["dental", "dentist", "orthodontic", "oral"]):
        return [
            f'site:.in {geo} "dental clinic" "book appointment"',
            f'{geo} premium dental clinic',
            f'{geo} cosmetic dentistry clinic',
        ]

    if any(token in niche for token in ["hair", "transplant", "trichology"]):
        return [
            f'site:.in {geo} "hair transplant clinic" consultation',
            f'{geo} premium hair clinic',
            f'{geo} trichology clinic whatsapp',
        ]

    return [f"{geo} {raw_niche}".strip()]


def is_low_quality_firecrawl_result(raw_url: str, title: str) -> bool:
    """Drop obvious directories, social links, and noisy listicles from Firecrawl search."""
    domain = (extract_domain(raw_url) or "").lower().replace("www.", "")
    lowered_title = (title or "").lower()

    if not domain:
        return True

    if domain in {
        "instagram.com",
        "facebook.com",
        "linkedin.com",
        "youtube.com",
        "x.com",
        "twitter.com",
        "justdial.com",
        "practo.com",
        "threebestrated.in",
        "sulekha.com",
    }:
        return True

    return any(blocked in lowered_title for blocked in ["top 10", "near me", "list of", "directory"])


def discover_company_candidates_firecrawl(raw_niche: str, raw_geo: str, limit: int) -> List[Lead]:
    """Use Firecrawl search as a discovery fallback when Google Maps/OSINT come up empty."""
    api_key = os.getenv("FIRECRAWL_API_KEY") or os.getenv("FIRE_CRAWL_API_KEY")
    if not api_key:
        return []

    leads: List[Lead] = []
    seen_domains = set()

    for query in build_firecrawl_clinic_queries(raw_niche, raw_geo):
        try:
            response = requests.post(
                FIRECRAWL_SEARCH_API_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "query": query,
                    "limit": min(max(limit, 8), 10),
                },
                timeout=30,
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            logger.warning("Firecrawl discovery search failed for query=%s: %s", query, exc)
            continue

        for item in payload.get("data") or []:
            website = canonicalize_company_website(str(item.get("url") or "").strip())
            title = str(item.get("title") or "").strip()
            domain = (extract_domain(website) or "").lower().replace("www.", "")

            if not website or not domain or domain in seen_domains:
                continue
            if is_low_quality_firecrawl_result(website, title):
                continue

            seen_domains.add(domain)
            company_name = infer_company_name_from_title(website, title)

            leads.append(
                Lead(
                    lead_id=uuid4(),
                    business_name=company_name,
                    category=raw_niche,
                    location=raw_geo,
                    geo_tags=[raw_niche, raw_geo],
                    website=website,
                    landing_page_url=website,
                    phone=None,
                    emails_found=[],
                    facebook_page=None,
                    instagram=None,
                    ads_active=False,
                    lead_lifecycle_state=LeadLifecycleState.NEW,
                )
            )

            if len(leads) >= limit * 2:
                return leads

    return leads


def normalize_search_result_url(raw_url: str) -> Optional[str]:
    """Normalize a search result URL and unwrap DuckDuckGo redirects."""
    if not raw_url:
        return None

    parsed = urlparse(raw_url)
    if "duckduckgo.com" in (parsed.netloc or "").lower() and parsed.path.startswith("/l/"):
        uddg_values = parse_qs(parsed.query).get("uddg", [])
        if uddg_values:
            raw_url = unquote(uddg_values[0])
            parsed = urlparse(raw_url)

    if parsed.scheme not in {"http", "https"}:
        return None

    domain = (parsed.netloc or "").lower().replace("www.", "")
    if domain in OSINT_BLOCKED_DOMAINS:
        return None

    normalized_path = parsed.path or ""
    if normalized_path == "/":
        normalized_path = ""
    return f"{parsed.scheme}://{parsed.netloc}{normalized_path}"


def fetch_brave_search_results(query: str, max_results: int = 10) -> List[Dict[str, str]]:
    """Fetch web search results from Brave Search when an API key is available."""
    brave_api_key = os.getenv("BRAVE_API_KEY")
    if not brave_api_key:
        return []

    try:
        response = requests.get(
            BRAVE_SEARCH_API_URL,
            params={
                "q": query,
                "count": max(1, min(max_results, 10)),
                "search_lang": "en",
            },
            headers={
                **DISCOVERY_HTTP_HEADERS,
                "Accept": "application/json",
                "X-Subscription-Token": brave_api_key,
            },
            timeout=20,
        )
        if response.status_code >= 400:
            return []

        payload = response.json()
        results: List[Dict[str, str]] = []
        for item in payload.get("web", {}).get("results", []):
            url = normalize_search_result_url(item.get("url") or "")
            if not url:
                continue
            results.append(
                {
                    "url": url,
                    "title": item.get("title") or "",
                    "snippet": item.get("description") or "",
                }
            )
            if len(results) >= max_results:
                break

        return results
    except Exception:
        return []


def fetch_duckduckgo_search_results(query: str, max_results: int = 10) -> List[Dict[str, str]]:
    """Fetch public web search results from DuckDuckGo HTML."""
    try:
        response = requests.get(
            "https://html.duckduckgo.com/html/",
            params={"q": query},
            headers=DISCOVERY_HTTP_HEADERS,
            timeout=20,
        )
        if response.status_code >= 400:
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        results: List[Dict[str, str]] = []

        for anchor in soup.select("a.result__a"):
            url = normalize_search_result_url(anchor.get("href") or "")
            if not url:
                continue

            title = anchor.get_text(" ", strip=True)
            snippet = ""
            container = anchor.find_parent("div", class_="result")
            if container:
                snippet_node = container.select_one(".result__snippet")
                if snippet_node:
                    snippet = snippet_node.get_text(" ", strip=True)

            results.append({"url": url, "title": title, "snippet": snippet})
            if len(results) >= max_results:
                break

        return results
    except Exception:
        return []


@lru_cache(maxsize=64)
def fetch_search_results(query: str, max_results: int = 10) -> List[Dict[str, str]]:
    """Fetch web search results, preferring Brave and falling back to DuckDuckGo HTML."""
    brave_results = fetch_brave_search_results(query, max_results=max_results)
    if brave_results:
        return brave_results
    return fetch_duckduckgo_search_results(query, max_results=max_results)


def infer_company_name_from_url(url: str) -> str:
    """Infer a readable company name from a domain."""
    domain = extract_domain(url) or url
    return _clean_company_name_candidate(_humanize_domain_stem(domain) or domain)


AGGREGATOR_DOMAINS = (
    "whatclinic.com",
    "practo.com",
    "justdial.com",
    "sulekha.com",
    "lybrate.com",
    "credihealth.com",
)

GENERIC_BRAND_SUFFIXES = (
    "premium",
    "clinic",
    "clinics",
    "hospital",
    "hospitals",
    "skin",
    "hair",
    "aesthetic",
    "aesthetics",
    "cosmetic",
    "cosmetics",
    "derma",
    "dermatology",
    "care",
    "vision",
    "laser",
    "center",
    "centre",
    "wellness",
    "medspa",
    "med",
    "spa",
)

GENERIC_BRAND_TITLES = (
    "home",
    "our clinic",
    "welcome",
    "welcome to our clinic",
    "our team",
    "book appointment",
    "contact us",
)

GENERIC_QUERY_NAME_TOKENS = {
    "aesthetic",
    "aesthetics",
    "clinic",
    "clinics",
    "skin",
    "hair",
    "laser",
    "cosmetic",
    "derma",
    "dermatology",
    "service",
    "services",
    "hospital",
    "doctor",
    "doctors",
    "bangalore",
    "bengaluru",
    "near",
    "me",
}


SEO_BRAND_BLOCKLIST = (
    "best ",
    "top ",
    "#1",
    "near me",
    "directory",
    "list of",
    "beauty clinic for ",
    "weight loss",
    "skin specialist in ",
    "best dermatologist",
    "best skin specialist",
    "best skin ",
    "clinic in ",
    "hospital in ",
    "dermatologist in ",
    "skin clinic in ",
    "hair clinic in ",
    "cosmetic clinic in ",
    "multispecialty hospital in ",
)

SEO_GEO_HINTS = (
    "bangalore",
    "bengaluru",
    "jayanagar",
    "indiranagar",
    "whitefield",
    "koramangala",
    "hsr",
    "marathahalli",
)


def _normalize_brand_token(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").lower())


def _strip_phone_like_suffix(value: str) -> str:
    return re.sub(r"\s*\+?\d[\d\s().-]{6,}$", "", str(value or "")).strip(" -:\u2013\u2014,")


def _clean_company_name_candidate(value: str) -> str:
    text = _strip_phone_like_suffix(str(value or ""))
    text = re.sub(r"(?i)%20", " ", text.replace("+", " "))
    text = re.sub(r"(?:\s+\d{2,4})+$", "", text)
    text = re.sub(r"\s+", " ", text).strip(" -:\u2013\u2014,")
    return text


def _is_aggregator_domain(url: str) -> bool:
    hostname = (extract_domain(url) or "").lower().replace("www.", "")
    return any(
        hostname == blocked or hostname.endswith(f".{blocked}")
        for blocked in AGGREGATOR_DOMAINS
    )


def _humanize_domain_stem(url: str) -> str:
    hostname = (extract_domain(url) or str(url or "").strip().lower()).replace("www.", "")
    stem = hostname.split(".")[0].replace("-", " ").replace("_", " ").strip()
    if not stem:
        return ""

    raw_stem = re.sub(r"\s+", "", stem.lower())
    words: List[str] = []
    remaining = raw_stem

    while remaining:
        matched_suffix = None
        for suffix in sorted(GENERIC_BRAND_SUFFIXES, key=len, reverse=True):
            suffix_token = _normalize_brand_token(suffix)
            if remaining.endswith(suffix_token) and len(remaining) > len(suffix_token) + 2:
                matched_suffix = suffix
                brand_root = remaining[: -len(suffix_token)]
                if brand_root:
                    words.insert(0, matched_suffix)
                    remaining = brand_root
                break
        if not matched_suffix:
            words.insert(0, remaining)
            break

    humanized = " ".join(word for word in words if word).strip()
    if not humanized:
        humanized = stem

    return " ".join(part.capitalize() for part in humanized.split())


def _looks_like_seo_brand_noise(value: str) -> bool:
    lowered = (value or "").strip().lower()
    if not lowered:
        return True
    return any(token in lowered for token in SEO_BRAND_BLOCKLIST)


def _looks_like_search_query_name(value: str) -> bool:
    text = str(value or "").strip()
    if not text:
        return True
    lowered = text.lower()
    has_encoded_separator = "+" in lowered or "%20" in lowered
    normalized = re.sub(r"(?i)%20", " ", lowered.replace("+", " "))
    tokens = [token for token in re.findall(r"[a-z]+", normalized) if token]
    if not tokens:
        return True
    generic_ratio = sum(1 for token in tokens if token in GENERIC_QUERY_NAME_TOKENS) / len(tokens)
    if has_encoded_separator and generic_ratio >= 0.7:
        return True
    if len(tokens) <= 3 and generic_ratio == 1:
        return True
    return False


def infer_company_name_from_title(url: str, title: str) -> str:
    """Infer a likely real brand name from a search result title."""
    fallback = _clean_company_name_candidate(infer_company_name_from_url(url))
    title = (title or "").strip()
    if not title:
        return fallback

    domain = extract_domain(url) or url
    hostname = domain.lower().replace("www.", "")
    domain_stem = hostname.split(".")[0]
    domain_token = _normalize_brand_token(domain_stem)

    raw_segments: List[str] = []
    for segment in re.split(r"\|", title):
        cleaned = _clean_company_name_candidate(segment)
        if cleaned:
            raw_segments.append(cleaned)
        for subsegment in re.split(r"\s[-\u2013\u2014]\s", cleaned):
            normalized = _clean_company_name_candidate(subsegment)
            if normalized:
                raw_segments.append(normalized)
        if ":" in cleaned:
            prefix = _clean_company_name_candidate(cleaned.split(":", 1)[0])
            if prefix:
                raw_segments.append(prefix)

    best_segment = ""
    best_score = float("-inf")
    for segment in raw_segments:
        lowered = segment.lower()
        normalized = _normalize_brand_token(segment)
        score = 0

        if _looks_like_seo_brand_noise(segment):
            score -= 6
        if re.search(r"\+?\d[\d\s().-]{6,}", segment):
            score -= 5
        if any(hint in lowered for hint in SEO_GEO_HINTS):
            score -= 3
        if len(segment.split()) > 8:
            score -= 2
        if 3 <= len(segment) <= 60:
            score += 1
        if len(segment.split()) <= 6:
            score += 1
        if any(token in lowered for token in ["clinic", "clinics", "aesthetic", "skin", "hair", "care", "laser"]):
            score += 1
        if domain_token and domain_token in normalized:
            score += 6
        if "example.com" in lowered:
            score -= 6

        if score > best_score:
            best_segment = segment
            best_score = score

    cleaned_best = _clean_company_name_candidate(best_segment)
    if cleaned_best and cleaned_best.lower() in GENERIC_BRAND_TITLES:
        return fallback

    if cleaned_best:
        normalized_best = _normalize_brand_token(cleaned_best)
        normalized_fallback = _normalize_brand_token(fallback)
        if normalized_best == normalized_fallback and " " not in cleaned_best and " " in fallback:
            return fallback

    if best_segment and best_score >= 2:
        return _clean_company_name_candidate(cleaned_best or best_segment)

    return fallback


def canonicalize_company_website(url: str) -> str:
    """Convert a resolved company URL into a stable homepage URL for storage/display."""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return url
    return f"{parsed.scheme}://{parsed.netloc}"


def is_low_quality_osint_result(result: Dict[str, str]) -> bool:
    """Drop listicles, communities, and generic content pages from SaaS discovery."""
    url = result.get("url") or ""
    title = (result.get("title") or "").strip().lower()
    snippet = (result.get("snippet") or "").strip().lower()
    domain = (extract_domain(url) or "").lower().replace("www.", "")

    if not domain:
        return True
    if domain in OSINT_RESULT_BLOCKLIST:
        return True

    haystack = f"{title} {snippet}"
    if any(term in haystack for term in OSINT_LISTICLE_TERMS):
        return True
    if any(token in haystack for token in ["jobs", "careers", "blog", "news", "guide"]):
        return True

    return False


def extract_tracxn_companies(url: str, max_names: int = 12) -> List[Dict[str, str]]:
    """Extract company names and profile URLs from an accessible Tracxn list page."""
    try:
        response = requests.get(
            url,
            headers=DISCOVERY_HTTP_HEADERS,
            timeout=20,
            allow_redirects=True,
        )
        if response.status_code >= 400:
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        companies: List[Dict[str, str]] = []
        seen = set()
        for anchor in soup.select('a[href^="/d/companies/"]'):
            name = anchor.get_text(" ", strip=True)
            normalized = re.sub(r"\s+", " ", name).strip()
            if len(normalized) < 2:
                continue
            lowered = normalized.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            href = anchor.get("href") or ""
            profile_url = href if href.startswith("http") else f"https://tracxn.com{href}"
            companies.append({"name": normalized, "profile_url": profile_url})
            if len(companies) >= max_names:
                break

        return companies
    except Exception:
        return []


@lru_cache(maxsize=128)
def resolve_company_website(company_name: str, raw_geo: str) -> Optional[str]:
    """Resolve an official company website from public search."""
    query = f'"{company_name}" official site {raw_geo}'.strip()
    results = fetch_search_results(query, max_results=5)
    for result in results:
        if is_low_quality_osint_result(result):
            continue
        website = normalize_search_result_url(result.get("url") or "")
        if not website:
            continue
        domain = (extract_domain(website) or "").lower().replace("www.", "")
        if not domain or domain in OSINT_RESULT_BLOCKLIST or domain in OSINT_BLOCKED_DOMAINS:
            continue
        return website
    return None


@lru_cache(maxsize=128)
def extract_official_website_from_tracxn_company_page(profile_url: str) -> Optional[str]:
    """Extract the official website from an accessible Tracxn company profile page."""
    try:
        response = requests.get(
            profile_url,
            headers=DISCOVERY_HTTP_HEADERS,
            timeout=20,
            allow_redirects=True,
        )
        if response.status_code >= 400:
            return None

        soup = BeautifulSoup(response.text, "html.parser")
        for anchor in soup.select('a[href^="http"]'):
            href = normalize_search_result_url(anchor.get("href") or "")
            if not href:
                continue
            domain = (extract_domain(href) or "").lower().replace("www.", "")
            if not domain or domain in OSINT_BLOCKED_DOMAINS or domain in OSINT_RESULT_BLOCKLIST:
                continue
            if domain == "tracxn.com" or domain.endswith(".tracxn.com"):
                continue
            return href
    except Exception:
        return None

    return None


def _domain_brand_hint(website: Optional[str]) -> Optional[str]:
    if not website or _is_aggregator_domain(str(website)):
        return None
    brand = infer_company_name_from_url(str(website))
    return brand or None


def _is_generic_company_title(title: str, *, raw_geo: str, brand_hint: Optional[str]) -> bool:
    cleaned_title = _clean_company_name_candidate(title)
    lowered = cleaned_title.lower()
    if not lowered:
        return True
    if lowered in GENERIC_BRAND_TITLES:
        return True
    if cleaned_title != str(title or "").strip():
        return True

    geo = (raw_geo or "").strip().lower()
    geo_tokens = [geo] if geo else []
    geo_tokens.extend([token for token in geo.split() if token])
    geo_hit = any(token in lowered for token in geo_tokens) if geo_tokens else False

    generic_tokens = [
        "best",
        "top",
        "near me",
        "in ",
        "clinic",
        "dermatologist",
        "skin",
        "aesthetic",
        "hair",
        "doctor",
        "specialist",
        "center",
        "centre",
    ]
    generic_hit = any(token in lowered for token in generic_tokens)
    branded_seo_hit = bool(
        brand_hint
        and brand_hint.lower() in lowered
        and generic_hit
        and (":" in lowered or "|" in lowered or len(lowered.split()) > 6)
    )
    if brand_hint and brand_hint.lower() in lowered and not branded_seo_hit and not (geo_hit and generic_hit):
        return False

    return (geo_hit and generic_hit) or branded_seo_hit


def discover_company_candidates_osint(raw_niche: str, raw_geo: str, limit: int) -> List[Lead]:
    """Discover company candidates from public-web search results."""
    queries = build_osint_queries(raw_niche, raw_geo, limit)
    leads: List[Lead] = []
    seen_domains = set()

    for query in queries:
        results = fetch_search_results(query, max_results=max(limit, 8))
        for result in results:
            result_url = result.get("url") or ""
            result_domain = (extract_domain(result_url) or "").lower().replace("www.", "")

            if is_low_quality_osint_result(result):
                if result_domain in OSINT_EXPANDABLE_SOURCE_DOMAINS:
                    companies = extract_tracxn_companies(result_url, max_names=max(limit * 2, 10))
                    for company in companies:
                        company_name = company["name"]
                        website = extract_official_website_from_tracxn_company_page(company["profile_url"])
                        if not website:
                            website = resolve_company_website(company_name, raw_geo)
                        if website:
                            website = canonicalize_company_website(website)
                        domain = (extract_domain(website) or "").lower() if website else ""
                        if not website or not domain or domain in seen_domains:
                            continue
                        seen_domains.add(domain)
                        leads.append(
                            Lead(
                                lead_id=uuid4(),
                                business_name=company_name,
                                category=raw_niche,
                                location=raw_geo,
                                geo_tags=[raw_niche, raw_geo],
                                website=website,
                                landing_page_url=website,
                                phone=None,
                                emails_found=[],
                                facebook_page=None,
                                instagram=None,
                                ads_active=False,
                                lead_lifecycle_state=LeadLifecycleState.NEW,
                            )
                        )
                        if len(leads) >= limit * 2:
                            return leads
                continue

            website = canonicalize_company_website(result_url)
            domain = (extract_domain(website) or "").lower()
            if not domain or domain in seen_domains:
                continue
            seen_domains.add(domain)

            title = str(result.get("title") or "")
            brand_hint = _domain_brand_hint(website) or infer_company_name_from_url(website)
            company_name = infer_company_name_from_title(website, title)
            if _looks_like_seo_brand_noise(company_name) or _is_generic_company_title(
                company_name,
                raw_geo=raw_geo,
                brand_hint=brand_hint,
            ):
                company_name = brand_hint or company_name
            if not company_name or len(company_name) < 3:
                company_name = brand_hint or infer_company_name_from_url(website)

            leads.append(
                Lead(
                    lead_id=uuid4(),
                    business_name=company_name,
                    category=raw_niche,
                    location=raw_geo,
                    geo_tags=[raw_niche, raw_geo],
                    website=website,
                    landing_page_url=website,
                    phone=None,
                    emails_found=[],
                    facebook_page=None,
                    instagram=None,
                    ads_active=False,
                    lead_lifecycle_state=LeadLifecycleState.NEW,
                )
            )

            if len(leads) >= limit * 2:
                return leads

    if is_clinic_style_niche(raw_niche) and len(leads) < max(4, min(limit, 8)):
        firecrawl_leads = discover_company_candidates_firecrawl(raw_niche, raw_geo, limit)
        for lead in firecrawl_leads:
            domain = (extract_domain(lead.website) or "").lower().replace("www.", "")
            if not domain or domain in seen_domains:
                continue
            seen_domains.add(domain)
            leads.append(lead)
            if len(leads) >= limit * 2:
                break

    return leads


def dedupe_discovered_leads(leads: List[Lead]) -> List[Lead]:
    """Collapse duplicate lead rows returned across multiple search variants."""
    deduped: List[Lead] = []
    seen = set()

    for lead in leads:
        domain = (extract_domain(lead.website) or "").strip().lower()
        if domain:
            dedupe_key = (domain,)
        else:
            dedupe_key = (
                (lead.business_name or "").strip().lower(),
                (lead.location or "").strip().lower(),
            )
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        deduped.append(lead)

    return deduped


def score_niche_relevance(raw_niche: str, lead: Lead) -> int:
    """Score how likely a lead is to match the requested niche."""
    niche = (raw_niche or "").strip().lower()
    if not niche:
        return 0

    haystack = " ".join(
        part
        for part in [
            (lead.business_name or "").lower(),
            (lead.category or "").lower(),
            (extract_domain(lead.website) or "").lower(),
        ]
        if part
    )

    score = 0
    if niche in haystack:
        score += 8

    hints = NICHE_RELEVANCE_HINTS.get(niche, {})
    for token in hints.get("include", []):
        if token in haystack:
            score += 3
    for token in hints.get("exclude", []):
        if token in haystack:
            score -= 6

    if is_clinic_style_niche(niche):
        clinic_terms = [
            "clinic",
            "aesthetic",
            "skin",
            "laser",
            "hair",
            "cosmetic",
            "derma",
            "dermatology",
            "medspa",
            "med spa",
        ]
        off_target_terms = [
            "hospital",
            "pharmacy",
            "medical college",
            "training institute",
            "wholesaler",
            "supplier",
        ]
        if any(token in haystack for token in clinic_terms):
            score += 8
        if any(token in haystack for token in ["aesthetic", "skin", "laser", "cosmetic"]):
            score += 4
        for token in off_target_terms:
            if token in haystack:
                score -= 5

    return score


def should_keep_discovered_lead(raw_niche: str, lead: Lead) -> bool:
    """Apply niche-specific quality gates after raw discovery."""
    niche = (raw_niche or "").strip().lower()
    if not niche:
        return True
    if lead.website and _is_aggregator_domain(str(lead.website)):
        return False
    if _looks_like_search_query_name(str(lead.business_name or "")):
        return False

    haystack = " ".join(
        part
        for part in [
            (lead.business_name or "").lower(),
            (lead.category or "").lower(),
            (extract_domain(lead.website) or "").lower(),
        ]
        if part
    )
    score = score_niche_relevance(raw_niche, lead)

    if niche == "saas":
        strong_terms = [
            "saas",
            "platform",
            "cloud",
            "crm",
            "erp",
            "automation",
            "b2b",
        ]
        weak_service_terms = [
            "software company",
            "software services",
            "development company",
            "mobile app development",
            "web development",
            "custom software",
            "it services",
            "consulting",
            "outsourcing",
            "agency",
        ]
        has_strong_term = any(token in haystack for token in strong_terms)
        has_weak_service_term = any(token in haystack for token in weak_service_terms)

        if has_weak_service_term and not has_strong_term:
            return False

        return score >= 6

    return score > 0


def rank_discovered_leads(raw_niche: str, leads: List[Lead], limit: int) -> List[Lead]:
    """Rank leads by niche relevance and keep the strongest matches."""
    niche = (raw_niche or "").strip().lower()
    ranked = sorted(
        leads,
        key=lambda lead: (
            score_niche_relevance(raw_niche, lead),
            (lead.reviews_count or 0),
            lead.business_name or "",
        ),
        reverse=True,
    )

    filtered_matches = [
        lead for lead in ranked if should_keep_discovered_lead(raw_niche, lead)
    ]
    if filtered_matches:
        return filtered_matches[:limit]

    if niche == "saas" or is_clinic_style_niche(niche):
        return []

    return ranked[:limit]


@lru_cache(maxsize=256)
def fetch_website_text(url: Optional[str]) -> str:
    """Fetch lightweight homepage text for secondary candidate verification."""
    if not url:
        return ""

    try:
        response = requests.get(
            url,
            headers=DISCOVERY_HTTP_HEADERS,
            timeout=6,
            allow_redirects=True,
        )
        if response.status_code >= 400:
            return ""

        body = response.text[:80000]
        body = re.sub(r"(?is)<script.*?>.*?</script>", " ", body)
        body = re.sub(r"(?is)<style.*?>.*?</style>", " ", body)
        body = re.sub(r"(?s)<[^>]+>", " ", body)
        body = re.sub(r"\s+", " ", body)
        return body.lower()
    except Exception:
        return ""


def score_website_relevance(raw_niche: str, lead: Lead, website_text: str) -> int:
    """Score website copy against the requested niche."""
    niche = (raw_niche or "").strip().lower()
    if not website_text:
        return 0

    if is_clinic_style_niche(niche):
        score = 0
        strong_terms = [
            "skin clinic",
            "aesthetic clinic",
            "laser hair",
            "hair transplant",
            "dermatology",
            "cosmetic treatment",
            "skin treatment",
            "book appointment",
            "book consultation",
            "contact us",
            "whatsapp",
        ]
        weak_terms = [
            "training institute",
            "medical college",
            "equipment supplier",
            "wholesale",
            "jobs",
            "career",
        ]
        for token in strong_terms:
            if token in website_text:
                score += 2
        for token in weak_terms:
            if token in website_text:
                score -= 3
        return score

    if niche != "saas":
        return 0

    score = 0
    strong_terms = [
        "saas",
        "software as a service",
        "platform",
        "book a demo",
        "request a demo",
        "start free",
        "free trial",
        "pricing",
        "integrations",
        "customers",
        "workflow automation",
        "crm",
        "erp",
        "cloud",
        "subscription",
    ]
    weak_service_terms = [
        "software development company",
        "mobile app development",
        "web development company",
        "custom software development",
        "outsourcing",
        "staff augmentation",
        "agency",
        "consulting services",
        "digital marketing",
        "it services",
    ]

    for token in strong_terms:
        if token in website_text:
            score += 2

    for token in weak_service_terms:
        if token in website_text:
            score -= 4

    return score


def extract_website_emails(website_text: str) -> List[str]:
    """Extract likely emails from homepage text."""
    if not website_text:
        return []

    matches = re.findall(
        r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b",
        website_text,
    )
    ignored_domains = {"example.com", "domain.com"}
    emails: List[str] = []
    seen = set()
    for email in matches:
        lowered = email.lower()
        domain = lowered.split("@")[-1]
        if domain in ignored_domains or lowered in seen:
            continue
        seen.add(lowered)
        emails.append(lowered)
        if len(emails) >= 3:
            break
    return emails


def extract_website_phones(website_text: str) -> List[str]:
    """Extract likely phone numbers from homepage text."""
    if not website_text:
        return []

    matches = re.findall(r"(?:\+\d{1,3}[\s-]?)?(?:\d[\s().-]?){8,15}\d", website_text)
    phones: List[str] = []
    seen = set()
    for match in matches:
        normalized = re.sub(r"\s+", " ", match).strip()
        if normalized.count(".") >= 2:
            continue
        digits = re.sub(r"\D", "", normalized)
        if len(digits) < 10 or len(digits) > 15:
            continue
        if digits in seen:
            continue
        seen.add(digits)
        phones.append(normalized)
        if len(phones) >= 2:
            break
    return phones


def detect_contact_paths(website_text: str, lead: Lead, emails: List[str], phones: List[str]) -> List[str]:
    """Return human-meaningful contact path hints for discovery preview."""
    paths: List[str] = []
    website_text = (website_text or "").lower()

    if emails or (lead.emails_found or []):
        paths.append("email")
    if phones or lead.phone:
        paths.append("phone")
    if any(token in website_text for token in ["contact us", "contact sales", "get in touch", "talk to sales"]):
        paths.append("contact form")
    if any(token in website_text for token in ["book a demo", "request a demo", "schedule demo", "schedule a demo"]):
        paths.append("demo cta")
    if any(token in website_text for token in ["book appointment", "book consultation", "schedule appointment", "appointment"]):
        paths.append("booking")
    if any(token in website_text for token in ["free trial", "start free", "start your free trial", "sign up"]):
        paths.append("trial signup")
    if any(
        token in website_text
        for token in ["wa.me/", "api.whatsapp.com", "whatsapp://send", "web.whatsapp.com/send"]
    ):
        paths.append("whatsapp")

    deduped: List[str] = []
    seen = set()
    for path in paths:
        if path in seen:
            continue
        seen.add(path)
        deduped.append(path)
    return deduped


def classify_verified_fit(raw_niche: str, lead: Lead, website_score: int) -> str:
    """Return a user-facing verified fit label instead of raw Maps category."""
    niche = (raw_niche or "").strip().lower()
    if niche == "saas":
        if website_score >= 10:
            return "Verified SaaS"
        if website_score >= 6:
            return "Possible SaaS"
        return "SaaS candidate"
    if is_clinic_style_niche(niche):
        if website_score >= 8:
            return "Verified clinic"
        if website_score >= 4:
            return "Likely clinic"
        return lead.category or "Clinic candidate"
    return lead.category or raw_niche or "candidate"


def infer_discovery_source_from_niche(raw_niche: str) -> str:
    """Infer the discovery lane from the niche/category string."""
    niche = (raw_niche or "").strip().lower()
    if should_use_osint_discovery(niche):
        return "osint"
    if any(token in niche for token in ["saas", "software", "fintech", "ecommerce"]):
        return "osint"
    return "google_maps"


def build_discovery_preview(raw_niche: str, lead: Lead) -> Dict[str, Any]:
    """Generate a qualified preview for the initial discovery artifact."""
    website_text = fetch_website_text(lead.website)
    base_score = score_niche_relevance(raw_niche, lead)
    website_score = score_website_relevance(raw_niche, lead, website_text)
    combined_score = max(base_score + website_score, 0)
    emails = extract_website_emails(website_text)
    phones = extract_website_phones(website_text)
    preview_score = combined_score * 2.8
    if not lead.website:
        preview_score -= 15
    if not emails and not phones and not lead.phone:
        preview_score -= 10
    if _looks_like_search_query_name(str(lead.business_name or "")):
        preview_score -= 20
    preview_score = min(max(preview_score, 0), 100)

    preview_contacts: List[Dict[str, Any]] = []
    for email in emails:
        preview_contacts.append({"email": email, "type": "email"})
    for phone in phones:
        preview_contacts.append({"phone": phone, "type": "phone"})
    if lead.phone:
        raw_phone = re.sub(r"\s+", " ", str(lead.phone)).strip()
        if raw_phone and not any(item.get("phone") == raw_phone for item in preview_contacts):
            preview_contacts.append({"phone": raw_phone, "type": "phone"})

    contact_paths = detect_contact_paths(website_text, lead, emails, phones)
    verified_fit = classify_verified_fit(raw_niche, lead, website_score)
    threshold = 62 if is_clinic_style_niche(raw_niche) else 65
    stage_status = "qualified_preview" if preview_score >= threshold else "candidate_preview"
    summary_bits = [verified_fit]
    if contact_paths:
        summary_bits.append(f"contact paths: {', '.join(contact_paths[:3])}")

    return {
        "score": preview_score if preview_score > 0 else None,
        "contacts": preview_contacts,
        "verified_fit": verified_fit,
        "status": stage_status,
        "contact_paths": contact_paths,
        "summary": " | ".join(summary_bits),
    }


def verify_discovered_leads(raw_niche: str, leads: List[Lead], limit: int) -> List[Lead]:
    """
    Run a second-pass website verification for niche-sensitive discovery.

    Discovery from Maps is only candidate collection. For SaaS, verify that the
    homepage copy looks like a product/business-software site before returning it.
    """
    niche = (raw_niche or "").strip().lower()
    if is_clinic_style_niche(niche):
        verified: List[tuple[int, Lead]] = []
        verification_cap = min(max(limit * 3, 8), 20)
        for lead in leads[:verification_cap]:
            if _looks_like_search_query_name(str(lead.business_name or "")):
                continue
            website_text = fetch_website_text(lead.website)
            website_score = score_website_relevance(raw_niche, lead, website_text)
            base_score = score_niche_relevance(raw_niche, lead)
            contact_bonus = 3 if (lead.phone or detect_contact_paths(website_text, lead, [], [])) else 0
            combined_score = base_score + website_score + contact_bonus

            if combined_score >= 4 or lead.phone or lead.website:
                verified.append((combined_score, lead))

        verified.sort(key=lambda item: (item[0], item[1].reviews_count or 0), reverse=True)
        return [lead for _, lead in verified[:limit]]

    if niche != "saas":
        return leads[:limit]

    verified: List[tuple[int, Lead]] = []
    verification_cap = min(max(limit + 2, 6), 12)
    for lead in leads[:verification_cap]:
        website_text = fetch_website_text(lead.website)
        website_score = score_website_relevance(raw_niche, lead, website_text)
        base_score = score_niche_relevance(raw_niche, lead)
        combined_score = base_score + website_score

        if combined_score >= 10:
            verified.append((combined_score, lead))

    verified.sort(key=lambda item: (item[0], item[1].reviews_count or 0), reverse=True)
    return [lead for _, lead in verified[:limit]]


def matches_requested_geo(raw_geo: str, lead: Lead) -> bool:
    geo_text = (raw_geo or "").strip().lower()
    if not geo_text:
        return True

    location_parts = [
        (lead.location or "").lower(),
        *[(tag or "").lower() for tag in (lead.geo_tags or [])],
    ]
    haystack = " ".join(part for part in location_parts if part)

    if not haystack:
        return True

    aliases = CITY_ALIASES.get(geo_text, [geo_text])
    return any(alias in haystack for alias in aliases)

# ============================================================================
# Health Check
# ============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    db = getattr(app.state, "db", None)
    agents_status = {
        "orchestrator": _is_agent_ready("orchestrator", get_orchestrator),
        "discovery": _is_agent_ready("discovery", get_discovery_agent),
        "enrichment": _is_agent_ready("enrichment", get_enrichment_agent),
        "scoring": _is_agent_ready("scoring", get_scoring_agent),
    }
    return {
        "status": "healthy" if all(agents_status.values()) else "degraded",
        "service": "zrai-lead-os",
        "agents": agents_status,
        "storage": "memory" if getattr(db, "is_memory_backend", False) else "supabase",
    }


def _is_agent_ready(agent_name: str, getter: Callable[[], Any]) -> bool:
    """Treat lazily initialized agents as healthy if they can initialize on demand."""
    try:
        getter()
        return True
    except Exception as exc:
        logger.warning("Health check could not initialize %s: %s", agent_name, exc)
        return False


def _is_apify_budget_error(exc: Exception) -> bool:
    """Detect Apify quota/billing exhaustion so discovery can fall back gracefully."""
    message = str(exc).lower()
    return (
        "remaining usage" in message
        or "billing/subscription" in message
        or "consider upgrading to a paid plan" in message
        or "budget exceeded" in message
        or "monthly usage hard limit exceeded" in message
        or "usage hard limit exceeded" in message
    )

# ============================================================================
# Discovery Endpoint
# ============================================================================

@app.post("/api/v1/discover", response_model=DiscoverResponse)
async def discover_leads(
    request: DiscoverRequest,
    user_id: Optional[str] = Depends(get_user_id),
):
    """
    Discover leads based on niche and geo.
    
    This endpoint triggers the Discovery Agent which uses Apify
    to scrape leads from various sources.
    
    Set mock=true for instant mock data (useful for development/testing).
    """
    logger.info(f"Discovery request: niche={request.niche}, geo={request.geo}, limit={request.limit}, mock={request.mock}")
    
    # MOCK MODE - Return fake data instantly for testing (NO AGENTS NEEDED)
    if request.mock:
        logger.info("Using mock data for discovery - returning instantly")
        mock_leads = []
        for i in range(min(request.limit, 20)):
            mock_leads.append(LeadResponse(
                id=str(uuid4()),
                company_name=f"{request.niche.upper()} Company {i+1}",
                domain=f"company{i+1}.com",
                niche=request.niche,
                geo=request.geo,
                status="discovered",
                score=None,
                contacts=[{"email": f"contact{i+1}@company{i+1}.com"}],
                intent_signals=[],
            ))
        
        logger.info(f"Returning {len(mock_leads)} mock leads")
        return DiscoverResponse(
            leads=mock_leads,
            count=len(mock_leads),
            run_id=str(uuid4()),
        )
    
    # REAL MODE - Use Apify (slow but real data)
    try:
        discovery_agent = get_discovery_agent()
        db = get_db()
        run_id = str(uuid4())
        
        loop = asyncio.get_event_loop()
        query_limit = min(request.limit, 15)
        if not should_use_osint_discovery(request.niche):
            # Preview discovery should stay lightweight. The explicit analyze/enrich
            # actions are where we spend more time on deep truth collection.
            query_limit = min(max(request.limit, 1), 8)

        if should_use_osint_discovery(request.niche):
            leads = await loop.run_in_executor(
                None,
                lambda: discover_company_candidates_osint(request.niche, request.geo, query_limit),
            )
        else:
            geo_filter = build_discovery_geo(request.geo)
            keywords = build_discovery_keywords(request.niche, query_limit)
            detailed_scrape = False
            try:
                leads = await loop.run_in_executor(
                    None,
                    lambda: discovery_agent.discover_from_google_maps(
                        keywords=keywords,
                        geo=geo_filter,
                        limit=query_limit,
                        auto_process=False,
                        skip_duplicate_check=True,
                        detailed_scrape=detailed_scrape,
                    )
                )
            except Exception as exc:
                if not _is_apify_budget_error(exc):
                    raise
                logger.warning(
                    "Apify discovery budget exceeded for niche=%s geo=%s; falling back to OSINT discovery",
                    request.niche,
                    request.geo,
                )
                leads = await loop.run_in_executor(
                    None,
                    lambda: discover_company_candidates_osint(request.niche, request.geo, query_limit),
                )

            if geo_filter.get("city"):
                leads = [lead for lead in leads if matches_requested_geo(request.geo, lead)]

        leads = dedupe_discovered_leads(leads)
        leads = rank_discovered_leads(request.niche, leads, request.limit)
        leads = await loop.run_in_executor(
            None,
            lambda: verify_discovered_leads(request.niche, leads, request.limit),
        )

        if not leads and is_clinic_style_niche(request.niche):
            logger.info(
                "Primary clinic discovery returned no leads for niche=%s geo=%s; trying broader clinic fallbacks",
                request.niche,
                request.geo,
            )
            fallback_pool: List[Lead] = []
            fallback_limit = min(max(request.limit, 4), 12)
            for fallback_niche in build_clinic_fallback_niches(request.niche):
                fallback_batch = await loop.run_in_executor(
                    None,
                    lambda fallback_niche=fallback_niche: discover_company_candidates_osint(
                        fallback_niche, request.geo, fallback_limit
                    ),
                )
                fallback_pool.extend(fallback_batch)
                fallback_pool = dedupe_discovered_leads(fallback_pool)
                if len(fallback_pool) >= fallback_limit:
                    break

            if fallback_pool:
                fallback_ranked = rank_discovered_leads(request.niche, fallback_pool, request.limit)
                leads = await loop.run_in_executor(
                    None,
                    lambda: verify_discovered_leads(request.niche, fallback_ranked, request.limit),
                )

        discovery_source = infer_discovery_source_from_niche(request.niche)

        # Convert leads to response format. Discovery returns a qualified preview only;
        # heavy enrichment/scoring happens in explicit follow-up actions.
        lead_responses = []
        for lead in leads:
            preview = await loop.run_in_executor(
                None,
                lambda current_lead=lead: build_discovery_preview(request.niche, current_lead),
            )
            lead_data = await loop.run_in_executor(
                None,
                lambda current_lead=lead: get_or_create_discovered_lead(db, current_lead, request.niche),
            )
            frontend_lead = build_frontend_lead(
                lead_data,
            )
            preview_signals = [
                signal
                for signal in [
                    {
                        "id": f"{lead.lead_id}-verified-fit",
                        "lead_id": str(lead.lead_id),
                        "signal_type": "verified_fit",
                        "signal_value": preview.get("verified_fit") or "",
                        "confidence": 0.8,
                        "source": "homepage+maps",
                        "detected_at": datetime.utcnow().isoformat(),
                    },
                    {
                        "id": f"{lead.lead_id}-contact-paths",
                        "lead_id": str(lead.lead_id),
                        "signal_type": "contact_paths",
                        "signal_value": ", ".join(preview.get("contact_paths") or []),
                        "confidence": 0.7,
                        "source": "homepage",
                        "detected_at": datetime.utcnow().isoformat(),
                    },
                    {
                        "id": f"{lead.lead_id}-summary",
                        "lead_id": str(lead.lead_id),
                        "signal_type": "summary",
                        "signal_value": preview.get("summary") or "",
                        "confidence": 0.7,
                        "source": "qualified_preview",
                        "detected_at": datetime.utcnow().isoformat(),
                    },
                    {
                        "id": f"{lead.lead_id}-source",
                        "lead_id": str(lead.lead_id),
                        "signal_type": "discovery_source",
                        "signal_value": discovery_source,
                        "confidence": 1.0,
                        "source": discovery_source,
                        "detected_at": datetime.utcnow().isoformat(),
                    },
                ]
                if signal["signal_value"]
            ]
            lead_responses.append(LeadResponse(
                id=frontend_lead["id"],
                company_name=frontend_lead["company_name"],
                domain=frontend_lead["domain"],
                niche=preview.get("verified_fit") or request.niche,
                geo=frontend_lead["geo"] or request.geo,
                status=preview.get("status") or "candidate_preview",
                score=preview.get("score"),
                contacts=preview.get("contacts") or frontend_lead.get("contacts") or [{"email": e} for e in (lead.emails_found or [])],
                intent_signals=preview_signals,
                verified_fit=preview.get("verified_fit"),
                source=discovery_source,
                source_label="OSINT web discovery" if discovery_source == "osint" else "Google Maps",
                score_kind="preview_match",
                preview_summary=preview.get("summary"),
                contact_paths=preview.get("contact_paths") or [],
            ))
        
        return DiscoverResponse(
            leads=lead_responses,
            count=len(lead_responses),
            run_id=run_id,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        if _is_apify_budget_error(e):
            logger.warning(
                "Discovery budget error escaped primary path for niche=%s geo=%s; forcing OSINT fallback",
                request.niche,
                request.geo,
            )
            try:
                db = get_db()
                run_id = str(uuid4())
                loop = asyncio.get_event_loop()
                query_limit = min(request.limit, 15)
                if not should_use_osint_discovery(request.niche):
                    query_limit = min(max(request.limit, 1), 8)

                leads = await loop.run_in_executor(
                    None,
                    lambda: discover_company_candidates_osint(request.niche, request.geo, query_limit),
                )
                geo_filter = build_discovery_geo(request.geo)
                if geo_filter.get("city"):
                    leads = [lead for lead in leads if matches_requested_geo(request.geo, lead)]

                leads = dedupe_discovered_leads(leads)
                leads = rank_discovered_leads(request.niche, leads, request.limit)
                leads = await loop.run_in_executor(
                    None,
                    lambda: verify_discovered_leads(request.niche, leads, request.limit),
                )

                discovery_source = "osint"
                lead_responses = []
                for lead in leads:
                    preview = await loop.run_in_executor(
                        None,
                        lambda current_lead=lead: build_discovery_preview(request.niche, current_lead),
                    )
                    lead_data = await loop.run_in_executor(
                        None,
                        lambda current_lead=lead: get_or_create_discovered_lead(db, current_lead, request.niche),
                    )
                    frontend_lead = build_frontend_lead(lead_data)
                    preview_signals = [
                        signal
                        for signal in [
                            {
                                "id": f"{lead.lead_id}-verified-fit",
                                "lead_id": str(lead.lead_id),
                                "signal_type": "verified_fit",
                                "signal_value": preview.get("verified_fit") or "",
                                "confidence": 0.8,
                                "source": "homepage+maps",
                                "detected_at": datetime.utcnow().isoformat(),
                            },
                            {
                                "id": f"{lead.lead_id}-contact-paths",
                                "lead_id": str(lead.lead_id),
                                "signal_type": "contact_paths",
                                "signal_value": ", ".join(preview.get("contact_paths") or []),
                                "confidence": 0.7,
                                "source": "homepage",
                                "detected_at": datetime.utcnow().isoformat(),
                            },
                            {
                                "id": f"{lead.lead_id}-summary",
                                "lead_id": str(lead.lead_id),
                                "signal_type": "summary",
                                "signal_value": preview.get("summary") or "",
                                "confidence": 0.7,
                                "source": "qualified_preview",
                                "detected_at": datetime.utcnow().isoformat(),
                            },
                            {
                                "id": f"{lead.lead_id}-source",
                                "lead_id": str(lead.lead_id),
                                "signal_type": "discovery_source",
                                "signal_value": discovery_source,
                                "confidence": 1.0,
                                "source": discovery_source,
                                "detected_at": datetime.utcnow().isoformat(),
                            },
                        ]
                        if signal["signal_value"]
                    ]
                    lead_responses.append(LeadResponse(
                        id=frontend_lead["id"],
                        company_name=frontend_lead["company_name"],
                        domain=frontend_lead["domain"],
                        niche=preview.get("verified_fit") or request.niche,
                        geo=frontend_lead["geo"] or request.geo,
                        status=preview.get("status") or "candidate_preview",
                        score=preview.get("score"),
                        contacts=preview.get("contacts") or frontend_lead.get("contacts") or [{"email": e} for e in (lead.emails_found or [])],
                        intent_signals=preview_signals,
                        verified_fit=preview.get("verified_fit"),
                        source=discovery_source,
                        source_label="OSINT web discovery",
                        score_kind="preview_match",
                        preview_summary=preview.get("summary"),
                        contact_paths=preview.get("contact_paths") or [],
                    ))

                return DiscoverResponse(
                    leads=lead_responses,
                    count=len(lead_responses),
                    run_id=run_id,
                )
            except Exception as fallback_exc:
                logger.error("Forced OSINT fallback failed: %s", fallback_exc)
                raise HTTPException(status_code=402, detail="Monthly usage hard limit exceeded")

        logger.error(f"Discovery error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# Enrichment Endpoint
# ============================================================================

@app.post("/api/v1/enrich")
async def enrich_lead(
    request: EnrichRequest,
    user_id: Optional[str] = Depends(get_user_id),
):
    """Enrich a lead with additional data."""
    logger.info(f"Enrich request: lead_id={request.lead_id}")
    
    try:
        from src.graph.state import LeadGraphState
        from uuid import UUID
        
        db = get_db()
        enrichment_agent = get_enrichment_agent()
        
        # Get lead from database
        lead_data = db.get_lead(request.lead_id)
        if not lead_data:
            raise HTTPException(status_code=404, detail="Lead not found")
        
        state = build_graph_state(
            db,
            lead_data,
            current_stage="enrichment",
            last_node="discovery",
        )
        
        loop = asyncio.get_event_loop()
        result_state = await loop.run_in_executor(None, lambda: enrichment_agent(state))
        
        enrichment = result_state.get("enrichment") or {}
        intent = result_state.get("intent") or {}
        scoring = result_state.get("scoring") or {}
        return {
            "success": True,
            "lead_id": request.lead_id,
            "lead": build_frontend_lead(lead_data, enrichment, intent, scoring),
            "enrichment": enrichment,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Enrichment error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# Intent Analysis Endpoint
# ============================================================================

@app.post("/api/v1/intent")
async def analyze_intent(
    request: IntentRequest,
    user_id: Optional[str] = Depends(get_user_id),
):
    """Analyze intent signals for a lead."""
    logger.info(f"Intent request: lead_id={request.lead_id}")
    
    try:
        from src.graph.state import LeadGraphState
        from uuid import UUID
        
        db = get_db()
        intent_agent = get_intent_agent()
        
        # Get lead from database
        lead_data = db.get_lead(request.lead_id)
        if not lead_data:
            raise HTTPException(status_code=404, detail="Lead not found")
        
        state = build_graph_state(
            db,
            lead_data,
            current_stage="intent",
            last_node="enrichment",
        )
        
        loop = asyncio.get_event_loop()
        result_state = await loop.run_in_executor(None, lambda: intent_agent(state))
        
        enrichment = result_state.get("enrichment") or {}
        intent = result_state.get("intent") or {}
        scoring = result_state.get("scoring") or {}
        return {
            "success": True,
            "lead_id": request.lead_id,
            "lead": build_frontend_lead(lead_data, enrichment, intent, scoring),
            "intent": intent,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Intent analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# Proof Generation Endpoint
# ============================================================================

@app.post("/api/v1/proof")
async def generate_proof(
    request: ProofRequest,
    user_id: Optional[str] = Depends(get_user_id),
):
    """Generate proof artifacts (screenshots, recordings)."""
    logger.info(f"Proof request: lead_id={request.lead_id}, type={request.proof_type}")
    
    try:
        from src.graph.state import LeadGraphState
        from uuid import UUID
        
        db = get_db()
        audit_agent = get_audit_agent()
        
        # Get lead from database
        lead_data = db.get_lead(request.lead_id)
        if not lead_data:
            raise HTTPException(status_code=404, detail="Lead not found")
        
        state = build_graph_state(
            db,
            lead_data,
            current_stage="audit",
            last_node="governance",
            metadata={"force_audit": True, "proof_type": request.proof_type},
        )
        
        loop = asyncio.get_event_loop()
        result_state = await loop.run_in_executor(None, lambda: audit_agent(state))

        enrichment = result_state.get("enrichment") or {}
        intent = result_state.get("intent") or {}
        scoring = result_state.get("scoring") or {}
        proof = result_state.get("proof") or {}
        if not proof:
            raise HTTPException(
                status_code=500,
                detail=result_state.get("last_error") or "No proof artifact was generated",
            )
        return {
            "success": True,
            "lead_id": request.lead_id,
            "lead": build_frontend_lead(lead_data, enrichment, intent, scoring),
            "proof": proof,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Proof generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# Selected Lead Processing Endpoint
# ============================================================================

@app.post("/api/v1/process-leads")
async def process_selected_leads(
    request: ProcessLeadsRequest,
    user_id: Optional[str] = Depends(get_user_id),
):
    """Run enrich -> intent -> proof -> score -> outreach for selected leads."""
    logger.info(
        "Process selected leads request: count=%s, include_outreach=%s, force_refresh=%s",
        len(request.lead_ids),
        request.include_outreach,
        request.force_refresh,
    )

    try:
        db = get_db()
        loop = asyncio.get_event_loop()
        results = []

        for lead_id in request.lead_ids:
            lead_data = db.get_lead(lead_id)
            if not lead_data:
                results.append(
                    {
                        "lead_id": lead_id,
                        "success": False,
                        "error": "Lead not found",
                    }
                )
                continue

            try:
                lead_model = lead_data_to_model(lead_data)
                source = infer_discovery_source_from_niche(lead_data.get("category") or "")
                preview = await loop.run_in_executor(
                    None,
                    lambda current_lead=lead_model: build_discovery_preview(
                        lead_data.get("category") or lead_data.get("business_name") or "",
                        current_lead,
                    ),
                )
                processed = await loop.run_in_executor(
                    None,
                    lambda current_lead=lead_data: run_selected_lead_pipeline(
                        db,
                        current_lead,
                        include_outreach=request.include_outreach,
                        force_refresh=request.force_refresh,
                        fast_mode=True,
                    ),
                )
                processed["intent"] = harmonize_intent_with_proof(
                    processed.get("intent") or {},
                    processed.get("proof") or {},
                    processed.get("signal_facts") or {},
                )
                analysis_updated_at = derive_analysis_updated_at(
                    processed.get("enrichment") or {},
                    processed.get("intent") or {},
                    processed.get("proof") or {},
                    processed.get("scoring") or {},
                    processed.get("outreach") or [],
                    {"metadata": {"ads_verification": processed.get("ads_verification") or {}}},
                )
                frontend_lead = build_frontend_lead(
                    lead_data,
                    processed.get("enrichment") or {},
                    processed.get("intent") or {},
                    processed.get("scoring") or {},
                    processed.get("signal_facts") or {},
                    "analyzed",
                    analysis_updated_at,
                )
                frontend_lead = attach_final_metadata(
                    frontend_lead,
                    discovery_source=source,
                    verified_fit=preview.get("verified_fit"),
                    preview_score=preview.get("score"),
                    preview_summary=preview.get("summary"),
                    contact_paths=preview.get("contact_paths") or [],
                    proof=processed.get("proof") or {},
                    analysis_state="analyzed",
                    analysis_updated_at=analysis_updated_at,
                    signal_facts=processed.get("signal_facts") or {},
                    intent=processed.get("intent") or {},
                )
                analysis_bundle = build_analysis_bundle(
                    lead=lead_data,
                    signal_facts=processed.get("signal_facts") or {},
                    intent=processed.get("intent") or {},
                    scoring=processed.get("scoring") or {},
                    proof=processed.get("proof") or {},
                    analysis_state="analyzed",
                    analysis_updated_at=analysis_updated_at,
                    preview_match_score=preview.get("score"),
                )
                persist_processed_lead_state(
                    db,
                    lead_id,
                    frontend_lead,
                    processed.get("enrichment") or {},
                    processed.get("signal_facts") or {},
                )
                persist_analysis_snapshot(
                    db,
                    lead_id,
                    analysis_state="analyzed",
                    signal_facts=processed.get("signal_facts") or {},
                    analysis_updated_at=analysis_updated_at,
                    ads_verification=processed.get("ads_verification") or {},
                    analysis_bundle=analysis_bundle,
                )
                results.append(
                    {
                        "lead_id": lead_id,
                        "success": True,
                        "lead": frontend_lead,
                        "enrichment": processed.get("enrichment") or {},
                        "intent": processed.get("intent") or {},
                        "proof": processed.get("proof") or {},
                        "scoring": processed.get("scoring") or {},
                        "outreach": processed.get("outreach") or [],
                        "signal_facts": processed.get("signal_facts") or {},
                        "analysis_state": "analyzed",
                        "analysis_updated_at": analysis_updated_at,
                        "signals_version": SIGNALS_VERSION,
                        "analysis_bundle": analysis_bundle,
                    }
                )
            except Exception as lead_error:
                logger.error("Selected lead processing failed for %s: %s", lead_id, lead_error)
                results.append(
                    {
                        "lead_id": lead_id,
                        "success": False,
                        "error": str(lead_error),
                    }
                )

        return {
            "success": True,
            "processed": results,
            "count": len(results),
        }
    except Exception as e:
        logger.error(f"Selected lead processing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/analyze-lead")
async def analyze_lead(
    request: AnalyzeLeadRequest,
    user_id: Optional[str] = Depends(get_user_id),
):
    """Run deterministic clinic analysis for a single lead."""
    logger.info(
        "Analyze lead request: lead_id=%s, include_outreach=%s, force_refresh=%s",
        request.lead_id,
        request.include_outreach,
        request.force_refresh,
    )

    try:
        db = get_db()
        lead_data = db.get_lead(UUID(request.lead_id))
        if not lead_data:
            raise HTTPException(status_code=404, detail="Lead not found")

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda current_lead=lead_data: execute_lead_analysis(
                db,
                current_lead,
                include_outreach=request.include_outreach,
                include_audit=False,
                force_refresh=request.force_refresh,
            ),
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Analyze lead error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


def execute_lead_analysis(
    db,
    lead_data: Dict[str, Any],
    *,
    include_outreach: bool,
    include_audit: bool = False,
    force_refresh: bool = False,
) -> Dict[str, Any]:
    """Run the full single-lead analysis flow and persist the result."""
    lead_model = lead_data_to_model(lead_data)
    source = infer_discovery_source_from_niche(lead_data.get("category") or "")
    preview = build_discovery_preview(
        lead_data.get("category") or lead_data.get("business_name") or "",
        lead_model,
    )
    processed = run_selected_lead_pipeline(
        db,
        lead_data,
        include_outreach=include_outreach,
        include_audit=include_audit,
        force_refresh=force_refresh,
        fast_mode=False,
    )
    processed["intent"] = harmonize_intent_with_proof(
        processed.get("intent") or {},
        processed.get("proof") or {},
        processed.get("signal_facts") or {},
    )
    analysis_updated_at = derive_analysis_updated_at(
        processed.get("enrichment") or {},
        processed.get("intent") or {},
        processed.get("proof") or {},
        processed.get("scoring") or {},
        processed.get("outreach") or [],
        {"metadata": {"ads_verification": processed.get("ads_verification") or {}}},
    )
    frontend_lead = build_frontend_lead(
        lead_data,
        processed.get("enrichment") or {},
        processed.get("intent") or {},
        processed.get("scoring") or {},
        processed.get("signal_facts") or {},
        "analyzed",
        analysis_updated_at,
    )
    frontend_lead = attach_final_metadata(
        frontend_lead,
        discovery_source=source,
        verified_fit=preview.get("verified_fit"),
        preview_score=preview.get("score"),
        preview_summary=preview.get("summary"),
        contact_paths=preview.get("contact_paths") or [],
        proof=processed.get("proof") or {},
        analysis_state="analyzed",
        analysis_updated_at=analysis_updated_at,
        signal_facts=processed.get("signal_facts") or {},
        intent=processed.get("intent") or {},
    )
    analysis_bundle = build_analysis_bundle(
        lead=lead_data,
        signal_facts=processed.get("signal_facts") or {},
        intent=processed.get("intent") or {},
        scoring=processed.get("scoring") or {},
        proof=processed.get("proof") or {},
        analysis_state="analyzed",
        analysis_updated_at=analysis_updated_at,
        preview_match_score=preview.get("score"),
    )
    persist_processed_lead_state(
        db,
        str(lead_data.get("lead_id")),
        frontend_lead,
        processed.get("enrichment") or {},
        processed.get("signal_facts") or {},
    )
    persist_analysis_snapshot(
        db,
        str(lead_data.get("lead_id")),
        analysis_state="analyzed",
        signal_facts=processed.get("signal_facts") or {},
        analysis_updated_at=analysis_updated_at,
        ads_verification=processed.get("ads_verification") or {},
        analysis_bundle=analysis_bundle,
    )

    processed_details = {
        "enrichment": processed.get("enrichment") or {},
        "intent": processed.get("intent") or {},
        "proof": processed.get("proof") or {},
        "scoring": processed.get("scoring") or {},
        "outreach": processed.get("outreach") or [],
        "signal_facts": processed.get("signal_facts") or {},
        "analysis_state": "analyzed",
        "analysis_updated_at": analysis_updated_at,
        "signals_version": SIGNALS_VERSION,
        "analysis_bundle": analysis_bundle,
    }

    return {
        "success": True,
        "lead": frontend_lead,
        "processed_details": processed_details,
        "signal_facts": processed.get("signal_facts") or {},
        "analysis_state": "analyzed",
        "analysis_updated_at": analysis_updated_at,
        "signals_version": SIGNALS_VERSION,
        "analysis_bundle": analysis_bundle,
    }


def run_lead_analysis_background(
    lead_id: str,
    include_outreach: bool,
    force_refresh: bool = False,
) -> None:
    """Run analysis outside the request/response window and persist success or failure state."""
    db = get_db()
    lead_data = db.get_lead(lead_id)
    if not lead_data:
        logger.warning("Background analysis skipped; lead not found: %s", lead_id)
        return

    try:
        execute_lead_analysis(
            db,
            lead_data,
            include_outreach=include_outreach,
            include_audit=False,
            force_refresh=force_refresh,
        )
        logger.info("Background analysis completed for lead_id=%s", lead_id)
    except Exception as exc:
        logger.exception("Background analysis failed for lead_id=%s", lead_id)
        lead_state = db.get_lead_state(UUID(str(lead_id))) or {}
        metadata = dict(lead_state.get("metadata") or {})
        persist_analysis_snapshot(
            db,
            str(lead_id),
            analysis_state="failed",
            signal_facts=metadata.get("signal_facts") or {},
            analysis_updated_at=datetime.utcnow().isoformat(),
            ads_verification=metadata.get("ads_verification") or {},
            analysis_bundle=metadata.get("analysis_bundle") or metadata.get("intelligence") or {},
        )
        db.save_lead_state(
            {
                "lead_id": str(lead_id),
                "current_stage": lead_state.get("current_stage") or "analysis",
                "last_node": lead_state.get("last_node") or "analysis",
                "last_error": str(exc),
                "retry_count": lead_state.get("retry_count", 0),
                "next_run_at": lead_state.get("next_run_at"),
                "locks": lead_state.get("locks") or [],
                "metadata": {
                    **metadata,
                    "analysis_state": "failed",
                    "analysis_updated_at": datetime.utcnow().isoformat(),
                    "last_error": str(exc),
                },
            }
        )


@app.post("/api/v1/analyze-lead-async")
async def analyze_lead_async(
    request: AnalyzeLeadRequest,
    background_tasks: BackgroundTasks,
    user_id: Optional[str] = Depends(get_user_id),
):
    """Queue single-lead analysis and return immediately for UI polling."""
    logger.info(
        "Analyze lead async request: lead_id=%s, include_outreach=%s, force_refresh=%s",
        request.lead_id,
        request.include_outreach,
        request.force_refresh,
    )

    try:
        db = get_db()
        normalized_lead_id = normalize_lead_id_value(request.lead_id)
        lead_data = db.get_lead(normalized_lead_id)
        if not lead_data:
            raise HTTPException(status_code=404, detail="Lead not found")

        if request.force_refresh:
            clear_lead_analysis_cache_safe(db, UUID(normalized_lead_id))

        lead_state = db.get_lead_state(UUID(normalized_lead_id)) or {}
        metadata = dict(lead_state.get("metadata") or {})
        now = datetime.utcnow().isoformat()
        persist_analysis_snapshot(
            db,
            normalized_lead_id,
            analysis_state="analyzing",
            signal_facts=metadata.get("signal_facts") or {},
            analysis_updated_at=now,
            ads_verification=metadata.get("ads_verification") or {},
            analysis_bundle=metadata.get("analysis_bundle") or metadata.get("intelligence") or {},
        )
        db.save_lead_state(
            {
                "lead_id": normalized_lead_id,
                "current_stage": "analysis",
                "last_node": "analysis",
                "last_error": None,
                "retry_count": lead_state.get("retry_count", 0),
                "next_run_at": lead_state.get("next_run_at"),
                "locks": lead_state.get("locks") or [],
                "metadata": {
                    **metadata,
                    "analysis_state": "analyzing",
                    "analysis_updated_at": now,
                    "last_error": None,
                },
            }
        )
        background_tasks.add_task(
            run_lead_analysis_background,
            normalized_lead_id,
            request.include_outreach,
            request.force_refresh,
        )
        return {
            "success": True,
            "queued": True,
            "lead_id": normalized_lead_id,
            "analysis_state": "analyzing",
            "analysis_updated_at": now,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Analyze lead async error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# Scoring Endpoint
# ============================================================================

@app.post("/api/v1/score")
async def score_leads(
    request: ScoreRequest,
    user_id: Optional[str] = Depends(get_user_id),
):
    """Score leads based on intent, fit, and engagement."""
    logger.info(f"Score request: niche={request.niche}, geo={request.geo}")
    
    try:
        from src.graph.state import LeadGraphState
        from uuid import UUID
        
        db = get_db()
        scoring_agent = get_scoring_agent()
        
        results = []
        
        # If specific lead_ids provided, score those
        if request.lead_ids:
            for lead_id in request.lead_ids:
                lead_data = db.get_lead(lead_id)
                if not lead_data:
                    continue
                state = build_graph_state(
                    db,
                    lead_data,
                    current_stage="scoring",
                    last_node="audit",
                )
                
                loop = asyncio.get_event_loop()
                result_state = await loop.run_in_executor(None, lambda: scoring_agent(state))
                
                scoring = result_state.get("scoring")
                if scoring:
                    results.append({
                        "lead_id": lead_id,
                        "lead": build_frontend_lead(
                            lead_data,
                            result_state.get("enrichment") or {},
                            result_state.get("intent") or {},
                            scoring,
                        ),
                        "score": scoring.get("final_score", 0),
                        "tier": scoring.get("lead_tier"),
                        "breakdown": scoring,
                        "disqualified": bool(scoring.get("do_not_contact")),
                        "disqualification_reason": scoring.get("do_not_contact_reason"),
                    })
        else:
            # Get leads from database based on filters
            leads = db.get_leads(niche=request.niche, geo=request.geo, limit=100)
            for lead_data in leads:
                lead_id = lead_data.get("lead_id")
                if lead_id:
                    state = build_graph_state(
                        db,
                        lead_data,
                        current_stage="scoring",
                        last_node="audit",
                    )
                    
                    loop = asyncio.get_event_loop()
                    result_state = await loop.run_in_executor(None, lambda: scoring_agent(state))
                    
                    scoring = result_state.get("scoring")
                    if scoring:
                        results.append({
                            "lead_id": lead_id,
                            "lead": build_frontend_lead(
                                lead_data,
                                result_state.get("enrichment") or {},
                                result_state.get("intent") or {},
                                scoring,
                            ),
                            "score": scoring.get("final_score", 0),
                            "tier": scoring.get("lead_tier"),
                            "breakdown": scoring,
                            "disqualified": bool(scoring.get("do_not_contact")),
                            "disqualification_reason": scoring.get("do_not_contact_reason"),
                        })

        return {
            "success": True,
            "results": results,
            "scored_leads": results,
            "count": len(results),
        }
    except Exception as e:
        logger.error(f"Scoring error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# Outreach Endpoint
# ============================================================================

@app.post("/api/v1/outreach")
async def handle_outreach(
    request: OutreachRequest,
    user_id: Optional[str] = Depends(get_user_id),
):
    """Draft or send outreach messages."""
    logger.info(f"Outreach request: lead_id={request.lead_id}, action={request.action}")
    
    try:
        from src.graph.state import LeadGraphState
        from uuid import UUID
        
        db = get_db()
        outreach_agent = get_outreach_agent()
        
        # Get lead from database
        lead_data = db.get_lead(request.lead_id)
        if not lead_data:
            raise HTTPException(status_code=404, detail="Lead not found")
        
        state = build_graph_state(
            db,
            lead_data,
            current_stage="outreach",
            last_node="scoring",
            metadata={"channel": request.channel, "action": request.action},
        )
        
        loop = asyncio.get_event_loop()
        result_state = await loop.run_in_executor(None, lambda: outreach_agent(state))
        
        # outreach_messages is a list
        outreach_data = result_state.get("outreach_messages") or []

        return {
            "success": True,
            "lead_id": request.lead_id,
            "lead": build_frontend_lead(
                lead_data,
                result_state.get("enrichment") or {},
                result_state.get("intent") or {},
                result_state.get("scoring") or {},
            ),
            "outreach": outreach_data,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Outreach error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# Conversation Endpoint
# ============================================================================

@app.post("/api/v1/conversation")
async def handle_conversation(
    request: ConversationRequest,
    user_id: Optional[str] = Depends(get_user_id),
):
    """Handle conversation with a lead."""
    logger.info(f"Conversation request: lead_id={request.lead_id}")
    
    try:
        from src.graph.state import LeadGraphState
        from uuid import UUID
        
        db = get_db()
        conversation_agent = get_conversation_agent()
        
        # Get lead from database
        lead_data = db.get_lead(request.lead_id)
        if not lead_data:
            raise HTTPException(status_code=404, detail="Lead not found")
        
        state = build_graph_state(
            db,
            lead_data,
            current_stage="conversation",
            last_node="outreach",
            metadata={"incoming_message": request.message, "channel": request.channel},
        )
        
        loop = asyncio.get_event_loop()
        result_state = await loop.run_in_executor(None, lambda: conversation_agent(state))
        
        transcript = result_state.get("conversation_transcript") or []
        conversation_entities = result_state.get("conversation_entities") or {}
        metadata = result_state.get("metadata") or {}
        ai_response = latest_assistant_message(transcript)
        conversation = {
            "conversation_id": metadata.get("conversation_id"),
            "lead_id": request.lead_id,
            "transcript": transcript,
            "entities": conversation_entities,
            "objection_summary": metadata.get("objection_summary"),
            "suggested_close_angle": metadata.get("suggested_close_angle"),
            "escalated": result_state.get("is_escalated", False),
            "updated_at": datetime.utcnow().isoformat(),
        }
        return {
            "success": True,
            "lead_id": request.lead_id,
            "lead": build_frontend_lead(
                lead_data,
                result_state.get("enrichment") or {},
                result_state.get("intent") or {},
                result_state.get("scoring") or {},
            ),
            "conversation": conversation,
            "response": {
                "message": ai_response,
            },
            "ai_response": ai_response,
            "needs_escalation": result_state.get("is_escalated", False),
            "escalation_reason": metadata.get("objection_summary"),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Conversation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _build_prospect_analysis_bundle(
    lead_context: Optional[Dict[str, Any]] = None,
    ops_state: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    lead_context = lead_context or {}
    ops_state = ops_state or {}
    top_issue = lead_context.get("top_issue") or "booking drop-off on WhatsApp"
    next_best_action = lead_context.get("next_best_action") or (
        "understand the clinic workflow before suggesting any change"
    )
    niche = ops_state.get("niche") or "Derm & Aesthetic clinic"
    city = ops_state.get("city")
    decision_maker_name = lead_context.get("decision_maker_name")
    decision_maker_role = lead_context.get("decision_maker_role")

    return {
        "guidance": {
            "top_issue": top_issue,
            "next_best_action": next_best_action,
            "recommended_channel": "whatsapp",
        },
        "facts": {
            "top_issue": top_issue,
            "next_best_action": next_best_action,
            "decision_maker_name": decision_maker_name,
            "decision_maker_role": decision_maker_role,
            "recommended_channel": "whatsapp",
        },
        "agent_context": {
            "business_summary": f"Early-stage sales thread for a {niche} lead.",
            "conversion_summary": f"Primary commercial angle: {top_issue}.",
            "known_pain_points": [top_issue],
            "trust_markers": [city] if city else [],
            "decision_maker_name": decision_maker_name,
            "decision_maker_role": decision_maker_role,
            "recommended_offer": "WhatsApp enquiry handling and booking conversion",
            "recommended_channel": "whatsapp",
            "recommended_next_step": next_best_action,
        },
        "scores": {
            "final_score": lead_context.get("final_score"),
            "preview_match_score": lead_context.get("preview_match_score"),
        },
    }


def _should_use_fast_prospect_opening(message: str, entities: Dict[str, Any]) -> bool:
    normalized = str(message or "").strip().lower()
    if not normalized:
        return True

    greeting_only = normalized in {
        "hi",
        "hii",
        "hello",
        "hey",
        "yo",
        "good morning",
        "good afternoon",
        "good evening",
    }
    very_short = len(normalized.split()) <= 3
    has_real_signal = bool(
        (entities.get("pain_points") or [])
        or (entities.get("objection_categories") or [])
        or entities.get("requested_next_step")
        or entities.get("pain_confirmed")
    )
    return greeting_only or (very_short and not has_real_signal)


def _build_prospect_fast_opening(message: str, ops_state: Optional[Dict[str, Any]] = None) -> str:
    normalized = str(message or "").strip().lower()
    ops_state = ops_state or {}
    niche = str(ops_state.get("niche") or "").strip().lower()
    clinic_label = "clinic"
    if "hospital" in niche:
        clinic_label = "hospital"
    elif "dental" in niche or "dent" in niche:
        clinic_label = "dental clinic"
    elif niche:
        clinic_label = "clinic"

    if any(token in normalized for token in ("booking", "appointment", "consultation")):
        return (
            "Understood. Is this for one clinic or multiple branches, and do you want WhatsApp "
            "to just capture enquiries or help confirm bookings too?"
        )

    return (
        f"Hi, this is ZRAI. Is this for one {clinic_label} or multiple branches, and is the main need "
        "enquiry capture, booking, or follow-up on WhatsApp?"
    )


@app.post("/api/v1/conversation/prospect")
async def handle_prospect_conversation(
    request: ProspectConversationRequest,
    user_id: Optional[str] = Depends(get_user_id),
):
    """Handle fast clinic-sales reasoning for unlinked WhatsApp prospect threads."""
    try:
        conversation_agent = get_conversation_agent()
        channel = normalize_channel(request.channel)
        lead_context = request.lead_context or {}
        ops_state = request.ops_state or {}

        synthetic_lead = {
            "lead_id": uuid4(),
            "business_name": (
                lead_context.get("company_name")
                or request.contact_name
                or "Clinic prospect"
            ),
            "category": ops_state.get("niche") or "clinic",
            "location": ops_state.get("city"),
        }
        analysis_bundle = _build_prospect_analysis_bundle(
            lead_context=lead_context,
            ops_state=ops_state,
        )

        transcript = conversation_agent._hydrate_transcript(
            [
                {"role": item.role, "message": item.message}
                for item in request.transcript[-6:]
            ]
        )
        entities = conversation_agent._hydrate_entities(request.entities or {})

        conversation = Conversation(
            conversation_id=uuid4(),
            lead_id=synthetic_lead["lead_id"],
            transcript=transcript,
            entities=entities,
        )
        conversation.transcript.append(
            ConversationMessage(
                role="prospect",
                message=request.message,
            )
        )

        entities = conversation_agent._extract_entities(
            request.message,
            conversation.entities,
            channel=channel,
            lead=synthetic_lead,
        )
        seed_signals = classify_sales_signals(request.message)
        if seed_signals.get("lead_channels"):
            entities.lead_channels = list(
                dict.fromkeys([*entities.lead_channels, *seed_signals["lead_channels"]])
            )
        entities.current_channel = channel
        entities.stage = infer_sales_stage(entities.model_dump())
        conversation.entities = entities

        if _should_use_fast_prospect_opening(request.message, entities.model_dump()):
            ai_response = _build_prospect_fast_opening(
                request.message,
                ops_state=ops_state,
            )
            conversation.transcript.append(
                ConversationMessage(
                    role="ai",
                    message=ai_response,
                )
            )
            return {
                "success": True,
                "conversation": {
                    "conversation_id": str(conversation.conversation_id),
                    "entities": conversation.entities.model_dump(),
                },
                "ai_response": ai_response,
                "needs_escalation": False,
                "escalation_reason": None,
            }

        should_escalate, escalation_reasons = conversation_agent._check_escalation_criteria(
            entities,
            request.message,
        )

        if entities.opt_out:
            ai_response = build_sales_fallback_response(
                entities.model_dump(),
                analysis_bundle,
            )
        else:
            try:
                ai_response = conversation_agent._generate_response(
                    conversation,
                    synthetic_lead,
                    request.message,
                    analysis_bundle,
                    channel,
                )
            except Exception as exc:
                logger.error(f"Prospect conversation response generation error: {exc}")
                ai_response = build_sales_fallback_response(
                    entities.model_dump(),
                    analysis_bundle,
                )

        conversation.transcript.append(
            ConversationMessage(
                role="ai",
                message=ai_response,
            )
        )

        return {
            "success": True,
            "conversation": {
                "conversation_id": str(conversation.conversation_id),
                "entities": conversation.entities.model_dump(),
            },
            "ai_response": ai_response,
            "needs_escalation": should_escalate,
            "escalation_reason": ", ".join(escalation_reasons) if escalation_reasons else None,
        }
    except Exception as e:
        logger.error(f"Prospect conversation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/conversation/sync")
async def sync_conversation(
    request: ConversationSyncRequest,
    user_id: Optional[str] = Depends(get_user_id),
):
    """Persist a human/AI/prospect message into canonical lead conversation memory."""
    try:
        db = get_db()
        try:
            normalized_lead_id = str(UUID(str(request.lead_id)))
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="Invalid lead_id")

        lead_data = db.get_lead(normalized_lead_id)
        if not lead_data:
            raise HTTPException(status_code=404, detail="Lead not found")

        conversation = sync_conversation_message(
            db,
            lead_id=normalized_lead_id,
            role=request.role,
            message=request.message,
            channel=request.channel,
            conversation_id=request.conversation_id,
        )

        return {
            "success": True,
            "conversation": conversation,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Conversation sync error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/leads/resolve-contact")
async def resolve_contact(
    request: ResolveContactRequest,
    user_id: Optional[str] = Depends(get_user_id),
):
    """Resolve a WhatsApp/public contact against the known lead set."""
    try:
        db = get_db()
        match = resolve_contact_to_lead(
            db,
            contact_phone=request.contact_phone,
            contact_name=request.contact_name,
            max_candidates=request.max_candidates,
        )
        return {
            "success": True,
            "match": match,
        }
    except Exception as e:
        logger.error(f"Resolve contact error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/whatsapp/policy/guard")
async def guard_whatsapp_policy(
    request: WhatsAppPolicyGuardRequest,
    user_id: Optional[str] = Depends(get_user_id),
):
    """Railway-first WhatsApp outbound policy guard."""
    normalized_body = _normalize_whatsapp_body(request.body)
    if not normalized_body:
        return {
            "allowed": False,
            "reason": "message_body_required",
            "detail": "Message body is required",
            "status": 400,
        }

    if _whatsapp_manual_kill_switch_enabled():
        return {
            "allowed": False,
            "reason": "manual_kill_switch_active",
            "detail": "WhatsApp outbound kill switch is enabled",
            "status": 503,
        }

    runtime_block = _whatsapp_get_runtime_kill_switch_reason()
    if runtime_block:
        return {
            "allowed": False,
            "reason": "runtime_kill_switch_active",
            "detail": f"WhatsApp outbound runtime kill switch is active ({runtime_block})",
            "status": 503,
        }

    db = get_db()
    conversation = _whatsapp_get_conversation(
        db,
        conversation_id=request.conversation_id,
        contact_phone=request.contact_phone,
        business_phone=request.business_phone,
    )
    if not conversation:
        return {
            "allowed": False,
            "reason": "conversation_not_found",
            "detail": "WhatsApp conversation not found for outbound policy check",
            "status": 404,
        }

    automation_kind = request.automation_kind or "manual"
    if automation_kind != "manual":
        if _whatsapp_has_impersonation_risk(normalized_body):
            return {
                "allowed": False,
                "reason": "automation_impersonation_risk",
                "detail": "Automated WhatsApp messages cannot imitate a human operator or clinic staff",
                "status": 409,
            }

        prior_messages = (
            db.client.table("WhatsAppMessage")
            .select("id, direction, authorType")
            .eq("conversationId", conversation.get("id"))
            .execute()
        ).data or []
        has_prior_automated = any(
            msg.get("direction") == "outgoing" and msg.get("authorType") == "bot"
            for msg in prior_messages
        )
        if not has_prior_automated and not _whatsapp_has_disclosure(normalized_body):
            return {
                "allowed": False,
                "reason": "automation_disclosure_required",
                "detail": "The first automated WhatsApp message must identify ZRAI as an automated assistant",
                "status": 409,
            }

    now = datetime.utcnow()
    global_outbound = _whatsapp_count_recent_outbound_global(
        db, since=now - timedelta(seconds=60)
    )
    if global_outbound >= WHATSAPP_POLICY_LIMITS["global_per_minute"]:
        _whatsapp_trip_runtime_kill_switch("global_minute_limit")
        return {
            "allowed": False,
            "reason": "global_minute_limit",
            "detail": "Global outbound rate limit reached",
            "status": 429,
        }

    contact_phone = conversation.get("contactPhone") or request.contact_phone
    if contact_phone:
        per_user_outbound = _whatsapp_count_recent_outbound_for_contact(
            db, contact_phone=contact_phone, since=now - timedelta(hours=1)
        )
        if per_user_outbound >= WHATSAPP_POLICY_LIMITS["per_user_hour"]:
            return {
                "allowed": False,
                "reason": "per_user_hour_limit",
                "detail": "This contact already received the hourly message limit",
                "status": 429,
            }

    recent_duplicate = _whatsapp_find_recent_duplicate(
        db,
        conversation_id=conversation.get("id"),
        body=normalized_body,
        since=now - timedelta(milliseconds=WHATSAPP_POLICY_LIMITS["duplicate_window_ms"]),
    )
    if recent_duplicate:
        return {
            "allowed": False,
            "reason": "duplicate_recently_sent",
            "detail": "Duplicate WhatsApp message blocked in short interval",
            "status": 409,
        }

    if request.message_style == "freeform":
        latest_inbound = _whatsapp_latest_inbound_at(
            db, conversation_id=conversation.get("id")
        )
        if not latest_inbound or (now - latest_inbound).total_seconds() * 1000 > WHATSAPP_POLICY_LIMITS["freeform_window_ms"]:
            return {
                "allowed": False,
                "reason": "customer_service_window_closed",
                "detail": "Free-form WhatsApp messages are only allowed inside the 24-hour customer service window",
                "status": 409,
            }

    if automation_kind == "campaign" and not _whatsapp_cold_outbound_override_enabled():
        latest_inbound = _whatsapp_latest_inbound_at(
            db, conversation_id=conversation.get("id")
        )
        if not latest_inbound:
            return {
                "allowed": False,
                "reason": "campaign_opt_in_required",
                "detail": "Automated WhatsApp campaigns require a prior inbound message or explicit policy override",
                "status": 409,
            }

    return {
        "allowed": True,
        "conversationId": conversation.get("id"),
        "contactPhone": conversation.get("contactPhone"),
        "businessPhone": conversation.get("businessPhone") or None,
    }

# ============================================================================
# Governance Endpoint
# ============================================================================

@app.get("/api/v1/governance")
async def get_governance_status(
    user_id: Optional[str] = Depends(get_user_id),
):
    """Get current governance status."""
    try:
        from src.config import load_config
        
        db = get_db()
        config = load_config()
        
        # Get current usage metrics
        today = datetime.utcnow()
        metrics = db.get_or_create_usage_metrics(today)
        
        # Get circuit breaker states
        circuit_breakers = {}
        for agent in ["discovery", "enrichment", "audit", "outreach"]:
            cb = db.get_circuit_breaker(agent)
            circuit_breakers[agent] = cb.get("state", "CLOSED") if cb else "CLOSED"
        
        agent_health = [
            {
                "agent_name": agent,
                "status": "degraded" if circuit_breakers.get(agent) != "CLOSED" else "healthy",
                "circuit_breaker": circuit_breakers.get(agent, "CLOSED").lower(),
                "avg_latency_ms": 0,
                "success_rate": 1.0 if circuit_breakers.get(agent) == "CLOSED" else 0.0,
                "last_error": None,
                "last_success_at": None,
            }
            for agent in ["discovery", "enrichment", "audit", "outreach"]
        ]

        budgets = {
            "llm_tokens": {
                "used": metrics.get("llm_tokens_used", 0),
                "limit": config.budget.daily_llm_token_limit,
            },
            "apify_runs": {
                "used": metrics.get("scraper_runs_used", 0),
                "limit": config.budget.daily_scraper_run_limit,
            },
            "browser_sessions": {
                "used": metrics.get("browser_sessions_used", 0),
                "limit": config.budget.daily_browser_session_limit,
            },
        }

        return {
            "success": True,
            "budget": {
                "llm_tokens_used": budgets["llm_tokens"]["used"],
                "llm_tokens_limit": budgets["llm_tokens"]["limit"],
                "browser_sessions_used": budgets["browser_sessions"]["used"],
                "browser_sessions_limit": budgets["browser_sessions"]["limit"],
                "scraper_runs_used": budgets["apify_runs"]["used"],
                "scraper_runs_limit": budgets["apify_runs"]["limit"],
            },
            "budgets": budgets,
            "rate_limits": [],
            "circuit_breakers": circuit_breakers,
            "agent_health": agent_health,
            "kill_switches": {
                "global": config.kill_switches.global_kill,
                "discovery": config.kill_switches.discovery_kill,
                "audit": config.kill_switches.audit_kill,
                "outreach": config.kill_switches.outreach_kill,
            },
        }
    except Exception as e:
        logger.error(f"Governance error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# Pipeline Run Endpoint
# ============================================================================

@app.post("/api/v1/run")
async def run_pipeline(
    request: RunPipelineRequest,
    user_id: Optional[str] = Depends(get_user_id),
):
    """Trigger a pipeline run."""
    logger.info(f"Pipeline run request: mode={request.mode}")
    
    try:
        from uuid import UUID
        
        orchestrator = get_orchestrator()
        
        run_id = request.run_id or str(uuid4())
        
        # For full pipeline, we need leads to process
        db = get_db()
        
        if request.mode == "full":
            # Get unprocessed leads
            leads = db.get_leads(status="discovered", limit=request.limit or 10)
            
            results = []
            for lead in leads:
                lead_id = lead.get("lead_id")
                if lead_id:
                    try:
                        loop = asyncio.get_event_loop()
                        result = await loop.run_in_executor(
                            None,
                            lambda lid=lead_id: orchestrator.process_lead(UUID(lid))
                        )
                        results.append({
                            "lead_id": lead_id,
                            "status": "completed",
                            "stage": result.current_stage if result else "unknown",
                        })
                    except Exception as e:
                        results.append({
                            "lead_id": lead_id,
                            "status": "error",
                            "error": str(e),
                        })
            
            return {
                "success": True,
                "run_id": run_id,
                "mode": request.mode,
                "processed": len(results),
                "results": results,
            }
        
        elif request.mode == "dry_run":
            # Dry run mode - simulate without writes
            leads = db.get_leads(status="discovered", limit=request.limit or 5)
            
            results = []
            for lead in leads:
                lead_id = lead.get("lead_id")
                if lead_id:
                    try:
                        loop = asyncio.get_event_loop()
                        result = await loop.run_in_executor(
                            None,
                            lambda lid=lead_id: orchestrator.dry_run(UUID(lid))
                        )
                        stage = (
                            result.get("current_stage")
                            if isinstance(result, dict)
                            else getattr(result, "current_stage", "unknown")
                        )
                        results.append({
                            "lead_id": lead_id,
                            "status": "simulated",
                            "stage": stage if result else "unknown",
                        })
                    except Exception as e:
                        results.append({
                            "lead_id": lead_id,
                            "status": "error",
                            "error": str(e),
                        })
            
            return {
                "success": True,
                "run_id": run_id,
                "mode": request.mode,
                "processed": len(results),
                "results": results,
            }
        
        else:
            return {
                "success": True,
                "run_id": run_id,
                "mode": request.mode,
                "message": f"Mode '{request.mode}' acknowledged",
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Pipeline run error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# Leads Endpoint
# ============================================================================

@app.get("/api/v1/leads")
async def get_leads(
    page: int = 1,
    page_size: int = 20,
    niche: Optional[str] = None,
    geo: Optional[str] = None,
    status: Optional[str] = None,
    min_score: Optional[float] = None,
    user_id: Optional[str] = Depends(get_user_id),
):
    """Get paginated list of leads."""
    try:
        db = get_db()
        
        # Calculate offset
        offset = (page - 1) * page_size
        
        # Get leads from database
        leads = db.get_leads(
            niche=niche,
            geo=geo,
            status=status,
            min_score=min_score,
            limit=page_size,
            offset=offset,
        )
        leads = [
            lead
            for lead in leads
            if not _looks_like_search_query_name(str(lead.get("business_name") or ""))
        ]
        
        # Get total count
        total = db.count_leads(niche=niche, geo=geo, status=status, min_score=min_score)
        
        return {
            "success": True,
            "leads": leads,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": (total + page_size - 1) // page_size,
            },
        }
    except Exception as e:
        logger.error(f"Get leads error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/leads/{lead_id}")
async def get_lead(
    lead_id: str,
    user_id: Optional[str] = Depends(get_user_id),
):
    """Get a single lead by ID."""
    try:
        db = get_db()
        normalized_lead_id = normalize_lead_id_value(lead_id)
        lead = db.get_lead(normalized_lead_id)
        
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")

        processed_details = get_processed_details_for_lead(db, normalized_lead_id)
        lead_model = lead_data_to_model(lead)
        source = infer_discovery_source_from_niche(lead.get("category") or "")
        preview = build_discovery_preview(
            lead.get("category") or lead.get("business_name") or "",
            lead_model,
        )
        frontend_lead = build_frontend_lead(
            lead,
            processed_details.get("enrichment") or {},
            processed_details.get("intent") or {},
            processed_details.get("scoring") or {},
            processed_details.get("signal_facts") or {},
            processed_details.get("analysis_state"),
            processed_details.get("analysis_updated_at"),
        )
        if processed_details.get("analysis_state") == "analyzed":
            frontend_lead = attach_final_metadata(
                frontend_lead,
                discovery_source=source,
                verified_fit=preview.get("verified_fit"),
                preview_score=preview.get("score"),
                preview_summary=preview.get("summary"),
                contact_paths=preview.get("contact_paths") or [],
                proof=processed_details.get("proof") or {},
                analysis_state=processed_details.get("analysis_state"),
                analysis_updated_at=processed_details.get("analysis_updated_at"),
                signal_facts=processed_details.get("signal_facts") or {},
                intent=processed_details.get("intent") or {},
            )
        else:
            frontend_lead = attach_preview_metadata(
                frontend_lead,
                verified_fit=preview.get("verified_fit"),
                discovery_source=source,
                preview_score=preview.get("score"),
                preview_summary=preview.get("summary"),
                contact_paths=preview.get("contact_paths") or [],
            )
        return {
            "success": True,
            "lead": frontend_lead,
            "processed_details": processed_details,
            "signal_facts": processed_details.get("signal_facts") or {},
            "analysis_state": processed_details.get("analysis_state"),
            "analysis_updated_at": processed_details.get("analysis_updated_at"),
            "signals_version": processed_details.get("signals_version"),
            "analysis_bundle": processed_details.get("analysis_bundle"),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get lead error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# Metrics Endpoint
# ============================================================================

@app.get("/api/v1/metrics")
async def get_metrics(
    period: str = "daily",
    user_id: Optional[str] = Depends(get_user_id),
):
    """Get system metrics."""
    try:
        db = get_db()
        
        # Get current usage metrics
        today = datetime.utcnow()
        metrics = db.get_or_create_usage_metrics(today)
        
        # Get lead counts by status
        lead_counts = db.get_lead_counts_by_status()
        
        # Get recent activity
        recent_leads = db.get_leads(limit=5)
        
        return {
            "success": True,
            "period": period,
            "usage": {
                "llm_calls": metrics.get("llm_calls_used", 0),
                "browser_sessions": metrics.get("browser_sessions_used", 0),
                "scraper_calls": metrics.get("scraper_calls_used", 0),
                "emails_sent": metrics.get("emails_sent", 0),
            },
            "leads": {
                "total": sum(lead_counts.values()) if lead_counts else 0,
                "by_status": lead_counts or {},
            },
            "recent_activity": [
                {
                    "lead_id": l.get("lead_id"),
                    "business_name": l.get("business_name"),
                    "status": l.get("lead_lifecycle_state"),
                    "updated_at": l.get("updated_at"),
                }
                for l in recent_leads
            ],
        }
    except Exception as e:
        logger.error(f"Get metrics error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(
        "src.api.server:app",
        host="0.0.0.0",
        port=port,
        reload=True,
    )
