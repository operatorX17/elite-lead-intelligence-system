"""
Enrichment Agent - Contact and context extraction.
Requirements: 4.1-4.6
"""

from typing import Dict, Any, List, Optional, Iterable
from datetime import datetime
import re
import logging
import os
from urllib.parse import parse_qs, unquote, urljoin, urlparse
from uuid import UUID

import requests
from bs4 import BeautifulSoup

from src.agents.base import BaseAgent, CircuitBreakerMixin
from src.graph.state import LeadGraphState
from src.db.models import EnrichmentData
from src.tools.apify import ApifyClient


logger = logging.getLogger(__name__)

BRAVE_SEARCH_API_URL = "https://api.search.brave.com/res/v1/web/search"
DISCOVERY_HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

PUBLIC_DIRECTORY_HOST_HINTS = {
    "linkedin.com",
    "instagram.com",
    "facebook.com",
    "practo.com",
    "lybrate.com",
    "justdial.com",
    "1mg.com",
}

INSTAGRAM_RESERVED_PATHS = {
    "accounts",
    "api",
    "developer",
    "directory",
    "explore",
    "media",
    "p",
    "reel",
    "reels",
    "share",
    "stories",
    "tv",
}

YOUTUBE_ALLOWED_CHANNEL_PREFIXES = {"@", "c", "channel", "user"}
YOUTUBE_RESERVED_PATHS = {
    "embed",
    "feed",
    "hashtag",
    "live",
    "playlist",
    "results",
    "shorts",
    "watch",
}

BRANCH_LOCALITY_ALIASES = {
    "jp nagar": "JP Nagar",
    "j p nagar": "JP Nagar",
    "koramangala": "Koramangala",
    "jayanagar": "Jayanagar",
    "indiranagar": "Indiranagar",
    "whitefield": "Whitefield",
    "hsr": "HSR Layout",
    "hsr layout": "HSR Layout",
    "electronic city": "Electronic City",
    "sarjapur": "Sarjapur",
    "sarjapur road": "Sarjapur",
    "thanisandra": "Thanisandra",
    "thannisandra": "Thanisandra",
    "thanisandra main road": "Thanisandra",
    "chikkabellandur": "Chikkabellandur",
    "nagawara": "Nagawara",
    "bilekahalli": "Bilekahalli",
    "uttarahalli": "Uttarahalli",
    "btm layout": "BTM Layout",
    "annapurneshwari nagar": "Annapurneshwari Nagar",
    "jnananjyothinagar": "Jnananjyothinagar",
    "railway layout": "Railway Layout",
}


# Tech signal patterns
BOOKING_PROVIDERS = {
    "calendly": r"calendly\.com",
    "acuity": r"acuityscheduling\.com",
    "square": r"squareup\.com|square\.site",
    "setmore": r"setmore\.com",
    "booksy": r"booksy\.com",
    "vagaro": r"vagaro\.com",
    "mindbody": r"mindbodyonline\.com",
}

CRM_HINTS = {
    "hubspot": r"hubspot|hs-scripts",
    "salesforce": r"salesforce|pardot",
    "zoho": r"zoho",
    "pipedrive": r"pipedrive",
    "freshsales": r"freshsales",
}

CHAT_WIDGETS = {
    "intercom": r"intercom",
    "drift": r"drift\.com|driftt",
    "zendesk": r"zendesk|zopim",
    "crisp": r"crisp\.chat",
    "tawk": r"tawk\.to",
    "livechat": r"livechatinc",
    "freshchat": r"freshchat",
}

FORM_TOOLS = {
    "typeform": r"typeform\.com",
    "jotform": r"jotform\.com",
    "google_forms": r"docs\.google\.com/forms",
    "wufoo": r"wufoo\.com",
    "formstack": r"formstack\.com",
}


class EnrichmentAgent(BaseAgent, CircuitBreakerMixin):
    """
    Enrichment Agent for contact and context extraction.
    
    Requirements:
    - 4.1: Extract technology signals (booking_provider, crm_hint, chat_widget, form_tool)
    - 4.2: Extract decision-maker hints from owner names, team pages, LinkedIn
    - 4.3: Normalize phone and email formats, validate email domains
    - 4.4: Compute enrichment_confidence score (0-1)
    - 4.5: Compute contact_quality_score (0-100)
    - 4.6: Deduplicate and merge duplicate contacts
    """
    
    def __init__(self):
        super().__init__("enrichment")
        self._apify = ApifyClient()
    
    def process(self, state: LeadGraphState) -> LeadGraphState:
        """Process enrichment for a lead."""
        if not state.get("lead"):
            self._logger.warning("No lead data to enrich")
            return state
        
        state["current_stage"] = "enrichment"
        
        lead = state["lead"]
        
        # Get raw Apify data from metadata (stored by discovery agent)
        metadata = state.get("metadata", {})
        fast_mode = bool(metadata.get("fast_mode"))
        self._fast_mode = fast_mode  # picked up by helpers (e.g. doctor IG enrichment)
        raw_apify_data = metadata.get("raw_apify_data", {})
        
        # Merge raw Apify data into lead for volume signal extraction
        lead_with_apify = {**lead, **raw_apify_data}
        
        website_context = self._fetch_website_context(
            lead.get("landing_page_url") or lead.get("website"),
            fast_mode=fast_mode,
        )
        instagram_profile = self._extract_instagram_profile(lead, website_context, fast_mode=fast_mode)
        youtube_channel = self._extract_youtube_channel(lead, website_context, fast_mode=fast_mode)
        if instagram_profile:
            social_profiles = dict(website_context.get("social_profiles") or {})
            social_profiles["instagram_profile"] = instagram_profile
            website_context["social_profiles"] = social_profiles
        if youtube_channel:
            social_profiles = dict(website_context.get("social_profiles") or {})
            social_profiles["youtube_channel"] = youtube_channel
            website_context["social_profiles"] = social_profiles

        # Extract tech signals and clinic-specific contact context from the site.
        tech_signals = self._extract_tech_signals(website_context.get("content", ""))

        people_intelligence = self._extract_people_intelligence(lead_with_apify, website_context)
        if instagram_profile:
            people_intelligence["instagram_profile"] = instagram_profile
            if instagram_profile.get("full_name") and not people_intelligence.get("decision_maker_name"):
                people_intelligence["decision_maker_name"] = instagram_profile.get("full_name")
        if youtube_channel:
            people_intelligence["youtube_channel"] = youtube_channel

        # Extract decision maker info from business name, contact pages, social/profile hints,
        # and ranked people intelligence derived from the site and public search results.
        decision_maker = self._extract_decision_maker(
            lead_with_apify,
            website_context,
            people_intelligence=people_intelligence,
        )

        # Normalize contacts from both discovery and website extraction.
        candidate_phones: List[str] = []
        if lead.get("phone"):
            candidate_phones.append(str(lead["phone"]))
        candidate_phones.extend(website_context.get("phones", []))
        candidate_phones.extend(people_intelligence.get("phone_numbers", []))

        normalized_phones: List[str] = []
        for phone in candidate_phones:
            normalized = self._normalize_phone(phone)
            if normalized and normalized not in normalized_phones:
                normalized_phones.append(normalized)

        normalized_phone = (
            self._normalize_phone(people_intelligence.get("best_contact_phone"))
            or (normalized_phones[0] if normalized_phones else None)
        )
        validated_emails = self._validate_emails(
            list(lead.get("emails_found", []))
            + website_context.get("emails", [])
            + list(people_intelligence.get("emails", []))
        )

        if website_context.get("booking_link") and not tech_signals.get("booking_provider"):
            tech_signals["booking_provider"] = "native_booking"
        if website_context.get("contact_form") and not tech_signals.get("form_tool"):
            tech_signals["form_tool"] = "native_form"
        if website_context.get("whatsapp") and not tech_signals.get("chat_widget"):
            tech_signals["chat_widget"] = "whatsapp"
        if lead.get("phone") and "phone" not in website_context.get("contact_paths", []):
            website_context.setdefault("contact_paths", []).append("phone")
        
        # Extract volume signals from Google Maps data (NEW) - use merged data
        volume_signals = self._extract_volume_signals(lead_with_apify)
        
        # Compute scores
        enrichment_confidence = self._compute_enrichment_confidence(
            tech_signals, decision_maker, normalized_phone, validated_emails
        )
        contact_quality_score = self._compute_contact_quality_score(
            normalized_phone, validated_emails, decision_maker
        )
        
        decision_maker_name = decision_maker.get("name") or people_intelligence.get("decision_maker_name")
        decision_maker_linkedin = (
            decision_maker.get("linkedin")
            or people_intelligence.get("best_contact_linkedin")
            or people_intelligence.get("decision_maker_linkedin")
        )

        state["metadata"] = {
            **(state.get("metadata") or {}),
            "people_intelligence": people_intelligence,
        }
        self._persist_people_intelligence(state, people_intelligence)

        # Create enrichment data dict
        enrichment = {
            "lead_id": lead.get("lead_id"),
            "enrichment_confidence": enrichment_confidence,
            "booking_provider": tech_signals.get("booking_provider"),
            "crm_hint": tech_signals.get("crm_hint"),
            "chat_widget": tech_signals.get("chat_widget"),
            "form_tool": tech_signals.get("form_tool"),
            "decision_maker_name": decision_maker_name,
            "decision_maker_linkedin": decision_maker_linkedin,
            "decision_maker_role": decision_maker.get("role"),
            "decision_maker_source": decision_maker.get("source"),
            "decision_maker_confidence": decision_maker.get("confidence"),
            "contact_quality_score": contact_quality_score,
            "normalized_phone": normalized_phone,
            "validated_emails": validated_emails,
            "contact_paths": website_context.get("contact_paths", []),
            "social_profiles": website_context.get("social_profiles", {}),
            "key_services": website_context.get("services", []),
            "booking_link": website_context.get("booking_link"),
            "whatsapp_detected": website_context.get("whatsapp", False),
            # Volume signals (NEW)
            "popular_times_histogram": volume_signals.get("popular_times_histogram"),
            "popular_times_live_text": volume_signals.get("popular_times_live_text"),
            "people_typically_spend_here": volume_signals.get("people_typically_spend_here"),
            "peak_busyness": volume_signals.get("peak_busyness"),
            "avg_busyness": volume_signals.get("avg_busyness"),
            "busy_hours_count": volume_signals.get("busy_hours_count"),
            "avg_visit_duration_min": volume_signals.get("avg_visit_duration_min"),
            "is_peak_busy": volume_signals.get("is_peak_busy", False),
            "is_above_average": volume_signals.get("is_above_average", False),
            "opening_hours": volume_signals.get("opening_hours"),
            "reviews_distribution": volume_signals.get("reviews_distribution"),
            "questions_and_answers": volume_signals.get("questions_and_answers"),
            "web_results": volume_signals.get("web_results"),
            "table_reservation_links": volume_signals.get("table_reservation_links"),
            "image_categories": volume_signals.get("image_categories"),
        }
        
        state["enrichment"] = enrichment
        
        # Save to database
        self._save_enrichment(enrichment)
        
        return state
    
    def _fetch_website_context(self, website: Optional[str], *, fast_mode: bool = False) -> Dict[str, Any]:
        """Fetch a website once and derive clinic-ready extraction hints."""
        context: Dict[str, Any] = {
            "content": "",
            "raw_content": "",
            "emails": [],
            "phones": [],
            "supporting_urls": [],
            "contact_paths": [],
            "social_profiles": {},
            "services": [],
            "booking_link": None,
            "contact_form": False,
            "whatsapp": False,
            "whatsapp_target": None,
        }

        if not website:
            return context

        website = self._normalize_url(website)

        raw_content = self._fetch_page_content(website, fast_mode=fast_mode)

        if not raw_content:
            try:
                crawl_result = self._apify.crawl_website(website, max_pages=2 if fast_mode else 5)
                raw_content = str(crawl_result)
            except Exception as exc:
                self._logger.warning("Apify crawl fallback failed for %s: %s", website, exc)

        supporting_urls = self._extract_candidate_page_urls(raw_content, website)
        context["supporting_urls"] = supporting_urls
        supporting_content: List[str] = []
        for supporting_url in supporting_urls[: (4 if fast_mode else 6)]:
            if supporting_url.rstrip("/") == website.rstrip("/"):
                continue
            extra_page = self._fetch_page_content(supporting_url, fast_mode=fast_mode)
            if extra_page:
                supporting_content.append(extra_page)

        if supporting_content:
            raw_content = "\n".join([raw_content, *supporting_content])

        asset_content = self._fetch_embedded_asset_content(raw_content, website, fast_mode=fast_mode)
        if asset_content:
            raw_content = "\n".join([raw_content, asset_content])

        lower_content = raw_content.lower()
        text_content = BeautifulSoup(raw_content, "html.parser").get_text("\n")
        context["raw_content"] = raw_content
        context["content"] = lower_content
        context["emails"] = self._validate_emails(
            re.findall(
                r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
                raw_content,
            )
            + re.findall(
                r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
                text_content,
            )
        )
        context["phones"] = self._extract_phone_candidates(raw_content)
        context["social_profiles"] = self._extract_social_profiles(raw_content)

        contact_paths: List[str] = []
        if context["emails"]:
            contact_paths.append("email")
        if context["phones"]:
            contact_paths.append("phone")
        whatsapp_target = self._extract_whatsapp_target(raw_content)
        if whatsapp_target:
            contact_paths.append("whatsapp")
            context["whatsapp"] = True
            context["whatsapp_target"] = whatsapp_target
        if any(
            token in lower_content
            for token in [
                "contact us",
                "get in touch",
                "book appointment",
                "book consultation",
                "schedule appointment",
                "request callback",
                "book now",
            ]
        ):
            contact_paths.append("contact form")
            context["contact_form"] = True
        booking_link = self._extract_first_link(
            raw_content,
            ["book", "appointment", "consultation", "schedule", "reserve"],
        )
        if booking_link:
            contact_paths.append("booking")
            context["booking_link"] = booking_link

        services = self._extract_key_services(raw_content)
        if services:
            context["services"] = services

        deduped_paths: List[str] = []
        for path in contact_paths:
            if path not in deduped_paths:
                deduped_paths.append(path)
        context["contact_paths"] = deduped_paths

        return context

    def _extract_instagram_profile(
        self,
        lead: Dict[str, Any],
        website_context: Dict[str, Any],
        *,
        fast_mode: bool = False,
    ) -> Dict[str, Any]:
        """Extract Instagram profile intelligence for the lead when an IG handle exists."""
        social_profiles = dict(website_context.get("social_profiles") or {})
        instagram_candidates: List[str] = []
        lead_instagram = lead.get("instagram")
        if isinstance(lead_instagram, str) and lead_instagram.strip():
            instagram_candidates.append(lead_instagram.strip())
        instagram_candidates.extend(list(social_profiles.get("instagram") or []))

        username = None
        profile_url = None
        for candidate in instagram_candidates:
            parsed = self._extract_instagram_username(candidate)
            if parsed:
                username = parsed
                profile_url = candidate
                break

        if not username:
            return {}

        lightweight_profile: Dict[str, Any] = {
            "username": username,
            "profile_url": self._normalize_instagram_profile_url(profile_url)
            or f"https://www.instagram.com/{username}/",
            "source": "website_instagram_link",
        }
        if fast_mode:
            return lightweight_profile

        profile: Dict[str, Any] = {}
        if self._env_feature_enabled("ZRAI_ENABLE_INSTAGRAM_PROFILE_ACTOR", default=True):
            profile_scraper = getattr(self._apify, "run_instagram_profile_scraper", None)
            if callable(profile_scraper):
                profile = profile_scraper(lightweight_profile["profile_url"])
            else:
                logger.warning(
                    "Apify client missing run_instagram_profile_scraper; falling back to lighter Instagram extraction"
                )

        html_snapshot = self._fetch_instagram_profile_snapshot(lightweight_profile["profile_url"])
        if html_snapshot:
            lightweight_profile.update(
                {
                    key: value
                    for key, value in html_snapshot.items()
                    if value not in (None, "", [], {})
                }
            )

        if profile:
            biography = (
                profile.get("biography")
                or profile.get("bio")
                or profile.get("biographyText")
                or profile.get("description")
            )
            full_name = (
                profile.get("fullName")
                or profile.get("full_name")
                or profile.get("name")
            )
            external_url = (
                profile.get("externalUrl")
                or profile.get("external_url")
                or profile.get("website")
                or profile.get("link")
            )
            follower_count = (
                profile.get("followersCount")
                or profile.get("followers")
                or profile.get("follower_count")
                or lightweight_profile.get("followers_count")
            )
            following_count = (
                profile.get("followsCount")
                or profile.get("followingCount")
                or profile.get("following")
                or lightweight_profile.get("following_count")
            )
            posts_count = (
                profile.get("postsCount")
                or profile.get("posts_count")
                or lightweight_profile.get("posts_count")
            )

            normalized_profile: Dict[str, Any] = {
                **lightweight_profile,
                "full_name": full_name or lightweight_profile.get("full_name"),
                "bio": biography or lightweight_profile.get("bio"),
                "external_url": external_url,
                "followers_count": follower_count,
                "following_count": following_count,
                "verified": profile.get("verified"),
                "email": profile.get("email"),
                "is_business_account": profile.get("isBusinessAccount"),
                "business_category": profile.get("businessCategoryName")
                or profile.get("business_category_name")
                or profile.get("category"),
                "posts_count": posts_count,
                "latest_post_count": len(profile.get("latestPosts") or []),
                "profile_pic_url": profile.get("profilePicUrl") or profile.get("profile_pic_url"),
                "source": "apify_instagram_profile_scraper" if profile else lightweight_profile.get("source"),
            }
            return {
                key: value
                for key, value in normalized_profile.items()
                if value not in (None, "", [], {})
            }

        if not self._env_feature_enabled("ZRAI_ENABLE_INSTAGRAM_BIO_ACTOR", default=True):
            return lightweight_profile

        profile = self._apify.run_instagram_bio_extractor(username)
        if not profile:
            return lightweight_profile

        biography = (
            profile.get("biography")
            or profile.get("bio")
            or profile.get("biographyText")
            or profile.get("description")
        )
        full_name = (
            profile.get("fullName")
            or profile.get("full_name")
            or profile.get("name")
        )
        external_url = profile.get("externalUrl") or profile.get("external_url") or profile.get("website")
        follower_count = (
            profile.get("followersCount")
            or profile.get("followers")
            or profile.get("follower_count")
            or lightweight_profile.get("followers_count")
        )
        following_count = (
            profile.get("followsCount")
            or profile.get("followingCount")
            or profile.get("following")
            or lightweight_profile.get("following_count")
        )
        posts_count = (
            profile.get("postsCount")
            or profile.get("posts_count")
            or lightweight_profile.get("posts_count")
        )

        normalized: Dict[str, Any] = {
            **lightweight_profile,
            "full_name": full_name or lightweight_profile.get("full_name"),
            "bio": biography or lightweight_profile.get("bio"),
            "external_url": external_url,
            "followers_count": follower_count,
            "following_count": following_count,
            "verified": profile.get("verified"),
            "business_category": profile.get("businessCategoryName")
            or profile.get("business_category_name"),
            "posts_count": posts_count,
            "latest_post_count": len(profile.get("latestPosts") or []),
            "source": "apify_instagram_bio_extractor"
            if any(value not in (None, "", [], {}) for value in profile.values())
            else lightweight_profile.get("source"),
        }
        return {key: value for key, value in normalized.items() if value not in (None, "", [], {})}

    def _fetch_instagram_profile_snapshot(self, profile_url: str) -> Dict[str, Any]:
        """Fetch lightweight public Instagram profile metrics from page HTML."""
        normalized_url = self._normalize_instagram_profile_url(profile_url)
        if not normalized_url:
            return {}

        try:
            response = requests.get(
                normalized_url,
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=20,
            )
            response.raise_for_status()
        except Exception as exc:
            logger.warning("Instagram HTML fallback error for %s: %s", normalized_url, exc)
            return {}

        html = response.text or ""
        if not html:
            return {}

        def _match_metric(pattern: str) -> Optional[int]:
            match = re.search(pattern, html, flags=re.IGNORECASE)
            if not match:
                return None
            return self._coerce_int(match.group(1))

        full_name = None
        username = self._extract_instagram_username(normalized_url) or ""
        meta_title = re.search(r'<meta[^>]+property="og:title"[^>]+content="([^"]+)"', html, flags=re.IGNORECASE)
        if meta_title:
            full_name = str(meta_title.group(1) or "").strip()
            if full_name.lower().endswith(f"(@{username.lower()})"):
                full_name = full_name[: -(len(username) + 3)].strip(" -:")
        if not full_name or "instagram photos and videos" in full_name.lower():
            og_description = re.search(
                r'<meta[^>]+property="og:description"[^>]+content="([^"]+)"',
                html,
                flags=re.IGNORECASE,
            )
            if og_description:
                description = str(og_description.group(1) or "")
                profile_name = re.search(
                    r"videos from\s+(.+?)\s+\((?:&#064;|@)",
                    description,
                    flags=re.IGNORECASE,
                )
                if profile_name:
                    full_name = profile_name.group(1).strip()

        return {
            "full_name": full_name,
            "followers_count": _match_metric(r'([0-9][0-9,\.]*)\s+Followers\b'),
            "following_count": _match_metric(r'([0-9][0-9,\.]*)\s+Following\b'),
            "posts_count": _match_metric(r'([0-9][0-9,\.]*)\s+Posts\b'),
            "source": "instagram_public_html",
        }

    def _extract_youtube_channel(
        self,
        lead: Dict[str, Any],
        website_context: Dict[str, Any],
        *,
        fast_mode: bool = False,
    ) -> Dict[str, Any]:
        """Extract lightweight YouTube channel intelligence from the site and actor."""
        social_profiles = dict(website_context.get("social_profiles") or {})
        youtube_candidates: List[str] = []
        youtube_candidates.extend(list(social_profiles.get("youtube") or []))

        channel_url = next(
            (
                normalized
                for normalized in (
                    self._normalize_youtube_channel_url(str(candidate).strip())
                    for candidate in youtube_candidates
                    if isinstance(candidate, str) and str(candidate).strip()
                )
                if normalized
            ),
            None,
        )
        if not channel_url:
            return {}

        lightweight_channel: Dict[str, Any] = {
            "channel_url": channel_url,
            "source": "website_youtube_link",
        }
        if fast_mode:
            return lightweight_channel
        if not self._env_feature_enabled("ZRAI_ENABLE_YOUTUBE_ACTOR", default=True):
            return lightweight_channel

        items = self._apify.run_youtube_scraper([channel_url])
        if not items:
            return lightweight_channel

        subscriber_count = 0
        total_views = 0
        total_videos = 0
        recent_view_sum = 0
        recent_view_items = 0
        latest_video_date = None
        channel_name = None
        resolved_channel_url = channel_url

        for item in items:
            if not isinstance(item, dict):
                continue
            channel_name = channel_name or item.get("channelName") or item.get("channel_name")
            resolved_channel_url = (
                item.get("channelUrl")
                or item.get("channel_url")
                or resolved_channel_url
            )
            subscriber_count = max(
                subscriber_count,
                self._coerce_int(item.get("numberOfSubscribers") or item.get("subscriberCount")),
            )
            total_views = max(
                total_views,
                self._coerce_int(item.get("channelTotalViews") or item.get("totalViews")),
            )
            total_videos = max(
                total_videos,
                self._coerce_int(item.get("channelTotalVideos") or item.get("videoCount")),
            )
            view_count = self._coerce_int(item.get("viewCount") or item.get("views"))
            if view_count > 0:
                recent_view_sum += view_count
                recent_view_items += 1
            published_at = str(item.get("date") or "").strip()
            if published_at and (latest_video_date is None or published_at > latest_video_date):
                latest_video_date = published_at

        normalized: Dict[str, Any] = {
            **lightweight_channel,
            "channel_name": channel_name,
            "channel_url": resolved_channel_url,
            "subscriber_count": subscriber_count or None,
            "total_views": total_views or None,
            "total_videos": total_videos or None,
            "recent_video_count": len([item for item in items if isinstance(item, dict)]),
            "avg_recent_views": int(recent_view_sum / recent_view_items) if recent_view_items else None,
            "latest_video_date": latest_video_date,
            "source": "apify_youtube_scraper",
        }
        return {key: value for key, value in normalized.items() if value not in (None, "", [], {})}

    def _env_feature_enabled(self, env_key: str, *, default: bool = False) -> bool:
        raw_value = os.getenv(env_key)
        if raw_value is None or not raw_value.strip():
            return default
        return raw_value.strip().lower() in {"1", "true", "yes", "on"}

    def _coerce_int(self, value: Any) -> int:
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        raw = str(value or "").strip()
        if not raw:
            return 0
        digits = re.sub(r"[^\d]", "", raw)
        return int(digits) if digits else 0

    def _extract_instagram_username(self, value: Optional[str]) -> Optional[str]:
        """Extract a clean Instagram username from a URL or raw handle."""
        raw = (value or "").strip()
        if not raw:
            return None
        if "instagram.com" not in raw.lower():
            candidate = raw.lstrip("@").strip("/")
            if candidate.lower() in INSTAGRAM_RESERVED_PATHS:
                return None
            if not re.fullmatch(r"[A-Za-z0-9._]{4,30}", candidate or ""):
                return None
            if len(re.findall(r"[A-Za-z]", candidate)) < 3:
                return None
            return candidate or None

        parsed = urlparse(raw if raw.startswith(("http://", "https://")) else f"https://{raw}")
        segments = [segment for segment in parsed.path.split("/") if segment]
        if not segments:
            return None
        candidate = segments[0].lstrip("@").strip()
        if candidate.lower() in INSTAGRAM_RESERVED_PATHS:
            return None
        if not re.fullmatch(r"[A-Za-z0-9._]{1,30}", candidate or ""):
            return None
        if len(re.findall(r"[A-Za-z]", candidate)) < 2:
            return None
        return candidate or None

    def _normalize_instagram_profile_url(self, value: Optional[str]) -> Optional[str]:
        username = self._extract_instagram_username(value)
        if not username:
            return None
        return f"https://www.instagram.com/{username}/"

    def _normalize_youtube_channel_url(self, value: Optional[str]) -> Optional[str]:
        raw = (value or "").strip()
        if not raw:
            return None

        parsed = urlparse(raw if raw.startswith(("http://", "https://")) else f"https://{raw}")
        hostname = parsed.netloc.lower().replace("www.", "").replace("m.", "")
        if hostname != "youtube.com":
            return None

        segments = [segment.strip() for segment in parsed.path.split("/") if segment.strip()]
        if not segments:
            return None

        first = segments[0]
        if first.lower() in YOUTUBE_RESERVED_PATHS:
            return None
        if first.startswith("@") and len(first) > 1:
            return f"https://www.youtube.com/{first}"
        if first in YOUTUBE_ALLOWED_CHANNEL_PREFIXES and len(segments) > 1:
            return f"https://www.youtube.com/{first}/{segments[1]}"
        return None

    def _fetch_embedded_asset_content(self, raw_html: str, base_url: str, *, fast_mode: bool = False) -> str:
        """Fetch a small bounded set of same-origin JS assets to recover data from JS-shell sites."""
        if not raw_html:
            return ""

        asset_urls: List[str] = []
        base_host = (urlparse(base_url).netloc or "").lower()
        for script_src in re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', raw_html, flags=re.IGNORECASE):
            absolute = urljoin(base_url, script_src)
            parsed = urlparse(absolute)
            if parsed.scheme not in {"http", "https"}:
                continue
            if base_host and (parsed.netloc or "").lower() != base_host:
                continue
            lowered = absolute.lower()
            if not lowered.endswith(".js"):
                continue
            if absolute not in asset_urls:
                asset_urls.append(absolute)

        chunks: List[str] = []
        remaining_chars = 500_000 if fast_mode else 1_200_000
        for asset_url in asset_urls[: (1 if fast_mode else 3)]:
            if remaining_chars <= 0:
                break
            try:
                response = requests.get(
                    asset_url,
                    timeout=8 if fast_mode else 25,
                    headers=DISCOVERY_HTTP_HEADERS,
                )
                response.raise_for_status()
                body = response.text or ""
                if not body:
                    continue
                body = body[: min(len(body), remaining_chars, 700_000)]
                remaining_chars -= len(body)
                chunks.append(body)
            except Exception as exc:
                self._logger.warning("Asset scrape failed for %s: %s", asset_url, exc)

        return "\n".join(chunks)

    def _fetch_page_content(self, url: str, *, fast_mode: bool = False) -> str:
        raw_content = ""
        try:
            api_key = os.getenv("FIRECRAWL_API_KEY")
            if api_key:
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                }
                payload = {
                    "url": url,
                    "formats": ["markdown", "html"],
                    "onlyMainContent": False,
                }
                response = requests.post(
                    "https://api.firecrawl.dev/v1/scrape",
                    json=payload,
                    headers=headers,
                    timeout=12 if fast_mode else 30,
                )
                response.raise_for_status()
                data = response.json().get("data", {})
                raw_content = " ".join(
                    [
                        str(data.get("html") or ""),
                        str(data.get("markdown") or ""),
                    ]
                ).strip()
        except Exception as exc:
            self._logger.warning("Firecrawl scrape failed for %s: %s", url, exc)

        if raw_content:
            return raw_content

        try:
            response = requests.get(
                url,
                timeout=8 if fast_mode else 20,
                headers=DISCOVERY_HTTP_HEADERS,
            )
            response.raise_for_status()
            return response.text
        except Exception as exc:
            self._logger.warning("Static website fallback failed for %s: %s", url, exc)
            return ""

    def _extract_candidate_page_urls(self, raw_content: str, base_url: str) -> List[str]:
        if not raw_content:
            return []

        keywords = (
            "contact",
            "about",
            "team",
            "doctor",
            "doctors",
            "founder",
            "director",
            "management",
            "locations",
            "clinics",
        )

        base_host = (urlparse(base_url).netloc or "").lower()
        candidates: List[str] = []
        raw_links = re.findall(r'href=["\']([^"\']+)["\']', raw_content, flags=re.IGNORECASE)
        raw_links.extend(re.findall(r"\((https?://[^\s)]+|/[^\s)]+)\)", raw_content))

        for href in raw_links:
            if not href:
                continue
            absolute = urljoin(base_url, href)
            parsed = urlparse(absolute)
            if parsed.scheme not in {"http", "https"}:
                continue
            if base_host and (parsed.netloc or "").lower() != base_host:
                continue
            lowered = absolute.lower()
            if not any(keyword in lowered for keyword in keywords):
                continue
            normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path or ''}"
            if normalized not in candidates:
                candidates.append(normalized)

        return candidates

    def _normalize_url(self, url: str) -> str:
        normalized = url.strip()
        if normalized and not normalized.startswith(("http://", "https://")):
            normalized = f"https://{normalized}"
        return normalized

    def _extract_tech_signals(self, page_content: str) -> Dict[str, str]:
        """
        Extract technology signals from already-fetched website content.
        Requirements: 4.1
        """
        signals = {}

        try:
            for provider, pattern in BOOKING_PROVIDERS.items():
                if re.search(pattern, page_content, re.IGNORECASE):
                    signals["booking_provider"] = provider
                    break

            for crm, pattern in CRM_HINTS.items():
                if re.search(pattern, page_content, re.IGNORECASE):
                    signals["crm_hint"] = crm
                    break

            for widget, pattern in CHAT_WIDGETS.items():
                if re.search(pattern, page_content, re.IGNORECASE):
                    signals["chat_widget"] = widget
                    break

            for tool, pattern in FORM_TOOLS.items():
                if re.search(pattern, page_content, re.IGNORECASE):
                    signals["form_tool"] = tool
                    break

        except Exception as e:
            self._logger.error(f"Error extracting tech signals: {e}")
        
        return signals
    
    def _extract_decision_maker(
        self,
        lead: Dict[str, Any],
        website_context: Optional[Dict[str, Any]] = None,
        people_intelligence: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Extract decision-maker information.
        Requirements: 4.2
        """
        decision_maker: Dict[str, Any] = {}
        website_context = website_context or {}
        people_intelligence = people_intelligence or {}
        raw_content = str(website_context.get("raw_content") or "")
        social_profiles = website_context.get("social_profiles") or {}
        linkedin_profiles = social_profiles.get("linkedin") or []
        if isinstance(linkedin_profiles, str):
            linkedin_profiles = [linkedin_profiles]

        stopwords = {
            "the",
            "aesthetic",
            "clinic",
            "skin",
            "hair",
            "laser",
            "best",
            "care",
            "center",
            "centre",
            "hospital",
        }

        candidates: List[Dict[str, Any]] = []
        candidates.extend(list(people_intelligence.get("decision_maker_candidates") or []))
        business_name = str(lead.get("business_name", "")).strip()
        business_name_person = self._extract_person_name_from_business_name(business_name)
        if business_name_person:
            candidates.append(
                {
                    "name": business_name_person,
                    "role": "doctor_named_brand",
                    "source": "business_name",
                    "score": 40,
                }
            )

        if raw_content:
            role_patterns = [
                (
                    "founder",
                    100,
                    [
                        r"(?i)(?:founder|co[-\s]?founder|owner|promoter|chairman)[^A-Za-z]{0,24}(?:dr\.?\s*)?(?P<name>[A-Z][A-Za-z.\-]+(?:\s+[A-Z][A-Za-z.\-]+){0,3})",
                        r"(?i)founded\s+by[^A-Za-z]{0,24}(?:dr\.?\s*)?(?P<name>[A-Z][A-Za-z.\-]+(?:\s+[A-Z][A-Za-z.\-]+){0,3})",
                    ],
                ),
                (
                    "director",
                    92,
                    [
                        r"(?i)(?:medical director|managing director|director|clinic director)[^A-Za-z]{0,24}(?:dr\.?\s*)?(?P<name>[A-Z][A-Za-z.\-]+(?:\s+[A-Z][A-Za-z.\-]+){0,3})",
                    ],
                ),
                (
                    "senior_doctor",
                    80,
                    [
                        r"(?i)(?:chief dermatologist|senior dermatologist|lead dermatologist|consultant dermatologist|head dermatologist)[^A-Za-z]{0,24}(?:dr\.?\s*)?(?P<name>[A-Z][A-Za-z.\-]+(?:\s+[A-Z][A-Za-z.\-]+){0,3})",
                    ],
                ),
                (
                    "doctor",
                    65,
                    [
                        r"(?i)\bdr\.?\s+(?P<name>[A-Z][A-Za-z.\-]+(?:\s+[A-Z][A-Za-z.\-]+){0,3})",
                    ],
                ),
            ]
            for role, score, patterns in role_patterns:
                for pattern in patterns:
                    for match in re.finditer(pattern, raw_content):
                        name = self._normalize_person_name(match.group("name"))
                        if not name or not self._is_plausible_person_name(name):
                            continue
                        candidates.append(
                            {
                                "name": name,
                                "role": role,
                                "source": "website_copy",
                                "score": score,
                            }
                        )

        enable_external_people_search = (
            os.getenv("ZRAI_ENABLE_EXTERNAL_PEOPLE_SEARCH", "").strip().lower() == "true"
        )
        search_candidates = (
            self._search_decision_maker_candidates(
                business_name=business_name,
                location=str(lead.get("location") or ""),
            )
            if enable_external_people_search
            else []
        )
        candidates.extend(search_candidates)

        deduped_candidates: List[Dict[str, Any]] = []
        seen_names = set()
        for candidate in sorted(candidates, key=lambda item: item.get("score", 0), reverse=True):
            normalized_name = str(candidate.get("name") or "").strip().lower()
            if not normalized_name or normalized_name in seen_names:
                continue
            seen_names.add(normalized_name)
            deduped_candidates.append(candidate)

        if deduped_candidates:
            best_candidate = deduped_candidates[0]
            decision_maker["name"] = best_candidate.get("name")
            decision_maker["role"] = best_candidate.get("role")
            decision_maker["source"] = best_candidate.get("source")
            decision_maker["confidence"] = round(
                min(float(best_candidate.get("score", 0)) / 100.0, 0.98),
                2,
            )

            if best_candidate.get("linkedin"):
                decision_maker["linkedin"] = str(best_candidate.get("linkedin"))
            else:
                matched_linkedin = self._match_candidate_linkedin(
                    str(best_candidate.get("name") or ""),
                    linkedin_profiles,
                )
                if matched_linkedin:
                    decision_maker["linkedin"] = matched_linkedin
        elif linkedin_profiles:
            decision_maker["linkedin"] = linkedin_profiles[0]

        if not decision_maker.get("linkedin") and linkedin_profiles:
            decision_maker["linkedin"] = linkedin_profiles[0]

        return decision_maker

    def _extract_people_intelligence(
        self,
        lead: Dict[str, Any],
        website_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Build richer doctor/founder/contact intelligence from site content and public search."""
        website_context = website_context or {}
        raw_content = str(website_context.get("raw_content") or "")
        business_name = str(lead.get("business_name") or "").strip()
        location = str(lead.get("location") or "").strip()
        website = self._normalize_url(str(lead.get("website") or lead.get("landing_page_url") or "").strip()) if (lead.get("website") or lead.get("landing_page_url")) else None

        doctor_profiles = self._extract_doctor_profiles(raw_content)
        branch_contacts = self._extract_branch_contacts(raw_content)
        branch_names = [item.get("name") for item in branch_contacts if item.get("name")]
        for branch_name in self._extract_branch_names_from_page_text(raw_content):
            if branch_name not in branch_names:
                branch_names.append(branch_name)
        phone_numbers = [item.get("phone") for item in branch_contacts if item.get("phone")]
        branch_hints = self._extract_branch_hints_from_sources(
            business_name=business_name,
            website_context=website_context,
            web_results=list(lead.get("webResults") or lead.get("web_results") or []),
            related_places=list(lead.get("relatedPlaces") or lead.get("related_places") or []),
            maps_title=lead.get("maps_title"),
            maps_address=lead.get("maps_address") or lead.get("address"),
        )
        for branch_hint in branch_hints:
            if branch_hint not in branch_names:
                branch_names.append(branch_hint)

        extra_phone_candidates = [] if branch_contacts else list(website_context.get("phones", []))
        for phone in extra_phone_candidates:
            normalized = self._normalize_phone(phone)
            if normalized and normalized not in phone_numbers:
                phone_numbers.append(normalized)

        location_hint = location.lower()
        if any(token in location_hint for token in ("india", "bengaluru", "bangalore", "karnataka")):
            phone_numbers = [phone for phone in phone_numbers if str(phone).startswith("+91")]

        emails = self._validate_emails(list(website_context.get("emails", [])))
        social_profiles = website_context.get("social_profiles") or {}
        enable_external_people_search = (
            os.getenv("ZRAI_ENABLE_EXTERNAL_PEOPLE_SEARCH", "").strip().lower() == "true"
        )
        external_profiles = (
            self._search_people_profiles(
                business_name=business_name,
                location=location,
                candidate_names=[item.get("name") for item in doctor_profiles],
                website=website,
            )
            if enable_external_people_search
            else {}
        )

        merged_doctors: List[Dict[str, Any]] = []
        by_name: Dict[str, Dict[str, Any]] = {}
        for doctor in doctor_profiles:
            name = str(doctor.get("name") or "").strip()
            if not name:
                continue
            merged = dict(doctor)
            external = external_profiles.get(name.lower()) or {}
            if external.get("linkedin") and not merged.get("linkedin"):
                merged["linkedin"] = external.get("linkedin")
            if external.get("emails"):
                merged["emails"] = self._validate_emails(
                    list(merged.get("emails") or []) + list(external.get("emails") or [])
                )
            if external.get("phones"):
                merged["phones"] = self._dedupe_phones(
                    list(merged.get("phones") or []) + list(external.get("phones") or [])
                )
            by_name[name.lower()] = merged

        merged_doctors.extend(by_name.values())

        # Doctor IG enrichment: doctors with thousands of personal followers
        # are real demand/trust signal beyond the clinic IG handle. Up to 4
        # doctors get HTML-fallback metrics so scoring can include them.
        clinic_instagram_url = None
        for ig_url in (social_profiles.get("instagram") or []):
            if isinstance(ig_url, str) and ig_url.strip():
                clinic_instagram_url = ig_url
                break
        merged_doctors = self._enrich_doctor_instagram_profiles(
            merged_doctors,
            clinic_instagram_url=clinic_instagram_url,
            fast_mode=bool(getattr(self, "_fast_mode", False)),
        )

        decision_maker_candidates: List[Dict[str, Any]] = []
        founder_roles = {"founder", "co_founder", "director", "senior_doctor"}
        for doctor in merged_doctors:
            score = int(doctor.get("score") or 55)
            if doctor.get("role") in founder_roles:
                score += 15
            if doctor.get("linkedin"):
                score += 4
            if doctor.get("emails"):
                score += 4
            if doctor.get("phones"):
                score += 3
            candidate = {
                "name": doctor.get("name"),
                "role": doctor.get("role"),
                "source": doctor.get("source"),
                "score": min(score, 99),
                "linkedin": doctor.get("linkedin"),
                "emails": doctor.get("emails") or [],
                "phones": doctor.get("phones") or [],
                "clinic": doctor.get("clinic"),
            }
            decision_maker_candidates.append(candidate)

        decision_maker_candidates.sort(key=lambda item: int(item.get("score") or 0), reverse=True)
        decision_maker_candidates = self._dedupe_candidates(decision_maker_candidates)
        trusted_candidates: List[Dict[str, Any]] = []
        for candidate in decision_maker_candidates:
            candidate_name = self._normalize_person_name(candidate.get("name"))
            if not candidate_name or not self._is_plausible_person_name(candidate_name):
                continue
            role = str(candidate.get("role") or "").strip().lower()
            candidate_phones = self._dedupe_phones(candidate.get("phones") or [])
            candidate_emails = self._validate_emails(candidate.get("emails") or [])
            has_direct_evidence = bool(candidate_phones or candidate_emails or candidate.get("linkedin"))
            has_strong_role = role in {"founder", "co_founder", "co-founder", "director", "senior_doctor", "senior doctor"}
            if not has_direct_evidence and not has_strong_role:
                continue
            cleaned_candidate = dict(candidate)
            cleaned_candidate["name"] = candidate_name
            cleaned_candidate["phones"] = candidate_phones
            cleaned_candidate["emails"] = candidate_emails
            trusted_candidates.append(cleaned_candidate)
        decision_maker_candidates = trusted_candidates

        best_candidate = decision_maker_candidates[0] if decision_maker_candidates else {}
        best_contact_phone = None
        for candidate_phone in list(best_candidate.get("phones") or []) + phone_numbers:
            normalized = self._normalize_phone(candidate_phone)
            if normalized:
                best_contact_phone = normalized
                break

        best_contact_email = None
        for candidate_email in list(best_candidate.get("emails") or []) + emails:
            validated = self._validate_emails([candidate_email])
            if validated:
                best_contact_email = validated[0]
                break

        best_contact_linkedin = best_candidate.get("linkedin") or None
        doctor_names = self._dedupe_strings([item.get("name") for item in merged_doctors])
        cleaned_branch_names: List[str] = []
        for branch_name in branch_names:
            normalized_branch = self._normalize_branch_hint_candidate(branch_name)
            if normalized_branch and normalized_branch not in cleaned_branch_names:
                cleaned_branch_names.append(normalized_branch)
        branch_names = cleaned_branch_names
        phone_numbers = self._dedupe_phones(phone_numbers)
        contact_evidence = self._dedupe_strings(
            [
                *(f"{item.get('name')}: {item.get('phone')}" for item in branch_contacts if item.get("name") and item.get("phone")),
                *(f"{item.get('name')} ({item.get('role')})" for item in merged_doctors if item.get("name") and item.get("role")),
            ]
        )

        return {
            "doctor_names": doctor_names,
            "doctor_profiles": merged_doctors[:8],
            "branch_names": branch_names,
            "branch_contacts": branch_contacts[:8],
            "phone_numbers": phone_numbers,
            "emails": emails,
            "social_profiles": social_profiles,
            "decision_maker_candidates": decision_maker_candidates[:6],
            "decision_maker_name": best_candidate.get("name"),
            "decision_maker_role": best_candidate.get("role"),
            "decision_maker_linkedin": best_contact_linkedin,
            "best_contact_phone": best_contact_phone,
            "best_contact_email": best_contact_email,
            "best_contact_linkedin": best_contact_linkedin,
            "contact_evidence": contact_evidence[:8],
        }

    def _extract_branch_hints_from_sources(
        self,
        *,
        business_name: str,
        website_context: Dict[str, Any],
        web_results: List[Dict[str, Any]],
        related_places: List[Dict[str, Any]],
        maps_title: Optional[str],
        maps_address: Optional[str],
    ) -> List[str]:
        candidates: List[str] = []
        if maps_address:
            candidates.append(str(maps_address))
        for result in related_places:
            if not isinstance(result, dict):
                continue
            if not self._source_text_matches_business(
                " ".join(
                    [
                        str(result.get("title") or result.get("name") or ""),
                        str(result.get("website") or ""),
                        str(result.get("url") or ""),
                        str(result.get("address") or ""),
                    ]
                ),
                business_name,
            ):
                continue
            if result.get("address"):
                candidates.append(str(result.get("address")))

        hints: List[str] = []
        seen = set()
        for candidate in candidates:
            hint = self._extract_branch_hint_from_text(candidate, business_name)
            if not hint:
                continue
            key = hint.lower()
            if key in seen:
                continue
            seen.add(key)
            hints.append(hint)
        return hints[:4]

    def _source_text_matches_business(self, text: str, business_name: str) -> bool:
        haystack = str(text or "").lower()
        if not haystack.strip():
            return False

        blocked = {
            "clinic",
            "clinics",
            "skin",
            "hair",
            "laser",
            "care",
            "center",
            "centre",
            "aesthetic",
            "aesthetics",
            "cosmetic",
            "doctor",
            "doctors",
            "specialist",
            "specialists",
            "best",
            "top",
            "premium",
            "bangalore",
            "bengaluru",
        }
        tokens = [
            token
            for token in re.findall(r"[a-z0-9]+", business_name.lower())
            if len(token) > 2 and token not in blocked
        ]
        if not tokens:
            return True
        matched = sum(1 for token in tokens if token in haystack)
        required = 1 if len(tokens) <= 2 else 2
        return matched >= required

    def _extract_branch_hint_from_text(self, text: str, business_name: str) -> Optional[str]:
        value = str(text or "").strip()
        if not value:
            return None

        lowered = value.lower()
        business_tokens = {
            token
            for token in re.findall(r"[a-z]+", business_name.lower())
            if len(token) > 2
        }
        generic_tokens = {
            "clinic",
            "clinics",
            "skin",
            "hair",
            "and",
            "the",
            "best",
            "near",
            "me",
            "dermatologist",
            "cosmetic",
            "aesthetic",
            "doctor",
            "doctors",
            "branch",
            "branches",
            "centre",
            "center",
            "care",
            "hospital",
            "treatment",
            "treatments",
        }

        direct_match = re.search(r"\bin\s+([a-z][a-z\s]{2,30})(?:,| -|\|)", lowered)
        if direct_match:
            normalized = self._normalize_branch_hint_candidate(direct_match.group(1))
            if normalized:
                return normalized
        address_match = re.search(
            r"([a-z][a-z\s]{2,40})\s*,\s*(?:bengaluru|bangalore)\b",
            lowered,
        )
        if address_match:
            normalized = self._normalize_branch_hint_candidate(address_match.group(1))
            if normalized:
                return normalized
        title_match = re.search(r"-\s*([a-z][a-z\s]{2,30})(?:,|:)", lowered)
        if title_match:
            normalized = self._normalize_branch_hint_candidate(title_match.group(1))
            if normalized:
                return normalized

        parsed = urlparse(value if value.startswith(("http://", "https://")) else f"https://example.com/{value.lstrip('/')}")
        segments = [unquote(segment) for segment in parsed.path.split("/") if segment]
        for segment in reversed(segments):
            tokens = [
                token
                for token in re.split(r"[-_]+", segment.lower())
                if token and token not in generic_tokens and token not in business_tokens and len(token) > 1
            ]
            if not tokens:
                continue
            for alias, canonical in BRANCH_LOCALITY_ALIASES.items():
                alias_tokens = alias.split()
                if all(token in tokens for token in alias_tokens):
                    return canonical
            normalized = self._normalize_branch_hint_candidate(" ".join(tokens[-3:]))
            if normalized:
                return normalized

        return None

    def _normalize_branch_hint_candidate(self, value: str) -> Optional[str]:
        text = re.sub(r"\s+", " ", str(value or "")).strip(" -,:;/")
        if not text:
            return None
        lowered = text.lower()
        if any(token in lowered for token in ("http://", "https://", "wp-content", ".jpg", ".jpeg", ".png", ".webp")):
            return None
        if any(symbol in text for symbol in ("[", "]", "(", ")", "/")):
            return None
        if len(text) > 80 or len(re.findall(r"[A-Za-z]+", text)) > 9:
            if not re.search(r"\d", text) and not re.search(r"\b(?:bangalor|bengalur|nagar|layout|road|cross|main|block|phase|stage)\b", lowered):
                return None
            if any(
                token in lowered
                for token in (
                    " brings ",
                    " holding ",
                    " specializes ",
                    " specialising ",
                    " dedicated ",
                    " provides ",
                    " receive ",
                    " patient ",
                    " concerns ",
                    " guidance ",
                    " under the ",
                )
            ):
                return None
        for alias, canonical in BRANCH_LOCALITY_ALIASES.items():
            if alias in lowered:
                return canonical
        if self._is_plausible_branch_name(text):
            return text.title()
        return None

    def _extract_branch_names_from_page_text(self, raw_content: str) -> List[str]:
        if not raw_content:
            return []

        text_content = BeautifulSoup(raw_content, "html.parser").get_text("\n")
        text_content = re.sub(r"\r", "\n", text_content)
        text_content = re.sub(r"\n{2,}", "\n", text_content)
        lines = [line.strip() for line in text_content.splitlines() if line.strip()]

        candidates: List[str] = []
        seen = set()
        for index, line in enumerate(lines):
            if len(line) > 90 or len(line.split()) > 10 or line.endswith("."):
                continue
            if line.lower() == "location":
                window_lines = lines[index + 1 : min(len(lines), index + 5)]
                for candidate_line in window_lines:
                    canonical = self._extract_branch_hint_from_text(candidate_line, "")
                    if not canonical:
                        continue
                    key = canonical.lower()
                    if key not in seen:
                        seen.add(key)
                        candidates.append(canonical)
                continue
            canonical = self._normalize_branch_hint_candidate(line)
            if not canonical:
                continue
            lowered_line = line.lower()
            if lowered_line in {"our clinic locations", "clinic locations", "our clinics", "locations"}:
                continue

            window_text = "\n".join(lines[max(0, index - 2) : min(len(lines), index + 8)]).lower()
            if not any(
                token in window_text
                for token in ("clinic", "location", "our clinics", "our clinic locations", "branch", "branches", "dermatologist")
            ):
                continue

            key = canonical.lower()
            if key in seen:
                continue
            seen.add(key)
            candidates.append(canonical)

        return candidates[:8]

    def _extract_doctor_profiles(self, raw_content: str) -> List[Dict[str, Any]]:
        profiles: List[Dict[str, Any]] = []
        if not raw_content:
            return profiles

        object_pattern = re.compile(
            r'\{name:"(?P<name>Dr\.[^"]+)"(?:,experience:"(?P<experience>[^"]+)")?(?:,specialty:"(?P<specialty>[^"]+)")?',
            flags=re.IGNORECASE,
        )
        simple_object_pattern = re.compile(
            r'\{name:"(?P<name>Dr\.[^"]+)"(?:,[^{}]{0,180})?\}',
            flags=re.IGNORECASE,
        )
        for match in object_pattern.finditer(raw_content):
            profile = self._build_doctor_profile_from_match(
                name=match.group("name"),
                specialty=match.group("specialty"),
                experience=match.group("experience"),
                source="website_asset",
                raw_context=match.group(0),
            )
            if profile:
                profiles.append(profile)

        for match in simple_object_pattern.finditer(raw_content):
            profile = self._build_doctor_profile_from_match(
                name=match.group("name"),
                specialty=None,
                experience=None,
                source="website_asset",
                raw_context=match.group(0),
            )
            if profile:
                profiles.append(profile)

        text_content = BeautifulSoup(raw_content, "html.parser").get_text("\n")
        text_content = re.sub(r"\r", "\n", text_content)
        text_content = re.sub(r"\n{2,}", "\n", text_content)
        heading_pattern = re.compile(
            r"(?P<name>Dr\.?[ \t]+[A-Z][A-Za-z.\-]*(?:[ \t]+[A-Z][A-Za-z.\-]*){0,4})",
            flags=re.IGNORECASE,
        )
        for match in heading_pattern.finditer(text_content):
            start, end = match.span()
            before_window = text_content[max(0, start - 40) : start]
            after_window = text_content[end : min(len(text_content), end + 260)]
            window = f"{before_window}\n{match.group('name')}\n{after_window}"
            lower_window = window.lower()
            if not any(
                token in lower_window
                for token in ("our doctors", "dermatologist", "cosmetologist", "founder", "director", "doctor")
            ):
                continue

            lines = [line.strip() for line in after_window.splitlines() if line.strip()]
            specialty = next(
                (
                    line
                    for line in lines
                    if any(
                        token in line.lower()
                        for token in ("dermatologist", "cosmetologist", "founder", "director", "doctor")
                    )
                ),
                None,
            )
            experience = next(
                (
                    line
                    for line in lines
                    if re.search(r"\b(?:mbbs|md|dvd|dnb|ms|mch)\b", line, flags=re.IGNORECASE)
                ),
                None,
            )
            profile = self._build_doctor_profile_from_match(
                name=match.group("name"),
                specialty=specialty,
                experience=experience,
                source="website_page",
                raw_context=window,
            )
            if profile:
                profiles.append(profile)

        deduped: List[Dict[str, Any]] = []
        seen = set()
        for profile in sorted(profiles, key=lambda item: int(item.get("score") or 0), reverse=True):
            key = str(profile.get("name") or "").strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            deduped.append(profile)
        return deduped

    def _build_doctor_profile_from_match(
        self,
        *,
        name: Optional[str],
        specialty: Optional[str],
        experience: Optional[str],
        source: str,
        raw_context: str,
    ) -> Optional[Dict[str, Any]]:
        normalized_name = self._normalize_person_name(name)
        if not normalized_name or not self._is_plausible_person_name(normalized_name):
            return None

        lower_context = str(raw_context or "").lower()
        lower_specialty = str(specialty or "").lower()
        explicit_dr_prefix = bool(re.search(r"\bdr\.?\s+", str(name or ""), flags=re.IGNORECASE))
        role = "doctor"
        score = 64
        if "co-founder" in lower_specialty or "co founder" in lower_specialty:
            role = "co_founder"
            score = 95
        elif "founder" in lower_specialty or "founder" in lower_context:
            role = "founder"
            score = 98
        elif "director" in lower_specialty or "director" in lower_context:
            role = "director"
            score = 90
        elif any(token in lower_specialty for token in ["senior", "chief", "lead", "consultant"]):
            role = "senior_doctor"
            score = 80

        clinic_match = re.search(
            r"(?i)iSkin\s+(?P<clinic>[A-Z][A-Za-z]+)",
            specialty or raw_context or "",
        )
        clinic = clinic_match.group("clinic") if clinic_match else None
        if clinic and clinic.lower() == "clinic":
            clinic = None
        phones = self._dedupe_phones(re.findall(r"\b\d{10}\b", raw_context or ""))
        emails = self._validate_emails(re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", raw_context or ""))
        has_supporting_context = bool(
            specialty
            or experience
            or phones
            or emails
            or any(
                token in lower_context
                for token in (
                    "doctor",
                    "dermat",
                    "physician",
                    "surgeon",
                    "founder",
                    "director",
                    "consultant",
                    "specialty",
                )
            )
        )
        if not has_supporting_context:
            return None

        return {
            "name": normalized_name,
            "role": role,
            "clinic": clinic,
            "specialty": specialty,
            "experience": experience,
            "source": source,
            "score": score,
            "phones": phones,
            "emails": emails,
            "explicit_dr_prefix": explicit_dr_prefix,
            "instagram_url": self._extract_instagram_handle_from_context(raw_context),
        }

    def _extract_instagram_handle_from_context(self, raw_context: Optional[str]) -> Optional[str]:
        """Extract a doctor-attached Instagram handle/URL from a raw_context window.

        Doctors with thousands of personal followers count as DEMAND/TRUST proof
        (not just the clinic IG handle). We look for the first plausible IG URL
        or @handle adjacent to the doctor's bio text. We deliberately reject
        the generic clinic handle later by deduping at the call site.
        """
        if not raw_context:
            return None
        text = str(raw_context)
        # Direct instagram.com URLs first.
        url_match = re.search(
            r"https?://(?:www\.)?instagram\.com/([A-Za-z0-9._]+)",
            text,
            flags=re.IGNORECASE,
        )
        if url_match:
            handle = url_match.group(1).strip("/").strip(".")
            if handle and not self._is_gps_coordinate_handle(handle):
                return f"https://www.instagram.com/{handle}/"
        # Fallback: @handle near "instagram"/"insta" mention.
        nearby = re.search(
            r"(?:instagram|insta|ig)\b[^@a-zA-Z0-9]{0,30}@?([A-Za-z][A-Za-z0-9._]{2,29})",
            text,
            flags=re.IGNORECASE,
        )
        if nearby:
            handle = nearby.group(1).strip("/").strip(".")
            if handle and not self._is_gps_coordinate_handle(handle):
                return f"https://www.instagram.com/{handle}/"
        return None

    @staticmethod
    def _is_gps_coordinate_handle(handle: str) -> bool:
        """Reject GPS-coordinate-looking strings (e.g. 17.4456,78.4123)."""
        return bool(re.match(r"^[\d\.,\-]+$", handle))

    def _enrich_doctor_instagram_profiles(
        self,
        doctors: List[Dict[str, Any]],
        *,
        clinic_instagram_url: Optional[str] = None,
        fast_mode: bool = False,
    ) -> List[Dict[str, Any]]:
        """For each doctor with an IG handle, fetch lightweight HTML metrics.

        Doctors with personal IG followings are real demand/trust signal -
        many clinics ride on a doctor's brand. We enrich up to 4 doctors so
        scoring can use their followers/posts. Skips:
          - the clinic IG handle (already enriched separately)
          - GPS-coordinate-looking strings
          - fast_mode runs (HTML fetch is too slow for bulk scans)
        """
        if fast_mode or not doctors:
            return doctors
        clinic_handle = self._extract_instagram_username(clinic_instagram_url or "") or ""
        clinic_handle = clinic_handle.lower().strip("/").strip(".")
        enriched_count = 0
        for doctor in doctors:
            if enriched_count >= 4:
                break
            ig_url = doctor.get("instagram_url")
            if not ig_url:
                continue
            doctor_handle = (self._extract_instagram_username(ig_url) or "").lower().strip("/").strip(".")
            if not doctor_handle or doctor_handle == clinic_handle:
                continue
            try:
                snapshot = self._fetch_instagram_profile_snapshot(ig_url)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Doctor IG snapshot failed for %s: %s", doctor_handle, exc)
                snapshot = {}
            if snapshot:
                # Sparse-Apify guard mirror: keep all keys with real values,
                # never overwrite a positive metric with an empty fallback.
                doctor_profile: Dict[str, Any] = {
                    "username": doctor_handle,
                    "profile_url": ig_url,
                    "source": snapshot.get("source") or "instagram_public_html",
                    "owner": "doctor",
                    "doctor_name": doctor.get("name"),
                }
                for key in ("full_name", "followers_count", "following_count", "posts_count"):
                    val = snapshot.get(key)
                    if val not in (None, "", [], {}):
                        doctor_profile[key] = val
                doctor["instagram_profile"] = doctor_profile
                enriched_count += 1
        return doctors

    def _extract_branch_contacts(self, raw_content: str) -> List[Dict[str, Any]]:
        contacts: List[Dict[str, Any]] = []
        if not raw_content:
            return contacts

        branch_pattern = re.compile(
            r'\{name:"(?P<name>[A-Za-z][A-Za-z\s]+)",phone:"(?P<phone>\d{8,15})"\}',
            flags=re.IGNORECASE,
        )
        for match in branch_pattern.finditer(raw_content):
            name = re.sub(r"\s+", " ", str(match.group("name") or "")).strip()
            phone = self._normalize_phone(match.group("phone"))
            if not name or not phone or not self._is_plausible_branch_name(name):
                continue
            canonical_name = self._normalize_branch_hint_candidate(name) or name
            contacts.append(
                {
                    "name": canonical_name,
                    "phone": phone,
                    "source": "website_asset",
                }
            )

        text_content = BeautifulSoup(raw_content, "html.parser").get_text("\n")
        text_content = re.sub(r"\r", "\n", text_content)
        text_content = re.sub(r"\n{2,}", "\n", text_content)
        lines = [line.strip() for line in text_content.splitlines() if line.strip()]
        for index, line in enumerate(lines):
            if not self._is_plausible_branch_name(line):
                continue
            window_lines = lines[index : index + 16]
            window_text = "\n".join(window_lines)
            phones = self._dedupe_phones(
                re.findall(r"(?:\+?\d[\d\s().-]{7,16}\d)", window_text, flags=re.IGNORECASE)
            )
            if not phones:
                continue
            canonical_name = self._normalize_branch_hint_candidate(line) or line
            contacts.append(
                {
                    "name": canonical_name,
                    "phone": phones[0],
                    "source": "website_page",
                }
            )

        deduped: List[Dict[str, Any]] = []
        seen = set()
        for contact in contacts:
            phone_key = str(contact.get("phone") or "")
            name_key = str(contact.get("name") or "").lower()
            key = ("name", name_key) if name_key else ("phone", phone_key)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(contact)
        return deduped[:6]

    def _is_plausible_branch_name(self, value: str) -> bool:
        normalized = re.sub(r"\s+", " ", str(value or "")).strip(" -,:;")
        if not normalized:
            return False
        lowered = normalized.lower()
        if "@" in lowered or lowered.startswith("http"):
            return False
        has_known_locality = any(alias in lowered for alias in BRANCH_LOCALITY_ALIASES)
        if len(normalized) > 140:
            return False
        if re.search(r"\b\d{5,6}\b", lowered) and not has_known_locality:
            return False
        if re.search(r"\b(?:bangalore|bengaluru)\b", lowered) and not has_known_locality:
            return False
        blocked_terms = {
            "about us",
            "contact us",
            "book appointment",
            "book your appointment",
            "treatments",
            "treatment",
            "gallery",
            "offers",
            "offer",
            "popular treatments",
            "latest offers",
            "photo facial",
            "chemical peel",
            "laser hair",
            "microdermabrasion",
            "success stories",
            "testimonials",
            "consultant",
            "dermatologist",
            "specialist",
            "doctor",
            "physician",
            "surgeon",
            "receptionist",
            "manager",
            "admin",
            "book",
            "appointment",
            "call",
            "email",
            "phone",
        }
        if any(term in lowered for term in blocked_terms):
            return False
        location_tokens = (
            "nagar",
            "layout",
            "road",
            "rd",
            "block",
            "phase",
            "cross",
            "main",
            "koramangala",
            "jayanagar",
            "indiranagar",
            "whitefield",
            "hsr",
            "jp",
            "bengaluru",
            "bangalore",
            "sarjapur",
            "thanisandra",
            "chikkabellandur",
        )
        if not has_known_locality and not any(token in lowered for token in location_tokens):
            return False
        if not has_known_locality and any(token in lowered for token in ("road", "rd", "cross", "main", "block", "phase")):
            return False
        return True

    def _search_people_profiles(
        self,
        *,
        business_name: str,
        location: str,
        candidate_names: Iterable[Optional[str]],
        website: Optional[str] = None,
    ) -> Dict[str, Dict[str, Any]]:
        results: Dict[str, Dict[str, Any]] = {}
        website_host = ""
        if website:
            parsed = urlparse(website)
            website_host = (parsed.netloc or "").lower().removeprefix("www.")

        filtered_names = []
        for candidate_name in candidate_names:
            name = self._normalize_person_name(candidate_name)
            if name and self._is_plausible_person_name(name) and name not in filtered_names:
                filtered_names.append(name)

        for name in filtered_names[:4]:
            aggregated = results.setdefault(name.lower(), {"name": name, "phones": [], "emails": []})
            queries = [
                f'"{name}" "{business_name}" linkedin {location}'.strip(),
                f'"{name}" "{business_name}" dermatologist {location}'.strip(),
            ]
            for query in queries:
                for result in self._fetch_search_results(query, max_results=5):
                    url = str(result.get("url") or "")
                    title = str(result.get("title") or "")
                    snippet = str(result.get("snippet") or "")
                    haystack = " ".join([title, snippet])
                    if "linkedin.com/" in url.lower() and not aggregated.get("linkedin"):
                        aggregated["linkedin"] = url
                    if website_host and website_host in url.lower():
                        aggregated.setdefault("source_urls", [])
                        if url not in aggregated["source_urls"]:
                            aggregated["source_urls"].append(url)
                    if any(host in url.lower() for host in PUBLIC_DIRECTORY_HOST_HINTS):
                        aggregated.setdefault("source_urls", [])
                        if url not in aggregated["source_urls"]:
                            aggregated["source_urls"].append(url)
                    for email in self._validate_emails(
                        re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", haystack)
                    ):
                        if email not in aggregated["emails"]:
                            aggregated["emails"].append(email)
                    for phone in self._dedupe_phones(re.findall(r"(?:\+?\d[\d\s().-]{8,}\d)", haystack)):
                        if phone not in aggregated["phones"]:
                            aggregated["phones"].append(phone)

        return results

    def _dedupe_phones(self, values: Iterable[Optional[str]]) -> List[str]:
        deduped: List[str] = []
        seen = set()
        for value in values:
            normalized = self._normalize_phone(value)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            deduped.append(normalized)
        return deduped

    def _dedupe_strings(self, values: Iterable[Optional[str]]) -> List[str]:
        deduped: List[str] = []
        seen = set()
        for value in values:
            normalized = str(value or "").strip()
            if not normalized or normalized.lower() in seen:
                continue
            seen.add(normalized.lower())
            deduped.append(normalized)
        return deduped

    def _dedupe_candidates(self, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        deduped: List[Dict[str, Any]] = []
        seen = set()
        for candidate in candidates:
            name = str(candidate.get("name") or "").strip().lower()
            if not name or name in seen:
                continue
            seen.add(name)
            deduped.append(candidate)
        return deduped

    def _extract_social_profiles(self, raw_content: str) -> Dict[str, List[str]]:
        """Extract obvious social/profile URLs from scraped website content."""
        social_patterns = {
            "linkedin": r"https?://(?:[a-z]{2,3}\.)?linkedin\.com/[^\s\"'<>]+",
            "instagram": r"https?://(?:www\.)?instagram\.com/[^\s\"'<>]+",
            "facebook": r"https?://(?:www\.)?facebook\.com/[^\s\"'<>]+",
            "youtube": r"https?://(?:www\.)?(?:youtube\.com|youtu\.be)/[^\s\"'<>]+",
        }

        profiles: Dict[str, List[str]] = {}
        for network, pattern in social_patterns.items():
            matches = [match.rstrip(".,);") for match in re.findall(pattern, raw_content, flags=re.IGNORECASE)]
            deduped = []
            for match in matches:
                normalized = match
                if network == "instagram":
                    normalized = self._normalize_instagram_profile_url(match)
                elif network == "youtube":
                    normalized = self._normalize_youtube_channel_url(match)
                elif network == "facebook" and "facebook.com" not in match.lower():
                    normalized = None
                if normalized and normalized not in deduped:
                    deduped.append(normalized)
            if deduped:
                profiles[network] = deduped[:4]

        soup = BeautifulSoup(raw_content, "html.parser")
        social_presence_flags = {
            "instagram_present": False,
            "youtube_present": False,
            "facebook_present": False,
        }
        for anchor in soup.find_all("a"):
            href = str(anchor.get("href") or "").strip()
            classes = " ".join(anchor.get("class") or []).lower()
            label = anchor.get_text(" ", strip=True).lower()
            haystack = " ".join([href.lower(), classes, label])
            if "instagram" in haystack:
                social_presence_flags["instagram_present"] = True
                normalized = self._normalize_instagram_profile_url(href)
                if normalized:
                    instagram_profiles = list(profiles.get("instagram") or [])
                    if normalized not in instagram_profiles:
                        instagram_profiles.append(normalized)
                    profiles["instagram"] = instagram_profiles[:6]
            if "youtube" in haystack:
                social_presence_flags["youtube_present"] = True
                normalized = self._normalize_youtube_channel_url(href)
                if normalized:
                    youtube_profiles = list(profiles.get("youtube") or [])
                    if normalized not in youtube_profiles:
                        youtube_profiles.append(normalized)
                    profiles["youtube"] = youtube_profiles[:6]
            if "facebook" in haystack:
                social_presence_flags["facebook_present"] = True
                if href and "facebook.com" in href.lower():
                    facebook_profiles = list(profiles.get("facebook") or [])
                    if href not in facebook_profiles:
                        facebook_profiles.append(href)
                    profiles["facebook"] = facebook_profiles[:6]

        instagram_handles = re.findall(
            r"(?<![A-Za-z0-9._])@(?P<handle>[A-Za-z0-9._]{4,30})\b",
            raw_content,
            flags=re.IGNORECASE,
        )
        if instagram_handles:
            instagram_profiles = list(profiles.get("instagram") or [])
            for handle in instagram_handles:
                normalized = self._normalize_instagram_profile_url(f"@{handle}")
                if normalized and normalized not in instagram_profiles:
                    instagram_profiles.append(normalized)
            if instagram_profiles:
                profiles["instagram"] = instagram_profiles[:6]

        for key, present in social_presence_flags.items():
            if present:
                profiles[key] = True

        return profiles

    def _normalize_person_name(self, value: Optional[str]) -> Optional[str]:
        if not value:
            return None

        normalized = re.sub(r"(?i)\bdr\.?\s*", "", str(value))
        normalized = re.sub(r"[^A-Za-z.\-\s]", " ", normalized)
        normalized = re.sub(r"\s+", " ", normalized).strip(" .,-")
        if not normalized:
            return None

        parts = [part for part in normalized.split(" ") if part]
        if len(parts) > 5:
            return None
        return " ".join(parts)

    def _extract_person_name_from_business_name(self, business_name: str) -> Optional[str]:
        if not business_name:
            return None

        dr_match = re.search(
            r"(?i)\bdr\.?\s+(?P<name>[A-Z][A-Za-z.\-]+(?:\s+[A-Z][A-Za-z.\-]+){1,3})",
            business_name,
        )
        if dr_match:
            name = self._normalize_person_name(dr_match.group("name"))
            if name and self._is_plausible_person_name(name):
                return name
        return None

    def _is_plausible_person_name(self, value: str) -> bool:
        tokens = [token.strip(".").lower() for token in value.split() if token.strip(".")]
        token_fragments = [
            fragment.lower()
            for token in value.split()
            for fragment in token.split(".")
            if fragment.strip(".-")
        ]
        significant_tokens = [token for token in token_fragments if len(token) > 1]
        has_embedded_initial = any(
            "." in token and len(token.replace(".", "").strip()) > 3
            for token in value.split()
        )
        has_initial_token = any(len(token.strip(".-")) == 1 for token in value.split())
        if len(significant_tokens) < 2 and not has_embedded_initial and not (significant_tokens and has_initial_token):
            return False
        original_tokens = [token for token in re.split(r"\s+", value.strip()) if token]
        for token in original_tokens:
            cleaned = token.strip(".-")
            if len(cleaned) == 1:
                continue
            if cleaned.isupper():
                continue
            if not cleaned[:1].isupper():
                return False
        if self._looks_like_business_label(value):
            return False
        return True

    def _looks_like_business_label(self, value: str) -> bool:
        tokens = [token.strip(".").lower() for token in value.split() if token.strip(".")]
        if not tokens:
            return True

        blocked = {
            "clinic",
            "skin",
            "hair",
            "laser",
            "care",
            "center",
            "centre",
            "hospital",
            "dermatology",
            "aesthetics",
            "aesthetic",
        }
        if all(token in blocked for token in tokens):
            return True
        if any(token.isdigit() for token in tokens):
            return True
        return False

    def _normalize_search_result_url(self, raw_url: str) -> Optional[str]:
        if not raw_url:
            return None

        parsed = urlparse(raw_url)
        if "duckduckgo.com" in (parsed.netloc or "").lower() and parsed.path.startswith("/l/"):
            uddg_values = parse_qs(parsed.query).get("uddg", [])
            if uddg_values:
                raw_url = unquote(uddg_values[0])
                parsed = urlparse(raw_url)

        if parsed.scheme not in {"http", "https"}:
            if raw_url.startswith("//"):
                return self._normalize_search_result_url(f"https:{raw_url}")
            return None

        return f"{parsed.scheme}://{parsed.netloc}{parsed.path or ''}"

    def _fetch_search_results(self, query: str, max_results: int = 6) -> List[Dict[str, str]]:
        brave_api_key = os.getenv("BRAVE_API_KEY")
        if brave_api_key:
            try:
                response = requests.get(
                    BRAVE_SEARCH_API_URL,
                    params={"q": query, "count": max(1, min(max_results, 10)), "search_lang": "en"},
                    headers={
                        **DISCOVERY_HTTP_HEADERS,
                        "Accept": "application/json",
                        "X-Subscription-Token": brave_api_key,
                    },
                    timeout=20,
                )
                response.raise_for_status()
                payload = response.json()
                results: List[Dict[str, str]] = []
                for item in payload.get("web", {}).get("results", []):
                    normalized = self._normalize_search_result_url(item.get("url") or "")
                    if not normalized:
                        continue
                    results.append(
                        {
                            "title": str(item.get("title") or ""),
                            "snippet": str(item.get("description") or ""),
                            "url": normalized,
                        }
                    )
                    if len(results) >= max_results:
                        break
                if results:
                    return results
            except Exception as exc:
                self._logger.warning("Brave search failed for %s: %s", query, exc)

        try:
            response = requests.get(
                "https://html.duckduckgo.com/html/",
                params={"q": query},
                headers=DISCOVERY_HTTP_HEADERS,
                timeout=20,
            )
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            results: List[Dict[str, str]] = []
            for anchor in soup.select("a.result__a"):
                normalized = self._normalize_search_result_url(anchor.get("href") or "")
                if not normalized:
                    continue
                container = anchor.find_parent("div", class_="result")
                snippet_node = container.select_one(".result__snippet") if container else None
                results.append(
                    {
                        "title": anchor.get_text(" ", strip=True),
                        "snippet": snippet_node.get_text(" ", strip=True) if snippet_node else "",
                        "url": normalized,
                    }
                )
                if len(results) >= max_results:
                    break
            return results
        except Exception as exc:
            self._logger.warning("DuckDuckGo search failed for %s: %s", query, exc)
            return []

    def _search_decision_maker_candidates(self, business_name: str, location: str) -> List[Dict[str, Any]]:
        if not business_name:
            return []

        queries = [
            f'"{business_name}" founder {location}'.strip(),
            f'"{business_name}" owner dermatologist {location}'.strip(),
            f'"{business_name}" linkedin doctor {location}'.strip(),
        ]

        candidates: List[Dict[str, Any]] = []
        role_patterns = [
            ("founder", 88, r"(?i)(?:founder|co[-\s]?founder|owner|promoter)[^A-Za-z]{0,24}(?:dr\.?\s*)?(?P<name>[A-Z][A-Za-z.\-]+(?:\s+[A-Z][A-Za-z.\-]+){1,3})"),
            ("director", 82, r"(?i)(?:director|medical director|managing director)[^A-Za-z]{0,24}(?:dr\.?\s*)?(?P<name>[A-Z][A-Za-z.\-]+(?:\s+[A-Z][A-Za-z.\-]+){1,3})"),
            ("doctor", 68, r"(?i)\bdr\.?\s+(?P<name>[A-Z][A-Za-z.\-]+(?:\s+[A-Z][A-Za-z.\-]+){1,3})"),
        ]

        for query in queries:
            for result in self._fetch_search_results(query, max_results=5):
                text = " ".join([result.get("title") or "", result.get("snippet") or ""])
                for role, score, pattern in role_patterns:
                    for match in re.finditer(pattern, text):
                        name = self._normalize_person_name(match.group("name"))
                        if not name or not self._is_plausible_person_name(name):
                            continue
                        candidate: Dict[str, Any] = {
                            "name": name,
                            "role": role,
                            "source": "search_result",
                            "score": score,
                        }
                        if "linkedin.com/" in (result.get("url") or "").lower():
                            candidate["linkedin"] = result.get("url")
                            candidate["score"] += 4
                        candidates.append(candidate)

                if "linkedin.com/" in (result.get("url") or "").lower():
                    title = str(result.get("title") or "")
                    title_prefix = title.split("|")[0].split("-")[0].strip()
                    linkedin_name = self._normalize_person_name(title_prefix)
                    if linkedin_name and self._is_plausible_person_name(linkedin_name):
                        candidates.append(
                            {
                                "name": linkedin_name,
                                "role": "linkedin_profile",
                                "source": "search_result",
                                "score": 72,
                                "linkedin": result.get("url"),
                            }
                        )

        return candidates

    def _match_candidate_linkedin(self, candidate_name: str, linkedin_profiles: List[str]) -> Optional[str]:
        if not candidate_name or not linkedin_profiles:
            return linkedin_profiles[0] if linkedin_profiles else None

        slug_tokens = [token.lower() for token in re.findall(r"[A-Za-z]+", candidate_name) if len(token) > 1]
        for profile in linkedin_profiles:
            lowered = profile.lower()
            if slug_tokens and all(token in lowered for token in slug_tokens[:2]):
                return profile
        return linkedin_profiles[0]

    def _extract_key_services(self, raw_content: str) -> List[str]:
        """Extract obvious clinic service signals from website content."""
        service_map = {
            "skin treatment": ["skin treatment", "skin rejuvenation", "facial"],
            "laser hair removal": ["laser hair removal", "laser hair reduction"],
            "hair transplant": ["hair transplant", "hair restoration", "gfc hair"],
            "botox": ["botox"],
            "fillers": ["dermal filler", "fillers"],
            "acne treatment": ["acne treatment", "acne scar"],
            "pigmentation treatment": ["pigmentation", "melasma"],
            "anti-aging": ["anti aging", "anti-aging", "age reversal"],
        }

        lowered = raw_content.lower()
        services: List[str] = []
        for label, tokens in service_map.items():
            if any(token in lowered for token in tokens):
                services.append(label)
        return services[:6]

    def _persist_people_intelligence(
        self,
        state: LeadGraphState,
        people_intelligence: Dict[str, Any],
    ) -> None:
        lead_id = state.get("lead_id") or (state.get("lead") or {}).get("lead_id")
        if not lead_id or not people_intelligence:
            return

        try:
            lead_uuid = UUID(str(lead_id))
        except Exception:
            return

        existing_state = self._db.get_lead_state(lead_uuid) or {}
        metadata = dict(existing_state.get("metadata") or {})
        metadata["people_intelligence"] = people_intelligence
        self._db.save_lead_state(
            {
                "lead_id": str(lead_uuid),
                "current_stage": state.get("current_stage") or existing_state.get("current_stage") or "enrichment",
                "last_node": state.get("last_node") or existing_state.get("last_node") or self.name,
                "last_error": existing_state.get("last_error"),
                "retry_count": existing_state.get("retry_count", 0),
                "metadata": metadata,
            }
        )

    def _extract_first_link(self, html: str, keywords: List[str]) -> Optional[str]:
        """Return the first href matching any keyword."""
        href_matches = re.findall(r'href=["\']([^"\']+)["\']', html, re.IGNORECASE)
        lowered_keywords = [keyword.lower() for keyword in keywords]
        for href in href_matches:
            lowered_href = href.lower()
            if any(keyword in lowered_href for keyword in lowered_keywords):
                return href
        return None

    def _extract_whatsapp_target(self, html: str) -> Optional[str]:
        """Return a strong WhatsApp target, not just a loose text mention."""
        href_matches = re.findall(r'href=["\']([^"\']+)["\']', html, re.IGNORECASE)
        for href in href_matches:
            lowered = href.lower()
            if (
                "wa.me/" in lowered
                or "api.whatsapp.com" in lowered
                or "whatsapp://send" in lowered
                or "web.whatsapp.com/send" in lowered
            ):
                phone_match = re.search(
                    r"(?:phone=|wa\.me/|send\?phone=)(\+?\d{7,15})",
                    href,
                    re.IGNORECASE,
                )
                if phone_match:
                    return phone_match.group(1)
                return href

        return None
    
    def _extract_volume_signals(self, lead: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract volume signals from Google Maps data (APIFY ACTUAL OUTPUT).
        
        REALITY CHECK: Apify does NOT provide popularTimesHistogram or peopleTypicallySpendHere.
        We work with what we actually get:
        - reviewsCount (primary volume indicator)
        - totalScore (rating)
        - reviewsDistribution (sentiment breakdown)
        - reviews (text for pain point mining)
        - openingHours (schedule)
        - peopleAlsoSearch (competition)
        - imageCategories (visual presence)
        """
        signals = {}
        
        # PRIMARY VOLUME SIGNAL: Review count
        reviews_count = lead.get("reviewsCount") or lead.get("reviews_count") or lead.get("review_count") or 0
        try:
            reviews_count = int(reviews_count) if reviews_count else 0
        except:
            reviews_count = 0
        
        # ALWAYS set these values (never None)
        if reviews_count >= 500:
            signals["peak_busyness"] = 95
            signals["avg_busyness"] = 80
            signals["busy_hours_count"] = 50
        elif reviews_count >= 200:
            signals["peak_busyness"] = 80
            signals["avg_busyness"] = 65
            signals["busy_hours_count"] = 35
        elif reviews_count >= 100:
            signals["peak_busyness"] = 65
            signals["avg_busyness"] = 50
            signals["busy_hours_count"] = 25
        elif reviews_count >= 50:
            signals["peak_busyness"] = 50
            signals["avg_busyness"] = 35
            signals["busy_hours_count"] = 15
        else:
            # Even with 0 reviews, set defaults (not None)
            signals["peak_busyness"] = 0
            signals["avg_busyness"] = 0
            signals["busy_hours_count"] = 0
        
        # Extract opening hours
        opening_hours = lead.get("openingHours") or lead.get("opening_hours")
        if opening_hours:
            signals["opening_hours"] = opening_hours
            
            # Calculate total open hours per week
            total_hours = 0
            for day_schedule in opening_hours:
                hours_str = day_schedule.get("hours", "")
                # Parse "10 AM to 7 PM" format
                if "to" in hours_str:
                    try:
                        parts = hours_str.split("to")
                        # Simple heuristic: assume 9 hours per day if we can't parse
                        total_hours += 9
                    except:
                        pass
            
            if total_hours > 0:
                # Estimate visit duration based on business type
                category = lead.get("category", "").lower()
                if "hospital" in category or "clinic" in category:
                    signals["avg_visit_duration_min"] = 45  # Medical visits are longer
                elif "restaurant" in category or "cafe" in category:
                    signals["avg_visit_duration_min"] = 60
                else:
                    signals["avg_visit_duration_min"] = 30  # Default
            else:
                # No hours data, set default
                signals["avg_visit_duration_min"] = 0
        else:
            # No opening hours, set default visit duration
            signals["avg_visit_duration_min"] = 0
        
        # Extract reviews distribution (sentiment analysis)
        reviews_dist = lead.get("reviewsDistribution") or lead.get("reviews_distribution")
        if reviews_dist:
            signals["reviews_distribution"] = reviews_dist
            
            # Calculate sentiment score
            total_reviews = sum(reviews_dist.values())
            if total_reviews > 0:
                weighted_score = (
                    reviews_dist.get("fiveStar", 0) * 5 +
                    reviews_dist.get("fourStar", 0) * 4 +
                    reviews_dist.get("threeStar", 0) * 3 +
                    reviews_dist.get("twoStar", 0) * 2 +
                    reviews_dist.get("oneStar", 0) * 1
                ) / total_reviews
                
                # High negative reviews = problems = opportunity
                negative_ratio = (reviews_dist.get("oneStar", 0) + reviews_dist.get("twoStar", 0)) / total_reviews
                if negative_ratio > 0.15:  # >15% negative
                    signals["is_above_average"] = False  # Has problems
                else:
                    signals["is_above_average"] = True  # Doing well
        
        # Extract Q&A data
        qa_data = lead.get("questionsAndAnswers") or lead.get("questions_and_answers")
        if qa_data:
            signals["questions_and_answers"] = qa_data
        
        # Extract web results
        web_results = lead.get("webResults") or lead.get("web_results")
        if web_results:
            signals["web_results"] = web_results
        
        # Extract reservation links
        reservation_links = lead.get("tableReservationLinks") or lead.get("table_reservation_links")
        if reservation_links:
            signals["table_reservation_links"] = reservation_links
        
        # Extract image categories
        image_cats = lead.get("imageCategories") or lead.get("image_categories")
        if image_cats:
            signals["image_categories"] = image_cats
        
        return signals
    
    def _parse_duration(self, duration_text: str) -> Optional[int]:
        """
        Parse duration text to average minutes.
        Examples:
        - "20 min to 2 hr" → 70 min
        - "1-2 hours" → 90 min
        - "30 minutes" → 30 min
        """
        try:
            # Extract all numbers
            numbers = re.findall(r'\d+', duration_text)
            if not numbers:
                return None
            
            # Check for hours
            has_hour = 'hr' in duration_text.lower() or 'hour' in duration_text.lower()
            
            if len(numbers) >= 2:
                # Range: "20 min to 2 hr"
                min_val = int(numbers[0])
                max_val = int(numbers[1])
                
                # Convert to minutes
                if 'min' in duration_text.lower() and has_hour:
                    # Mixed: "20 min to 2 hr"
                    max_val = max_val * 60
                elif has_hour:
                    # Both hours: "1-2 hours"
                    min_val = min_val * 60
                    max_val = max_val * 60
                
                return (min_val + max_val) // 2
            
            elif len(numbers) == 1:
                # Single value: "30 minutes" or "2 hours"
                val = int(numbers[0])
                if has_hour:
                    return val * 60
                return val
        
        except Exception as e:
            self._logger.warning(f"Failed to parse duration '{duration_text}': {e}")
        
        return None
    
    def _normalize_phone(self, phone: Optional[str]) -> Optional[str]:
        """
        Normalize phone number format.
        Requirements: 4.3
        """
        if not phone:
            return None

        raw_value = str(phone).strip()

        # Remove all non-digit characters
        digits = re.sub(r'\D', '', phone)
        core = digits[-10:]
        if len(core) == 10 and core in {"0123456789", "1234567890", "0987654321", "9876543210"}:
            return None
        if core.endswith("123456789") or core.endswith("987654321"):
            return None
        if core and len(set(core)) == 1:
            return None
        
        # Handle likely Indian mobile numbers first.
        if len(digits) == 10:
            if digits[0] in {"6", "7", "8", "9"}:
                return f"+91{digits}"
            if re.search(r"[\s().-]", raw_value) and digits[0] in {"2", "3", "4", "5", "6", "7", "8", "9"}:
                return f"+1{digits}"
            return None
        elif len(digits) == 12 and digits.startswith("91"):
            return f"+{digits}"
        elif len(digits) == 11 and digits.startswith("0") and digits[1] in {"6", "7", "8", "9"}:
            return f"+91{digits[1:]}"
        elif len(digits) == 11 and digits.startswith('1'):
            if raw_value.startswith("+1") or re.search(r"[\s().-]", raw_value):
                return f"+{digits}"
            return None
        elif len(digits) == 13 and digits.startswith("091"):
            return f"+{digits[1:]}"
        elif 10 < len(digits) <= 13 and raw_value.startswith("+"):
            return f"+{digits}"
        
        return None

    def _extract_phone_candidates(self, raw_content: str) -> List[str]:
        matches = re.findall(r"(?:\+?\d[\d\s().-]{7,16}\d)", raw_content or "")
        return self._dedupe_phones(matches)
    
    def _validate_emails(self, emails: List[str]) -> List[str]:
        """
        Validate email addresses.
        Requirements: 4.3
        """
        validated = []

        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        junk_prefixes = ("frame-",)
        junk_domain_tokens = ("mht", "mhtml")
        max_local_length = 64

        # Disposable email domains to filter out
        disposable_domains = {
            'tempmail.com', 'throwaway.com', 'mailinator.com',
            'guerrillamail.com', '10minutemail.com',
        }
        
        for email in emails:
            email = email.lower().strip()
            
            # Check format
            if not re.match(email_pattern, email):
                continue

            local_part, domain = email.split("@", 1)
            if local_part.startswith(junk_prefixes):
                continue
            if len(local_part) > max_local_length:
                continue
            if any(token in domain for token in junk_domain_tokens):
                continue
            
            # Check for disposable domains
            if domain in disposable_domains:
                continue
            
            # In production, would also check MX records
            validated.append(email)
        
        return list(set(validated))  # Deduplicate
    
    def _compute_enrichment_confidence(
        self,
        tech_signals: Dict[str, str],
        decision_maker: Dict[str, str],
        normalized_phone: Optional[str],
        validated_emails: List[str],
    ) -> float:
        """
        Compute enrichment confidence score.
        Requirements: 4.4
        """
        score = 0.0
        
        # Tech signals contribute 0.3
        if tech_signals:
            score += 0.1 * len(tech_signals)
            score = min(score, 0.3)
        
        # Decision maker contributes 0.3
        if decision_maker.get("name"):
            score += 0.15
        if decision_maker.get("linkedin"):
            score += 0.15
        
        # Contact info contributes 0.4
        if normalized_phone:
            score += 0.2
        if validated_emails:
            score += 0.2
        
        return min(score, 1.0)
    
    def _compute_contact_quality_score(
        self,
        normalized_phone: Optional[str],
        validated_emails: List[str],
        decision_maker: Dict[str, str],
    ) -> int:
        """
        Compute contact quality score.
        Requirements: 4.5
        
        Score breakdown:
        - has_validated_email: +40
        - has_normalized_phone: +30
        - has_decision_maker: +20
        - has_linkedin: +10
        """
        score = 0
        
        if validated_emails:
            score += 40
        
        if normalized_phone:
            score += 30
        
        if decision_maker.get("name"):
            score += 20
        
        if decision_maker.get("linkedin"):
            score += 10
        
        return min(score, 100)
    
    def _save_enrichment(self, enrichment: Dict[str, Any]) -> None:
        """Save enrichment data to database."""
        persistable_keys = {
            "lead_id",
            "enrichment_confidence",
            "booking_provider",
            "crm_hint",
            "chat_widget",
            "form_tool",
            "decision_maker_name",
            "decision_maker_linkedin",
            "contact_quality_score",
            "normalized_phone",
            "validated_emails",
            "popular_times_histogram",
            "popular_times_live_text",
            "people_typically_spend_here",
            "peak_busyness",
            "avg_busyness",
            "busy_hours_count",
            "avg_visit_duration_min",
            "is_peak_busy",
            "is_above_average",
            "opening_hours",
            "reviews_distribution",
            "questions_and_answers",
            "web_results",
            "table_reservation_links",
            "image_categories",
        }
        data = {key: value for key, value in enrichment.items() if key in persistable_keys}
        data["lead_id"] = str(enrichment.get("lead_id", ""))
        data["created_at"] = datetime.utcnow().isoformat()
        
        self._db.save_enrichment_data(data)


_enrichment_agent: Optional[EnrichmentAgent] = None


def _get_enrichment_agent() -> EnrichmentAgent:
    global _enrichment_agent
    if _enrichment_agent is None:
        _enrichment_agent = EnrichmentAgent()
    return _enrichment_agent


def enrichment_node(state: LeadGraphState) -> LeadGraphState:
    """LangGraph node function for enrichment."""
    return _get_enrichment_agent()(state)
