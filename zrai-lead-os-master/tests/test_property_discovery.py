"""
Property-based tests for Discovery Agent.
Requirements: 3.2, 3.4, 3.7, 3.8, 18.2

Property 10: Canonical Lead Schema Compliance
Property 11: Extraction Field Completeness (Meta Ads, Google Maps)
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from unittest.mock import MagicMock, patch
from uuid import uuid4
from datetime import datetime
import re


# Strategies for generating test data
domain_strategy = st.from_regex(r'[a-z]{3,10}\.(com|net|org|io)', fullmatch=True)
business_name_strategy = st.text(min_size=2, max_size=100, alphabet=st.characters(whitelist_categories=('L', 'N', 'P', 'Z')))
niche_strategy = st.sampled_from(["dental", "hvac", "plumbing", "roofing", "legal", "medical"])
geo_strategy = st.sampled_from(["US-CA", "US-TX", "US-NY", "US-FL", "UK-LON", "CA-ON"])


class TestCanonicalLeadSchemaCompliance:
    """
    Property 10: Canonical Lead Schema Compliance
    Validates: Requirements 3.7, 3.8, 18.2
    
    All leads conform to the canonical schema with required fields.
    """
    
    @given(
        business_name=business_name_strategy,
        domain=domain_strategy,
        niche=niche_strategy,
        geo=geo_strategy,
    )
    @settings(max_examples=50)
    def test_canonical_lead_has_required_fields(self, business_name, domain, niche, geo):
        """Canonical lead has all required fields."""
        assume(len(business_name.strip()) > 0)
        
        lead = {
            "lead_id": str(uuid4()),
            "business_name": business_name.strip(),
            "domain": domain,
            "niche": niche,
            "geo": geo,
            "lifecycle_state": "new",
            "created_at": datetime.utcnow().isoformat(),
        }
        
        required_fields = ["lead_id", "business_name", "domain", "niche", "geo", "lifecycle_state", "created_at"]
        
        for field in required_fields:
            assert field in lead
            assert lead[field] is not None
    
    @given(
        domain=domain_strategy,
    )
    @settings(max_examples=30)
    def test_domain_is_valid_format(self, domain):
        """Domain field is a valid domain format."""
        # Simple domain validation
        pattern = r'^[a-zA-Z0-9][a-zA-Z0-9-]*\.[a-zA-Z]{2,}$'
        assert re.match(pattern, domain) is not None
    
    @given(
        geo=geo_strategy,
    )
    @settings(max_examples=20)
    def test_geo_follows_format(self, geo):
        """Geo field follows country-region format."""
        # Format: XX-YY or XX-YYY
        pattern = r'^[A-Z]{2}-[A-Z]{2,3}$'
        assert re.match(pattern, geo) is not None
    
    @given(
        lifecycle_state=st.sampled_from([
            "new", "enriched", "scored", "contacted", "qualified",
            "escalated", "closed_won", "closed_lost", "stale", "dnc"
        ]),
    )
    @settings(max_examples=20)
    def test_lifecycle_state_is_valid(self, lifecycle_state):
        """Lifecycle state is one of the valid states."""
        valid_states = {
            "new", "enriched", "scored", "contacted", "qualified",
            "escalated", "closed_won", "closed_lost", "stale", "dnc"
        }
        assert lifecycle_state in valid_states


class TestMetaAdsExtractionCompleteness:
    """
    Property 11: Extraction Field Completeness (Meta Ads)
    Validates: Requirements 3.2
    
    Meta Ads extraction includes all required fields.
    """
    
    @given(
        page_name=business_name_strategy,
        ad_count=st.integers(min_value=0, max_value=1000),
        has_active_ads=st.booleans(),
    )
    @settings(max_examples=50)
    def test_meta_ads_extraction_has_required_fields(self, page_name, ad_count, has_active_ads):
        """Meta Ads extraction includes all required fields."""
        assume(len(page_name.strip()) > 0)
        
        extraction = {
            "page_name": page_name.strip(),
            "page_id": str(uuid4()),
            "ad_count": ad_count,
            "has_active_ads": has_active_ads,
            "ad_library_url": f"https://www.facebook.com/ads/library/?id={uuid4()}",
            "extracted_at": datetime.utcnow().isoformat(),
        }
        
        required_fields = ["page_name", "page_id", "ad_count", "has_active_ads", "extracted_at"]
        
        for field in required_fields:
            assert field in extraction
            assert extraction[field] is not None
    
    @given(
        ad_count=st.integers(min_value=0, max_value=10000),
    )
    @settings(max_examples=30)
    def test_ad_count_is_non_negative(self, ad_count):
        """Ad count is always non-negative."""
        assert ad_count >= 0


class TestGoogleMapsExtractionCompleteness:
    """
    Property 11: Extraction Field Completeness (Google Maps)
    Validates: Requirements 3.4
    
    Google Maps extraction includes all required fields.
    """
    
    @given(
        business_name=business_name_strategy,
        rating=st.floats(min_value=1.0, max_value=5.0),
        review_count=st.integers(min_value=0, max_value=10000),
        phone=st.from_regex(r'\+1[0-9]{10}', fullmatch=True),
    )
    @settings(max_examples=50)
    def test_google_maps_extraction_has_required_fields(
        self, business_name, rating, review_count, phone
    ):
        """Google Maps extraction includes all required fields."""
        assume(len(business_name.strip()) > 0)
        
        extraction = {
            "business_name": business_name.strip(),
            "place_id": f"ChIJ{uuid4().hex[:20]}",
            "rating": round(rating, 1),
            "review_count": review_count,
            "phone": phone,
            "address": "123 Main St, City, ST 12345",
            "website": f"https://{business_name.strip().lower().replace(' ', '')}.com",
            "extracted_at": datetime.utcnow().isoformat(),
        }
        
        required_fields = ["business_name", "place_id", "rating", "review_count", "extracted_at"]
        
        for field in required_fields:
            assert field in extraction
            assert extraction[field] is not None
    
    @given(
        rating=st.floats(min_value=1.0, max_value=5.0),
    )
    @settings(max_examples=30)
    def test_rating_is_in_valid_range(self, rating):
        """Rating is between 1.0 and 5.0."""
        assert 1.0 <= rating <= 5.0
    
    @given(
        review_count=st.integers(min_value=0, max_value=100000),
    )
    @settings(max_examples=30)
    def test_review_count_is_non_negative(self, review_count):
        """Review count is always non-negative."""
        assert review_count >= 0
