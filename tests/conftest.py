"""
Pytest configuration and fixtures for ZRAI Lead OS tests.
"""

import pytest
from unittest.mock import MagicMock, patch
from uuid import uuid4
from datetime import datetime, timedelta
from typing import Dict, Any
import sys

# Mock the database modules before importing
sys.modules['supabase'] = MagicMock()
sys.modules['pinecone'] = MagicMock()


@pytest.fixture
def mock_db():
    """Mock database client."""
    db = MagicMock()
    db.get_lead.return_value = None
    db.create_lead.return_value = {"lead_id": str(uuid4())}
    db.update_lead.return_value = True
    db.get_circuit_breaker.return_value = None
    db.check_idempotency_key.return_value = False
    db.get_or_create_usage_metrics.return_value = {
        "llm_tokens_used": 0,
        "browser_sessions_used": 0,
        "scraper_runs_used": 0,
    }
    return db


@pytest.fixture
def mock_config():
    """Mock configuration."""
    config = MagicMock()
    config.kill_switches.global_kill = False
    config.kill_switches.discovery_kill = False
    config.kill_switches.audit_kill = False
    config.kill_switches.outreach_kill = False
    config.budget.daily_llm_token_limit = 1_000_000
    config.budget.daily_browser_session_limit = 100
    config.budget.daily_scraper_run_limit = 50
    config.rate_limits.per_domain_email_per_day = 5
    config.rate_limits.email_per_day = 200
    config.rate_limits.cool_downs.after_bounce_days = 7
    return config


@pytest.fixture
def sample_lead_dict() -> Dict[str, Any]:
    """Create a sample lead dictionary."""
    return {
        "lead_id": str(uuid4()),
        "business_name": "Test Business",
        "domain": "testbusiness.com",
        "niche": "dental",
        "geo": "US-CA",
        "lifecycle_state": "new",
        "tier": "B",
        "created_at": datetime.utcnow().isoformat(),
    }
