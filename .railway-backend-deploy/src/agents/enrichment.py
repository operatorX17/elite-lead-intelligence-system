"""
Enrichment Agent - Contact and context extraction.
Requirements: 4.1-4.6
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import re
import logging
import os

import requests

from src.agents.base import BaseAgent, CircuitBreakerMixin
from src.graph.state import LeadGraphState
from src.db.models import EnrichmentData
from src.tools.apify import ApifyClient


logger = logging.getLogger(__name__)


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
    "whatsapp": r"wa\.me|api\.whatsapp\.com|whatsapp",
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
        raw_apify_data = metadata.get("raw_apify_data", {})
        
        # Merge raw Apify data into lead for volume signal extraction
        lead_with_apify = {**lead, **raw_apify_data}
        
        website_context = self._fetch_website_context(lead.get("website"))

        # Extract tech signals and clinic-specific contact context from the site.
        tech_signals = self._extract_tech_signals(website_context.get("content", ""))

        # Extract decision maker info from business name, contact pages, and social/profile hints.
        decision_maker = self._extract_decision_maker(lead, website_context)

        # Normalize contacts from both discovery and website extraction.
        candidate_phones: List[str] = []
        if lead.get("phone"):
            candidate_phones.append(str(lead["phone"]))
        candidate_phones.extend(website_context.get("phones", []))

        normalized_phones: List[str] = []
        for phone in candidate_phones:
            normalized = self._normalize_phone(phone)
            if normalized and normalized not in normalized_phones:
                normalized_phones.append(normalized)

        normalized_phone = normalized_phones[0] if normalized_phones else None
        validated_emails = self._validate_emails(
            list(lead.get("emails_found", [])) + website_context.get("emails", [])
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
        
        # Create enrichment data dict
        enrichment = {
            "lead_id": lead.get("lead_id"),
            "enrichment_confidence": enrichment_confidence,
            "booking_provider": tech_signals.get("booking_provider"),
            "crm_hint": tech_signals.get("crm_hint"),
            "chat_widget": tech_signals.get("chat_widget"),
            "form_tool": tech_signals.get("form_tool"),
            "decision_maker_name": decision_maker.get("name"),
            "decision_maker_linkedin": decision_maker.get("linkedin"),
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
    
    def _fetch_website_context(self, website: Optional[str]) -> Dict[str, Any]:
        """Fetch a website once and derive clinic-ready extraction hints."""
        context: Dict[str, Any] = {
            "content": "",
            "raw_content": "",
            "emails": [],
            "phones": [],
            "contact_paths": [],
            "social_profiles": {},
            "services": [],
            "booking_link": None,
            "contact_form": False,
            "whatsapp": False,
        }

        if not website:
            return context

        website = self._normalize_url(website)

        raw_content = ""

        try:
            api_key = os.getenv("FIRECRAWL_API_KEY")
            if api_key:
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                }
                payload = {
                    "url": website,
                    "formats": ["markdown", "html"],
                    "onlyMainContent": False,
                }
                response = requests.post(
                    "https://api.firecrawl.dev/v1/scrape",
                    json=payload,
                    headers=headers,
                    timeout=30,
                )
                response.raise_for_status()
                data = response.json().get("data", {})
                raw_content = " ".join(
                    [
                        str(data.get("html") or ""),
                        str(data.get("markdown") or ""),
                    ]
                )
        except Exception as exc:
            self._logger.warning("Firecrawl scrape failed for %s: %s", website, exc)

        if not raw_content:
            try:
                crawl_result = self._apify.crawl_website(website, max_pages=2)
                raw_content = str(crawl_result)
            except Exception as exc:
                self._logger.warning("Apify crawl fallback failed for %s: %s", website, exc)

        if not raw_content:
            try:
                response = requests.get(
                    website,
                    timeout=20,
                    headers={"User-Agent": "Mozilla/5.0"},
                )
                response.raise_for_status()
                raw_content = response.text
            except Exception as exc:
                self._logger.warning("Static website fallback failed for %s: %s", website, exc)

        lower_content = raw_content.lower()
        context["raw_content"] = raw_content
        context["content"] = lower_content
        context["emails"] = re.findall(
            r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
            raw_content,
        )
        context["phones"] = re.findall(
            r"(?:\+?\d[\d\s().-]{8,}\d)",
            raw_content,
        )
        context["social_profiles"] = self._extract_social_profiles(raw_content)

        contact_paths: List[str] = []
        if context["emails"]:
            contact_paths.append("email")
        if context["phones"]:
            contact_paths.append("phone")
        if any(token in lower_content for token in ["whatsapp", "wa.me", "api.whatsapp.com"]):
            contact_paths.append("whatsapp")
            context["whatsapp"] = True
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
    ) -> Dict[str, Any]:
        """
        Extract decision-maker information.
        Requirements: 4.2
        """
        decision_maker: Dict[str, Any] = {}
        website_context = website_context or {}
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
        business_name = str(lead.get("business_name", "")).strip()
        token_match = re.match(r"^([A-Za-z][A-Za-z'-]{2,})", business_name)
        if token_match:
            potential = token_match.group(1).replace("'s", "").strip()
            if potential and potential.lower() not in stopwords:
                candidates.append(
                    {
                        "name": potential,
                        "role": "brand_owner_hint",
                        "source": "business_name",
                        "score": 15,
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
                        if not name or self._looks_like_business_label(name):
                            continue
                        candidates.append(
                            {
                                "name": name,
                                "role": role,
                                "source": "website_copy",
                                "score": score,
                            }
                        )

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
                if match not in deduped:
                    deduped.append(match)
            if deduped:
                profiles[network] = deduped[:4]
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

    def _extract_first_link(self, html: str, keywords: List[str]) -> Optional[str]:
        """Return the first href matching any keyword."""
        href_matches = re.findall(r'href=["\']([^"\']+)["\']', html, re.IGNORECASE)
        lowered_keywords = [keyword.lower() for keyword in keywords]
        for href in href_matches:
            lowered_href = href.lower()
            if any(keyword in lowered_href for keyword in lowered_keywords):
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
        
        # Remove all non-digit characters
        digits = re.sub(r'\D', '', phone)
        
        # Handle likely Indian mobile numbers first.
        if len(digits) == 10:
            if digits[0] in {"6", "7", "8", "9"}:
                return f"+91{digits}"
            return f"+1{digits}"
        elif len(digits) == 12 and digits.startswith("91"):
            return f"+{digits}"
        elif len(digits) == 11 and digits.startswith('1'):
            return f"+{digits}"
        elif len(digits) > 10:
            return f"+{digits}"
        
        return None
    
    def _validate_emails(self, emails: List[str]) -> List[str]:
        """
        Validate email addresses.
        Requirements: 4.3
        """
        validated = []
        
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        
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
            
            # Check for disposable domains
            domain = email.split('@')[1]
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


# Create singleton instance for LangGraph node
_enrichment_agent = EnrichmentAgent()


def enrichment_node(state: LeadGraphState) -> LeadGraphState:
    """LangGraph node function for enrichment."""
    return _enrichment_agent(state)
