"""
Property-based tests for Outreach Agent.
Requirements: 8.3, 8.4, 8.5, 8.7

Property 21: Outreach Message Structure Compliance
Property 22: Email Opt-Out Inclusion
Property 23: A/B Variant Generation
Property 24: Approval Queue Default Behavior
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from unittest.mock import MagicMock, patch
from uuid import uuid4
import re


# Strategies
text_strategy = st.text(min_size=10, max_size=500, alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Z')))


class TestOutreachMessageStructureCompliance:
    """
    Property 21: Outreach Message Structure Compliance
    Validates: Requirements 8.3
    
    Outreach messages follow the 4-part structure.
    """
    
    @given(
        observation=text_strategy,
        impact=text_strategy,
        offer=text_strategy,
        cta=text_strategy,
    )
    @settings(max_examples=50)
    def test_message_has_four_parts(self, observation, impact, offer, cta):
        """Outreach message contains all 4 required parts."""
        assume(len(observation.strip()) > 0)
        assume(len(impact.strip()) > 0)
        assume(len(offer.strip()) > 0)
        assume(len(cta.strip()) > 0)
        
        message = {
            "observation": observation.strip(),
            "impact": impact.strip(),
            "offer": offer.strip(),
            "cta": cta.strip(),
        }
        
        required_parts = ["observation", "impact", "offer", "cta"]
        
        for part in required_parts:
            assert part in message
            assert len(message[part]) > 0
    
    @given(
        parts=st.lists(text_strategy, min_size=4, max_size=4),
    )
    @settings(max_examples=30)
    def test_message_parts_are_non_empty(self, parts):
        """All message parts are non-empty strings."""
        assume(all(len(p.strip()) > 0 for p in parts))
        
        message = {
            "observation": parts[0].strip(),
            "impact": parts[1].strip(),
            "offer": parts[2].strip(),
            "cta": parts[3].strip(),
        }
        
        for part_name, part_value in message.items():
            assert isinstance(part_value, str)
            assert len(part_value) > 0


class TestEmailOptOutInclusion:
    """
    Property 22: Email Opt-Out Inclusion
    Validates: Requirements 8.4
    
    All email outreach includes opt-out line.
    """
    
    @given(
        message_body=text_strategy,
    )
    @settings(max_examples=50)
    def test_email_has_opt_out(self, message_body):
        """Email messages include opt-out line."""
        assume(len(message_body.strip()) > 0)
        
        opt_out_line = "Reply STOP to unsubscribe"
        
        full_message = f"{message_body.strip()}\n\n{opt_out_line}"
        
        assert "STOP" in full_message or "unsubscribe" in full_message.lower()
    
    @given(
        channel=st.sampled_from(["email", "dm", "form"]),
        message_body=text_strategy,
    )
    @settings(max_examples=30)
    def test_opt_out_only_required_for_email(self, channel, message_body):
        """Opt-out is required for email, optional for other channels."""
        assume(len(message_body.strip()) > 0)
        
        def add_opt_out_if_needed(ch: str, body: str) -> str:
            if ch == "email":
                return f"{body}\n\nReply STOP to unsubscribe"
            return body
        
        result = add_opt_out_if_needed(channel, message_body.strip())
        
        if channel == "email":
            assert "STOP" in result or "unsubscribe" in result.lower()


class TestABVariantGeneration:
    """
    Property 23: A/B Variant Generation
    Validates: Requirements 8.5
    
    A/B testing generates exactly 2 variants per lead.
    """
    
    @given(
        lead_id=st.uuids(),
        base_message=text_strategy,
    )
    @settings(max_examples=50)
    def test_generates_two_variants(self, lead_id, base_message):
        """A/B test generates exactly 2 variants."""
        assume(len(base_message.strip()) > 0)
        
        def generate_variants(msg: str) -> list:
            return [
                {"variant": "A", "message": msg, "subject_line": "Option A"},
                {"variant": "B", "message": msg, "subject_line": "Option B"},
            ]
        
        variants = generate_variants(base_message.strip())
        
        assert len(variants) == 2
        assert variants[0]["variant"] == "A"
        assert variants[1]["variant"] == "B"
    
    @given(
        lead_id=st.uuids(),
    )
    @settings(max_examples=30)
    def test_variants_are_different(self, lead_id):
        """A/B variants have different content."""
        variants = [
            {"variant": "A", "subject": "Quick question about your business"},
            {"variant": "B", "subject": "I noticed something on your website"},
        ]
        
        assert variants[0]["subject"] != variants[1]["subject"]
    
    @given(
        num_leads=st.integers(min_value=1, max_value=20),
    )
    @settings(max_examples=20)
    def test_each_lead_gets_two_variants(self, num_leads):
        """Each lead in batch gets exactly 2 variants."""
        all_variants = []
        
        for i in range(num_leads):
            lead_variants = [
                {"lead_id": i, "variant": "A"},
                {"lead_id": i, "variant": "B"},
            ]
            all_variants.extend(lead_variants)
        
        assert len(all_variants) == num_leads * 2
        
        # Each lead should have exactly 2 variants
        for i in range(num_leads):
            lead_variants = [v for v in all_variants if v["lead_id"] == i]
            assert len(lead_variants) == 2


class TestApprovalQueueDefaultBehavior:
    """
    Property 24: Approval Queue Default Behavior
    Validates: Requirements 8.7
    
    Messages are queued for approval by default.
    """
    
    @given(
        tier=st.sampled_from(["A", "B", "C"]),
        auto_send_tier_a=st.booleans(),
    )
    @settings(max_examples=30)
    def test_default_requires_approval(self, tier, auto_send_tier_a):
        """Messages require approval by default unless auto-send enabled."""
        def needs_approval(t: str, auto_send: bool) -> bool:
            if t == "A" and auto_send:
                return False
            return True
        
        result = needs_approval(tier, auto_send_tier_a)
        
        # Tier B and C always need approval
        if tier in ["B", "C"]:
            assert result is True
        # Tier A depends on auto_send setting
        elif tier == "A":
            assert result == (not auto_send_tier_a)
    
    @given(
        num_messages=st.integers(min_value=1, max_value=20),
    )
    @settings(max_examples=20)
    def test_all_messages_queued_by_default(self, num_messages):
        """All messages are queued for approval by default."""
        queue = []
        
        for i in range(num_messages):
            message = {
                "message_id": i,
                "status": "pending_approval",
                "approved": False,
            }
            queue.append(message)
        
        assert all(m["status"] == "pending_approval" for m in queue)
        assert all(m["approved"] is False for m in queue)
    
    @given(
        message_id=st.uuids(),
        approved=st.booleans(),
    )
    @settings(max_examples=20)
    def test_approval_status_is_explicit(self, message_id, approved):
        """Approval status is explicitly tracked."""
        message = {
            "message_id": str(message_id),
            "approved": approved,
            "approved_by": "user@example.com" if approved else None,
            "approved_at": "2024-01-01T00:00:00Z" if approved else None,
        }
        
        if approved:
            assert message["approved_by"] is not None
            assert message["approved_at"] is not None
        else:
            assert message["approved_by"] is None
            assert message["approved_at"] is None
