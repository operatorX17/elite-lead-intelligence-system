"""
Test Steel Playwright directly
"""

import asyncio
from dotenv import load_dotenv
load_dotenv()

from src.tools.steel_playwright import SteelPlaywright


async def test():
    steel = SteelPlaywright()
    
    print("Testing Steel Playwright with Apollo Diagnostics...")
    result = await steel.analyze_website(
        "https://www.apollodiagnostics.in",
        "Apollo Diagnostics"
    )
    
    print("\nResults:")
    print(f"Status: {result.get('status')}")
    print(f"Has booking: {result.get('has_booking_system')}")
    print(f"Has WhatsApp: {result.get('has_whatsapp')}")
    print(f"Has form: {result.get('has_lead_form')}")
    print(f"Has click-to-call: {result.get('has_click_to_call')}")
    print(f"Emails: {result.get('emails', [])}")
    print(f"Phones: {result.get('phones', [])}")


if __name__ == "__main__":
    asyncio.run(test())
