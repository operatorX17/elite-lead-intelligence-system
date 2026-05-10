"""
ZRAI Lead OS - Real-Time Terminal Dashboard
Dystopian futuristic interface showing all system operations in real-time.
"""
import sys
sys.path.append('src')

import time
import os
from datetime import datetime
from typing import Dict, Any, List
from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich.layout import Layout
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.text import Text
from rich.align import Align

from src.db.client import SupabaseClient
from src.agents.discovery import DiscoveryAgent


console = Console()


class ZRAIDashboard:
    """Real-time system dashboard."""
    
    def __init__(self):
        self.client = SupabaseClient()
        self.discovery = DiscoveryAgent()
        self.start_time = datetime.now()
    
    def get_system_stats(self) -> Dict[str, Any]:
        """Get real-time system statistics."""
        # Get all leads
        leads_result = self.client._client.table("leads").select("*").execute()
        leads = leads_result.data if leads_result.data else []
        
        # Get enrichment data
        enrichment_result = self.client._client.table("enrichment_data").select("*").execute()
        enrichments = enrichment_result.data if enrichment_result.data else []
        
        # Get intent data
        intent_result = self.client._client.table("intent_data").select("*").execute()
        intents = intent_result.data if intent_result.data else []
        
        # Get scoring data
        scoring_result = self.client._client.table("scoring_results").select("*").execute()
        scorings = scoring_result.data if scoring_result.data else []
        
        # Calculate stats
        total_leads = len(leads)
        enriched = len(enrichments)
        scored = len(scorings)
        
        # Tier breakdown
        tier_a = sum(1 for s in scorings if s.get('lead_tier') == 'A')
        tier_b = sum(1 for s in scorings if s.get('lead_tier') == 'B')
        tier_c = sum(1 for s in scorings if s.get('lead_tier') == 'C')
        
        # Volume stats
        with_reviews = sum(1 for l in leads if l.get('reviews_count') and l.get('reviews_count') > 0)
        avg_reviews = sum(l.get('reviews_count', 0) for l in leads) / total_leads if total_leads > 0 else 0
        
        # Volume score stats
        volume_scores = [i.get('volume_score', 0) for i in intents if i.get('volume_score') is not None]
        avg_volume_score = sum(volume_scores) / len(volume_scores) if volume_scores else 0
        
        return {
            'total_leads': total_leads,
            'enriched': enriched,
            'scored': scored,
            'tier_a': tier_a,
            'tier_b': tier_b,
            'tier_c': tier_c,
            'with_reviews': with_reviews,
            'avg_reviews': avg_reviews,
            'avg_volume_score': avg_volume_score,
            'pipeline_completion': (scored / total_leads * 100) if total_leads > 0 else 0,
        }
    
    def get_recent_leads(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get most recent leads with full pipeline data."""
        # Get leads with all related data
        leads_result = self.client._client.table("leads").select("*").order("created_at", desc=True).limit(limit).execute()
        leads = leads_result.data if leads_result.data else []
        
        enriched_leads = []
        for lead in leads:
            lead_id = lead['lead_id']
            
            # Get enrichment
            enrich = self.client.get_enrichment_data(lead_id)
            
            # Get intent
            intent = self.client.get_intent_data(lead_id)
            
            # Get scoring
            scoring = self.client.get_scoring_result(lead_id)
            
            enriched_leads.append({
                'lead': lead,
                'enrichment': enrich,
                'intent': intent,
                'scoring': scoring,
            })
        
        return enriched_leads
    
    def create_header(self) -> Panel:
        """Create dashboard header."""
        uptime = datetime.now() - self.start_time
        uptime_str = f"{int(uptime.total_seconds())}s"
        
        header_text = Text()
        header_text.append("╔═══════════════════════════════════════════════════════════════════════════════╗\n", style="bold cyan")
        header_text.append("║                    ", style="bold cyan")
        header_text.append("ZRAI LEAD OS - AUTONOMOUS INTELLIGENCE SYSTEM", style="bold white")
        header_text.append("                    ║\n", style="bold cyan")
        header_text.append("║                         ", style="bold cyan")
        header_text.append("REAL-TIME OPERATIONS DASHBOARD", style="bold green")
        header_text.append("                          ║\n", style="bold cyan")
        header_text.append("╚═══════════════════════════════════════════════════════════════════════════════╝", style="bold cyan")
        
        return Panel(
            Align.center(header_text),
            style="bold cyan",
            border_style="cyan"
        )
    
    def create_stats_panel(self, stats: Dict[str, Any]) -> Panel:
        """Create system statistics panel."""
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="bold white")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="bold white")
        
        # Row 1
        table.add_row(
            "📊 TOTAL LEADS", f"{stats['total_leads']:,}",
            "✅ ENRICHED", f"{stats['enriched']:,}"
        )
        
        # Row 2
        table.add_row(
            "🎯 SCORED", f"{stats['scored']:,}",
            "📈 PIPELINE", f"{stats['pipeline_completion']:.1f}%"
        )
        
        # Row 3
        table.add_row(
            "⭐ TIER A", f"{stats['tier_a']:,}",
            "🔵 TIER B", f"{stats['tier_b']:,}"
        )
        
        # Row 4
        table.add_row(
            "⚪ TIER C", f"{stats['tier_c']:,}",
            "📝 WITH REVIEWS", f"{stats['with_reviews']:,}"
        )
        
        # Row 5
        table.add_row(
            "💬 AVG REVIEWS", f"{stats['avg_reviews']:.1f}",
            "🔥 AVG VOLUME", f"{stats['avg_volume_score']:.1f}/100"
        )
        
        return Panel(
            table,
            title="[bold white]⚡ SYSTEM METRICS",
            border_style="green",
            padding=(1, 2)
        )
    
    def create_leads_table(self, leads: List[Dict[str, Any]]) -> Panel:
        """Create recent leads table."""
        table = Table(show_header=True, header_style="bold magenta", box=None)
        table.add_column("BUSINESS", style="cyan", width=25)
        table.add_column("REVIEWS", justify="right", style="yellow", width=8)
        table.add_column("RATING", justify="right", style="yellow", width=7)
        table.add_column("VOL", justify="right", style="green", width=6)
        table.add_column("INTENT", justify="right", style="blue", width=7)
        table.add_column("LEAK", justify="right", style="red", width=6)
        table.add_column("FINAL", justify="right", style="bold white", width=7)
        table.add_column("TIER", justify="center", style="bold", width=6)
        
        for item in leads:
            lead = item['lead']
            enrichment = item['enrichment']
            intent = item['intent']
            scoring = item['scoring']
            
            # Get values
            business = lead.get('business_name', 'Unknown')[:24]
            reviews = lead.get('reviews_count', 0) or 0
            rating = lead.get('rating', 0.0) or 0.0
            
            vol_score = intent.get('volume_score', 0) if intent else 0
            intent_score = intent.get('intent_score', 0) if intent else 0
            leak_score = intent.get('leak_score', 0) if intent else 0
            
            final_score = scoring.get('final_score', 0) if scoring else 0
            tier = scoring.get('lead_tier', '-') if scoring else '-'
            
            # Color tier
            tier_style = "bold green" if tier == 'A' else "bold blue" if tier == 'B' else "white"
            
            table.add_row(
                business,
                f"{reviews:,}",
                f"{rating:.1f}",
                f"{vol_score}",
                f"{intent_score}",
                f"{leak_score}",
                f"{final_score}",
                Text(tier, style=tier_style)
            )
        
        return Panel(
            table,
            title="[bold white]🎯 RECENT LEADS (LIVE PIPELINE DATA)",
            border_style="magenta",
            padding=(1, 2)
        )
    
    def create_pipeline_status(self, leads: List[Dict[str, Any]]) -> Panel:
        """Create pipeline status panel."""
        if not leads:
            return Panel(
                Text("No leads in pipeline", style="yellow"),
                title="[bold white]🔄 PIPELINE STATUS",
                border_style="yellow"
            )
        
        # Check latest lead pipeline status
        latest = leads[0]
        lead = latest['lead']
        enrichment = latest['enrichment']
        intent = latest['intent']
        scoring = latest['scoring']
        
        status_text = Text()
        status_text.append(f"Latest: {lead.get('business_name', 'Unknown')}\n\n", style="bold white")
        
        # Discovery
        status_text.append("1. DISCOVERY    ", style="cyan")
        status_text.append("✓ COMPLETE\n", style="bold green")
        status_text.append(f"   Reviews: {lead.get('reviews_count', 0):,} | Rating: {lead.get('rating', 0.0):.1f}\n\n", style="white")
        
        # Enrichment
        if enrichment:
            status_text.append("2. ENRICHMENT   ", style="cyan")
            status_text.append("✓ COMPLETE\n", style="bold green")
            status_text.append(f"   Peak Busy: {enrichment.get('peak_busyness', 0)} | Contact: {enrichment.get('contact_quality_score', 0)}/100\n\n", style="white")
        else:
            status_text.append("2. ENRICHMENT   ", style="cyan")
            status_text.append("⏳ PENDING\n\n", style="yellow")
        
        # Intent
        if intent:
            status_text.append("3. INTENT       ", style="cyan")
            status_text.append("✓ COMPLETE\n", style="bold green")
            status_text.append(f"   Volume: {intent.get('volume_score', 0)}/100 | Intent: {intent.get('intent_score', 0)}/100\n\n", style="white")
        else:
            status_text.append("3. INTENT       ", style="cyan")
            status_text.append("⏳ PENDING\n\n", style="yellow")
        
        # Scoring
        if scoring:
            status_text.append("4. SCORING      ", style="cyan")
            status_text.append("✓ COMPLETE\n", style="bold green")
            status_text.append(f"   Final: {scoring.get('final_score', 0)}/100 | Tier: {scoring.get('lead_tier', '-')}\n", style="white")
        else:
            status_text.append("4. SCORING      ", style="cyan")
            status_text.append("⏳ PENDING\n", style="yellow")
        
        return Panel(
            status_text,
            title="[bold white]🔄 PIPELINE STATUS",
            border_style="blue",
            padding=(1, 2)
        )
    
    def create_footer(self) -> Panel:
        """Create dashboard footer."""
        footer_text = Text()
        footer_text.append("Press ", style="white")
        footer_text.append("CTRL+C", style="bold red")
        footer_text.append(" to exit | Refreshing every 2 seconds | ", style="white")
        footer_text.append(f"Last update: {datetime.now().strftime('%H:%M:%S')}", style="cyan")
        
        return Panel(
            Align.center(footer_text),
            style="dim",
            border_style="dim"
        )
    
    def render(self) -> Layout:
        """Render complete dashboard."""
        # Get data
        stats = self.get_system_stats()
        leads = self.get_recent_leads(limit=10)
        
        # Create layout
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=5),
            Layout(name="stats", size=10),
            Layout(name="body"),
            Layout(name="footer", size=3)
        )
        
        # Split body into two columns
        layout["body"].split_row(
            Layout(name="leads", ratio=2),
            Layout(name="pipeline", ratio=1)
        )
        
        # Populate layout
        layout["header"].update(self.create_header())
        layout["stats"].update(self.create_stats_panel(stats))
        layout["leads"].update(self.create_leads_table(leads))
        layout["pipeline"].update(self.create_pipeline_status(leads))
        layout["footer"].update(self.create_footer())
        
        return layout
    
    def run(self):
        """Run dashboard in live mode."""
        console.clear()
        
        try:
            with Live(self.render(), refresh_per_second=0.5, console=console) as live:
                while True:
                    time.sleep(2)  # Refresh every 2 seconds
                    live.update(self.render())
        except KeyboardInterrupt:
            console.print("\n[bold red]Dashboard stopped.[/bold red]")


if __name__ == "__main__":
    console.print("[bold cyan]Starting ZRAI Lead OS Dashboard...[/bold cyan]\n")
    time.sleep(1)
    
    dashboard = ZRAIDashboard()
    dashboard.run()
