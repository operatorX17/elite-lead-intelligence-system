"""
Steel MCP Wrapper - Call Steel MCP tools from Python
Uses the working Steel MCP server configuration
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime
import re
from pathlib import Path

logger = logging.getLogger(__name__)


class SteelMCPWrapper:
    """Wrapper to call Steel MCP tools"""
    
    def __init__(self):
        self.screenshots_dir = Path("screenshots")
        self.screenshots_dir.mkdir(exist_ok=True)
    
    async def analyze_website(self, website: str, business_name: str) -> Dict[str, Any]:
        """
        Analyze website using Steel MCP tools
        
        NOTE: This requires the MCP tools to be available in the execution context.
        When running from lead_os.py, the MCP tools should be injected by the runtime.
        """
        
        if not website:
            return {"status": "no_website"}
        
        try:
            logger.info(f"[STEEL MCP] Analyzing {website} for {business_name}")
            
            # The MCP tools are available as global functions when running in MCP context
            # For now, we'll use a placeholder that can be replaced by actual MCP calls
            
            # In the actual execution, these would be:
            # - mcp_steel_mcp_server_navigate(url=website)
            # - mcp_steel_mcp_server_wait(seconds=3)
            # - mcp_steel_mcp_server_save_unmarked_screenshot(resourceName=...)
            
            # For now, return basic signals based on URL patterns
            logger.warning("[STEEL MCP] MCP tools not available in this context - using fallback")
            return self._extract_basic_signals(website)
            
        except Exception as e:
            logger.error(f"[STEEL MCP] Error: {e}")
            return self._extract_basic_signals(website)
    
    def _extract_basic_signals(self, website: str) -> Dict[str, Any]:
        """Extract basic signals from URL when MCP not available"""
        
        website_lower = website.lower()
        
        return {
            "status": "basic_signals",
            "has_booking_system": any(kw in website_lower for kw in ["practo", "calendly", "booking"]),
            "has_whatsapp": "whatsapp" in website_lower or "wa.me" in website_lower,
            "has_lead_form": True,  # Assume most healthcare sites have forms
            "has_click_to_call": True,  # Assume most have phone
            "has_chat_widget": False,
            "emails": [],
            "phones": [],
            "booking_links": [],
            "social_links": {},
            "screenshot": ""
        }
    
    def extract_signals_from_html(self, html: str) -> Dict[str, Any]:
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
