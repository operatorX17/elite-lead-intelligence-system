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
from src.tools.llm import get_llm_client


logger = logging.getLogger(__name__)


# High-ticket categories
HIGH_TICKET_CATEGORIES = {
    "roofing", "hvac", "plumbing", "electrical", "solar",
    "remodeling", "construction", "landscaping", "pool",
    "dental", "medical", "legal", "financial", "insurance",
    "real estate", "automotive", "home services",
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
        self._llm = get_llm_client()
    
    def process(self, state: LeadGraphState) -> LeadGraphState:
        """Process intent detection for a lead."""
        if not state.lead:
            self._logger.warning("No lead data for intent detection")
            return state
        
        state.current_stage = "intent"
        
        lead = state.lead
        enrichment = state.enrichment
        
        # Compute scores
        intent_score = self._compute_intent_score(lead, enrichment)
        leak_score = self._compute_leak_score(lead, enrichment)
        reactivation_fit = self._compute_reactivation_fit(lead, enrichment)
        speed_to_lead_risk = self._classify_speed_to_lead_risk(lead, enrichment)
        
        # Mine reviews for evidence
        review_evidence = self._mine_reviews(lead)
        
        # Generate explanation
        why_this_lead = self._generate_explanation(
            lead, enrichment, intent_score, leak_score, reactivation_fit
        )
        
        # Create intent data
        intent = IntentData(
            lead_id=lead.lead_id,
            intent_score=intent_score,
            leak_score=leak_score,
            reactivation_fit=reactivation_fit,
            why_this_lead=why_this_lead,
            speed_to_lead_risk=speed_to_lead_risk,
            review_evidence=review_evidence,
        )
        
        state.intent = intent
        
        # Save to database
        self._save_intent(intent)
        
        return state
    
    def _compute_intent_score(self, lead, enrichment) -> int:
        """
        Compute intent score.
        Requirements: 5.1
        
        Scoring:
        - ads_active: +30
        - cta_type == 'CALL': +20
        - high_ticket_category: +25
        - multiple_ad_creatives: +15
        - recent_ad_start (< 30 days): +10
        """
        score = 0
        
        # Active ads indicate spending intent
        if lead.ads_active:
            score += 30
        
        # Call CTA indicates high-intent leads
        if lead.cta_type == CTAType.CALL or lead.cta_type == "CALL":
            score += 20
        
        # High-ticket category
        if lead.category:
            category_lower = lead.category.lower()
            if any(htc in category_lower for htc in HIGH_TICKET_CATEGORIES):
                score += 25
        
        # Recent ad start indicates active campaign
        if lead.ad_start_date:
            days_since_start = (datetime.utcnow() - lead.ad_start_date).days
            if days_since_start < 30:
                score += 10
        
        # Booking system indicates service business
        if enrichment and enrichment.booking_provider:
            score += 15
        
        return min(score, 100)
    
    def _compute_leak_score(self, lead, enrichment) -> int:
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
        
        # Call-only with no booking = missed after-hours leads
        if (lead.cta_type == CTAType.CALL or lead.cta_type == "CALL"):
            if not enrichment or not enrichment.booking_provider:
                score += 30
        
        # No chat widget = no after-hours capture
        if not enrichment or not enrichment.chat_widget:
            score += 15
        
        # No booking system = after-hours gap
        if not enrichment or not enrichment.booking_provider:
            score += 25
        
        # Form friction (would need audit data for accurate count)
        # Placeholder: assume friction if no form tool detected
        if enrichment and not enrichment.form_tool:
            score += 10
        
        return min(score, 100)
    
    def _compute_reactivation_fit(self, lead, enrichment) -> int:
        """
        Compute reactivation fit score.
        Requirements: 5.3
        
        Scoring:
        - long_consideration_cycle: +40
        - follow_up_failure_cues: +30
        - high_ticket: +20
        - seasonal_business: +10
        """
        score = 0
        
        # High-ticket = long consideration cycle
        if lead.category:
            category_lower = lead.category.lower()
            if any(htc in category_lower for htc in HIGH_TICKET_CATEGORIES):
                score += 40  # Long consideration cycle
                score += 20  # High ticket
        
        # Follow-up failure cues from reviews
        # (Would be populated from review mining)
        
        # Seasonal businesses
        seasonal_keywords = ["landscaping", "pool", "hvac", "roofing", "snow"]
        if lead.category and any(kw in lead.category.lower() for kw in seasonal_keywords):
            score += 10
        
        return min(score, 100)
    
    def _classify_speed_to_lead_risk(self, lead, enrichment) -> SpeedToLeadRisk:
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
            has_after_hours = bool(enrichment.chat_widget or enrichment.booking_provider)
        
        # Call CTA with no after-hours capture = HIGH risk
        if (lead.cta_type == CTAType.CALL or lead.cta_type == "CALL") and not has_after_hours:
            return SpeedToLeadRisk.HIGH
        
        # Form only with no chat = MED risk
        if (lead.cta_type == CTAType.FORM or lead.cta_type == "FORM"):
            if not enrichment or not enrichment.chat_widget:
                return SpeedToLeadRisk.MED
        
        return SpeedToLeadRisk.LOW
    
    def _mine_reviews(self, lead) -> List[ReviewEvidence]:
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
    
    def _generate_explanation(
        self,
        lead,
        enrichment,
        intent_score: int,
        leak_score: int,
        reactivation_fit: int,
    ) -> str:
        """
        Generate plain-English explanation.
        Requirements: 5.4
        """
        reasons = []
        
        # Intent reasons
        if lead.ads_active:
            reasons.append("actively running ads")
        
        if lead.cta_type == CTAType.CALL or lead.cta_type == "CALL":
            reasons.append("using call-based CTAs")
        
        if lead.category:
            category_lower = lead.category.lower()
            if any(htc in category_lower for htc in HIGH_TICKET_CATEGORIES):
                reasons.append(f"in high-ticket {lead.category} category")
        
        # Leak reasons
        if not enrichment or not enrichment.booking_provider:
            reasons.append("no online booking system detected")
        
        if not enrichment or not enrichment.chat_widget:
            reasons.append("no chat widget for after-hours capture")
        
        # Build explanation
        if reasons:
            explanation = f"This lead scores well because they are {', '.join(reasons[:3])}."
            
            if leak_score > 50:
                explanation += f" Revenue leak potential is high ({leak_score}/100) due to gaps in lead capture."
            
            return explanation
        
        return "This lead shows moderate potential based on available signals."
    
    def _save_intent(self, intent: IntentData) -> None:
        """Save intent data to database."""
        data = intent.model_dump()
        data["lead_id"] = str(intent.lead_id)
        data["created_at"] = datetime.utcnow().isoformat()
        
        # Convert enums
        data["speed_to_lead_risk"] = intent.speed_to_lead_risk.value if hasattr(intent.speed_to_lead_risk, 'value') else intent.speed_to_lead_risk
        
        # Convert review evidence to JSON-serializable format
        data["review_evidence"] = [
            {"snippet": e.snippet, "source_url": e.source_url, "sentiment": e.sentiment}
            for e in intent.review_evidence
        ]
        
        self._db.save_intent_data(data)


# Create singleton instance for LangGraph node
_intent_agent = IntentAgent()


def intent_node(state: LeadGraphState) -> LeadGraphState:
    """LangGraph node function for intent detection."""
    return _intent_agent(state)
