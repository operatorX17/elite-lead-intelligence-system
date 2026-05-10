"""
Test Steel CLI directly
"""

import asyncio
from src.tools.steel_cli import SteelCLI


async def test():
    steel = SteelCLI()
    
    print("Testing Steel CLI with Apollo Diagnostics...")
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
