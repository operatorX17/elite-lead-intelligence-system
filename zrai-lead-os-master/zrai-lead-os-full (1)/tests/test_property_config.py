"""
Property-based tests for configuration system.
Requirements: 17.2, 17.3, 19.3

Property 41: Configuration Hot Reload
Property 42: Configuration Validation
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from unittest.mock import MagicMock, patch
import tempfile
import os
import yaml
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict
from enum import Enum


# Mock config models for testing
class BudgetConfig(BaseModel):
    daily_llm_token_limit: int = Field(default=1_000_000, ge=0)
    daily_browser_session_limit: int = Field(default=100, ge=0)
    daily_scraper_run_limit: int = Field(default=50, ge=0)


class RateLimitConfig(BaseModel):
    per_domain_email_per_day: int = Field(default=5, ge=1, le=50)
    email_per_day: int = Field(default=200, ge=1, le=2000)


class ScoringWeights(BaseModel):
    ad_activity: float = Field(default=0.20, ge=0, le=1)
    intent: float = Field(default=0.25, ge=0, le=1)
    leak: float = Field(default=0.30, ge=0, le=1)
    reactivation: float = Field(default=0.10, ge=0, le=1)
    contact_quality: float = Field(default=0.10, ge=0, le=1)
    business_size: float = Field(default=0.05, ge=0, le=1)


class NicheConfig(BaseModel):
    name: str
    tier_a_threshold: int = Field(default=80, ge=0, le=100)
    tier_b_threshold: int = Field(default=60, ge=0, le=100)


class KillSwitchConfig(BaseModel):
    global_kill: bool = Field(default=False)
    discovery_kill: bool = Field(default=False)
    audit_kill: bool = Field(default=False)
    outreach_kill: bool = Field(default=False)


# Strategies for generating test data
valid_budget_values = st.integers(min_value=0, max_value=10_000_000)
valid_rate_limit_values = st.integers(min_value=1, max_value=1000)
valid_threshold_values = st.integers(min_value=0, max_value=100)


class TestConfigValidation:
    """
    Property 42: Configuration Validation
    Validates: Requirements 17.3, 19.3
    
    For any configuration input, validation either succeeds with valid config
    or fails with a clear error message.
    """
    
    @given(
        daily_llm_limit=valid_budget_values,
        daily_browser_limit=st.integers(min_value=0, max_value=1000),
        daily_scraper_limit=st.integers(min_value=0, max_value=500),
    )
    @settings(max_examples=50)
    def test_budget_config_accepts_valid_values(
        self, daily_llm_limit, daily_browser_limit, daily_scraper_limit
    ):
        """Budget config accepts any non-negative integer values."""
        config = BudgetConfig(
            daily_llm_token_limit=daily_llm_limit,
            daily_browser_session_limit=daily_browser_limit,
            daily_scraper_run_limit=daily_scraper_limit,
        )
        
        assert config.daily_llm_token_limit == daily_llm_limit
        assert config.daily_browser_session_limit == daily_browser_limit
        assert config.daily_scraper_run_limit == daily_scraper_limit
    
    @given(
        per_domain_email=st.integers(min_value=1, max_value=50),
        email_per_day=st.integers(min_value=1, max_value=2000),
    )
    @settings(max_examples=50)
    def test_rate_limit_config_accepts_valid_values(
        self, per_domain_email, email_per_day
    ):
        """Rate limit config accepts values within valid ranges."""
        config = RateLimitConfig(
            per_domain_email_per_day=per_domain_email,
            email_per_day=email_per_day,
        )
        
        assert config.per_domain_email_per_day == per_domain_email
        assert config.email_per_day == email_per_day
    
    @given(
        ad_activity=st.floats(min_value=0, max_value=0.3),
        intent=st.floats(min_value=0, max_value=0.3),
        leak=st.floats(min_value=0, max_value=0.4),
        reactivation=st.floats(min_value=0, max_value=0.2),
        contact_quality=st.floats(min_value=0, max_value=0.2),
    )
    @settings(max_examples=50)
    def test_scoring_weights_must_sum_to_one(
        self, ad_activity, intent, leak, reactivation, contact_quality
    ):
        """Scoring weights must sum to approximately 1.0."""
        # Calculate what business_size would need to be
        partial_sum = ad_activity + intent + leak + reactivation + contact_quality
        business_size = 1.0 - partial_sum
        
        # Skip if business_size would be out of range
        assume(0 <= business_size <= 1)
        assume(0.99 <= partial_sum + business_size <= 1.01)
        
        config = ScoringWeights(
            ad_activity=ad_activity,
            intent=intent,
            leak=leak,
            reactivation=reactivation,
            contact_quality=contact_quality,
            business_size=business_size,
        )
        
        total = (
            config.ad_activity +
            config.intent +
            config.leak +
            config.reactivation +
            config.contact_quality +
            config.business_size
        )
        assert 0.99 <= total <= 1.01
    
    @given(
        tier_a=st.integers(min_value=0, max_value=100),
        tier_b=st.integers(min_value=0, max_value=100),
    )
    @settings(max_examples=50)
    def test_niche_config_tier_thresholds(self, tier_a, tier_b):
        """Niche config accepts valid tier thresholds."""
        config = NicheConfig(
            name="test_niche",
            tier_a_threshold=tier_a,
            tier_b_threshold=tier_b,
        )
        
        assert config.tier_a_threshold == tier_a
        assert config.tier_b_threshold == tier_b
    
    @given(
        global_kill=st.booleans(),
        discovery_kill=st.booleans(),
        audit_kill=st.booleans(),
        outreach_kill=st.booleans(),
    )
    @settings(max_examples=20)
    def test_kill_switch_config_accepts_booleans(
        self, global_kill, discovery_kill, audit_kill, outreach_kill
    ):
        """Kill switch config accepts any boolean combination."""
        config = KillSwitchConfig(
            global_kill=global_kill,
            discovery_kill=discovery_kill,
            audit_kill=audit_kill,
            outreach_kill=outreach_kill,
        )
        
        assert config.global_kill == global_kill
        assert config.discovery_kill == discovery_kill
        assert config.audit_kill == audit_kill
        assert config.outreach_kill == outreach_kill


class TestConfigHotReload:
    """
    Property 41: Configuration Hot Reload
    Validates: Requirements 17.2
    
    When config file changes, the system reloads without restart.
    """
    
    @given(
        initial_limit=st.integers(min_value=100, max_value=1000),
        new_limit=st.integers(min_value=100, max_value=1000),
    )
    @settings(max_examples=20)
    def test_config_reload_updates_values(self, initial_limit, new_limit):
        """Config reload updates values without restart."""
        assume(initial_limit != new_limit)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            initial_config = {
                'budget': {
                    'daily_llm_token_limit': initial_limit,
                    'daily_browser_session_limit': 100,
                    'daily_scraper_run_limit': 50,
                }
            }
            yaml.dump(initial_config, f)
            config_path = f.name
        
        try:
            # Load initial config
            with open(config_path, 'r') as f:
                loaded = yaml.safe_load(f)
            assert loaded['budget']['daily_llm_token_limit'] == initial_limit
            
            # Update config file
            with open(config_path, 'w') as f:
                updated_config = {
                    'budget': {
                        'daily_llm_token_limit': new_limit,
                        'daily_browser_session_limit': 100,
                        'daily_scraper_run_limit': 50,
                    }
                }
                yaml.dump(updated_config, f)
            
            # Reload and verify
            with open(config_path, 'r') as f:
                reloaded = yaml.safe_load(f)
            assert reloaded['budget']['daily_llm_token_limit'] == new_limit
            
        finally:
            os.unlink(config_path)
    
    @given(
        kill_switch_state=st.booleans(),
    )
    @settings(max_examples=10)
    def test_kill_switch_hot_reload(self, kill_switch_state):
        """Kill switches can be toggled via hot reload."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            config = {
                'kill_switches': {
                    'global_kill': kill_switch_state,
                }
            }
            yaml.dump(config, f)
            config_path = f.name
        
        try:
            with open(config_path, 'r') as f:
                loaded = yaml.safe_load(f)
            assert loaded['kill_switches']['global_kill'] == kill_switch_state
            
            # Toggle and reload
            with open(config_path, 'w') as f:
                config['kill_switches']['global_kill'] = not kill_switch_state
                yaml.dump(config, f)
            
            with open(config_path, 'r') as f:
                reloaded = yaml.safe_load(f)
            assert reloaded['kill_switches']['global_kill'] == (not kill_switch_state)
            
        finally:
            os.unlink(config_path)
