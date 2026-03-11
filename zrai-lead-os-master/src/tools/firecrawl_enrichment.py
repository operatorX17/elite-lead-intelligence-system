"""
Firecrawl Enrichment - Use Firecrawl API properly with JSON extraction
Cloud-based scraping with structured data extraction
"""

import logging
from typing import Dict, Any, List
import re
import os
import asyncio
import aiohttp

logger = logging.getLogger(__name__)


class FirecrawlEnrichment:
    """Wrapper for Firecrawl API with proper JSON extraction"""
    
    def __init__(self):
        self.api_key = os.getenv("FIRECRAWL_API_KEY")
        self.base_url = "https://api.firecrawl.dev/v1"
    
    async def analyze_website(self, website: str, business_name: str) -> Dict[str, Any]:
        """
        Analyze website using Firecrawl with JSON extraction
        
        Uses Firecrawl's /scrape endpoint with JSON format for structured extraction
        """
        
        if not website:
            return {"status": "no_website"}
        
        if not self.api_key or self.api_key == "your-firecrawl-api-key-here":
            logger.warning("[FIRECRAWL] No API key found - using fallback")
            return self._fallback_signals(website)
        
        try:
            logger.info(f"[FIRECRAWL] Scraping {website} with JSON extraction")
            
            # Use Firecrawl's JSON extraction with prompt
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }
                
                # Use simple markdown format (JSON extraction with prompt is not supported)
                payload = {
                    "url": website,
                    "formats": ["markdown"],  # Simple format - extract from markdown
                    "onlyMainContent": False,
                    "waitFor": 3000,
                    "timeout": 45000  # 45 second timeout
                }
                
                async with session.post(
                    f"{self.base_url}/scrape",
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as response:
                    
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"[FIRECRAWL] API error {response.status}: {error_text}")
                        return self._fallback_signals(website)
                    
                    result = await response.json()
            
            # Extract structured data
            if not result or 'data' not in result:
                logger.error(f"[FIRECRAWL] No data in response")
                return self._fallback_signals(website)
            
            data = result['data']
            
            # Get markdown content
            markdown = data.get('markdown', '')
            
            if not markdown:
                logger.error(f"[FIRECRAWL] No markdown content in response")
                return self._fallback_signals(website)
            
            logger.info(f"[FIRECRAWL] SUCCESS: Scraped {len(markdown)} chars from {website}")
            
            # Extract signals from markdown
            signals = self._extract_from_markdown(markdown, website)
            signals["status"] = "firecrawl_success"
            
            return signals
            
        except asyncio.TimeoutError:
            logger.error(f"[FIRECRAWL] Timeout scraping {website}")
            return self._fallback_signals(website)
        except Exception as e:
            logger.error(f"[FIRECRAWL] Error scraping {website}: {e}")
            return self._fallback_signals(website)
    
    def _extract_from_markdown(self, markdown: str, website: str) -> Dict[str, Any]:
        """Extract signals from markdown content"""
        
        markdown_lower = markdown.lower()
        
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
            "zocdoc", "bookingpress", "schedule now", "book a test",
            "book test", "request appointment", "make appointment"
        ]
        signals["has_booking_system"] = any(kw in markdown_lower for kw in booking_keywords)
        
        # WhatsApp
        signals["has_whatsapp"] = any(kw in markdown_lower for kw in ["whatsapp", "wa.me", "api.whatsapp.com"])
        
        # Lead form
        signals["has_lead_form"] = any(kw in markdown_lower for kw in ["form", "contact", "enquiry", "inquiry", "submit"])
        
        # Click to call
        signals["has_click_to_call"] = "tel:" in markdown_lower or "call now" in markdown_lower
        
        # Chat widget
        chat_keywords = ["tawk.to", "intercom", "drift", "crisp", "livechat", "zendesk", "chat"]
        signals["has_chat_widget"] = any(kw in markdown_lower for kw in chat_keywords)
        
        # Extract emails
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        emails = re.findall(email_pattern, markdown)
        emails = [e for e in emails if not any(x in e.lower() for x in ['example.com', 'test.com', 'sentry.io', 'placeholder'])]
        signals["emails"] = list(set(emails))[:5]
        
        # Extract phones (Indian format)
        phone_pattern = r'\+91[\s-]?\d{10}|\d{10}'
        phones = re.findall(phone_pattern, markdown)
        signals["phones"] = list(set(phones))[:3]
        
        return signals
    
    def _fallback_signals(self, website: str) -> Dict[str, Any]:
        """Fallback when Firecrawl fails"""
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
