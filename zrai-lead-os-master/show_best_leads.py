#!/usr/bin/env python
"""
Show Best Leads - Top 10 WARM leads with full details
"""

import pandas as pd
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
import json

console = Console()

# Load CSV
df = pd.read_csv("output/Bangalore_mixed_20260125_192634/Bangalore_500_leads.csv")

# Get top 10 WARM leads
warm_leads = df[df['priority'] == 'WARM'].sort_values('leak_score', ascending=False).head(10)

console.print(Panel.fit(
    "[bold yellow]TOP 10 WARM LEADS[/bold yellow]\n"
    "[cyan]Ready for Outreach - Highest Scores[/cyan]",
    border_style="yellow"
))

for idx, (_, lead) in enumerate(warm_leads.iterrows(), 1):
    console.print(f"\n[bold cyan]═══ LEAD #{idx} ═══[/bold cyan]")
    
    # Basic Info
    console.print(f"[bold]{lead['business_name']}[/bold]")
    console.print(f"Category: {lead['category']}")
    console.print(f"Area: {lead['area']}")
    
    # Contact Info
    console.print(f"\n[yellow]Contact Info:[/yellow]")
    if pd.notna(lead['website']):
        console.print(f"  Website: {lead['website']}")
    if pd.notna(lead['phone']):
        console.print(f"  Phone: {lead['phone']}")
    
    # Parse emails
    try:
        emails = eval(lead['emails']) if isinstance(lead['emails'], str) else []
        if emails:
            console.print(f"  Emails: {', '.join(emails)}")
    except:
        pass
    
    # Signals
    console.print(f"\n[yellow]Automation Gaps:[/yellow]")
    console.print(f"  Booking System: {'❌ NO' if not lead['has_booking_system'] else '✅ YES'}")
    console.print(f"  WhatsApp: {'❌ NO' if not lead['has_whatsapp'] else '✅ YES'}")
    console.print(f"  Lead Form: {'❌ NO' if not lead['has_lead_form'] else '✅ YES'}")
    
    # Money
    console.print(f"\n[yellow]Revenue Opportunity:[/yellow]")
    console.print(f"  Score: [bold]{lead['leak_score']}/100[/bold]")
    console.print(f"  Monthly Leads: {lead['estimated_monthly_leads']}")
    console.print(f"  Missed %: {int(lead['estimated_missed_pct']*100)}%")
    console.print(f"  Revenue Loss: [red]₹{lead['estimated_revenue_loss_inr']//1000}k/month[/red]")
    console.print(f"  Recoverable: [green]₹{lead['recoverable_amount_inr']//1000}k/month[/green]")
    console.print(f"  Recommended Tier: {lead['recommended_tier']}")
    console.print(f"  ROI: {lead['roi_multiple']}x")
    
    # Outreach Preview
    if pd.notna(lead['email_subject']):
        console.print(f"\n[yellow]Email Subject:[/yellow]")
        console.print(f"  {lead['email_subject']}")
    
    if pd.notna(lead['whatsapp_msg']):
        console.print(f"\n[yellow]WhatsApp Message:[/yellow]")
        msg = lead['whatsapp_msg'][:150] + "..." if len(lead['whatsapp_msg']) > 150 else lead['whatsapp_msg']
        console.print(f"  {msg}")

console.print("\n" + "="*70)
console.print("[bold green]✅ These 10 leads are your BEST opportunities![/bold green]")
console.print("[yellow]Export full list: python export_current_leads.py[/yellow]")
console.print("="*70 + "\n")
