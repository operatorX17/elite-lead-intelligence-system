#!/usr/bin/env python
"""
Check Current Leads in Database
Quick script to see what we have so far
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import os
from dotenv import load_dotenv
load_dotenv()

from src.db.client import get_supabase_client
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
import json

console = Console()


def check_leads():
    """Check current leads in database"""
    
    console.print(Panel.fit(
        "[bold cyan]Current Leads in Database[/bold cyan]\n"
        "[yellow]Checking what we have so far...[/yellow]",
        border_style="cyan"
    ))
    
    db = get_supabase_client()
    
    # Get all leads
    response = db._client.table("leads").select("*").execute()
    leads = response.data
    
    console.print(f"\n[green]✓ Found {len(leads)} leads in database[/green]\n")
    
    if not leads:
        console.print("[yellow]No leads found yet. The system is still discovering.[/yellow]")
        return
    
    # Count by priority
    hot = sum(1 for l in leads if l.get("priority") == "HOT")
    warm = sum(1 for l in leads if l.get("priority") == "WARM")
    cold = sum(1 for l in leads if l.get("priority") == "COLD")
    unknown = sum(1 for l in leads if not l.get("priority"))
    
    # Summary table
    table = Table(title="Lead Summary")
    table.add_column("Priority", style="cyan")
    table.add_column("Count", style="green")
    table.add_column("Percentage", style="yellow")
    
    total = len(leads)
    table.add_row("HOT (70+)", str(hot), f"{hot/total*100:.1f}%")
    table.add_row("WARM (50-69)", str(warm), f"{warm/total*100:.1f}%")
    table.add_row("COLD (<50)", str(cold), f"{cold/total*100:.1f}%")
    table.add_row("Unknown", str(unknown), f"{unknown/total*100:.1f}%")
    table.add_row("[bold]TOTAL[/bold]", f"[bold]{total}[/bold]", "[bold]100%[/bold]")
    
    console.print(table)
    
    # Show HOT leads
    if hot > 0:
        console.print(f"\n[bold green]🔥 HOT LEADS ({hot})[/bold green]")
        hot_table = Table()
        hot_table.add_column("Business Name", style="cyan", width=40)
        hot_table.add_column("Website", style="blue", width=30)
        hot_table.add_column("Score", style="green")
        hot_table.add_column("Revenue Loss", style="red")
        
        hot_leads = [l for l in leads if l.get("priority") == "HOT"]
        for lead in hot_leads[:10]:  # Show first 10
            name = lead.get("business_name", "Unknown")[:40]
            website = lead.get("website", "N/A")[:30]
            score = lead.get("leak_score", "?")
            revenue = lead.get("estimated_revenue_loss_inr", 0)
            hot_table.add_row(name, website, str(score), f"₹{revenue//1000}k")
        
        console.print(hot_table)
        
        if hot > 10:
            console.print(f"[yellow]... and {hot-10} more HOT leads[/yellow]")
    
    # Show WARM leads
    if warm > 0:
        console.print(f"\n[bold yellow]⚡ WARM LEADS ({warm})[/bold yellow]")
        warm_table = Table()
        warm_table.add_column("Business Name", style="cyan", width=40)
        warm_table.add_column("Website", style="blue", width=30)
        warm_table.add_column("Score", style="yellow")
        
        warm_leads = [l for l in leads if l.get("priority") == "WARM"]
        for lead in warm_leads[:5]:  # Show first 5
            name = lead.get("business_name", "Unknown")[:40]
            website = lead.get("website", "N/A")[:30]
            score = lead.get("leak_score", "?")
            warm_table.add_row(name, website, str(score))
        
        console.print(warm_table)
        
        if warm > 5:
            console.print(f"[yellow]... and {warm-5} more WARM leads[/yellow]")
    
    # Check enrichment status
    enriched = sum(1 for l in leads if l.get("website"))
    console.print(f"\n[cyan]Enrichment Progress: {enriched}/{total} leads have websites ({enriched/total*100:.1f}%)[/cyan]")
    
    # Check if still processing
    if unknown > 0:
        console.print(f"\n[yellow]⏳ Still processing {unknown} leads...[/yellow]")
        console.print("[yellow]You can stop anytime with Ctrl+C - all data is saved![/yellow]")
    
    # Export option
    console.print(f"\n[bold]Want to export current leads?[/bold]")
    console.print("[cyan]Run: python export_current_leads.py[/cyan]")


if __name__ == "__main__":
    check_leads()
