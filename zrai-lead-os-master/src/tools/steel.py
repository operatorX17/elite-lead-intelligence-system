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
from datetime import datetime

from src.config import load_config

logger = logging.getLogger(__name__)


class SteelClient:
    """Steel.dev client wrapper - PRODUCTION READY"""
    
    BASE_URL = "https://api.steel.dev/v1"
    
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
            result = self.scrape(url, screenshot=True, extract_html=True, delay=3)
            
            html = result.get("html", "")
            screenshot_b64 = result.get("screenshot", "")
            
            # Extract data from HTML
            import re
            
            # Phone numbers
            phone_regex = r'(\+?1?[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})'
            phone_numbers = list(set(re.findall(phone_regex, html)))
            
            # Forms (count <form> tags)
            form_count = html.count('<form')
            
            # Booking keywords
            booking_keywords = ['book', 'schedule', 'appointment', 'reserve', 'consultation']
            has_booking = any(kw in html.lower() for kw in booking_keywords)
            
            # CTA buttons
            cta_keywords = ['contact', 'call', 'email', 'get started', 'book now', 'schedule']
            has_cta = any(kw in html.lower() for kw in cta_keywords)
            
            # Business hours
            hours_keywords = ['hours', 'open', 'monday', 'tuesday', 'am', 'pm']
            has_hours = sum(1 for kw in hours_keywords if kw in html.lower()) >= 3
            
            extraction_data = {
                "phone_numbers": phone_numbers[:5],  # Top 5
                "form_count": form_count,
                "has_booking_link": has_booking,
                "has_cta": has_cta,
                "has_business_hours": has_hours,
                "phone_visible": len(phone_numbers) > 0
            }
            
            # Decode screenshot
            screenshot_bytes = base64.b64decode(screenshot_b64) if screenshot_b64 else None
            
            return {
                "url": url,
                "extraction_data": extraction_data,
                "hero_screenshot": screenshot_bytes,
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

