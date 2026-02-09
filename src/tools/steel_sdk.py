"""
Steel SDK Wrapper - Use Steel browser via Python SDK
Direct SDK calls - simple and fast
"""

import os
import logging
from typing import Dict, Any
from pathlib import Path
import re

logger = logging.getLogger(__name__)

STEEL_API_KEY = os.getenv("STEEL_API_KEY")


class SteelSDK:
    """Wrapper for Steel Python SDK"""
    
    def __init__(self):
        self.screenshots_dir = Path("screenshots")
        self.screenshots_dir.mkdir(exist_ok=True)
        self.steel = None
    
    async def analyze_website(self, website: str, business_name: str) -> Dict[str, Any]:
        """
        Analyze website using Steel SDK
        """
        
        if not website:
            return {"status": "no_website"}
        
        if not STEEL_API_KEY:
            logger.error("[STEEL SDK] No API key")
            return self._fallback_signals(website)
        
        try:
            # Import Steel SDK
            from steel import Steel
            
            logger.info(f"[STEEL SDK] Analyzing {website}")
            
            # Initialize Steel client (uses STEEL_API_KEY env var automatically)
            if not self.steel:
                self.steel = Steel()
            
            # Create a session
            session = await self.steel.sessions.create()
            session_id = session.id
            
            logger.info(f"[STEEL SDK] Session created: {session_id}")
            
            try:
                # Navigate to website
                await session.navigate(url=website)
                
                # Wait for page load
                await session.wait(2000)
                
                # Get page content
                content = await session.scrape()
                html = content.get("content", "") if content else ""
                
                logger.info(f"[STEEL SDK] Scraped {len(html)} chars")
                
                # Extract signals
                signals = self._extract_signals(html, website)
                signals["status"] = "steel_sdk_success"
                
                return signals
                
            finally:
                # Release session
                try:
                    await self.steel.sessions.release(session_id)
                    logger.info(f"[STEEL SDK] Session released: {session_id}")
                except:
                    pass
                    
        except ImportError:
            logger.warning("[STEEL SDK] SDK not installed - using fallback")
            return self._fallback_signals(website)
        except Exception as e:
            logger.error(f"[STEEL SDK] Error: {e}")
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
        """Fallback when Steel SDK fails"""
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
