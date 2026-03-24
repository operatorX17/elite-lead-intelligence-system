"""
Steel.dev client for browser automation - PRODUCTION VERSION
Uses Steel API v1 with correct authentication header
"""

from typing import Dict, Any, List, Optional
import logging
import time
import json
import requests
import base64
import re
from datetime import datetime
from io import BytesIO

from PIL import Image
from bs4 import BeautifulSoup

from src.config import load_config

logger = logging.getLogger(__name__)


class SteelClient:
    """Steel.dev client wrapper - PRODUCTION READY"""
    
    BASE_URL = "https://api.steel.dev/v1"
    PHONE_REGEX = r"(?:\+?\d[\d\s().-]{8,}\d)"
    
    def __init__(self, api_key: Optional[str] = None):
        config = load_config()
        self._api_key = api_key or config.steel.api_key
        self._config = config.steel
        
        if not self._api_key or not self._api_key.startswith('ste-'):
            raise ValueError("Invalid Steel API key - must start with 'ste-'")
    
    def _make_request(self, method: str, endpoint: str, data: Optional[Dict] = None, timeout: int = 30) -> Dict:
        """Make HTTP request to Steel API with correct authentication"""
        url = f"{self.BASE_URL}{endpoint}"
        headers = {
            "steel-api-key": self._api_key,  # CORRECT HEADER!
            "Content-Type": "application/json",
        }
        
        try:
            if method == "POST":
                response = requests.post(url, json=data, headers=headers, timeout=timeout)
            elif method == "GET":
                response = requests.get(url, headers=headers, timeout=timeout)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            response.raise_for_status()
            return response.json() if response.text else {}
            
        except requests.exceptions.HTTPError as e:
            error_msg = f"Steel API {e.response.status_code}"
            try:
                error_body = e.response.json()
                error_msg += f": {error_body}"
            except:
                error_msg += f": {e.response.text}"
            logger.error(error_msg)
            raise Exception(error_msg)
        except Exception as e:
            logger.error(f"Steel request failed: {e}")
            raise
    
    def scrape(self, url: str, screenshot: bool = True, extract_html: bool = True, 
               extract_markdown: bool = False, delay: int = 2) -> Dict[str, Any]:
        """
        Simple scrape endpoint - best for quick page extraction
        
        Args:
            url: URL to scrape
            screenshot: Capture screenshot
            extract_html: Extract HTML content
            extract_markdown: Extract as markdown
            delay: Wait time in seconds before extraction
            
        Returns:
            Dict with html, markdown, screenshot (base64), etc.
        """
        logger.info(f"Scraping: {url}")
        
        formats = []
        if extract_html:
            formats.append("html")
        if extract_markdown:
            formats.append("markdown")
        
        payload = {
            "url": url,
            "format": formats,
            "screenshot": screenshot,
            "delay": delay,
            "useProxy": False,
            "solveCaptcha": True
        }
        
        try:
            result = self._make_request("POST", "/scrape", payload, timeout=60)
            logger.info(f"Scrape successful: {url}")
            return result
        except Exception as e:
            logger.error(f"Scrape failed for {url}: {e}")
            raise
    
    def create_session(self) -> Dict[str, Any]:
        """Create browser session for advanced automation"""
        logger.info("Creating Steel session")
        
        result = self._make_request("POST", "/sessions", {
            "useProxy": False,
            "solveCaptcha": True,
            "sessionTimeout": 300000  # 5 minutes
        })
        
        session_id = result.get("id")
        if not session_id:
            raise Exception(f"No session ID in response: {result}")
        
        logger.info(f"Created session {session_id}")
        return {
            "session_id": session_id,
            "status": result.get("status", "created"),
            "viewer_url": result.get("sessionViewerUrl"),
            "websocket_url": result.get("websocketUrl")
        }
    
    def close_session(self, session_id: str) -> None:
        """Close/release session"""
        try:
            self._make_request("POST", f"/sessions/{session_id}/release")
            logger.info(f"Session {session_id} released")
        except Exception as e:
            logger.warning(f"Failed to release session {session_id}: {e}")
    
    def audit_landing_page(self, url: str) -> Dict[str, Any]:
        """
        Full audit of landing page using simple scrape endpoint
        Extracts: phone numbers, forms, booking links, CTAs, screenshots
        """
        logger.info(f"Auditing: {url}")
        
        try:
            # Use simple scrape endpoint
            result = self.scrape(url, screenshot=True, extract_html=True, extract_markdown=True, delay=3)
            
            html = result.get("html", "")
            markdown = result.get("markdown", "")
            rendered_content = "\n".join(part for part in [html, markdown] if part)
            screenshot_payload = result.get("screenshot", "")
            
            phone_numbers = self._extract_phone_numbers(rendered_content)

            # Forms (count <form> tags)
            form_count = html.count('<form')

            # Booking keywords
            booking_keywords = ['book', 'schedule', 'appointment', 'reserve', 'consultation']
            lowered_rendered = rendered_content.lower()
            has_booking = any(kw in lowered_rendered for kw in booking_keywords)
            booking_link = self._extract_first_link(rendered_content, booking_keywords)

            # CTA buttons
            cta_keywords = ['contact', 'call', 'email', 'get started', 'book now', 'schedule']
            has_cta = any(kw in lowered_rendered for kw in cta_keywords)

            # Chat / after-hours capture
            chat_keywords = ['intercom', 'drift', 'zendesk', 'crisp', 'tawk', 'whatsapp', 'chat']
            chat_widget = self._detect_chat_widget(rendered_content, chat_keywords)
            whatsapp_target = self._extract_whatsapp_target(rendered_content)
            if whatsapp_target and not chat_widget:
                chat_widget = "whatsapp"
            after_hours_capture = bool(chat_widget or booking_link)

            # Business hours
            hours_keywords = ['hours', 'open', 'monday', 'tuesday', 'am', 'pm']
            has_hours = sum(1 for kw in hours_keywords if kw in lowered_rendered) >= 3

            phone_visibility = "hero" if phone_numbers else "none"

            extraction_data = {
                "phone_visibility": phone_visibility,
                "form_field_count": form_count,
                "booking_link": booking_link,
                "chat_widget": chat_widget,
                "whatsapp_target": whatsapp_target,
                "after_hours_capture": after_hours_capture,
                "phone_numbers": phone_numbers[:5],  # Top 5
                "form_count": form_count,
                "has_booking_link": has_booking,
                "has_cta": has_cta,
                "has_business_hours": has_hours,
                "phone_visible": len(phone_numbers) > 0,
            }
            
            # Decode screenshot payload. Steel may return either a raw base64
            # string or an object containing the base64/url fields.
            screenshot_b64 = screenshot_payload
            screenshot_source_url = None
            if isinstance(screenshot_payload, dict):
                screenshot_b64 = (
                    screenshot_payload.get("data")
                    or screenshot_payload.get("base64")
                    or screenshot_payload.get("content")
                    or screenshot_payload.get("url")
                    or ""
                )
                screenshot_source_url = screenshot_payload.get("url")

            screenshot_bytes = None
            if isinstance(screenshot_b64, str) and screenshot_b64:
                if screenshot_b64.startswith("http://") or screenshot_b64.startswith("https://"):
                    screenshot_source_url = screenshot_b64
                    try:
                        screenshot_response = requests.get(screenshot_b64, timeout=60)
                        screenshot_response.raise_for_status()
                        screenshot_bytes = screenshot_response.content
                    except Exception as exc:
                        logger.warning("Could not download Steel screenshot URL: %s", exc)
                else:
                    screenshot_bytes = base64.b64decode(screenshot_b64)

            hero_screenshot, cta_screenshot = self._split_screenshot_regions(
                screenshot_bytes
            )
            
            return {
                "url": url,
                "extraction_data": extraction_data,
                "hero_screenshot": hero_screenshot,
                "cta_screenshot": cta_screenshot,
                "hero_screenshot_url": screenshot_source_url,
                "cta_screenshot_url": screenshot_source_url,
                "rendered_html": html,
                "rendered_markdown": markdown,
                "rendered_content": rendered_content,
                "html_length": len(html),
                "success": True,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Audit failed for {url}: {e}")
            return {
                "url": url,
                "error": str(e),
                "success": False,
                "timestamp": datetime.utcnow().isoformat()
            }

    def scrape_page_bundle(self, url: str, delay: int = 3) -> Dict[str, Any]:
        """
        Fetch a rendered page bundle for deeper clinic analysis.

        Returns rendered content plus a screenshot payload so downstream
        extraction can fall back to vision when HTML/markdown is empty.
        """
        logger.info(f"Scraping page bundle: {url}")
        result = self.scrape(
            url,
            screenshot=True,
            extract_html=True,
            extract_markdown=True,
            delay=delay,
        )
        html = result.get("html", "") or ""
        markdown = result.get("markdown", "") or ""
        rendered_content = "\n".join(part for part in [html, markdown] if part)

        screenshot_payload = result.get("screenshot", "")
        screenshot_b64 = screenshot_payload
        screenshot_source_url = None
        if isinstance(screenshot_payload, dict):
            screenshot_b64 = (
                screenshot_payload.get("data")
                or screenshot_payload.get("base64")
                or screenshot_payload.get("content")
                or screenshot_payload.get("url")
                or ""
            )
            screenshot_source_url = screenshot_payload.get("url")

        screenshot_bytes = None
        if isinstance(screenshot_b64, str) and screenshot_b64:
            if screenshot_b64.startswith("http://") or screenshot_b64.startswith("https://"):
                screenshot_source_url = screenshot_b64
                try:
                    screenshot_response = requests.get(screenshot_b64, timeout=60)
                    screenshot_response.raise_for_status()
                    screenshot_bytes = screenshot_response.content
                except Exception as exc:
                    logger.warning("Could not download Steel screenshot URL: %s", exc)
            else:
                try:
                    screenshot_bytes = base64.b64decode(screenshot_b64)
                except Exception as exc:
                    logger.warning("Could not decode Steel screenshot payload: %s", exc)

        return {
            "url": url,
            "html": html,
            "markdown": markdown,
            "rendered_content": rendered_content,
            "screenshot_bytes": screenshot_bytes,
            "screenshot_url": screenshot_source_url,
        }

    def _split_screenshot_regions(
        self, screenshot_bytes: Optional[bytes]
    ) -> tuple[Optional[bytes], Optional[bytes]]:
        """Derive hero and CTA crops from a full-page screenshot."""
        if not screenshot_bytes:
            return None, None

        try:
            image = Image.open(BytesIO(screenshot_bytes))
            width, height = image.size

            hero_box = (0, 0, width, max(height // 3, 1))
            cta_top = min(max(height // 2, 0), max(height - 1, 0))
            cta_box = (0, cta_top, width, height)

            hero_image = image.crop(hero_box)
            cta_image = image.crop(cta_box)

            hero_buffer = BytesIO()
            cta_buffer = BytesIO()
            hero_image.save(hero_buffer, format="PNG")
            cta_image.save(cta_buffer, format="PNG")
            return hero_buffer.getvalue(), cta_buffer.getvalue()
        except Exception as exc:
            logger.warning("Failed to split screenshot regions: %s", exc)
            return screenshot_bytes, screenshot_bytes

    def _extract_first_link(self, html: str, keywords: List[str]) -> Optional[str]:
        """Return the first href matching booking keywords."""
        href_matches = re.findall(r'href=["\']([^"\']+)["\']', html, re.IGNORECASE)
        for href in href_matches:
            lowered = href.lower()
            if any(keyword in lowered for keyword in keywords):
                return href
        return None

    def _extract_whatsapp_target(self, html: str) -> Optional[str]:
        """Return the WhatsApp target phone or link if one exists."""
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

        try:
            soup = BeautifulSoup(html, "html.parser")
            visible_text = " ".join(soup.stripped_strings)
            whatsapp_text_match = re.search(
                r"whatsapp(?:\s*(?:us|now|chat|message|number|at|on))?[:\s-]*(\+?\d[\d\s().-]{7,}\d)",
                visible_text,
                re.IGNORECASE,
            )
            if whatsapp_text_match:
                normalized = re.sub(r"[^\d+]", "", whatsapp_text_match.group(1))
                if normalized:
                    return normalized
        except Exception:
            pass

        return None

    def _extract_phone_numbers(self, html: str) -> List[str]:
        """Extract international phone-like strings from visible text and link targets."""
        text_candidates = [html]
        try:
            soup = BeautifulSoup(html, "html.parser")
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
            logger.warning("Failed to parse Steel HTML for phone extraction: %s", exc)

        matches: List[str] = []
        for candidate in text_candidates:
            matches.extend(re.findall(self.PHONE_REGEX, candidate))
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
            elif not normalized.startswith("+") and digit_count == 10:
                # Keep naked 10-digit numbers as-is to avoid assuming wrong country code.
                normalized = normalized

            dedupe_key = re.sub(r"\D", "", normalized)
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            cleaned.append(normalized)

        return cleaned[:5]

    def _detect_chat_widget(self, html: str, keywords: List[str]) -> Optional[str]:
        lowered = html.lower()
        for keyword in keywords:
            if keyword in lowered:
                return keyword
        return None
