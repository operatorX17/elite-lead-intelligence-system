"""
Steel Enrichment using MCP Server
Uses Steel MCP tools for cloud browser automation
"""

import os
import logging
from typing import Dict, Any
from datetime import datetime
import re
from pathlib import Path

logger = logging.getLogger(__name__)


class SteelEnrichmentMCP:
    """Steel enrichment using MCP server"""
    
    def __init__(self, mcp_client):
        """
        Initialize with MCP client
        
        Args:
            mcp_client: The MCP client instance that can call Steel tools
        """
        self.mcp = mcp_client
        self.screenshots_dir = Path("screenshots")
        self.screenshots_dir.mkdir(exist_ok=True)
    
    async def analyze_website(self, website: str, business_name: str) -> Dict[str, Any]:
        """
        Analyze website using Steel MCP tools
        
        Args:
            website: URL to analyze
            business_name: Name of business for screenshot naming
            
        Returns:
            Dict with signals and screenshot path
        """
        
        if not website:
            return {"status": "no_website"}
        
        try:
            # Navigate to website using Steel MCP
            logger.info(f"Navigating to {website} via Steel MCP")
            await self.mcp.call_tool("mcp_steel_mcp_server_navigate", {"url": website})
            
            # Wait for page load
            await self.mcp.call_tool("mcp_steel_mcp_server_wait", {"seconds": 3})
            
            # Get page content (Steel MCP provides annotated screenshots)
            # The screenshot is automatically captured by Steel MCP
            
            # Save screenshot with business name
            screenshot_name = f"{business_name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            screenshot_path = await self.mcp.call_tool(
                "mcp_steel_mcp_server_save_unmarked_screenshot",
                {"resourceName": screenshot_name}
            )
            
            # Extract signals from the page
            # Steel MCP doesn't give us raw HTML, so we'll use heuristics based on URL patterns
            signals = self.extract_signals_from_url(website)
            signals["screenshot"] = screenshot_path
            signals["status"] = "success"
            
            return signals
            
        except Exception as e:
            logger.error(f"Error analyzing website {website}: {e}")
            return {"status": "error", "error": str(e)}
    
    def extract_signals_from_url(self, url: str) -> Dict[str, Any]:
        """
        Extract basic signals from URL patterns
        Since Steel MCP doesn't expose HTML, we use URL-based heuristics
        """
        
        url_lower = url.lower()
        
        signals = {
            "has_booking_system": False,
            "has_whatsapp": False,
            "has_lead_form": True,  # Assume most healthcare sites have forms
            "has_click_to_call": True,  # Assume most have phone
            "has_chat_widget": False,
            "emails": [],
            "phones": [],
            "booking_links": [],
            "social_links": {}
        }
        
        # Check for known booking platforms in URL
        if any(x in url_lower for x in ["practo", "calendly", "zocdoc", "bookingpress"]):
            signals["has_booking_system"] = True
        
        # Check for WhatsApp in URL
        if "whatsapp" in url_lower or "wa.me" in url_lower:
            signals["has_whatsapp"] = True
        
        return signals


def create_steel_enrichment_simple():
    """
    Create a simple Steel enrichment that doesn't require MCP
    Uses direct HTTP calls to Steel API
    """
    
    import aiohttp
    
    STEEL_API_KEY = os.getenv("STEEL_API_KEY")
    STEEL_API_URL = "https://api.steel.dev/v1"
    
    class SimpleSteel:
        def __init__(self):
            self.screenshots_dir = Path("screenshots")
            self.screenshots_dir.mkdir(exist_ok=True)
        
        async def analyze_website(self, website: str, business_name: str) -> Dict[str, Any]:
            """Analyze website using direct Steel API calls"""
            
            if not website or not STEEL_API_KEY:
                return {"status": "no_api_key" if not STEEL_API_KEY else "no_website"}
            
            try:
                async with aiohttp.ClientSession() as session:
                    headers = {
                        "Authorization": f"Bearer {STEEL_API_KEY}",
                        "Content-Type": "application/json"
                    }
                    
                    # Create session
                    async with session.post(
                        f"{STEEL_API_URL}/sessions",
                        headers=headers,
                        json={"useProxy": True, "solveCaptchas": True},
                        timeout=aiohttp.ClientTimeout(total=30)
                    ) as resp:
                        if resp.status not in [200, 201]:
                            logger.error(f"Failed to create session: {resp.status}")
                            return {"status": "session_failed"}
                        
                        session_data = await resp.json()
                        session_id = session_data.get("id") or session_data.get("sessionId")
                    
                    # Navigate
                    async with session.post(
                        f"{STEEL_API_URL}/sessions/{session_id}/navigate",
                        headers=headers,
                        json={"url": website},
                        timeout=aiohttp.ClientTimeout(total=30)
                    ) as resp:
                        if resp.status != 200:
                            logger.error(f"Navigation failed: {resp.status}")
                    
                    # Wait
                    import asyncio
                    await asyncio.sleep(3)
                    
                    # Scrape
                    async with session.get(
                        f"{STEEL_API_URL}/sessions/{session_id}/scrape",
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=30)
                    ) as resp:
                        if resp.status == 200:
                            content = await resp.json()
                            html = str(content.get("content", ""))
                        else:
                            html = ""
                    
                    # Screenshot
                    screenshot_path = ""
                    async with session.get(
                        f"{STEEL_API_URL}/sessions/{session_id}/screenshot",
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=30)
                    ) as resp:
                        if resp.status == 200:
                            screenshot_data = await resp.read()
                            safe_name = re.sub(r'[^\w\s-]', '', business_name).strip().replace(' ', '_')
                            filename = f"{safe_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                            filepath = self.screenshots_dir / filename
                            with open(filepath, 'wb') as f:
                                f.write(screenshot_data)
                            screenshot_path = str(filepath)
                    
                    # Release session
                    async with session.post(
                        f"{STEEL_API_URL}/sessions/{session_id}/release",
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=10)
                    ) as resp:
                        pass
                    
                    # Extract signals
                    signals = extract_signals_from_html(html)
                    signals["screenshot"] = screenshot_path
                    signals["status"] = "success"
                    
                    return signals
                    
            except Exception as e:
                logger.error(f"Steel API error: {e}")
                return {"status": "error", "error": str(e)}
    
    return SimpleSteel()


def extract_signals_from_html(html: str) -> Dict[str, Any]:
    """Extract signals from HTML content"""
    
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
        "online booking", "calendly", "practo", "zocdoc"
    ]
    signals["has_booking_system"] = any(kw in html_lower for kw in booking_keywords)
    
    # WhatsApp
    signals["has_whatsapp"] = any(kw in html_lower for kw in ["whatsapp", "wa.me"])
    
    # Lead form
    signals["has_lead_form"] = "<form" in html_lower or "contact form" in html_lower
    
    # Click to call
    signals["has_click_to_call"] = "tel:" in html_lower
    
    # Chat widget
    chat_keywords = ["tawk.to", "intercom", "drift", "crisp", "livechat"]
    signals["has_chat_widget"] = any(kw in html_lower for kw in chat_keywords)
    
    # Extract emails
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    emails = re.findall(email_pattern, html)
    signals["emails"] = list(set(emails))[:5]
    
    # Extract phones
    phone_pattern = r'\+91[\s-]?\d{10}|\d{10}'
    phones = re.findall(phone_pattern, html)
    signals["phones"] = list(set(phones))[:5]
    
    return signals
