"""
ZRAI Lead OS - System Status Viewer
Shows complete system state in one beautiful view.
"""
import sys
sys.path.append('src')

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.columns import Columns

from src.db.client import SupabaseClient

console = Console()
client = SupabaseClient()


def show_system():
    """Show complete system status."""
    console.clear()
    
    # Header
    console.print("\n[bold cyan]╔═══════════════════════════════════════════════════════════════════════════════╗[/bold cyan]")
    console.print("[bold cyan]║[/bold cyan]                    [bold white]ZRAI LEAD OS - SYSTEM STATUS REPORT[/bold white]                    [bold cyan]║[/bold cyan]")
    console.print("[bold cyan]╚═══════════════════════════════════════════════════════════════════════════════╝[/bold cyan]\n")
    
    # Get data
    leads_result = client._client.table("leads").select("*").execute()
    leads = leads_result.data if leads_result.data else []
    
    enrichment_result = client._client.table("enrichment_data").select("*").execute()
    enrichments = enrichment_result.data if enrichment_result.data else []
    
    intent_result = client._client.table("intent_data").select("*").execute()
    intents = intent_result.data if intent_result.data else []
    
    scoring_result = client._client.table("scoring_results").select("*").execute()
    scorings = scoring_result.data if scoring_result.data else []
    
    # System metrics
    total_leads = len(leads)
    enriched = len(enrichments)
    scored = len(scorings)
    
    tier_a = sum(1 for s in scorings if s.get('lead_tier') == 'A')
    tier_b = sum(1 for s in scorings if s.get('lead_tier') == 'B')
    tier_c = sum(1 for s in scorings if s.get('lead_tier') == 'C')
    
    with_reviews = sum(1 for l in leads if l.get('reviews_count') and l.get('reviews_count') > 0)
    avg_reviews = sum(l.get('reviews_count') or 0 for l in leads) / total_leads if total_leads > 0 else 0
    
    volume_scores = [i.get('volume_score', 0) for i in intents if i.get('volume_score') is not None]
    avg_volume_score = sum(volume_scores) / len(volume_scores) if volume_scores else 0
    
    # Metrics table
    metrics_table = Table(show_header=False, box=None, padding=(0, 2))
    metrics_table.add_column("Metric", style="cyan", width=20)
    metrics_table.add_column("Value", style="bold white", width=15)
    metrics_table.add_column("Metric", style="cyan", width=20)
    metrics_table.add_column("Value", style="bold white", width=15)
    
    metrics_table.add_row("📊 TOTAL LEADS", f"{total_leads:,}", "✅ ENRICHED", f"{enriched:,}")
    metrics_table.add_row("🎯 SCORED", f"{scored:,}", "📈 COMPLETION", f"{(scored/total_leads*100) if total_leads > 0 else 0:.1f}%")
    metrics_table.add_row("⭐ TIER A", f"{tier_a:,}", "🔵 TIER B", f"{tier_b:,}")
    metrics_table.add_row("⚪ TIER C", f"{tier_c:,}", "📝 WITH REVIEWS", f"{with_reviews:,}")
    metrics_table.add_row("💬 AVG REVIEWS", f"{avg_reviews:.1f}", "🔥 AVG VOLUME", f"{avg_volume_score:.1f}/100")
    
    console.print(Panel(metrics_table, title="[bold white]⚡ SYSTEM METRICS", border_style="green", padding=(1, 2)))
    console.print()
    
    # Leads table
    leads_table = Table(show_header=True, header_style="bold magenta")
    leads_table.add_column("BUSINESS", style="cyan", width=30)
    leads_table.add_column("REVIEWS", justify="right", style="yellow", width=10)
    leads_table.add_column("RATING", justify="right", style="yellow", width=8)
    leads_table.add_column("VOL", justify="right", style="green", width=6)
    leads_table.add_column("INTENT", justify="right", style="blue", width=8)
    leads_table.add_column("LEAK", justify="right", style="red", width=6)
    leads_table.add_column("FINAL", justify="right", style="bold white", width=8)
    leads_table.add_column("TIER", justify="center", style="bold", width=6)
    
    # Get recent leads with all data
    recent_leads = client._client.table("leads").select("*").order("created_at", desc=True).limit(20).execute()
    
    for lead in (recent_leads.data if recent_leads.data else []):
        lead_id = lead['lead_id']
        
        # Get related data
        enrich = client.get_enrichment_data(lead_id)
        intent = client.get_intent_data(lead_id)
        scoring = client.get_scoring_result(lead_id)
        
        business = lead.get('business_name', 'Unknown')[:29]
        reviews = lead.get('reviews_count', 0) or 0
        rating = lead.get('rating', 0.0) or 0.0
        
        vol_score = intent.get('volume_score', 0) if intent else 0
        intent_score = intent.get('intent_score', 0) if intent else 0
        leak_score = intent.get('leak_score', 0) if intent else 0
        
        final_score = scoring.get('final_score', 0) if scoring else 0
        tier = scoring.get('lead_tier', '-') if scoring else '-'
        
        tier_style = "bold green" if tier == 'A' else "bold blue" if tier == 'B' else "white"
        
        leads_table.add_row(
            business,
            f"{reviews:,}",
            f"{rating:.1f}",
            f"{vol_score}",
            f"{intent_score}",
            f"{leak_score}",
            f"{final_score}",
            Text(tier, style=tier_style)
        )
    
    console.print(Panel(leads_table, title="[bold white]🎯 ALL LEADS (COMPLETE PIPELINE DATA)", border_style="magenta", padding=(1, 2)))
    console.print()
    
    # Volume signal breakdown
    if intents:
        console.print("[bold cyan]═══ VOLUME SIGNAL ANALYSIS ═══[/bold cyan]\n")
        
        high_volume = sum(1 for i in intents if i.get('volume_score', 0) >= 70)
        med_volume = sum(1 for i in intents if 40 <= i.get('volume_score', 0) < 70)
        low_volume = sum(1 for i in intents if i.get('volume_score', 0) < 40)
        
        console.print(f"  [green]High Volume (≥70):[/green] {high_volume} leads")
        console.print(f"  [yellow]Medium Volume (40-69):[/yellow] {med_volume} leads")
        console.print(f"  [red]Low Volume (<40):[/red] {low_volume} leads")
        console.print()
    
    # Pipeline health
    console.print("[bold cyan]═══ PIPELINE HEALTH ═══[/bold cyan]\n")
    
    discovery_rate = 100.0
    enrichment_rate = (enriched / total_leads * 100) if total_leads > 0 else 0
    intent_rate = (len(intents) / total_leads * 100) if total_leads > 0 else 0
    scoring_rate = (scored / total_leads * 100) if total_leads > 0 else 0
    
    console.print(f"  [green]1. Discovery:[/green]   {discovery_rate:.1f}% ({'✓' if discovery_rate == 100 else '✗'})")
    console.print(f"  [green]2. Enrichment:[/green] {enrichment_rate:.1f}% ({'✓' if enrichment_rate >= 90 else '⚠' if enrichment_rate >= 50 else '✗'})")
    console.print(f"  [green]3. Intent:[/green]     {intent_rate:.1f}% ({'✓' if intent_rate >= 90 else '⚠' if intent_rate >= 50 else '✗'})")
    console.print(f"  [green]4. Scoring:[/green]    {scoring_rate:.1f}% ({'✓' if scoring_rate >= 90 else '⚠' if scoring_rate >= 50 else '✗'})")
    console.print()
    
    console.print("[bold green]═══ SYSTEM OPERATIONAL ═══[/bold green]\n")


if __name__ == "__main__":
    show_system()
