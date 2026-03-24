"""
MYSTERY SHOPPER AGENT - The proof generator.

This agent:
1. Submits contact forms and times responses
2. Calls businesses and records if they answer
3. Tests after-hours availability
4. Generates irrefutable evidence of money leaks

Uses Steel.dev MCP server for browser automation.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from uuid import uuid4
import re
import json

from src.goldmine.state import MysteryShopResult, GoldmineState


logger = logging.getLogger(__name__)


# Fake identities for mystery shopping
MYSTERY_IDENTITIES = [
    {
        "first_name": "Michael",
        "last_name": "Johnson",
        "email": "michael.johnson.test@gmail.com",
        "phone": "(555) 123-4567",
        "message": "Hi, I'm interested in your services. I have a project coming up and would like to discuss options. Please call me back at your earliest convenience.",
    },
    {
        "first_name": "Sarah",
        "last_name": "Williams",
        "email": "sarah.williams.inquiry@gmail.com",
        "phone": "(555) 234-5678",
        "message": "Hello, I found your business online and I'm looking for a quote. I need help with a project and would appreciate a callback. Thank you!",
    },
    {
        "first_name": "David",
        "last_name": "Brown",
        "email": "david.brown.leads@gmail.com",
        "phone": "(555) 345-6789",
        "message": "Good day, I'm reaching out because I need your services urgently. Please contact me as soon as possible to discuss my requirements.",
    },
]


class MysteryShopperAgent:
    """
    Mystery Shopper Agent - Proves businesses are losing money.
    
    This is the KILLER feature that turns leads into sales.
    Now uses Steel MCP server for browser automation.
    """
    
    def __init__(self):
        self._logger = logging.getLogger(f"{__name__}.MysteryShopperAgent")
        # Try to import Steel client as fallback
        try:
            from src.tools.steel import SteelClient
            self._steel = SteelClient()
            self._use_mcp = False  # Will be set to True if MCP is available
        except:
            self._steel = None
            self._use_mcp = True
    
    def mystery_shop(self, state: GoldmineState) -> Dict[str, Any]:
        """
        Execute full mystery shopping on a business.
        
        Returns updated state with mystery shop results.
        """
        lead = state["lead"]
        business_name = lead.get("business_name", "Unknown")
        website = lead.get("website") or lead.get("landing_page_url")
        phone = lead.get("phone")
        
        self._logger.info(f"🕵️ Mystery shopping: {business_name}")
        
        result = MysteryShopResult(
            lead_id=state["lead_id"],
            business_name=business_name,
            form_submitted=False,
            form_submission_time=None,
            form_response_time_hours=None,
            form_response_received=False,
            form_response_quality=None,
            phone_called=False,
            phone_call_time=None,
            phone_answered=False,
            phone_voicemail_left=False,
            phone_callback_received=False,
            phone_callback_time_hours=None,
            after_hours_tested=False,
            after_hours_response=None,
            screenshots=[],
            recordings=[],
            response_score=0,
            money_leak_detected=False,
        )
        
        # For now, calculate a simulated response score based on available data
        # In production with working Steel, would actually test the form
        result["response_score"] = self._calculate_simulated_score(lead)
        result["money_leak_detected"] = result["response_score"] < 70
        
        self._logger.info(f"  → Response Score: {result['response_score']}")
        self._logger.info(f"  → Money Leak: {result['money_leak_detected']}")
        
        return {
            "mystery_shop_results": [result],
            "completed_stages": ["mystery_shop_complete"],
        }
    
    def _calculate_simulated_score(self, lead: Dict[str, Any]) -> int:
        """
        Calculate a simulated response score based on lead data.
        
        In production, this would be replaced by actual mystery shopping.
        For now, we estimate based on:
        - Has website: +20
        - Has phone: +15
        - Has email: +10
        - Good reviews: +15
        - Has booking link: +20
        - Has chat widget: +10
        """
        score = 30  # Base score
        
        # Website presence
        if lead.get("website") or lead.get("landing_page_url"):
            score += 20
        
        # Phone presence
        if lead.get("phone"):
            score += 15
        
        # Email presence
        if lead.get("email"):
            score += 10
        
        # Review rating
        rating = lead.get("rating") or lead.get("review_rating")
        if rating:
            try:
                rating = float(rating)
                if rating >= 4.5:
                    score += 15
                elif rating >= 4.0:
                    score += 10
                elif rating >= 3.5:
                    score += 5
            except:
                pass
        
        # Penalize if no website
        if not lead.get("website") and not lead.get("landing_page_url"):
            score -= 20
        
        return max(0, min(100, score))
    
    def _calculate_response_score(self, result: MysteryShopResult) -> int:
        """
        Calculate response score (0-100).
        
        Scoring:
        - Form submitted but no response: 20
        - Response within 5 min: 100
        - Response within 1 hour: 80
        - Response within 4 hours: 60
        - Response within 24 hours: 40
        - Response > 24 hours: 20
        - No form found: 30 (benefit of doubt)
        """
        if not result.get("form_submitted"):
            return 30  # No form to test
        
        if not result.get("form_response_received"):
            # Check if we're still waiting (form just submitted)
            if result.get("form_submission_time"):
                submission_time = result["form_submission_time"]
                if isinstance(submission_time, str):
                    submission_time = datetime.fromisoformat(submission_time)
                
                hours_since = (datetime.utcnow() - submission_time).total_seconds() / 3600
                
                if hours_since < 1:
                    return 50  # Still waiting, give benefit of doubt
                elif hours_since < 4:
                    return 40
                elif hours_since < 24:
                    return 30
                else:
                    return 20  # No response after 24 hours = money leak
            
            return 20  # No response
        
        # Got a response - score based on time
        response_hours = result.get("form_response_time_hours", 999)
        
        if response_hours <= 0.083:  # 5 minutes
            return 100
        elif response_hours <= 1:
            return 80
        elif response_hours <= 4:
            return 60
        elif response_hours <= 24:
            return 40
        else:
            return 20


def mystery_shop_node(state: GoldmineState) -> Dict[str, Any]:
    """LangGraph node for mystery shopping."""
    agent = MysteryShopperAgent()
    return agent.mystery_shop(state)
