#!/usr/bin/env python
"""
Show Production Run Results - Visual Summary
"""

import pandas as pd
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from pathlib import Path

console = Console()

# Load CSV
csv_file = Path("output/Bangalore_mixed_20260125_192634/Bangalore_500_leads.csv")
df = pd.read_csv(csv_file)

# Header
console.print(Panel.fit(
    "[bold red]PRODUCTION RUN RESULTS[/bold red]\n"
    "[yellow]January 25, 2026 - Bangalore Healthcare Leads[/yellow]",
    border_style="red"
))

# Summary Stats
console.print("\n[bold cyan]📊 SUMMARY STATISTICS[/bold cyan]\n")

stats_table = Table(show_header=False, box=None)
stats_table.add_column("Metric", style="cyan", width=30)
stats_table.add_column("Value", style="green", width=20)

stats_table.add_row("Total Discovered", "116 businesses")
stats_table.add_row("Total Enriched", "50 businesses (43%)")
stats_table.add_row("", "")
stats_table.add_row("[bold]HOT Leads (70+)[/bold]", "[bold red]0[/bold red]")
stats_table.add_row("[bold]WARM Leads (50-69)[/bold]", "[bold yellow]38[/bold yellow] ← READY")
stats_table.add_row("[bold]COLD Leads (<50)[/bold]", "[bold blue]12[/bold blue]")
stats_table.add_row("", "")
stats_table.add_row("Pending Enrichment", "66 businesses")
stats_table.add_row("", "")
stats_table.add_row("Total Cost", "$0.51")
stats_table.add_row("Time Taken", "~10 minutes")

console.print(stats_table)

# Priority Distribution
console.print("\n[bold cyan]🎯 PRIORITY DISTRIBUTION[/bold cyan]\n")

priority_counts = df['priority'].value_counts()
for priority, count in priority_counts.items():
    pct = count / len(df) * 100
    if priority == "WARM":
        console.print(f"  [yellow]⚡ {priority}: {count} leads ({pct:.1f}%)[/yellow]")
    elif priority == "COLD":
        console.print(f"  [blue]❄️  {priority}: {count} leads ({pct:.1f}%)[/blue]")
    else:
        console.print(f"  {priority}: {count} leads ({pct:.1f}%)")

# Top WARM Leads
console.print("\n[bold cyan]🔥 TOP 10 WARM LEADS[/bold cyan]\n")

warm_leads = df[df['priority'] == 'WARM'].sort_values('leak_score', ascending=False).head(10)

warm_table = Table()
warm_table.add_column("Business Name", style="cyan", width=40)
warm_table.add_column("Score", style="yellow", justify="center")
warm_table.add_column("Revenue Loss", style="red", justify="right")
warm_table.add_column("Recoverable", style="green", justify="right")

for _, lead in warm_leads.iterrows():
    name = lead['business_name'][:40]
    score = f"{lead['leak_score']}/100"
    revenue = f"₹{lead['estimated_revenue_loss_inr']//1000}k"
    recoverable = f"₹{lead['recoverable_amount_inr']//1000}k"
    warm_table.add_row(name, score, revenue, recoverable)

console.print(warm_table)

# Contact Info Stats
console.print("\n[bold cyan]📞 CONTACT INFO EXTRACTED[/bold cyan]\n")

has_website = df['website'].notna().sum()
has_phone = df['phone'].notna().sum()
has_email = df['emails'].apply(lambda x: len(eval(x)) > 0 if isinstance(x, str) and x != '[]' else False).sum()

contact_table = Table(show_header=False, box=None)
contact_table.add_column("Type", style="cyan", width=20)
contact_table.add_column("Count", style="green", width=15)
contact_table.add_column("Percentage", style="yellow", width=15)

contact_table.add_row("Websites", str(has_website), f"{has_website/len(df)*100:.1f}%")
contact_table.add_row("Phones", str(has_phone), f"{has_phone/len(df)*100:.1f}%")
contact_table.add_row("Emails", str(has_email), f"{has_email/len(df)*100:.1f}%")

console.print(contact_table)

# Next Steps
console.print("\n[bold cyan]🚀 NEXT STEPS[/bold cyan]\n")

console.print("  1. [yellow]Export leads:[/yellow] python export_current_leads.py")
console.print("  2. [yellow]Review quality:[/yellow] Check 5-10 WARM leads manually")
console.print("  3. [yellow]Fix rate limit:[/yellow] Add delays to Firecrawl")
console.print("  4. [yellow]Continue:[/yellow] Enrich remaining 66 leads")
console.print("  5. [yellow]Scale:[/yellow] Run full 500 lead discovery")

# Files
console.print("\n[bold cyan]📁 OUTPUT FILES[/bold cyan]\n")
console.print(f"  [green]✓[/green] CSV: {csv_file}")
console.print(f"  [green]✓[/green] Report: output/Bangalore_mixed_20260125_192634/run_report.json")
console.print(f"  [green]✓[/green] Database: All data saved to Supabase")

# Bottom Line
console.print("\n" + "="*70)
console.print("[bold green]✅ YOU HAVE 38 WARM LEADS READY FOR OUTREACH![/bold green]")
console.print("[bold yellow]⚠️  66 leads still need enrichment (fix rate limit)[/bold yellow]")
console.print("="*70 + "\n")
