import os
from pathlib import Path

import pytest

from src.config.loader import load_env_file, get_env, ConfigLoader
from src.config.models import ScoringWeights


def test_load_env_file_sets_env_vars(tmp_path, monkeypatch):
    env_file = tmp_path / "sample.env"
    env_file.write_text(
        "\n".join(
            [
                "# comment",
                "FOO=bar",
                "BAZ=qux",
                "SPACED = value with spaces",
                "EMPTY=",
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.delenv("FOO", raising=False)
    monkeypatch.delenv("BAZ", raising=False)
    monkeypatch.delenv("SPACED", raising=False)
    monkeypatch.delenv("EMPTY", raising=False)

    load_env_file(str(env_file))

    assert os.environ.get("FOO") == "bar"
    assert os.environ.get("BAZ") == "qux"
    assert os.environ.get("SPACED") == "value with spaces"
    assert os.environ.get("EMPTY") == ""


def test_get_env_required_raises(monkeypatch):
    monkeypatch.delenv("MISSING_REQUIRED", raising=False)
    with pytest.raises(ValueError):
        get_env("MISSING_REQUIRED", required=True)


def test_config_loader_defaults_without_niches(tmp_path, monkeypatch):
    config_dir = tmp_path / "config"
    config_dir.mkdir()

    env_file = tmp_path / "nope.env"
    loader = ConfigLoader(config_dir=str(config_dir), env_file=str(env_file))
    config = loader.load()

    assert config.database.supabase_url.startswith("https://")
    assert config.llm.provider in {"google", "openai", "anthropic", "openrouter", "minimax"}
    assert config.niches == {}


def test_config_loader_loads_niches_yaml(tmp_path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()

    niches_yaml = config_dir / "niches.yaml"
    niches_yaml.write_text(
        "\n".join(
            [
                "niches:",
                "  hvac:",
                "    keywords: [\"hvac\", \"air conditioning\"]",
                "    geo_filters: [\"US\"]",
                "    scoring_weights:",
                "      ad_activity: 0.20",
                "      intent: 0.25",
                "      leak: 0.30",
                "      reactivation: 0.10",
                "      contact_quality: 0.10",
                "      business_size: 0.05",
                "    min_score_threshold: 55",
                "    tier_a_threshold: 85",
                "    tier_b_threshold: 65",
            ]
        ),
        encoding="utf-8",
    )

    loader = ConfigLoader(config_dir=str(config_dir), env_file=str(tmp_path / ".env"))
    config = loader.load()

    assert "hvac" in config.niches
    niche = config.niches["hvac"]
    assert niche.keywords == ["hvac", "air conditioning"]
    assert niche.geo_filters == ["US"]
    assert niche.min_score_threshold == 55
    assert niche.tier_a_threshold == 85
    assert niche.tier_b_threshold == 65
    assert niche.scoring_weights.business_size == 0.05


def test_scoring_weights_validation():
    ScoringWeights(
        ad_activity=0.2,
        intent=0.25,
        leak=0.3,
        reactivation=0.1,
        contact_quality=0.1,
        business_size=0.05,
    )

    with pytest.raises(ValueError):
        ScoringWeights(
            ad_activity=0.3,
            intent=0.3,
            leak=0.3,
            reactivation=0.2,
            contact_quality=0.1,
            business_size=0.1,
        )
