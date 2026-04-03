"""
ZRAI Lead OS - FastAPI Server

Exposes the LangGraph pipeline via REST API for the frontend.
"""

import os
import logging
import asyncio
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager
from uuid import uuid4, UUID
from datetime import datetime
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
SIGNALS_VERSION = "clinic_intel_v1"

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


class AnalyzeLeadRequest(BaseModel):
    lead_id: str = Field(..., description="Lead ID to analyze")
    include_outreach: bool = True

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


def build_contact_rows(lead_data: Dict[str, Any], enrichment: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Build lightweight frontend contact rows from lead/enrichment data."""
    emails = []
    if enrichment:
        emails = enrichment.get("validated_emails") or []
    if not emails:
        emails = lead_data.get("emails_found") or []

    contact_name = enrichment.get("decision_maker_name") if enrichment else None
    phone = (enrichment or {}).get("normalized_phone") or lead_data.get("phone")

    contacts = []
    for index, email in enumerate(emails):
        contacts.append(
            {
                "id": f"{lead_data.get('lead_id')}-contact-{index}",
                "lead_id": str(lead_data.get("lead_id")),
                "name": contact_name or lead_data.get("business_name") or "Primary contact",
                "title": "Decision maker" if contact_name else None,
                "email": email,
                "phone": phone,
                "linkedin_url": (enrichment or {}).get("decision_maker_linkedin"),
                "is_primary": index == 0,
                "created_at": lead_data.get("created_at") or datetime.utcnow().isoformat(),
            }
        )

    if not contacts and phone:
        contacts.append(
            {
                "id": f"{lead_data.get('lead_id')}-phone",
                "lead_id": str(lead_data.get("lead_id")),
                "name": contact_name or lead_data.get("business_name") or "Primary contact",
                "title": "Phone contact",
                "email": None,
                "phone": phone,
                "linkedin_url": (enrichment or {}).get("decision_maker_linkedin"),
                "is_primary": True,
                "created_at": lead_data.get("created_at") or datetime.utcnow().isoformat(),
            }
        )

    return contacts


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


def _pick_best_email(emails: List[Any], website: Optional[str]) -> Optional[str]:
    deduped = _dedupe_strings(emails)
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
    }
    tokens = [token.lower() for token in re.findall(r"[A-Za-z]+", str(value))]
    significant_tokens = [token for token in tokens if len(token) > 1]
    if len(significant_tokens) < 2:
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
    if whatsapp_detected and (whatsapp_target or phone_numbers):
        return "whatsapp", "WhatsApp is already present on the clinic flow and should get the fastest response."
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
            if not value:
                continue
            if isinstance(value, list):
                existing = list(merged.get(key) or [])
                merged[key] = _dedupe_strings(existing + list(value))
            else:
                merged[key] = value
    return merged


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

    if lead_state and lead_state.get("current_stage") in {"enrichment", "intent", "audit", "scoring", "outreach"}:
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
    ads_verification = lead_state_metadata.get("ads_verification") or {}
    people_intelligence = dict(lead_state_metadata.get("people_intelligence") or {})

    phone_numbers = _dedupe_strings(
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
    whatsapp_detected = bool(
        whatsapp_target
        or enrichment_payload.get("whatsapp_detected")
        or proof_extraction.get("chat_widget") == "whatsapp"
        or enrichment_payload.get("chat_widget") == "whatsapp"
        or "whatsapp" in [path.lower() for path in contact_paths]
    )
    chat_widget_type = (
        "whatsapp"
        if whatsapp_detected
        else proof_extraction.get("chat_widget") or enrichment_payload.get("chat_widget")
    )

    if ads_verification.get("status") in {"yes", "no", "not_checked"}:
        ads_status = ads_verification.get("status")
    elif lead_data.get("ad_last_seen") or lead_data.get("ad_start_date"):
        ads_status = "yes" if lead_data.get("ads_active") else "not_checked"
    else:
        ads_status = "not_checked"

    ads_channels = _dedupe_strings(list(ads_verification.get("channels") or []))
    ads_last_seen = ads_verification.get("last_seen") or lead_data.get("ad_last_seen")

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
    doctor_profiles = list(people_intelligence.get("doctor_profiles") or []) or list(stored_signal_facts.get("doctor_profiles") or [])
    decision_maker_candidates = list(people_intelligence.get("decision_maker_candidates") or []) or list(stored_signal_facts.get("decision_maker_candidates") or [])
    branch_contacts = list(people_intelligence.get("branch_contacts") or []) or list(stored_signal_facts.get("branch_contacts") or [])
    contact_evidence = _dedupe_strings(
        list(people_intelligence.get("contact_evidence") or [])
        + list(stored_signal_facts.get("contact_evidence") or [])
    )
    branch_names = _dedupe_strings(
        list(proof_extraction.get("branch_names") or [])
        + list(people_intelligence.get("branch_names") or [])
        + list(stored_signal_facts.get("branch_names") or [])
        + [
            contact.get("name")
            for contact in branch_contacts
            if isinstance(contact, dict)
        ]
    )
    doctor_names = _dedupe_strings(
        list(proof_extraction.get("doctor_names") or [])
        + list(people_intelligence.get("doctor_names") or [])
        + list(stored_signal_facts.get("doctor_names") or [])
        + [
            profile.get("name")
            for profile in doctor_profiles
            if isinstance(profile, dict)
        ]
    )
    multi_clinic = bool(proof_extraction.get("multi_clinic") or len(branch_names) > 1)
    branch_count = proof_extraction.get("branch_count")
    if not isinstance(branch_count, int):
        branch_count = len(branch_names)
    doctor_count = proof_extraction.get("doctor_count")
    if not isinstance(doctor_count, int):
        doctor_count = len(doctor_names)
    instagram_present = bool(
        proof_extraction.get("instagram_present")
        or social_profiles.get("instagram")
        or lead_data.get("instagram")
    )
    youtube_present = bool(proof_extraction.get("youtube_present") or social_profiles.get("youtube"))
    testimonials_present = bool(proof_extraction.get("testimonials_present"))
    gallery_present = bool(proof_extraction.get("gallery_present"))
    after_hours_capture = bool(proof_extraction.get("after_hours_capture"))
    instant_response_path = bool(
        proof_extraction.get("instant_response_path")
        or whatsapp_detected
        or chat_widget_type
        or booking_detected
    )
    content_ready_score = proof_extraction.get("content_ready_score")
    raw_booking_flow_quality = str(proof_extraction.get("booking_flow_quality") or "").strip().lower()
    if booking_detected and raw_booking_flow_quality in {"", "none", "unknown", "n/a"}:
        booking_flow_quality = "strong" if contact_form_detected else "basic"
    elif raw_booking_flow_quality in {"strong", "basic", "weak", "none"}:
        booking_flow_quality = raw_booking_flow_quality
    else:
        booking_flow_quality = (
            "strong" if booking_detected and contact_form_detected else "basic" if booking_detected else "none"
        )

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
        + ([stored_signal_facts.get("best_contact_email")] if stored_signal_facts.get("best_contact_email") else [])
    )
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
        or stored_signal_facts.get("decision_maker_name")
    )
    if not decision_maker_name and doctor_names:
        decision_maker_name = doctor_names[0]
    decision_maker_linkedin = (
        enrichment_payload.get("decision_maker_linkedin")
        or people_intelligence.get("decision_maker_linkedin")
        or people_intelligence.get("best_contact_linkedin")
        or ranked_candidate.get("linkedin")
        or stored_signal_facts.get("decision_maker_linkedin")
    )
    decision_maker_role = (
        enrichment_payload.get("decision_maker_role")
        or people_intelligence.get("decision_maker_role")
        or ranked_candidate.get("role")
        or stored_signal_facts.get("decision_maker_role")
    )
    decision_maker_source = (
        enrichment_payload.get("decision_maker_source")
        or ranked_candidate.get("source")
        or stored_signal_facts.get("decision_maker_source")
    )
    decision_maker_confidence = (
        enrichment_payload.get("decision_maker_confidence")
        or (min(float(ranked_candidate.get("score", 0)) / 100.0, 0.98) if ranked_candidate else None)
        or stored_signal_facts.get("decision_maker_confidence")
    )
    if decision_maker_name and not _is_plausible_person_name(str(decision_maker_name)):
        decision_maker_name = None
        decision_maker_role = None
        decision_maker_source = None
        decision_maker_confidence = None
    best_contact_phone = (
        people_intelligence.get("best_contact_phone")
        or (phone_numbers[0] if phone_numbers else None)
        or stored_signal_facts.get("best_contact_phone")
    )
    best_contact_email = (
        people_intelligence.get("best_contact_email")
        or _pick_best_email(
            email_contacts,
            lead_data.get("website") or lead_data.get("landing_page_url"),
        )
        or stored_signal_facts.get("best_contact_email")
    )
    best_contact_linkedin = (
        people_intelligence.get("best_contact_linkedin")
        or ranked_candidate.get("linkedin")
        or decision_maker_linkedin
        or stored_signal_facts.get("best_contact_linkedin")
    )
    if not decision_maker_name and doctor_names:
        plausible_doctors = [name for name in doctor_names if _is_plausible_person_name(str(name))]
        if plausible_doctors:
            decision_maker_name = plausible_doctors[0]
            decision_maker_role = decision_maker_role or "primary_doctor_contact"
            decision_maker_source = decision_maker_source or "doctor_roster"
            decision_maker_confidence = decision_maker_confidence or 0.55
    recommended_channel, best_contact_reason = _derive_best_contact_channel(
        phone_numbers=phone_numbers,
        best_contact_email=best_contact_email,
        whatsapp_detected=whatsapp_detected,
        whatsapp_target=str(whatsapp_target) if whatsapp_target else None,
        decision_maker_linkedin=str(best_contact_linkedin or decision_maker_linkedin) if (best_contact_linkedin or decision_maker_linkedin) else None,
    )
    if not recommended_channel:
        recommended_channel = stored_signal_facts.get("best_contact_channel")
    if not best_contact_reason:
        best_contact_reason = stored_signal_facts.get("best_contact_reason")

    return {
        "phone_visible": phone_visible,
        "phone_numbers": phone_numbers,
        "booking_detected": booking_detected,
        "booking_target": str(booking_target) if booking_target else None,
        "contact_form_detected": contact_form_detected,
        "whatsapp_detected": whatsapp_detected,
        "whatsapp_target": str(whatsapp_target) if whatsapp_target else None,
        "chat_widget_type": str(chat_widget_type) if chat_widget_type else None,
        "ads_status": ads_status,
        "ads_channels": ads_channels,
        "ads_last_seen": str(ads_last_seen) if ads_last_seen else None,
        "reviews_count": lead_data.get("reviews_count") or lead_data.get("review_count"),
        "rating": lead_data.get("rating") or lead_data.get("review_rating"),
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
        "doctor_count": doctor_count,
        "doctor_names": doctor_names,
        "doctor_profiles": doctor_profiles,
        "instagram_present": instagram_present,
        "youtube_present": youtube_present,
        "testimonials_present": testimonials_present,
        "gallery_present": gallery_present,
        "content_ready_score": content_ready_score,
        "booking_flow_quality": booking_flow_quality,
        "after_hours_capture": after_hours_capture,
        "instant_response_path": instant_response_path,
        "confidence_by_signal": {
            "phone": 1.0 if phone_numbers else 0.0,
            "booking": 0.95 if booking_target else 0.7 if booking_detected else 0.0,
            "contact_form": 0.8 if contact_form_detected else 0.0,
            "whatsapp": 0.95 if whatsapp_target else 0.7 if whatsapp_detected else 0.0,
            "ads": 1.0 if ads_status in {"yes", "no"} else 0.25,
            "reviews": 0.95 if lead_data.get("reviews_count") is not None else 0.0,
            "services": 0.8 if services else 0.0,
            "multi_clinic": 0.85 if multi_clinic else 0.5 if branch_count else 0.0,
            "doctors": 0.85 if doctor_names else 0.0,
            "social": 0.75 if social_profiles else 0.0,
        },
        "decision_maker_name": str(decision_maker_name) if decision_maker_name else None,
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
            "reviews_count": lead_data.get("reviews_count") or lead_data.get("review_count"),
            "rating": lead_data.get("rating") or lead_data.get("review_rating"),
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
            "reviews_count": lead_data.get("reviews_count") or lead_data.get("review_count"),
            "rating": lead_data.get("rating") or lead_data.get("review_rating"),
            "content_ready_score": content_ready_score,
            "branch_count": branch_count,
        }),
        "scoring_context": {
            "final_score": (scoring or {}).get("final_score"),
            "lead_tier": (scoring or {}).get("lead_tier"),
            "contact_quality_score": enrichment_payload.get("contact_quality_score"),
        },
    }


def build_site_truth_summary_from_signal_facts(signal_facts: Optional[Dict[str, Any]]) -> Optional[str]:
    if not signal_facts:
        return None

    facts: List[str] = []
    facts.append("phone visible" if signal_facts.get("phone_visible") else "phone not detected")
    facts.append("booking detected" if signal_facts.get("booking_detected") else "no booking detected")

    if signal_facts.get("whatsapp_detected"):
        whatsapp_target = signal_facts.get("whatsapp_target")
        facts.append(
            f"WhatsApp detected ({whatsapp_target})" if whatsapp_target else "WhatsApp detected"
        )
    else:
        facts.append("no WhatsApp detected")

    contact_form_detected = signal_facts.get("contact_form_detected")
    if contact_form_detected:
        facts.append("contact form detected")
    if signal_facts.get("after_hours_capture"):
        facts.append("after-hours capture present")
    else:
        facts.append("no after-hours capture")
    if signal_facts.get("instant_response_path"):
        facts.append("instant response path present")
    else:
        facts.append("no instant response path")

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

    if signal_facts.get("multi_clinic"):
        branch_count = signal_facts.get("branch_count") or 0
        facts.append(f"multi-clinic ({branch_count} locations)" if branch_count else "multi-clinic")

    doctor_count = signal_facts.get("doctor_count")
    if isinstance(doctor_count, int) and doctor_count > 0:
        facts.append(f"{doctor_count} doctors detected")

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
        branch_count = signal_facts.get("branch_count") or 0
        positives.append(f"multi-location footprint ({branch_count} clinics)" if branch_count else "multi-location footprint")

    doctor_count = signal_facts.get("doctor_count")
    if isinstance(doctor_count, int) and doctor_count > 0:
        positives.append(f"visible doctor-led trust ({doctor_count} doctors)")

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
    if isinstance(content_ready_score, int) and content_ready_score >= 50:
        positives.append("content-ready brand")
    contact_intelligence = signal_facts.get("contact_intelligence") or {}
    top_contact = contact_intelligence.get("top_contact") or {}
    if top_contact.get("name"):
        contact_label = str(top_contact.get("contact_type") or top_contact.get("owner_scope") or "contact").replace("_", " ")
        positives.append(f"{top_contact.get('name')} ({contact_label})")
    contact_quality_score = signal_facts.get("contact_quality_score")
    if contact_quality_score is not None:
        try:
            positives.append(f"contact quality {int(float(contact_quality_score))}/100")
        except (TypeError, ValueError):
            pass

    if not signal_facts.get("phone_visible"):
        problems.append("phone is not prominent")
    if not signal_facts.get("whatsapp_detected"):
        problems.append("no WhatsApp capture path")
    booking_quality = str(signal_facts.get("booking_flow_quality") or "none").lower()
    if booking_quality in {"none", "weak"}:
        problems.append("booking path is weak")
    if not signal_facts.get("after_hours_capture"):
        problems.append("no after-hours capture")
    if not signal_facts.get("instant_response_path"):
        problems.append("no instant response path")

    volume_score = ((signal_facts.get("volume_score_inputs") or {}).get("volume_score"))
    summary_parts: List[str] = []
    if positives:
        summary_parts.append("This clinic looks commercially strong because it has " + ", ".join(positives[:3]) + ".")
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

    reviews = signal_facts.get("reviews_count") or 0
    rating = signal_facts.get("rating") or 0
    content_ready_score = signal_facts.get("content_ready_score") or 0
    branch_count = signal_facts.get("branch_count") or 0

    if not signal_facts.get("phone_visible"):
        return "Phone is not prominent"
    if not signal_facts.get("whatsapp_detected"):
        return "WhatsApp capture is missing"
    booking_quality = str(signal_facts.get("booking_flow_quality") or "none").lower()
    if not signal_facts.get("booking_detected") or booking_quality in {"none", "weak"}:
        return "Booking flow is weak"
    if not signal_facts.get("after_hours_capture"):
        return "No after-hours capture"
    if not signal_facts.get("instant_response_path"):
        return "No instant response path"
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

    reviews = signal_facts.get("reviews_count") or 0
    rating = signal_facts.get("rating") or 0
    content_ready_score = signal_facts.get("content_ready_score") or 0
    branch_count = signal_facts.get("branch_count") or 0

    if not signal_facts.get("phone_visible"):
        return "Make phone visible in header and hero"
    if not signal_facts.get("whatsapp_detected"):
        return "Add WhatsApp entry path and autoresponse"
    booking_quality = str(signal_facts.get("booking_flow_quality") or "none").lower()
    if not signal_facts.get("booking_detected") or booking_quality in {"none", "weak"}:
        return "Fix booking flow and confirmation path"
    if not signal_facts.get("instant_response_path"):
        return "Add instant response automation"
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

    return {
        "id": str(lead_data.get("lead_id")),
        "company_name": lead_data.get("business_name") or "Unknown",
        "domain": extract_domain(lead_data.get("website") or lead_data.get("landing_page_url")) or "",
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
    if proof_extraction.get("chat_widget") == "whatsapp" or proof_extraction.get("whatsapp_target"):
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
    if signal_facts is not None:
        payload["signal_facts"] = signal_facts
        payload["signals_version"] = SIGNALS_VERSION
    if intent:
        if intent.get("site_truth_summary") is not None:
            payload["site_truth_summary"] = intent.get("site_truth_summary")
        if intent.get("why_this_lead") is not None:
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

    reviews = signal_facts.get("reviews_count")
    rating = signal_facts.get("rating")
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
    best_contact_channel = signal_facts.get("best_contact_channel")
    best_contact_reason = signal_facts.get("best_contact_reason")
    contact_intelligence = signal_facts.get("contact_intelligence") or {}
    top_contact = contact_intelligence.get("top_contact") or {}

    trust_markers: List[str] = []
    pain_points: List[str] = []
    if isinstance(reviews, (int, float)) and reviews:
        trust_markers.append(f"{int(reviews)} reviews")
    if isinstance(rating, (int, float)) and rating:
        trust_markers.append(f"{float(rating):.1f} rating")
    if isinstance(branch_count, int) and branch_count > 1:
        trust_markers.append(f"{branch_count} locations")
    if isinstance(doctor_count, int) and doctor_count > 0:
        trust_markers.append(f"{doctor_count} doctors")
    if isinstance(content_ready_score, int) and content_ready_score >= 70:
        trust_markers.append("strong content readiness")
    if top_contact.get("name"):
        contact_label = str(top_contact.get("contact_type") or top_contact.get("owner_scope") or "contact").replace("_", " ")
        trust_markers.append(f"{top_contact.get('name')} ({contact_label})")
    contact_quality_score = signal_facts.get("contact_quality_score")
    if contact_quality_score is not None:
        try:
            trust_markers.append(f"contact quality {int(float(contact_quality_score))}/100")
        except (TypeError, ValueError):
            pass

    if not whatsapp_detected:
        pain_points.append("missing WhatsApp capture")
    if not booking_detected:
        pain_points.append("weak booking conversion")
    if signal_facts.get("contact_form_detected") is False and (
        (isinstance(reviews, (int, float)) and reviews >= 200)
        or (isinstance(content_ready_score, int) and content_ready_score >= 70)
        or (isinstance(branch_count, int) and branch_count > 1)
    ):
        pain_points.append("no fallback form for high-intent visitors")
    if not phone_visible:
        pain_points.append("phone not prominent")
    if not after_hours_capture:
        pain_points.append("after-hours response gap")
    if not instant_response_path:
        pain_points.append("no instant-response path")

    if not whatsapp_detected:
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
            "site_truth_summary": intent.get("site_truth_summary"),
            "why_this_lead": intent.get("why_this_lead"),
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
    if chat_widget == "whatsapp" or whatsapp_target:
        if whatsapp_target:
            facts.append(f"WhatsApp detected ({whatsapp_target})")
        else:
            facts.append("WhatsApp detected")
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
            return {
                "status": "yes",
                "channels": ["meta"],
                "last_seen": first_item.get("adSnapshotUrl")
                or first_item.get("startDate")
                or lead_data.get("ad_last_seen"),
                "evidence_url": first_item.get("adSnapshotUrl") or str(facebook_page),
                "source": "facebook_page_ads_scraper",
            }
        return {
            "status": "no",
            "channels": ["meta"],
            "last_seen": None,
            "evidence_url": str(facebook_page),
            "source": "facebook_page_ads_scraper",
        }
    except Exception as exc:
        logger.warning("Clinic ads verification failed for %s: %s", lead_data.get("business_name"), exc)
        return {
            "status": "not_checked",
            "channels": [],
            "last_seen": None,
            "evidence_url": str(facebook_page),
            "source": "facebook_page_ads_scraper_failed",
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
        if not scoring:
            return True

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

        has_upstream_signal = bool(intent) or bool(enrichment) or bool(proof)
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

    signal_facts = build_signal_facts(
        lead_data,
        enrichment=enrichment,
        intent=intent,
        proof=proof,
        scoring=scoring,
        lead_state=lead_state,
    )
    if intent or proof or signal_facts:
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
    if not digits:
        return None
    if len(digits) > 10:
        return digits[-10:]
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
        if signal_facts.get("decision_maker_name"):
            reasons.append(
                f"Decision maker candidate {signal_facts.get('decision_maker_name')}"
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
    existing_query = (
        db.client.table("leads")
        .select("*")
        .eq("business_name", lead.business_name)
        .eq("location", lead.location or "")
    )
    if lead.website:
        existing_query = existing_query.eq("website", lead.website)
    existing_result = existing_query.limit(1).execute()
    if existing_result.data:
        return existing_result.data[0]

    return db.create_lead(serialize_lead_for_storage(lead, raw_niche))


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
) -> Dict[str, Any]:
    """Run the heavy operator chain for a selected lead preview."""
    lead_payload = dict(lead_data)
    lead_state = db.get_lead_state(UUID(str(lead_data.get("lead_id")))) or {}
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
            "force_audit": True,
        },
    )

    enrichment_agent = get_enrichment_agent()
    intent_agent = get_intent_agent()
    audit_agent = get_audit_agent()
    scoring_agent = get_scoring_agent()
    outreach_agent = get_outreach_agent()

    state = enrichment_agent(state)
    state = intent_agent(state)
    state = audit_agent(state)

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
        state = outreach_agent(state)

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
) -> Dict[str, Any]:
    """Build a dict-based graph state with persisted related data."""
    lead_id = UUID(str(lead_data.get("lead_id")))
    lead_state = db.get_lead_state(lead_id) or {}
    enrichment = db.get_enrichment_data(lead_id) or {}
    intent = db.get_intent_data(lead_id) or {}
    scoring = db.get_scoring_result(lead_id) or {}
    proof = db.get_proof_artifact(lead_id) or {}
    conversations = db.get_conversations_for_lead(lead_id)
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
    return niche in OSINT_FIRST_NICHES


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
    else:
        candidates = [
            f"{geo} {raw_niche} companies",
            f'{geo} "{raw_niche}" software platform',
            f'{geo} "{raw_niche}" "request a demo"',
        ]

    max_queries = max(3, min(5, requested_limit))
    return candidates[:max_queries]


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
    hostname = domain.lower().replace("www.", "")
    stem = hostname.split(".")[0].replace("-", " ").replace("_", " ").strip()
    return " ".join(part.capitalize() for part in stem.split()) or domain


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

            company_name = result["title"].split("|")[0].split("-")[0].strip()
            if not company_name or len(company_name) < 3:
                company_name = infer_company_name_from_url(website)

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


def dedupe_discovered_leads(leads: List[Lead]) -> List[Lead]:
    """Collapse duplicate lead rows returned across multiple search variants."""
    deduped: List[Lead] = []
    seen = set()

    for lead in leads:
        dedupe_key = (
            (lead.business_name or "").strip().lower(),
            (extract_domain(lead.website) or "").strip().lower(),
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

    if niche == "saas":
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
    if any(token in website_text for token in ["whatsapp", "wa.me", "api.whatsapp.com"]):
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
    preview_score = min(combined_score * 5, 100)
    emails = extract_website_emails(website_text)
    phones = extract_website_phones(website_text)

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
    threshold = 55 if is_clinic_style_niche(raw_niche) else 60
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
        "orchestrator": hasattr(app.state, 'orchestrator') and app.state.orchestrator is not None,
        "discovery": hasattr(app.state, 'discovery_agent') and app.state.discovery_agent is not None,
        "enrichment": hasattr(app.state, 'enrichment_agent') and app.state.enrichment_agent is not None,
        "scoring": hasattr(app.state, 'scoring_agent') and app.state.scoring_agent is not None,
    }
    return {
        "status": "healthy" if all(agents_status.values()) else "degraded",
        "service": "zrai-lead-os",
        "agents": agents_status,
        "storage": "memory" if getattr(db, "is_memory_backend", False) else "supabase",
    }

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
            query_limit = min(max(request.limit * 2, 10), 30)

        if should_use_osint_discovery(request.niche):
            leads = await loop.run_in_executor(
                None,
                lambda: discover_company_candidates_osint(request.niche, request.geo, query_limit),
            )
        else:
            geo_filter = build_discovery_geo(request.geo)
            keywords = build_discovery_keywords(request.niche, query_limit)
            leads = await loop.run_in_executor(
                None,
                lambda: discovery_agent.discover_from_google_maps(
                    keywords=keywords,
                    geo=geo_filter,
                    limit=query_limit,
                    auto_process=False,
                    skip_duplicate_check=True,
                    detailed_scrape=False,
                )
            )

            if geo_filter.get("city"):
                leads = [lead for lead in leads if matches_requested_geo(request.geo, lead)]

        leads = dedupe_discovered_leads(leads)
        leads = rank_discovered_leads(request.niche, leads, request.limit)
        leads = await loop.run_in_executor(
            None,
            lambda: verify_discovered_leads(request.niche, leads, request.limit),
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
        
    except Exception as e:
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
        "Process selected leads request: count=%s, include_outreach=%s",
        len(request.lead_ids),
        request.include_outreach,
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
        "Analyze lead request: lead_id=%s, include_outreach=%s",
        request.lead_id,
        request.include_outreach,
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


def run_lead_analysis_background(lead_id: str, include_outreach: bool) -> None:
    """Run analysis outside the request/response window and persist success or failure state."""
    db = get_db()
    lead_data = db.get_lead(lead_id)
    if not lead_data:
        logger.warning("Background analysis skipped; lead not found: %s", lead_id)
        return

    try:
        execute_lead_analysis(db, lead_data, include_outreach=include_outreach)
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
        "Analyze lead async request: lead_id=%s, include_outreach=%s",
        request.lead_id,
        request.include_outreach,
    )

    try:
        db = get_db()
        normalized_lead_id = normalize_lead_id_value(request.lead_id)
        lead_data = db.get_lead(normalized_lead_id)
        if not lead_data:
            raise HTTPException(status_code=404, detail="Lead not found")

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
