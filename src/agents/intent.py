"""
Intent Agent - Intent and revenue leak detection.
Requirements: 5.1-5.6
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import re
import logging

from src.agents.base import BaseAgent
from src.graph.state import LeadGraphState
from src.db.models import IntentData, SpeedToLeadRisk, ReviewEvidence, CTAType


logger = logging.getLogger(__name__)


# High-ticket categories with expanded matching terms
HIGH_TICKET_CATEGORIES = {
    # Home Services
    "roofing", "roofer", "roof",
    "hvac", "heating", "cooling", "air conditioning", "ac repair",
    "plumbing", "plumber", "pipe", "drain",
    "electrical", "electrician", "electric",
    "solar", "solar panel", "renewable energy",
    "remodeling", "remodel", "renovation", "contractor",
    "construction", "builder", "general contractor",
    "landscaping", "landscaper", "lawn", "garden",
    "pool", "swimming pool", "pool service",
    "pest control", "exterminator",
    "garage door", "fence", "painting", "painter",
    "flooring", "carpet", "tile",
    "window", "door", "siding",
    "home services", "handyman",
    
    # Medical/Health
    "dental", "dentist", "orthodontist", "oral surgeon",
    "medical", "doctor", "physician", "clinic",
    "chiropractic", "chiropractor", "spine",
    "physical therapy", "physiotherapy", "pt",
    "veterinary", "vet", "animal hospital",
    "optometry", "optometrist", "eye doctor",
    "dermatology", "dermatologist", "skin",
    "plastic surgery", "cosmetic",
    "mental health", "therapy", "counseling", "psychologist",
    
    # Professional Services
    "legal", "lawyer", "attorney", "law firm",
    "financial", "accountant", "cpa", "tax",
    "insurance", "insurance agent",
    "real estate", "realtor", "property",
    
    # Automotive
    "automotive", "auto repair", "mechanic", "car",
    "body shop", "collision", "tire",
    
    # Other High-Value
    "moving", "mover", "relocation",
    "storage", "self storage",
    "cleaning", "maid", "janitorial",
    "security", "alarm", "locksmith",
    "appliance repair", "appliance",
}

# Review phrases indicating missed responses
NEGATIVE_REVIEW_PHRASES = [
    "no response", "never called back", "hard to reach",
    "couldn't get through", "didn't answer", "no reply",
    "waited days", "never heard back", "ignored my call",
    "poor communication", "unresponsive",
]


class IntentAgent(BaseAgent):
    """
    Intent Agent for computing intent and revenue leak scores.
    
    Requirements:
    - 5.1: Compute intent_score (0-100) based on CTA type, ad activity, high-ticket patterns
    - 5.2: Compute leak_score (0-100) based on call-only CTAs, missing booking, after-hours gaps
    - 5.3: Compute reactivation_fit (0-100) based on consideration cycle and follow-up failure
    - 5.4: Generate plain-English explanation in why_this_lead field
    - 5.5: Classify speed_to_lead_risk as LOW, MED, or HIGH
    - 5.6: Mine reviews for missed response phrases
    """
    
    def __init__(self):
        super().__init__("intent")
    
    def process(self, state: LeadGraphState) -> LeadGraphState:
        """Process intent detection for a lead."""
        if not state.get("lead"):
            self._logger.warning("No lead data for intent detection")
            return state
        
        state["current_stage"] = "intent"
        
        lead = state["lead"]
        enrichment = state.get("enrichment", {})
        
        # Compute scores
        intent_score = self._compute_intent_score(lead, enrichment)
        leak_score = self._compute_leak_score(lead, enrichment)
        reactivation_fit = self._compute_reactivation_fit(lead, enrichment)
        volume_score = self._calculate_volume_score(lead, enrichment)  # NEW
        speed_to_lead_risk = self._classify_speed_to_lead_risk(lead, enrichment)
        
        # Mine reviews for evidence
        review_evidence = self._mine_reviews(lead)
        
        # Generate explanation
        why_this_lead = self._generate_explanation(
            lead, enrichment, intent_score, leak_score, reactivation_fit, volume_score
        )
        
        # Create intent data dict
        intent = {
            "lead_id": lead.get("lead_id"),
            "intent_score": intent_score,
            "leak_score": leak_score,
            "reactivation_fit": reactivation_fit,
            "volume_score": volume_score,  # NEW
            "why_this_lead": why_this_lead,
            "speed_to_lead_risk": speed_to_lead_risk,
            "review_evidence": review_evidence,
        }
        
        state["intent"] = intent
        
        # Save to database
        self._save_intent(intent)
        
        return state
    
    def _is_high_ticket_category(self, category: str) -> bool:
        """Check if category matches high-ticket list using fuzzy matching."""
        if not category:
            return False
        category_lower = category.lower()
        
        # Check both directions: category contains keyword OR keyword contains category
        for htc in HIGH_TICKET_CATEGORIES:
            if htc in category_lower or category_lower in htc:
                return True
        
        # Also check individual words (but require meaningful overlap)
        category_words = set(category_lower.split())
        # Filter out common non-meaningful words
        stop_words = {"the", "a", "an", "and", "or", "of", "in", "for", "to", "shop", "store", "center", "inc", "llc", "co"}
        category_words = category_words - stop_words
        
        for htc in HIGH_TICKET_CATEGORIES:
            htc_words = set(htc.split()) - stop_words
            if category_words & htc_words:  # Any meaningful word overlap
                return True
        
        return False
    
    def _compute_intent_score(self, lead: Dict[str, Any], enrichment: Dict[str, Any]) -> int:
        """
        Compute intent score (100X ENHANCED - aggressive scoring).
        Requirements: 5.1
        
        Scoring (max 100):
        - high_ticket_category: +30 (most important signal)
        - has_website: +20 (cares about online presence)
        - has_phone: +15 (reachable, serious business)
        - has_email: +10 (contactable)
        - ads_active: +15 (bonus for ad spenders)
        - good_reviews (4+ stars): +15
        - review_count > 10: +10 (established business)
        - has_address: +10 (legitimate business)
        - booking_provider: +10
        - recent_ad_start (< 30 days): +5
        """
        score = 0
        
        # High-ticket category is the PRIMARY signal (using fuzzy matching)
        if self._is_high_ticket_category(lead.get("category")):
            score += 30
        
        # Has website = cares about online presence (major signal)
        website = lead.get("website") or lead.get("landing_page_url")
        if website and str(website).strip():
            score += 20
        
        # Has phone = reachable, serious business
        if lead.get("phone"):
            score += 15
        
        # Has email = contactable
        emails = lead.get("emails_found") or []
        if emails and len(emails) > 0:
            score += 10
        
        # Active ads indicate spending intent (bonus)
        if lead.get("ads_active"):
            score += 15
        
        # Good review rating (if available)
        rating = lead.get("rating") or lead.get("review_rating")
        if rating:
            try:
                if float(rating) >= 4.0:
                    score += 15
                elif float(rating) >= 3.5:
                    score += 8
            except:
                pass
        
        # Review count indicates established business
        review_count = lead.get("review_count") or lead.get("reviews_count") or 0
        try:
            if int(review_count) > 50:
                score += 10
            elif int(review_count) > 10:
                score += 5
        except:
            pass
        
        # Has address = legitimate business
        if lead.get("address") or lead.get("location"):
            score += 10
        
        # Booking system indicates service business
        if enrichment and enrichment.get("booking_provider"):
            score += 10
        
        # Recent ad start indicates active campaign
        ad_start_date = lead.get("ad_start_date")
        if ad_start_date:
            try:
                if isinstance(ad_start_date, str):
                    ad_start_date = datetime.fromisoformat(ad_start_date.replace('Z', '+00:00'))
                days_since_start = (datetime.utcnow() - ad_start_date.replace(tzinfo=None)).days
                if days_since_start < 30:
                    score += 5
            except:
                pass
        
        return min(score, 100)
    
    def _compute_leak_score(self, lead: Dict[str, Any], enrichment: Dict[str, Any]) -> int:
        """
        Compute revenue leak score.
        Requirements: 5.2
        
        Scoring:
        - cta_type == 'CALL' and no_booking_system: +30
        - no_chat_widget: +15
        - after_hours_gap: +25
        - form_friction (>5 fields): +20
        - slow_website (>3s load): +10
        """
        score = 0
        
        cta_type = lead.get("cta_type")
        
        # Call-only with no booking = missed after-hours leads
        if cta_type == CTAType.CALL or cta_type == "CALL":
            if not enrichment or not enrichment.get("booking_provider"):
                score += 30
        
        # No chat widget = no after-hours capture
        if not enrichment or not enrichment.get("chat_widget"):
            score += 15
        
        # No booking system = after-hours gap
        if not enrichment or not enrichment.get("booking_provider"):
            score += 25
        
        # Form friction (would need audit data for accurate count)
        # Placeholder: assume friction if no form tool detected
        if enrichment and not enrichment.get("form_tool"):
            score += 10
        
        return min(score, 100)
    
    def _compute_reactivation_fit(self, lead: Dict[str, Any], enrichment: Dict[str, Any]) -> int:
        """
        Compute reactivation fit score (100X ENHANCED).
        Requirements: 5.3
        
        Scoring:
        - high_ticket_category: +35 (long consideration cycle)
        - has_website_no_booking: +25 (missing lead capture)
        - no_chat_widget: +20 (after-hours gap)
        - seasonal_business: +15
        - established_business: +10
        """
        score = 0
        
        category = lead.get("category")
        
        # High-ticket = long consideration cycle = high reactivation potential
        if self._is_high_ticket_category(category):
            score += 35
        
        # Has website but no booking = missing lead capture opportunity
        website = lead.get("website") or lead.get("landing_page_url")
        has_booking = enrichment and enrichment.get("booking_provider")
        if website and not has_booking:
            score += 25
        
        # No chat widget = after-hours gap
        has_chat = enrichment and enrichment.get("chat_widget")
        if not has_chat:
            score += 20
        
        # Seasonal businesses have reactivation cycles
        seasonal_keywords = ["landscaping", "pool", "hvac", "roofing", "snow", "lawn", "garden", "heating", "cooling"]
        if category and any(kw in category.lower() for kw in seasonal_keywords):
            score += 15
        
        # Established business = more leads to reactivate
        review_count = lead.get("review_count") or lead.get("reviews_count") or 0
        try:
            if int(review_count) > 20:
                score += 10
        except:
            pass
        
        return min(score, 100)
    
    def _classify_speed_to_lead_risk(self, lead: Dict[str, Any], enrichment: Dict[str, Any]) -> SpeedToLeadRisk:
        """
        Classify speed-to-lead risk.
        Requirements: 5.5
        
        Logic:
        - if cta_type == 'CALL' and no_after_hours: risk = 'HIGH'
        - elif form_only and no_auto_response: risk = 'MED'
        - else: risk = 'LOW'
        """
        has_after_hours = False
        if enrichment:
            has_after_hours = bool(enrichment.get("chat_widget") or enrichment.get("booking_provider"))
        
        cta_type = lead.get("cta_type")
        
        # Call CTA with no after-hours capture = HIGH risk
        if (cta_type == CTAType.CALL or cta_type == "CALL") and not has_after_hours:
            return SpeedToLeadRisk.HIGH
        
        # Form only with no chat = MED risk
        if cta_type == CTAType.FORM or cta_type == "FORM":
            if not enrichment or not enrichment.get("chat_widget"):
                return SpeedToLeadRisk.MED
        
        return SpeedToLeadRisk.LOW
    
    def _mine_reviews(self, lead: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Mine reviews for missed response evidence.
        Requirements: 5.6
        """
        evidence = []
        
        # In production, would:
        # 1. Fetch reviews from Google Maps data
        # 2. Search for negative phrases
        # 3. Extract snippets with source URLs
        
        # Placeholder - would be populated from actual review data
        return evidence
    
    def _calculate_volume_score(self, lead: Dict[str, Any], enrichment: Dict[str, Any]) -> int:
        """
        Calculate volume score from Google Maps signals.
        Requirements: MAXIMUM QUALITY LEAD SCORING
        
        Scoring (max 100):
        - Review count (0-40 points):
          - >500 reviews: 40 pts (very high volume)
          - >200 reviews: 30 pts (high volume)
          - >100 reviews: 20 pts (medium volume)
          - >50 reviews: 10 pts (low volume)
        
        - Peak busyness (0-30 points):
          - >90: 30 pts ("Usually as busy as it gets")
          - >70: 20 pts (very busy)
          - >50: 10 pts (moderately busy)
        
        - Busy hours count (0-20 points):
          - >40 hours/week: 20 pts (busy most of week)
          - >20 hours/week: 10 pts (regularly busy)
        
        - Visit duration (0-10 points):
          - >60 min: 10 pts (long visits = high engagement)
          - >30 min: 5 pts (moderate engagement)
        """
        score = 0
        
        # Review count (0-40 points) - PRIMARY volume indicator
        reviews = lead.get("reviews_count") or lead.get("reviewsCount") or 0
        try:
            reviews = int(reviews) if reviews else 0
            if reviews > 500:
                score += 40  # Very high volume
            elif reviews > 200:
                score += 30  # High volume
            elif reviews > 100:
                score += 20  # Medium volume
            elif reviews > 50:
                score += 10  # Low volume
        except:
            pass
        
        # Peak busyness (0-30 points) - Google Maps popular times
        if enrichment:
            peak = enrichment.get("peak_busyness") or 0
            try:
                peak = int(peak) if peak else 0
                if peak > 90:
                    score += 30  # "Usually as busy as it gets"
                elif peak > 70:
                    score += 20  # Very busy
                elif peak > 50:
                    score += 10  # Moderately busy
            except:
                pass
            
            # Busy hours count (0-20 points) - Consistency indicator
            busy_hours = enrichment.get("busy_hours_count") or 0
            try:
                busy_hours = int(busy_hours) if busy_hours else 0
                if busy_hours > 40:  # Busy most of the week
                    score += 20
                elif busy_hours > 20:  # Regularly busy
                    score += 10
            except:
                pass
            
            # Visit duration (0-10 points) - Engagement indicator
            duration = enrichment.get("avg_visit_duration_min") or 0
            try:
                duration = int(duration) if duration else 0
                if duration > 60:  # Long visits = high engagement
                    score += 10
                elif duration > 30:  # Moderate engagement
                    score += 5
            except:
                pass
        
        return min(score, 100)
    
    def _generate_explanation(
        self,
        lead: Dict[str, Any],
        enrichment: Dict[str, Any],
        intent_score: int,
        leak_score: int,
        reactivation_fit: int,
        volume_score: int = 0,  # NEW parameter
    ) -> str:
        """
        Generate plain-English explanation.
        Requirements: 5.4
        """
        reasons = []
        
        cta_type = lead.get("cta_type")
        category = lead.get("category")
        
        # Volume reasons (NEW - highest priority)
        if volume_score > 70:
            reviews = lead.get("reviews_count") or lead.get("reviewsCount") or 0
            if enrichment and enrichment.get("peak_busyness", 0) > 90:
                reasons.append(f"extremely high volume ({reviews}+ reviews, peak busy)")
            else:
                reasons.append(f"high volume business ({reviews}+ reviews)")
        elif volume_score > 40:
            reasons.append("moderate volume with growth potential")
        
        # Intent reasons
        if lead.get("ads_active"):
            reasons.append("actively running ads")
        
        if cta_type == CTAType.CALL or cta_type == "CALL":
            reasons.append("using call-based CTAs")
        
        if category:
            category_lower = category.lower()
            if any(htc in category_lower for htc in HIGH_TICKET_CATEGORIES):
                reasons.append(f"in high-ticket {category} category")
        
        # Leak reasons
        if not enrichment or not enrichment.get("booking_provider"):
            reasons.append("no online booking system detected")
        
        if not enrichment or not enrichment.get("chat_widget"):
            reasons.append("no chat widget for after-hours capture")
        
        # Build explanation
        if reasons:
            explanation = f"This lead scores well because they are {', '.join(reasons[:3])}."
            
            if leak_score > 50:
                explanation += f" Revenue leak potential is high ({leak_score}/100) due to gaps in lead capture."
            
            if volume_score > 70:
                explanation += f" Volume signals are strong ({volume_score}/100) indicating high traffic."
            
            return explanation
        
        return "This lead shows moderate potential based on available signals."
    
    def _save_intent(self, intent: Dict[str, Any]) -> None:
        """Save intent data to database."""
        data = dict(intent)
        data["lead_id"] = str(intent.get("lead_id", ""))
        data["created_at"] = datetime.utcnow().isoformat()
        
        # Convert enums
        speed_risk = intent.get("speed_to_lead_risk")
        data["speed_to_lead_risk"] = speed_risk.value if hasattr(speed_risk, 'value') else speed_risk
        
        # Review evidence is already a list of dicts
        
        self._db.save_intent_data(data)


_intent_agent: Optional[IntentAgent] = None


def _get_intent_agent() -> IntentAgent:
    global _intent_agent
    if _intent_agent is None:
        _intent_agent = IntentAgent()
    return _intent_agent


def intent_node(state: LeadGraphState) -> LeadGraphState:
    """LangGraph node function for intent detection."""
    return _get_intent_agent()(state)
