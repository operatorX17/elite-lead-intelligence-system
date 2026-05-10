#!/usr/bin/env python
"""
Export Current Leads to CSV
Export whatever we have in the database right now
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import os
from dotenv import load_dotenv
load_dotenv()

from src.db.client import get_supabase_client
from rich.console import Console
import csv
from datetime import datetime

console = Console()


def export_leads():
    """Export current leads to CSV"""
    
    console.print("[cyan]Exporting current leads from database...[/cyan]")
    
    db = get_supabase_client()
    
    # Get all leads
    response = db._client.table("leads").select("*").execute()
    leads = response.data
    
    if not leads:
        console.print("[red]No leads found in database[/red]")
        return
    
    # Create output directory
    output_dir = Path("output/current_export")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Export ALL leads
    all_file = output_dir / f"all_leads_{timestamp}.csv"
    export_to_csv(leads, all_file, "All Leads")
    
    # Export HOT leads
    hot_leads = [l for l in leads if l.get("priority") == "HOT"]
    if hot_leads:
        hot_file = output_dir / f"hot_leads_{timestamp}.csv"
        export_to_csv(hot_leads, hot_file, "HOT Leads")
    
    # Export WARM leads
    warm_leads = [l for l in leads if l.get("priority") == "WARM"]
    if warm_leads:
        warm_file = output_dir / f"warm_leads_{timestamp}.csv"
        export_to_csv(warm_leads, warm_file, "WARM Leads")
    
    console.print(f"\n[bold green]✓ Export complete![/bold green]")
    console.print(f"[cyan]Files saved to: {output_dir}[/cyan]")


def export_to_csv(leads, filepath, label):
    """Export leads to CSV file"""
    
    if not leads:
        return
    
    # Define fieldnames
    fieldnames = [
        "business_name", "category", "city", "area", "google_maps_url",
        "website", "phone", "emails", "has_booking_system", "has_whatsapp",
        "has_lead_form", "rating", "reviews_count", "leak_score", "priority",
        "estimated_monthly_leads", "estimated_missed_pct",
        "estimated_revenue_loss_inr", "recoverable_amount_inr",
        "recommended_tier", "roi_multiple",
        "email_subject", "email_body", "whatsapp_msg"
    ]
    
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        
        for lead in leads:
            # Convert lists to strings
            if isinstance(lead.get("emails"), list):
                lead["emails"] = ", ".join(lead["emails"])
            
            writer.writerow(lead)
    
    console.print(f"[green]✓ Exported {len(leads)} {label} to {filepath.name}[/green]")


if __name__ == "__main__":
    export_leads()
