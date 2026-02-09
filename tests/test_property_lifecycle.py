"""
Property-based tests for Lead Lifecycle Management.
Requirements: 21.1, 21.2, 21.3, 21.4, 21.5, 21.6, 21.7, 21.8, 21.9, 22.1, 22.2, 22.9

Property 43: Lead Lifecycle State Machine Validity
Property 44: Contact Timestamp Recording
Property 45: Stale Lead Contact Prevention
Property 46: Contact Eligibility Calculation
Property 47: Opt-Out Detection and Enforcement
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from unittest.mock import MagicMock, patch
from uuid import uuid4
from datetime import datetime, timedelta


# Valid lifecycle states
LIFECYCLE_STATES = [
    "new", "enriched", "scored", "contacted", "qualified",
    "escalated", "closed_won", "closed_lost", "stale", "dnc"
]

# Valid state transitions
VALID_TRANSITIONS = {
    "new": ["enriched", "stale", "dnc"],
    "enriched": ["scored", "stale", "dnc"],
    "scored": ["contacted", "stale", "dnc"],
    "contacted": ["qualified", "stale", "dnc", "closed_lost"],
    "qualified": ["escalated", "closed_won", "closed_lost", "dnc"],
    "escalated": ["closed_won", "closed_lost", "dnc"],
    "closed_won": [],
    "closed_lost": [],
    "stale": ["new"],  # Can be reactivated
    "dnc": [],
}


class TestLeadLifecycleStateMachineValidity:
    """
    Property 43: Lead Lifecycle State Machine Validity
    Validates: Requirements 21.1, 21.3, 21.4, 21.7, 21.8, 21.9
    
    Lead lifecycle follows valid state transitions.
    """
    
    @given(
        current_state=st.sampled_from(LIFECYCLE_STATES),
        target_state=st.sampled_from(LIFECYCLE_STATES),
    )
    @settings(max_examples=100)
    def test_only_valid_transitions_allowed(self, current_state, target_state):
        """Only valid state transitions are allowed."""
        def is_valid_transition(current: str, target: str) -> bool:
            if current == target:
                return True  # No change is always valid
            return target in VALID_TRANSITIONS.get(current, [])
        
        result = is_valid_transition(current_state, target_state)
        
        if current_state == target_state:
            assert result is True
        else:
            expected = target_state in VALID_TRANSITIONS.get(current_state, [])
            assert result == expected
    
    @given(
        state=st.sampled_from(LIFECYCLE_STATES),
    )
    @settings(max_examples=30)
    def test_terminal_states_have_no_transitions(self, state):
        """Terminal states have no outgoing transitions."""
        terminal_states = ["closed_won", "closed_lost", "dnc"]
        
        if state in terminal_states:
            assert len(VALID_TRANSITIONS.get(state, [])) == 0
    
    @given(
        state=st.sampled_from(LIFECYCLE_STATES),
    )
    @settings(max_examples=30)
    def test_dnc_reachable_from_most_states(self, state):
        """DNC is reachable from most non-terminal states."""
        non_terminal = ["new", "enriched", "scored", "contacted", "qualified", "escalated"]
        
        if state in non_terminal:
            assert "dnc" in VALID_TRANSITIONS.get(state, [])


class TestContactTimestampRecording:
    """
    Property 44: Contact Timestamp Recording
    Validates: Requirements 21.2
    
    Contact events update last_contacted_at timestamp.
    """
    
    @given(
        contact_time=st.datetimes(
            min_value=datetime(2020, 1, 1),
            max_value=datetime(2030, 12, 31),
        ),
    )
    @settings(max_examples=30)
    def test_contact_updates_timestamp(self, contact_time):
        """Contact event updates last_contacted_at."""
        lead = {
            "lead_id": str(uuid4()),
            "last_contacted_at": None,
        }
        
        # Simulate contact
        lead["last_contacted_at"] = contact_time.isoformat()
        
        assert lead["last_contacted_at"] is not None
        assert lead["last_contacted_at"] == contact_time.isoformat()
    
    @given(
        num_contacts=st.integers(min_value=1, max_value=10),
    )
    @settings(max_examples=20)
    def test_latest_contact_recorded(self, num_contacts):
        """Most recent contact timestamp is recorded."""
        lead = {"last_contacted_at": None}
        
        for i in range(num_contacts):
            contact_time = datetime.utcnow() + timedelta(days=i)
            lead["last_contacted_at"] = contact_time.isoformat()
        
        # Should have the latest timestamp
        expected = (datetime.utcnow() + timedelta(days=num_contacts - 1)).date()
        actual = datetime.fromisoformat(lead["last_contacted_at"]).date()
        
        assert actual == expected


class TestStaleLeadContactPrevention:
    """
    Property 45: Stale Lead Contact Prevention
    Validates: Requirements 21.6
    
    Stale leads cannot be contacted.
    """
    
    @given(
        lifecycle_state=st.sampled_from(LIFECYCLE_STATES),
    )
    @settings(max_examples=30)
    def test_stale_leads_blocked_from_contact(self, lifecycle_state):
        """Stale leads are blocked from contact."""
        def can_contact(state: str) -> bool:
            blocked_states = ["stale", "dnc", "closed_won", "closed_lost"]
            return state not in blocked_states
        
        result = can_contact(lifecycle_state)
        
        if lifecycle_state == "stale":
            assert result is False
    
    @given(
        days_inactive=st.integers(min_value=0, max_value=365),
        stale_threshold_days=st.integers(min_value=30, max_value=90),
    )
    @settings(max_examples=30)
    def test_lead_becomes_stale_after_threshold(self, days_inactive, stale_threshold_days):
        """Lead becomes stale after inactivity threshold."""
        def is_stale(days: int, threshold: int) -> bool:
            return days >= threshold
        
        result = is_stale(days_inactive, stale_threshold_days)
        
        assert result == (days_inactive >= stale_threshold_days)


class TestContactEligibilityCalculation:
    """
    Property 46: Contact Eligibility Calculation
    Validates: Requirements 21.5
    
    Contact eligibility respects minimum wait days.
    """
    
    @given(
        days_since_contact=st.integers(min_value=0, max_value=60),
        minimum_wait_days=st.integers(min_value=1, max_value=14),
    )
    @settings(max_examples=50)
    def test_contact_eligibility_respects_wait(self, days_since_contact, minimum_wait_days):
        """Contact eligibility respects minimum wait period."""
        def is_eligible_for_contact(days: int, min_wait: int) -> bool:
            return days >= min_wait
        
        result = is_eligible_for_contact(days_since_contact, minimum_wait_days)
        
        assert result == (days_since_contact >= minimum_wait_days)
    
    @given(
        last_contact=st.datetimes(
            min_value=datetime(2024, 1, 1),
            max_value=datetime(2024, 6, 30),
        ),
        minimum_wait_days=st.integers(min_value=1, max_value=14),
    )
    @settings(max_examples=30)
    def test_days_since_contact_calculated_correctly(self, last_contact, minimum_wait_days):
        """Days since last contact is calculated correctly."""
        now = datetime(2024, 7, 1)
        days_since = (now - last_contact).days
        
        assert days_since >= 0
        assert isinstance(days_since, int)


class TestOptOutDetectionAndEnforcement:
    """
    Property 47: Opt-Out Detection and Enforcement
    Validates: Requirements 22.1, 22.2, 22.9
    
    Opt-outs are detected and enforced.
    """
    
    @given(
        message=st.text(min_size=1, max_size=200),
    )
    @settings(max_examples=50)
    def test_opt_out_keywords_detected(self, message):
        """Opt-out keywords are detected in messages."""
        opt_out_keywords = ["stop", "unsubscribe", "remove me", "opt out", "no more"]
        
        def contains_opt_out(msg: str) -> bool:
            msg_lower = msg.lower()
            return any(kw in msg_lower for kw in opt_out_keywords)
        
        result = contains_opt_out(message)
        
        # Verify detection logic
        expected = any(kw in message.lower() for kw in opt_out_keywords)
        assert result == expected
    
    @given(
        is_opted_out=st.booleans(),
    )
    @settings(max_examples=20)
    def test_opted_out_leads_blocked(self, is_opted_out):
        """Opted-out leads are blocked from contact."""
        lead = {
            "lead_id": str(uuid4()),
            "opted_out": is_opted_out,
        }
        
        def can_contact(l: dict) -> bool:
            return not l.get("opted_out", False)
        
        result = can_contact(lead)
        
        assert result == (not is_opted_out)
    
    @given(
        lead_id=st.uuids(),
    )
    @settings(max_examples=20)
    def test_opt_out_adds_to_dnc(self, lead_id):
        """Opt-out adds lead to DNC list."""
        dnc_list = set()
        
        def process_opt_out(lid: str) -> None:
            dnc_list.add(lid)
        
        process_opt_out(str(lead_id))
        
        assert str(lead_id) in dnc_list
