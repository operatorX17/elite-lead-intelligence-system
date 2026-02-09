#!/usr/bin/env python3
"""
ZRAI ELITE INFRASTRUCTURE v1.0
================================
Trillion-Dollar Company Grade Architecture

This is the FOUNDATION for all future intelligence systems.
Modular, extensible, production-ready.

ARCHITECTURE:
┌─────────────────────────────────────────────────────────────┐
│                    ORCHESTRATOR AGENT                        │
│  (Routes tasks to specialized sub-agents)                   │
└─────────────────────────────────────────────────────────────┘
        │           │           │           │           │
        ▼           ▼           ▼           ▼           ▼
┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
│DISCOVERY │ │ENRICHMENT│ │   ADS    │ │ANALYSIS  │ │ OUTREACH │
│  AGENT   │ │  AGENT   │ │  AGENT   │ │  AGENT   │ │  AGENT   │
└──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘
        │           │           │           │           │
        ▼           ▼           ▼           ▼           ▼
┌─────────────────────────────────────────────────────────────┐
│                      TOOL REGISTRY                           │
│  Apify │ Firecrawl │ Steel │ OpenRouter │ Supabase │ ...    │
└─────────────────────────────────────────────────────────────┘

DESIGN PRINCIPLES:
1. Single Responsibility - Each agent does ONE thing well
2. Loose Coupling - Agents communicate via standardized messages
3. Plugin Architecture - Add new tools without changing core
4. Fail-Safe - Graceful degradation, never crash
5. Observable - Every action is logged and traceable

Author: ZRAI Architecture Team
"""

import os
import sys
import json
import logging
import hashlib
import asyncio
import ssl
import re
import time
from abc import ABC, abstractmethod
from pathlib import Path
from datetime import datetime, timezone
from typing import (
    Dict, Any, List, Optional, Callable, Type, TypeVar, 
    Union, Tuple, Protocol, runtime_checkable
)
from dataclasses import dataclass, field, asdict
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, as_completed
import urllib.request
import urllib.error

from dotenv import load_dotenv
load_dotenv('.env')

# =============================================================================
# LOGGING INFRASTRUCTURE
# =============================================================================

class ColoredFormatter(logging.Formatter):
    """Colored logging for better visibility."""
    
    COLORS = {
        'DEBUG': '\033[36m',    # Cyan
        'INFO': '\033[32m',     # Green
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',    # Red
        'CRITICAL': '\033[35m', # Magenta
    }
    RESET = '\033[0m'
    
    def format(self, record):
        color = self.COLORS.get(record.levelname, self.RESET)
        record.levelname = f"{color}{record.levelname}{self.RESET}"
        return super().format(record)


def setup_logging(level: str = "INFO") -> logging.Logger:
    """Configure logging for the entire system."""
    logger = logging.getLogger("ZRAI")
    logger.setLevel(getattr(logging, level))
    
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(ColoredFormatter(
            '%(asctime)s | %(levelname)s | %(name)s | %(message)s',
            datefmt='%H:%M:%S'
        ))
        logger.addHandler(handler)
    
    return logger

logger = setup_logging()


# =============================================================================
# CORE DATA MODELS
# =============================================================================

class LeadTier(str, Enum):
    """Lead classification tiers."""
    WHALE = "WHALE"      # Active ad spenders, high budget
    HOT = "HOT"          # High opportunity, ready to buy
    WARM = "WARM"        # Good potential, needs nurturing
    COLD = "COLD"        # Low priority
    DISQUALIFIED = "DISQUALIFIED"  # Not a fit


class BudgetTier(str, Enum):
    """Budget classification."""
    ENTERPRISE = "ENTERPRISE"  # >10L/month budget
    HIGH = "HIGH"              # 2-10L/month
    MEDIUM = "MEDIUM"          # 50K-2L/month
    LOW = "LOW"                # <50K/month
    UNKNOWN = "UNKNOWN"


class DataSource(str, Enum):
    """Data source tracking."""
    GOOGLE_MAPS = "google_maps"
    FIRECRAWL = "firecrawl"
    STEEL = "steel"
    RAW_HTML = "raw_html"
    FB_AD_LIBRARY = "fb_ad_library"
    GOOGLE_ADS_TRANSPARENCY = "google_ads_transparency"
    MANUAL = "manual"


@dataclass
class TrackingData:
    """Website tracking pixel data."""
    has_gtm: bool = False
    gtm_id: Optional[str] = None
    has_ga4: bool = False
    ga4_id: Optional[str] = None
    has_ua: bool = False
    ua_id: Optional[str] = None
    has_fb_pixel: bool = False
    fb_pixel_id: Optional[str] = None
    has_google_ads: bool = False
    google_ads_id: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class WhatsAppData:
    """WhatsApp presence data."""
    detected: bool = False
    detection_type: str = "NONE"  # BUTTON, LINK, MENTION, NONE
    phone_number: Optional[str] = None
    click_to_chat_url: Optional[str] = None
    confidence: float = 0.0  # 0-1
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class AdLibraryData:
    """Ad library intelligence."""
    is_running_fb_ads: bool = False
    fb_ad_count: int = 0
    fb_ads: List[Dict] = field(default_factory=list)
    is_running_google_ads: bool = False
    google_ad_count: int = 0
    google_ads: List[Dict] = field(default_factory=list)
    estimated_monthly_spend: Optional[int] = None
    ad_platforms: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class TechStackData:
    """Technology stack detection."""
    cms: Optional[str] = None
    booking_system: Optional[str] = None
    chat_widget: Optional[str] = None
    crm: Optional[str] = None
    payment_systems: List[str] = field(default_factory=list)
    marketing_tools: List[str] = field(default_factory=list)
    ecommerce_platform: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class ContactData:
    """Contact information."""
    emails: List[str] = field(default_factory=list)
    phones: List[str] = field(default_factory=list)
    whatsapp: WhatsAppData = field(default_factory=WhatsAppData)
    social_links: Dict[str, str] = field(default_factory=dict)
    contact_form_url: Optional[str] = None
    booking_url: Optional[str] = None
    
    def to_dict(self) -> Dict:
        data = asdict(self)
        data['whatsapp'] = self.whatsapp.to_dict()
        return data


@dataclass
class ScoreData:
    """Lead scoring data."""
    data_quality: int = 0       # 0-100
    reachability: int = 0       # 0-100
    money_signal: int = 0       # 0-100
    opportunity: int = 0        # 0-100
    urgency: int = 0            # 0-100
    final_score: int = 0        # 0-100
    
    def calculate_final(self, weights: Dict[str, float] = None) -> int:
        """Calculate final score with custom weights."""
        if weights is None:
            weights = {
                'data_quality': 0.15,
                'reachability': 0.15,
                'money_signal': 0.30,
                'opportunity': 0.25,
                'urgency': 0.15,
            }
        
        self.final_score = int(
            self.data_quality * weights.get('data_quality', 0.2) +
            self.reachability * weights.get('reachability', 0.2) +
            self.money_signal * weights.get('money_signal', 0.2) +
            self.opportunity * weights.get('opportunity', 0.2) +
            self.urgency * weights.get('urgency', 0.2)
        )
        return self.final_score
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class OutreachData:
    """Generated outreach content."""
    angle: str = "general"
    email_subject: str = ""
    email_body: str = ""
    whatsapp_message: str = ""
    call_script: str = ""
    linkedin_note: str = ""
    follow_up_sequence: List[Dict] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class Lead:
    """
    MASTER LEAD MODEL
    
    This is the single source of truth for all lead data.
    All agents read from and write to this model.
    """
    # Identity
    lead_id: str
    business_name: str
    
    # Basic Info
    category: str = ""
    city: str = ""
    state: str = ""
    country: str = "India"
    address: str = ""
    website: str = ""
    
    # Google Maps Data
    google_maps_url: str = ""
    rating: Optional[float] = None
    reviews_count: Optional[int] = None
    
    # Intelligence Components
    tracking: TrackingData = field(default_factory=TrackingData)
    contacts: ContactData = field(default_factory=ContactData)
    tech_stack: TechStackData = field(default_factory=TechStackData)
    ad_intel: AdLibraryData = field(default_factory=AdLibraryData)
    scores: ScoreData = field(default_factory=ScoreData)
    outreach: OutreachData = field(default_factory=OutreachData)
    
    # Classification
    tier: LeadTier = LeadTier.COLD
    budget_tier: BudgetTier = BudgetTier.UNKNOWN
    priority_rank: int = 0
    
    # AI Analysis
    ai_summary: str = ""
    pain_points: List[str] = field(default_factory=list)
    selling_angles: List[str] = field(default_factory=list)
    objection_handlers: Dict[str, str] = field(default_factory=dict)
    
    # Revenue Opportunity
    estimated_monthly_leads: int = 0
    estimated_missed_pct: float = 0.0
    estimated_revenue_loss: int = 0
    recoverable_amount: int = 0
    recommended_solution: str = ""
    roi_multiple: float = 0.0
    
    # Flags
    is_actively_acquiring: bool = False
    is_leaking_leads: bool = False
    is_ready_to_scale: bool = False
    has_automation: bool = False
    
    # Data Quality
    data_sources: List[str] = field(default_factory=list)
    enrichment_complete: bool = False
    validation_issues: List[str] = field(default_factory=list)
    
    # Timestamps
    created_at: str = ""
    updated_at: str = ""
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()
        self.updated_at = datetime.now(timezone.utc).isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = {
            'lead_id': self.lead_id,
            'business_name': self.business_name,
            'category': self.category,
            'city': self.city,
            'state': self.state,
            'country': self.country,
            'address': self.address,
            'website': self.website,
            'google_maps_url': self.google_maps_url,
            'rating': self.rating,
            'reviews_count': self.reviews_count,
            'tracking': self.tracking.to_dict(),
            'contacts': self.contacts.to_dict(),
            'tech_stack': self.tech_stack.to_dict(),
            'ad_intel': self.ad_intel.to_dict(),
            'scores': self.scores.to_dict(),
            'outreach': self.outreach.to_dict(),
            'tier': self.tier.value,
            'budget_tier': self.budget_tier.value,
            'priority_rank': self.priority_rank,
            'ai_summary': self.ai_summary,
            'pain_points': self.pain_points,
            'selling_angles': self.selling_angles,
            'objection_handlers': self.objection_handlers,
            'estimated_monthly_leads': self.estimated_monthly_leads,
            'estimated_missed_pct': self.estimated_missed_pct,
            'estimated_revenue_loss': self.estimated_revenue_loss,
            'recoverable_amount': self.recoverable_amount,
            'recommended_solution': self.recommended_solution,
            'roi_multiple': self.roi_multiple,
            'is_actively_acquiring': self.is_actively_acquiring,
            'is_leaking_leads': self.is_leaking_leads,
            'is_ready_to_scale': self.is_ready_to_scale,
            'has_automation': self.has_automation,
            'data_sources': self.data_sources,
            'enrichment_complete': self.enrichment_complete,
            'validation_issues': self.validation_issues,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
        }
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Lead':
        """Create Lead from dictionary."""
        lead = cls(
            lead_id=data.get('lead_id', ''),
            business_name=data.get('business_name', ''),
        )
        # Copy all fields
        for key, value in data.items():
            if hasattr(lead, key) and key not in ['tracking', 'contacts', 'tech_stack', 'ad_intel', 'scores', 'outreach']:
                setattr(lead, key, value)
        return lead


# =============================================================================
# TOOL REGISTRY - Plugin Architecture
# =============================================================================

@runtime_checkable
class Tool(Protocol):
    """Protocol for all tools."""
    name: str
    description: str
    
    def execute(self, **kwargs) -> Dict[str, Any]:
        """Execute the tool and return results."""
        ...


class ToolRegistry:
    """
    Central registry for all tools.
    
    Enables plugin architecture - add new tools without changing core code.
    """
    
    _instance = None
    _tools: Dict[str, Tool] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._tools = {}
        return cls._instance
    
    @classmethod
    def register(cls, tool: Tool) -> None:
        """Register a tool."""
        cls._tools[tool.name] = tool
        logger.debug(f"Registered tool: {tool.name}")
    
    @classmethod
    def get(cls, name: str) -> Optional[Tool]:
        """Get a tool by name."""
        return cls._tools.get(name)
    
    @classmethod
    def list_tools(cls) -> List[str]:
        """List all registered tools."""
        return list(cls._tools.keys())
    
    @classmethod
    def execute(cls, name: str, **kwargs) -> Dict[str, Any]:
        """Execute a tool by name."""
        tool = cls.get(name)
        if tool is None:
            return {"error": f"Tool not found: {name}"}
        try:
            return tool.execute(**kwargs)
        except Exception as e:
            logger.error(f"Tool {name} failed: {e}")
            return {"error": str(e)}


# =============================================================================
# BASE TOOLS
# =============================================================================

class ApifyTool:
    """Apify Google Maps discovery tool."""
    
    name = "apify_google_maps"
    description = "Discover businesses from Google Maps"
    
    ACTOR_ID = "nwua9Gu5YrADL7ZDj"
    
    def __init__(self):
        self.api_token = os.environ.get("APIFY_API_TOKEN", "")
        self.base_url = "https://api.apify.com/v2"
    
    def _request(self, method: str, endpoint: str, data: Optional[Dict] = None, timeout: int = 60) -> Dict:
        url = f"{self.base_url}{endpoint}?token={self.api_token}"
        headers = {"Content-Type": "application/json"}
        req_data = json.dumps(data).encode() if data else None
        req = urllib.request.Request(url, data=req_data, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    
    def execute(self, query: str, limit: int = 20, **kwargs) -> Dict[str, Any]:
        """
        Execute Google Maps discovery.
        
        Args:
            query: Search query (e.g., "dental clinic in Mumbai")
            limit: Maximum results
        """
        if not self.api_token:
            return {"error": "APIFY_API_TOKEN not set", "items": []}
        
        logger.info(f"🔍 Apify: Searching '{query}' (limit: {limit})")
        
        input_data = {
            "searchStringsArray": [query],
            "maxCrawledPlacesPerSearch": limit,
            "language": "en",
            "deeperCityScrape": True,
        }
        
        try:
            # Start run
            result = self._request("POST", f"/acts/{self.ACTOR_ID}/runs", input_data)
            run_id = result.get("data", {}).get("id")
            
            if not run_id:
                return {"error": "Failed to start actor", "items": []}
            
            # Poll for completion
            for _ in range(30):
                time.sleep(10)
                status_result = self._request("GET", f"/actor-runs/{run_id}")
                status = status_result.get("data", {}).get("status")
                
                if status == "SUCCEEDED":
                    break
                elif status in ["FAILED", "ABORTED", "TIMED-OUT"]:
                    return {"error": f"Actor {status}", "items": []}
            
            # Get results
            dataset_id = status_result.get("data", {}).get("defaultDatasetId")
            items = self._request("GET", f"/datasets/{dataset_id}/items")
            
            logger.info(f"   ✅ Found {len(items)} businesses")
            return {"items": items if isinstance(items, list) else [], "count": len(items)}
            
        except Exception as e:
            logger.error(f"   ❌ Apify error: {e}")
            return {"error": str(e), "items": []}


class FirecrawlTool:
    """Firecrawl website scraping tool."""
    
    name = "firecrawl"
    description = "Scrape website content and extract data"
    
    def __init__(self):
        self.api_key = os.environ.get("FIRECRAWL_API_KEY", "")
        self.base_url = "https://api.firecrawl.dev/v1"
    
    def execute(self, url: str, **kwargs) -> Dict[str, Any]:
        """
        Scrape a website.
        
        Args:
            url: Website URL to scrape
        """
        if not self.api_key or not url:
            return {"error": "Missing API key or URL", "content": ""}
        
        if not url.startswith(('http://', 'https://')):
            url = f"https://{url}"
        
        logger.info(f"   🕷️ Firecrawl: {url[:50]}...")
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        data = {
            "url": url,
            "formats": ["markdown"],
            "onlyMainContent": True,
        }
        
        try:
            req = urllib.request.Request(
                f"{self.base_url}/scrape",
                data=json.dumps(data).encode(),
                headers=headers
            )
            
            with urllib.request.urlopen(req, timeout=45) as resp:
                result = json.loads(resp.read().decode())
            
            if result.get("success"):
                page_data = result.get("data", {})
                return {
                    "success": True,
                    "markdown": page_data.get("markdown", ""),
                    "metadata": page_data.get("metadata", {}),
                }
            
            return {"error": "Scrape failed", "content": ""}
            
        except Exception as e:
            logger.warning(f"   ⚠️ Firecrawl error: {str(e)[:30]}")
            return {"error": str(e), "content": ""}


class RawHTMLTool:
    """Raw HTML fetcher for accurate tracking detection."""
    
    name = "raw_html"
    description = "Fetch raw HTML for tracking pixel detection"
    
    def execute(self, url: str, timeout: int = 20, **kwargs) -> Dict[str, Any]:
        """
        Fetch raw HTML from URL.
        
        Args:
            url: Website URL
            timeout: Request timeout
        """
        if not url:
            return {"error": "No URL provided", "html": ""}
        
        if not url.startswith(('http://', 'https://')):
            url = f"https://{url}"
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml",
        }
        
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
                html = resp.read().decode('utf-8', errors='ignore')
            
            return {"success": True, "html": html, "length": len(html)}
            
        except Exception as e:
            return {"error": str(e), "html": ""}


class OpenRouterTool:
    """OpenRouter LLM tool."""
    
    name = "openrouter_llm"
    description = "AI reasoning and text generation"
    
    def __init__(self):
        self.api_key = os.environ.get("OPENROUTER_API_KEY", "")
        self.model = "google/gemini-2.0-flash-001"
    
    def execute(self, prompt: str, system: str = None, json_mode: bool = False, **kwargs) -> Dict[str, Any]:
        """
        Generate text using LLM.
        
        Args:
            prompt: User prompt
            system: System prompt
            json_mode: If True, expect JSON response
        """
        if not self.api_key:
            return {"error": "OPENROUTER_API_KEY not set", "response": ""}
        
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        
        if json_mode:
            prompt = f"{prompt}\n\nRespond ONLY with valid JSON."
        
        messages.append({"role": "user", "content": prompt})
        
        data = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.1 if json_mode else 0.3,
            "max_tokens": 2048,
        }
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        
        try:
            req = urllib.request.Request(
                "https://openrouter.ai/api/v1/chat/completions",
                data=json.dumps(data).encode(),
                headers=headers
            )
            
            with urllib.request.urlopen(req, timeout=60) as resp:
                result = json.loads(resp.read().decode())
            
            response = result.get("choices", [{}])[0].get("message", {}).get("content", "")
            
            if json_mode:
                # Parse JSON
                response = response.strip()
                if response.startswith("```"):
                    response = re.sub(r'^```\w*\n?', '', response)
                    response = re.sub(r'\n?```$', '', response)
                try:
                    return {"success": True, "data": json.loads(response)}
                except:
                    return {"success": False, "error": "JSON parse failed", "raw": response}
            
            return {"success": True, "response": response}
            
        except Exception as e:
            return {"error": str(e), "response": ""}


# Register all tools
ToolRegistry.register(ApifyTool())
ToolRegistry.register(FirecrawlTool())
ToolRegistry.register(RawHTMLTool())
ToolRegistry.register(OpenRouterTool())


# =============================================================================
# DETECTION UTILITIES
# =============================================================================

class TrackingDetector:
    """Detect tracking pixels from raw HTML."""
    
    @staticmethod
    def detect(html: str) -> TrackingData:
        """Detect all tracking pixels."""
        data = TrackingData()
        
        if not html:
            return data
        
        # GTM
        gtm = re.search(r"GTM-([A-Z0-9]+)", html)
        if gtm:
            data.has_gtm = True
            data.gtm_id = gtm.group()
        
        # GA4
        ga4 = re.search(r"(G-[A-Z0-9]{10,12})", html)
        if ga4:
            data.has_ga4 = True
            data.ga4_id = ga4.group(1)
        
        # UA
        ua = re.search(r"(UA-\d+-\d+)", html)
        if ua:
            data.has_ua = True
            data.ua_id = ua.group(1)
        
        # FB Pixel
        fb = re.search(r"fbq\s*\(\s*['\"]init['\"],\s*['\"](\d+)['\"]", html)
        if fb:
            data.has_fb_pixel = True
            data.fb_pixel_id = fb.group(1)
        elif "connect.facebook.net" in html and "fbq(" in html:
            data.has_fb_pixel = True
        
        # Google Ads
        gads = re.search(r"(AW-\d+)", html)
        if gads:
            data.has_google_ads = True
            data.google_ads_id = gads.group(1)
        elif "googleadservices.com" in html:
            data.has_google_ads = True
        
        return data


class WhatsAppDetector:
    """Detect WhatsApp presence accurately."""
    
    @staticmethod
    def detect(html: str) -> WhatsAppData:
        """Detect WhatsApp with confidence levels."""
        data = WhatsAppData()
        
        if not html:
            return data
        
        html_lower = html.lower()
        
        # Check for BUTTON (highest confidence)
        button_patterns = [
            r'whatsapp[-_]?(widget|button|chat|float)',
            r'class=["\'][^"\']*whatsapp[^"\']*["\'].*?(?:button|click)',
            r'data-whatsapp',
            r'wa-chat-widget',
            r'elfsight.*whatsapp',
        ]
        
        for pattern in button_patterns:
            if re.search(pattern, html_lower):
                data.detected = True
                data.detection_type = "BUTTON"
                data.confidence = 0.95
                break
        
        # Check for LINK (high confidence)
        wa_link = re.search(r'href=["\']https?://wa\.me/(\d{10,15})["\']', html, re.I)
        if wa_link:
            data.detected = True
            data.phone_number = f"+{wa_link.group(1)}"
            data.click_to_chat_url = f"https://wa.me/{wa_link.group(1)}"
            if not data.detection_type:
                data.detection_type = "LINK"
                data.confidence = 1.0
        
        # Check api.whatsapp.com/send
        wa_api = re.search(r'api\.whatsapp\.com/send\?phone=(\d+)', html)
        if wa_api:
            data.detected = True
            data.phone_number = f"+{wa_api.group(1)}"
            if not data.detection_type:
                data.detection_type = "LINK"
                data.confidence = 1.0
        
        # Check for MENTION (lower confidence)
        if not data.detection_type:
            mentions = len(re.findall(r'\bwhatsapp\b', html_lower))
            if mentions >= 3:
                data.detected = True
                data.detection_type = "MENTION"
                data.confidence = 0.5
        
        if not data.detection_type:
            data.detection_type = "NONE"
            data.confidence = 0.0
        
        return data


class TechStackDetector:
    """Detect technology stack."""
    
    CMS_PATTERNS = {
        "WordPress": ["wp-content", "wp-includes", "wordpress"],
        "Wix": ["wix.com", "_wix"],
        "Shopify": ["cdn.shopify", "shopify"],
        "Squarespace": ["squarespace"],
        "Webflow": ["webflow"],
    }
    
    BOOKING_PATTERNS = {
        "Practo": "practo",
        "Calendly": "calendly",
        "Zocdoc": "zocdoc",
        "Setmore": "setmore",
        "SimplyBook": "simplybook",
    }
    
    CHAT_PATTERNS = {
        "Intercom": "intercom",
        "Zendesk": "zendesk",
        "Freshdesk": "freshdesk",
        "Tawk.to": "tawk.to",
        "Crisp": "crisp.chat",
        "Drift": "drift.com",
        "Tidio": "tidio",
    }
    
    @classmethod
    def detect(cls, html: str) -> TechStackData:
        """Detect tech stack from HTML."""
        data = TechStackData()
        
        if not html:
            return data
        
        html_lower = html.lower()
        
        # CMS
        for cms, patterns in cls.CMS_PATTERNS.items():
            if any(p in html_lower for p in patterns):
                data.cms = cms
                break
        
        # Booking
        for system, pattern in cls.BOOKING_PATTERNS.items():
            if pattern in html_lower:
                data.booking_system = system
                break
        
        # Chat
        for widget, pattern in cls.CHAT_PATTERNS.items():
            if pattern in html_lower:
                data.chat_widget = widget
                break
        
        # Payment
        payment_list = ["razorpay", "paytm", "phonepe", "stripe", "paypal", "instamojo"]
        data.payment_systems = [p for p in payment_list if p in html_lower]
        
        # Marketing
        marketing_list = ["mailchimp", "hubspot", "zoho", "clevertap", "moengage"]
        data.marketing_tools = [m for m in marketing_list if m in html_lower]
        
        return data


class EmailExtractor:
    """Extract emails from content."""
    
    EXCLUDE_PATTERNS = ['example.com', 'domain.com', 'test.com', 'samplemail', 'yoursite']
    
    @classmethod
    def extract(cls, content: str) -> List[str]:
        """Extract valid email addresses."""
        if not content:
            return []
        
        patterns = [
            r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
            r'mailto:([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
        ]
        
        emails = []
        for pattern in patterns:
            found = re.findall(pattern, content, re.I)
            emails.extend(found)
        
        # Clean and filter
        cleaned = []
        for email in emails:
            email = email.lower().strip()
            if '@' in email and not any(ex in email for ex in cls.EXCLUDE_PATTERNS):
                cleaned.append(email)
        
        return list(set(cleaned))[:5]


# =============================================================================
# AGENT BASE CLASS
# =============================================================================

class BaseAgent(ABC):
    """
    Base class for all agents.
    
    Every agent must:
    1. Have a name and description
    2. Implement process() method
    3. Use the ToolRegistry for tool access
    """
    
    name: str = "base_agent"
    description: str = "Base agent class"
    
    def __init__(self):
        self.logger = logging.getLogger(f"ZRAI.{self.name}")
    
    @abstractmethod
    def process(self, lead: Lead, **kwargs) -> Lead:
        """
        Process a lead and return updated lead.
        
        Args:
            lead: Input lead
            **kwargs: Additional parameters
            
        Returns:
            Updated lead
        """
        pass
    
    def log(self, message: str, level: str = "info"):
        """Log a message."""
        getattr(self.logger, level)(message)


# =============================================================================
# SPECIALIZED AGENTS
# =============================================================================

class DiscoveryAgent(BaseAgent):
    """
    Agent responsible for discovering businesses.
    
    Uses: Apify Google Maps
    Output: Raw business data
    """
    
    name = "discovery_agent"
    description = "Discover businesses from Google Maps"
    
    def discover(self, niche: str, city: str, limit: int = 20) -> List[Lead]:
        """
        Discover businesses and create Lead objects.
        
        Args:
            niche: Business category
            city: Target city
            limit: Maximum results
            
        Returns:
            List of Lead objects
        """
        self.log(f"🔍 Discovering: {niche} in {city}")
        
        query = f"{niche} in {city}, India"
        tool = ToolRegistry.get("apify_google_maps")
        
        result = tool.execute(query=query, limit=limit)
        
        if result.get("error"):
            self.log(f"❌ Discovery failed: {result['error']}", "error")
            return []
        
        leads = []
        for item in result.get("items", []):
            lead_id = hashlib.md5(
                f"{item.get('title', '')}{item.get('address', '')}".encode()
            ).hexdigest()[:16]
            
            lead = Lead(
                lead_id=lead_id,
                business_name=item.get("title") or item.get("name", "Unknown"),
                category=niche,
                city=city,
                website=item.get("website") or "",
                google_maps_url=item.get("url") or "",
                rating=item.get("totalScore") or item.get("rating"),
                reviews_count=item.get("reviewsCount") or item.get("reviews"),
                address=item.get("address") or "",
            )
            
            # Add phone to contacts
            if item.get("phone"):
                lead.contacts.phones.append(item["phone"])
            
            lead.data_sources.append(DataSource.GOOGLE_MAPS.value)
            leads.append(lead)
        
        self.log(f"✅ Discovered {len(leads)} businesses")
        return leads
    
    def process(self, lead: Lead, **kwargs) -> Lead:
        """Process method for single lead (not used for discovery)."""
        return lead


class EnrichmentAgent(BaseAgent):
    """
    Agent responsible for enriching leads with website data.
    
    Uses: Firecrawl, Raw HTML
    Output: Tracking data, contacts, tech stack
    """
    
    name = "enrichment_agent"
    description = "Enrich leads with website intelligence"
    
    def process(self, lead: Lead, **kwargs) -> Lead:
        """
        Enrich a lead with website data.
        
        Steps:
        1. Fetch raw HTML for tracking detection
        2. Use Firecrawl for content extraction
        3. Detect tech stack
        4. Extract contacts
        """
        if not lead.website:
            self.log(f"   ⏭️ No website for {lead.business_name[:30]}")
            return lead
        
        self.log(f"   🌐 Enriching: {lead.business_name[:30]}")
        
        # 1. Raw HTML for tracking (most accurate)
        html_tool = ToolRegistry.get("raw_html")
        html_result = html_tool.execute(url=lead.website)
        
        if html_result.get("success"):
            html = html_result.get("html", "")
            lead.data_sources.append(DataSource.RAW_HTML.value)
            
            # Tracking detection
            lead.tracking = TrackingDetector.detect(html)
            
            if lead.tracking.has_gtm:
                self.log(f"      ✅ GTM: {lead.tracking.gtm_id}")
            if lead.tracking.has_ga4:
                self.log(f"      ✅ GA4: {lead.tracking.ga4_id}")
            if lead.tracking.has_fb_pixel:
                self.log(f"      ✅ FB Pixel: {lead.tracking.fb_pixel_id or 'Detected'}")
            
            # WhatsApp detection
            lead.contacts.whatsapp = WhatsAppDetector.detect(html)
            
            if lead.contacts.whatsapp.detected:
                self.log(f"      ✅ WhatsApp: {lead.contacts.whatsapp.detection_type} {lead.contacts.whatsapp.phone_number or ''}")
            
            # Tech stack
            lead.tech_stack = TechStackDetector.detect(html)
            
            if lead.tech_stack.booking_system:
                self.log(f"      ✅ Booking: {lead.tech_stack.booking_system}")
            if lead.tech_stack.chat_widget:
                self.log(f"      ✅ Chat: {lead.tech_stack.chat_widget}")
        
        # 2. Firecrawl for content
        fc_tool = ToolRegistry.get("firecrawl")
        fc_result = fc_tool.execute(url=lead.website)
        
        if fc_result.get("success"):
            lead.data_sources.append(DataSource.FIRECRAWL.value)
            
            markdown = fc_result.get("markdown", "")
            
            # Extract emails
            emails = EmailExtractor.extract(markdown)
            lead.contacts.emails.extend(emails)
            lead.contacts.emails = list(set(lead.contacts.emails))[:5]
            
            if emails:
                self.log(f"      ✅ Emails: {len(emails)} found")
        
        lead.enrichment_complete = True
        return lead


class AdsIntelAgent(BaseAgent):
    """
    Agent responsible for ad library intelligence.
    
    Uses: Apify FB Ad Library, Google Ads Transparency
    Output: Active ad campaigns, spend signals
    """
    
    name = "ads_intel_agent"
    description = "Check if business is running ads"
    
    # Note: This agent is OPTIONAL - uses extra credits
    
    def process(self, lead: Lead, check_fb: bool = True, check_google: bool = True, **kwargs) -> Lead:
        """
        Check ad libraries for active campaigns.
        
        This is EXPENSIVE (Apify credits) - use selectively.
        """
        # Implementation would call Apify FB Ad Library and Google Ads Transparency actors
        # For now, we rely on pixel detection as a proxy
        
        # If they have FB Pixel, they're likely to be running or planning FB ads
        if lead.tracking.has_fb_pixel:
            lead.is_ready_to_scale = True
        
        # If they have Google Ads tag, they're likely running Google Ads
        if lead.tracking.has_google_ads:
            lead.ad_intel.is_running_google_ads = True
            lead.is_actively_acquiring = True
        
        return lead


class ScoringAgent(BaseAgent):
    """
    Agent responsible for scoring and classification.
    
    Uses: Internal scoring algorithms
    Output: Scores, tier, budget tier
    """
    
    name = "scoring_agent"
    description = "Score and classify leads"
    
    # Industry configurations
    INDUSTRY_CONFIG = {
        "diagnostic": {"ticket": 1500, "leads": 500},
        "dental": {"ticket": 2500, "leads": 200},
        "eye": {"ticket": 3000, "leads": 150},
        "coaching": {"ticket": 50000, "leads": 100},
        "hospital": {"ticket": 15000, "leads": 1000},
        "clinic": {"ticket": 800, "leads": 300},
        "default": {"ticket": 3000, "leads": 150},
    }
    
    def _get_config(self, category: str) -> Dict:
        """Get industry config."""
        category_lower = category.lower()
        for key, config in self.INDUSTRY_CONFIG.items():
            if key in category_lower:
                return config
        return self.INDUSTRY_CONFIG["default"]
    
    def process(self, lead: Lead, **kwargs) -> Lead:
        """Score and classify a lead."""
        
        # Data Quality Score
        dq = 0
        if lead.business_name: dq += 15
        if lead.contacts.phones: dq += 20
        if lead.website: dq += 15
        if lead.contacts.emails: dq += 15
        if lead.contacts.whatsapp.detected: dq += 15
        if lead.rating: dq += 10
        if lead.reviews_count: dq += 10
        lead.scores.data_quality = min(dq, 100)
        
        # Reachability Score
        reach = 0
        if lead.contacts.phones: reach += 30
        if lead.contacts.emails: reach += 25
        if lead.contacts.whatsapp.detection_type in ["BUTTON", "LINK"]: reach += 25
        if lead.contacts.social_links.get("linkedin"): reach += 15
        if lead.tech_stack.booking_system: reach += 5
        lead.scores.reachability = min(reach, 100)
        
        # Money Signal Score
        money = 0
        if lead.ad_intel.is_running_fb_ads: money += 30
        if lead.ad_intel.is_running_google_ads: money += 30
        if lead.tracking.has_gtm: money += 15
        if lead.tracking.has_ga4: money += 10
        if lead.tracking.has_fb_pixel: money += 15
        if lead.reviews_count and lead.reviews_count > 500: money += 20
        elif lead.reviews_count and lead.reviews_count > 100: money += 10
        lead.scores.money_signal = min(money, 100)
        
        # Opportunity Score
        opp = 0
        if not lead.tech_stack.booking_system:
            opp += 20
            lead.is_leaking_leads = True
        if not lead.tech_stack.chat_widget:
            opp += 15
        if not lead.contacts.whatsapp.detected:
            opp += 15
        if (lead.tracking.has_gtm or lead.tracking.has_ga4) and not lead.ad_intel.is_running_fb_ads:
            opp += 20
            lead.is_ready_to_scale = True
        if lead.tracking.has_fb_pixel and not lead.tech_stack.booking_system:
            opp += 20  # Running ads but leaking
        lead.scores.opportunity = min(opp, 100)
        
        # Urgency Score
        urg = 0
        if lead.is_leaking_leads: urg += 30
        if lead.is_ready_to_scale: urg += 20
        if lead.is_actively_acquiring: urg += 25
        if lead.reviews_count and lead.reviews_count > 200: urg += 15
        lead.scores.urgency = min(urg, 100)
        
        # Final Score
        lead.scores.calculate_final()
        
        # Budget Tier
        if lead.scores.money_signal >= 50:
            lead.budget_tier = BudgetTier.HIGH
        elif lead.scores.money_signal >= 25:
            lead.budget_tier = BudgetTier.MEDIUM
        else:
            lead.budget_tier = BudgetTier.LOW
        
        # Lead Tier
        if lead.is_actively_acquiring and lead.scores.opportunity >= 40:
            lead.tier = LeadTier.WHALE
        elif lead.scores.final_score >= 70:
            lead.tier = LeadTier.HOT
        elif lead.scores.final_score >= 50:
            lead.tier = LeadTier.WARM
        else:
            lead.tier = LeadTier.COLD
        
        # Revenue Calculation
        config = self._get_config(lead.category)
        ticket = config["ticket"]
        monthly_leads = config["leads"]
        
        if lead.reviews_count:
            if lead.reviews_count > 500:
                monthly_leads = int(monthly_leads * 1.5)
            elif lead.reviews_count > 200:
                monthly_leads = int(monthly_leads * 1.2)
        
        lead.estimated_monthly_leads = monthly_leads
        
        missed_pct = 0.0
        if not lead.tech_stack.booking_system: missed_pct += 0.15
        if not lead.tech_stack.chat_widget: missed_pct += 0.10
        if not lead.contacts.whatsapp.detected: missed_pct += 0.10
        
        lead.estimated_missed_pct = min(missed_pct, 0.50)
        lead.estimated_revenue_loss = int(monthly_leads * missed_pct * ticket * 0.25)
        lead.recoverable_amount = int(lead.estimated_revenue_loss * 0.70)
        
        if lead.estimated_revenue_loss >= 200000:
            cost = 150000
            lead.recommended_solution = "Enterprise ₹1.5L/month"
        elif lead.estimated_revenue_loss >= 100000:
            cost = 60000
            lead.recommended_solution = "Pro ₹60K/month"
        else:
            cost = 35000
            lead.recommended_solution = "Growth ₹35K/month"
        
        lead.roi_multiple = lead.recoverable_amount / cost if cost else 0
        
        self.log(f"      📊 Score: {lead.scores.final_score} | Tier: {lead.tier.value} | Money: {lead.scores.money_signal}")
        
        return lead


class AnalysisAgent(BaseAgent):
    """
    Agent responsible for AI analysis.
    
    Uses: OpenRouter LLM
    Output: AI summary, pain points, selling angles
    """
    
    name = "analysis_agent"
    description = "Generate AI-powered lead analysis"
    
    def process(self, lead: Lead, **kwargs) -> Lead:
        """Generate AI analysis for a lead."""
        
        llm_tool = ToolRegistry.get("openrouter_llm")
        
        prompt = f"""Analyze this {lead.category} business for B2B sales:

BUSINESS: {lead.business_name}
CITY: {lead.city}
WEBSITE: {lead.website or 'None'}
RATING: {lead.rating} ({lead.reviews_count} reviews)

TRACKING:
- GTM: {lead.tracking.gtm_id or 'None'}
- GA4: {lead.tracking.ga4_id or 'None'}
- FB Pixel: {'Yes' if lead.tracking.has_fb_pixel else 'No'}

GAPS:
- No Booking: {not lead.tech_stack.booking_system}
- No Chat: {not lead.tech_stack.chat_widget}
- No WhatsApp: {not lead.contacts.whatsapp.detected}

SCORES:
- Money Signal: {lead.scores.money_signal}/100
- Opportunity: {lead.scores.opportunity}/100
- Final: {lead.scores.final_score}/100

REVENUE:
- Loss: ₹{lead.estimated_revenue_loss:,}/month
- Recoverable: ₹{lead.recoverable_amount:,}/month

Provide JSON:
{{
    "summary": "2-3 sentence assessment",
    "pain_points": ["3 specific pain points"],
    "selling_angles": ["3 personalized angles"],
    "objections": {{"price": "handler", "timing": "handler"}}
}}"""

        result = llm_tool.execute(prompt=prompt, json_mode=True)
        
        if result.get("success") and result.get("data"):
            data = result["data"]
            lead.ai_summary = data.get("summary", "")
            lead.pain_points = data.get("pain_points", [])
            lead.selling_angles = data.get("selling_angles", [])
            lead.objection_handlers = data.get("objections", {})
        
        return lead


class OutreachAgent(BaseAgent):
    """
    Agent responsible for generating outreach content.
    
    Uses: Templates + AI
    Output: Email, WhatsApp, call scripts
    """
    
    name = "outreach_agent"
    description = "Generate outreach content"
    
    def process(self, lead: Lead, **kwargs) -> Lead:
        """Generate outreach content based on lead intelligence."""
        
        # Determine angle
        if lead.is_actively_acquiring:
            angle = "ad_optimization"
            subject = f"Your ads are leaking leads at {lead.business_name}"
            opening = f"I noticed {lead.business_name} is running Facebook ads - smart move."
            pain = "But without WhatsApp capture, you're losing 15-20% of that ad spend."
        elif lead.is_ready_to_scale:
            angle = "scale_ready"
            subject = f"Ready to scale {lead.business_name}?"
            opening = f"I noticed {lead.business_name} has analytics set up properly."
            pain = "Before you start paid ads, let me show you how to capture 30% more leads."
        elif lead.is_leaking_leads:
            angle = "leak_fix"
            subject = f"₹{lead.estimated_revenue_loss//1000}K/month leak at {lead.business_name}"
            opening = f"Found {lead.business_name} on Google - {lead.reviews_count or 'good'} reviews."
            pain = f"Quick analysis: you're losing ₹{lead.estimated_revenue_loss//1000}K/month."
        else:
            angle = "general"
            subject = f"Quick question about {lead.business_name}"
            opening = f"Found {lead.business_name} on Google."
            pain = "I noticed a few gaps that might be costing you leads."
        
        lead.outreach.angle = angle
        lead.outreach.email_subject = subject
        
        lead.outreach.email_body = f"""Hi,

{opening}

{pain}

We can fix this with:
✅ WhatsApp lead capture
✅ Missed call automation
✅ Follow-up sequences

ROI: {lead.roi_multiple:.1f}x

2-min call?

[Your Name]"""

        lead.outreach.whatsapp_message = f"""Hi! Quick note about {lead.business_name}.

{pain}

We can recover this with WhatsApp automation.

Want a free audit? Reply YES"""

        lead.outreach.call_script = f"""Hi, is this [Owner] from {lead.business_name}?

I'm [Name], I help {lead.category} businesses recover lost revenue.

{pain}

Do you have 2 minutes?"""

        return lead


# =============================================================================
# ORCHESTRATOR - MAIN ENGINE
# =============================================================================

class Orchestrator:
    """
    Master orchestrator that coordinates all agents.
    
    This is the MAIN entry point for the intelligence system.
    """
    
    def __init__(self):
        self.discovery_agent = DiscoveryAgent()
        self.enrichment_agent = EnrichmentAgent()
        self.ads_agent = AdsIntelAgent()
        self.scoring_agent = ScoringAgent()
        self.analysis_agent = AnalysisAgent()
        self.outreach_agent = OutreachAgent()
        
        self.output_dir = Path("output")
        self.output_dir.mkdir(exist_ok=True)
        
        logger.info("🚀 ZRAI Orchestrator initialized")
        logger.info(f"   Tools: {', '.join(ToolRegistry.list_tools())}")
    
    def run_pipeline(
        self,
        niche: str,
        city: str,
        target: int = 10,
        enable_ai: bool = True,
        enable_ads_check: bool = False,
        parallel: bool = True,
    ) -> Dict[str, Any]:
        """
        Run the full intelligence pipeline.
        
        Args:
            niche: Business category
            city: Target city
            target: Number of leads
            enable_ai: Enable AI analysis (uses LLM credits)
            enable_ads_check: Enable ad library check (expensive)
            parallel: Enable parallel processing
            
        Returns:
            Complete intelligence report
        """
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_dir = self.output_dir / f"{city}_{niche.replace(' ', '_')}_{run_id}"
        run_dir.mkdir(exist_ok=True)
        
        print("\n" + "=" * 70)
        print("🚀 ZRAI ELITE INTELLIGENCE SYSTEM")
        print("=" * 70)
        print(f"   Target: {niche} in {city}")
        print(f"   Goal: {target} leads")
        print(f"   AI Analysis: {'✅' if enable_ai else '❌'}")
        print(f"   Ad Check: {'✅' if enable_ads_check else '❌'}")
        print("=" * 70)
        
        # Phase 1: Discovery
        print("\n📍 PHASE 1: DISCOVERY")
        leads = self.discovery_agent.discover(niche, city, limit=target * 2)
        
        if not leads:
            return {"error": "Discovery failed", "leads": []}
        
        # Phase 2: Enrichment
        print(f"\n🔬 PHASE 2: ENRICHMENT")
        
        processed = []
        for i, lead in enumerate(leads[:target * 2], 1):
            if len(processed) >= target:
                break
            
            print(f"\n[{i}/{len(leads)}] {lead.business_name[:40]}")
            
            # Enrichment
            lead = self.enrichment_agent.process(lead)
            
            # Ads check (optional)
            if enable_ads_check:
                lead = self.ads_agent.process(lead)
            
            # Scoring
            lead = self.scoring_agent.process(lead)
            
            # Skip low quality
            if lead.scores.data_quality < 30:
                print(f"      ⏭️ Skipped (low quality)")
                continue
            
            # AI Analysis (optional)
            if enable_ai:
                lead = self.analysis_agent.process(lead)
            
            # Outreach
            lead = self.outreach_agent.process(lead)
            
            processed.append(lead)
        
        # Sort and rank
        processed.sort(key=lambda x: -x.scores.final_score)
        for i, lead in enumerate(processed, 1):
            lead.priority_rank = i
        
        # Stats
        stats = {
            "whale": sum(1 for l in processed if l.tier == LeadTier.WHALE),
            "hot": sum(1 for l in processed if l.tier == LeadTier.HOT),
            "warm": sum(1 for l in processed if l.tier == LeadTier.WARM),
            "cold": sum(1 for l in processed if l.tier == LeadTier.COLD),
        }
        
        total_opp = sum(l.estimated_revenue_loss for l in processed)
        
        # Report
        report = {
            "run_id": run_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "config": {
                "niche": niche,
                "city": city,
                "target": target,
                "enable_ai": enable_ai,
                "enable_ads_check": enable_ads_check,
            },
            "summary": {
                "discovered": len(leads),
                "processed": len(processed),
                **stats,
                "total_opportunity_inr": total_opp,
            },
            "leads": [l.to_dict() for l in processed],
        }
        
        # Save
        with open(run_dir / "report.json", 'w') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        with open(run_dir / "leads.json", 'w') as f:
            json.dump(report["leads"], f, indent=2, ensure_ascii=False)
        
        # Summary
        print("\n" + "=" * 70)
        print("✅ INTELLIGENCE COMPLETE")
        print("=" * 70)
        print(f"\n📁 Output: {run_dir}")
        print(f"\n📊 RESULTS:")
        print(f"   🐋 WHALE: {stats['whale']}")
        print(f"   🔥 HOT:   {stats['hot']}")
        print(f"   ☀️ WARM:  {stats['warm']}")
        print(f"   ❄️ COLD:  {stats['cold']}")
        print(f"\n💰 OPPORTUNITY: ₹{total_opp:,}/month")
        
        if processed:
            print("\n🎯 TOP LEADS:")
            for i, lead in enumerate(processed[:5], 1):
                emoji = {"WHALE": "🐋", "HOT": "🔥", "WARM": "☀️", "COLD": "❄️"}.get(lead.tier.value, "")
                print(f"   {i}. {emoji} {lead.business_name[:30]:<30} | {lead.scores.final_score:>3} | {lead.outreach.angle}")
        
        print("\n" + "=" * 70)
        
        return report


# =============================================================================
# CLI
# =============================================================================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="ZRAI Elite Intelligence System")
    parser.add_argument("--niche", type=str, required=True)
    parser.add_argument("--city", type=str, required=True)
    parser.add_argument("--count", type=int, default=10)
    parser.add_argument("--no-ai", action="store_true", help="Disable AI analysis")
    parser.add_argument("--check-ads", action="store_true", help="Enable ad library check")
    
    args = parser.parse_args()
    
    orchestrator = Orchestrator()
    orchestrator.run_pipeline(
        niche=args.niche,
        city=args.city,
        target=args.count,
        enable_ai=not args.no_ai,
        enable_ads_check=args.check_ads,
    )


if __name__ == "__main__":
    main()
