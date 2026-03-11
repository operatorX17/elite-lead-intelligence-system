#!/usr/bin/env python3
"""
LEAD-OS V2 — Production Intelligence Engine
=============================================
Unified CLI tool for lead discovery, analysis, scoring, and export.
No external database required — uses local SQLite + JSON.

Usage:
    python lead_os_v2.py --city "Hyderabad" --niche "dental" --count 20
    python lead_os_v2.py --dry-run --city "Mumbai" --niche "hospital" --count 5
"""

import os, sys, json, csv, re, time, hashlib, logging, ssl, sqlite3, asyncio, aiohttp
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
import urllib.request, urllib.error, urllib.parse

from dotenv import load_dotenv
load_dotenv()

# Fix Windows Unicode output
import sys
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from lead_os_config import (
    LeadTier, PriorityLevel, INDUSTRY_CONFIG, get_industry_config,
    NICHE_KEYWORDS, SCORING_WEIGHTS, TIER_THRESHOLDS,
    CMS_PATTERNS, BOOKING_SYSTEM_PATTERNS, CHAT_WIDGET_PATTERNS,
    ANALYTICS_PATTERNS, PAYMENT_PATTERNS, REVENUE_TIERS,
    CACHE_DIR, CACHE_EXPIRY_HOURS, MAX_RETRIES, RETRY_BACKOFF_BASE,
    RATE_LIMIT_DELAY, BATCH_SIZE,
)

# ─── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("LeadOS")

try:
    from rich.console import Console
    from rich.table import Table
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
    from rich.panel import Panel
    console = Console(force_terminal=True)
    HAS_RICH = True
except ImportError:
    HAS_RICH = False
    class _FallbackConsole:
        def print(self, *a, **kw):
            text = str(a[0]) if a else ""
            text = re.sub(r"\[.*?\]", "", text)
            print(text)
    console = _FallbackConsole()


# ═══════════════════════════════════════════════════════════════════════════════
# DATA MODEL
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class BusinessLead:
    lead_id: str = ""
    business_name: str = ""
    category: str = ""
    city: str = ""
    area: str = ""
    address: str = ""
    website: str = ""
    phone: str = ""
    google_maps_url: str = ""
    rating: Optional[float] = None
    reviews_count: Optional[int] = None
    # Contacts
    emails: List[str] = field(default_factory=list)
    phones: List[str] = field(default_factory=list)
    owner_name: str = ""
    doctor_name: str = ""
    linkedin_url: str = ""
    instagram_url: str = ""
    facebook_url: str = ""
    twitter_url: str = ""
    whatsapp_number: str = ""
    # Website intelligence
    website_title: str = ""
    website_description: str = ""
    website_content_preview: str = ""
    services: List[str] = field(default_factory=list)
    business_hours: str = ""
    estimated_size: str = ""
    # Tech stack
    cms: str = ""
    booking_system: str = ""
    chat_widget: str = ""
    analytics_tools: List[str] = field(default_factory=list)
    payment_tools: List[str] = field(default_factory=list)
    # Detection flags
    has_booking: bool = False
    has_whatsapp: bool = False
    has_lead_form: bool = False
    has_chat_widget: bool = False
    has_click_to_call: bool = False
    has_online_payment: bool = False
    has_google_ads: bool = False
    has_facebook_pixel: bool = False
    has_reviews_mgmt: bool = False
    google_tag_manager_id: str = ""
    google_analytics_id: str = ""
    google_ads_id: str = ""
    facebook_pixel_id: str = ""
    # Weakness signals
    weaknesses: List[str] = field(default_factory=list)
    weakness_count: int = 0
    # Scores
    data_quality_score: int = 0
    reachability_score: int = 0
    opportunity_score: int = 0
    urgency_score: int = 0
    growth_score: int = 0
    marketing_gap_score: int = 0
    final_score: int = 0
    tier: str = "COLD"
    priority: str = "LOW"
    # Revenue
    estimated_monthly_leads: int = 0
    estimated_missed_pct: float = 0.0
    estimated_revenue_loss: int = 0
    recoverable_amount: int = 0
    recommended_tier: str = ""
    roi_multiple: float = 0.0
    payback_days: int = 0
    # AI analysis
    ai_verdict: str = ""
    ai_reasoning: str = ""
    pain_points: List[str] = field(default_factory=list)
    selling_angles: List[str] = field(default_factory=list)
    outreach_angle: str = ""
    # Outreach
    email_subject: str = ""
    email_body: str = ""
    whatsapp_msg: str = ""
    call_script: str = ""
    # Intelligence report
    intelligence_report: str = ""
    # Enrichment source
    enrichment_source: str = ""
    status: str = "discovered"
    created_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        for k in ("emails", "phones", "services", "analytics_tools",
                   "payment_tools", "weaknesses", "pain_points", "selling_angles"):
            if isinstance(d.get(k), list):
                d[k] = json.dumps(d[k])
        return d

    @staticmethod
    def csv_headers() -> List[str]:
        return [
            "lead_id", "business_name", "category", "city", "area", "address",
            "website", "phone", "google_maps_url", "rating", "reviews_count",
            "emails", "phones", "owner_name", "doctor_name", "linkedin_url",
            "whatsapp_number", "website_title", "cms", "booking_system",
            "chat_widget", "has_booking", "has_whatsapp", "has_lead_form",
            "has_chat_widget", "has_google_ads", "has_facebook_pixel",
            "weaknesses", "weakness_count", "final_score", "tier", "priority",
            "estimated_revenue_loss", "recoverable_amount", "recommended_tier",
            "roi_multiple", "ai_verdict", "outreach_angle",
            "email_subject", "whatsapp_msg",
        ]


# ═══════════════════════════════════════════════════════════════════════════════
# MODULE 10: RELIABILITY LAYER
# ═══════════════════════════════════════════════════════════════════════════════

class ReliabilityLayer:
    """Retry logic, caching, rate limiting, and API abstraction."""

    def __init__(self):
        self._cache_dir = Path(CACHE_DIR)
        self._cache_dir.mkdir(exist_ok=True)

    # ── Retry with backoff ──
    @staticmethod
    def retry(func, *args, max_retries=MAX_RETRIES, **kwargs):
        for attempt in range(max_retries + 1):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if attempt == max_retries:
                    logger.error(f"Failed after {max_retries+1} attempts: {e}")
                    return None
                wait = RETRY_BACKOFF_BASE ** attempt
                logger.warning(f"Retry {attempt+1}/{max_retries} in {wait}s: {e}")
                time.sleep(wait)

    # ── Disk cache ──
    def cache_get(self, key: str) -> Optional[Dict]:
        path = self._cache_dir / f"{hashlib.md5(key.encode()).hexdigest()}.json"
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            cached_at = datetime.fromisoformat(data.get("_cached_at", "2000-01-01"))
            if datetime.now() - cached_at > timedelta(hours=CACHE_EXPIRY_HOURS):
                path.unlink(missing_ok=True)
                return None
            return data
        except Exception:
            return None

    def cache_set(self, key: str, data: Dict):
        path = self._cache_dir / f"{hashlib.md5(key.encode()).hexdigest()}.json"
        data["_cached_at"] = datetime.now().isoformat()
        path.write_text(json.dumps(data, ensure_ascii=False, default=str), encoding="utf-8")

    # ── HTTP helpers ──
    @staticmethod
    def http_get(url: str, headers: Dict = None, timeout: int = 30) -> Optional[str]:
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            h = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"}
            if headers:
                h.update(headers)
            req = urllib.request.Request(url, headers=h)
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
                return resp.read().decode("utf-8", errors="ignore")
        except Exception:
            return None

    @staticmethod
    def http_post_json(url: str, data: Dict, headers: Dict = None, timeout: int = 60) -> Optional[Dict]:
        try:
            h = {"Content-Type": "application/json"}
            if headers:
                h.update(headers)
            body = json.dumps(data).encode()
            req = urllib.request.Request(url, data=body, headers=h, method="POST")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode())
        except Exception as e:
            logger.debug(f"HTTP POST failed: {e}")
            return None

    # ── Rate limiter ──
    _last_call_time = 0.0

    @classmethod
    def rate_limit(cls):
        elapsed = time.time() - cls._last_call_time
        if elapsed < RATE_LIMIT_DELAY:
            time.sleep(RATE_LIMIT_DELAY - elapsed)
        cls._last_call_time = time.time()


rl = ReliabilityLayer()


# ═══════════════════════════════════════════════════════════════════════════════
# MODULE 1: LEAD DISCOVERY ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

class LeadDiscoveryEngine:
    """Discover businesses from Google Maps via Apify, with pagination and dedup."""

    ACTOR_ID = "nwua9Gu5YrADL7ZDj"

    def __init__(self):
        self.api_token = os.getenv("APIFY_API_TOKEN", "")
        self.base = "https://api.apify.com/v2"

    def discover(self, niche: str, city: str, country: str = "India",
                 limit: int = 50) -> List[Dict]:
        if not self.api_token:
            logger.error("APIFY_API_TOKEN not set — cannot discover leads")
            return []

        keywords = NICHE_KEYWORDS.get(niche, [niche])
        all_results = []

        for kw in keywords:
            if len(all_results) >= limit:
                break
            query = f"{kw} in {city}, {country}"
            logger.info(f"🔍 Discovering: {query}")
            batch = self._run_actor(query, min(limit - len(all_results), 100))
            all_results.extend(batch)
            rl.rate_limit()

        # Deduplicate by name+address hash
        seen = set()
        deduped = []
        for r in all_results:
            key = f"{r.get('title','')}{r.get('address','')}".lower().strip()
            h = hashlib.md5(key.encode()).hexdigest()
            if h not in seen:
                seen.add(h)
                deduped.append(r)

        logger.info(f"✅ Discovered {len(deduped)} unique leads (from {len(all_results)} raw)")
        return deduped[:limit]

    def _run_actor(self, query: str, limit: int) -> List[Dict]:
        input_data = {
            "searchStringsArray": [query],
            "maxCrawledPlacesPerSearch": limit,
            "language": "en",
            "deeperCityScrape": True,
        }
        result = rl.retry(
            rl.http_post_json,
            f"{self.base}/acts/{self.ACTOR_ID}/runs?token={self.api_token}",
            input_data, timeout=60
        )
        if not result:
            return []

        run_id = result.get("data", {}).get("id")
        if not run_id:
            return []

        # Poll
        for _ in range(36):  # 6 minutes max
            time.sleep(10)
            status_url = f"{self.base}/actor-runs/{run_id}?token={self.api_token}"
            sr = rl.retry(rl.http_get, status_url)
            if not sr:
                continue
            try:
                sd = json.loads(sr)
            except Exception:
                continue
            status = sd.get("data", {}).get("status", "")
            if status == "SUCCEEDED":
                ds_id = sd["data"].get("defaultDatasetId")
                items_url = f"{self.base}/datasets/{ds_id}/items?token={self.api_token}"
                raw = rl.http_get(items_url)
                if raw:
                    try:
                        return json.loads(raw)
                    except Exception:
                        pass
                return []
            if status in ("FAILED", "ABORTED", "TIMED-OUT"):
                logger.error(f"Apify run {status}")
                return []
        return []

    @staticmethod
    def generate_mock_leads(city: str, niche: str, count: int) -> List[Dict]:
        """Generate mock leads for --dry-run testing."""
        mock = []
        areas = ["Banjara Hills", "Jubilee Hills", "Madhapur", "Kukatpally",
                 "Secunderabad", "Gachibowli", "Hitech City", "Ameerpet",
                 "Kondapur", "Begumpet", "Somajiguda", "Lakdi Ka Pul"]
        for i in range(count):
            area = areas[i % len(areas)]
            mock.append({
                "title": f"{area} {niche.title()} Clinic {'Plus' if i % 3 == 0 else 'Care' if i % 3 == 1 else 'Center'}",
                "address": f"Plot {10+i}, {area}, {city}",
                "phone": f"+91 98765 {43210 + i}",
                "website": f"https://www.{area.lower().replace(' ','')}clinic.com" if i % 4 != 0 else "",
                "totalScore": round(3.5 + (i % 15) * 0.1, 1),
                "reviewsCount": 20 + i * 17,
                "url": f"https://maps.google.com/place/{area.lower().replace(' ','+')}",
                "city": area,
                "email": f"info@{area.lower().replace(' ','')}clinic.com" if i % 3 == 0 else "",
            })
        return mock


# ═══════════════════════════════════════════════════════════════════════════════
# MODULE 2: WEBSITE INTELLIGENCE SCANNER
# ═══════════════════════════════════════════════════════════════════════════════

class WebsiteIntelligenceScanner:
    """Scan websites for booking systems, WhatsApp, forms, pixels, tech stack."""

    def __init__(self):
        self.firecrawl_key = os.getenv("FIRECRAWL_API_KEY", "")
        self.steel_key = os.getenv("STEEL_API_KEY", "")

    def scan(self, lead: BusinessLead) -> None:
        if not lead.website:
            return

        # Check cache first
        cached = rl.cache_get(f"scan:{lead.website}")
        if cached:
            self._apply_scan_results(lead, cached)
            lead.enrichment_source = "cache"
            return

        # Try Firecrawl
        scan_data = self._firecrawl_scan(lead.website)
        if not scan_data:
            scan_data = {}

        # Always fetch raw HTML for tracking detection
        raw_html = rl.http_get(lead.website) or ""
        tracking = self._detect_tracking(raw_html)
        scan_data.update(tracking)

        # Detect tech stack from HTML
        tech = self._detect_tech_stack(raw_html, scan_data.get("markdown", ""))
        scan_data.update(tech)

        # Extract contacts from content
        content = scan_data.get("markdown", "") + raw_html
        contacts = self._extract_contacts(content)
        scan_data.update(contacts)

        # Detect forms and interactive elements
        forms = self._detect_forms(raw_html)
        scan_data.update(forms)

        # Cache and apply
        rl.cache_set(f"scan:{lead.website}", scan_data)
        self._apply_scan_results(lead, scan_data)
        lead.enrichment_source = scan_data.get("source", "raw_html")

    def _firecrawl_scan(self, url: str) -> Optional[Dict]:
        if not self.firecrawl_key:
            return None
        rl.rate_limit()
        result = rl.retry(
            rl.http_post_json,
            "https://api.firecrawl.dev/v1/scrape",
            {"url": url, "formats": ["markdown", "html"], "onlyMainContent": True, "waitFor": 3000},
            {"Authorization": f"Bearer {self.firecrawl_key}", "Content-Type": "application/json"},
        )
        if result and result.get("success"):
            data = result.get("data", {})
            meta = data.get("metadata", {})
            return {
                "source": "firecrawl",
                "markdown": data.get("markdown", ""),
                "html": data.get("html", ""),
                "title": meta.get("title", ""),
                "description": meta.get("description", ""),
            }
        return None

    def _detect_tracking(self, html: str) -> Dict:
        r = {}
        if not html:
            return r
        # GTM
        m = re.search(r"GTM-([A-Z0-9]+)", html)
        r["gtm_id"] = m.group() if m else ""
        # GA4
        m = re.search(r"(G-[A-Z0-9]{10,12})", html)
        r["ga4_id"] = m.group(1) if m else ""
        # UA
        m = re.search(r"(UA-\d+-\d+)", html)
        r["ua_id"] = m.group(1) if m else ""
        # Google Ads
        m = re.search(r"(AW-\d+)", html)
        r["gads_id"] = m.group(1) if m else ""
        r["has_google_ads"] = bool(r["gads_id"]) or "googleadservices.com" in html or "adsbygoogle" in html
        # Facebook Pixel
        m = re.search(r"fbq\s*\(\s*['\"]init['\"],\s*['\"](\d+)['\"]", html)
        r["fb_pixel_id"] = m.group(1) if m else ""
        r["has_facebook_pixel"] = bool(r["fb_pixel_id"]) or "connect.facebook.net" in html or "fbq(" in html
        # WhatsApp
        wa = re.search(r"wa\.me/(\d{10,15})", html)
        if wa:
            r["whatsapp_number"] = f"+{wa.group(1)}"
            r["has_whatsapp"] = True
        else:
            wa2 = re.search(r"api\.whatsapp\.com/send\?phone=(\d+)", html)
            if wa2:
                r["whatsapp_number"] = f"+{wa2.group(1)}"
                r["has_whatsapp"] = True
            else:
                r["has_whatsapp"] = html.lower().count("whatsapp") >= 2
                r["whatsapp_number"] = ""
        return r

    def _detect_tech_stack(self, html: str, markdown: str) -> Dict:
        content = (html + markdown).lower()
        r = {"cms": "", "booking_system": "", "chat_widget": "",
             "analytics_tools": [], "payment_tools": []}
        for cms, pats in CMS_PATTERNS.items():
            if any(p in content for p in pats):
                r["cms"] = cms
                break
        for bk, pats in BOOKING_SYSTEM_PATTERNS.items():
            if any(p in content for p in pats):
                r["booking_system"] = bk
                break
        for cw, pats in CHAT_WIDGET_PATTERNS.items():
            if any(p in content for p in pats):
                r["chat_widget"] = cw
                break
        r["analytics_tools"] = [a for a in ANALYTICS_PATTERNS if a in content]
        r["payment_tools"] = [p for p in PAYMENT_PATTERNS if p in content]
        return r

    def _extract_contacts(self, content: str) -> Dict:
        r = {"found_emails": [], "found_phones": [], "social_links": {}}
        if not content:
            return r
        # Emails
        emails = re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", content)
        exclude = ["example.com", "domain.com", "samplemail", "noreply", "wixpress"]
        r["found_emails"] = list(set(e.lower() for e in emails if not any(x in e.lower() for x in exclude)))[:5]
        # Phones
        phones = re.findall(r"\+91[\s-]?\d{5}[\s-]?\d{5}", content)
        if not phones:
            phones = re.findall(r"(?<!\d)\d{10}(?!\d)", content)
        r["found_phones"] = list(set(phones))[:5]
        # Social
        for platform, pat in [("linkedin", r"linkedin\.com/(?:company|in)/[\w-]+"),
                               ("facebook", r"facebook\.com/[\w.]+"),
                               ("instagram", r"instagram\.com/[\w.]+"),
                               ("twitter", r"(?:twitter|x)\.com/[\w]+")]:
            m = re.search(pat, content.lower())
            if m:
                r["social_links"][platform] = f"https://{m.group()}"
        return r

    def _detect_forms(self, html: str) -> Dict:
        hl = html.lower() if html else ""
        return {
            "has_lead_form": "<form" in hl and ("contact" in hl or "enquiry" in hl or "inquiry" in hl or "appointment" in hl),
            "has_click_to_call": "tel:" in hl,
        }

    def _apply_scan_results(self, lead: BusinessLead, data: Dict) -> None:
        lead.website_title = data.get("title", "") or lead.website_title
        lead.website_description = data.get("description", "") or lead.website_description
        lead.website_content_preview = (data.get("markdown", "") or "")[:500]
        lead.cms = data.get("cms", "") or lead.cms
        lead.booking_system = data.get("booking_system", "") or lead.booking_system
        lead.has_booking = bool(lead.booking_system)
        lead.chat_widget = data.get("chat_widget", "") or lead.chat_widget
        lead.has_chat_widget = bool(lead.chat_widget)
        lead.analytics_tools = data.get("analytics_tools", []) or lead.analytics_tools
        lead.payment_tools = data.get("payment_tools", []) or lead.payment_tools
        lead.has_online_payment = bool(lead.payment_tools)
        lead.has_google_ads = data.get("has_google_ads", False) or lead.has_google_ads
        lead.google_ads_id = data.get("gads_id", "") or lead.google_ads_id
        lead.has_facebook_pixel = data.get("has_facebook_pixel", False) or lead.has_facebook_pixel
        lead.facebook_pixel_id = data.get("fb_pixel_id", "") or lead.facebook_pixel_id
        lead.google_tag_manager_id = data.get("gtm_id", "") or lead.google_tag_manager_id
        lead.google_analytics_id = data.get("ga4_id", "") or data.get("ua_id", "") or lead.google_analytics_id
        if data.get("has_whatsapp"):
            lead.has_whatsapp = True
        if data.get("whatsapp_number"):
            lead.whatsapp_number = data["whatsapp_number"]
        if data.get("has_lead_form"):
            lead.has_lead_form = True
        if data.get("has_click_to_call"):
            lead.has_click_to_call = True
        # Merge contacts
        for e in data.get("found_emails", []):
            if e not in lead.emails:
                lead.emails.append(e)
        for p in data.get("found_phones", []):
            if p not in lead.phones:
                lead.phones.append(p)
        social = data.get("social_links", {})
        if social.get("linkedin"):
            lead.linkedin_url = social["linkedin"]
        if social.get("instagram"):
            lead.instagram_url = social["instagram"]
        if social.get("facebook"):
            lead.facebook_url = social["facebook"]
        if social.get("twitter"):
            lead.twitter_url = social["twitter"]


# ═══════════════════════════════════════════════════════════════════════════════
# MODULE 3: MARKETING WEAKNESS ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════════

class MarketingWeaknessAnalyzer:
    """Generate weakness signals for each lead."""

    @staticmethod
    def analyze(lead: BusinessLead) -> None:
        w = []
        # High reviews but poor conversion
        if (lead.reviews_count or 0) > 100 and not lead.has_booking and not lead.has_whatsapp:
            w.append("HIGH_REVIEWS_NO_CONVERSION: High review count but no booking system or WhatsApp — losing walk-in inquiries")
        # Missing booking automation
        if not lead.has_booking:
            w.append("NO_BOOKING_SYSTEM: No online booking detected — after-hours leads are lost")
        # Missing WhatsApp
        if not lead.has_whatsapp:
            w.append("NO_WHATSAPP: No WhatsApp integration — missing instant communication channel")
        # No chat widget
        if not lead.has_chat_widget:
            w.append("NO_LIVE_CHAT: No live chat widget — slow response to website visitors")
        # No lead capture form
        if not lead.has_lead_form:
            w.append("NO_LEAD_FORM: No contact/enquiry form detected — website visitors have no way to reach out")
        # Running ads but weak funnel
        if (lead.has_google_ads or lead.has_facebook_pixel) and not lead.has_booking and not lead.has_lead_form:
            w.append("ADS_WEAK_FUNNEL: Running paid ads but no booking/form to capture traffic — ad spend wasted")
        # High traffic signals but no CRM/follow-up
        if (lead.reviews_count or 0) > 200 and not lead.has_chat_widget and not lead.has_booking:
            w.append("HIGH_TRAFFIC_NO_FOLLOWUP: High-volume business with no follow-up automation")
        # Outdated website
        if lead.cms in ("", "godaddy", "weebly") and lead.website:
            w.append("OUTDATED_WEBSITE: Website appears outdated or using basic platform")
        # Low review reply rate (approximated)
        if lead.rating and lead.rating < 4.0 and (lead.reviews_count or 0) > 50:
            w.append("LOW_SATISFACTION: Below 4.0 rating with significant reviews — potential reputation issue")
        # No analytics
        if not lead.analytics_tools and lead.website:
            w.append("NO_ANALYTICS: No tracking/analytics detected — flying blind on website performance")
        # No online payment
        if not lead.has_online_payment and lead.website:
            w.append("NO_ONLINE_PAYMENT: No payment gateway detected — missing convenience revenue")
        # Has website but no mobile optimization signals
        if lead.website and not lead.has_click_to_call:
            w.append("NO_CLICK_TO_CALL: No click-to-call link — mobile users can't call easily")

        lead.weaknesses = w
        lead.weakness_count = len(w)


# ═══════════════════════════════════════════════════════════════════════════════
# MODULE 4: LEAD SCORING ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

class LeadScoringEngine:
    """Multi-dimensional scoring producing a 0-100 numeric score."""

    @staticmethod
    def score(lead: BusinessLead) -> None:
        # Data quality (0-100)
        dq = 0
        if lead.business_name: dq += 20
        if lead.phone or lead.phones: dq += 20
        if lead.website: dq += 15
        if lead.emails: dq += 15
        if lead.address: dq += 10
        if lead.rating is not None: dq += 10
        if lead.reviews_count: dq += 10
        lead.data_quality_score = min(dq, 100)

        # Reachability (0-100)
        rc = 0
        if lead.phone or lead.phones: rc += 25
        if lead.emails: rc += 25
        if lead.has_whatsapp: rc += 20
        if lead.linkedin_url: rc += 15
        if lead.has_lead_form: rc += 10
        if lead.has_click_to_call: rc += 5
        lead.reachability_score = min(rc, 100)

        # Opportunity (0-100) — higher = more gaps = more opportunity
        op = 0
        if not lead.has_booking: op += 20
        if not lead.has_chat_widget: op += 15
        if not lead.has_whatsapp: op += 15
        if not lead.has_lead_form: op += 10
        if not lead.has_online_payment: op += 10
        if not lead.has_click_to_call: op += 5
        if lead.has_google_ads and not lead.has_booking:
            op += 15  # Spending on ads but can't convert
        if lead.rating and lead.rating < 4.5 and (lead.reviews_count or 0) > 50:
            op += 10
        lead.opportunity_score = min(op, 100)

        # Urgency (0-100)
        ur = 0
        if not lead.has_booking: ur += 25
        if not lead.has_chat_widget: ur += 20
        config = get_industry_config(lead.category)
        if config["ticket"] >= 5000: ur += 20
        if (lead.reviews_count or 0) > 100: ur += 15
        if lead.has_google_ads: ur += 10  # Spending money → more urgency
        if lead.weakness_count >= 5: ur += 10
        lead.urgency_score = min(ur, 100)

        # Growth (0-100) — proxy for business health
        gr = 0
        if (lead.reviews_count or 0) > 500: gr += 30
        elif (lead.reviews_count or 0) > 200: gr += 25
        elif (lead.reviews_count or 0) > 100: gr += 20
        elif (lead.reviews_count or 0) > 50: gr += 15
        elif (lead.reviews_count or 0) > 20: gr += 10
        if lead.rating and lead.rating >= 4.5: gr += 25
        elif lead.rating and lead.rating >= 4.0: gr += 20
        elif lead.rating and lead.rating >= 3.5: gr += 15
        if lead.website: gr += 15
        if lead.has_google_ads or lead.has_facebook_pixel: gr += 15
        if lead.instagram_url or lead.facebook_url: gr += 10
        lead.growth_score = min(gr, 100)

        # Marketing gap (0-100)
        mg = 0
        if lead.weakness_count >= 8: mg = 100
        elif lead.weakness_count >= 6: mg = 80
        elif lead.weakness_count >= 4: mg = 60
        elif lead.weakness_count >= 2: mg = 40
        elif lead.weakness_count >= 1: mg = 20
        lead.marketing_gap_score = mg

        # Final weighted score
        w = SCORING_WEIGHTS
        lead.final_score = int(
            lead.data_quality_score * w["data_quality"] +
            lead.reachability_score * w["reachability"] +
            lead.opportunity_score * w["opportunity"] +
            lead.urgency_score * w["urgency"] +
            lead.growth_score * w["growth"] +
            lead.marketing_gap_score * w["marketing_gap"]
        )

        # Tier assignment
        if lead.final_score >= TIER_THRESHOLDS["hot"]:
            lead.tier = LeadTier.HOT.value
            lead.priority = PriorityLevel.CRITICAL.value if lead.opportunity_score >= 50 else PriorityLevel.HIGH.value
        elif lead.final_score >= TIER_THRESHOLDS["warm"]:
            lead.tier = LeadTier.WARM.value
            lead.priority = PriorityLevel.HIGH.value if lead.opportunity_score >= 40 else PriorityLevel.MEDIUM.value
        else:
            lead.tier = LeadTier.COLD.value
            lead.priority = PriorityLevel.LOW.value


# ═══════════════════════════════════════════════════════════════════════════════
# MODULE 5: DECISION MAKER DISCOVERY
# ═══════════════════════════════════════════════════════════════════════════════

class DecisionMakerDiscovery:
    """Extract owner/doctor names, LinkedIn, emails, social profiles."""

    TITLE_PATTERNS = [
        r"(?:Dr\.?\s+|Doctor\s+)([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})",
        r"(?:Founded\s+by|CEO|Director|Owner|Founder|Managing\s+Director|Chief)\s*[:\-]?\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})",
        r"(?:Principal\s+Dentist|Chief\s+Doctor|Head\s+Doctor|Senior\s+Consultant)\s*[:\-]?\s*(?:Dr\.?\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})",
    ]

    @staticmethod
    def discover(lead: BusinessLead) -> None:
        content = lead.website_content_preview or ""
        if not content:
            return

        # Extract doctor/owner names
        for pat in DecisionMakerDiscovery.TITLE_PATTERNS:
            m = re.search(pat, content)
            if m:
                name = m.group(1).strip()
                if len(name) > 3 and len(name) < 60:
                    if "Dr" in content[:m.start() + 30]:
                        lead.doctor_name = f"Dr. {name}"
                    else:
                        lead.owner_name = name
                    break

        # Derive email patterns if we have a domain
        if lead.website and lead.emails:
            pass  # Already have real emails
        elif lead.website and (lead.owner_name or lead.doctor_name):
            domain = lead.website.replace("https://", "").replace("http://", "").replace("www.", "").split("/")[0]
            name = (lead.owner_name or lead.doctor_name).replace("Dr. ", "").lower().split()
            if name and domain and "." in domain:
                lead.emails = lead.emails or []
                if f"info@{domain}" not in lead.emails:
                    lead.emails.append(f"info@{domain}")


# ═══════════════════════════════════════════════════════════════════════════════
# MODULE 6: DATA ENRICHMENT ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

class DataEnrichmentEngine:
    """Enhance leads with metadata, estimated size, hours, service types."""

    @staticmethod
    def enrich(lead: BusinessLead, raw_data: Dict) -> None:
        # Business hours from raw Google data
        oh = raw_data.get("openingHours") or raw_data.get("opening_hours")
        if oh:
            if isinstance(oh, list):
                if len(oh) > 0 and isinstance(oh[0], dict):
                    parts = []
                    for d in oh[:7]:
                        day = d.get("day", "")
                        hours = d.get("hours", "")
                        if day and hours:
                            parts.append(f"{day}: {hours}")
                    lead.business_hours = "; ".join(parts)
                else:
                    lead.business_hours = "; ".join(str(x) for x in oh[:7])
            elif isinstance(oh, str):
                lead.business_hours = oh

        # Estimated size based on review count
        rc = lead.reviews_count or 0
        if rc > 1000:
            lead.estimated_size = "Large (1000+ reviews)"
        elif rc > 500:
            lead.estimated_size = "Medium-Large (500-1000 reviews)"
        elif rc > 100:
            lead.estimated_size = "Medium (100-500 reviews)"
        elif rc > 30:
            lead.estimated_size = "Small-Medium (30-100 reviews)"
        else:
            lead.estimated_size = "Small (<30 reviews)"

        # Service types from content
        if lead.website_content_preview:
            svcs = DataEnrichmentEngine._extract_services(
                lead.website_content_preview, lead.category
            )
            lead.services = svcs

        # Industry category from raw data
        cats = raw_data.get("categories") or raw_data.get("category")
        if cats:
            if isinstance(cats, list):
                lead.category = lead.category or cats[0]
            elif isinstance(cats, str):
                lead.category = lead.category or cats

    @staticmethod
    def _extract_services(content: str, category: str) -> List[str]:
        services = []
        content_low = content.lower()
        healthcare_svcs = [
            "dental implants", "root canal", "orthodontics", "teeth whitening",
            "cosmetic dentistry", "pediatric dentistry", "oral surgery",
            "x-ray", "blood test", "ultrasound", "mri", "ct scan",
            "ecg", "pathology", "health checkup", "full body checkup",
            "skin treatment", "laser treatment", "hair transplant",
            "eye surgery", "lasik", "cataract", "glaucoma",
            "physiotherapy", "rehabilitation", "sports medicine",
            "ivf", "fertility", "gynecology", "obstetrics",
            "general medicine", "cardiology", "orthopedics",
        ]
        for svc in healthcare_svcs:
            if svc in content_low:
                services.append(svc.title())
        return services[:10]


# ═══════════════════════════════════════════════════════════════════════════════
# REVENUE CALCULATOR
# ═══════════════════════════════════════════════════════════════════════════════

class RevenueCalculator:
    """Calculate revenue loss and ROI for each lead."""

    @staticmethod
    def calculate(lead: BusinessLead) -> None:
        config = get_industry_config(lead.category)
        ticket = config["ticket"]
        monthly_leads = config["leads"]
        conv = config["conversion"]

        # Scale by reviews
        rc = lead.reviews_count or 0
        if rc > 500: monthly_leads = int(monthly_leads * 1.5)
        elif rc > 200: monthly_leads = int(monthly_leads * 1.2)
        elif rc < 50: monthly_leads = int(monthly_leads * 0.7)
        lead.estimated_monthly_leads = monthly_leads

        # Missed percentage
        missed = 0.0
        if not lead.has_booking: missed += 0.15
        if not lead.has_chat_widget: missed += 0.10
        if not lead.has_whatsapp: missed += 0.10
        if not lead.has_lead_form: missed += 0.05
        if not lead.has_click_to_call: missed += 0.05
        lead.estimated_missed_pct = min(missed, 0.50)

        missed_count = int(monthly_leads * lead.estimated_missed_pct)
        lead.estimated_revenue_loss = int(missed_count * ticket * conv)
        lead.recoverable_amount = int(lead.estimated_revenue_loss * 0.70)

        # Tier
        for rt in REVENUE_TIERS:
            if lead.estimated_revenue_loss >= rt["min_loss"]:
                lead.recommended_tier = rt["tier"]
                cost = rt["cost"]
                break
        else:
            cost = 15000
            lead.recommended_tier = "Starter ₹15K/month"

        lead.roi_multiple = round(lead.recoverable_amount / cost, 1) if cost else 0
        lead.payback_days = int(30 / lead.roi_multiple) if lead.roi_multiple > 0 else 999


# ═══════════════════════════════════════════════════════════════════════════════
# MODULE 7: INTELLIGENCE REPORT GENERATOR
# ═══════════════════════════════════════════════════════════════════════════════

class IntelligenceReportGenerator:
    """Generate per-lead structured intelligence reports."""

    def __init__(self):
        self.api_key = os.getenv("OPENROUTER_API_KEY", "")
        self.model = os.getenv("DEFAULT_LLM_MODEL", "google/gemini-2.0-flash-001")

    def generate(self, lead: BusinessLead) -> None:
        """Generate intelligence report and outreach content."""
        loss_str = f"₹{lead.estimated_revenue_loss/100000:.1f}L" if lead.estimated_revenue_loss >= 100000 else f"₹{lead.estimated_revenue_loss/1000:.0f}K"
        rec_str = f"₹{lead.recoverable_amount/100000:.1f}L" if lead.recoverable_amount >= 100000 else f"₹{lead.recoverable_amount/1000:.0f}K"

        # Build weakness summary
        weakness_lines = "\n".join(f"  - {w.split(': ', 1)[-1]}" for w in lead.weaknesses[:6]) if lead.weaknesses else "  - No major weaknesses detected"

        # Generate report (works without LLM too)
        lead.intelligence_report = f"""# Intelligence Report: {lead.business_name}
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}

## Business Overview
- **Name:** {lead.business_name}
- **Category:** {lead.category}
- **Location:** {lead.area}, {lead.city}
- **Rating:** {lead.rating or 'N/A'}/5 ({lead.reviews_count or 0} reviews)
- **Website:** {lead.website or 'None'}
- **Phone:** {lead.phone or 'N/A'}
- **Estimated Size:** {lead.estimated_size}
- **Business Hours:** {lead.business_hours or 'Not available'}

## Technology Stack
- **CMS:** {lead.cms or 'Not detected'}
- **Booking System:** {lead.booking_system or '❌ NOT DETECTED'}
- **Chat Widget:** {lead.chat_widget or '❌ NOT DETECTED'}
- **Analytics:** {', '.join(lead.analytics_tools) if lead.analytics_tools else 'None detected'}
- **Payment:** {', '.join(lead.payment_tools) if lead.payment_tools else 'None detected'}
- **Google Ads:** {'✅ Active' + (f' ({lead.google_ads_id})' if lead.google_ads_id else '') if lead.has_google_ads else '❌ Not detected'}
- **Facebook Pixel:** {'✅ Active' + (f' ({lead.facebook_pixel_id})' if lead.facebook_pixel_id else '') if lead.has_facebook_pixel else '❌ Not detected'}

## Detected Weaknesses ({lead.weakness_count} found)
{weakness_lines}

## Revenue Impact Analysis
- **Estimated Monthly Inquiries:** {lead.estimated_monthly_leads}
- **Estimated Leakage Rate:** {int(lead.estimated_missed_pct * 100)}%
- **Monthly Revenue Loss:** {loss_str}
- **Recoverable Amount:** {rec_str}
- **Recommended Plan:** {lead.recommended_tier}
- **Projected ROI:** {lead.roi_multiple}x
- **Payback Period:** ~{lead.payback_days} days

## Lead Score Breakdown
- **Data Quality:** {lead.data_quality_score}/100
- **Reachability:** {lead.reachability_score}/100
- **Opportunity:** {lead.opportunity_score}/100
- **Urgency:** {lead.urgency_score}/100
- **Growth:** {lead.growth_score}/100
- **Marketing Gap:** {lead.marketing_gap_score}/100
- **FINAL SCORE:** {lead.final_score}/100 ({lead.tier})

## Contact Intelligence
- **Owner/Decision Maker:** {lead.owner_name or lead.doctor_name or 'Not identified'}
- **Email(s):** {', '.join(lead.emails) if lead.emails else 'Not found'}
- **Phone(s):** {', '.join(lead.phones) if lead.phones else lead.phone or 'Not found'}
- **WhatsApp:** {lead.whatsapp_number or ('Available' if lead.has_whatsapp else 'Not detected')}
- **LinkedIn:** {lead.linkedin_url or 'Not found'}

## Suggested Automation Improvements
1. {'Install online booking system (Calendly/Practo)' if not lead.has_booking else '✅ Booking system present'}
2. {'Add WhatsApp Business integration' if not lead.has_whatsapp else '✅ WhatsApp present'}
3. {'Deploy live chat widget (Tawk.to/Tidio)' if not lead.has_chat_widget else '✅ Chat widget present'}
4. {'Create lead capture forms' if not lead.has_lead_form else '✅ Lead forms present'}
5. {'Add click-to-call for mobile' if not lead.has_click_to_call else '✅ Click-to-call present'}

## Personalized Outreach Angle
{lead.business_name} has {lead.reviews_count or 'multiple'} Google reviews showing strong demand, but is losing an estimated {loss_str}/month due to {lead.weakness_count} automation gaps. Key pitch: recover {rec_str}/month with {lead.recommended_tier} — {lead.roi_multiple}x ROI.
"""
        lead.outreach_angle = f"Losing {loss_str}/month due to {lead.weakness_count} gaps. Recover {rec_str} with {lead.recommended_tier}."

        # AI-enhanced analysis if LLM available
        if self.api_key and lead.tier in ("HOT", "WARM"):
            ai = self._llm_analyze(lead, loss_str, rec_str)
            if ai:
                lead.ai_verdict = ai.get("verdict", "REVIEW")
                lead.ai_reasoning = ai.get("reasoning", "")
                lead.pain_points = ai.get("pain_points", [])
                lead.selling_angles = ai.get("selling_angles", [])
        
        if not lead.ai_verdict:
            lead.ai_verdict = "ACCEPT" if lead.final_score >= 60 else "REVIEW" if lead.final_score >= 35 else "SKIP"

        # Generate outreach content
        self._generate_outreach(lead, loss_str, rec_str)

    def _llm_analyze(self, lead: BusinessLead, loss: str, rec: str) -> Optional[Dict]:
        prompt = f"""Analyze this business for B2B sales. Respond ONLY with valid JSON.

Business: {lead.business_name} ({lead.category}) in {lead.city}
Rating: {lead.rating}/5, Reviews: {lead.reviews_count}
Score: {lead.final_score}/100, Weaknesses: {lead.weakness_count}
Revenue Loss: {loss}/month, Recoverable: {rec}/month

{{"verdict":"ACCEPT|REVIEW|SKIP","reasoning":"2 sentences","pain_points":["point1","point2","point3"],"selling_angles":["angle1","angle2"]}}"""

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        data = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You are an elite B2B sales analyst. Be specific and use the business name."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
            "max_tokens": 512,
        }
        rl.rate_limit()
        result = rl.retry(rl.http_post_json, "https://openrouter.ai/api/v1/chat/completions", data, headers)
        if not result:
            return None
        try:
            text = result["choices"][0]["message"]["content"].strip()
            if text.startswith("```"):
                text = re.sub(r"^```\w*\n?", "", text)
                text = re.sub(r"\n?```$", "", text)
            return json.loads(text)
        except Exception:
            return None

    @staticmethod
    def _generate_outreach(lead: BusinessLead, loss: str, rec: str) -> None:
        pain = lead.pain_points[0] if lead.pain_points else "missed appointments and slow follow-up"
        angle = lead.selling_angles[0] if lead.selling_angles else "WhatsApp automation + booking system"

        lead.email_subject = f"Quick question about {lead.business_name}"
        lead.email_body = f"""Hi,

Noticed {lead.business_name} on Google — {lead.reviews_count or 'many'} reviews, solid presence.

Quick analysis: you're likely losing {loss}/month in {pain}.

We help {lead.category} businesses recover {rec}/month with {angle}.

ROI: {lead.roi_multiple}x (payback in ~{lead.payback_days} days)

2-min call to discuss?

Best,
[Your Name]

P.S. Happy to share a free audit showing exact ₹ being lost."""

        lead.whatsapp_msg = f"""Hi! Quick note about {lead.business_name}.

Based on your {lead.reviews_count or 'many'} Google reviews, you're likely missing {loss}/month in {pain}.

We can recover {rec}/month with {angle}.

ROI: {lead.roi_multiple}x

Want a free audit? Reply YES"""

        lead.call_script = f"""Hi, is this the owner/manager at {lead.business_name}?

I'm [Name]. I help {lead.category} businesses recover lost revenue.

I noticed your {lead.reviews_count or 'many'} Google reviews — great traffic. But you may be losing {loss}/month in {pain}.

We can recover {rec} with {angle}. ROI: {lead.roi_multiple}x.

Would you be open to a free audit? Takes 2 days, shows exact ₹ lost."""


# ═══════════════════════════════════════════════════════════════════════════════
# MODULE 8: EXPORT PIPELINE
# ═══════════════════════════════════════════════════════════════════════════════

class ExportPipeline:
    """Export leads to CSV, JSON, SQLite, and prioritized lists."""

    @staticmethod
    def export_all(leads: List[BusinessLead], output_dir: Path, run_id: str) -> None:
        output_dir.mkdir(parents=True, exist_ok=True)
        reports_dir = output_dir / "intelligence_reports"
        reports_dir.mkdir(exist_ok=True)

        # Sort by score descending
        sorted_leads = sorted(leads, key=lambda x: x.final_score, reverse=True)

        # 1. CSV
        ExportPipeline._export_csv(sorted_leads, output_dir / "leads.csv")

        # 2. Full JSON
        ExportPipeline._export_json(sorted_leads, output_dir / "leads.json")

        # 3. SQLite
        ExportPipeline._export_sqlite(sorted_leads, output_dir / "leads.db")
        
        # 3.5 Global Persistent SQLite
        ExportPipeline._export_global_sqlite(sorted_leads)

        # 4. Prioritized lists
        for n in (10, 25, 50):
            top = sorted_leads[:n]
            if top:
                ExportPipeline._export_prioritized(top, output_dir / f"top_{n}.json", n)

        # 5. Per-lead intelligence reports
        for lead in sorted_leads:
            if lead.intelligence_report:
                safe_name = re.sub(r"[^\w\s-]", "", lead.business_name)[:50].strip().replace(" ", "_")
                (reports_dir / f"{safe_name}.md").write_text(
                    lead.intelligence_report, encoding="utf-8"
                )

        # 6. Run report
        stats = ExportPipeline._build_stats(sorted_leads, run_id)
        (output_dir / "report.json").write_text(
            json.dumps(stats, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
        )

        logger.info(f"📁 All exports saved to: {output_dir}")

    @staticmethod
    def _export_csv(leads: List[BusinessLead], path: Path) -> None:
        headers = BusinessLead.csv_headers()
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
            w.writeheader()
            for lead in leads:
                d = lead.to_dict()
                w.writerow(d)
        logger.info(f"  ✅ CSV: {path.name} ({len(leads)} leads)")

    @staticmethod
    def _export_json(leads: List[BusinessLead], path: Path) -> None:
        data = [lead.to_dict() for lead in leads]
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        logger.info(f"  ✅ JSON: {path.name} ({len(leads)} leads)")

    @staticmethod
    def _export_sqlite(leads: List[BusinessLead], path: Path) -> None:
        conn = sqlite3.connect(str(path))
        c = conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS leads (
            lead_id TEXT PRIMARY KEY, business_name TEXT, category TEXT, city TEXT,
            area TEXT, address TEXT, website TEXT, phone TEXT, rating REAL,
            reviews_count INTEGER, emails TEXT, owner_name TEXT, doctor_name TEXT,
            linkedin_url TEXT, whatsapp_number TEXT, cms TEXT, booking_system TEXT,
            chat_widget TEXT, has_booking INTEGER, has_whatsapp INTEGER,
            has_lead_form INTEGER, has_chat_widget INTEGER, has_google_ads INTEGER,
            has_facebook_pixel INTEGER, weaknesses TEXT, weakness_count INTEGER,
            final_score INTEGER, tier TEXT, priority TEXT,
            estimated_revenue_loss INTEGER, recoverable_amount INTEGER,
            recommended_tier TEXT, roi_multiple REAL, ai_verdict TEXT,
            outreach_angle TEXT, email_subject TEXT, whatsapp_msg TEXT,
            enrichment_source TEXT, created_at TEXT
        )""")
        for lead in leads:
            d = lead.to_dict()
            cols = list(d.keys())
            # Filter to only columns that exist in our table
            table_cols = [
                "lead_id", "business_name", "category", "city", "area", "address",
                "website", "phone", "rating", "reviews_count", "emails", "owner_name",
                "doctor_name", "linkedin_url", "whatsapp_number", "cms", "booking_system",
                "chat_widget", "has_booking", "has_whatsapp", "has_lead_form",
                "has_chat_widget", "has_google_ads", "has_facebook_pixel", "weaknesses",
                "weakness_count", "final_score", "tier", "priority",
                "estimated_revenue_loss", "recoverable_amount", "recommended_tier",
                "roi_multiple", "ai_verdict", "outreach_angle", "email_subject",
                "whatsapp_msg", "enrichment_source", "created_at",
            ]
            vals = [d.get(c, "") for c in table_cols]
            placeholders = ",".join(["?"] * len(table_cols))
            c.execute(
                f"INSERT OR REPLACE INTO leads ({','.join(table_cols)}) VALUES ({placeholders})",
                vals,
            )
        conn.commit()
        conn.close()
        logger.info(f"  ✅ SQLite: {path.name} ({len(leads)} leads)")

    @staticmethod
    def _export_global_sqlite(leads: List[BusinessLead]) -> None:
        """Saves leads to the persistent, national Clinic Intelligence Database."""
        db_path = Path("clinic_intelligence.db")
        conn = sqlite3.connect(str(db_path))
        c = conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS clinic_intelligence (
            clinic_id TEXT PRIMARY KEY,
            business_name TEXT,
            specialty TEXT,
            city TEXT,
            area TEXT,
            website TEXT,
            phone TEXT,
            rating REAL,
            reviews_count INTEGER,
            cms TEXT,
            booking_system TEXT,
            analytics_tools TEXT,
            payment_tools TEXT,
            has_booking INTEGER,
            has_whatsapp INTEGER,
            has_google_ads INTEGER,
            has_facebook_pixel INTEGER,
            weakness_count INTEGER,
            estimated_revenue_loss INTEGER,
            final_score INTEGER,
            last_scanned TIMESTAMP
        )""")
        
        new_or_updated = 0
        for lead in leads:
            d = lead.to_dict()
            # Simple primary key based on business name
            clinic_id = lead.business_name.lower().replace(" ", "_") if lead.business_name else "unknown"
            
            c.execute("""
                INSERT OR REPLACE INTO clinic_intelligence (
                    clinic_id, business_name, specialty, city, area, website, phone,
                    rating, reviews_count, cms, booking_system, analytics_tools, payment_tools,
                    has_booking, has_whatsapp, has_google_ads, has_facebook_pixel,
                    weakness_count, estimated_revenue_loss, final_score, last_scanned
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                clinic_id,
                lead.business_name,
                lead.category,
                lead.city,
                lead.area,
                lead.website,
                lead.phone,
                lead.rating,
                lead.reviews_count,
                lead.cms,
                lead.booking_system,
                ",".join(lead.analytics_tools) if lead.analytics_tools else "",
                ",".join(lead.payment_tools) if lead.payment_tools else "",
                1 if lead.has_booking else 0,
                1 if lead.has_whatsapp else 0,
                1 if lead.has_google_ads else 0,
                1 if lead.has_facebook_pixel else 0,
                len(lead.weaknesses) if lead.weaknesses else 0,
                lead.estimated_revenue_loss,
                lead.final_score,
                datetime.datetime.now()
            ))
            new_or_updated += 1
            
        conn.commit()
        conn.close()
        logger.info(f"  ✅ Global DB: clinic_intelligence.db updated ({new_or_updated} leads)")

    @staticmethod
    def _export_prioritized(leads: List[BusinessLead], path: Path, n: int) -> None:
        output = []
        for rank, lead in enumerate(leads, 1):
            output.append({
                "rank": rank,
                "business_name": lead.business_name,
                "score": lead.final_score,
                "tier": lead.tier,
                "city": lead.city,
                "area": lead.area,
                "phone": lead.phone,
                "website": lead.website,
                "rating": lead.rating,
                "reviews": lead.reviews_count,
                "revenue_loss": lead.estimated_revenue_loss,
                "recoverable": lead.recoverable_amount,
                "weakness_count": lead.weakness_count,
                "outreach_angle": lead.outreach_angle,
                "reasoning": f"Score {lead.final_score}/100 — {lead.weakness_count} weaknesses, "
                             f"₹{lead.estimated_revenue_loss:,}/mo loss, {lead.tier} tier",
            })
        path.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info(f"  ✅ Top {n}: {path.name}")

    @staticmethod
    def _build_stats(leads: List[BusinessLead], run_id: str) -> Dict:
        hot = sum(1 for l in leads if l.tier == "HOT")
        warm = sum(1 for l in leads if l.tier == "WARM")
        cold = sum(1 for l in leads if l.tier == "COLD")
        total_loss = sum(l.estimated_revenue_loss for l in leads)
        return {
            "run_id": run_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_leads": len(leads),
            "hot": hot, "warm": warm, "cold": cold,
            "total_monthly_opportunity": total_loss,
            "total_annual_opportunity": total_loss * 12,
            "avg_score": round(sum(l.final_score for l in leads) / max(len(leads), 1), 1),
            "avg_weaknesses": round(sum(l.weakness_count for l in leads) / max(len(leads), 1), 1),
        }


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN PIPELINE
# ═══════════════════════════════════════════════════════════════════════════════

class LeadOSPipeline:
    """Main orchestrator — runs all modules in sequence."""

    def __init__(self, city: str, niche: str, count: int, dry_run: bool = False):
        self.city = city
        self.niche = niche
        self.count = count
        self.dry_run = dry_run
        self.run_id = f"{city}_{niche}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.output_dir = Path("output") / self.run_id

        # Modules
        self.discovery = LeadDiscoveryEngine()
        self.scanner = WebsiteIntelligenceScanner()
        self.report_gen = IntelligenceReportGenerator()

    def run(self) -> None:
        self._print_banner()

        # ── Stage 1: Discovery ──
        console.print("\n[bold cyan]━━━ STAGE 1: DISCOVERY ━━━[/bold cyan]")
        if self.dry_run:
            raw_leads = LeadDiscoveryEngine.generate_mock_leads(self.city, self.niche, self.count)
            console.print(f"[yellow]🧪 Dry-run: generated {len(raw_leads)} mock leads[/yellow]")
        else:
            raw_leads = self.discovery.discover(self.niche, self.city, limit=self.count)

        if not raw_leads:
            console.print("[red]❌ No leads discovered. Check your API keys.[/red]")
            return

        # ── Stage 2-7: Process each lead ──
        console.print(f"\n[bold cyan]━━━ STAGE 2-7: PROCESSING {len(raw_leads)} LEADS ━━━[/bold cyan]")
        processed: List[BusinessLead] = []

        for i, raw in enumerate(raw_leads, 1):
            lead = self._create_lead(raw)
            console.print(f"\n[cyan][{i}/{len(raw_leads)}] {lead.business_name[:50]}[/cyan]")

            try:
                # Stage 2: Website Intelligence
                if not self.dry_run:
                    try:
                        self.scanner.scan(lead)
                    except Exception as scan_err:
                        logger.warning(f"  ⚠️ Scan failed (continuing): {scan_err}")

                # Stage 3: Weakness Analysis
                MarketingWeaknessAnalyzer.analyze(lead)

                # Stage 4: Scoring
                LeadScoringEngine.score(lead)

                # Stage 5: Decision Maker
                DecisionMakerDiscovery.discover(lead)

                # Stage 6: Enrichment
                DataEnrichmentEngine.enrich(lead, raw)

                # Revenue
                RevenueCalculator.calculate(lead)

                # Stage 7: Intelligence Report + Outreach
                self.report_gen.generate(lead)

                lead.status = "processed"
                processed.append(lead)

                tier_emoji = "🔥" if lead.tier == "HOT" else "☀️" if lead.tier == "WARM" else "❄️"
                console.print(
                    f"  {tier_emoji} {lead.tier} | Score: {lead.final_score} | "
                    f"Weaknesses: {lead.weakness_count} | "
                    f"Loss: ₹{lead.estimated_revenue_loss:,}/mo"
                )
            except Exception as e:
                import traceback
                logger.error(f"  ❌ Error processing {lead.business_name}: {e}")
                logger.error(f"  ❌ Traceback: {traceback.format_exc()}")
                continue

        if not processed:
            console.print("[red]❌ No leads processed successfully.[/red]")
            return

        # ── Stage 8: Export ──
        console.print(f"\n[bold cyan]━━━ STAGE 8: EXPORT ━━━[/bold cyan]")
        ExportPipeline.export_all(processed, self.output_dir, self.run_id)

        # ── Final Summary ──
        self._print_summary(processed)

    def _create_lead(self, raw: Dict) -> BusinessLead:
        name = str(raw.get("title") or raw.get("name") or "Unknown").strip()
        addr = str(raw.get("address") or raw.get("street") or "").strip()
        lead_id = hashlib.md5(f"{name}{addr}".encode()).hexdigest()[:16]

        # Safe type conversions for Apify data
        rating_raw = raw.get("totalScore") or raw.get("rating") or raw.get("stars")
        try:
            rating = float(rating_raw) if rating_raw is not None else None
        except (ValueError, TypeError):
            rating = None

        reviews_raw = raw.get("reviewsCount") or raw.get("reviews") or raw.get("reviewCount")
        try:
            reviews_count = int(reviews_raw) if reviews_raw is not None else None
        except (ValueError, TypeError):
            reviews_count = None

        # Area can come from multiple fields
        area = ""
        for field in ("city", "neighborhood", "district", "subLocality", "postalAddress"):
            v = raw.get(field, "")
            if v and isinstance(v, str):
                area = v
                break

        website = str(raw.get("website") or raw.get("url") or "").strip()
        # Filter out Google Maps URLs as websites
        if "google.com" in website or "maps.google" in website:
            website = ""

        phone = str(raw.get("phone") or raw.get("phoneUnformatted") or "").strip()
        email = str(raw.get("email") or "").strip()
        gmap_url = str(raw.get("url") or raw.get("googleMapsUrl") or "").strip()

        return BusinessLead(
            lead_id=lead_id,
            business_name=name,
            category=self.niche,
            city=self.city,
            area=area,
            address=addr,
            website=website,
            phone=phone,
            google_maps_url=gmap_url,
            rating=rating,
            reviews_count=reviews_count,
            emails=[email] if email and "@" in email else [],
            phones=[phone] if phone else [],
            has_click_to_call=bool(phone),
            created_at=datetime.now(timezone.utc).isoformat(),
        )

    def _print_banner(self):
        console.print(Panel(
            f"[bold green]LEAD-OS V2 — Production Intelligence Engine[/bold green]\n\n"
            f"[yellow]City:[/yellow] {self.city}\n"
            f"[yellow]Niche:[/yellow] {self.niche}\n"
            f"[yellow]Target:[/yellow] {self.count} leads\n"
            f"[yellow]Mode:[/yellow] {'🧪 DRY RUN' if self.dry_run else '🚀 LIVE'}\n\n"
            f"[cyan]Pipeline: Discovery → Scan → Weakness → Score → Enrich → Report → Export[/cyan]",
            border_style="green",
        ) if HAS_RICH else f"LEAD-OS V2 | {self.city} | {self.niche} | {self.count} leads")

    def _print_summary(self, leads: List[BusinessLead]):
        hot = [l for l in leads if l.tier == "HOT"]
        warm = [l for l in leads if l.tier == "WARM"]
        cold = [l for l in leads if l.tier == "COLD"]
        total_loss = sum(l.estimated_revenue_loss for l in leads)

        if HAS_RICH:
            table = Table(title="📊 Lead-OS V2 Run Summary")
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="green")
            table.add_row("Total Processed", str(len(leads)))
            table.add_row("🔥 HOT", str(len(hot)))
            table.add_row("☀️ WARM", str(len(warm)))
            table.add_row("❄️ COLD", str(len(cold)))
            table.add_row("Monthly Opportunity", f"₹{total_loss:,}")
            table.add_row("Annual Opportunity", f"₹{total_loss * 12:,}")
            table.add_row("Avg Score", f"{sum(l.final_score for l in leads) / max(len(leads),1):.0f}/100")
            table.add_row("Output Directory", str(self.output_dir))
            console.print(table)

            if hot:
                t2 = Table(title="🎯 Top HOT Leads")
                t2.add_column("#", style="bold")
                t2.add_column("Business", style="cyan")
                t2.add_column("Score", style="green")
                t2.add_column("Loss/mo", style="red")
                t2.add_column("Weaknesses", style="yellow")
                for i, l in enumerate(sorted(hot, key=lambda x: x.final_score, reverse=True)[:10], 1):
                    t2.add_row(
                        str(i), l.business_name[:40], str(l.final_score),
                        f"₹{l.estimated_revenue_loss:,}", str(l.weakness_count),
                    )
                console.print(t2)
        else:
            print(f"\n{'='*60}")
            print(f"RESULTS: {len(leads)} leads | HOT:{len(hot)} WARM:{len(warm)} COLD:{len(cold)}")
            print(f"Opportunity: ₹{total_loss:,}/month | Output: {self.output_dir}")
            print(f"{'='*60}\n")

        console.print(f"\n[bold green]✅ Lead-OS V2 run complete! Output: {self.output_dir}[/bold green]")


# ═══════════════════════════════════════════════════════════════════════════════
# CLI ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="LEAD-OS V2 — Production Intelligence Engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python lead_os_v2.py --city "Hyderabad" --niche "dental" --count 20
  python lead_os_v2.py --dry-run --city "Mumbai" --niche "hospital" --count 5
  python lead_os_v2.py --city "Bangalore" --niche "mixed" --count 50
        """,
    )
    parser.add_argument("--city", required=True, help="Target city")
    parser.add_argument("--niche", default="mixed",
                        choices=list(NICHE_KEYWORDS.keys()),
                        help="Business niche to target")
    parser.add_argument("--count", type=int, default=20, help="Number of leads")
    parser.add_argument("--dry-run", action="store_true",
                        help="Run with mock data (no API calls)")
    args = parser.parse_args()

    pipeline = LeadOSPipeline(args.city, args.niche, args.count, args.dry_run)
    pipeline.run()


if __name__ == "__main__":
    main()

