from unittest.mock import patch

from src.agents.enrichment import EnrichmentAgent
from src.api.server import build_signal_facts


@patch("src.agents.enrichment.ApifyClient")
def test_instagram_profile_links_ignore_post_urls(mock_apify_client):
    agent = EnrichmentAgent()

    assert agent._extract_instagram_username("https://www.instagram.com/reel/ABC123/") is None
    assert agent._extract_instagram_username("https://www.instagram.com/p/ABC123/") is None


@patch("src.agents.enrichment.ApifyClient")
def test_instagram_profile_links_normalize_to_clean_profile_url(mock_apify_client):
    agent = EnrichmentAgent()

    assert (
        agent._normalize_instagram_profile_url(
            "https://www.instagram.com/looksclinics/?hl=en"
        )
        == "https://www.instagram.com/looksclinics/"
    )


@patch("src.agents.enrichment.ApifyClient")
def test_youtube_channel_links_reject_video_urls(mock_apify_client):
    agent = EnrichmentAgent()

    assert agent._normalize_youtube_channel_url("https://www.youtube.com/watch?v=abc123") is None
    assert agent._normalize_youtube_channel_url("https://www.youtube.com/shorts/abc123") is None
    assert (
        agent._normalize_youtube_channel_url("https://www.youtube.com/@looksclinics/videos")
        == "https://www.youtube.com/@looksclinics"
    )


def test_build_signal_facts_sanitizes_invalid_social_profiles():
    signal_facts = build_signal_facts(
        lead_data={"business_name": "Looks Clinics", "website": "https://looksclinics.in"},
        runtime_metadata={
            "people_intelligence": {
                "instagram_profile": {
                    "profile_url": "https://www.instagram.com/looksclinics/?hl=en",
                    "followers_count": "1200",
                    "source": "apify_instagram_profile_scraper",
                },
                "youtube_channel": {
                    "channel_url": "https://www.youtube.com/watch?v=abc123",
                    "subscriber_count": "34",
                    "source": "apify_youtube_scraper",
                },
            }
        },
    )

    assert signal_facts["instagram_profile"]["profile_url"] == "https://www.instagram.com/looksclinics/"
    assert signal_facts["instagram_profile"]["followers_count"] == 1200
    assert signal_facts["fact_sources"]["instagram"] == "apify_instagram_profile_scraper"
    assert signal_facts["youtube_channel"] == {}
    assert signal_facts["fact_sources"]["youtube"] == "not_verified"
