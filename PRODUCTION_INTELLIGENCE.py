#!/usr/bin/env python3
"""
ZRAI PRODUCTION INTELLIGENCE ENGINE v3.0
=========================================
The ULTIMATE lead intelligence system - production-ready, battle-tested.

Core Pipeline:
1. Discovery → Find businesses via Apify/Google Maps
2. Enrichment → Extract contacts, tech signals, pain points  
3. AI Reasoning → Deep analysis with OpenRouter/Gemini
4. Revenue Calculation → Precise loss estimation
5. Scoring → Tier assignment (HOT/WARM/COLD)

This system generates cash-ready leads with:
- Real data from Apify
- AI-powered analysis via OpenRouter
- Accurate revenue loss calculations
- Production-grade error handling
- Local file storage (Supabase-ready)

Author: ZRAI Intelligence Team
"""

import os
import sys
import json
import hashlib
import logging
import asyncio
import re
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict, field
from enum import Enum
from concurrent.futures import ThreadPoolExecutor
import urllib.request
import urllib.error

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

# Load environment
from dotenv import load_dotenv
load_dotenv('.env')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("ZRAI-Intelligence")


# =============================================================================
# DATA MODELS
# =============================================================================

class LeadTier(str, Enum):
    HOT = "HOT"      # Score >= 70 - Ready to pitch
    WARM = "WARM"    # Score >= 45 - Soft approach
    COLD = "COLD"    # Score < 45 - Nurture

class PriorityLevel(str, Enum):
    CRITICAL = "CRITICAL"  # Reach out TODAY
    HIGH = "HIGH"          # Reach out this week
    MEDIUM = "MEDIUM"      # Reach out this month
    LOW = "LOW"            # Nurture sequence


@dataclass
class BusinessLead:
    """Core lead data model."""
    lead_id: str
    business_name: str
    category: str = ""
    city: str = ""
    area: str = ""
    website: str = ""
    phone: str = ""
    emails: List[str] = field(default_factory=list)
    google_maps_url: str = ""
    rating: Optional[float] = None
    reviews_count: Optional[int] = None
    address: str = ""
    
    # Enrichment data
    has_booking_system: bool = False
    has_whatsapp: bool = False
    has_lead_form: bool = False
    has_chat_widget: bool = False
    has_click_to_call: bool = False
    ads_detected: bool = False
    
    # Calculated signals
    has_slow_response_risk: bool = False
    has_after_hours_leak: bool = False
    
    # Scores
    data_quality_score: int = 0
    reachability_score: int = 0
    opportunity_score: int = 0
    final_score: int = 0
    
    # AI Analysis
    ai_reasoning: str = ""
    reasoning_verdict: str = ""
    validation_issues: List[str] = field(default_factory=list)
    
    # Revenue
    estimated_monthly_leads: int = 0
    estimated_missed_pct: float = 0.0
    estimated_revenue_loss_inr: int = 0
    recoverable_amount_inr: int = 0
    recommended_tier: str = ""
    roi_multiple: float = 0.0
    
    # Classification
    tier: LeadTier = LeadTier.COLD
    priority: PriorityLevel = PriorityLevel.LOW
    
    # Outreach
    email_subject: str = ""
    email_body: str = ""
    whatsapp_msg: str = ""
    call_script: str = ""
    loom_script: str = ""
    
    # Meta
    status: str = "discovered"
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

class ApifyDiscovery:
    """Discover leads using Apify Google Maps scraper."""
    
    # Google Maps Scraper actor ID (official Apify actor)
    GOOGLE_MAPS_ACTOR = "nwua9Gu5YrADL7ZDj"
    
    def __init__(self):
        self.api_token = os.environ.get("APIFY_API_TOKEN", "")
        self.base_url = "https://api.apify.com/v2"
        
        if not self.api_token:
            logger.warning("⚠️ APIFY_API_TOKEN not set - discovery will fail")
    
    def _make_request(self, method: str, endpoint: str, data: Optional[Dict] = None, timeout: int = 300) -> Dict[str, Any]:
        """Make HTTP request to Apify API."""
        url = f"{self.base_url}{endpoint}?token={self.api_token}"
        
        headers = {"Content-Type": "application/json"}
        
        if data:
            req = urllib.request.Request(url, data=json.dumps(data).encode(), headers=headers, method=method)
        else:
            req = urllib.request.Request(url, headers=headers, method=method)
        
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                return json.loads(response.read().decode())
        except urllib.error.HTTPError as e:
            error_body = e.read().decode() if e.fp else str(e)
            logger.error(f"Apify API error {e.code}: {error_body[:500]}")
            raise
        except Exception as e:
            logger.error(f"Apify request failed: {e}")
            raise
    
    def discover_businesses(
        self,
        niche: str,
        city: str,
        country: str = "India",
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Discover businesses using Apify Google Maps scraper.
        
        Args:
            niche: Business category (e.g., "diagnostic center", "dental clinic")
            city: City name
            country: Country name
            limit: Maximum results
            
        Returns:
            List of raw business data from Google Maps
        """
        if not self.api_token:
            logger.error("❌ Cannot discover - APIFY_API_TOKEN not set")
            return []
        
        logger.info(f"🔍 Discovering {niche} in {city}, {country} (limit: {limit})")
        
        # Build search query
        search_query = f"{niche} in {city}, {country}"
        
        input_data = {
            "searchStringsArray": [search_query],
            "maxCrawledPlacesPerSearch": limit,
            "language": "en",
            "deeperCityScrape": True,
            "includeWebResults": False,
        }
        
        try:
            # Start the actor run
            logger.info(f"   Starting Apify actor: {self.GOOGLE_MAPS_ACTOR}")
            run_result = self._make_request(
                "POST",
                f"/acts/{self.GOOGLE_MAPS_ACTOR}/runs",
                data=input_data,
                timeout=60
            )
            
            run_id = run_result.get("data", {}).get("id")
            if not run_id:
                logger.error("❌ Failed to start Apify run")
                return []
            
            logger.info(f"   Run started: {run_id}")
            
            # Wait for completion (poll every 10 seconds)
            max_wait = 300  # 5 minutes
            waited = 0
            
            while waited < max_wait:
                import time
                time.sleep(10)
                waited += 10
                
                status_result = self._make_request("GET", f"/actor-runs/{run_id}")
                status = status_result.get("data", {}).get("status")
                
                logger.info(f"   Status: {status} ({waited}s)")
                
                if status == "SUCCEEDED":
                    break
                elif status in ["FAILED", "ABORTED", "TIMED-OUT"]:
                    logger.error(f"❌ Apify run failed: {status}")
                    return []
            
            # Get results from dataset
            dataset_id = status_result.get("data", {}).get("defaultDatasetId")
            if not dataset_id:
                logger.error("❌ No dataset ID found")
                return []
            
            items_result = self._make_request("GET", f"/datasets/{dataset_id}/items")
            items = items_result if isinstance(items_result, list) else []
            
            logger.info(f"✅ Discovered {len(items)} businesses")
            return items
            
        except Exception as e:
            logger.error(f"❌ Discovery failed: {e}")
            return []


# =============================================================================
# OPENROUTER LLM CLIENT - AI Reasoning
# =============================================================================

class OpenRouterLLM:
    """OpenRouter LLM client for AI reasoning."""
    
    def __init__(self):
        self.api_key = os.environ.get("OPENROUTER_API_KEY", "")
        self.model = os.environ.get("DEFAULT_LLM_MODEL", "google/gemini-2.0-flash-001")
        self.base_url = "https://openrouter.ai/api/v1"
        
        if not self.api_key:
            logger.warning("⚠️ OPENROUTER_API_KEY not set - AI reasoning will fail")
    
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 2048
    ) -> str:
        """Generate text using OpenRouter."""
        if not self.api_key:
            logger.error("❌ Cannot generate - OPENROUTER_API_KEY not set")
            return ""
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        data = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "https://zrai-lead-os.com",
            "X-Title": "ZRAI Lead Intelligence",
        }
        
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(data).encode(),
            headers=headers,
            method="POST"
        )
        
        try:
            with urllib.request.urlopen(req, timeout=60) as response:
                result = json.loads(response.read().decode())
                
            if "choices" in result and result["choices"]:
                return result["choices"][0]["message"]["content"]
            return ""
            
        except Exception as e:
            logger.error(f"❌ LLM generation failed: {e}")
            return ""
    
    def generate_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate JSON response."""
        full_prompt = f"{prompt}\n\nRespond ONLY with valid JSON, no other text."
        
        response = self.generate(full_prompt, system_prompt, temperature=0.1)
        
        if not response:
            return {}
        
        # Extract JSON from response
        try:
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]
            
            return json.loads(response.strip())
        except json.JSONDecodeError as e:
            logger.error(f"❌ JSON parse error: {e}")
            return {}


# =============================================================================
# INDUSTRY CONFIGURATION
# =============================================================================

# Average ticket prices by industry (INR)
INDUSTRY_TICKET_PRICES = {
    # Healthcare
    "diagnostic": 1500,
    "diagnostics": 1500,
    "pathology": 1200,
    "lab": 1200,
    "radiology": 3500,
    "mri": 8000,
    "ct scan": 5000,
    "hospital": 15000,
    "clinic": 800,
    "dental": 2500,
    "dentist": 2500,
    "orthodontist": 25000,
    "eye": 3000,
    "ophthalmology": 5000,
    "dermatology": 1500,
    "skin": 1500,
    "physiotherapy": 800,
    "chiropractic": 1200,
    "ivf": 150000,
    "fertility": 100000,
    "cosmetic": 50000,
    "plastic surgery": 100000,
    "ayurveda": 2000,
    "homeopathy": 500,
    "veterinary": 1500,
    "vet": 1500,
    
    # Home Services
    "plumber": 2000,
    "plumbing": 2000,
    "electrician": 1500,
    "electrical": 1500,
    "hvac": 5000,
    "ac repair": 3000,
    "roofing": 50000,
    "contractor": 100000,
    "interior": 200000,
    "pest control": 2500,
    
    # Professional
    "lawyer": 10000,
    "legal": 10000,
    "accountant": 5000,
    "ca": 5000,
    "consultant": 15000,
    
    # Education
    "coaching": 50000,
    "tuition": 30000,
    "training": 25000,
    
    # Default
    "default": 3000,
}

# Lead volume estimates by category
MONTHLY_LEAD_ESTIMATES = {
    "diagnostic": 500,
    "hospital": 1000,
    "clinic": 300,
    "dental": 200,
    "coaching": 100,
    "default": 150,
}


# =============================================================================
# INTELLIGENCE ENGINE - THE CORE
# =============================================================================

class IntelligenceEngine:
    """
    Production Intelligence Engine.
    
    Processes raw business data through:
    1. Data Quality Assessment
    2. Contact Enrichment
    3. Opportunity Analysis
    4. AI-Powered Reasoning
    5. Revenue Calculation
    6. Tier Assignment
    7. Outreach Generation
    """
    
    def __init__(self):
        self.apify = ApifyDiscovery()
        self.llm = OpenRouterLLM()
        self.output_dir = Path("output")
        self.output_dir.mkdir(exist_ok=True)
    
    def _get_ticket_price(self, category: str) -> int:
        """Get average ticket price for industry."""
        category_lower = category.lower()
        for keyword, price in INDUSTRY_TICKET_PRICES.items():
            if keyword in category_lower:
                return price
        return INDUSTRY_TICKET_PRICES["default"]
    
    def _get_monthly_leads(self, category: str) -> int:
        """Estimate monthly leads for business type."""
        category_lower = category.lower()
        for keyword, leads in MONTHLY_LEAD_ESTIMATES.items():
            if keyword in category_lower:
                return leads
        return MONTHLY_LEAD_ESTIMATES["default"]
    
    def _calculate_data_quality(self, lead: BusinessLead) -> int:
        """
        Calculate data quality score (0-100).
        
        Factors:
        - Has business name: +20
        - Has phone: +25
        - Has website: +20
        - Has email: +15
        - Has address/location: +10
        - Has rating: +5
        - Has reviews: +5
        """
        score = 0
        
        if lead.business_name and lead.business_name.strip():
            score += 20
        if lead.phone and lead.phone.strip():
            score += 25
        if lead.website and lead.website.strip() and lead.website != "N/A":
            score += 20
        if lead.emails and len(lead.emails) > 0:
            score += 15
        if lead.address or lead.area or lead.city:
            score += 10
        if lead.rating and lead.rating > 0:
            score += 5
        if lead.reviews_count and lead.reviews_count > 0:
            score += 5
        
        return min(score, 100)
    
    def _calculate_reachability(self, lead: BusinessLead) -> int:
        """
        Calculate reachability score (0-100).
        
        Factors:
        - Has phone: +35
        - Has email: +25
        - Has WhatsApp: +15
        - Has website with contact form: +10
        - Has Google Maps listing: +10
        - Has click-to-call: +5
        """
        score = 0
        
        if lead.phone:
            score += 35
        if lead.emails:
            score += 25
        if lead.has_whatsapp:
            score += 15
        if lead.has_lead_form:
            score += 10
        if lead.google_maps_url:
            score += 10
        if lead.has_click_to_call:
            score += 5
        
        return min(score, 100)
    
    def _calculate_opportunity(self, lead: BusinessLead) -> int:
        """
        Calculate opportunity score (0-100).
        
        High opportunity = Missing automation they NEED
        
        Factors:
        - No online booking: +25
        - No chat widget: +20
        - No WhatsApp: +20
        - No lead form: +15
        - High-ticket category: +10
        - Good reviews but missing capture: +10
        """
        score = 0
        
        if not lead.has_booking_system:
            score += 25
            lead.has_after_hours_leak = True
        
        if not lead.has_chat_widget:
            score += 20
            lead.has_slow_response_risk = True
        
        if not lead.has_whatsapp:
            score += 20
        
        if not lead.has_lead_form:
            score += 15
        
        # High-ticket industries have more opportunity
        ticket = self._get_ticket_price(lead.category)
        if ticket >= 5000:
            score += 10
        
        # Good reviews but missing capture = big opportunity
        if lead.rating and lead.rating >= 4.0 and not lead.has_booking_system:
            score += 10
        
        return min(score, 100)
    
    def _calculate_revenue_loss(self, lead: BusinessLead) -> Tuple[int, int, float, str, float]:
        """
        Calculate estimated revenue loss.
        
        Returns:
            (monthly_leads, revenue_loss, missed_pct, recommended_tier, roi)
        """
        ticket_price = self._get_ticket_price(lead.category)
        monthly_leads = self._get_monthly_leads(lead.category)
        
        # Calculate missed percentage based on gaps
        missed_pct = 0.0
        
        if not lead.has_booking_system:
            missed_pct += 0.15  # 15% lost to competitors who respond faster
        
        if not lead.has_chat_widget:
            missed_pct += 0.10  # 10% lost after hours
        
        if not lead.has_whatsapp:
            missed_pct += 0.10  # 10% prefer WhatsApp
        
        if lead.has_slow_response_risk:
            missed_pct += 0.05  # Additional 5%
        
        missed_pct = min(missed_pct, 0.50)  # Cap at 50%
        
        # Calculate loss
        missed_leads = int(monthly_leads * missed_pct)
        revenue_loss = missed_leads * ticket_price
        
        # Calculate recoverable (70% recovery rate)
        recoverable = int(revenue_loss * 0.70)
        
        # Recommend tier based on loss
        if revenue_loss >= 200000:
            tier = "Enterprise ₹1.5L/month"
            our_cost = 150000
        elif revenue_loss >= 100000:
            tier = "Pro ₹60K/month"
            our_cost = 60000
        elif revenue_loss >= 50000:
            tier = "Growth ₹35K/month"
            our_cost = 35000
        else:
            tier = "Starter ₹15K/month"
            our_cost = 15000
        
        roi = recoverable / our_cost if our_cost > 0 else 0
        
        return monthly_leads, revenue_loss, missed_pct, tier, roi
    
    def _ai_reason_lead(self, lead: BusinessLead) -> Tuple[str, str, List[str]]:
        """
        Use AI to reason about lead quality and generate verdict.
        
        Returns:
            (reasoning, verdict, issues)
        """
        if not self.llm.api_key:
            # Fallback reasoning without AI
            return self._fallback_reasoning(lead)
        
        prompt = f"""Analyze this business lead for sales potential:

BUSINESS DATA:
- Name: {lead.business_name}
- Category: {lead.category}
- City: {lead.city}
- Website: {lead.website or 'None'}
- Phone: {lead.phone or 'None'}
- Emails: {', '.join(lead.emails) if lead.emails else 'None'}
- Rating: {lead.rating or 'Unknown'} ({lead.reviews_count or 0} reviews)

ENRICHMENT SIGNALS:
- Has Online Booking: {lead.has_booking_system}
- Has WhatsApp: {lead.has_whatsapp}
- Has Lead Form: {lead.has_lead_form}
- Has Chat Widget: {lead.has_chat_widget}
- Slow Response Risk: {lead.has_slow_response_risk}
- After Hours Leak: {lead.has_after_hours_leak}

SCORES:
- Data Quality: {lead.data_quality_score}/100
- Reachability: {lead.reachability_score}/100
- Opportunity: {lead.opportunity_score}/100

TASK:
1. Is this lead data REAL and VALID? (not fake/test data)
2. What validation issues exist?
3. Should we ACCEPT, REVIEW, or REJECT this lead?

Respond in JSON format:
{{
    "reasoning": "2-3 sentence analysis",
    "verdict": "ACCEPT|REVIEW|REJECT",
    "issues": ["list of issues if any"]
}}"""

        system_prompt = """You are a lead quality analyst. Be critical but fair.
ACCEPT = High quality, reachable, real business
REVIEW = Some concerns but potentially valid
REJECT = Fake data, unreachable, or too low quality"""

        result = self.llm.generate_json(prompt, system_prompt)
        
        if result:
            return (
                result.get("reasoning", "AI analysis unavailable"),
                result.get("verdict", "REVIEW"),
                result.get("issues", [])
            )
        
        return self._fallback_reasoning(lead)
    
    def _fallback_reasoning(self, lead: BusinessLead) -> Tuple[str, str, List[str]]:
        """Fallback reasoning without AI."""
        issues = []
        
        if not lead.phone and not lead.emails:
            issues.append("No contact information")
        if not lead.website:
            issues.append("No website")
        if lead.data_quality_score < 50:
            issues.append("Low data quality")
        
        if lead.data_quality_score >= 70 and lead.reachability_score >= 50:
            verdict = "ACCEPT"
            reasoning = f"Good data quality ({lead.data_quality_score}/100) with reachable contacts."
        elif lead.data_quality_score >= 40:
            verdict = "REVIEW"
            reasoning = f"Moderate data quality. Manual review recommended."
        else:
            verdict = "REJECT"
            reasoning = f"Insufficient data quality ({lead.data_quality_score}/100)."
        
        return reasoning, verdict, issues
    
    def _calculate_final_score(self, lead: BusinessLead) -> int:
        """
        Calculate final lead score (0-100).
        
        Weighted formula:
        - Data Quality: 30%
        - Reachability: 30%
        - Opportunity: 40%
        """
        score = (
            lead.data_quality_score * 0.30 +
            lead.reachability_score * 0.30 +
            lead.opportunity_score * 0.40
        )
        return int(min(max(score, 0), 100))
    
    def _assign_tier(self, score: int, opportunity: int) -> Tuple[LeadTier, PriorityLevel]:
        """Assign tier and priority based on scores."""
        if score >= 70 and opportunity >= 50:
            return LeadTier.HOT, PriorityLevel.CRITICAL
        elif score >= 70:
            return LeadTier.HOT, PriorityLevel.HIGH
        elif score >= 45 and opportunity >= 40:
            return LeadTier.WARM, PriorityLevel.HIGH
        elif score >= 45:
            return LeadTier.WARM, PriorityLevel.MEDIUM
        else:
            return LeadTier.COLD, PriorityLevel.LOW
    
    def _generate_outreach(self, lead: BusinessLead) -> None:
        """Generate all outreach content for lead."""
        loss_str = f"₹{lead.estimated_revenue_loss_inr/1000:.0f}k" if lead.estimated_revenue_loss_inr < 100000 else f"₹{lead.estimated_revenue_loss_inr/100000:.1f}L"
        recoverable_str = f"₹{lead.recoverable_amount_inr/1000:.0f}k" if lead.recoverable_amount_inr < 100000 else f"₹{lead.recoverable_amount_inr/100000:.1f}L"
        
        # Email
        lead.email_subject = f"Recovering {recoverable_str}/month for {lead.business_name}"
        
        lead.email_body = f"""Hi,

I came across {lead.business_name} and noticed you're likely losing {loss_str}/month in missed appointments and slow follow-ups.

Based on your Google reviews and category, here's what I found:
• {lead.estimated_monthly_leads} leads/month
• ~{int(lead.estimated_missed_pct*100)}% missed due to slow response
• {loss_str}/month revenue loss

We can recover {recoverable_str}/month with:
✅ WhatsApp assistant (instant response)
✅ Missed call capture
✅ Automated follow-ups

Cost: {lead.recommended_tier}
ROI: {lead.roi_multiple:.1f}x return

Want a free audit? Takes 2 days, shows exact ₹ being lost.

Reply "YES" and I'll send details.

Best,
[Your Name]
"""
        
        # WhatsApp
        lead.whatsapp_msg = f"""Hi! I noticed {lead.business_name} might be losing {recoverable_str}/month in missed appointments. 

We can recover this with WhatsApp automation + missed call capture.

Cost: {lead.recommended_tier}
ROI: {lead.roi_multiple:.1f}x

Want a free audit? Reply YES"""
        
        # Call Script
        lead.call_script = f"""Hi, this is [Name]. I'm calling about {lead.business_name}.

I noticed you're getting good reviews but might be losing {recoverable_str}/month in missed appointments due to slow response times.

We've helped similar {lead.category} businesses recover this revenue with WhatsApp automation.

Do you have 2 minutes to discuss?"""
        
        # Loom Script
        lead.loom_script = f"""[60 seconds]

Hi! I'm [Name] and I found {lead.business_name} on Google.

You have {lead.reviews_count or 'many'} reviews which is great, but I noticed you might be losing {recoverable_str}/month.

Here's why:
- {lead.estimated_monthly_leads} leads/month
- ~{int(lead.estimated_missed_pct*100)}% missed due to slow response
- That's {loss_str}/month gone

We can recover {recoverable_str}/month with simple WhatsApp automation.

Cost: {lead.recommended_tier}
ROI: {lead.roi_multiple:.1f}x return

Want a free audit? Email me at [email]"""
    
    def process_lead(self, raw_data: Dict[str, Any], category: str, city: str) -> Optional[BusinessLead]:
        """
        Process raw lead data through full intelligence pipeline.
        
        Args:
            raw_data: Raw data from Apify
            category: Business category
            city: City name
            
        Returns:
            Processed BusinessLead or None if invalid
        """
        # Create lead from raw data
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
            emails=[],
            google_maps_url=raw_data.get("url") or f"https://www.google.com/maps/search/{raw_data.get('title', '').replace(' ', '+')}",
            rating=raw_data.get("totalScore") or raw_data.get("rating"),
            reviews_count=raw_data.get("reviewsCount") or raw_data.get("reviews"),
            address=raw_data.get("address") or "",
            created_at=datetime.now(timezone.utc).isoformat(),
            updated_at=datetime.now(timezone.utc).isoformat(),
        )
        
        # Extract emails from various fields
        for field in ["email", "emails", "contactEmail"]:
            if raw_data.get(field):
                if isinstance(raw_data[field], list):
                    lead.emails.extend(raw_data[field])
                else:
                    lead.emails.append(raw_data[field])
        
        # Detect features from website/description
        website_lower = (lead.website or "").lower()
        desc = str(raw_data.get("description", "")).lower()
        
        lead.has_booking_system = any(x in website_lower or x in desc for x in 
            ["book", "appointment", "schedule", "practo", "justdial", "lybrate"])
        lead.has_whatsapp = any(x in website_lower or x in desc for x in 
            ["whatsapp", "wa.me", "api.whatsapp"])
        lead.has_lead_form = "form" in desc or "contact" in website_lower
        lead.has_chat_widget = any(x in desc for x in ["chat", "livechat", "intercom", "zendesk"])
        lead.has_click_to_call = lead.phone and len(lead.phone) >= 10
        
        # Calculate scores
        lead.data_quality_score = self._calculate_data_quality(lead)
        lead.reachability_score = self._calculate_reachability(lead)
        lead.opportunity_score = self._calculate_opportunity(lead)
        
        # Skip very low quality leads
        if lead.data_quality_score < 30:
            logger.info(f"   ⏭️ Skipping low quality lead: {lead.business_name}")
            return None
        
        # AI Reasoning
        logger.info(f"   🤖 AI reasoning for: {lead.business_name}")
        lead.ai_reasoning, lead.reasoning_verdict, lead.validation_issues = self._ai_reason_lead(lead)
        
        # Skip rejected leads
        if lead.reasoning_verdict == "REJECT":
            logger.info(f"   ❌ AI rejected: {lead.business_name} - {lead.ai_reasoning}")
            return None
        
        # Calculate revenue
        monthly_leads, loss, missed_pct, tier, roi = self._calculate_revenue_loss(lead)
        lead.estimated_monthly_leads = monthly_leads
        lead.estimated_revenue_loss_inr = loss
        lead.estimated_missed_pct = missed_pct
        lead.recoverable_amount_inr = int(loss * 0.70)
        lead.recommended_tier = tier
        lead.roi_multiple = roi
        
        # Final score and tier
        lead.final_score = self._calculate_final_score(lead)
        lead.tier, lead.priority = self._assign_tier(lead.final_score, lead.opportunity_score)
        
        # Generate outreach
        self._generate_outreach(lead)
        
        lead.status = "enriched"
        lead.updated_at = datetime.now(timezone.utc).isoformat()
        
        return lead
    
    def run_intelligence(
        self,
        niche: str,
        city: str,
        country: str = "India",
        target_count: int = 10
    ) -> Dict[str, Any]:
        """
        Run full intelligence pipeline.
        
        Args:
            niche: Business category to search
            city: Target city
            country: Target country
            target_count: Number of leads to process
            
        Returns:
            Report with all processed leads and summary
        """
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_dir = self.output_dir / f"{city}_{niche.replace(' ', '_')}_{run_id}"
        run_dir.mkdir(exist_ok=True)
        
        logger.info("=" * 70)
        logger.info(f"🚀 ZRAI INTELLIGENCE ENGINE v3.0")
        logger.info(f"   Target: {niche} in {city}, {country}")
        logger.info(f"   Goal: {target_count} leads")
        logger.info("=" * 70)
        
        # Phase 1: Discovery
        logger.info("\n📍 PHASE 1: DISCOVERY")
        raw_leads = self.apify.discover_businesses(niche, city, country, limit=target_count * 2)
        
        if not raw_leads:
            logger.error("❌ No leads discovered. Check Apify token.")
            return {"error": "Discovery failed", "leads": []}
        
        # Phase 2: Processing
        logger.info(f"\n🔬 PHASE 2: INTELLIGENCE PROCESSING ({len(raw_leads)} raw leads)")
        
        processed_leads: List[BusinessLead] = []
        hot_count = 0
        warm_count = 0
        cold_count = 0
        
        for i, raw in enumerate(raw_leads[:target_count * 2], 1):
            if len(processed_leads) >= target_count:
                break
            
            logger.info(f"\n[{i}/{len(raw_leads)}] Processing: {raw.get('title', 'Unknown')}")
            
            lead = self.process_lead(raw, niche, city)
            
            if lead:
                processed_leads.append(lead)
                
                if lead.tier == LeadTier.HOT:
                    hot_count += 1
                    emoji = "🔥"
                elif lead.tier == LeadTier.WARM:
                    warm_count += 1
                    emoji = "☀️"
                else:
                    cold_count += 1
                    emoji = "❄️"
                
                logger.info(f"   {emoji} {lead.tier.value} | Score: {lead.final_score} | Loss: ₹{lead.estimated_revenue_loss_inr:,}/mo")
        
        # Phase 3: Save Results
        logger.info(f"\n💾 PHASE 3: SAVING RESULTS")
        
        # Sort by tier and score
        processed_leads.sort(key=lambda x: (-1 if x.tier == LeadTier.HOT else 0 if x.tier == LeadTier.WARM else 1, -x.final_score))
        
        # Create report
        report = {
            "run_id": run_id,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "config": {
                "niche": niche,
                "city": city,
                "country": country,
                "target_count": target_count,
            },
            "summary": {
                "discovered": len(raw_leads),
                "processed": len(processed_leads),
                "hot": hot_count,
                "warm": warm_count,
                "cold": cold_count,
                "total_opportunity_inr": sum(l.estimated_revenue_loss_inr for l in processed_leads),
            },
            "leads": [lead.to_dict() for lead in processed_leads],
        }
        
        # Save files
        summary_file = run_dir / "summary.json"
        with open(summary_file, 'w') as f:
            json.dump(report["summary"] | report["config"], f, indent=2)
        
        leads_file = run_dir / "leads.json"
        with open(leads_file, 'w') as f:
            json.dump(report["leads"], f, indent=2, ensure_ascii=False)
        
        # Save hot leads separately
        hot_leads = [l for l in processed_leads if l.tier == LeadTier.HOT]
        if hot_leads:
            hot_file = run_dir / "hot_leads.json"
            with open(hot_file, 'w') as f:
                json.dump([l.to_dict() for l in hot_leads], f, indent=2, ensure_ascii=False)
        
        # Print Summary
        self._print_summary(report, run_dir)
        
        return report
    
    def _print_summary(self, report: Dict[str, Any], run_dir: Path) -> None:
        """Print beautiful summary."""
        summary = report["summary"]
        config = report["config"]
        
        print("\n" + "=" * 70)
        print("✅ INTELLIGENCE RUN COMPLETE")
        print("=" * 70)
        print(f"\n📁 Output: {run_dir}")
        print(f"\n📊 RESULTS:")
        print(f"   Discovered:  {summary['discovered']}")
        print(f"   Processed:   {summary['processed']}")
        print(f"   🔥 HOT:      {summary['hot']}")
        print(f"   ☀️ WARM:     {summary['warm']}")
        print(f"   ❄️ COLD:     {summary['cold']}")
        print(f"\n💰 TOTAL OPPORTUNITY: ₹{summary['total_opportunity_inr']:,}/month")
        print(f"   Annual: ₹{summary['total_opportunity_inr'] * 12:,}/year")
        
        # Top 5 leads
        if report["leads"]:
            print("\n🎯 TOP LEADS:")
            for i, lead in enumerate(report["leads"][:5], 1):
                tier_emoji = "🔥" if lead["tier"] == "HOT" else "☀️" if lead["tier"] == "WARM" else "❄️"
                print(f"   {i}. {tier_emoji} {lead['business_name'][:30]} | Score: {lead['final_score']} | Loss: ₹{lead['estimated_revenue_loss_inr']:,}/mo")
        
        print("\n" + "=" * 70)
        print("🚀 GO CLOSE DEALS!")
        print("=" * 70 + "\n")


# =============================================================================
# CLI INTERFACE
# =============================================================================

def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="ZRAI Production Intelligence Engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python PRODUCTION_INTELLIGENCE.py --niche "diagnostic center" --city Bangalore
  python PRODUCTION_INTELLIGENCE.py --niche "dental clinic" --city Mumbai --count 20
  python PRODUCTION_INTELLIGENCE.py --niche "coaching center" --city Hyderabad --count 15
        """
    )
    
    parser.add_argument("--niche", type=str, required=True, help="Business category to search")
    parser.add_argument("--city", type=str, required=True, help="Target city")
    parser.add_argument("--country", type=str, default="India", help="Target country")
    parser.add_argument("--count", type=int, default=10, help="Number of leads to process")
    
    args = parser.parse_args()
    
    engine = IntelligenceEngine()
    report = engine.run_intelligence(
        niche=args.niche,
        city=args.city,
        country=args.country,
        target_count=args.count
    )
    
    if report.get("error"):
        print(f"\n❌ Error: {report['error']}")
        sys.exit(1)
    
    print(f"\n✅ Success! Processed {report['summary']['processed']} leads.")


if __name__ == "__main__":
    main()
