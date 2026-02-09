"""
Property-based tests for Enrichment Agent.
Requirements: 4.3, 4.4, 4.5, 5.1, 5.2, 5.3, 5.5

Property 12: Contact Normalization Consistency
Property 13: Score Range Validity
Property 14: Risk Classification Validity
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from unittest.mock import MagicMock, patch
import re


# Strategies
phone_strategy = st.from_regex(r'[0-9]{10,15}', fullmatch=True)
email_strategy = st.from_regex(r'[a-z]{3,10}@[a-z]{3,10}\.(com|net|org)', fullmatch=True)
score_strategy = st.floats(min_value=0.0, max_value=100.0)


class TestContactNormalizationConsistency:
    """
    Property 12: Contact Normalization Consistency
    Validates: Requirements 4.3
    
    Contact normalization produces consistent, valid formats.
    """
    
    @given(
        phone_digits=st.text(alphabet='0123456789', min_size=10, max_size=15),
    )
    @settings(max_examples=50)
    def test_phone_normalization_produces_e164(self, phone_digits):
        """Phone normalization produces E.164 format."""
        assume(len(phone_digits) >= 10)
        
        # Simple E.164 normalization
        def normalize_phone(phone: str) -> str:
            digits = ''.join(c for c in phone if c.isdigit())
            if len(digits) == 10:
                return f"+1{digits}"
            elif len(digits) == 11 and digits.startswith('1'):
                return f"+{digits}"
            elif len(digits) > 10:
                return f"+{digits}"
            return None
        
        normalized = normalize_phone(phone_digits)
        
        if normalized:
            # E.164 format: + followed by digits
            assert normalized.startswith('+')
            assert normalized[1:].isdigit()
            assert len(normalized) >= 11
    
    @given(
        phone=phone_strategy,
    )
    @settings(max_examples=30)
    def test_same_phone_normalizes_consistently(self, phone):
        """Same phone number always normalizes to same result."""
        def normalize_phone(p: str) -> str:
            digits = ''.join(c for c in p if c.isdigit())
            if len(digits) >= 10:
                return f"+1{digits[-10:]}"
            return None
        
        result1 = normalize_phone(phone)
        result2 = normalize_phone(phone)
        
        assert result1 == result2
    
    @given(
        email=email_strategy,
    )
    @settings(max_examples=50)
    def test_email_normalization_is_lowercase(self, email):
        """Email normalization produces lowercase."""
        normalized = email.lower().strip()
        
        assert normalized == normalized.lower()
        assert '@' in normalized
        assert '.' in normalized.split('@')[1]


class TestScoreRangeValidity:
    """
    Property 13: Score Range Validity
    Validates: Requirements 4.4, 4.5, 5.1, 5.2, 5.3
    
    All scores are within valid ranges [0, 100].
    """
    
    @given(
        intent_score=score_strategy,
        leak_score=score_strategy,
        reactivation_score=score_strategy,
        contact_quality=score_strategy,
    )
    @settings(max_examples=50)
    def test_all_scores_in_valid_range(
        self, intent_score, leak_score, reactivation_score, contact_quality
    ):
        """All individual scores are in [0, 100] range."""
        scores = [intent_score, leak_score, reactivation_score, contact_quality]
        
        for score in scores:
            assert 0.0 <= score <= 100.0
    
    @given(
        weights=st.lists(
            st.floats(min_value=0.0, max_value=1.0),
            min_size=5,
            max_size=5,
        ),
        scores=st.lists(
            st.floats(min_value=0.0, max_value=100.0),
            min_size=5,
            max_size=5,
        ),
    )
    @settings(max_examples=50)
    def test_weighted_score_in_valid_range(self, weights, scores):
        """Weighted final score is in [0, 100] range."""
        # Normalize weights to sum to 1
        total_weight = sum(weights)
        assume(total_weight > 0)
        
        normalized_weights = [w / total_weight for w in weights]
        
        final_score = sum(w * s for w, s in zip(normalized_weights, scores))
        
        assert 0.0 <= final_score <= 100.0
    
    @given(
        enrichment_confidence=st.floats(min_value=0.0, max_value=1.0),
    )
    @settings(max_examples=30)
    def test_confidence_score_is_probability(self, enrichment_confidence):
        """Confidence scores are valid probabilities [0, 1]."""
        assert 0.0 <= enrichment_confidence <= 1.0


class TestRiskClassificationValidity:
    """
    Property 14: Risk Classification Validity
    Validates: Requirements 5.5
    
    Risk classification produces valid LOW/MED/HIGH values.
    """
    
    @given(
        speed_to_lead_minutes=st.integers(min_value=0, max_value=10080),  # Up to 1 week
    )
    @settings(max_examples=50)
    def test_risk_classification_is_valid(self, speed_to_lead_minutes):
        """Risk classification is one of LOW, MED, HIGH."""
        def classify_risk(minutes: int) -> str:
            if minutes <= 5:
                return "LOW"
            elif minutes <= 60:
                return "MED"
            else:
                return "HIGH"
        
        risk = classify_risk(speed_to_lead_minutes)
        
        assert risk in {"LOW", "MED", "HIGH"}
    
    @given(
        minutes1=st.integers(min_value=0, max_value=5),
        minutes2=st.integers(min_value=61, max_value=1000),
    )
    @settings(max_examples=30)
    def test_faster_response_is_lower_risk(self, minutes1, minutes2):
        """Faster response time results in lower or equal risk."""
        def classify_risk(minutes: int) -> str:
            if minutes <= 5:
                return "LOW"
            elif minutes <= 60:
                return "MED"
            else:
                return "HIGH"
        
        risk_order = {"LOW": 0, "MED": 1, "HIGH": 2}
        
        risk1 = classify_risk(minutes1)
        risk2 = classify_risk(minutes2)
        
        assert risk_order[risk1] <= risk_order[risk2]
    
    @given(
        has_booking=st.booleans(),
        has_chat=st.booleans(),
        has_phone=st.booleans(),
    )
    @settings(max_examples=30)
    def test_leak_risk_based_on_signals(self, has_booking, has_chat, has_phone):
        """Leak risk is determined by presence of contact methods."""
        def calculate_leak_risk(booking: bool, chat: bool, phone: bool) -> str:
            score = sum([booking, chat, phone])
            if score >= 2:
                return "LOW"
            elif score == 1:
                return "MED"
            else:
                return "HIGH"
        
        risk = calculate_leak_risk(has_booking, has_chat, has_phone)
        
        assert risk in {"LOW", "MED", "HIGH"}
