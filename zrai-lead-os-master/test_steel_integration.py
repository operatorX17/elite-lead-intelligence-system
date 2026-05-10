#!/usr/bin/env python
"""
Test Steel API integration
"""

import asyncio
import sys
import os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()  # Load .env first

from src.tools.steel_enrichment import SteelEnrichment
from rich.console import Console
import logging

console = Console()
logging.basicConfig(level=logging.INFO)

async def test_steel():
    """Test Steel API with a real website"""
    
    console.print("\n[bold]Testing Steel API Integration[/bold]\n")
    
    steel = SteelEnrichment()
    
    # Test with a known healthcare website
    test_website = "https://redcliffelabs.com/"
    test_business = "Redcliffe Labs"
    
    console.print(f"[yellow]Analyzing {test_website}...[/yellow]")
    
    try:
        result = await steel.analyze_website(test_website, test_business)
        
        console.print("\n[bold green]✅ Steel Analysis Result:[/bold green]")
        console.print(result)
        
        if result.get("status") == "success":
            console.print("\n[bold green]✅ Steel API is working![/bold green]")
            console.print(f"Booking system: {result.get('has_booking_system')}")
            console.print(f"WhatsApp: {result.get('has_whatsapp')}")
            console.print(f"Lead form: {result.get('has_lead_form')}")
            console.print(f"Screenshot: {result.get('screenshot')}")
        else:
            console.print(f"\n[bold red]❌ Steel API failed: {result.get('status')}[/bold red]")
            
    except Exception as e:
        console.print(f"\n[bold red]❌ Error: {e}[/bold red]")

if __name__ == "__main__":
    asyncio.run(test_steel())
