"""Regression tests for the Jan 2026 stability hardening pass.

Goal: stop burning credits and stop accidental re-analyses.

Covers:
  1. Backend `execute_lead_analysis` short-circuits when force_refresh=False
     and the lead is already analyzed (cache-first).
  2. The cache-first helper `_try_return_cached_analysis` exists and is
     wired in BOTH backend trees (src/ and .railway-backend-deploy/).
  3. Frontend lead-list defaults `autoAnalyzeEnabled = false` so opening
     the canvas does NOT trigger an automatic re-analysis run.
  4. Frontend lead-list has a "Re-analyze all" guard prompt and the
     primary button skips already-analyzed leads when force_refresh=false.

All checks are source-text or pure-helper level so they run without
LangGraph / Supabase / Apify credentials.
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# Backend cache-first guard
# ---------------------------------------------------------------------------


def _read(*parts: str) -> str:
    return REPO_ROOT.joinpath(*parts).read_text(encoding="utf-8")


def test_cache_first_helper_exists_in_src():
    text = _read("src", "api", "server.py")
    assert "def _try_return_cached_analysis(" in text
    # Must check analysis_state == "analyzed" before reusing cache.
    block = text.split("def _try_return_cached_analysis(", 1)[1].split("\ndef ", 1)[0]
    assert '"analyzed"' in block
    assert "signal_facts" in block


def test_cache_first_helper_mirrored_in_railway():
    text = _read(".railway-backend-deploy", "src", "api", "server.py")
    assert "def _try_return_cached_analysis(" in text


def test_execute_lead_analysis_uses_cache_first_in_src():
    text = _read("src", "api", "server.py")
    func = text.split("def execute_lead_analysis(", 1)[1].split("\ndef ", 1)[0]
    # Must call the cache helper before doing the heavy pipeline run.
    assert "_try_return_cached_analysis(" in func
    cache_idx = func.index("_try_return_cached_analysis(")
    pipeline_idx = func.index("run_selected_lead_pipeline(")
    assert cache_idx < pipeline_idx, (
        "Cache-first guard must run BEFORE run_selected_lead_pipeline to save credits."
    )
    # Must respect force_refresh.
    assert "if not force_refresh" in func


def test_execute_lead_analysis_uses_cache_first_in_railway():
    text = _read(".railway-backend-deploy", "src", "api", "server.py")
    func = text.split("def execute_lead_analysis(", 1)[1].split("\ndef ", 1)[0]
    assert "_try_return_cached_analysis(" in func
    assert "if not force_refresh" in func


def test_cached_payload_marked_from_cache():
    """When we serve from cache, the payload must be flagged so the
    frontend / observability can tell apart a cache hit from a real run."""
    text = _read("src", "api", "server.py")
    block = text.split("def _try_return_cached_analysis(", 1)[1].split("\ndef ", 1)[0]
    assert 'cached["from_cache"] = True' in block


# ---------------------------------------------------------------------------
# Frontend: auto-analyze default off, single intuitive analyze CTA
# ---------------------------------------------------------------------------


def test_auto_analyze_default_off_in_lead_list():
    text = _read("frontend", "artifacts", "zrai", "lead-list", "client.tsx")
    # The default value handed to React state must be false now.
    assert "metadata?.autoAnalyzeEnabled ?? false" in text, (
        "Auto-analyze must default to OFF so opening the canvas does not "
        "trigger background re-runs that burn credits."
    )
    # The hydration helpers must also default to false to stop stale
    # `true` defaults from old localStorage reviving.
    assert "autoAnalyzeEnabled: payload.autoAnalyzeEnabled ?? false" in text
    # Must NOT default to true anywhere via the `?? true` shortcut for the
    # auto-analyze flag specifically.
    assert "autoAnalyzeEnabled ?? true" not in text, (
        "Found a stale `?? true` default for autoAnalyzeEnabled - the user "
        "explicitly disabled auto-analyze. All defaults must read `?? false`."
    )


def test_lead_list_has_single_clear_primary_cta():
    """User asked for ONE intuitive analyze button, not multiple. The
    bulk "Re-analyze all" button has been removed - re-analysis is now
    a per-lead action from the inspector. Auto-analyze toggle is also
    hidden from the toolbar (still respected if set via metadata)."""
    text = _read("frontend", "artifacts", "zrai", "lead-list", "client.tsx")
    # Primary CTA still exists.
    assert 'data-testid="lead-list-analyze-new-btn"' in text
    # The bulk "Re-analyze all" button must NOT be in the toolbar.
    assert 'data-testid="lead-list-reanalyze-all-btn"' not in text, (
        "Found a `Re-analyze all` button - the user explicitly asked for "
        "fewer buttons. Re-analyze is per-lead from the inspector now."
    )
    # The auto-analyze checkbox must NOT be in the toolbar.
    assert 'data-testid="lead-list-auto-analyze-toggle"' not in text, (
        "Found the `Auto-analyze on open` checkbox in the toolbar - the "
        "user explicitly asked for fewer toggles. It is OFF by default "
        "and is no longer surfaced in the toolbar."
    )


def test_lead_list_primary_analyze_button_skips_analyzed():
    text = _read("frontend", "artifacts", "zrai", "lead-list", "client.tsx")
    # The primary toolbar CTA filters down to unanalyzed visible leads and
    # uses force_refresh: false (cache-first).
    assert 'data-testid="lead-list-analyze-new-btn"' in text
    # Must use force_refresh: false (cache-first) for the unanalyzed batch.
    block_start = text.index('data-testid="lead-list-analyze-new-btn"')
    block = text[block_start : block_start + 4000]
    assert "forceRefresh: false" in block, (
        "The primary analyze button must run cache-first so the backend "
        "short-circuits any already-analyzed leads."
    )


def test_keyboard_shortcut_analyze_visible_skips_already_analyzed():
    """The artifact actions[] entry for "Analyze visible" is the keyboard
    shortcut equivalent of the toolbar button. It must also skip already-
    analyzed leads and run cache-first."""
    text = _read("frontend", "artifacts", "zrai", "lead-list", "client.tsx")
    # Find the action with label "Analyze visible".
    block_start = text.index('label: "Analyze visible"')
    block = text[block_start:block_start + 6000]
    assert "isTerminalAnalysisState" in block, (
        "The 'Analyze visible' shortcut must filter out already-analyzed "
        "leads before sending them to the backend."
    )
    assert "force_refresh: false" in block, (
        "The 'Analyze visible' shortcut must request cache-first so the "
        "backend skips re-running the LangGraph pipeline on analyzed leads."
    )


# ---------------------------------------------------------------------------
# Frontend: error sanitizer is wired in both inspectors
# ---------------------------------------------------------------------------


def test_sanitize_error_helper_wired_in_lead_card_and_list():
    card = _read("frontend", "artifacts", "zrai", "lead-card", "client.tsx")
    list_ = _read("frontend", "artifacts", "zrai", "lead-list", "client.tsx")
    assert 'from "@/lib/zrai/sanitize-error"' in card
    assert 'from "@/lib/zrai/sanitize-error"' in list_
    assert "sanitizeOperatorError(" in card
    assert "sanitizeOperatorError(" in list_


def test_lead_card_has_truth_state_badge_and_doctor_social_section():
    card = _read("frontend", "artifacts", "zrai", "lead-card", "client.tsx")
    assert 'data-testid="lead-card-truth-badge"' in card
    assert 'data-testid="lead-card-doctor-social"' in card
    # And the consolidated single Analyze CTA.
    assert 'data-testid="lead-card-analyze-btn"' in card
    # The duplicate "Refresh truth" BUTTON must be gone (toast strings
    # referencing the words "Refresh truth in a moment" are background
    # copy, not buttons - we tolerate those).
    assert ">Refresh truth<" not in card, (
        "Found a `Refresh truth` button in the lead-card - the user "
        "explicitly asked for ONE intuitive analyze CTA only."
    )
    assert "?\"Refreshing...\":\"Refresh truth\"" not in card.replace(" ", ""), (
        "Found a `Refresh truth` button label in the lead-card."
    )
