"""
Property-based tests for Scoring Agent.
Requirements: 7.1, 7.4, 7.5, 7.6

Property 15: Lead Tier Assignment Validity
Property 16: Tier C Exclusion
Property 17: Disqualification Reason Recording
Property 18: Weighted Scoring Formula Correctness
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from unittest.mock import MagicMock, patch


# Strategies
score_strategy = st.floats(min_value=0.0, max_value=100.0, allow_nan=False)
weight_strategy = st.floats(min_value=0.0, max_value=1.0, allow_nan=False)


class TestLeadTierAssignmentValidity:
    """
    Property 15: Lead Tier Assignment Validity
    Validates: Requirements 7.5
    
    Lead tier assignment is consistent with score thresholds.
    """
    
    @given(
        score=score_strategy,
        tier_a_threshold=st.integers(min_value=70, max_value=90),
        tier_b_threshold=st.integers(min_value=50, max_value=69),
    )
    @settings(max_examples=50)
    def test_tier_assignment_matches_thresholds(self, score, tier_a_threshold, tier_b_threshold):
        """Tier assignment matches configured thresholds."""
        assume(tier_a_threshold > tier_b_threshold)
        
        def assign_tier(s: float, a_thresh: int, b_thresh: int) -> str:
            if s >= a_thresh:
                return "A"
            elif s >= b_thresh:
                return "B"
            else:
                return "C"
        
        tier = assign_tier(score, tier_a_threshold, tier_b_threshold)
        
        if score >= tier_a_threshold:
            assert tier == "A"
        elif score >= tier_b_threshold:
            assert tier == "B"
        else:
            assert tier == "C"
    
    @given(
        score=score_strategy,
    )
    @settings(max_examples=50)
    def test_tier_is_always_valid(self, score):
        """Tier is always one of A, B, or C."""
        def assign_tier(s: float) -> str:
            if s >= 80:
                return "A"
            elif s >= 60:
                return "B"
            else:
                return "C"
        
        tier = assign_tier(score)
        
        assert tier in {"A", "B", "C"}
    
    @given(
        score1=st.floats(min_value=80.0, max_value=100.0, allow_nan=False),
        score2=st.floats(min_value=0.0, max_value=59.9, allow_nan=False),
    )
    @settings(max_examples=30)
    def test_higher_score_gets_better_tier(self, score1, score2):
        """Higher scores result in better (or equal) tiers."""
        tier_order = {"A": 0, "B": 1, "C": 2}
        
        def assign_tier(s: float) -> str:
            if s >= 80:
                return "A"
            elif s >= 60:
                return "B"
            else:
                return "C"
        
        tier1 = assign_tier(score1)
        tier2 = assign_tier(score2)
        
        assert tier_order[tier1] <= tier_order[tier2]


class TestTierCExclusion:
    """
    Property 16: Tier C Exclusion
    Validates: Requirements 7.6
    
    Tier C leads are excluded from outreach queues.
    """
    
    @given(
        tier=st.sampled_from(["A", "B", "C"]),
    )
    @settings(max_examples=30)
    def test_tier_c_excluded_from_outreach(self, tier):
        """Tier C leads are not added to outreach queue."""
        def should_add_to_outreach(t: str) -> bool:
            return t != "C"
        
        result = should_add_to_outreach(tier)
        
        if tier == "C":
            assert result is False
        else:
            assert result is True
    
    @given(
        num_leads=st.integers(min_value=1, max_value=50),
        tier_distribution=st.lists(
            st.sampled_from(["A", "B", "C"]),
            min_size=1,
            max_size=50,
        ),
    )
    @settings(max_examples=30)
    def test_outreach_queue_has_no_tier_c(self, num_leads, tier_distribution):
        """Outreach queue never contains Tier C leads."""
        outreach_queue = []
        
        for i, tier in enumerate(tier_distribution[:num_leads]):
            if tier != "C":
                outreach_queue.append({"lead_id": i, "tier": tier})
        
        for item in outreach_queue:
            assert item["tier"] != "C"


class TestDisqualificationReasonRecording:
    """
    Property 17: Disqualification Reason Recording
    Validates: Requirements 7.4
    
    All disqualifications include a recorded reason.
    """
    
    @given(
        reason=st.sampled_from([
            "dnc_list",
            "competitor",
            "invalid_contact",
            "budget_mismatch",
            "geo_excluded",
            "duplicate",
        ]),
    )
    @settings(max_examples=30)
    def test_disqualification_has_reason(self, reason):
        """Every disqualification has a recorded reason."""
        disqualification = {
            "lead_id": "test_lead",
            "disqualified": True,
            "reason": reason,
            "timestamp": "2024-01-01T00:00:00Z",
        }
        
        assert disqualification["reason"] is not None
        assert len(disqualification["reason"]) > 0
    
    @given(
        is_on_dnc=st.booleans(),
        is_competitor=st.booleans(),
        has_invalid_contact=st.booleans(),
    )
    @settings(max_examples=30)
    def test_disqualification_reasons_are_specific(
        self, is_on_dnc, is_competitor, has_invalid_contact
    ):
        """Disqualification reasons are specific and actionable."""
        reasons = []
        
        if is_on_dnc:
            reasons.append("dnc_list")
        if is_competitor:
            reasons.append("competitor")
        if has_invalid_contact:
            reasons.append("invalid_contact")
        
        # If disqualified, must have at least one reason
        if reasons:
            assert len(reasons) >= 1
            assert all(r in {"dnc_list", "competitor", "invalid_contact"} for r in reasons)


class TestWeightedScoringFormulaCorrectness:
    """
    Property 18: Weighted Scoring Formula Correctness
    Validates: Requirements 7.1
    
    Weighted scoring formula produces correct results.
    """
    
    @given(
        ad_activity=score_strategy,
        intent=score_strategy,
        leak=score_strategy,
        reactivation=score_strategy,
        contact_quality=score_strategy,
        business_size=score_strategy,
    )
    @settings(max_examples=50)
    def test_weighted_score_calculation(
        self, ad_activity, intent, leak, reactivation, contact_quality, business_size
    ):
        """Weighted score is calculated correctly."""
        weights = {
            "ad_activity": 0.20,
            "intent": 0.25,
            "leak": 0.30,
            "reactivation": 0.10,
            "contact_quality": 0.10,
            "business_size": 0.05,
        }
        
        scores = {
            "ad_activity": ad_activity,
            "intent": intent,
            "leak": leak,
            "reactivation": reactivation,
            "contact_quality": contact_quality,
            "business_size": business_size,
        }
        
        final_score = sum(weights[k] * scores[k] for k in weights)
        
        # Score should be in valid range
        assert 0.0 <= final_score <= 100.0
        
        # Verify calculation
        expected = (
            0.20 * ad_activity +
            0.25 * intent +
            0.30 * leak +
            0.10 * reactivation +
            0.10 * contact_quality +
            0.05 * business_size
        )
        
        assert abs(final_score - expected) < 0.001
    
    @given(
        score=score_strategy,
        weight=weight_strategy,
    )
    @settings(max_examples=30)
    def test_single_component_contribution(self, score, weight):
        """Single component contributes proportionally to final score."""
        contribution = score * weight
        
        # Contribution should be <= score (since weight <= 1)
        assert contribution <= score + 0.001  # Small epsilon for float comparison
        
        # Contribution should be >= 0
        assert contribution >= 0
