#!/usr/bin/env python
"""
LEAD OS v1.0 - "Bangalore 500 Lead War Run"
The Money Machine - Autonomous Lead Intelligence Factory

Goal: Generate ₹5L/month in 30 days
Target: 500 leads/day → 50 hot → 10 conversations → 3 calls → 1-2 closes/week

Usage:
    python lead_os.py --city "Bangalore" --n 500 --niche "diagnostics"
    python lead_os.py --city "Bangalore" --n 500 --niche "dental"
    python lead_os.py --city "Bangalore" --n 500 --niche "mixed"

Output:
    - bangalore_500_leads.csv
    - top50_hot_leads.json
    - top50_proof_decks.pdf
    - /screenshots/lead_id/*.png
    - run_report.json
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import os
from dotenv import load_dotenv
load_dotenv()  # Load environment variables first

import asyncio
import aiohttp
from typing import Dict, Any, List, Optional
from datetime import datetime
import json
import csv
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.panel import Panel
from rich.table import Table
import logging
from dataclasses import dataclass, asdict
from enum import Enum

# Import existing tools
from src.db.client import get_supabase_client
from src.graph.orchestrator import LeadOrchestrator
from src.tools.llm import get_llm_client

console = Console()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration
STEEL_API_KEY = os.getenv("STEEL_API_KEY")
STEEL_API_URL = "https://api.steel.dev/v1"
APIFY_API_TOKEN = os.getenv("APIFY_API_TOKEN")

# Niche configurations
NICHE_CONFIGS = {
    "diagnostics": {
        "keywords": ["diagnostic centre", "pathology lab", "diagnostic center"],
        "category": "Diagnostics / Labs",
        "avg_leads_per_month": 300,
        "avg_appointment_value": 1500,
        "typical_missed_pct": 0.40
    },
    "dental": {
        "keywords": ["dental clinic", "dental hospital", "dentist"],
        "category": "Dental Clinics",
        "avg_leads_per_month": 200,
        "avg_appointment_value": 3000,
        "typical_missed_pct": 0.50
    },
    "skin": {
        "keywords": ["skin clinic", "dermatology", "hair clinic"],
        "category": "Skin / Hair Clinics",
        "avg_leads_per_month": 250,
        "avg_appointment_value": 2500,
        "typical_missed_pct": 0.45
    },
    "ivf": {
        "keywords": ["IVF clinic", "fertility centre", "fertility center"],
        "category": "IVF / Fertility",
        "avg_leads_per_month": 100,
        "avg_appointment_value": 150000,
        "typical_missed_pct": 0.30
    },
    "physio": {
        "keywords": ["physiotherapy", "physio clinic", "rehabilitation"],
        "category": "Ortho / Physio / Chiro",
        "avg_leads_per_month": 150,
        "avg_appointment_value": 2000,
        "typical_missed_pct": 0.50
    },
    "multispeciality": {
        "keywords": ["multi-speciality clinic", "polyclinic", "medical center"],
        "category": "Multi-speciality Clinics",
        "avg_leads_per_month": 400,
        "avg_appointment_value": 2000,
        "typical_missed_pct": 0.35
    },
    "mixed": {
        "keywords": [
            "diagnostic centre", "dental clinic", "skin clinic",
            "IVF clinic", "physiotherapy", "polyclinic"
        ],
        "category": "Mixed",
        "avg_leads_per_month": 250,
        "avg_appointment_value": 3000,
        "typical_missed_pct": 0.40
    }
}

# Offer tiers
class OfferTier(Enum):
    BASIC = "Basic ₹25K/month"
    PRO = "Pro ₹60K/month"
    ELITE = "Elite ₹1.2L/month"


@dataclass
class LeadData:
    """Core lead data"""
    business_name: str
    category: str
    city: str
    area: Optional[str]
    google_maps_url: Optional[str]
    website: Optional[str]
    phone: Optional[str]
    emails: List[str]
    
    # Signals
    has_booking_system: bool
    has_whatsapp: bool
    has_lead_form: bool
    has_slow_response_risk: bool
    has_after_hours_leak: bool
    rating: Optional[float]
    reviews_count: Optional[int]
    ads_detected: bool
    
    # Leak audit
    leak_score: int
    leak_categories: List[str]
    
    # Money estimate
    estimated_monthly_leads: int
    estimated_missed_pct: float
    estimated_revenue_loss_inr: int
    recoverable_amount_inr: int
    roi_multiple: float
    
    # Decision maker
    owner_name: Optional[str]
    linkedin_url: Optional[str]
    email_pattern: Optional[str]
    instagram_handle: Optional[str]
    whatsapp_number: Optional[str]
    
    # Outreach
    email_subject: str
    email_body: str
    whatsapp_msg: str
    call_script: str
    loom_script: str
    
    # Tier
    recommended_tier: str
    
    # Proof
    screenshots: List[str]
    proof_notes: List[str]


class LeadOSPipeline:
    """Main LEAD OS pipeline"""
    
    def __init__(self, city: str, niche: str, target_count: int):
        self.city = city
        self.niche = niche
        self.target_count = target_count
        self.niche_config = NICHE_CONFIGS.get(niche, NICHE_CONFIGS["mixed"])
        
        self.run_id = f"{city}_{niche}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.db = get_supabase_client()
        self.llm = get_llm_client()  # OpenRouter with Kimi model
        self.orchestrator = LeadOrchestrator(mode='production')  # LangGraph orchestrator
        
        self.discovered_leads = []
        self.enriched_leads = []
        self.hot_leads = []
        
        # Stats
        self.stats = {
            "started_at": datetime.utcnow().isoformat(),
            "city": city,
            "niche": niche,
            "target_count": target_count,
            "discovered": 0,
            "enriched": 0,
            "hot": 0,
            "warm": 0,
            "cold": 0,
            "errors": 0
        }
        
        logger.info(f"LEAD OS initialized with LangGraph + OpenRouter (Kimi model)")
    
    async def run(self):
        """Execute full pipeline"""
        
        console.print(Panel.fit(
            f"[bold red]LEAD OS v1.0 - Bangalore 500 Lead War Run[/bold red]\n\n"
            f"[yellow]City: {self.city}[/yellow]\n"
            f"[yellow]Niche: {self.niche}[/yellow]\n"
            f"[yellow]Target: {self.target_count} leads[/yellow]\n\n"
            f"[cyan]Pipeline: Discovery -> Enrichment -> Audit -> Money -> Outreach -> Export[/cyan]\n\n"
            f"[green]Goal: Rs 5L/month in 30 days[/green]",
            border_style="red"
        ))
        
        try:
            # Stage 1: Discovery
            console.print("\n[bold cyan]STAGE 1: DISCOVERY[/bold cyan]")
            await self.stage_discovery()
            
            # Stage 2: Enrichment
            console.print("\n[bold cyan]STAGE 2: ENRICHMENT[/bold cyan]")
            await self.stage_enrichment()
            
            # Stage 3: Leak Audit
            console.print("\n[bold cyan]STAGE 3: LEAK AUDIT[/bold cyan]")
            await self.stage_leak_audit()
            
            # Stage 4: Money Estimate
            console.print("\n[bold cyan]STAGE 4: MONEY ESTIMATE[/bold cyan]")
            await self.stage_money_estimate()
            
            # Stage 5: Prioritization
            console.print("\n[bold cyan]STAGE 5: PRIORITIZATION[/bold cyan]")
            await self.stage_prioritization()
            
            # Stage 6: Outreach Generation
            console.print("\n[bold cyan]STAGE 6: OUTREACH GENERATION[/bold cyan]")
            await self.stage_outreach_generation()
            
            # Stage 7: Export
            console.print("\n[bold cyan]STAGE 7: EXPORT[/bold cyan]")
            await self.stage_export()
            
            # Final stats
            self.stats["ended_at"] = datetime.utcnow().isoformat()
            self.print_final_stats()
            
        except Exception as e:
            logger.error(f"Pipeline error: {e}")
            self.stats["error"] = str(e)
            raise
    
    async def stage_discovery(self):
        """Stage 1: Discover leads from Google Maps"""
        
        # Use minimal Apify for bulk discovery
        from src.agents.discovery import DiscoveryAgent
        discovery = DiscoveryAgent()
        
        console.print(f"[yellow]Searching Google Maps for {self.niche} in {self.city}...[/yellow]")
        
        leads = discovery.discover_from_google_maps(
            keywords=self.niche_config["keywords"],
            geo={"city": self.city, "country": "India"},
            limit=self.target_count,
            auto_process=False,
            skip_duplicate_check=True  # Allow duplicates for testing
        )
        
        self.discovered_leads = leads
        self.stats["discovered"] = len(leads)
        
        console.print(f"[green]✓ Discovered {len(leads)} leads[/green]")
    
    async def stage_enrichment(self):
        """Stage 2: Enrich with Steel + Firecrawl"""
        
        console.print(f"[yellow]Enriching {len(self.discovered_leads)} leads with Steel...[/yellow]")
        
        # Process in batches to manage Steel sessions efficiently
        batch_size = 10  # Process 10 leads per batch
        total_leads = min(len(self.discovered_leads), 50)  # Start with 50 for testing
        
        for i in range(0, total_leads, batch_size):
            batch = self.discovered_leads[i:i+batch_size]
            console.print(f"[cyan]Processing batch {i//batch_size + 1} ({len(batch)} leads)...[/cyan]")
            
            # Process batch in parallel
            tasks = [self.enrich_lead(lead) for lead in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in results:
                if isinstance(result, Exception):
                    self.stats["errors"] += 1
                    logger.error(f"Enrichment error: {result}")
                else:
                    self.enriched_leads.append(result)
            
            # Small delay between batches to avoid rate limits
            if i + batch_size < total_leads:
                await asyncio.sleep(2)
        
        self.stats["enriched"] = len(self.enriched_leads)
        console.print(f"[green]✓ Enriched {len(self.enriched_leads)} leads[/green]")
    
    async def enrich_lead(self, lead) -> Dict:
        """Enrich single lead with Steel"""
        
        enriched = {
            "business_name": lead.business_name,
            "category": self.niche_config["category"],
            "city": self.city,
            "area": lead.location,
            "google_maps_url": f"https://www.google.com/maps/search/{lead.business_name.replace(' ', '+')}",
            "website": lead.website,
            "phone": lead.phone,
            "emails": [],
            "has_booking_system": False,
            "has_whatsapp": False,
            "has_lead_form": False,
            "has_slow_response_risk": True,  # Default assumption
            "has_after_hours_leak": True,  # Default assumption
            "rating": None,
            "reviews_count": None,
            "ads_detected": False,
            "screenshots": []
        }
        
        # Use Steel to analyze website
        if lead.website:
            steel_data = await self.steel_analyze_website(lead.website, lead.business_name)
            enriched.update(steel_data)
        
        return enriched
    
    async def steel_analyze_website(self, website: str, business_name: str) -> Dict:
        """Analyze website using Firecrawl (cloud scraping - WORKING)"""
        
        logger.info(f"[FIRECRAWL] Analyzing {website} for {business_name}")
        
        try:
            # Use Firecrawl for cloud-based scraping (working solution)
            from src.tools.firecrawl_enrichment import FirecrawlEnrichment
            
            firecrawl = FirecrawlEnrichment()
            signals = await firecrawl.analyze_website(website, business_name)
            
            logger.info(f"[FIRECRAWL] Signals: booking={signals.get('has_booking_system')}, whatsapp={signals.get('has_whatsapp')}, emails={len(signals.get('emails', []))}")
            
            return signals
            
        except Exception as e:
            logger.error(f"[FIRECRAWL] Error: {e}")
            return self._fallback_signals(website)
    
    def _fallback_signals(self, website: str) -> Dict:
        """Fallback when Steel CLI fails"""
        website_lower = website.lower()
        return {
            "status": "fallback",
            "has_booking_system": any(kw in website_lower for kw in ["practo", "calendly", "zocdoc", "booking"]),
            "has_whatsapp": "whatsapp" in website_lower or "wa.me" in website_lower,
            "has_lead_form": True,
            "has_click_to_call": True,
            "has_chat_widget": False,
            "emails": [],
            "phones": [],
            "booking_links": [],
            "social_links": {}
        }
    
    async def stage_leak_audit(self):
        """Stage 3: AI-Powered Reasoning & Validation"""
        
        console.print(f"[yellow]Activating AI Reasoning Agent (Supreme Validator)...[/yellow]")
        
        # Import reasoning agent
        from src.agents.reasoning import ReasoningAgent
        
        reasoning_agent = ReasoningAgent(self.llm)
        
        validated_leads = []
        rejected_count = 0
        
        for lead in self.enriched_leads:
            # Use AI reasoning to validate and score
            result = await reasoning_agent.validate_lead(lead)
            
            # Apply corrections from reasoning agent
            lead.update(result.corrections)
            
            # Log reasoning
            if result.final_verdict == "REJECT":
                logger.warning(f"[REASONING] REJECTED: {lead['business_name']}")
                logger.warning(f"[REASONING] Issues: {', '.join(result.issues_found)}")
                rejected_count += 1
            else:
                logger.info(f"[REASONING] {result.final_verdict}: {lead['business_name']} (score: {result.corrections['leak_score']})")
            
            # Print detailed reasoning for first 3 leads (for debugging)
            if len(validated_leads) < 3:
                console.print(reasoning_agent.explain_decision(result))
            
            validated_leads.append(lead)
        
        # Replace enriched leads with validated leads
        self.enriched_leads = validated_leads
        
        console.print(f"[green]✓ AI Reasoning complete: {rejected_count} rejected, {len(validated_leads) - rejected_count} validated[/green]")
    
    async def stage_money_estimate(self):
        """Stage 4: Estimate revenue loss"""
        
        for lead in self.enriched_leads:
            # Use niche benchmarks
            monthly_leads = self.niche_config["avg_leads_per_month"]
            avg_value = self.niche_config["avg_appointment_value"]
            missed_pct = self.niche_config["typical_missed_pct"]
            
            # Adjust based on reviews (proxy for volume)
            if lead.get("reviews_count"):
                if lead["reviews_count"] > 500:
                    monthly_leads = int(monthly_leads * 1.5)
                elif lead["reviews_count"] > 200:
                    monthly_leads = int(monthly_leads * 1.2)
                elif lead["reviews_count"] < 50:
                    monthly_leads = int(monthly_leads * 0.7)
            
            # Calculate
            missed_leads = int(monthly_leads * missed_pct)
            revenue_loss = missed_leads * avg_value
            recoverable = int(revenue_loss * 0.7)  # 70% recovery rate
            
            # Determine tier
            if recoverable >= 200000:  # ₹2L+
                tier = OfferTier.ELITE.value
                price = 120000
            elif recoverable >= 80000:  # ₹80k+
                tier = OfferTier.PRO.value
                price = 60000
            else:
                tier = OfferTier.BASIC.value
                price = 25000
            
            roi_multiple = recoverable / price if price > 0 else 0
            
            lead["estimated_monthly_leads"] = monthly_leads
            lead["estimated_missed_pct"] = missed_pct
            lead["estimated_revenue_loss_inr"] = revenue_loss
            lead["recoverable_amount_inr"] = recoverable
            lead["recommended_tier"] = tier
            lead["roi_multiple"] = round(roi_multiple, 1)
        
        console.print(f"[green]✓ Money estimates complete[/green]")
    
    async def stage_prioritization(self):
        """Stage 5: Prioritize leads"""
        
        for lead in self.enriched_leads:
            score = lead["leak_score"]
            
            # REALISTIC thresholds for Indian healthcare businesses
            # Most real businesses will score 50-70, not 80-100
            if score >= 55:  # LOWERED from 70 - Any business with website + some signals
                lead["priority"] = "HOT"
                self.hot_leads.append(lead)
                self.stats["hot"] += 1
            elif score >= 35:  # LOWERED from 50 - Has basic presence
                lead["priority"] = "WARM"
                self.stats["warm"] += 1
            else:
                lead["priority"] = "COLD"
                self.stats["cold"] += 1
        
        # Sort hot leads by recoverable amount
        self.hot_leads.sort(key=lambda x: x["recoverable_amount_inr"], reverse=True)
        
        console.print(f"[green]✓ Prioritization complete: {self.stats['hot']} HOT, {self.stats['warm']} WARM, {self.stats['cold']} COLD[/green]")
    
    async def stage_outreach_generation(self):
        """Stage 6: Generate outreach for HOT + WARM"""
        
        for lead in self.enriched_leads:
            if lead.get("priority") in ["HOT", "WARM"]:
                outreach = self.generate_outreach(lead)
                lead.update(outreach)
        
        console.print(f"[green]✓ Outreach generated for {self.stats['hot'] + self.stats['warm']} leads[/green]")
    
    def generate_outreach(self, lead: Dict) -> Dict:
        """Generate outreach messages"""
        
        business_name = lead["business_name"]
        revenue_loss = lead["estimated_revenue_loss_inr"]
        recoverable = lead["recoverable_amount_inr"]
        roi = lead["roi_multiple"]
        tier = lead["recommended_tier"]
        
        # Email subject
        email_subject = f"Recovering ₹{recoverable//1000}k/month for {business_name}"
        
        # Email body
        email_body = f"""Hi,

I came across {business_name} and noticed you're likely losing ₹{revenue_loss//1000}k/month in missed appointments and slow follow-ups.

Based on your Google reviews and category, here's what I found:
• {lead['estimated_monthly_leads']} leads/month
• ~{int(lead['estimated_missed_pct']*100)}% missed due to slow response
• ₹{revenue_loss//1000}k/month revenue loss

We can recover ₹{recoverable//1000}k/month with:
✅ WhatsApp assistant (instant response)
✅ Missed call capture
✅ Automated follow-ups

Cost: {tier}
ROI: {roi}x return

Want a free audit? Takes 2 days, shows exact ₹ being lost.

Reply "YES" and I'll send details.

Best,
[Your Name]
"""
        
        # WhatsApp message
        whatsapp_msg = f"""Hi! I noticed {business_name} might be losing ₹{recoverable//1000}k/month in missed appointments. 

We can recover this with WhatsApp automation + missed call capture.

Cost: {tier}
ROI: {roi}x

Want a free audit? Reply YES"""
        
        # Call script
        call_script = f"""Hi, this is [Name]. I'm calling about {business_name}.

I noticed you're getting good reviews but might be losing ₹{recoverable//1000}k/month in missed appointments due to slow response times.

We've helped similar {lead['category']} businesses recover this revenue with WhatsApp automation.

Do you have 2 minutes to discuss?"""
        
        # Loom script
        loom_script = f"""[60 seconds]

Hi! I'm [Name] and I found {business_name} on Google.

You have {lead.get('reviews_count', 'many')} reviews which is great, but I noticed you might be losing ₹{recoverable//1000}k/month.

Here's why:
- {lead['estimated_monthly_leads']} leads/month
- ~{int(lead['estimated_missed_pct']*100)}% missed due to slow response
- That's ₹{revenue_loss//1000}k/month gone

We can recover ₹{recoverable//1000}k/month with simple WhatsApp automation.

Cost: {tier}
ROI: {roi}x return

Want a free audit? Email me at [email]"""
        
        return {
            "email_subject": email_subject,
            "email_body": email_body,
            "whatsapp_msg": whatsapp_msg,
            "call_script": call_script,
            "loom_script": loom_script
        }
    
    async def stage_export(self):
        """Stage 7: Export results"""
        
        # Create output directory
        output_dir = Path(f"output/{self.run_id}")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Export CSV (all leads)
        csv_file = output_dir / f"{self.city}_{self.target_count}_leads.csv"
        self.export_csv(csv_file)
        
        # Export JSON (top 50 hot)
        json_file = output_dir / "top50_hot_leads.json"
        self.export_json(json_file)
        
        # Export run report
        report_file = output_dir / "run_report.json"
        with open(report_file, 'w') as f:
            json.dump(self.stats, f, indent=2)
        
        console.print(f"[green]✓ Exported to {output_dir}[/green]")
    
    def export_csv(self, filepath: Path):
        """Export all leads to CSV"""
        
        if not self.enriched_leads:
            return
        
        # Define all possible fieldnames
        fieldnames = [
            "business_name", "category", "city", "area", "google_maps_url",
            "website", "phone", "emails", "has_booking_system", "has_whatsapp",
            "has_lead_form", "has_click_to_call", "has_chat_widget",
            "has_slow_response_risk", "has_after_hours_leak", "rating",
            "reviews_count", "ads_detected", "screenshots", "phones",
            "booking_links", "social_links", "leak_score", "leak_categories",
            "estimated_monthly_leads", "estimated_missed_pct",
            "estimated_revenue_loss_inr", "recoverable_amount_inr",
            "recommended_tier", "roi_multiple", "priority",
            "email_subject", "email_body", "whatsapp_msg",
            "call_script", "loom_script"
        ]
        
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
            
            writer.writeheader()
            for lead in self.enriched_leads:
                writer.writerow(lead)
        
        console.print(f"[green]✓ CSV exported: {filepath}[/green]")
    
    def export_json(self, filepath: Path):
        """Export top 50 hot leads to JSON"""
        
        top_50 = self.hot_leads[:50]
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(top_50, f, indent=2, default=str)
        
        console.print(f"[green]✓ JSON exported: {filepath} ({len(top_50)} leads)[/green]")
    
    def print_final_stats(self):
        """Print final statistics"""
        
        table = Table(title="LEAD OS Run Statistics")
        
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")
        
        table.add_row("City", self.city)
        table.add_row("Niche", self.niche)
        table.add_row("Target", str(self.target_count))
        table.add_row("Discovered", str(self.stats["discovered"]))
        table.add_row("Enriched", str(self.stats["enriched"]))
        table.add_row("HOT", str(self.stats["hot"]))
        table.add_row("WARM", str(self.stats["warm"]))
        table.add_row("COLD", str(self.stats["cold"]))
        table.add_row("Errors", str(self.stats["errors"]))
        
        console.print(table)


async def main():
    """Main entry point"""
    
    import argparse
    
    parser = argparse.ArgumentParser(description="LEAD OS v1.0 - Bangalore 500 Lead War Run")
    parser.add_argument("--city", default="Bangalore", help="City to target")
    parser.add_argument("--n", type=int, default=500, help="Number of leads to generate")
    parser.add_argument("--niche", default="mixed", choices=list(NICHE_CONFIGS.keys()), help="Niche to target")
    
    args = parser.parse_args()
    
    # Run pipeline
    pipeline = LeadOSPipeline(args.city, args.niche, args.n)
    await pipeline.run()


if __name__ == "__main__":
    asyncio.run(main())
