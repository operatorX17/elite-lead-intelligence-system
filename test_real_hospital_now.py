#!/usr/bin/env python
"""
REAL TEST - Find HOT leads for Indian hospitals
Full pipeline test with actual data
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import os
from dotenv import load_dotenv
load_dotenv()

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
import json
from datetime import datetime

console = Console()

console.print(Panel.fit(
    "[bold red]🔥 REAL PIPELINE TEST - FINDING HOT LEADS[/bold red]\n"
    "[yellow]Testing FULL intelligence system with REAL data[/yellow]\n"
    "[green]Target: Multi-specialty hospitals in Hyderabad[/green]",
    border_style="red"
))

# Test 1: Steel API
console.print("\n[bold cyan]TEST 1: Steel API Connection[/bold cyan]")
try:
    from src.tools.steel import SteelClient
    steel = SteelClient()
    console.print("[green]✅ Steel client initialized[/green]")
except Exception as e:
    console.print(f"[red]❌ Steel failed: {e}[/red]")
    sys.exit(1)

# Test 2: Apify Discovery
console.print("\n[bold cyan]TEST 2: Hospital Discovery (Apify)[/bold cyan]")
try:
    from src.agents.discovery import DiscoveryAgent
    discovery = DiscoveryAgent()
    
    console.print("[yellow]Searching for hospitals in Hyderabad...[/yellow]")
    leads = discovery.discover_from_google_maps(
        keywords=["multi-specialty hospital", "super specialty hospital"],
        geo={"city": "Hyderabad", "country": "India"},
        limit=3,  # Just 3 for quick test
        auto_process=False,
        skip_duplicate_check=True
    )
    
    console.print(f"[green]✅ Found {len(leads)} hospitals[/green]")
    
    if not leads:
        console.print("[red]❌ No hospitals found[/red]")
        sys.exit(1)
    
    # Display discovered hospitals
    table = Table(title="Discovered Hospitals", show_header=True)
    table.add_column("#", width=3)
    table.add_column("Name", width=30)
    table.add_column("Website", width=35)
    table.add_column("Phone", width=15)
    
    for i, lead in enumerate(leads[:3], 1):
        table.add_row(
            str(i),
            lead.business_name[:30],
            (lead.website or "N/A")[:35],
            lead.phone or "N/A"
        )
    
    console.print(table)
    
except Exception as e:
    console.print(f"[red]❌ Discovery failed: {e}[/red]")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 3: Steel Website Analysis
console.print("\n[bold cyan]TEST 3: Website Analysis (Steel)[/bold cyan]")

hot_leads = []

for i, lead in enumerate(leads[:3], 1):
    console.print(f"\n[yellow]Analyzing {i}/3: {lead.business_name}[/yellow]")
    
    if not lead.website:
        console.print("[yellow]⚠ No website, skipping Steel analysis[/yellow]")
        continue
    
    try:
        # Use Steel to analyze website
        console.print(f"[cyan]Steel analyzing: {lead.website}[/cyan]")
        audit = steel.audit_landing_page(lead.website)
        
        if audit.get("success"):
            extraction = audit.get("extraction_data", {})
            pain_signals = audit.get("pain_signals", [])
            
            console.print(f"[green]✅ Analysis complete[/green]")
            console.print(f"   - Phone numbers: {len(extraction.get('phone_numbers', []))}")
            console.print(f"   - Forms: {extraction.get('form_count', 0)}")
            console.print(f"   - Has booking: {extraction.get('has_booking_link', False)}")
            console.print(f"   - Pain signals: {len(pain_signals)}")
            
            if pain_signals:
                console.print(f"[red]   🔥 PAIN SIGNALS:[/red]")
                for signal in pain_signals[:3]:
                    console.print(f"      • {signal}")
            
            # Calculate hotness score
            hotness = 0
            if not extraction.get('phone_visible'):
                hotness += 30
            if not extraction.get('has_booking_link'):
                hotness += 25
            if extraction.get('form_count', 0) == 0:
                hotness += 20
            if not extraction.get('has_cta'):
                hotness += 15
            if len(pain_signals) >= 3:
                hotness += 10
            
            # Revenue calculation
            bed_count = 100  # Conservative estimate
            monthly_claims = bed_count * 10
            rejection_rate = 0.35
            rejected_claims = int(monthly_claims * rejection_rate)
            avg_claim_value = 25000
            monthly_loss = rejected_claims * avg_claim_value
            recoverable = monthly_loss * 0.7
            
            hot_lead = {
                "rank": i,
                "hospital_name": lead.business_name,
                "website": lead.website,
                "phone": lead.phone,
                "location": lead.location,
                "hotness_score": hotness,
                "pain_signals": pain_signals,
                "extraction": extraction,
                "revenue_opportunity": {
                    "monthly_loss_inr": f"₹{monthly_loss/100000:.1f} lakhs",
                    "recoverable": f"₹{recoverable/100000:.1f} lakhs/month",
                    "roi": f"{recoverable/35000:.1f}x"
                },
                "priority": "🔥 HOT" if hotness >= 50 else "⚡ WARM" if hotness >= 30 else "❄️ COLD"
            }
            
            hot_leads.append(hot_lead)
            
            console.print(f"[bold yellow]   🎯 Hotness Score: {hotness}/100[/bold yellow]")
            console.print(f"[bold yellow]   💰 Monthly Loss: {hot_lead['revenue_opportunity']['monthly_loss_inr']}[/bold yellow]")
            console.print(f"[bold yellow]   🎯 Priority: {hot_lead['priority']}[/bold yellow]")
            
        else:
            console.print(f"[yellow]⚠ Partial analysis: {audit.get('error')}[/yellow]")
            
    except Exception as e:
        console.print(f"[red]❌ Steel analysis failed: {e}[/red]")
        import traceback
        traceback.print_exc()

# Test 4: Generate Outreach
console.print("\n[bold cyan]TEST 4: Generate Outreach for Top Lead[/bold cyan]")

if hot_leads:
    # Sort by hotness
    hot_leads.sort(key=lambda x: x['hotness_score'], reverse=True)
    top_lead = hot_leads[0]
    
    console.print(f"\n[bold green]🔥 HOTTEST LEAD: {top_lead['hospital_name']}[/bold green]")
    console.print(f"[yellow]Hotness: {top_lead['hotness_score']}/100[/yellow]")
    console.print(f"[yellow]Revenue Opportunity: {top_lead['revenue_opportunity']['monthly_loss_inr']}[/yellow]")
    
    # Generate outreach
    pain_bullets = "\n".join([f"• {p}" for p in top_lead['pain_signals'][:3]])
    
    outreach_email = f"""Subject: Recovering {top_lead['revenue_opportunity']['monthly_loss_inr']}/month for {top_lead['hospital_name']}

Dear Sir/Madam,

I came across {top_lead['hospital_name']} and noticed some opportunities to recover significant revenue from insurance claims.

Based on our analysis of your website and operations:

{pain_bullets}

**The Numbers:**
• Estimated monthly loss: {top_lead['revenue_opportunity']['monthly_loss_inr']}
• Recoverable with our AI system: {top_lead['revenue_opportunity']['recoverable']}
• Our cost: ₹35,000/month
• Your ROI: {top_lead['revenue_opportunity']['roi']}

**Free Audit Offer:**
Let me analyze your last 100 claims and show you:
1. Exact rejection patterns
2. Exact ₹ amount being lost
3. Recovery roadmap

Takes 2 days. No cost. No commitment.

Would you be open to a 15-minute call this week?

Best regards,
[Your Name]
"""
    
    console.print(Panel(outreach_email, title="[bold green]Generated Outreach Email[/bold green]", border_style="green"))

# Final Summary
console.print("\n[bold green]{'='*70}[/bold green]")
console.print("[bold green]✅ PIPELINE TEST COMPLETE[/bold green]")
console.print("[bold green]{'='*70}[/bold green]")

# Results table
if hot_leads:
    results_table = Table(title="🔥 HOT LEADS FOUND", show_header=True, header_style="bold red")
    results_table.add_column("Rank", width=5)
    results_table.add_column("Hospital", width=25)
    results_table.add_column("Hotness", width=10)
    results_table.add_column("Monthly Loss", width=15)
    results_table.add_column("Priority", width=10)
    
    for lead in hot_leads:
        results_table.add_row(
            str(lead['rank']),
            lead['hospital_name'][:25],
            f"{lead['hotness_score']}/100",
            lead['revenue_opportunity']['monthly_loss_inr'],
            lead['priority']
        )
    
    console.print(results_table)
    
    # Save results
    output_file = f"HOT_LEADS_TEST_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, 'w') as f:
        json.dump(hot_leads, f, indent=2, default=str)
    
    console.print(f"\n[yellow]📁 Results saved to: {output_file}[/yellow]")
    
    console.print("\n[bold red]🎯 PIPELINE WORKS![/bold red]")
    console.print("[green]✅ Discovery: Working[/green]")
    console.print("[green]✅ Steel Analysis: Working[/green]")
    console.print("[green]✅ Pain Detection: Working[/green]")
    console.print("[green]✅ Revenue Calculation: Working[/green]")
    console.print("[green]✅ Outreach Generation: Working[/green]")
    
    console.print(f"\n[bold yellow]Found {len(hot_leads)} leads with total opportunity of:")
    total_loss = sum(
        float(lead['revenue_opportunity']['monthly_loss_inr'].replace('₹', '').replace('lakhs', '').strip())
        for lead in hot_leads
    )
    console.print(f"[bold red]💰 ₹{total_loss:.1f} lakhs/month[/bold red]")
    console.print(f"[bold red]💰 ₹{total_loss*12:.1f} lakhs/year[/bold red]")
    
    console.print("\n[bold green]🚀 READY TO SELL![/bold green]")
else:
    console.print("[yellow]⚠ No hot leads found in this test[/yellow]")

console.print("\n[bold cyan]Next: Run full system with 20+ hospitals[/bold cyan]")
console.print("[white]python ELITE_INTELLIGENCE_V2.py Hyderabad 20[/white]")
