"""
Steel Playwright Wrapper - Use Steel cloud browsers via Playwright
WebSocket connection - same as MCP but programmatic
"""

import os
import logging
from typing import Dict, Any
import re
import asyncio

logger = logging.getLogger(__name__)

STEEL_API_KEY = os.getenv("STEEL_API_KEY")


class SteelPlaywright:
    """Wrapper for Steel using Playwright WebSocket connection"""
    
    async def analyze_website(self, website: str, business_name: str) -> Dict[str, Any]:
        """
        Analyze website using Steel cloud browser via Playwright
        
        Uses WebSocket connection: wss://connect.steel.dev?apiKey=KEY
        This is the SAME method the MCP server uses
        """
        
        if not website:
            return {"status": "no_website"}
        
        if not STEEL_API_KEY:
            logger.error("[STEEL] No API key")
            return self._fallback_signals(website)
        
        try:
            from playwright.async_api import async_playwright
            
            logger.info(f"[STEEL] Analyzing {website} via cloud browser")
            
            async with async_playwright() as p:
                # Connect to Steel cloud browser via WebSocket
                # This is how MCP connects - same authentication method
                browser = await p.chromium.connect_over_cdp(
                    f'wss://connect.steel.dev?apiKey={STEEL_API_KEY}'
                )
                
                try:
                    # Get the default context and page
                    contexts = browser.contexts
                    if contexts:
                        context = contexts[0]
                        pages = context.pages
                        page = pages[0] if pages else await context.new_page()
                    else:
                        context = await browser.new_context()
                        page = await context.new_page()
                    
                    # Navigate to website
                    await page.goto(website, wait_until='networkidle', timeout=30000)
                    
                    # Wait a bit for dynamic content
                    await asyncio.sleep(2)
                    
                    # Get page content
                    html = await page.content()
                    
                    logger.info(f"[STEEL] Scraped {len(html)} chars from {website}")
                    
                    # Extract signals
                    signals = self._extract_signals(html, website)
                    signals["status"] = "steel_success"
                    
                    return signals
                    
                finally:
                    await browser.close()
                    
        except ImportError:
            logger.error("[STEEL] Playwright not installed: pip install playwright")
            return self._fallback_signals(website)
        except Exception as e:
            logger.error(f"[STEEL] Error: {e}")
            return self._fallback_signals(website)
    
    def _extract_signals(self, html: str, website: str) -> Dict[str, Any]:
        """Extract booking/contact signals from HTML"""
        
        html_lower = html.lower()
        
        signals = {
            "has_booking_system": False,
            "has_whatsapp": False,
            "has_lead_form": False,
            "has_click_to_call": False,
            "has_chat_widget": False,
            "emails": [],
            "phones": [],
            "booking_links": [],
            "social_links": {}
        }
        
        # Booking system
        booking_keywords = [
            "book appointment", "book now", "schedule appointment",
            "online booking", "book online", "calendly", "practo", 
            "zocdoc", "bookingpress", "schedule now"
        ]
        signals["has_booking_system"] = any(kw in html_lower for kw in booking_keywords)
        
        # WhatsApp
        signals["has_whatsapp"] = any(kw in html_lower for kw in ["whatsapp", "wa.me", "api.whatsapp.com"])
        
        # Lead form
        signals["has_lead_form"] = "<form" in html_lower or "contact form" in html_lower
        
        # Click to call
        signals["has_click_to_call"] = "tel:" in html_lower or "call now" in html_lower
        
        # Chat widget
        chat_keywords = ["tawk.to", "intercom", "drift", "crisp", "livechat", "zendesk"]
        signals["has_chat_widget"] = any(kw in html_lower for kw in chat_keywords)
        
        # Extract emails
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        emails = re.findall(email_pattern, html)
        emails = [e for e in emails if not any(x in e.lower() for x in ['example.com', 'test.com'])]
        signals["emails"] = list(set(emails))[:5]
        
        # Extract phones
        phone_pattern = r'\+91[\s-]?\d{10}|\d{10}'
        phones = re.findall(phone_pattern, html)
        signals["phones"] = list(set(phones))[:3]
        
        return signals
    
    def _fallback_signals(self, website: str) -> Dict[str, Any]:
        """Fallback when Steel fails"""
        website_lower = website.lower()
        return {
            "status": "fallback",
            "has_booking_system": any(kw in website_lower for kw in ["practo", "calendly", "zocdoc", "booking"]),
            "has_whatsapp": "whatsapp" in website_lower or "wa.me" in website_lower,
            "has_lead_form": True,
            "has_click_to_call": True,
            "has_chat_widget": False,
            "emails": [],
            "phones": [],
            "booking_links": [],
            "social_links": {}
        }
