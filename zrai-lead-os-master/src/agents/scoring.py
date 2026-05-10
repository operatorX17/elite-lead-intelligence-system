"""
Scoring Agent - Weighted scoring and disqualification.
Requirements: 7.1-7.6
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import logging

from src.agents.base import BaseAgent
from src.graph.state import LeadGraphState
from src.db.models import ScoringResult, ScoreBreakdown, LeadTier
from src.config import load_config


logger = logging.getLogger(__name__)


# Disqualification rules (Requirement 7.3)
DISQUALIFICATION_RULES = [
    {
        "name": "too_small",
        "reason": "Owner-only business",
    },
    {
        "name": "no_ads_history",
        "reason": "No advertising spend detected",
    },
    {
        "name": "emergency_only",
        "reason": "Emergency-only service",
    },
    {
        "name": "toxic_reviews",
        "reason": "Toxic review pattern",
    },
    {
        "name": "no_contact_path",
        "reason": "No valid contact method",
    },
]


class ScoringAgent(BaseAgent):
    """
    Scoring Agent for weighted scoring and disqualification.
    
    Requirements:
    - 7.1: Compute final_score using weighted formula
    - 7.2: Load per-niche weight configuration
    - 7.3: Apply do_not_contact rules
    - 7.4: Record do_not_contact_reason
    - 7.5: Assign lead_tier (A/B/C)
    - 7.6: Exclude tier C from outreach queues
    """
    
    # Default weights (100X ENHANCED - favor signals we have)
    DEFAULT_WEIGHTS = {
        "ad_activity": 0.05,      # Reduced - most leads don't have ads
        "intent": 0.35,           # Increased - our best signal
        "leak": 0.25,             # High leak = high opportunity
        "reactivation": 0.20,     # Increased - good for high-ticket
        "contact_quality": 0.10,  # Keep same
        "business_size": 0.05,    # Keep same
    }
    
    # Tier thresholds (100X ADJUSTED for realistic scoring)
    TIER_A_THRESHOLD = 55  # Hot leads - ready to pitch
    TIER_B_THRESHOLD = 35  # Warm leads - soft pitch
    
    def __init__(self):
        super().__init__("scoring")
    
    def process(self, state: LeadGraphState) -> LeadGraphState:
        """Process scoring for a lead."""
        if not state.get("lead"):
            self._logger.warning("No lead data for scoring")
            return state
        
        state["current_stage"] = "scoring"
        
        lead = state["lead"]
        enrichment = state.get("enrichment", {})
        intent = state.get("intent", {})
        
        # Check disqualification rules first
        disqualified, reason = self._check_disqualification(lead, enrichment, intent)
        
        if disqualified:
            scoring = {
                "lead_id": lead.get("lead_id"),
                "final_score": 0,
                "score_breakdown": {},
                "lead_tier": "C",
                "do_not_contact": True,
                "do_not_contact_reason": reason,
            }
            state["scoring"] = scoring
            state["is_disqualified"] = True
            state["should_skip_outreach"] = True
            
            self._save_scoring(scoring)
            return state
        
        # Get weights (per-niche if available)
        weights = self._get_weights(lead.get("category"))
        
        # Compute component scores
        breakdown = self._compute_score_breakdown(lead, enrichment, intent)
        
        # Compute final weighted score
        final_score = self._compute_final_score(breakdown, weights)
        
        # Assign tier
        tier = self._assign_tier(final_score)
        
        # Create scoring result dict
        scoring = {
            "lead_id": lead.get("lead_id"),
            "final_score": final_score,
            "score_breakdown": breakdown,
            "lead_tier": tier,
            "do_not_contact": False,
            "do_not_contact_reason": None,
        }
        
        state["scoring"] = scoring
        
        # Set skip flag for tier C (Requirement 7.6)
        if tier == "C":
            state["should_skip_outreach"] = True
        
        # Save to database
        self._save_scoring(scoring)
        
        return state
    
    def _get_weights(self, category: Optional[str]) -> Dict[str, float]:
        """
        Get scoring weights, potentially per-niche.
        Requirements: 7.2
        """
        config = load_config()
        
        # Check for niche-specific weights
        if category:
            category_lower = category.lower()
            for niche_name, niche_config in config.niches.items():
                if niche_name.lower() in category_lower:
                    weights = niche_config.scoring_weights
                    return {
                        "ad_activity": weights.ad_activity,
                        "intent": weights.intent,
                        "leak": weights.leak,
                        "reactivation": weights.reactivation,
                        "contact_quality": weights.contact_quality,
                        "business_size": weights.business_size,
                    }
        
        return self.DEFAULT_WEIGHTS
    
    def _compute_score_breakdown(
        self,
        lead: Dict[str, Any],
        enrichment: Dict[str, Any],
        intent: Dict[str, Any],
    ) -> Dict[str, int]:
        """Compute individual score components."""
        # Ad activity score (0-100)
        ad_activity_score = 0
        if lead.get("ads_active"):
            ad_activity_score += 50
        
        ad_start_date = lead.get("ad_start_date")
        if ad_start_date:
            if isinstance(ad_start_date, str):
                ad_start_date = datetime.fromisoformat(ad_start_date)
            days_active = (datetime.utcnow() - ad_start_date).days
            if days_active < 30:
                ad_activity_score += 30
            elif days_active < 90:
                ad_activity_score += 20
            else:
                ad_activity_score += 10
        
        ad_last_seen = lead.get("ad_last_seen")
        if ad_last_seen:
            if isinstance(ad_last_seen, str):
                ad_last_seen = datetime.fromisoformat(ad_last_seen)
            days_since = (datetime.utcnow() - ad_last_seen).days
            if days_since < 7:
                ad_activity_score += 20
        ad_activity_score = min(ad_activity_score, 100)
        
        # Intent score (from intent agent)
        intent_score = intent.get("intent_score", 0) if intent else 0
        
        # Leak score (from intent agent)
        leak_score = intent.get("leak_score", 0) if intent else 0
        
        # Reactivation score (from intent agent)
        reactivation_score = intent.get("reactivation_fit", 0) if intent else 0
        
        # Contact quality score (from enrichment)
        contact_quality_score = enrichment.get("contact_quality_score", 0) if enrichment else 0
        
        # Business size score (placeholder - would need more data)
        business_size_score = 50  # Default middle score
        
        return {
            "ad_activity": ad_activity_score,
            "intent": intent_score,
            "leak": leak_score,
            "reactivation": reactivation_score,
            "contact_quality": contact_quality_score,
            "business_size": business_size_score,
        }
    
    def _compute_final_score(
        self,
        breakdown: Dict[str, int],
        weights: Dict[str, float],
    ) -> int:
        """
        Compute final weighted score.
        Requirements: 7.1
        
        Formula:
        final_score = w1×ad_activity + w2×intent + w3×leak + 
                      w4×reactivation + w5×contact_quality + w6×business_size
        """
        score = (
            weights["ad_activity"] * breakdown.get("ad_activity", 0) +
            weights["intent"] * breakdown.get("intent", 0) +
            weights["leak"] * breakdown.get("leak", 0) +
            weights["reactivation"] * breakdown.get("reactivation", 0) +
            weights["contact_quality"] * breakdown.get("contact_quality", 0) +
            weights["business_size"] * breakdown.get("business_size", 0)
        )
        
        return int(min(max(score, 0), 100))
    
    def _assign_tier(self, final_score: int) -> str:
        """
        Assign lead tier based on score.
        Requirements: 7.5
        
        - A (Pitch now): score >= 80
        - B (Soft pitch): score >= 60
        - C (Skip): score < 60
        """
        if final_score >= self.TIER_A_THRESHOLD:
            return "A"
        elif final_score >= self.TIER_B_THRESHOLD:
            return "B"
        else:
            return "C"
    
    def _check_disqualification(
        self,
        lead: Dict[str, Any],
        enrichment: Dict[str, Any],
        intent: Dict[str, Any],
    ) -> tuple[bool, Optional[str]]:
        """
        Check disqualification rules.
        Requirements: 7.3, 7.4
        
        UPDATED: Removed "no_ads_history" rule - most local businesses
        don't run Google Ads but are still valid prospects.
        """
        # Rule: too_small (owner-only)
        # Would need employee count data - skip for now
        
        # REMOVED: no_ads_history rule
        # Most local businesses don't run Google Ads but are still valid prospects
        # The scoring system will naturally rank them lower if they have no ads
        
        # Rule: emergency_only
        category = lead.get("category")
        if category:
            emergency_keywords = ["emergency", "24/7 emergency", "urgent care"]
            if any(kw in category.lower() for kw in emergency_keywords):
                # Only disqualify if it's ONLY emergency services
                if "only" in category.lower() or category.lower().startswith("emergency"):
                    return True, "Emergency-only service"
        
        # Rule: no_contact_path
        has_phone = bool(lead.get("phone"))
        has_email = bool(lead.get("emails_found"))
        has_website = bool(lead.get("website") or lead.get("landing_page_url"))
        has_validated_email = bool(enrichment and enrichment.get("validated_emails"))
        
        # Need at least one contact method
        if not has_phone and not has_email and not has_website and not has_validated_email:
            return True, "No valid contact method"
        
        # Rule: toxic_reviews (would need review sentiment data)
        # Placeholder - would check review_sentiment_avg < -0.5
        
        return False, None
    
    def _save_scoring(self, scoring: Dict[str, Any]) -> None:
        """Save scoring result to database."""
        data = dict(scoring)
        data["lead_id"] = str(scoring.get("lead_id", ""))
        data["created_at"] = datetime.utcnow().isoformat()
        
        # Tier is already a string
        # score_breakdown is already a dict
        
        self._db.save_scoring_result(data)


# Create singleton instance for LangGraph node
_scoring_agent = ScoringAgent()


def scoring_node(state: LeadGraphState) -> LeadGraphState:
    """LangGraph node function for scoring."""
    return _scoring_agent(state)
