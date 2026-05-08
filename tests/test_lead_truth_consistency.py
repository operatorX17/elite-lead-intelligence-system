"""Regression tests for lead-truth correctness (P0 bugs found in live API).

Covers the bug classes from the codex/palate-twilio-demo handoff:

  1. social_profiles[network] character explosion when a string payload is
     followed by a list payload in _merge_social_profiles. Originally produced
     payloads like ["h","t","p","s",":","/","w",...] in production for the
     Sapphire and iSkin lead inspectors.

  2. GPS-coordinate-shaped Instagram handles ("13.0533989", "12.8877892")
     leaking into social_profiles.instagram for iSkin Clinic. The server-side
     normalizer was too permissive.

  3. Truth-state derivation produces a single canonical state that the
     frontend can render explicitly (verified_maps / cached_maps /
     website_proof / social_presence_only / incomplete_verification / failed),
     so sparse leads never show a confident commercial judgment.

  4. Drift between src/api/server.py and .railway-backend-deploy/src/api/server.py.
     Both must expose the same fixes.
"""
from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_helpers_from(server_path: Path) -> types.ModuleType:
    """Load just the pure-Python helper functions from a server.py file.

    server.py imports heavy deps (supabase, FastAPI, langgraph) that we don't
    want pulled into a fast unit test. We extract the helper block into a
    standalone module and exec it in a clean namespace with only stdlib.
    """
    text = server_path.read_text(encoding="utf-8")

    # Helper names we need.
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
        "_SOCIAL_URL_LIST_KEYS",
        "_coerce_int",
        "_coerce_float",
    ]

    # We grep each function/constant out by name. This is brittle but keeps
    # tests independent of the entire 8k-line server.py module graph.
    extracted: list[str] = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        for name in names:
            if line.startswith(f"def {name}(") or line.startswith(f"{name} ="):
                # Capture this top-level block until the next top-level def/class
                # or a clearly non-indented line that is not a continuation.
                start = i
                i += 1
                while i < len(lines):
                    nxt = lines[i]
                    if nxt and not nxt.startswith((" ", "\t", ")", "]", "}")) and not nxt.startswith("#"):
                        if nxt.startswith(("def ", "class ", "@", "_", "#")) or nxt.strip() == "":
                            if nxt.startswith(("def ", "class ", "@")):
                                break
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
    module_name = f"_zrai_helpers_{server_path.parent.parent.name}"
    spec = importlib.util.spec_from_loader(module_name, loader=None)
    module = importlib.util.module_from_spec(spec)
    exec(compile(src, str(server_path) + "::extracted", "exec"), module.__dict__)  # noqa: S102
    sys.modules[module_name] = module
    return module


@pytest.fixture(scope="module")
def src_helpers():
    return _load_helpers_from(REPO_ROOT / "src" / "api" / "server.py")


@pytest.fixture(scope="module")
def deploy_helpers():
    return _load_helpers_from(REPO_ROOT / ".railway-backend-deploy" / "src" / "api" / "server.py")


# ---------------------------------------------------------------------------
# Bug #1: social_profiles character explosion
# ---------------------------------------------------------------------------


class TestMergeSocialProfilesNoCharExplosion:
    def test_string_then_list_does_not_explode(self, src_helpers):
        merged = src_helpers._merge_social_profiles(
            {"instagram": "https://www.instagram.com/foo"},
            {"instagram": ["https://www.instagram.com/bar"]},
        )
        # Must not contain single-character fragments.
        assert all(len(u) > 2 for u in merged["instagram"])
        assert merged["instagram"] == [
            "https://www.instagram.com/foo/",
            "https://www.instagram.com/bar/",
        ]

    def test_list_then_string_does_not_explode(self, src_helpers):
        merged = src_helpers._merge_social_profiles(
            {"instagram": ["https://www.instagram.com/foo"]},
            {"instagram": "https://www.instagram.com/bar"},
        )
        assert all(len(u) > 2 for u in merged["instagram"])
        # Both URLs must survive.
        assert any("foo" in u for u in merged["instagram"])
        assert any("bar" in u for u in merged["instagram"])

    def test_persisted_char_fragments_filtered(self, src_helpers):
        # Simulates the broken Sapphire payload that was already persisted.
        bad_payload = {
            "instagram": [
                "h", "t", "p", "s", ":", "/", "w", ".",
                "https://www.instagram.com/sapphire_skin_clinic",
                "https://www.instagram.com/sapphire_skin_clinic/",
                "https://www.instagram.com/sheelanatraj3371/",
            ]
        }
        merged = src_helpers._merge_social_profiles(bad_payload)
        assert "h" not in merged["instagram"]
        assert ":" not in merged["instagram"]
        assert "https://www.instagram.com/sapphire_skin_clinic/" in merged["instagram"]
        # Both real handles must survive (deduped by canonical URL).
        assert any("sheelanatraj3371" in u for u in merged["instagram"])

    def test_iskin_realistic_payload(self, src_helpers):
        merged = src_helpers._merge_social_profiles(
            {"instagram": "https://www.instagram.com/iskin_clinics/"},
            {"instagram": ["https://www.instagram.com/dr_abhiram_dermatologist/"]},
            {"instagram": [
                "https://www.instagram.com/13.0533989/",  # GPS coord
                "https://www.instagram.com/12.8877892/",  # GPS coord
                "https://www.instagram.com/12.9103096/",  # GPS coord
            ]},
            {"instagram": ["https://www.instagram.com/drshashikiran.a.r_iskinclinic/"]},
            {"instagram_present": True},
        )
        # GPS coords gone, real handles preserved, presence flag carried through.
        assert all("13.05" not in u for u in merged["instagram"])
        assert all("12.88" not in u for u in merged["instagram"])
        assert all("12.91" not in u for u in merged["instagram"])
        assert any("iskin_clinics" in u for u in merged["instagram"])
        assert any("dr_abhiram" in u for u in merged["instagram"])
        assert merged["instagram_present"] is True


# ---------------------------------------------------------------------------
# Bug #2: GPS-coordinate handles
# ---------------------------------------------------------------------------


class TestInstagramNormalizerRejectsCoords:
    @pytest.mark.parametrize("bad", [
        "https://www.instagram.com/13.0533989/",
        "https://www.instagram.com/12.8877892/",
        "https://www.instagram.com/12.9103096/",
        "https://www.instagram.com/0.123/",
        "https://www.instagram.com/123/",  # pure numeric
    ])
    def test_rejects_numeric_handles(self, src_helpers, bad):
        assert src_helpers._normalize_instagram_profile_url(bad) is None

    @pytest.mark.parametrize("good,expected", [
        ("https://www.instagram.com/iskin/", "https://www.instagram.com/iskin/"),
        ("https://www.instagram.com/sapphire_skin_clinic", "https://www.instagram.com/sapphire_skin_clinic/"),
        ("https://www.instagram.com/dr_abhiram_dermatologist", "https://www.instagram.com/dr_abhiram_dermatologist/"),
        # Underscore + dot handle.
        ("https://www.instagram.com/drshashikiran.a.r_iskinclinic/", "https://www.instagram.com/drshashikiran.a.r_iskinclinic/"),
    ])
    def test_accepts_real_handles(self, src_helpers, good, expected):
        assert src_helpers._normalize_instagram_profile_url(good) == expected

    def test_rejects_reserved_paths(self, src_helpers):
        for reserved in ["explore", "p", "reel", "reels", "stories", "accounts"]:
            url = f"https://www.instagram.com/{reserved}/foo"
            assert src_helpers._normalize_instagram_profile_url(url) is None

    def test_rejects_other_hosts(self, src_helpers):
        assert src_helpers._normalize_instagram_profile_url("https://twitter.com/iskin") is None
        assert src_helpers._normalize_instagram_profile_url("not a url") is None


# ---------------------------------------------------------------------------
# Bug #3: truth_state derivation
# ---------------------------------------------------------------------------


class TestDeriveTruthState:
    def test_verified_maps_when_google_maps_source(self, src_helpers):
        facts = {
            "fact_sources": {"reviews": "google_maps", "rating": "google_maps"},
            "reviews_count": 681,
            "rating": 4.6,
        }
        assert src_helpers._derive_truth_state(facts) == "verified_maps"

    def test_cached_maps_when_cached_source(self, src_helpers):
        facts = {
            "fact_sources": {"reviews": "google_maps_cached", "rating": "google_maps_cached"},
            "reviews_count": 2160,
            "rating": 4.9,
        }
        assert src_helpers._derive_truth_state(facts) == "cached_maps"

    def test_website_proof_when_doctors_and_phone(self, src_helpers):
        facts = {
            "phone_visible": True,
            "booking_detected": True,
            "doctor_count": 3,
            "branch_count": 0,
            "fact_sources": {"reviews": "not_verified", "rating": "not_verified"},
        }
        assert src_helpers._derive_truth_state(facts) == "website_proof"

    def test_social_presence_only(self, src_helpers):
        facts = {
            "phone_visible": False,
            "booking_detected": False,
            "doctor_count": 0,
            "branch_count": 0,
            "instagram_present": True,
            "social_profiles": {"instagram": ["https://www.instagram.com/foo/"]},
            "fact_sources": {"reviews": "not_verified", "rating": "not_verified"},
        }
        assert src_helpers._derive_truth_state(facts) == "social_presence_only"

    def test_incomplete_verification_when_nothing(self, src_helpers):
        facts = {
            "phone_visible": False,
            "booking_detected": False,
            "doctor_count": 0,
            "branch_count": 0,
            "fact_sources": {"reviews": "not_verified", "rating": "not_verified"},
        }
        assert src_helpers._derive_truth_state(facts) == "incomplete_verification"

    def test_label_for_each_state(self, src_helpers):
        # Sparse leads must surface 'Needs verification' (not a confident
        # commercial judgment) - this is the gating contract.
        assert src_helpers._truth_state_label("incomplete_verification") == "Needs verification"
        assert src_helpers._truth_state_label("verified_maps") == "Verified"
        assert src_helpers._truth_state_label("cached_maps") == "Cached verification"
        assert src_helpers._truth_state_label("website_proof") == "Website-verified"
        assert src_helpers._truth_state_label("social_presence_only") == "Social presence only"


# ---------------------------------------------------------------------------
# Bug #4: backend trees must agree on these helpers
# ---------------------------------------------------------------------------


class TestRailwayDeployTreeMatches:
    """Same fixes must exist in .railway-backend-deploy/src/api/server.py.

    Drift between trees was the single biggest source of recurring runtime
    errors documented in the handoff (e.g. `name 'rating' is not defined`).
    """

    @pytest.mark.parametrize("bad", [
        "https://www.instagram.com/13.0533989/",
        "https://www.instagram.com/12.8877892/",
    ])
    def test_deploy_tree_rejects_gps_coords(self, deploy_helpers, bad):
        assert deploy_helpers._normalize_instagram_profile_url(bad) is None

    def test_deploy_tree_does_not_explode_strings(self, deploy_helpers):
        merged = deploy_helpers._merge_social_profiles(
            {"instagram": "https://www.instagram.com/foo"},
            {"instagram": ["https://www.instagram.com/bar"]},
        )
        assert all(len(u) > 2 for u in merged["instagram"])
        assert any("foo" in u for u in merged["instagram"])

    def test_deploy_tree_has_truth_state(self, deploy_helpers):
        assert deploy_helpers._derive_truth_state({}) == "incomplete_verification"
        assert deploy_helpers._truth_state_label("verified_maps") == "Verified"
