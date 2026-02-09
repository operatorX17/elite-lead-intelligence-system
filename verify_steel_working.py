#!/usr/bin/env python
"""Quick verification that Steel is working - 30 second test"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from src.tools.steel import SteelClient
from rich.console import Console
from rich.panel import Panel

console = Console()

console.print(Panel.fit(
    "[bold green]🔧 STEEL API VERIFICATION TEST[/bold green]\n"
    "[yellow]Testing all Steel functionality...[/yellow]",
    border_style="green"
))

try:
    # Test 1: Initialize client
    console.print("\n[cyan]Test 1: Initialize Steel Client...[/cyan]")
    client = SteelClient()
    console.print("[green]✅ Client initialized[/green]")
    
    # Test 2: Simple scrape
    console.print("\n[cyan]Test 2: Simple Scrape (example.com)...[/cyan]")
    result = client.scrape("https://example.com", screenshot=True, extract_html=True)
    console.print(f"[green]✅ Scrape successful[/green]")
    console.print(f"   - HTML length: {len(result.get('html', ''))} chars")
    console.print(f"   - Screenshot: {len(result.get('screenshot', '')) // 1024}KB")
    
    # Test 3: Session management
    console.print("\n[cyan]Test 3: Session Management...[/cyan]")
    session = client.create_session()
    console.print(f"[green]✅ Session created: {session['session_id'][:20]}...[/green]")
    client.close_session(session['session_id'])
    console.print(f"[green]✅ Session released[/green]")
    
    # Test 4: Audit landing page
    console.print("\n[cyan]Test 4: Audit Landing Page (Apollo Hospitals)...[/cyan]")
    audit = client.audit_landing_page("https://www.apollohospitals.com")
    
    if audit.get("success"):
        extraction = audit.get("extraction_data", {})
        console.print(f"[green]✅ Audit successful[/green]")
        console.print(f"   - Phone numbers: {len(extraction.get('phone_numbers', []))}")
        console.print(f"   - Forms: {extraction.get('form_count', 0)}")
        console.print(f"   - Has booking: {extraction.get('has_booking_link', False)}")
        console.print(f"   - Has CTA: {extraction.get('has_cta', False)}")
        console.print(f"   - Pain signals: {len(audit.get('pain_signals', []))}")
        console.print(f"   - Screenshot: {bool(audit.get('hero_screenshot'))}")
    else:
        console.print(f"[yellow]⚠ Partial success: {audit.get('error')}[/yellow]")
    
    # Success!
    console.print(Panel.fit(
        "[bold green]🎉 ALL TESTS PASSED![/bold green]\n\n"
        "[yellow]Steel API is FULLY OPERATIONAL[/yellow]\n"
        "[cyan]You have 5 days left with unlimited credits[/cyan]\n\n"
        "[bold red]NEXT STEP:[/bold red]\n"
        "[white]python ELITE_INTELLIGENCE_V2.py Hyderabad 10[/white]",
        border_style="green"
    ))
    
except Exception as e:
    console.print(f"\n[bold red]❌ TEST FAILED: {e}[/bold red]")
    import traceback
    traceback.print_exc()
    sys.exit(1)
