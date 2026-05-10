"""Regression tests for the three rock-solid hardening fixes.

1. ApifyClient must expose `run_instagram_profile_scraper` even though the
   actor is deprecated, returning {} as a graceful no-op. Fixes the red
   "'ApifyClient' object has no attribute 'run_instagram_profile_scraper'"
   banner that was killing operator trust on Sapphire / iSkin / Skin Vision.

2. The processed-details payload returned by `/api/v1/leads/{id}` must
   suppress `lead_state.last_error` whenever `analysis_state == "analyzed"`.
   Stale errors from a previous failed run must not haunt the inspector
   after re-analysis succeeded.

3. Read-time scoring gate: legacy scoring rows that lack `judgment_state` /
   `truth_coverage` must have them computed on the fly so the inspector
   never shows a confident commercial judgment on sparse truth.
"""
from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


# -----------------------------------------------------------------
# Fix 1 - ApifyClient stub method (test the source file directly to
# avoid pulling in the heavy Apify SDK / supabase / etc.).
# -----------------------------------------------------------------


def test_apify_has_run_instagram_profile_scraper_stub():
    text = (REPO_ROOT / "src" / "tools" / "apify.py").read_text(encoding="utf-8")
    # The method must exist with the right signature so getattr succeeds
    # AND a direct attribute access does not raise AttributeError.
    assert "def run_instagram_profile_scraper(" in text, (
        "ApifyClient is missing run_instagram_profile_scraper stub - "
        "the AttributeError will surface in the inspector again."
    )
    # Must return {} on the stub path.
    method_block = text.split("def run_instagram_profile_scraper(", 1)[1]
    assert "return {}" in method_block.split("def ", 1)[0], (
        "Stub must return {} so callers fall through gracefully."
    )


def test_apify_stub_mirrored_in_railway_tree():
    text = (REPO_ROOT / ".railway-backend-deploy" / "src" / "tools" / "apify.py").read_text()
    assert "def run_instagram_profile_scraper(" in text


# -----------------------------------------------------------------
# Fix 2 + 3 - read-time helpers from src/api/server.py.
# Same extraction trick used by test_lead_truth_consistency.py.
# -----------------------------------------------------------------


def _load_helpers(server_path: Path):
    text = server_path.read_text(encoding="utf-8")
    names = [
        "_dedupe_strings",
        "_normalize_instagram_profile_url",
        "_normalize_youtube_channel_url",
        "_filter_social_url_list",
        "_merge_social_profiles",
        "_has_meaningful_verified_social",
        "_commercial_truth_coverage",
        "_has_sparse_commercial_truth",
        "_derive_truth_state",
        "_truth_state_label",
        "_apply_read_time_judgment_gate",
        "_SOCIAL_URL_LIST_KEYS",
        "_MIN_TRUTH_COVERAGE_FOR_JUDGMENT",
        "_coerce_int",
        "_coerce_float",
    ]
    extracted: list[str] = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        for name in names:
            if line.startswith(f"def {name}(") or line.startswith(f"{name} ="):
                start = i
                i += 1
                while i < len(lines):
                    nxt = lines[i]
                    if (
                        nxt.startswith("def ")
                        or nxt.startswith("class ")
                        or (nxt.startswith("@") and not nxt.startswith("    "))
                    ):
                        break
                    i += 1
                extracted.append("\n".join(lines[start:i]))
                break
        else:
            i += 1
    src = (
        "import re\n"
        "from typing import Any, Dict, List, Optional\n"
        "from urllib.parse import urlparse\n\n"
        + "\n\n".join(extracted)
    )
    spec = importlib.util.spec_from_loader("_zrai_rs_helpers", loader=None)
    module = importlib.util.module_from_spec(spec)
    exec(compile(src, str(server_path) + "::extracted", "exec"), module.__dict__)  # noqa: S102
    return module


@pytest.fixture(scope="module")
def src_helpers():
    return _load_helpers(REPO_ROOT / "src" / "api" / "server.py")


@pytest.fixture(scope="module")
def deploy_helpers():
    return _load_helpers(REPO_ROOT / ".railway-backend-deploy" / "src" / "api" / "server.py")


# Fix 3 - read-time judgment gate
def test_read_time_gate_demotes_legacy_sparse(src_helpers):
    legacy_scoring = {"final_score": 78, "lead_tier": "A"}  # no judgment_state
    sparse_facts = {"phone_visible": True}  # 0 verified commercial facts
    out = src_helpers._apply_read_time_judgment_gate(legacy_scoring, sparse_facts)
    assert out["judgment_state"] == "needs_verification"
    assert out["lead_tier"] == "C"
    assert out["original_lead_tier"] == "A"
    assert out["truth_coverage"] == 0
    assert out["should_skip_outreach"] is True


def test_read_time_gate_keeps_strong_lead(src_helpers):
    legacy_scoring = {"final_score": 91, "lead_tier": "A"}
    sapphire_facts = {
        "reviews_count": 681,
        "rating": 4.6,
        "branch_count": 2,
        "doctor_count": 4,
    }
    out = src_helpers._apply_read_time_judgment_gate(legacy_scoring, sapphire_facts)
    assert out["judgment_state"] == "ready"
    assert out["lead_tier"] == "A"
    assert "original_lead_tier" not in out
    assert out["truth_coverage"] == 4


def test_read_time_gate_mirrored_in_railway_tree(deploy_helpers):
    out = deploy_helpers._apply_read_time_judgment_gate(
        {"final_score": 50, "lead_tier": "B"}, {}
    )
    assert out["judgment_state"] == "needs_verification"
    assert out["lead_tier"] == "C"


# Fix 2 - stale error suppression contract test (string-level - the actual
# logic lives inside get_processed_details_for_lead which we can't import
# without LangGraph; we assert the source code carries the contract).
def test_stale_error_suppression_in_source():
    text = (REPO_ROOT / "src" / "api" / "server.py").read_text()
    # The processed-details return must include a guarded `error` field that
    # nulls out `last_error` whenever analysis_state == "analyzed".
    assert 'analysis_state == "analyzed"' in text
    assert "last_error" in text
    # Must be inside the get_processed_details_for_lead return.
    func = text.split("def get_processed_details_for_lead(", 1)[1].split("\ndef ", 1)[0]
    assert 'analysis_state == "analyzed"' in func, (
        "get_processed_details_for_lead must suppress last_error when analyzed"
    )


def test_stale_error_suppression_mirrored_in_railway_tree():
    text = (
        REPO_ROOT / ".railway-backend-deploy" / "src" / "api" / "server.py"
    ).read_text()
    func = text.split("def get_processed_details_for_lead(", 1)[1].split("\ndef ", 1)[0]
    assert 'analysis_state == "analyzed"' in func
