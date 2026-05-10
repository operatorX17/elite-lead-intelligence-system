#!/usr/bin/env python
"""
FAST EXECUTION - Get to revenue FAST
No bullshit. Just results.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from rich.console import Console
from rich.panel import Panel
import logging

console = Console()
logging.basicConfig(level=logging.INFO)

def main():
    console.print(Panel.fit(
        "[bold red]🚀 FAST EXECUTION MODE[/bold red]\n"
        "[yellow]Goal: First paying customer in 2 weeks[/yellow]\n"
        "[dim]No demo data. Real leads. Real money.[/dim]",
        border_style="red"
    ))
    
    console.print("\n[bold cyan]EXECUTION PLAN:[/bold cyan]\n")
    console.print("1. Discover 100 Indian hospital leads (Apify)")
    console.print("2. Score and qualify them automatically")
    console.print("3. Generate outreach for top 20")
    console.print("4. YOU send first 10 emails manually")
    console.print("5. Close first deal in 2 weeks")
    console.print("\n[bold green]Expected First Month Revenue: ₹50k-1L[/bold green]")
    
    choice = console.input("\n[bold yellow]Ready to execute? (yes/no):[/bold yellow] ")
    
    if choice.lower() != 'yes':
        console.print("[red]Execution cancelled.[/red]")
        return
    
    # Step 1: Discover leads
    console.print("\n[bold]Step 1: Discovering hospital leads...[/bold]")
    console.print("[dim]This will use Apify credits to scrape Google Maps[/dim]")
    
    from src.agents.discovery import DiscoveryAgent
    discovery = DiscoveryAgent()
    
    cities = ["Hyderabad", "Bangalore", "Mumbai"]  # Start with 3 cities
    all_leads = []
    
    for city in cities:
        console.print(f"\n[cyan]Discovering hospitals in {city}...[/cyan]")
        try:
            leads = discovery.discover_from_google_maps(
                keywords=["hospital", "multi-specialty hospital"],
                geo={"city": city, "country": "India"},
                limit=30,
                auto_process=True  # Auto-score
            )
            console.print(f"[green]✓ Found {len(leads)} leads in {city}[/green]")
            all_leads.extend(leads)
        except Exception as e:
            console.print(f"[red]✗ Error in {city}: {e}[/red]")
    
    console.print(f"\n[bold green]Total leads discovered: {len(all_leads)}[/bold green]")
    
    # Step 2: Get top leads
    console.print("\n[bold]Step 2: Getting top-tier leads...[/bold]")
    
    from src.db.client import get_supabase_client
    db = get_supabase_client()
    
    tier_a = db.get_leads_by_tier("A", limit=20)
    tier_b = db.get_leads_by_tier("B", limit=20)
    
    top_leads = tier_a + tier_b[:10]  # Top 30 leads
    
    console.print(f"[green]✓ {len(tier_a)} Tier A leads (hot)[/green]")
    console.print(f"[yellow]✓ {len(tier_b)} Tier B leads (warm)[/green]")
    
    # Step 3: Generate outreach
    console.print("\n[bold]Step 3: Generating outreach messages...[/bold]")
    
    outreach_list = []
    for lead in top_leads[:20]:  # Top 20
        business = lead.get("business_name", "Unknown")
        location = lead.get("location", "Unknown")
        website = lead.get("website", "")
        phone = lead.get("phone", "")
        
        # Simple outreach template
        message = f"""
Subject: Recovering ₹8-15 lakhs/month in rejected insurance claims - {business}

Hi Team,

I noticed {business} in {location} processes insurance claims.

Based on industry data, you're likely losing ₹8-15 lakhs/month due to:
• 30-40% claim rejection rate
• Manual processing delays
• Data entry errors

We've built an AI system that:
✅ Validates claims BEFORE submission (90% acceptance rate)
✅ Auto-fills forms in seconds (zero errors)
✅ Recovers rejected claims automatically

**Free Audit Offer:**
Let me analyze your last 100 claims and show you exactly how much you're losing.

Takes 2 days. No cost. No commitment.

Interested? Reply to this email or call me at [YOUR PHONE].

Best regards,
[YOUR NAME]
[YOUR COMPANY]
"""
        
        outreach_list.append({
            "business": business,
            "location": location,
            "website": website,
            "phone": phone,
            "message": message
        })
    
    # Save to file
    import json
    with open("outreach_ready.json", "w") as f:
        json.dump(outreach_list, f, indent=2)
    
    console.print(f"[green]✓ Generated {len(outreach_list)} outreach messages[/green]")
    console.print("[yellow]Saved to: outreach_ready.json[/yellow]")
    
    # Step 4: Display first 3 for manual sending
    console.print("\n[bold]Step 4: SEND THESE EMAILS NOW:[/bold]\n")
    
    for i, outreach in enumerate(outreach_list[:3], 1):
        console.print(f"\n[bold cyan]Lead {i}: {outreach['business']}[/bold cyan]")
        console.print(f"[dim]Location: {outreach['location']}[/dim]")
        console.print(f"[dim]Website: {outreach['website']}[/dim]")
        console.print(f"[dim]Phone: {outreach['phone']}[/dim]")
        console.print("\n[yellow]Message:[/yellow]")
        console.print(outreach['message'])
        console.print("\n" + "="*60)
    
    console.print(f"\n[bold green]✓ EXECUTION COMPLETE[/bold green]")
    console.print("\n[bold yellow]NEXT STEPS:[/bold yellow]")
    console.print("1. Copy the messages above")
    console.print("2. Send via Gmail to the hospitals")
    console.print("3. Track responses in a spreadsheet")
    console.print("4. Follow up in 3 days if no response")
    console.print("5. Book demos with interested leads")
    console.print("\n[bold green]Target: First paying customer in 2 weeks[/bold green]")
    console.print("[bold green]Expected Revenue: ₹15-35k/month per customer[/bold green]")

if __name__ == "__main__":
    main()
