"""
Steel Enrichment - Using Steel SDK
Direct SDK calls via steel-python package
"""

import os
import asyncio
from typing import Dict, Any
import logging
from datetime import datetime
import re
from pathlib import Path

logger = logging.getLogger(__name__)

STEEL_API_KEY = os.getenv("STEEL_API_KEY")


class SteelEnrichment:
    """Steel enrichment using Steel SDK"""
    
    def __init__(self):
        self.screenshots_dir = Path("screenshots")
        self.screenshots_dir.mkdir(exist_ok=True)
        self.steel = None
    
    async def analyze_website(self, website: str, business_name: str) -> Dict[str, Any]:
        """Analyze website using Steel SDK"""
        
        if not website:
            return {"status": "no_website"}
        
        if not STEEL_API_KEY:
            logger.error("[STEEL SDK] No API key found")
            return self._fallback_signals(website)
        
        try:
            # Import Steel SDK
            from steel import Steel
            
            logger.info(f"[STEEL SDK] Analyzing {website} for {business_name}")
            
            # Initialize Steel client (uses STEEL_API_KEY env var automatically)
            if not self.steel:
                self.steel = Steel(steel_api_key=STEEL_API_KEY)
            
            # Create a session
            session = await self.steel.sessions.create()
            session_id = session.id
            
            logger.info(f"[STEEL SDK] Session created: {session_id}")
            
            try:
                # Navigate to website
                await session.navigate(url=website)
                logger.info(f"[STEEL SDK] Navigated to {website}")
                
                # Wait for page load
                await session.wait(2000)
                
                # Get page content
                content = await session.scrape()
                html = content.get("content", "") if content else ""
                
                logger.info(f"[STEEL SDK] Scraped {len(html)} chars from {website}")
                
                # Extract signals
                signals = self.extract_signals(html)
                signals["status"] = "steel_sdk_success"
                signals["screenshot"] = ""  # TODO: Add screenshot capture
                
                logger.info(f"[STEEL SDK] Signals extracted: booking={signals.get('has_booking_system')}, whatsapp={signals.get('has_whatsapp')}")
                
                return signals
                
            finally:
                # Release session
                try:
                    await self.steel.sessions.release(session_id)
                    logger.info(f"[STEEL SDK] Session released: {session_id}")
                except Exception as e:
                    logger.warning(f"[STEEL SDK] Failed to release session: {e}")
                    
        except ImportError:
            logger.warning("[STEEL SDK] SDK not installed (pip install steel-python) - using fallback")
            return self._fallback_signals(website)
        except Exception as e:
            logger.error(f"[STEEL SDK] Error analyzing {website}: {e}")
            return self._fallback_signals(website)
    
    def _fallback_signals(self, website: str) -> Dict[str, Any]:
        """Fallback when Steel MCP fails"""
        return {
            "status": "fallback",
            "has_booking_system": "practo" in website.lower() or "calendly" in website.lower(),
            "has_whatsapp": False,
            "has_lead_form": True,
            "has_click_to_call": True,
            "has_chat_widget": False,
            "emails": [],
            "phones": [],
            "booking_links": [],
            "social_links": {},
            "screenshot": ""
        }
    
    def extract_signals(self, html: str) -> Dict[str, Any]:
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
        signals["phones"] = list(set(phones))[:5]
        
        # Booking links
        if "calendly.com" in html_lower:
            links = re.findall(r'https://calendly\.com/[^\s<>"\']+', html)
            signals["booking_links"].extend(links[:2])
        
        if "practo.com" in html_lower:
            links = re.findall(r'https://www\.practo\.com/[^\s<>"\']+', html)
            signals["booking_links"].extend(links[:2])
        
        # Social links
        if "instagram.com" in html_lower:
            links = re.findall(r'https://(?:www\.)?instagram\.com/[^\s<>"\']+', html)
            if links:
                signals["social_links"]["instagram"] = links[0]
        
        if "facebook.com" in html_lower:
            links = re.findall(r'https://(?:www\.)?facebook\.com/[^\s<>"\']+', html)
            if links:
                signals["social_links"]["facebook"] = links[0]
        
        return signals
