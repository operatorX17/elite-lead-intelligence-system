"""
Audit Agent - Precision audit and proof generation via Steel.dev.
Requirements: 6.1-6.7
"""

from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import logging
import os
import re
from io import BytesIO
from urllib.parse import urlparse, urljoin

import requests
from bs4 import BeautifulSoup
from PIL import Image
try:
    from rapidocr_onnxruntime import RapidOCR
except Exception:  # pragma: no cover - optional runtime dependency
    RapidOCR = None

from src.agents.base import BaseAgent, CircuitBreakerMixin
from src.graph.state import LeadGraphState
from src.db.models import ProofArtifact, AuditBullet
from src.tools.steel import SteelClient


logger = logging.getLogger(__name__)


class AuditAgent(BaseAgent, CircuitBreakerMixin):
    """
    Audit Agent for proof generation via Steel.dev browser automation.
    
    Requirements:
    - 6.1: Trigger Steel_Task when lead exceeds score threshold
    - 6.2: Open landing_page_url in a real browser
    - 6.3: Interact like a human (scroll, click CTAs, open forms)
    - 6.4: Extract phone_visibility, form_field_count, booking_link, etc.
    - 6.5: Capture screenshots of hero section and CTA/form/phone section
    - 6.6: Save artifacts to object storage and link URLs in database
    - 6.7: Generate Proof_Pack with 3 audit_bullets
    """
    
    SCORE_THRESHOLD = 70  # Minimum score to trigger audit
    
    def __init__(self):
        super().__init__("audit")
        self._steel = SteelClient()
        self._ocr = RapidOCR() if RapidOCR else None
    
    def process(self, state: LeadGraphState) -> LeadGraphState:
        """Process audit for a lead."""
        if not state.get("lead"):
            self._logger.warning("No lead data for audit")
            return state
        
        # Check kill switch
        if self._check_kill_switch():
            self._logger.warning("Audit kill switch is active")
            state["should_skip_audit"] = True
            return state
        
        # Check circuit breaker
        if self._is_circuit_open("audit"):
            self._logger.warning("Audit circuit breaker is open")
            state["should_skip_audit"] = True
            return state
        
        # Check budget
        if not self._check_budget("browser"):
            self._logger.warning("Browser budget exceeded")
            state["should_skip_audit"] = True
            state["last_error"] = "budget_exceeded"
            return state
        
        lead = state["lead"]
        scoring = state.get("scoring", {})
        intent = state.get("intent", {})
        metadata = state.get("metadata", {})
        
        # Check score threshold (Requirement 6.1)
        should_audit = bool(metadata.get("force_audit"))
        if not should_audit:
            if scoring and scoring.get("final_score", 0) >= self.SCORE_THRESHOLD:
                should_audit = True
            elif scoring and scoring.get("lead_tier") == "A":
                should_audit = True
            elif intent:
                avg_score = (intent.get("intent_score", 0) + intent.get("leak_score", 0)) / 2
                if avg_score >= self.SCORE_THRESHOLD:
                    should_audit = True
        
        if not should_audit:
            self._logger.info(f"Lead {lead.get('lead_id')} below audit threshold, skipping")
            state["should_skip_audit"] = True
            return state
        
        state["current_stage"] = "audit"
        
        # Get landing page URL
        landing_page_url = lead.get("landing_page_url") or lead.get("website")
        if not landing_page_url:
            self._logger.warning("No landing page URL for audit")
            state["should_skip_audit"] = True
            return state
        
        try:
            # Run Steel audit
            audit_result = self._steel.audit_landing_page(landing_page_url)
            
            if not audit_result.get("success"):
                self._logger.warning(
                    "Steel audit failed for %s, attempting static fallback: %s",
                    landing_page_url,
                    audit_result.get("error"),
                )
                proof = self._fallback_static_audit(
                    lead,
                    landing_page_url,
                    audit_result.get("error"),
                )
                if proof:
                    state["proof"] = proof
                    self._save_proof(proof)
                    self._record_success("audit")
                    return state

                self._record_failure("audit")
                state["last_error"] = audit_result.get("error", "Audit failed")
                return state

            extraction_data = audit_result.get("extraction_data", {}) or {}
            rendered_content = (
                audit_result.get("rendered_content")
                or audit_result.get("rendered_markdown")
                or audit_result.get("rendered_html")
                or ""
            )
            if rendered_content:
                extraction_data = self._merge_extraction_payloads(
                    primary=extraction_data,
                    secondary=self._extract_static_audit_data(rendered_content),
                )
            extraction_data = self._merge_static_audit_signals(
                landing_page_url,
                extraction_data,
            )
            
            # Save screenshots to storage
            hero_url = self._save_screenshot(
                lead.get("lead_id"),
                "hero",
                audit_result.get("hero_screenshot", b""),
            ) or audit_result.get("hero_screenshot_url")
            cta_url = self._save_screenshot(
                lead.get("lead_id"),
                "cta",
                audit_result.get("cta_screenshot", b""),
            ) or audit_result.get("cta_screenshot_url") or hero_url
            
            # Generate audit bullets
            audit_bullets = self._generate_audit_bullets(lead, extraction_data)
            
            # Create proof artifact dict
            proof = {
                "lead_id": lead.get("lead_id"),
                "hero_screenshot_url": hero_url,
                "cta_screenshot_url": cta_url,
                "audit_bullets": audit_bullets,
                "extraction_data": extraction_data,
            }
            
            state["proof"] = proof
            
            # Save to database
            self._save_proof(proof)
            
            self._record_success("audit")
            self._increment_usage("browser")
            
        except Exception as e:
            self._logger.error(f"Audit error: {e}")
            self._record_failure("audit")
            state["last_error"] = str(e)
        
        return state

    def _fallback_static_audit(
        self,
        lead: Dict[str, Any],
        url: str,
        source_error: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Generate a proof pack from static page content when Steel fails."""
        page = self._fetch_static_page(url)
        html = page.get("html", "")
        if not html:
            return None

        extraction_data = self._extract_static_audit_data(html)
        extraction_data["proof_mode"] = "static_fallback"
        if source_error:
            extraction_data["source_error"] = source_error

        return {
            "lead_id": lead.get("lead_id"),
            "hero_screenshot_url": None,
            "cta_screenshot_url": None,
            "audit_bullets": self._generate_audit_bullets(lead, extraction_data),
            "extraction_data": extraction_data,
        }

    def _merge_static_audit_signals(
        self,
        url: str,
        steel_extraction: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Supplement Steel extraction with static HTML signals without discarding screenshots."""
        page = self._fetch_static_page(url)
        html = page.get("html", "")
        if not html:
            return steel_extraction

        static_extraction = self._extract_static_audit_data(html)
        homepage_url = self._derive_homepage_url(url)
        homepage_source = page.get("source")
        if homepage_url and homepage_url != self._normalize_url(url):
            homepage_page = self._fetch_rendered_page(homepage_url)
            if not homepage_page.get("html"):
                homepage_page = self._fetch_static_page(homepage_url)
            homepage_html = homepage_page.get("html", "")
            if homepage_html:
                homepage_extraction = self._extract_static_audit_data(homepage_html)
                static_extraction = self._merge_extraction_payloads(
                    primary=static_extraction,
                    secondary=homepage_extraction,
                )
                homepage_source = homepage_page.get("source") or homepage_source
                deep_page_urls = self._collect_deep_clinic_pages(homepage_url, homepage_html)
                static_extraction = self._analyze_page_bundle(
                    static_extraction,
                    deep_page_urls,
                )
        else:
            rendered_page = self._fetch_rendered_page(url)
            rendered_html = rendered_page.get("html", "") or html
            deep_page_urls = self._collect_deep_clinic_pages(url, rendered_html)
            static_extraction = self._analyze_page_bundle(
                static_extraction,
                deep_page_urls,
            )
        merged = dict(steel_extraction)

        steel_phone_numbers = steel_extraction.get("phone_numbers") or []
        static_phone_numbers = static_extraction.get("phone_numbers") or []
        merged_phone_numbers = []
        seen_phone_keys = set()
        for phone in [*steel_phone_numbers, *static_phone_numbers]:
            phone_key = re.sub(r"\D", "", str(phone))
            if not phone_key or phone_key in seen_phone_keys:
                continue
            seen_phone_keys.add(phone_key)
            merged_phone_numbers.append(phone)
        if merged_phone_numbers:
            merged["phone_numbers"] = merged_phone_numbers[:5]
            merged["phone_visible"] = True
            merged["phone_visibility"] = "visible"

        if not merged.get("booking_link") and static_extraction.get("booking_link"):
            merged["booking_link"] = static_extraction["booking_link"]

        if not merged.get("chat_widget") and static_extraction.get("chat_widget"):
            merged["chat_widget"] = static_extraction["chat_widget"]

        if static_extraction.get("after_hours_capture"):
            merged["after_hours_capture"] = True

        if not merged.get("form_field_count") and static_extraction.get("form_field_count"):
            merged["form_field_count"] = static_extraction["form_field_count"]

        if static_extraction.get("detected_phone_count", 0) > merged.get("detected_phone_count", 0):
            merged["detected_phone_count"] = static_extraction["detected_phone_count"]

        merged = self._merge_extraction_payloads(
            primary=merged,
            secondary=static_extraction,
        )
        merged["proof_mode"] = "steel_plus_static"
        merged["static_signal_source"] = page.get("source")
        if homepage_source and homepage_source != page.get("source"):
            merged["homepage_signal_source"] = homepage_source
        return merged

    def _fetch_static_page(self, url: str) -> Dict[str, Any]:
        """Fetch page content via Firecrawl first, then plain HTTP."""
        url = self._normalize_url(url)
        api_key = os.getenv("FIRECRAWL_API_KEY")
        if api_key:
            try:
                response = requests.post(
                    "https://api.firecrawl.dev/v1/scrape",
                    json={
                        "url": url,
                        "formats": ["html", "markdown"],
                        "onlyMainContent": False,
                    },
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    timeout=30,
                )
                response.raise_for_status()
                data = response.json().get("data", {})
                html = data.get("html") or ""
                markdown = data.get("markdown") or ""
                if html or markdown:
                    return {
                        "html": " ".join([str(html), str(markdown)]).strip(),
                        "source": "firecrawl",
                    }
            except Exception as exc:
                self._logger.warning("Firecrawl fallback failed for %s: %s", url, exc)

        try:
            response = requests.get(
                url,
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=20,
            )
            response.raise_for_status()
            return {"html": response.text, "source": "requests"}
        except Exception as exc:
            self._logger.error("Static proof fallback failed for %s: %s", url, exc)
            return {"html": "", "source": "failed"}

    def _fetch_rendered_page(self, url: str) -> Dict[str, Any]:
        """Fetch rendered page content via Steel scrape for JS-heavy clinic sites."""
        normalized_url = self._normalize_url(url)
        try:
            result = self._steel.scrape_page_bundle(normalized_url, delay=3)
            content = result.get("rendered_content", "") or ""
            return {
                "html": content,
                "screenshot_bytes": result.get("screenshot_bytes"),
                "screenshot_url": result.get("screenshot_url"),
                "source": "steel_rendered" if content else "steel_empty",
            }
        except Exception as exc:
            self._logger.warning("Rendered page fetch failed for %s: %s", normalized_url, exc)
            return {"html": "", "screenshot_bytes": None, "screenshot_url": None, "source": "steel_failed"}

    def _normalize_url(self, url: str) -> str:
        normalized = (url or "").strip()
        if normalized and not normalized.startswith(("http://", "https://")):
            normalized = f"https://{normalized}"
        return normalized

    def _derive_homepage_url(self, url: str) -> Optional[str]:
        normalized = self._normalize_url(url)
        if not normalized:
            return None

        parsed = urlparse(normalized)
        if not parsed.scheme or not parsed.netloc:
            return normalized

        return f"{parsed.scheme}://{parsed.netloc}/"

    def _merge_extraction_payloads(
        self,
        primary: Dict[str, Any],
        secondary: Dict[str, Any],
    ) -> Dict[str, Any]:
        merged = dict(primary)

        for key in ["phone_numbers", "services", "branch_names", "doctor_names", "deep_analysis_pages"]:
            merged[key] = self._dedupe_list([
                *(merged.get(key) or []),
                *(secondary.get(key) or []),
            ])

        merged_social_profiles = dict(merged.get("social_profiles") or {})
        for platform, values in (secondary.get("social_profiles") or {}).items():
            existing_values = merged_social_profiles.get(platform) or []
            if isinstance(existing_values, str):
                existing_values = [existing_values]
            if isinstance(values, str):
                values = [values]
            merged_social_profiles[platform] = self._dedupe_list([
                *existing_values,
                *(values or []),
            ])
        if merged_social_profiles:
            merged["social_profiles"] = merged_social_profiles

        for key in [
            "branch_count",
            "doctor_count",
            "content_ready_score",
            "form_field_count",
            "detected_phone_count",
        ]:
            primary_value = merged.get(key)
            secondary_value = secondary.get(key)
            if secondary_value is None:
                continue
            if primary_value is None or secondary_value > primary_value:
                merged[key] = secondary_value

        for key in [
            "multi_clinic",
            "instagram_present",
            "youtube_present",
            "facebook_present",
            "testimonials_present",
            "gallery_present",
            "after_hours_capture",
            "instant_response_path",
            "contact_form_detected",
            "booking_detected",
        ]:
            merged[key] = bool(merged.get(key) or secondary.get(key))

        for key in ["booking_link", "whatsapp_target", "chat_widget", "booking_flow_quality"]:
            if not merged.get(key) and secondary.get(key):
                merged[key] = secondary[key]

        if merged.get("phone_numbers"):
            merged["phone_visible"] = True
            merged["phone_visibility"] = "visible"
        elif not merged.get("phone_visibility") and secondary.get("phone_visibility"):
            merged["phone_visibility"] = secondary["phone_visibility"]

        return merged

    def _collect_deep_clinic_pages(self, base_url: str, html: str) -> List[Dict[str, str]]:
        page_plan = self._build_page_analysis_plan(base_url, html)
        selected = [
            *self._select_related_pages(page_plan["locations"], limit=2),
            *self._select_related_pages(page_plan["doctors"], limit=2),
            *self._select_related_pages(page_plan["booking"], limit=1),
            *self._select_related_pages(page_plan["services"], limit=2),
        ]
        deduped: List[Dict[str, str]] = []
        seen = set()
        for page in selected:
            page_url = page.get("url")
            if not page_url or page_url in seen:
                continue
            seen.add(page_url)
            deduped.append(page)
        return deduped[:5]

    def _build_page_analysis_plan(self, base_url: str, html: str) -> Dict[str, List[Dict[str, str]]]:
        soup = BeautifulSoup(html or "", "html.parser")
        buckets = {
            "locations": [],
            "doctors": [],
            "booking": [],
            "services": [],
        }
        keyword_map = {
            "locations": ["location", "locations", "clinic", "clinics", "branch", "branches"],
            "doctors": ["doctor", "doctors", "team", "experts", "specialists"],
            "booking": ["book", "appointment", "consultation", "schedule", "reserve"],
            "services": ["service", "services", "treatment", "treatments", "speciality", "specialities", "specialty", "specialties"],
        }

        for anchor in soup.find_all("a", href=True):
            href = (anchor.get("href") or "").strip()
            anchor_text = " ".join(anchor.get_text(" ", strip=True).split())
            if not href:
                continue
            lowered = f"{href} {anchor_text}".lower()
            if href.startswith(("mailto:", "tel:", "#", "javascript:")):
                continue
            absolute_url = urljoin(self._normalize_url(base_url), href)
            if urlparse(absolute_url).netloc != urlparse(self._normalize_url(base_url)).netloc:
                continue
            for bucket, keywords in keyword_map.items():
                if any(keyword in lowered for keyword in keywords):
                    buckets[bucket].append({"url": absolute_url, "page_type": bucket})

        guessed_paths = {
            "locations": ["/clinics", "/locations", "/our-clinics", "/our-locations", "/branches"],
            "doctors": ["/doctors", "/team", "/our-doctors", "/experts", "/specialists"],
            "booking": ["/appointment", "/consultation", "/book-appointment", "/book-consultation", "/contact-us"],
            "services": ["/services", "/treatments", "/specialities", "/specialties"],
        }
        normalized_base = self._normalize_url(base_url)
        for bucket, paths in guessed_paths.items():
            buckets[bucket].extend(
                {"url": urljoin(normalized_base, path), "page_type": bucket}
                for path in paths
            )
        return {
            key: self._select_related_pages(value, limit=max(len(value), 1))
            for key, value in buckets.items()
        }

    def _select_related_pages(self, urls: List[Dict[str, str]], limit: int) -> List[Dict[str, str]]:
        cleaned: List[Dict[str, str]] = []
        seen = set()
        for page in urls:
            url = page.get("url", "")
            lowered = url.lower()
            if any(token in lowered for token in ["instagram.com", "facebook.com", "youtube.com", "youtu.be"]):
                continue
            if not url or url in seen:
                continue
            seen.add(url)
            cleaned.append(page)
        return cleaned[:limit]

    def _analyze_page_bundle(
        self,
        base_extraction: Dict[str, Any],
        page_urls: List[Dict[str, str]],
    ) -> Dict[str, Any]:
        merged = dict(base_extraction)
        analyzed_pages: List[str] = []

        for page_spec in page_urls[:5]:
            page_url = page_spec.get("url")
            page_type = page_spec.get("page_type") or "general"
            if not page_url:
                continue
            try:
                page_result = self._fetch_rendered_page(page_url)
                page_content = page_result.get("html", "")
                page_screenshot = page_result.get("screenshot_bytes")
                if page_content:
                    page_extraction = self._extract_static_audit_data(page_content)
                    page_extraction["page_type"] = page_type
                    merged = self._merge_extraction_payloads(merged, page_extraction)
                if not page_content:
                    page_result = self._fetch_static_page(page_url)
                    page_content = page_result.get("html", "")
                    if page_content:
                        page_extraction = self._extract_static_audit_data(page_content)
                        page_extraction["page_type"] = page_type
                        merged = self._merge_extraction_payloads(merged, page_extraction)
                if page_screenshot:
                    visual_extraction = self._extract_visual_page_signals(
                        page_url=page_url,
                        page_type=page_type,
                        screenshot_bytes=page_screenshot,
                    )
                    if visual_extraction:
                        merged = self._merge_extraction_payloads(merged, visual_extraction)
                if page_content or page_screenshot:
                    analyzed_pages.append(f"{page_url} ({page_result.get('source')}, {page_type})")
            except Exception as exc:
                self._logger.warning("Deep clinic page scrape failed for %s: %s", page_url, exc)

        if analyzed_pages:
            merged["deep_analysis_pages"] = analyzed_pages
        return merged

    def _extract_visual_page_signals(
        self,
        *,
        page_url: str,
        page_type: str,
        screenshot_bytes: bytes,
    ) -> Dict[str, Any]:
        prepared_image = self._prepare_screenshot_for_llm(screenshot_bytes)
        if not prepared_image:
            return {}
        ocr_text = self._extract_ocr_text(prepared_image)
        if not ocr_text:
            return {}
        lowered = ocr_text.lower()
        if "page not found" in lowered and "404" in lowered:
            return {}

        phone_numbers = self._extract_phone_numbers(ocr_text)
        booking_tokens = [
            "book appointment",
            "bookappointment",
            "book consultation",
            "bookconsultation",
            "schedule consultation",
            "book your consultation",
            "bookyourconsultation",
            "book visit",
            "bookvisit",
            "schedule now",
            "book now",
        ]
        booking_detected = any(token in lowered for token in booking_tokens)
        booking_cta_count = sum(lowered.count(token) for token in booking_tokens)
        contact_form_detected = all(token in lowered for token in ["name", "phone"]) and any(
            token in lowered for token in ["submit", "book", "appointment", "consultation"]
        )
        whatsapp_target = self._extract_whatsapp_target(ocr_text)
        whatsapp_detected = bool(whatsapp_target or "whatsapp" in lowered)
        chat_widget = "whatsapp" if whatsapp_detected else None
        hours_present = self._detect_business_hours_text(lowered)
        after_hours_capture = self._determine_after_hours_capture(
            booking_detected=booking_detected,
            contact_form_detected=contact_form_detected,
            whatsapp_detected=whatsapp_detected,
            chat_widget=chat_widget,
            hours_present=hours_present,
            lowered_text=lowered,
        )

        doctor_names = self._extract_doctor_names_from_text(ocr_text)
        branch_names = self._extract_branch_names_from_text(ocr_text)
        if page_type == "locations" and branch_names:
            multi_clinic = len(branch_names) > 1
        else:
            multi_clinic = (
                len(branch_names) > 1
                or "our clinic locations" in lowered
                or "our clinics" in lowered
                or "across 3" in lowered
                or "across three" in lowered
            )

        instagram_present = "instagram" in lowered or "@" in ocr_text
        youtube_present = "youtube" in lowered
        facebook_present = "facebook" in lowered
        testimonials_present = any(token in lowered for token in ["what our patients say", "testimonial", "happy patients"])
        gallery_present = "gallery" in lowered or "before after" in lowered
        services = self._extract_services_from_text(ocr_text)
        content_ready_score = self._calculate_content_ready_score(
            services=services,
            doctor_names=doctor_names,
            testimonials_present=testimonials_present,
            gallery_present=gallery_present,
            instagram_present=instagram_present,
            youtube_present=youtube_present,
            multi_clinic=multi_clinic,
        )
        booking_flow_quality = self._determine_booking_flow_quality(
            booking_link="visible_cta" if booking_detected else None,
            phone_numbers=phone_numbers,
            form_present=contact_form_detected,
            whatsapp_detected=whatsapp_detected,
            booking_cta_count=booking_cta_count,
        )
        instant_response_path = self._determine_instant_response_path(
            phone_numbers=phone_numbers,
            booking_detected=booking_detected,
            contact_form_detected=contact_form_detected,
            whatsapp_detected=whatsapp_detected,
            chat_widget=chat_widget,
            lowered_text=lowered,
        )

        return {
            "page_type": page_type,
            "phone_visibility": "visible" if phone_numbers else "none",
            "phone_numbers": phone_numbers,
            "services": services,
            "booking_link": "visible_cta" if booking_detected else None,
            "booking_detected": booking_detected,
            "contact_form_detected": contact_form_detected,
            "chat_widget": chat_widget,
            "whatsapp_target": whatsapp_target if isinstance(whatsapp_target, str) and whatsapp_target else None,
            "multi_clinic": multi_clinic,
            "branch_count": len(branch_names),
            "branch_names": branch_names,
            "doctor_count": len(doctor_names),
            "doctor_names": doctor_names,
            "instagram_present": instagram_present,
            "youtube_present": youtube_present,
            "facebook_present": facebook_present,
            "testimonials_present": testimonials_present,
            "gallery_present": gallery_present,
            "content_ready_score": content_ready_score,
            "booking_flow_quality": booking_flow_quality,
            "after_hours_capture": after_hours_capture,
            "instant_response_path": instant_response_path,
        }

    def _prepare_screenshot_for_llm(self, screenshot_bytes: bytes) -> Optional[bytes]:
        try:
            image = Image.open(BytesIO(screenshot_bytes))
            image = image.convert("RGB")
            max_dimension = 1800
            if max(image.size) > max_dimension:
                image.thumbnail((max_dimension, max_dimension))
            buffer = BytesIO()
            image.save(buffer, format="PNG", optimize=True)
            return buffer.getvalue()
        except Exception as exc:
            self._logger.warning("Failed to prepare screenshot for LLM: %s", exc)
            return None

    def _extract_ocr_text(self, screenshot_bytes: bytes) -> str:
        if not self._ocr:
            return ""
        try:
            result, _ = self._ocr(screenshot_bytes)
            lines = [item[1] for item in (result or []) if len(item) > 1 and item[1]]
            return "\n".join(self._dedupe_list(lines))
        except Exception as exc:
            self._logger.warning("Screenshot OCR failed: %s", exc)
            return ""

    def _extract_doctor_names_from_text(self, text: str) -> List[str]:
        candidates: List[str] = []
        for line in text.splitlines():
            line = " ".join(line.split()).strip()
            if not line or "dr" not in line.lower():
                continue
            matches = re.findall(
                r"\bDr\.?\s*[A-Z][A-Za-z.\-']+(?:\s+[A-Z][A-Za-z.\-']+){0,3}",
                line,
            )
            for match in matches:
                cleaned = re.sub(
                    r"\b(?:Founder|Co-Founder|Chief|Dermatologist|Clinic|Callfor.*|Specializations.*)\b.*$",
                    "",
                    match,
                    flags=re.IGNORECASE,
                ).strip(" -,:")
                if cleaned:
                    candidates.append(cleaned)
        return self._dedupe_list(candidates)[:12]

    def _extract_branch_names_from_text(self, text: str) -> List[str]:
        matches = []
        for line in text.splitlines():
            line = " ".join(line.split()).strip()
            if not line:
                continue
            direct = re.findall(
                r"\biSkin\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)?)\b",
                line,
            )
            for suffix in direct:
                suffix_clean = re.sub(
                    r"\b(?:Dermatologists?|Book|Founder|Co|Clinic|Doctors?)\b.*$",
                    "",
                    suffix,
                    flags=re.IGNORECASE,
                ).strip(" -,:")
                if suffix_clean:
                    matches.append(f"iSkin {suffix_clean}")
        if not matches:
            neighborhood_matches = re.findall(
                r"\b(?:Nagawara|Bilekahalli|Uttarahalli|Indiranagar|Jayanagar|HSR|Bellandur|Marathahalli)\b",
                text,
                re.IGNORECASE,
            )
            matches = [f"Clinic {name.title()}" for name in neighborhood_matches]
        return self._dedupe_list(matches)[:12]

    def _extract_services_from_text(self, text: str) -> List[str]:
        lowered = text.lower()
        services = []
        mapping = {
            "advanced skincare": ["advanced skincare", "skin care", "skincare", "clinical dermatology"],
            "hair care": ["hair care", "hair treatment", "hair transplant", "hair loss"],
            "cosmetic procedures": ["cosmetic", "laser", "aesthetic"],
            "medical dermatology": ["medical dermatology", "dermatology"],
        }
        for label, keywords in mapping.items():
            if any(keyword in lowered for keyword in keywords):
                services.append(label)
        return services[:8]

    def _extract_static_audit_data(self, html: str) -> Dict[str, Any]:
        """Infer proof-relevant fields from static page content."""
        lowered = html.lower()
        soup = BeautifulSoup(html, "html.parser")
        phones = self._extract_phone_numbers(html)
        booking_link = self._extract_first_link(
            html,
            ["book", "appointment", "consultation", "schedule", "reserve"],
        )
        booking_cta_count = sum(
            lowered.count(token)
            for token in [
                "book appointment",
                "book consultation",
                "schedule consultation",
                "book now",
                "schedule now",
            ]
        )
        chat_widget = None
        if any(token in lowered for token in ["whatsapp", "wa.me", "api.whatsapp.com"]):
            chat_widget = "whatsapp"
        elif any(token in lowered for token in ["intercom", "drift", "tawk.to", "crisp.chat"]):
            chat_widget = "chat_widget"
        whatsapp_target = self._extract_whatsapp_target(html)
        social_profiles = self._extract_social_profiles(soup)
        services = self._extract_service_categories(soup)
        doctor_names = self._extract_doctor_names(soup)
        branch_names = self._extract_branch_names(soup)
        contact_form_detected = "<form" in lowered or "<input" in lowered
        testimonials_present = self._detect_testimonials(soup, lowered)
        gallery_present = self._detect_gallery(soup, lowered)
        instagram_present = bool(social_profiles.get("instagram"))
        youtube_present = bool(social_profiles.get("youtube"))
        facebook_present = bool(social_profiles.get("facebook"))
        multi_clinic = len(branch_names) > 1 or any(
            token in lowered for token in ["our locations", "locations", "our clinics", "branches"]
        )
        booking_flow_quality = self._determine_booking_flow_quality(
            booking_link=booking_link,
            phone_numbers=phones,
            form_present=contact_form_detected,
            whatsapp_detected=bool(whatsapp_target),
            booking_cta_count=booking_cta_count,
        )
        instant_response_path = self._determine_instant_response_path(
            phone_numbers=phones,
            booking_detected=bool(booking_link),
            contact_form_detected=contact_form_detected,
            whatsapp_detected=bool(whatsapp_target),
            chat_widget=chat_widget,
            lowered_text=lowered,
        )
        after_hours_capture = self._determine_after_hours_capture(
            booking_detected=bool(booking_link),
            contact_form_detected=contact_form_detected,
            whatsapp_detected=bool(whatsapp_target),
            chat_widget=chat_widget,
            hours_present=self._detect_business_hours_text(lowered),
            lowered_text=lowered,
        )
        content_ready_score = self._calculate_content_ready_score(
            services=services,
            doctor_names=doctor_names,
            testimonials_present=testimonials_present,
            gallery_present=gallery_present,
            instagram_present=instagram_present,
            youtube_present=youtube_present,
            multi_clinic=multi_clinic,
        )

        form_field_count = html.lower().count("<input") + html.lower().count("<textarea")

        return {
            "phone_visibility": "visible" if phones else "none",
            "form_field_count": form_field_count,
            "booking_link": booking_link,
            "booking_detected": bool(booking_link),
            "booking_cta_count": booking_cta_count,
            "chat_widget": chat_widget,
            "whatsapp_target": whatsapp_target,
            "after_hours_capture": after_hours_capture,
            "detected_phone_count": len(phones),
            "phone_numbers": phones[:5],
            "social_profiles": social_profiles,
            "services": services,
            "multi_clinic": multi_clinic,
            "branch_count": len(branch_names),
            "branch_names": branch_names,
            "doctor_count": len(doctor_names),
            "doctor_names": doctor_names,
            "instagram_present": instagram_present,
            "youtube_present": youtube_present,
            "facebook_present": facebook_present,
            "testimonials_present": testimonials_present,
            "gallery_present": gallery_present,
            "content_ready_score": content_ready_score,
            "booking_flow_quality": booking_flow_quality,
            "contact_form_detected": contact_form_detected,
            "instant_response_path": instant_response_path,
        }

    def _extract_phone_numbers(self, content: str) -> List[str]:
        """Extract phone-like strings from visible text and hrefs, then normalize."""
        text_candidates = [content]
        try:
            soup = BeautifulSoup(content, "html.parser")
            visible_text = " ".join(soup.stripped_strings)
            href_values = " ".join(
                href
                for href in (
                    anchor.get("href", "")
                    for anchor in soup.find_all("a", href=True)
                )
                if href
            )
            text_candidates = [visible_text, href_values]
        except Exception as exc:
            self._logger.warning("BeautifulSoup parsing failed during static phone extraction: %s", exc)

        matches: List[str] = []
        for candidate in text_candidates:
            matches.extend(re.findall(r"(?:\+?\d[\d\s().-]{8,}\d)", candidate))
        cleaned: List[str] = []
        seen = set()

        for raw in matches:
            normalized = re.sub(r"[^\d+]", "", raw.strip())
            digit_count = len(re.sub(r"\D", "", normalized))
            if digit_count < 10 or digit_count > 15:
                continue

            if normalized.startswith("00"):
                normalized = f"+{normalized[2:]}"
            elif normalized.startswith("91") and not normalized.startswith("+91"):
                normalized = f"+{normalized}"
            elif normalized.startswith("1") and digit_count == 11 and not normalized.startswith("+1"):
                normalized = f"+{normalized}"

            dedupe_key = re.sub(r"\D", "", normalized)
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            cleaned.append(normalized)

        return cleaned[:5]

    def _extract_first_link(self, html: str, keywords: List[str]) -> Optional[str]:
        href_matches = re.findall(r'href=["\']([^"\']+)["\']', html, re.IGNORECASE)
        lowered_keywords = [keyword.lower() for keyword in keywords]
        for href in href_matches:
            lowered_href = href.lower()
            if any(keyword in lowered_href for keyword in lowered_keywords):
                return href
        return None

    def _extract_whatsapp_target(self, html: str) -> Optional[str]:
        href_matches = re.findall(r'href=["\']([^"\']+)["\']', html, re.IGNORECASE)
        for href in href_matches:
            lowered = href.lower()
            if "wa.me/" in lowered or "api.whatsapp.com" in lowered:
                phone_match = re.search(r"(?:phone=|wa\.me/)(\+?\d{7,15})", href, re.IGNORECASE)
                if phone_match:
                    return phone_match.group(1)
                return href
        return None

    def _extract_social_profiles(self, soup: BeautifulSoup) -> Dict[str, List[str]]:
        profiles: Dict[str, List[str]] = {
            "instagram": [],
            "youtube": [],
            "facebook": [],
        }
        for anchor in soup.find_all("a", href=True):
            href = anchor.get("href", "").strip()
            lowered = href.lower()
            if not href:
                continue
            if "instagram.com" in lowered:
                profiles["instagram"].append(href)
            if "youtube.com" in lowered or "youtu.be" in lowered:
                profiles["youtube"].append(href)
            if "facebook.com" in lowered:
                profiles["facebook"].append(href)
        return {key: self._dedupe_list(value) for key, value in profiles.items() if value}

    def _extract_service_categories(self, soup: BeautifulSoup) -> List[str]:
        service_keywords = {
            "advanced skincare": ["advanced skincare", "skin care", "facial", "skin treatment", "dermatology"],
            "hair care": ["hair care", "hair treatment", "hair transplant", "hair loss", "prp"],
            "cosmetic procedures": ["cosmetic", "laser", "aesthetic", "botox", "fillers", "procedures"],
            "medical dermatology": ["medical dermatology", "eczema", "psoriasis", "acne", "pigmentation"],
        }
        text_candidates = " ".join(soup.stripped_strings).lower()
        services: List[str] = []
        for label, keywords in service_keywords.items():
            if any(keyword in text_candidates for keyword in keywords):
                services.append(label)
        return services[:8]

    def _extract_doctor_names(self, soup: BeautifulSoup) -> List[str]:
        names: List[str] = []
        patterns = [
            re.compile(r"\bDr\.?\s+[A-Z][A-Za-z.\-']+(?:\s+[A-Z][A-Za-z.\-']+){0,3}\b"),
        ]
        for text in soup.stripped_strings:
            candidate = " ".join(text.split())
            if len(candidate) > 80:
                continue
            for pattern in patterns:
                for match in pattern.findall(candidate):
                    names.append(match.strip())
        return self._dedupe_list(names)[:12]

    def _extract_branch_names(self, soup: BeautifulSoup) -> List[str]:
        names: List[str] = []
        location_heading = soup.find(
            lambda tag: tag.name in {"h1", "h2", "h3", "h4", "strong", "b"}
            and any(token in tag.get_text(" ", strip=True).lower() for token in ["location", "our clinics", "branches"])
        )
        search_roots = [location_heading.parent] if location_heading and location_heading.parent else []
        if not search_roots:
            search_roots = [soup]

        for root in search_roots:
            for tag in root.find_all(["h3", "h4", "h5", "strong", "b", "a", "p", "span"]):
                text = " ".join(tag.get_text(" ", strip=True).split())
                lowered = text.lower()
                if not text or len(text) > 90:
                    continue
                if any(token in lowered for token in ["book visit", "view doctors", "book consultation", "book appointment"]):
                    continue
                if (
                    "clinic" in lowered
                    or "branch" in lowered
                    or re.search(r"\b[a-z]+\s+(nagar|layout|road|halli|pet|puram|city|clinic)\b", lowered)
                ):
                    names.append(text)
        return self._dedupe_list(names)[:12]

    def _detect_testimonials(self, soup: BeautifulSoup, lowered_html: str) -> bool:
        if any(token in lowered_html for token in ["testimonial", "what our patients say", "success stories"]):
            return True
        rating_stars = lowered_html.count("star")
        return rating_stars >= 4

    def _detect_gallery(self, soup: BeautifulSoup, lowered_html: str) -> bool:
        return any(token in lowered_html for token in ["gallery", "before after", "before & after", "results gallery"])

    def _determine_booking_flow_quality(
        self,
        *,
        booking_link: Optional[str],
        phone_numbers: List[str],
        form_present: bool,
        whatsapp_detected: bool = False,
        booking_cta_count: int = 0,
    ) -> str:
        if booking_link and (form_present or whatsapp_detected or booking_cta_count >= 2):
            return "strong"
        if booking_link and phone_numbers:
            return "strong"
        if booking_link:
            return "basic"
        if form_present and whatsapp_detected:
            return "basic"
        if form_present or phone_numbers or whatsapp_detected:
            return "weak"
        return "none"

    def _detect_business_hours_text(self, lowered_text: str) -> bool:
        day_tokens = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        has_day = any(token in lowered_text for token in day_tokens)
        has_time = bool(re.search(r"\b\d{1,2}\s*(?::\d{2})?\s*(?:am|pm)\b", lowered_text))
        return has_day or has_time

    def _determine_after_hours_capture(
        self,
        *,
        booking_detected: bool,
        contact_form_detected: bool,
        whatsapp_detected: bool,
        chat_widget: Optional[str],
        hours_present: bool,
        lowered_text: str,
    ) -> bool:
        explicit_always_on = any(
            token in lowered_text
            for token in [
                "24/7",
                "24x7",
                "book anytime",
                "schedule anytime",
                "message us anytime",
                "chat now",
            ]
        )
        if explicit_always_on:
            return True
        if whatsapp_detected or chat_widget:
            return True
        if booking_detected:
            return True
        if contact_form_detected and not hours_present:
            return True
        return False

    def _determine_instant_response_path(
        self,
        *,
        phone_numbers: List[str],
        booking_detected: bool,
        contact_form_detected: bool,
        whatsapp_detected: bool,
        chat_widget: Optional[str],
        lowered_text: str,
    ) -> bool:
        if whatsapp_detected or chat_widget:
            return True
        if any(
            token in lowered_text
            for token in ["instant reply", "quick response", "response within", "chat now", "message now"]
        ):
            return True
        if booking_detected:
            return True
        if contact_form_detected and any(
            token in lowered_text for token in ["get a call back", "call back", "we will call you", "request callback"]
        ):
            return True
        return False

    def _calculate_content_ready_score(
        self,
        *,
        services: List[str],
        doctor_names: List[str],
        testimonials_present: bool,
        gallery_present: bool,
        instagram_present: bool,
        youtube_present: bool,
        multi_clinic: bool,
    ) -> int:
        score = 0
        score += min(len(services), 4) * 10
        score += min(len(doctor_names), 4) * 8
        if testimonials_present:
            score += 15
        if gallery_present:
            score += 10
        if instagram_present:
            score += 10
        if youtube_present:
            score += 7
        if multi_clinic:
            score += 8
        return min(score, 100)

    def _dedupe_list(self, values: List[str]) -> List[str]:
        seen = set()
        cleaned: List[str] = []
        for value in values:
            normalized = " ".join(str(value).split()).strip()
            if not normalized:
                continue
            key = normalized.lower()
            if key in seen:
                continue
            seen.add(key)
            cleaned.append(normalized)
        return cleaned
    
    def _save_screenshot(
        self,
        lead_id,
        screenshot_type: str,
        data: bytes,
    ) -> Optional[str]:
        """
        Save screenshot to storage.
        Requirements: 6.6
        """
        if not data:
            return None
        
        filename = f"{lead_id}/{screenshot_type}.png"

        if hasattr(self._db, "upload_artifact_bytes"):
            return self._db.upload_artifact_bytes(
                filename,
                data,
                content_type="image/png",
            )

        return None
    
    def _generate_audit_bullets(
        self,
        lead: Dict[str, Any],
        extraction_data: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        Generate proof pack audit bullets.
        Requirements: 6.7
        
        Each bullet has:
        - type: 'leak', 'fix', or 'upside'
        - evidence/specific/estimate based on type
        """
        bullets = []
        
        # Analyze extraction data for leak evidence
        phone_visibility = extraction_data.get("phone_visibility", "none")
        form_field_count = extraction_data.get("form_field_count", 0)
        booking_link = extraction_data.get("booking_link")
        chat_widget = extraction_data.get("chat_widget")
        after_hours_capture = extraction_data.get("after_hours_capture", False)
        
        # Generate leak bullet
        leak_evidence = None
        if phone_visibility == "below_fold":
            leak_evidence = "Phone number hidden below the fold - visitors may leave before finding it"
        elif phone_visibility == "hidden":
            leak_evidence = "Phone number requires click to reveal - adds friction for callers"
        elif phone_visibility == "none":
            leak_evidence = "No visible phone number on landing page"
        elif not booking_link and not chat_widget:
            leak_evidence = "No online booking or chat widget for after-hours lead capture"
        elif form_field_count > 5:
            leak_evidence = f"Contact form has {form_field_count} fields - high friction may reduce submissions"
        
        if leak_evidence:
            bullets.append({
                "type": "leak",
                "evidence": leak_evidence,
            })
        
        # Generate fix bullet
        fix_specific = None
        if phone_visibility in ["below_fold", "hidden", "none"]:
            fix_specific = "Add prominent phone number in hero section with click-to-call"
        elif not booking_link:
            fix_specific = "Add online booking widget (Calendly, Acuity) for 24/7 scheduling"
        elif not chat_widget:
            fix_specific = "Add chat widget with after-hours auto-response"
        elif form_field_count > 5:
            fix_specific = "Reduce form to essential fields (name, phone, email, message)"
        
        if fix_specific:
            bullets.append({
                "type": "fix",
                "specific": fix_specific,
            })
        
        # Generate upside bullet
        upside_estimate = None
        if phone_visibility in ["below_fold", "hidden", "none"]:
            upside_estimate = "Recover 15-20% of missed calls by making phone prominent"
        elif not booking_link:
            upside_estimate = "Capture 10-15% more leads with 24/7 online booking"
        elif not after_hours_capture:
            upside_estimate = "Capture after-hours leads (30-40% of traffic) with chat/booking"
        elif form_field_count > 5:
            upside_estimate = "Increase form submissions 20-30% by reducing friction"
        
        if upside_estimate:
            bullets.append({
                "type": "upside",
                "estimate": upside_estimate,
            })
        
        # Ensure we have 3 bullets
        while len(bullets) < 3:
            if len(bullets) == 0:
                bullets.append({
                    "type": "leak",
                    "evidence": "Landing page could benefit from conversion optimization",
                })
            elif len(bullets) == 1:
                bullets.append({
                    "type": "fix",
                    "specific": "Implement lead capture best practices",
                })
            else:
                bullets.append({
                    "type": "upside",
                    "estimate": "Potential 10-20% improvement in lead capture rate",
                })
        
        return bullets[:3]  # Return exactly 3 bullets
    
    def _save_proof(self, proof: Dict[str, Any]) -> None:
        """Save proof artifact to database."""
        data = dict(proof)
        data["lead_id"] = str(proof.get("lead_id", ""))
        data["generated_at"] = datetime.utcnow().isoformat()
        
        # audit_bullets is already a list of dicts
        
        self._db.save_proof_artifact(data)


_audit_agent: Optional[AuditAgent] = None


def _get_audit_agent() -> AuditAgent:
    global _audit_agent
    if _audit_agent is None:
        _audit_agent = AuditAgent()
    return _audit_agent


def audit_node(state: LeadGraphState) -> LeadGraphState:
    """LangGraph node function for audit."""
    return _get_audit_agent()(state)
