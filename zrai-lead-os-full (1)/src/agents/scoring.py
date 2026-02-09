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
    
    # Default weights (Requirement 7.2)
    DEFAULT_WEIGHTS = {
        "ad_activity": 0.20,
        "intent": 0.25,
        "leak": 0.30,
        "reactivation": 0.10,
        "contact_quality": 0.10,
        "business_size": 0.05,
    }
    
    # Tier thresholds
    TIER_A_THRESHOLD = 80
    TIER_B_THRESHOLD = 60
    
    def __init__(self):
        super().__init__("scoring")
    
    def process(self, state: LeadGraphState) -> LeadGraphState:
        """Process scoring for a lead."""
        if not state.lead:
            self._logger.warning("No lead data for scoring")
            return state
        
        state.current_stage = "scoring"
        
        lead = state.lead
        enrichment = state.enrichment
        intent = state.intent
        
        # Check disqualification rules first
        disqualified, reason = self._check_disqualification(lead, enrichment, intent)
        
        if disqualified:
            scoring = ScoringResult(
                lead_id=lead.lead_id,
                final_score=0,
                score_breakdown=ScoreBreakdown(),
                lead_tier=LeadTier.C,
                do_not_contact=True,
                do_not_contact_reason=reason,
            )
            state.scoring = scoring
            state.is_disqualified = True
            state.should_skip_outreach = True
            
            self._save_scoring(scoring)
            return state
        
        # Get weights (per-niche if available)
        weights = self._get_weights(lead.category)
        
        # Compute component scores
        breakdown = self._compute_score_breakdown(lead, enrichment, intent)
        
        # Compute final weighted score
        final_score = self._compute_final_score(breakdown, weights)
        
        # Assign tier
        tier = self._assign_tier(final_score)
        
        # Create scoring result
        scoring = ScoringResult(
            lead_id=lead.lead_id,
            final_score=final_score,
            score_breakdown=breakdown,
            lead_tier=tier,
            do_not_contact=False,
            do_not_contact_reason=None,
        )
        
        state.scoring = scoring
        
        # Set skip flag for tier C (Requirement 7.6)
        if tier == LeadTier.C:
            state.should_skip_outreach = True
        
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
        lead,
        enrichment,
        intent,
    ) -> ScoreBreakdown:
        """Compute individual score components."""
        # Ad activity score (0-100)
        ad_activity_score = 0
        if lead.ads_active:
            ad_activity_score += 50
        if lead.ad_start_date:
            days_active = (datetime.utcnow() - lead.ad_start_date).days
            if days_active < 30:
                ad_activity_score += 30
            elif days_active < 90:
                ad_activity_score += 20
            else:
                ad_activity_score += 10
        if lead.ad_last_seen:
            days_since = (datetime.utcnow() - lead.ad_last_seen).days
            if days_since < 7:
                ad_activity_score += 20
        ad_activity_score = min(ad_activity_score, 100)
        
        # Intent score (from intent agent)
        intent_score = intent.intent_score if intent else 0
        
        # Leak score (from intent agent)
        leak_score = intent.leak_score if intent else 0
        
        # Reactivation score (from intent agent)
        reactivation_score = intent.reactivation_fit if intent else 0
        
        # Contact quality score (from enrichment)
        contact_quality_score = enrichment.contact_quality_score if enrichment else 0
        
        # Business size score (placeholder - would need more data)
        business_size_score = 50  # Default middle score
        
        return ScoreBreakdown(
            ad_activity=ad_activity_score,
            intent=intent_score,
            leak=leak_score,
            reactivation=reactivation_score,
            contact_quality=contact_quality_score,
            business_size=business_size_score,
        )
    
    def _compute_final_score(
        self,
        breakdown: ScoreBreakdown,
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
            weights["ad_activity"] * breakdown.ad_activity +
            weights["intent"] * breakdown.intent +
            weights["leak"] * breakdown.leak +
            weights["reactivation"] * breakdown.reactivation +
            weights["contact_quality"] * breakdown.contact_quality +
            weights["business_size"] * breakdown.business_size
        )
        
        return int(min(max(score, 0), 100))
    
    def _assign_tier(self, final_score: int) -> LeadTier:
        """
        Assign lead tier based on score.
        Requirements: 7.5
        
        - A (Pitch now): score >= 80
        - B (Soft pitch): score >= 60
        - C (Skip): score < 60
        """
        if final_score >= self.TIER_A_THRESHOLD:
            return LeadTier.A
        elif final_score >= self.TIER_B_THRESHOLD:
            return LeadTier.B
        else:
            return LeadTier.C
    
    def _check_disqualification(
        self,
        lead,
        enrichment,
        intent,
    ) -> tuple[bool, Optional[str]]:
        """
        Check disqualification rules.
        Requirements: 7.3, 7.4
        """
        # Rule: too_small (owner-only)
        # Would need employee count data
        
        # Rule: no_ads_history
        if not lead.ads_active and not lead.ad_start_date:
            return True, "No advertising spend detected"
        
        # Rule: emergency_only
        if lead.category:
            emergency_keywords = ["emergency", "24/7 emergency", "urgent"]
            if any(kw in lead.category.lower() for kw in emergency_keywords):
                return True, "Emergency-only service"
        
        # Rule: no_contact_path
        has_phone = bool(lead.phone)
        has_email = bool(lead.emails_found)
        has_validated_email = bool(enrichment and enrichment.validated_emails)
        
        if not has_phone and not has_email and not has_validated_email:
            return True, "No valid contact method"
        
        # Rule: toxic_reviews (would need review sentiment data)
        # Placeholder - would check review_sentiment_avg < -0.5
        
        return False, None
    
    def _save_scoring(self, scoring: ScoringResult) -> None:
        """Save scoring result to database."""
        data = scoring.model_dump()
        data["lead_id"] = str(scoring.lead_id)
        data["created_at"] = datetime.utcnow().isoformat()
        
        # Convert tier enum
        data["lead_tier"] = scoring.lead_tier.value if hasattr(scoring.lead_tier, 'value') else scoring.lead_tier
        
        # Convert score breakdown to dict
        data["score_breakdown"] = {
            "ad_activity": scoring.score_breakdown.ad_activity,
            "intent": scoring.score_breakdown.intent,
            "leak": scoring.score_breakdown.leak,
            "reactivation": scoring.score_breakdown.reactivation,
            "contact_quality": scoring.score_breakdown.contact_quality,
            "business_size": scoring.score_breakdown.business_size,
        }
        
        self._db.save_scoring_result(data)


# Create singleton instance for LangGraph node
_scoring_agent = ScoringAgent()


def scoring_node(state: LeadGraphState) -> LeadGraphState:
    """LangGraph node function for scoring."""
    return _scoring_agent(state)
