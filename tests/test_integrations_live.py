import os
import asyncio

import pytest
from pathlib import Path

from src.config.loader import load_env_file

from src.tools.apify import ApifyClient
from src.tools.firecrawl_enrichment import FirecrawlEnrichment
from src.tools.llm import LLMClient
from src.tools.steel import SteelClient
import src.tools.llm as llm_module


def _require_env(var_name: str) -> str:
    repo_root = Path(__file__).resolve().parents[1]
    env_path = repo_root / ".env"
    if env_path.exists():
        load_env_file(str(env_path))
    value = os.getenv(var_name)
    if not value:
        pytest.skip(f"{var_name} not set")
    return value


def test_apify_token_valid():
    _require_env("APIFY_API_TOKEN")
    client = ApifyClient()
    user_info = client._client.user().get()
    assert user_info.get("id")


def test_steel_scrape_example_dot_com():
    _require_env("STEEL_API_KEY")
    client = SteelClient()
    result = client.scrape(
        "https://example.com",
        screenshot=False,
        extract_html=True,
        extract_markdown=False,
        delay=1,
    )
    html = result.get("html") or result.get("content", {}).get("html", "")
    assert html


def test_firecrawl_scrape_example_dot_com():
    _require_env("FIRECRAWL_API_KEY")
    enrichment = FirecrawlEnrichment()
    result = asyncio.run(
        enrichment.analyze_website("https://example.com", "Example Domain")
    )
    assert result.get("status") == "firecrawl_success"
    assert "emails" in result
    assert "phones" in result


def test_openrouter_deepseek_v3_2_generate():
    _require_env("OPENROUTER_API_KEY")
    os.environ["DEFAULT_LLM_PROVIDER"] = "openrouter"
    os.environ["DEFAULT_LLM_MODEL"] = "deepseek/deepseek-v3.2"
    llm_module._llm_client = None

    client = LLMClient(provider="openrouter", model="deepseek/deepseek-v3.2")
    response = client.generate("Reply with the single word: OK", max_tokens=5)
    assert response
