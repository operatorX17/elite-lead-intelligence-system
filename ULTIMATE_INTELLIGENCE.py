#!/usr/bin/env python3
"""
ZRAI ULTIMATE INTELLIGENCE ENGINE v4.0
=======================================
Production-grade lead intelligence with FULL enrichment stack:

1. APIFY → Google Maps business discovery
2. FIRECRAWL → Deep website scraping (emails, contacts, tech)
3. STEEL.DEV → JavaScript-heavy site handling
4. OPENROUTER → AI reasoning and analysis
5. SUPABASE → Database storage (when available)

This is the CASH MACHINE - highest accuracy lead intelligence.

Author: ZRAI Intelligence Team
"""

import os
import sys
import json
import hashlib
import logging
import re
import time
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict, field
from enum import Enum
import urllib.request
import urllib.error
import urllib.parse

# Load environment
from dotenv import load_dotenv
load_dotenv('.env')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("ZRAI")


# =============================================================================
# DATA MODELS
# =============================================================================

class LeadTier(str, Enum):
    HOT = "HOT"
    WARM = "WARM"
    COLD = "COLD"

class PriorityLevel(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


@dataclass
class ContactInfo:
    """Extracted contact information."""
    emails: List[str] = field(default_factory=list)
    phones: List[str] = field(default_factory=list)
    decision_makers: List[Dict[str, str]] = field(default_factory=list)
    social_links: Dict[str, str] = field(default_factory=dict)


@dataclass
class TechStack:
    """Detected technology stack."""
    cms: Optional[str] = None
    booking_system: Optional[str] = None
    chat_widget: Optional[str] = None
    crm: Optional[str] = None
    analytics: List[str] = field(default_factory=list)
    payment: List[str] = field(default_factory=list)
    marketing: List[str] = field(default_factory=list)


@dataclass
class BusinessLead:
    """Complete lead data model."""
    lead_id: str
    business_name: str
    category: str = ""
    city: str = ""
    area: str = ""
    website: str = ""
    phone: str = ""
    google_maps_url: str = ""
    rating: Optional[float] = None
    reviews_count: Optional[int] = None
    address: str = ""
    
    # Deep enrichment data
    contacts: ContactInfo = field(default_factory=ContactInfo)
    tech_stack: TechStack = field(default_factory=TechStack)
    
    # Website analysis
    website_title: str = ""
    website_description: str = ""
    website_content_summary: str = ""
    services_offered: List[str] = field(default_factory=list)
    
    # Gap analysis
    has_booking_system: bool = False
    has_whatsapp: bool = False
    has_lead_form: bool = False
    has_chat_widget: bool = False
    has_click_to_call: bool = False
    has_online_payment: bool = False
    has_reviews_management: bool = False
    has_follow_up_automation: bool = False
    ads_detected: bool = False
    
    # Advertising & Marketing Detection
    has_google_ads: bool = False
    has_facebook_ads: bool = False
    google_tag_manager_id: str = ""
    google_analytics_id: str = ""
    google_ads_id: str = ""
    facebook_pixel_id: str = ""
    whatsapp_number: str = ""
    
    # Risk signals
    has_slow_response_risk: bool = False
    has_after_hours_leak: bool = False
    has_lead_capture_gap: bool = False
    has_competition_vulnerability: bool = False
    
    # Scores
    data_quality_score: int = 0
    reachability_score: int = 0
    opportunity_score: int = 0
    urgency_score: int = 0
    final_score: int = 0
    
    # AI Analysis
    ai_reasoning: str = ""
    reasoning_verdict: str = ""
    pain_points: List[str] = field(default_factory=list)
    selling_angles: List[str] = field(default_factory=list)
    objection_handlers: Dict[str, str] = field(default_factory=dict)
    validation_issues: List[str] = field(default_factory=list)
    
    # Revenue calculations
    estimated_monthly_leads: int = 0
    estimated_missed_pct: float = 0.0
    estimated_revenue_loss_inr: int = 0
    recoverable_amount_inr: int = 0
    recommended_tier: str = ""
    roi_multiple: float = 0.0
    payback_days: int = 0
    
    # Classification
    tier: LeadTier = LeadTier.COLD
    priority: PriorityLevel = PriorityLevel.LOW
    
    # Outreach content
    email_subject: str = ""
    email_body: str = ""
    whatsapp_msg: str = ""
    call_script: str = ""
    loom_script: str = ""
    linkedin_note: str = ""
    follow_up_sequence: List[Dict[str, str]] = field(default_factory=list)
    
    # Meta
    status: str = "discovered"
    enrichment_source: str = ""
    created_at: str = ""
    updated_at: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data['tier'] = self.tier.value if isinstance(self.tier, LeadTier) else str(self.tier)
        data['priority'] = self.priority.value if isinstance(self.priority, PriorityLevel) else str(self.priority)
        return data


# =============================================================================
# APIFY CLIENT - Lead Discovery
# =============================================================================

class ApifyClient:
    """Apify Google Maps scraper client."""
    
    GOOGLE_MAPS_ACTOR = "nwua9Gu5YrADL7ZDj"
    
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
    
    def discover(self, niche: str, city: str, country: str = "India", limit: int = 20) -> List[Dict]:
        """Discover businesses from Google Maps."""
        if not self.api_token:
            logger.error("❌ APIFY_API_TOKEN not set")
            return []
        
        logger.info(f"🔍 Discovering: {niche} in {city}")
        
        input_data = {
            "searchStringsArray": [f"{niche} in {city}, {country}"],
            "maxCrawledPlacesPerSearch": limit,
            "language": "en",
            "deeperCityScrape": True,
        }
        
        try:
            # Start run
            result = self._request("POST", f"/acts/{self.GOOGLE_MAPS_ACTOR}/runs", input_data)
            run_id = result.get("data", {}).get("id")
            
            if not run_id:
                return []
            
            logger.info(f"   Run: {run_id}")
            
            # Poll for completion
            for i in range(30):  # Max 5 minutes
                time.sleep(10)
                status_result = self._request("GET", f"/actor-runs/{run_id}")
                status = status_result.get("data", {}).get("status")
                
                if status == "SUCCEEDED":
                    break
                elif status in ["FAILED", "ABORTED", "TIMED-OUT"]:
                    logger.error(f"   ❌ Run failed: {status}")
                    return []
            
            # Get results
            dataset_id = status_result.get("data", {}).get("defaultDatasetId")
            items = self._request("GET", f"/datasets/{dataset_id}/items")
            
            logger.info(f"   ✅ Found {len(items)} businesses")
            return items if isinstance(items, list) else []
            
        except Exception as e:
            logger.error(f"   ❌ Discovery error: {e}")
            return []


# =============================================================================
# TRACKING DETECTOR - Ads & WhatsApp Detection
# =============================================================================

class TrackingDetector:
    """Detect Facebook Ads, Google Ads, and WhatsApp from website HTML."""
    
    @staticmethod
    def fetch_raw_html(url: str, timeout: int = 20) -> str:
        """Fetch raw HTML directly (bypasses content extraction limitations)."""
        if not url:
            return ""
        
        if not url.startswith(('http://', 'https://')):
            url = f"https://{url}"
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        
        try:
            import ssl
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
                return resp.read().decode('utf-8', errors='ignore')
        except Exception as e:
            logger.debug(f"   Raw HTML fetch failed: {str(e)[:30]}")
            return ""
    
    @staticmethod
    def detect_all(html: str) -> Dict[str, Any]:
        """
        Detect all tracking and communication signals.
        
        Returns:
            {
                "google_tag_manager": "GTM-XXXXX" or None,
                "google_analytics_ga4": "G-XXXXXXXXXX" or None,
                "google_analytics_ua": "UA-XXXXX-X" or None,
                "google_ads": "AW-XXXXX" or True/False,
                "facebook_pixel": "XXXXXXXX" or True/False,
                "whatsapp_number": "+91XXXXXXXXXX" or None,
                "has_whatsapp": True/False,
                "has_google_ads": True/False,
                "has_facebook_ads": True/False,
            }
        """
        result = {
            "google_tag_manager": None,
            "google_analytics_ga4": None,
            "google_analytics_ua": None,
            "google_ads": None,
            "facebook_pixel": None,
            "whatsapp_number": None,
            "has_whatsapp": False,
            "has_google_ads": False,
            "has_facebook_ads": False,
        }
        
        if not html:
            return result
        
        # Google Tag Manager
        gtm_match = re.search(r"GTM-([A-Z0-9]+)", html)
        if gtm_match:
            result["google_tag_manager"] = gtm_match.group()
        
        # Google Analytics GA4
        ga4_match = re.search(r"(G-[A-Z0-9]{10,12})", html)
        if ga4_match:
            result["google_analytics_ga4"] = ga4_match.group(1)
        
        # Google Analytics UA (legacy)
        ua_match = re.search(r"(UA-\d+-\d+)", html)
        if ua_match:
            result["google_analytics_ua"] = ua_match.group(1)
        
        # Google Ads
        gads_match = re.search(r"(AW-\d+)", html)
        if gads_match:
            result["google_ads"] = gads_match.group(1)
            result["has_google_ads"] = True
        elif "googleadservices.com" in html or "adsbygoogle" in html or "google_conversion" in html:
            result["has_google_ads"] = True
        
        # Facebook Pixel
        fb_match = re.search(r"fbq\s*\(\s*['\"]init['\"],\s*['\"](\d+)['\"]", html)
        if fb_match:
            result["facebook_pixel"] = fb_match.group(1)
            result["has_facebook_ads"] = True
        elif "connect.facebook.net" in html or "fbq(" in html or "facebook.com/tr" in html:
            result["has_facebook_ads"] = True
        
        # WhatsApp
        wa_match = re.search(r"wa\.me/(\d{10,15})", html)
        if wa_match:
            result["whatsapp_number"] = f"+{wa_match.group(1)}"
            result["has_whatsapp"] = True
        elif "api.whatsapp.com/send" in html:
            result["has_whatsapp"] = True
            # Try to extract number from send link
            wa_send = re.search(r"api\.whatsapp\.com/send\?phone=(\d+)", html)
            if wa_send:
                result["whatsapp_number"] = f"+{wa_send.group(1)}"
        elif "whatsapp" in html.lower():
            # Check for WhatsApp mentions that might indicate presence
            wa_mentions = len(re.findall(r"whatsapp", html, re.I))
            if wa_mentions >= 2:  # Multiple mentions suggest they use it
                result["has_whatsapp"] = True
        
        return result


# =============================================================================
# FIRECRAWL CLIENT - Deep Website Scraping
# =============================================================================

class FirecrawlClient:
    """Firecrawl website scraper for deep enrichment."""
    
    def __init__(self):
        self.api_key = os.environ.get("FIRECRAWL_API_KEY", "")
        self.base_url = "https://api.firecrawl.dev/v1"
    
    def scrape(self, url: str) -> Dict[str, Any]:
        """Scrape a website for content and metadata."""
        if not self.api_key or not url:
            return {}
        
        # Clean URL
        if not url.startswith(('http://', 'https://')):
            url = f"https://{url}"
        
        logger.info(f"   🕷️ Firecrawl: {url[:50]}...")
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        data = {
            "url": url,
            "formats": ["markdown", "html"],
            "onlyMainContent": True,
            "waitFor": 3000,
        }
        
        try:
            req = urllib.request.Request(
                f"{self.base_url}/scrape",
                data=json.dumps(data).encode(),
                headers=headers,
                method="POST"
            )
            
            with urllib.request.urlopen(req, timeout=60) as resp:
                result = json.loads(resp.read().decode())
            
            if result.get("success"):
                return result.get("data", {})
            
            return {}
            
        except Exception as e:
            logger.warning(f"   ⚠️ Firecrawl error: {str(e)[:50]}")
            return {}
    
    def extract_contacts(self, content: str) -> ContactInfo:
        """Extract contact information from website content."""
        contacts = ContactInfo()
        
        if not content:
            return contacts
        
        # Email patterns - more comprehensive
        email_patterns = [
            r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
            r'[a-zA-Z0-9._%+-]+\s*(?:\[at\]|@)\s*[a-zA-Z0-9.-]+\s*(?:\[dot\]|\.)\s*[a-zA-Z]{2,}',
            r'mailto:([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
        ]
        all_emails = []
        for pattern in email_patterns:
            found = re.findall(pattern, content, re.IGNORECASE)
            all_emails.extend(found)
        
        # Clean and deduplicate
        cleaned_emails = []
        for email in all_emails:
            email = email.lower().strip()
            # Clean [at] and [dot] formats
            email = re.sub(r'\s*\[at\]\s*', '@', email)
            email = re.sub(r'\s*\[dot\]\s*', '.', email)
            if email and '@' in email:
                cleaned_emails.append(email)
        
        # Filter out common non-business emails
        exclude_patterns = ['example.com', 'domain.com', 'email.com', 'test.com', 
                          'yoursite', 'website', 'samplemail', 'placeholder', 
                          'noreply', 'no-reply', 'donotreply']
        contacts.emails = list(set([e for e in cleaned_emails 
                                   if not any(x in e for x in exclude_patterns)]))[:5]
        
        # Phone patterns (Indian)
        phone_patterns = [
            r'\+91[\s-]?\d{5}[\s-]?\d{5}',
            r'\d{10}',
            r'\d{5}[\s-]\d{5}',
        ]
        for pattern in phone_patterns:
            phones = re.findall(pattern, content)
            contacts.phones.extend(phones)
        contacts.phones = list(set(contacts.phones))[:5]
        
        # Social links
        social_patterns = {
            'linkedin': r'linkedin\.com/(?:company|in)/[\w-]+',
            'facebook': r'facebook\.com/[\w.]+',
            'twitter': r'twitter\.com/[\w]+',
            'instagram': r'instagram\.com/[\w.]+',
        }
        for platform, pattern in social_patterns.items():
            match = re.search(pattern, content.lower())
            if match:
                contacts.social_links[platform] = f"https://{match.group()}"
        
        return contacts
    
    def detect_tech_stack(self, html: str, markdown: str) -> TechStack:
        """Detect technology stack from website."""
        tech = TechStack()
        content = (html or "") + (markdown or "")
        content_lower = content.lower()
        
        # CMS detection
        cms_patterns = {
            'wordpress': ['wp-content', 'wordpress', 'wp-'],
            'wix': ['wix.com', '_wix'],
            'shopify': ['shopify', 'cdn.shopify'],
            'squarespace': ['squarespace'],
            'webflow': ['webflow'],
        }
        for cms, patterns in cms_patterns.items():
            if any(p in content_lower for p in patterns):
                tech.cms = cms
                break
        
        # Booking systems
        booking_patterns = {
            'practo': 'practo',
            'zocdoc': 'zocdoc',
            'calendly': 'calendly',
            'setmore': 'setmore',
            'acuity': 'acuity',
            'booknetic': 'booknetic',
            'simplybook': 'simplybook',
        }
        for system, pattern in booking_patterns.items():
            if pattern in content_lower:
                tech.booking_system = system
                break
        
        # Chat widgets
        chat_patterns = {
            'intercom': 'intercom',
            'zendesk': 'zendesk',
            'freshdesk': 'freshdesk',
            'tawk': 'tawk.to',
            'crisp': 'crisp.chat',
            'drift': 'drift.com',
            'livechat': 'livechat',
        }
        for widget, pattern in chat_patterns.items():
            if pattern in content_lower:
                tech.chat_widget = widget
                break
        
        # Analytics
        analytics_patterns = ['google-analytics', 'gtag', 'fbq', 'hotjar', 'mixpanel', 'amplitude']
        tech.analytics = [a for a in analytics_patterns if a in content_lower]
        
        # Payment
        payment_patterns = ['razorpay', 'paytm', 'phonepe', 'stripe', 'paypal']
        tech.payment = [p for p in payment_patterns if p in content_lower]
        
        return tech


# =============================================================================
# STEEL.DEV CLIENT - Browser Automation
# =============================================================================

class SteelClient:
    """Steel.dev browser automation for JS-heavy sites."""
    
    def __init__(self):
        self.api_key = os.environ.get("STEEL_API_KEY", "")
        self.base_url = "https://api.steel.dev/v1"
    
    def scrape(self, url: str) -> Dict[str, Any]:
        """Scrape a JavaScript-heavy website."""
        if not self.api_key or not url:
            return {}
        
        if not url.startswith(('http://', 'https://')):
            url = f"https://{url}"
        
        logger.info(f"   🤖 Steel: {url[:50]}...")
        
        headers = {
            "Content-Type": "application/json",
            "steel-api-key": self.api_key
        }
        
        data = {
            "url": url,
            "waitFor": 5000,
            "screenshot": False,
        }
        
        try:
            req = urllib.request.Request(
                f"{self.base_url}/scrape",
                data=json.dumps(data).encode(),
                headers=headers,
                method="POST"
            )
            
            with urllib.request.urlopen(req, timeout=90) as resp:
                result = json.loads(resp.read().decode())
            
            return result
            
        except Exception as e:
            logger.warning(f"   ⚠️ Steel error: {str(e)[:50]}")
            return {}


# =============================================================================
# OPENROUTER LLM - AI Reasoning
# =============================================================================

class OpenRouterLLM:
    """OpenRouter LLM for AI analysis."""
    
    def __init__(self):
        self.api_key = os.environ.get("OPENROUTER_API_KEY", "")
        self.model = os.environ.get("DEFAULT_LLM_MODEL", "google/gemini-2.0-flash-001")
    
    def generate(self, prompt: str, system: str = None, temp: float = 0.3) -> str:
        if not self.api_key:
            return ""
        
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        
        data = {
            "model": self.model,
            "messages": messages,
            "temperature": temp,
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
            
            return result.get("choices", [{}])[0].get("message", {}).get("content", "")
        except Exception as e:
            logger.error(f"   ❌ LLM error: {e}")
            return ""
    
    def generate_json(self, prompt: str, system: str = None) -> Dict:
        response = self.generate(f"{prompt}\n\nRespond ONLY with valid JSON.", system, temp=0.1)
        
        if not response:
            return {}
        
        try:
            # Clean response
            response = response.strip()
            if response.startswith("```"):
                response = re.sub(r'^```\w*\n?', '', response)
                response = re.sub(r'\n?```$', '', response)
            return json.loads(response)
        except:
            return {}


# =============================================================================
# INDUSTRY CONFIG
# =============================================================================

INDUSTRY_CONFIG = {
    # Healthcare
    "diagnostic": {"ticket": 1500, "leads": 500, "conversion": 0.25},
    "hospital": {"ticket": 15000, "leads": 1000, "conversion": 0.20},
    "clinic": {"ticket": 800, "leads": 300, "conversion": 0.30},
    "dental": {"ticket": 2500, "leads": 200, "conversion": 0.35},
    "eye": {"ticket": 3000, "leads": 150, "conversion": 0.30},
    "derma": {"ticket": 1500, "leads": 200, "conversion": 0.35},
    "physio": {"ticket": 800, "leads": 100, "conversion": 0.40},
    "ivf": {"ticket": 150000, "leads": 50, "conversion": 0.15},
    "cosmetic": {"ticket": 50000, "leads": 80, "conversion": 0.20},
    "vet": {"ticket": 1500, "leads": 100, "conversion": 0.35},
    
    # Home Services
    "plumber": {"ticket": 2000, "leads": 150, "conversion": 0.40},
    "electrician": {"ticket": 1500, "leads": 150, "conversion": 0.40},
    "hvac": {"ticket": 5000, "leads": 80, "conversion": 0.30},
    "contractor": {"ticket": 100000, "leads": 30, "conversion": 0.15},
    "interior": {"ticket": 200000, "leads": 20, "conversion": 0.10},
    "pest": {"ticket": 2500, "leads": 100, "conversion": 0.35},
    
    # Professional
    "lawyer": {"ticket": 10000, "leads": 50, "conversion": 0.20},
    "ca": {"ticket": 5000, "leads": 80, "conversion": 0.25},
    "consultant": {"ticket": 15000, "leads": 40, "conversion": 0.20},
    
    # Education
    "coaching": {"ticket": 50000, "leads": 100, "conversion": 0.15},
    "tuition": {"ticket": 30000, "leads": 80, "conversion": 0.20},
    
    # Default
    "default": {"ticket": 3000, "leads": 150, "conversion": 0.25},
}

def get_industry_config(category: str) -> Dict:
    """Get industry configuration."""
    category_lower = category.lower()
    for key, config in INDUSTRY_CONFIG.items():
        if key in category_lower:
            return config
    return INDUSTRY_CONFIG["default"]


# =============================================================================
# ULTIMATE INTELLIGENCE ENGINE
# =============================================================================

class UltimateIntelligenceEngine:
    """
    The ULTIMATE lead intelligence engine.
    
    Full pipeline:
    1. Discovery (Apify) → Find businesses
    2. Deep Enrichment (Firecrawl + Steel) → Extract everything
    3. AI Analysis (OpenRouter) → Reasoning & scoring
    4. Revenue Calculation → Precise loss estimation
    5. Outreach Generation → Ready-to-send content
    """
    
    def __init__(self):
        self.apify = ApifyClient()
        self.firecrawl = FirecrawlClient()
        self.steel = SteelClient()
        self.llm = OpenRouterLLM()
        self.output_dir = Path("output")
        self.output_dir.mkdir(exist_ok=True)
        
        logger.info("🚀 Ultimate Intelligence Engine v4.0 initialized")
        logger.info(f"   Apify: {'✅' if self.apify.api_token else '❌'}")
        logger.info(f"   Firecrawl: {'✅' if self.firecrawl.api_key else '❌'}")
        logger.info(f"   Steel: {'✅' if self.steel.api_key else '❌'}")
        logger.info(f"   OpenRouter: {'✅' if self.llm.api_key else '❌'}")
    
    def _deep_enrich(self, lead: BusinessLead) -> None:
        """Deep enrichment using Firecrawl and Steel."""
        if not lead.website:
            return
        
        # Try Firecrawl first
        scraped = self.firecrawl.scrape(lead.website)
        
        if scraped:
            lead.enrichment_source = "firecrawl"
            
            # Extract metadata
            metadata = scraped.get("metadata", {})
            lead.website_title = metadata.get("title", "")
            lead.website_description = metadata.get("description", "")
            
            # Get content
            markdown = scraped.get("markdown", "")
            html = scraped.get("html", "")
            
            # Extract contacts
            lead.contacts = self.firecrawl.extract_contacts(markdown + html)
            
            # Detect tech stack
            lead.tech_stack = self.firecrawl.detect_tech_stack(html, markdown)
            
            # Update enrichment flags
            if lead.tech_stack.booking_system:
                lead.has_booking_system = True
            if lead.tech_stack.chat_widget:
                lead.has_chat_widget = True
            if lead.tech_stack.payment:
                lead.has_online_payment = True
            
            # Detect WhatsApp
            if 'whatsapp' in markdown.lower() or 'wa.me' in markdown.lower():
                lead.has_whatsapp = True
            
            # Detect lead form
            if '<form' in html.lower() or 'contact' in markdown.lower():
                lead.has_lead_form = True
            
            # Store content summary (first 500 chars)
            lead.website_content_summary = markdown[:500] if markdown else ""
        
        # Fallback to Steel for JS-heavy sites
        elif self.steel.api_key:
            steel_data = self.steel.scrape(lead.website)
            if steel_data:
                lead.enrichment_source = "steel"
                content = steel_data.get("content", "")
                # Ensure content is a string
                if isinstance(content, str) and content:
                    lead.contacts = self.firecrawl.extract_contacts(content)
        
        # TRACKING DETECTION - Always fetch raw HTML for accurate detection
        logger.info(f"   📡 Detecting ads & tracking...")
        raw_html = TrackingDetector.fetch_raw_html(lead.website)
        if raw_html:
            tracking = TrackingDetector.detect_all(raw_html)
            
            # Update lead with tracking data
            lead.has_google_ads = tracking.get("has_google_ads", False)
            lead.has_facebook_ads = tracking.get("has_facebook_ads", False)
            lead.google_tag_manager_id = tracking.get("google_tag_manager") or ""
            lead.google_analytics_id = tracking.get("google_analytics_ga4") or tracking.get("google_analytics_ua") or ""
            lead.google_ads_id = tracking.get("google_ads") if isinstance(tracking.get("google_ads"), str) else ""
            lead.facebook_pixel_id = tracking.get("facebook_pixel") if isinstance(tracking.get("facebook_pixel"), str) else ""
            
            # WhatsApp from tracking (may be more accurate)
            if tracking.get("has_whatsapp"):
                lead.has_whatsapp = True
            if tracking.get("whatsapp_number"):
                lead.whatsapp_number = tracking["whatsapp_number"]
            
            # Update ads_detected flag
            lead.ads_detected = lead.has_google_ads or lead.has_facebook_ads
            
            # Log findings
            if lead.has_google_ads:
                logger.info(f"   ✅ Google Ads: {lead.google_ads_id or 'Detected'}")
            if lead.has_facebook_ads:
                logger.info(f"   ✅ Facebook Ads: {lead.facebook_pixel_id or 'Detected'}")
            if lead.whatsapp_number:
                logger.info(f"   ✅ WhatsApp: {lead.whatsapp_number}")
    
    def _calculate_scores(self, lead: BusinessLead) -> None:
        """Calculate all scoring dimensions."""
        
        # Data Quality Score (0-100)
        dq = 0
        if lead.business_name: dq += 20
        if lead.phone: dq += 20
        if lead.website: dq += 15
        if lead.contacts.emails: dq += 15
        if lead.address: dq += 10
        if lead.rating: dq += 10
        if lead.reviews_count: dq += 10
        lead.data_quality_score = min(dq, 100)
        
        # Reachability Score (0-100)
        reach = 0
        if lead.phone: reach += 30
        if lead.contacts.emails: reach += 25
        if lead.has_whatsapp: reach += 20
        if lead.contacts.social_links.get('linkedin'): reach += 15
        if lead.has_lead_form: reach += 10
        lead.reachability_score = min(reach, 100)
        
        # Opportunity Score (0-100) - Higher = More gaps = More opportunity
        opp = 0
        if not lead.has_booking_system:
            opp += 25
            lead.has_after_hours_leak = True
        if not lead.has_chat_widget:
            opp += 20
            lead.has_slow_response_risk = True
        if not lead.has_whatsapp:
            opp += 20
        if not lead.has_lead_form:
            opp += 15
            lead.has_lead_capture_gap = True
        if not lead.has_online_payment:
            opp += 10
        if lead.rating and lead.rating < 4.5 and lead.reviews_count and lead.reviews_count > 50:
            opp += 10  # Good volume but satisfaction issues
        lead.opportunity_score = min(opp, 100)
        
        # Urgency Score (0-100)
        urg = 0
        if lead.has_after_hours_leak: urg += 30
        if lead.has_slow_response_risk: urg += 25
        if lead.has_lead_capture_gap: urg += 20
        config = get_industry_config(lead.category)
        if config["ticket"] >= 5000: urg += 15  # High ticket = more urgency
        if lead.reviews_count and lead.reviews_count > 100: urg += 10  # High volume
        lead.urgency_score = min(urg, 100)
        
        # Final Score (weighted)
        lead.final_score = int(
            lead.data_quality_score * 0.20 +
            lead.reachability_score * 0.25 +
            lead.opportunity_score * 0.35 +
            lead.urgency_score * 0.20
        )
    
    def _calculate_revenue(self, lead: BusinessLead) -> None:
        """Calculate revenue loss and ROI."""
        config = get_industry_config(lead.category)
        
        ticket = config["ticket"]
        monthly_leads = config["leads"]
        base_conversion = config["conversion"]
        
        # Adjust based on reviews (proxy for business size)
        if lead.reviews_count:
            if lead.reviews_count > 500:
                monthly_leads = int(monthly_leads * 1.5)
            elif lead.reviews_count > 200:
                monthly_leads = int(monthly_leads * 1.2)
            elif lead.reviews_count < 50:
                monthly_leads = int(monthly_leads * 0.7)
        
        lead.estimated_monthly_leads = monthly_leads
        
        # Calculate missed percentage
        missed_pct = 0.0
        if not lead.has_booking_system:
            missed_pct += 0.15
        if not lead.has_chat_widget:
            missed_pct += 0.10
        if not lead.has_whatsapp:
            missed_pct += 0.10
        if lead.has_slow_response_risk:
            missed_pct += 0.05
        if lead.has_lead_capture_gap:
            missed_pct += 0.05
        
        lead.estimated_missed_pct = min(missed_pct, 0.50)
        
        # Revenue calculations
        missed_leads = int(monthly_leads * lead.estimated_missed_pct)
        converted_revenue = missed_leads * ticket * base_conversion
        lead.estimated_revenue_loss_inr = int(converted_revenue)
        lead.recoverable_amount_inr = int(converted_revenue * 0.70)  # 70% recovery rate
        
        # Recommend tier and calculate ROI
        loss = lead.estimated_revenue_loss_inr
        if loss >= 200000:
            lead.recommended_tier = "Enterprise ₹1.5L/month"
            our_cost = 150000
        elif loss >= 100000:
            lead.recommended_tier = "Pro ₹60K/month"
            our_cost = 60000
        elif loss >= 50000:
            lead.recommended_tier = "Growth ₹35K/month"
            our_cost = 35000
        else:
            lead.recommended_tier = "Starter ₹15K/month"
            our_cost = 15000
        
        lead.roi_multiple = lead.recoverable_amount_inr / our_cost if our_cost else 0
        lead.payback_days = int(30 / lead.roi_multiple) if lead.roi_multiple > 0 else 999
    
    def _ai_analyze(self, lead: BusinessLead) -> None:
        """Deep AI analysis of the lead."""
        
        # Build context-specific prompt
        website_context = ""
        if lead.website_content_summary:
            website_context = f"\nWEBSITE CONTENT PREVIEW:\n{lead.website_content_summary[:300]}..."
        
        services_context = ""
        if lead.services_offered:
            services_context = f"\nSERVICES OFFERED: {', '.join(lead.services_offered[:5])}"
        
        prompt = f"""Analyze this {lead.category} business in {lead.city} for B2B sales potential.

BUSINESS PROFILE:
- Name: {lead.business_name}
- Category: {lead.category}
- Location: {lead.city}, {lead.area}
- Website: {lead.website or 'None'}
- Google Rating: {lead.rating or 'N/A'}/5 ({lead.reviews_count or 0} reviews)
{website_context}
{services_context}

CONTACT INTELLIGENCE:
- Primary Phone: {lead.phone or 'None'}
- Email(s): {', '.join(lead.contacts.emails[:3]) if lead.contacts.emails else 'Not found'}
- LinkedIn: {lead.contacts.social_links.get('linkedin', 'Not found')}
- Social Presence: {', '.join(lead.contacts.social_links.keys()) if lead.contacts.social_links else 'None'}

TECHNOLOGY AUDIT:
- Website CMS: {lead.tech_stack.cms or 'Unknown'}
- Booking System: {lead.tech_stack.booking_system or '❌ NOT DETECTED'}
- Chat Widget: {lead.tech_stack.chat_widget or '❌ NOT DETECTED'}
- Analytics: {', '.join(lead.tech_stack.analytics) if lead.tech_stack.analytics else 'Unknown'}
- Payment: {', '.join(lead.tech_stack.payment) if lead.tech_stack.payment else 'Unknown'}

CRITICAL GAPS IDENTIFIED:
- Online Booking: {'❌ MISSING' if not lead.has_booking_system else '✅ Present'}
- Live Chat: {'❌ MISSING' if not lead.has_chat_widget else '✅ Present'}
- WhatsApp Business: {'❌ MISSING' if not lead.has_whatsapp else '✅ Present'}
- Lead Capture Form: {'❌ MISSING' if not lead.has_lead_form else '✅ Present'}
- Online Payment: {'❌ MISSING' if not lead.has_online_payment else '✅ Present'}

LEAD SCORES:
- Data Quality: {lead.data_quality_score}/100
- Reachability: {lead.reachability_score}/100
- Opportunity Size: {lead.opportunity_score}/100
- Urgency Level: {lead.urgency_score}/100
- FINAL SCORE: {lead.final_score}/100

REVENUE IMPACT ANALYSIS:
- Estimated Monthly Inquiries: {lead.estimated_monthly_leads}
- Estimated Leakage: {int(lead.estimated_missed_pct * 100)}%
- Monthly Revenue Loss: ₹{lead.estimated_revenue_loss_inr:,}
- Recoverable with Our Solution: ₹{lead.recoverable_amount_inr:,}
- Recommended Tier: {lead.recommended_tier}
- Projected ROI: {lead.roi_multiple:.1f}x

YOUR TASK:
1. Validate if this is a REAL business worth pursuing
2. Identify 3 SPECIFIC pain points based on their gaps
3. Create 3 PERSONALIZED selling angles (not generic)
4. Prepare objection handlers for price, timing, and need
5. Flag any validation concerns

Respond with JSON:
{{
    "verdict": "ACCEPT|REVIEW|REJECT",
    "reasoning": "2-3 sentences explaining your decision with specific details about THIS business",
    "pain_points": [
        "Specific pain point 1 mentioning their business name/category",
        "Specific pain point 2 with revenue impact",
        "Specific pain point 3 related to their gaps"
    ],
    "selling_angles": [
        "Personalized angle 1 for {lead.category}",
        "Personalized angle 2 mentioning their review count/rating",
        "Personalized angle 3 with ROI numbers"
    ],
    "objections": {{
        "price": "How to handle 'too expensive' using their revenue loss",
        "timing": "How to handle 'not now' using urgency signals",
        "need": "How to handle 'we're fine' using their gaps"
    }},
    "issues": ["List any validation concerns"]
}}"""

        system = """You are an elite B2B sales analyst specializing in lead qualification.

VERDICT CRITERIA:
- ACCEPT: Real business, good data quality (60+), reachable, clear opportunity (50+ opp score)
- REVIEW: Potentially valid but needs verification, medium scores (40-60)
- REJECT: Fake/test data, unreachable (<40 data quality), no opportunity

IMPORTANT:
- Be SPECIFIC - mention the business name and category in your responses
- Use EXACT numbers from the revenue analysis
- Tailor objection handlers to their specific situation
- Flag suspicious patterns (test data, placeholder info, etc.)"""

        result = self.llm.generate_json(prompt, system)
        
        if result:
            lead.reasoning_verdict = result.get("verdict", "REVIEW")
            lead.ai_reasoning = result.get("reasoning", "")
            lead.pain_points = result.get("pain_points", [])
            lead.selling_angles = result.get("selling_angles", [])
            lead.objection_handlers = result.get("objections", {})
            lead.validation_issues = result.get("issues", [])
        else:
            # Fallback with personalized reasoning
            if lead.final_score >= 60 and lead.opportunity_score >= 50:
                lead.reasoning_verdict = "ACCEPT"
                lead.ai_reasoning = f"{lead.business_name} shows strong opportunity with {lead.reviews_count or 'multiple'} reviews and missing {sum([not lead.has_booking_system, not lead.has_chat_widget, not lead.has_whatsapp])} key systems."
            elif lead.final_score >= 40:
                lead.reasoning_verdict = "REVIEW"
                lead.ai_reasoning = f"{lead.business_name} has moderate potential. Score {lead.final_score}/100 with ₹{lead.estimated_revenue_loss_inr:,}/mo opportunity."
            else:
                lead.reasoning_verdict = "REJECT"
                lead.ai_reasoning = f"Low potential - Score {lead.final_score}/100, insufficient data quality."
    
    def _assign_tier(self, lead: BusinessLead) -> None:
        """Assign tier and priority."""
        score = lead.final_score
        opp = lead.opportunity_score
        
        if score >= 70 and opp >= 50:
            lead.tier = LeadTier.HOT
            lead.priority = PriorityLevel.CRITICAL
        elif score >= 70:
            lead.tier = LeadTier.HOT
            lead.priority = PriorityLevel.HIGH
        elif score >= 50 and opp >= 40:
            lead.tier = LeadTier.WARM
            lead.priority = PriorityLevel.HIGH
        elif score >= 50:
            lead.tier = LeadTier.WARM
            lead.priority = PriorityLevel.MEDIUM
        else:
            lead.tier = LeadTier.COLD
            lead.priority = PriorityLevel.LOW
    
    def _generate_outreach(self, lead: BusinessLead) -> None:
        """Generate all outreach content."""
        loss_str = f"₹{lead.estimated_revenue_loss_inr/100000:.1f}L" if lead.estimated_revenue_loss_inr >= 100000 else f"₹{lead.estimated_revenue_loss_inr/1000:.0f}K"
        recoverable_str = f"₹{lead.recoverable_amount_inr/100000:.1f}L" if lead.recoverable_amount_inr >= 100000 else f"₹{lead.recoverable_amount_inr/1000:.0f}K"
        
        # Email
        lead.email_subject = f"Quick question about {lead.business_name}"
        
        pain_point = lead.pain_points[0] if lead.pain_points else "missed appointments"
        selling_angle = lead.selling_angles[0] if lead.selling_angles else "WhatsApp automation"
        
        lead.email_body = f"""Hi,

Noticed {lead.business_name} on Google - {lead.reviews_count or 'many'} reviews, solid presence.

Quick analysis: you're likely losing {loss_str}/month in {pain_point}.

We've helped similar {lead.category} businesses recover {recoverable_str}/month with {selling_angle}.

ROI: {lead.roi_multiple:.1f}x (payback in ~{lead.payback_days} days)

2-min call to discuss?

Best,
[Your Name]

P.S. Happy to share a free audit showing exact ₹ being lost."""

        # WhatsApp
        lead.whatsapp_msg = f"""Hi! Quick note about {lead.business_name}.

Based on your {lead.reviews_count or 'many'} Google reviews, you're likely missing {loss_str}/month in {pain_point}.

We can recover {recoverable_str}/month with {selling_angle}.

ROI: {lead.roi_multiple:.1f}x

Want a free audit? Reply YES"""

        # Call Script
        lead.call_script = f"""Hi, is this [Owner/Manager] from {lead.business_name}?

Great! I'm [Name] from [Company]. I help {lead.category} businesses recover lost revenue.

I noticed from your Google listing you're getting good traffic - {lead.reviews_count or 'many'} reviews.

Quick question: how are you currently handling {pain_point}?

[Listen]

Got it. What we've found is businesses like yours typically lose {loss_str}/month there.

We can recover about {recoverable_str} with {selling_angle}.

Would you be open to a quick audit? It's free and shows exact ₹ being lost."""

        # Loom Script
        lead.loom_script = f"""[60 seconds]

Hey! Found {lead.business_name} while researching {lead.category} businesses in {lead.city}.

{lead.reviews_count or 'Many'} reviews - clearly you're doing something right.

But I noticed something: {pain_point}.

Quick math:
- {lead.estimated_monthly_leads} leads/month
- ~{int(lead.estimated_missed_pct * 100)}% missed
- {loss_str}/month gone

We can recover {recoverable_str} with {selling_angle}.

ROI: {lead.roi_multiple:.1f}x

Want a free audit? Email me at [email]"""

        # LinkedIn Note
        lead.linkedin_note = f"""Hi! Came across {lead.business_name} - impressive {lead.reviews_count or ''} reviews.

I help {lead.category} businesses recover lost revenue. Noticed a few gaps that might be costing you {loss_str}/month.

Worth a quick chat?"""

        # Follow-up Sequence
        lead.follow_up_sequence = [
            {"day": 3, "channel": "email", "subject": f"Re: {lead.business_name} - the {loss_str}/month question"},
            {"day": 7, "channel": "whatsapp", "message": f"Following up - still interested in that free audit for {lead.business_name}?"},
            {"day": 14, "channel": "email", "subject": f"Last check: {recoverable_str} recovery for {lead.business_name}"},
        ]
    
    def process_lead(self, raw_data: Dict, category: str, city: str) -> Optional[BusinessLead]:
        """Process a single lead through the full pipeline."""
        
        # Create lead
        lead_id = hashlib.md5(
            f"{raw_data.get('title', '')}{raw_data.get('address', '')}".encode()
        ).hexdigest()[:16]
        
        lead = BusinessLead(
            lead_id=lead_id,
            business_name=raw_data.get("title") or raw_data.get("name", "Unknown"),
            category=category,
            city=city,
            area=raw_data.get("city") or raw_data.get("neighborhood", ""),
            website=raw_data.get("website") or "",
            phone=raw_data.get("phone") or "",
            google_maps_url=raw_data.get("url") or "",
            rating=raw_data.get("totalScore") or raw_data.get("rating"),
            reviews_count=raw_data.get("reviewsCount") or raw_data.get("reviews"),
            address=raw_data.get("address") or "",
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        
        # Initial contact from raw data
        if raw_data.get("email"):
            lead.contacts.emails.append(raw_data["email"])
        if lead.phone:
            lead.contacts.phones.append(lead.phone)
        lead.has_click_to_call = bool(lead.phone)
        
        logger.info(f"   📊 Processing: {lead.business_name[:40]}")
        
        # Step 1: Deep Enrichment
        self._deep_enrich(lead)
        
        # Step 2: Calculate Scores
        self._calculate_scores(lead)
        
        # Skip low quality
        if lead.data_quality_score < 30:
            logger.info(f"   ⏭️ Skipped (low quality: {lead.data_quality_score})")
            return None
        
        # Step 3: Revenue Calculation
        self._calculate_revenue(lead)
        
        # Step 4: AI Analysis
        self._ai_analyze(lead)
        
        # Skip rejected
        if lead.reasoning_verdict == "REJECT":
            logger.info(f"   ❌ Rejected: {lead.ai_reasoning[:50]}")
            return None
        
        # Step 5: Assign Tier
        self._assign_tier(lead)
        
        # Step 6: Generate Outreach
        self._generate_outreach(lead)
        
        lead.status = "enriched"
        lead.updated_at = datetime.now(timezone.utc).isoformat()
        
        tier_emoji = "🔥" if lead.tier == LeadTier.HOT else "☀️" if lead.tier == LeadTier.WARM else "❄️"
        logger.info(f"   {tier_emoji} {lead.tier.value} | Score: {lead.final_score} | Loss: ₹{lead.estimated_revenue_loss_inr:,}/mo")
        
        return lead
    
    def run(
        self,
        niche: str,
        city: str,
        country: str = "India",
        target: int = 10
    ) -> Dict[str, Any]:
        """
        Run the full intelligence pipeline.
        
        Args:
            niche: Business category
            city: Target city
            country: Target country
            target: Number of leads to process
            
        Returns:
            Complete intelligence report
        """
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_dir = self.output_dir / f"{city}_{niche.replace(' ', '_')}_{run_id}"
        run_dir.mkdir(exist_ok=True)
        
        print("\n" + "=" * 70)
        print("🚀 ZRAI ULTIMATE INTELLIGENCE ENGINE v4.0")
        print("=" * 70)
        print(f"   Target: {niche} in {city}, {country}")
        print(f"   Goal: {target} leads")
        print("=" * 70)
        
        # Phase 1: Discovery
        print("\n📍 PHASE 1: DISCOVERY")
        raw_leads = self.apify.discover(niche, city, country, limit=target * 2)
        
        if not raw_leads:
            return {"error": "Discovery failed", "leads": []}
        
        # Phase 2: Processing
        print(f"\n🔬 PHASE 2: INTELLIGENCE PROCESSING")
        
        processed: List[BusinessLead] = []
        stats = {"hot": 0, "warm": 0, "cold": 0}
        
        for i, raw in enumerate(raw_leads, 1):
            if len(processed) >= target:
                break
            
            print(f"\n[{i}/{len(raw_leads)}]")
            lead = self.process_lead(raw, niche, city)
            
            if lead:
                processed.append(lead)
                stats[lead.tier.value.lower()] += 1
        
        # Sort by tier and score
        processed.sort(key=lambda x: (
            0 if x.tier == LeadTier.HOT else 1 if x.tier == LeadTier.WARM else 2,
            -x.final_score
        ))
        
        # Create report
        total_opportunity = sum(l.estimated_revenue_loss_inr for l in processed)
        
        report = {
            "run_id": run_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "config": {
                "niche": niche,
                "city": city,
                "country": country,
                "target": target,
            },
            "summary": {
                "discovered": len(raw_leads),
                "processed": len(processed),
                "hot": stats["hot"],
                "warm": stats["warm"],
                "cold": stats["cold"],
                "total_opportunity_inr": total_opportunity,
                "total_opportunity_annual_inr": total_opportunity * 12,
            },
            "leads": [l.to_dict() for l in processed],
        }
        
        # Save files
        with open(run_dir / "report.json", 'w') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        with open(run_dir / "leads.json", 'w') as f:
            json.dump(report["leads"], f, indent=2, ensure_ascii=False)
        
        # Save HOT leads separately
        hot_leads = [l for l in processed if l.tier == LeadTier.HOT]
        if hot_leads:
            with open(run_dir / "hot_leads.json", 'w') as f:
                json.dump([l.to_dict() for l in hot_leads], f, indent=2, ensure_ascii=False)
        
        # Save outreach CSV
        self._save_outreach_csv(processed, run_dir / "outreach.csv")
        
        # Print Summary
        self._print_summary(report, run_dir)
        
        return report
    
    def _save_outreach_csv(self, leads: List[BusinessLead], path: Path) -> None:
        """Save leads as CSV for easy outreach."""
        import csv
        
        with open(path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                'Business Name', 'Category', 'City', 'Phone', 'Email', 'Website',
                'Rating', 'Reviews', 'Tier', 'Score', 'Loss/Month', 'Recoverable',
                'Email Subject', 'WhatsApp Message'
            ])
            
            for lead in leads:
                writer.writerow([
                    lead.business_name,
                    lead.category,
                    lead.city,
                    lead.phone,
                    lead.contacts.emails[0] if lead.contacts.emails else '',
                    lead.website,
                    lead.rating,
                    lead.reviews_count,
                    lead.tier.value,
                    lead.final_score,
                    lead.estimated_revenue_loss_inr,
                    lead.recoverable_amount_inr,
                    lead.email_subject,
                    lead.whatsapp_msg[:100] + '...' if len(lead.whatsapp_msg) > 100 else lead.whatsapp_msg
                ])
    
    def _print_summary(self, report: Dict, run_dir: Path) -> None:
        """Print beautiful summary."""
        s = report["summary"]
        c = report["config"]
        
        print("\n" + "=" * 70)
        print("✅ INTELLIGENCE RUN COMPLETE")
        print("=" * 70)
        print(f"\n📁 Output: {run_dir}")
        print(f"\n📊 RESULTS:")
        print(f"   Discovered:  {s['discovered']}")
        print(f"   Processed:   {s['processed']}")
        print(f"   🔥 HOT:      {s['hot']}")
        print(f"   ☀️ WARM:     {s['warm']}")
        print(f"   ❄️ COLD:     {s['cold']}")
        print(f"\n💰 TOTAL OPPORTUNITY:")
        print(f"   Monthly: ₹{s['total_opportunity_inr']:,}")
        print(f"   Annual:  ₹{s['total_opportunity_annual_inr']:,}")
        
        if report["leads"]:
            print("\n🎯 TOP LEADS:")
            for i, lead in enumerate(report["leads"][:5], 1):
                emoji = "🔥" if lead["tier"] == "HOT" else "☀️" if lead["tier"] == "WARM" else "❄️"
                name = lead["business_name"][:35]
                print(f"   {i}. {emoji} {name:<35} | {lead['final_score']:>3} | ₹{lead['estimated_revenue_loss_inr']:>7,}/mo")
        
        print("\n📄 FILES SAVED:")
        print(f"   • report.json - Full intelligence report")
        print(f"   • leads.json - All processed leads")
        print(f"   • hot_leads.json - HOT tier only")
        print(f"   • outreach.csv - Ready for outreach")
        
        print("\n" + "=" * 70)
        print("🚀 GO CLOSE DEALS!")
        print("=" * 70 + "\n")


# =============================================================================
# CLI
# =============================================================================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="ZRAI Ultimate Intelligence Engine v4.0")
    parser.add_argument("--niche", type=str, required=True, help="Business category")
    parser.add_argument("--city", type=str, required=True, help="Target city")
    parser.add_argument("--country", type=str, default="India", help="Target country")
    parser.add_argument("--count", type=int, default=10, help="Number of leads")
    
    args = parser.parse_args()
    
    engine = UltimateIntelligenceEngine()
    report = engine.run(
        niche=args.niche,
        city=args.city,
        country=args.country,
        target=args.count
    )
    
    if report.get("error"):
        print(f"\n❌ Error: {report['error']}")
        sys.exit(1)


if __name__ == "__main__":
    main()
