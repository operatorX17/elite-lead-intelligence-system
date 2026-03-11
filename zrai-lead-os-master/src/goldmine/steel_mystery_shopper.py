"""
STEEL MYSTERY SHOPPER - Real browser automation for mystery shopping.

This module provides functions that can be called from the CLI or 
integrated with the Goldmine pipeline to perform REAL mystery shopping
using the Steel MCP server.

Usage:
    from src.goldmine.steel_mystery_shopper import mystery_shop_website
    
    result = await mystery_shop_website("https://example.com")
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional
import random

logger = logging.getLogger(__name__)


# Mystery shopping identities
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


class SteelMysteryShopperInstructions:
    """
    Instructions for mystery shopping using Steel MCP.
    
    This class provides step-by-step instructions that can be executed
    via the Steel MCP tools (navigate, click, type, scroll_down, etc.)
    
    The actual execution happens through the MCP tools in the chat interface.
    """
    
    @staticmethod
    def get_mystery_shop_steps(website_url: str) -> Dict[str, Any]:
        """
        Get step-by-step instructions for mystery shopping a website.
        
        Returns a dict with:
        - identity: The fake identity to use
        - steps: List of MCP tool calls to execute
        """
        identity = random.choice(MYSTERY_IDENTITIES)
        
        return {
            "identity": identity,
            "website": website_url,
            "steps": [
                {
                    "action": "navigate",
                    "tool": "mcp_steel_mcp_server_navigate",
                    "params": {"url": website_url},
                    "description": f"Navigate to {website_url}",
                },
                {
                    "action": "screenshot",
                    "tool": "mcp_steel_mcp_server_save_unmarked_screenshot",
                    "params": {"resourceName": "hero_screenshot"},
                    "description": "Capture hero section screenshot",
                },
                {
                    "action": "find_contact",
                    "description": "Look for 'Contact', 'Contact Us', or 'Get Quote' link/button and click it",
                    "hint": "Usually in the navigation bar or as a CTA button",
                },
                {
                    "action": "scroll_to_form",
                    "tool": "mcp_steel_mcp_server_scroll_down",
                    "params": {"pixels": 400},
                    "description": "Scroll down to find contact form",
                },
                {
                    "action": "fill_form",
                    "description": "Fill in the contact form fields",
                    "fields": {
                        "first_name": identity["first_name"],
                        "last_name": identity["last_name"],
                        "email": identity["email"],
                        "phone": identity["phone"],
                        "message": identity["message"],
                    },
                },
                {
                    "action": "screenshot_form",
                    "tool": "mcp_steel_mcp_server_save_unmarked_screenshot",
                    "params": {"resourceName": "filled_form_screenshot"},
                    "description": "Capture screenshot of filled form (before submit)",
                },
                {
                    "action": "submit",
                    "description": "Click the Submit/Send button",
                    "note": "Record the exact time of submission",
                },
                {
                    "action": "screenshot_confirmation",
                    "tool": "mcp_steel_mcp_server_save_unmarked_screenshot",
                    "params": {"resourceName": "confirmation_screenshot"},
                    "description": "Capture confirmation page/message",
                },
            ],
            "tracking": {
                "submission_time": None,  # To be filled when form is submitted
                "response_time": None,    # To be filled when response is received
                "response_quality": None, # "excellent", "good", "poor", "none"
            },
        }
    
    @staticmethod
    def calculate_response_score(
        form_submitted: bool,
        response_received: bool,
        response_time_hours: Optional[float],
    ) -> int:
        """
        Calculate response score (0-100).
        
        Scoring:
        - Response within 5 min: 100
        - Response within 1 hour: 80
        - Response within 4 hours: 60
        - Response within 24 hours: 40
        - Response > 24 hours: 20
        - No response: 20
        - No form found: 30
        """
        if not form_submitted:
            return 30  # No form to test
        
        if not response_received:
            return 20  # No response
        
        if response_time_hours is None:
            return 20
        
        if response_time_hours <= 0.083:  # 5 minutes
            return 100
        elif response_time_hours <= 1:
            return 80
        elif response_time_hours <= 4:
            return 60
        elif response_time_hours <= 24:
            return 40
        else:
            return 20


def generate_mystery_shop_report(
    business_name: str,
    website: str,
    form_submitted: bool,
    submission_time: Optional[datetime],
    screenshots: list,
    notes: str = "",
) -> Dict[str, Any]:
    """
    Generate a mystery shopping report.
    
    This can be called after completing the Steel MCP mystery shopping steps.
    """
    return {
        "business_name": business_name,
        "website": website,
        "form_submitted": form_submitted,
        "submission_time": submission_time.isoformat() if submission_time else None,
        "screenshots": screenshots,
        "notes": notes,
        "status": "awaiting_response" if form_submitted else "no_form_found",
        "created_at": datetime.utcnow().isoformat(),
    }


# Quick reference for Steel MCP tools:
STEEL_MCP_TOOLS = """
Available Steel MCP Tools:
- mcp_steel_mcp_server_navigate(url) - Navigate to a URL
- mcp_steel_mcp_server_click(label) - Click element by label number
- mcp_steel_mcp_server_type(label, text, replaceText=False) - Type into input
- mcp_steel_mcp_server_scroll_down(pixels) - Scroll down
- mcp_steel_mcp_server_scroll_up(pixels) - Scroll up
- mcp_steel_mcp_server_go_back() - Go back in history
- mcp_steel_mcp_server_wait(seconds) - Wait for page load
- mcp_steel_mcp_server_save_unmarked_screenshot(resourceName) - Save screenshot
- mcp_steel_mcp_server_search(query) - Google search
"""
