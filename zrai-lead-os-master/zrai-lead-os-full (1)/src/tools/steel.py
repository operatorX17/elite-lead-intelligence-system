"""
Steel.dev client for browser automation.
Requirements: 6.2-6.6
Runtime: Uses official Steel SDK/HTTP (NOT MCP)
"""

from typing import Dict, Any, List, Optional
import logging
import time
import json
import urllib.request
import urllib.error
import base64

from src.config import load_config


logger = logging.getLogger(__name__)


class SteelClient:
    """
    Steel.dev client wrapper for ZRAI Lead OS.
    
    Requirements:
    - 6.2: Open landing_page_url in a real browser
    - 6.3: Interact like a human (scroll, click CTAs, open forms)
    - 6.4: Extract phone_visibility, form_field_count, booking_link, etc.
    - 6.5: Capture screenshots of hero section and CTA/form/phone section
    - 6.6: Save artifacts to object storage
    
    Runtime Architecture (Rule 3):
    - Uses official Steel SDK or direct HTTP/WebSocket calls
    - NOT MCP at runtime
    """
    
    BASE_URL = "https://api.steel.dev/v1"
    
    def __init__(self, api_key: Optional[str] = None):
        config = load_config()
        self._api_key = api_key or config.steel.api_key
        self._config = config.steel
    
    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make HTTP request to Steel API."""
        url = f"{self.BASE_URL}{endpoint}"
        
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        
        body = json.dumps(data).encode() if data else None
        
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        
        try:
            with urllib.request.urlopen(req, timeout=self._config.default_timeout_ms // 1000) as response:
                return json.loads(response.read().decode())
        except urllib.error.HTTPError as e:
            error_body = e.read().decode()
            logger.error(f"Steel API error: {e.code} - {error_body}")
            raise Exception(f"Steel API error: {e.code} - {error_body}")
    
    def create_session(self) -> Dict[str, Any]:
        """Create a new browser session."""
        logger.info("Creating Steel browser session")
        
        result = self._make_request("POST", "/sessions", {
            "timeout": self._config.default_timeout_ms,
        })
        
        return {
            "session_id": result.get("id") or result.get("sessionId"),
            "ws_url": result.get("wsUrl"),
            "status": result.get("status", "created"),
        }
    
    def close_session(self, session_id: str) -> None:
        """Close a browser session."""
        logger.info(f"Closing Steel session: {session_id}")
        
        try:
            self._make_request("DELETE", f"/sessions/{session_id}")
        except Exception as e:
            logger.warning(f"Error closing session: {e}")
    
    def navigate(self, session_id: str, url: str) -> Dict[str, Any]:
        """Navigate to a URL."""
        logger.info(f"Navigating to: {url}")
        
        return self._make_request("POST", f"/sessions/{session_id}/navigate", {
            "url": url,
            "waitUntil": "networkidle",
        })
    
    def screenshot(
        self,
        session_id: str,
        full_page: bool = False,
        selector: Optional[str] = None,
    ) -> bytes:
        """Take a screenshot."""
        logger.info(f"Taking screenshot (full_page={full_page}, selector={selector})")
        
        data = {
            "fullPage": full_page,
        }
        if selector:
            data["selector"] = selector
        
        result = self._make_request("POST", f"/sessions/{session_id}/screenshot", data)
        
        # Result should contain base64 encoded image
        if result.get("data"):
            return base64.b64decode(result["data"])
        elif result.get("screenshot"):
            return base64.b64decode(result["screenshot"])
        
        return b""
    
    def click(self, session_id: str, selector: str) -> Dict[str, Any]:
        """Click an element."""
        logger.info(f"Clicking: {selector}")
        
        return self._make_request("POST", f"/sessions/{session_id}/click", {
            "selector": selector,
        })
    
    def scroll(
        self,
        session_id: str,
        direction: str = "down",
        amount: int = 500,
    ) -> Dict[str, Any]:
        """Scroll the page."""
        logger.info(f"Scrolling {direction} by {amount}px")
        
        return self._make_request("POST", f"/sessions/{session_id}/scroll", {
            "direction": direction,
            "amount": amount,
        })
    
    def evaluate(self, session_id: str, script: str) -> Any:
        """Execute JavaScript in the browser."""
        result = self._make_request("POST", f"/sessions/{session_id}/evaluate", {
            "script": script,
        })
        return result.get("result")
    
    def extract_page_data(self, session_id: str) -> Dict[str, Any]:
        """
        Extract structured data from the current page.
        Requirements: 6.4
        """
        logger.info("Extracting page data")
        
        # JavaScript to extract relevant data
        extraction_script = """
        (() => {
            const data = {
                phone_numbers: [],
                forms: [],
                booking_links: [],
                cta_buttons: [],
                business_hours: null,
                chat_widget: null,
            };
            
            // Find phone numbers
            const phoneRegex = /(\+?1?[-.\s]?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4})/g;
            const bodyText = document.body.innerText;
            const phones = bodyText.match(phoneRegex) || [];
            data.phone_numbers = [...new Set(phones)];
            
            // Find forms
            const forms = document.querySelectorAll('form');
            forms.forEach((form, i) => {
                const inputs = form.querySelectorAll('input, textarea, select');
                data.forms.push({
                    index: i,
                    field_count: inputs.length,
                    has_email: !!form.querySelector('input[type="email"]'),
                    has_phone: !!form.querySelector('input[type="tel"]'),
                });
            });
            
            // Find booking links
            const bookingKeywords = ['book', 'schedule', 'appointment', 'calendar', 'reserve'];
            const links = document.querySelectorAll('a');
            links.forEach(link => {
                const text = (link.innerText + ' ' + link.href).toLowerCase();
                if (bookingKeywords.some(kw => text.includes(kw))) {
                    data.booking_links.push({
                        text: link.innerText.trim(),
                        href: link.href,
                    });
                }
            });
            
            // Find CTA buttons
            const buttons = document.querySelectorAll('button, a.btn, a.button, [role="button"]');
            buttons.forEach(btn => {
                const text = btn.innerText.trim();
                if (text && text.length < 50) {
                    data.cta_buttons.push(text);
                }
            });
            
            // Check for chat widgets
            const chatSelectors = [
                '[class*="chat"]',
                '[id*="chat"]',
                '[class*="intercom"]',
                '[class*="drift"]',
                '[class*="zendesk"]',
                '[class*="crisp"]',
            ];
            for (const selector of chatSelectors) {
                if (document.querySelector(selector)) {
                    data.chat_widget = selector;
                    break;
                }
            }
            
            // Find business hours
            const hoursRegex = /(\d{1,2}(?::\d{2})?\s*(?:am|pm|AM|PM)?\s*[-–]\s*\d{1,2}(?::\d{2})?\s*(?:am|pm|AM|PM)?)/g;
            const hoursMatches = bodyText.match(hoursRegex);
            if (hoursMatches) {
                data.business_hours = hoursMatches[0];
            }
            
            return data;
        })()
        """
        
        return self.evaluate(session_id, extraction_script)
    
    def check_phone_visibility(self, session_id: str) -> str:
        """
        Check phone number visibility on page.
        Requirements: 6.4
        Returns: 'above_fold', 'below_fold', 'hidden', or 'none'
        """
        script = """
        (() => {
            const phoneRegex = /(\+?1?[-.\s]?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4})/;
            const viewportHeight = window.innerHeight;
            
            // Check all text nodes
            const walker = document.createTreeWalker(
                document.body,
                NodeFilter.SHOW_TEXT,
                null,
                false
            );
            
            while (walker.nextNode()) {
                const node = walker.currentNode;
                if (phoneRegex.test(node.textContent)) {
                    const range = document.createRange();
                    range.selectNode(node);
                    const rect = range.getBoundingClientRect();
                    
                    if (rect.top < viewportHeight) {
                        return 'above_fold';
                    } else {
                        return 'below_fold';
                    }
                }
            }
            
            // Check for click-to-reveal phone
            const phoneButtons = document.querySelectorAll('[onclick*="phone"], [data-phone], .phone-reveal');
            if (phoneButtons.length > 0) {
                return 'hidden';
            }
            
            return 'none';
        })()
        """
        
        result = self.evaluate(session_id, script)
        return result or "none"
    
    def audit_landing_page(self, url: str) -> Dict[str, Any]:
        """
        Full audit of a landing page.
        Requirements: 6.2-6.6
        
        Returns extraction data and screenshots.
        """
        logger.info(f"Auditing landing page: {url}")
        
        session = None
        try:
            # Create session
            session = self.create_session()
            session_id = session["session_id"]
            
            # Navigate to page
            self.navigate(session_id, url)
            time.sleep(2)  # Wait for page to load
            
            # Take hero screenshot (viewport)
            hero_screenshot = self.screenshot(session_id, full_page=False)
            
            # Scroll down to reveal content
            self.scroll(session_id, "down", 500)
            time.sleep(1)
            
            # Extract page data
            extraction_data = self.extract_page_data(session_id)
            
            # Check phone visibility
            phone_visibility = self.check_phone_visibility(session_id)
            extraction_data["phone_visibility"] = phone_visibility
            
            # Try to click CTA buttons to reveal forms/phone
            cta_selectors = [
                'button:contains("Call")',
                'button:contains("Contact")',
                'a:contains("Book")',
                '.cta-button',
                '[data-action="call"]',
            ]
            
            for selector in cta_selectors:
                try:
                    self.click(session_id, selector)
                    time.sleep(0.5)
                except:
                    pass
            
            # Take CTA section screenshot
            cta_screenshot = self.screenshot(session_id, full_page=False)
            
            # Calculate form field count
            form_field_count = 0
            if extraction_data.get("forms"):
                form_field_count = max(f.get("field_count", 0) for f in extraction_data["forms"])
            
            extraction_data["form_field_count"] = form_field_count
            extraction_data["booking_link"] = extraction_data.get("booking_links", [{}])[0].get("href") if extraction_data.get("booking_links") else None
            extraction_data["after_hours_capture"] = bool(extraction_data.get("chat_widget") or extraction_data.get("forms"))
            
            return {
                "url": url,
                "hero_screenshot": hero_screenshot,
                "cta_screenshot": cta_screenshot,
                "extraction_data": extraction_data,
                "success": True,
            }
            
        except Exception as e:
            logger.error(f"Landing page audit error: {e}")
            return {
                "url": url,
                "error": str(e),
                "success": False,
            }
            
        finally:
            if session:
                self.close_session(session["session_id"])
