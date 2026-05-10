#!/usr/bin/env python
"""
Generate KILLER Intelligence Reports on Hospitals
1000 IQ analysis that would take 100 executives 10 years to compile
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import argparse
import logging
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown

from src.agents.deep_intelligence import DeepIntelligenceAgent
from src.db.client import get_supabase_client

logging.basicConfig(level=logging.INFO)
console = Console()


def display_intelligence_report(report: dict):
    """Display intelligence report in beautiful format"""
    
    console.print("\n")
    console.print(Panel.fit(
        f"[bold cyan]🎯 DEEP INTELLIGENCE REPORT[/bold cyan]\n"
        f"[yellow]{report['hospital_name']}[/yellow]\n"
        f"[dim]{report['location']}[/dim]\n"
        f"Intelligence Score: [bold green]{report['intelligence_score']}/100[/bold green]",
        border_style="cyan"
    ))
    
    # Pain Points
    console.print("\n[bold red]🔥 CRITICAL PAIN POINTS[/bold red]")
    pain_table = Table(show_header=True, header_style="bold magenta")
    pain_table.add_column("Pain", style="yellow")
    pain_table.add_column("Impact", style="red")
    pain_table.add_column("Revenue Loss", style="bold red")
    pain_table.add_column("Urgency", style="bold")
    
    for pain in report.get("pain_points", []):
        pain_table.add_row(
            pain.get("pain", ""),
            pain.get("impact", ""),
            pain.get("revenue_loss_monthly", ""),
            pain.get("urgency", "")
        )
    
    console.print(pain_table)
    
    # Revenue Opportunity
    console.print("\n[bold green]💰 REVENUE OPPORTUNITY[/bold green]")
    opp = report.get("revenue_opportunity", {})
    opp_table = Table(show_header=False, box=None)
    opp_table.add_column("Metric", style="cyan")
    opp_table.add_column("Value", style="bold green")
    
    opp_table.add_row("Current Monthly Loss", opp.get("current_monthly_loss", "unknown"))
    opp_table.add_row("Annual Loss", opp.get("annual_loss", "unknown"))
    opp_table.add_row("Recoverable with Solution", opp.get("recoverable_with_solution", "unknown"))
    opp_table.add_row("ROI Timeline", opp.get("roi_timeline", "unknown"))
    opp_table.add_row("5-Year Value", opp.get("5_year_value", "unknown"))
    
    console.print(opp_table)
    
    # Decision Makers
    console.print("\n[bold blue]👔 DECISION MAKERS[/bold blue]")
    dm_table = Table(show_header=True, header_style="bold blue")
    dm_table.add_column("Role", style="cyan")
    dm_table.add_column("Best Approach", style="yellow")
    dm_table.add_column("Key Priorities", style="green")
    
    for dm in report.get("decision_makers", []):
        dm_table.add_row(
            dm.get("role", ""),
            dm.get("best_approach", ""),
            ", ".join(dm.get("priorities", [])[:2])
        )
    
    console.print(dm_table)
    
    # Action Plan
    console.print("\n[bold magenta]🎬 IMMEDIATE ACTION PLAN[/bold magenta]")
    action_plan = report.get("action_plan", {})
    
    for action in action_plan.get("immediate_actions", []):
        console.print(
            f"\n[bold]Step {action['step']}:[/bold] {action['action']}\n"
            f"  [dim]Timing: {action['timing']}[/dim]\n"
            f"  [green]Success Probability: {action['success_probability']}[/green]"
        )
    
    # Closing Strategy
    console.print("\n[bold yellow]🎯 CLOSING STRATEGY[/bold yellow]")
    closing = action_plan.get("closing_strategy", {})
    console.print(f"[cyan]Primary Pitch:[/cyan] {closing.get('primary_pitch', '')}")
    console.print(f"[cyan]Closing Question:[/cyan] {closing.get('closing_question', '')}")
    console.print(f"[green]Expected Timeline:[/green] {action_plan.get('expected_timeline', '')}")
    console.print(f"[bold green]Success Probability:[/bold green] {action_plan.get('success_probability', '')}")
    
    console.print("\n")


def generate_report_for_lead(lead_id: str):
    """Generate intelligence report for a lead from database"""
    
    db = get_supabase_client()
    from uuid import UUID
    
    lead = db.get_lead(UUID(lead_id))
    if not lead:
        console.print(f"[red]Lead {lead_id} not found[/red]")
        return
    
    console.print(f"\n[cyan]Generating intelligence report for:[/cyan] {lead.get('business_name')}")
    
    agent = DeepIntelligenceAgent()
    report = agent.generate_hospital_intelligence_report(
        hospital_name=lead.get("business_name", "Unknown"),
        location=lead.get("location", "Unknown"),
        website=lead.get("website")
    )
    
    display_intelligence_report(report)
    
    # Save to file
    import json
    import os
    from datetime import datetime
    
    filename = f"intelligence_reports/{lead.get('business_name', 'unknown').replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    os.makedirs("intelligence_reports", exist_ok=True)
    
    with open(filename, 'w') as f:
        json.dump(report, f, indent=2)
    
    console.print(f"\n[green]✅ Report saved to:[/green] {filename}")


def generate_reports_for_top_leads(limit: int = 5):
    """Generate intelligence reports for top-tier leads"""
    
    db = get_supabase_client()
    
    # Get Tier A leads
    leads = db.get_leads_by_tier("A", limit=limit)
    
    if not leads:
        console.print("[yellow]No Tier A leads found. Trying Tier B...[/yellow]")
        leads = db.get_leads_by_tier("B", limit=limit)
    
    if not leads:
        console.print("[red]No leads found in database[/red]")
        return
    
    console.print(f"\n[bold cyan]Generating intelligence reports for {len(leads)} top leads...[/bold cyan]\n")
    
    for i, lead in enumerate(leads, 1):
        console.print(f"\n[bold]{'='*60}[/bold]")
        console.print(f"[bold cyan]Lead {i}/{len(leads)}[/bold cyan]")
        console.print(f"[bold]{'='*60}[/bold]")
        
        generate_report_for_lead(lead.get("lead_id"))
        
        if i < len(leads):
            input("\nPress ENTER to continue to next lead...")


def main():
    parser = argparse.ArgumentParser(description="Generate KILLER Intelligence Reports")
    parser.add_argument("--lead-id", type=str, help="Generate report for specific lead ID")
    parser.add_argument("--top-leads", type=int, default=5, help="Generate reports for top N leads")
    parser.add_argument("--hospital", type=str, help="Hospital name (for manual entry)")
    parser.add_argument("--location", type=str, help="Location (for manual entry)")
    parser.add_argument("--website", type=str, help="Website (for manual entry)")
    
    args = parser.parse_args()
    
    console.print(Panel.fit(
        "[bold cyan]🧠 DEEP INTELLIGENCE SYSTEM[/bold cyan]\n"
        "[yellow]1000 IQ Analysis Engine[/yellow]\n"
        "[dim]Generates intelligence that would take 100 executives 10 years to compile[/dim]",
        border_style="cyan"
    ))
    
    if args.lead_id:
        generate_report_for_lead(args.lead_id)
    elif args.hospital and args.location:
        agent = DeepIntelligenceAgent()
        report = agent.generate_hospital_intelligence_report(
            hospital_name=args.hospital,
            location=args.location,
            website=args.website
        )
        display_intelligence_report(report)
    else:
        generate_reports_for_top_leads(args.top_leads)


if __name__ == "__main__":
    main()
