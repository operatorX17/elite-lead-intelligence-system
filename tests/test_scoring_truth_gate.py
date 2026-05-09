"""Regression tests for the sparse-truth scoring gate.

When commercial truth coverage is below MIN_TRUTH_COVERAGE_FOR_JUDGMENT
(currently 2 facts), the ScoringAgent must:
  * mark `judgment_state = "needs_verification"`
  * cap `lead_tier` at "C"
  * set `should_skip_outreach`
  * preserve `final_score` for transparency

We extract the helpers directly from src/agents/scoring.py so this test
suite runs without LangGraph / Supabase being installed in the env.
"""
from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def _build_helpers_only_class(scoring_path: Path) -> type:
    """Build a minimal stand-in of ScoringAgent containing just the gate helpers.

    We can't import the real class because it transitively imports langgraph.
    Instead we read the source, extract the three method bodies we need, and
    splice them into a tiny class definition.
    """
    text = scoring_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    needed_methods = (
        "_truth_coverage",
        "_gate_judgment_for_sparse_truth",
    )
    needed_constants = ("MIN_TRUTH_COVERAGE_FOR_JUDGMENT",)

    method_blocks: list[str] = []
    constant_blocks: list[str] = []

    for name in needed_constants:
        for i, line in enumerate(lines):
            if line.strip().startswith(f"{name} ="):
                constant_blocks.append(line.strip())
                break

    for name in needed_methods:
        i = 0
        while i < len(lines):
            if lines[i].strip().startswith(f"def {name}("):
                start = i
                # Find end: next "    def " at same 4-space indent, or class end.
                i += 1
                while i < len(lines):
                    nxt = lines[i]
                    if nxt.startswith("    def ") or nxt.startswith("class ") or nxt.startswith("def "):
                        break
                    i += 1
                # Capture from start to i (exclusive). Lines have 4-space class indent already.
                block = "\n".join(lines[start:i])
                method_blocks.append(block)
                break
            i += 1

    src = (
        "from typing import Any, Dict, Optional\n"
        "\n"
        "class ScoringAgentHelpers:\n"
        f"    {chr(10).join(constant_blocks)}\n"
        "\n"
        + "\n\n".join(method_blocks)
        + "\n"
    )
    module_name = f"_zrai_scoring_helpers_{scoring_path.parent.parent.name}"
    spec = importlib.util.spec_from_loader(module_name, loader=None)
    module = importlib.util.module_from_spec(spec)
    exec(compile(src, str(scoring_path) + "::extracted", "exec"), module.__dict__)  # noqa: S102
    sys.modules[module_name] = module
    return module.ScoringAgentHelpers


@pytest.fixture(scope="module")
def Agent():
    return _build_helpers_only_class(REPO_ROOT / "src" / "agents" / "scoring.py")


@pytest.fixture(scope="module")
def DeployAgent():
    return _build_helpers_only_class(
        REPO_ROOT / ".railway-backend-deploy" / "src" / "agents" / "scoring.py"
    )


def test_truth_coverage_zero_for_empty_facts(Agent):
    a = Agent()
    assert a._truth_coverage(None) == 0
    assert a._truth_coverage({}) == 0


def test_truth_coverage_counts_each_fact(Agent):
    a = Agent()
    facts = {
        "reviews_count": 681,
        "rating": 4.6,
        "branch_count": 2,
        "doctor_count": 4,
        "instagram_profile": {"followers_count": 12000},
    }
    assert a._truth_coverage(facts) == 5


def test_truth_coverage_string_numbers_handled(Agent):
    a = Agent()
    facts = {"reviews_count": "681", "rating": "4.6"}
    assert a._truth_coverage(facts) == 2


def test_gating_demotes_tier_when_sparse(Agent):
    a = Agent()
    scoring = {"final_score": 78, "lead_tier": "A"}
    facts = {"phone_visible": True}  # phone_visible is NOT in coverage; coverage=0
    out = a._gate_judgment_for_sparse_truth(scoring, facts)
    assert out["judgment_state"] == "needs_verification"
    assert out["judgment_label"] == "Needs verification"
    assert out["lead_tier"] == "C"
    assert out["original_lead_tier"] == "A"
    assert out["final_score"] == 78  # score itself preserved
    assert out["should_skip_outreach"] is True
    assert "score_gating_reason" in out
    assert out["truth_coverage"] == 0


def test_gating_passes_through_when_sufficient(Agent):
    a = Agent()
    scoring = {"final_score": 78, "lead_tier": "A"}
    facts = {"reviews_count": 681, "rating": 4.6, "doctor_count": 3}
    out = a._gate_judgment_for_sparse_truth(scoring, facts)
    assert out["judgment_state"] == "ready"
    assert out["judgment_label"] == "Ready for outreach"
    assert out["lead_tier"] == "A"
    assert "original_lead_tier" not in out
    assert out["truth_coverage"] == 3


def test_gating_at_exact_threshold_passes(Agent):
    a = Agent()
    scoring = {"final_score": 55, "lead_tier": "B"}
    facts = {"reviews_count": 100, "rating": 4.0}
    out = a._gate_judgment_for_sparse_truth(scoring, facts)
    assert out["judgment_state"] == "ready"
    assert out["lead_tier"] == "B"


def test_gating_below_threshold_demotes_b_to_c(Agent):
    a = Agent()
    scoring = {"final_score": 55, "lead_tier": "B"}
    facts = {"rating": 4.0}
    out = a._gate_judgment_for_sparse_truth(scoring, facts)
    assert out["judgment_state"] == "needs_verification"
    assert out["lead_tier"] == "C"
    assert out["original_lead_tier"] == "B"


def test_railway_deploy_tree_has_same_gating(DeployAgent):
    """Drift guard: the Railway deploy mirror must expose the same gate."""
    a = DeployAgent()
    scoring = {"final_score": 78, "lead_tier": "A"}
    facts = {}  # zero coverage
    out = a._gate_judgment_for_sparse_truth(scoring, facts)
    assert out["judgment_state"] == "needs_verification"
    assert out["lead_tier"] == "C"
    assert out["original_lead_tier"] == "A"
