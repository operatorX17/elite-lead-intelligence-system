"""
Test pipeline with real-time dashboard visualization.
Run this to see EVERYTHING happening in real-time.
"""
import sys
sys.path.append('src')

import subprocess
import time
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from src.agents.discovery import DiscoveryAgent

console = Console()


def run_pipeline_test():
    """Run pipeline test on 5 hospitals."""
    console.print("\n[bold cyan]╔═══════════════════════════════════════════════════════════════╗[/bold cyan]")
    console.print("[bold cyan]║[/bold cyan]  [bold white]ZRAI LEAD OS - FULL PIPELINE TEST[/bold white]                          [bold cyan]║[/bold cyan]")
    console.print("[bold cyan]╚═══════════════════════════════════════════════════════════════╝[/bold cyan]\n")
    
    console.print("[yellow]Testing on 5 Hyderabad hospitals from ELITE_INTELLIGENCE_Hyderabad_5_hospitals.json[/yellow]\n")
    
    # Hospital names
    hospitals = [
        "HK Hospital Hyderabad",
        "Royal Multi Speciality Hospital Hyderabad",
        "Sri Chandra Hospital Hyderabad",
        "St Theresa's Hospital Hyderabad",
        "Premier Hospital Hyderabad"
    ]
    
    agent = DiscoveryAgent()
    
    for i, hospital in enumerate(hospitals, 1):
        console.print(f"\n[bold cyan]═══ Processing {i}/5: {hospital} ═══[/bold cyan]")
        
        try:
            leads = agent.discover_from_google_maps(
                keywords=[hospital],
                geo={'city': 'Hyderabad', 'state': 'Telangana', 'country': 'India'},
                limit=1,
                auto_process=True,  # Run full pipeline
                skip_duplicate_check=True
            )
            
            if leads:
                lead = leads[0]
                console.print(f"[green]✓[/green] {lead.business_name}")
                console.print(f"  Reviews: {lead.reviews_count or 0:,}")
                console.print(f"  Rating: {lead.rating or 0.0:.1f}")
            else:
                console.print(f"[red]✗[/red] No lead found")
        
        except Exception as e:
            console.print(f"[red]✗ Error: {e}[/red]")
    
    console.print("\n[bold green]═══ PIPELINE TEST COMPLETE ═══[/bold green]\n")
    console.print("[yellow]Starting dashboard in 3 seconds...[/yellow]")
    time.sleep(3)


if __name__ == "__main__":
    # Run pipeline test
    run_pipeline_test()
    
    # Launch dashboard
    console.clear()
    subprocess.run([sys.executable, "dashboard.py"])
