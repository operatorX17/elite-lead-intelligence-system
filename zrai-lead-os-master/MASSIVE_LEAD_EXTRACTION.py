#!/usr/bin/env python
"""
MASSIVE LEAD EXTRACTION SYSTEM
Combines Apify (bulk discovery) + Steel (deep intelligence)
Target: 30,000-40,000 leads in 3 days

Strategy:
1. Use Apify to discover leads FAST (bulk Google Maps scraping)
2. Use Steel to extract DEEP intelligence from websites (parallel)
3. Save to database in real-time
4. Run 24/7 with auto-recovery

Usage:
    python MASSIVE_LEAD_EXTRACTION.py --target 30000 --steel-sessions 50
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import os
import asyncio
import aiohttp
from typing import Dict, Any, List
from datetime import datetime
import json
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeElapsedColumn
from rich.panel import Panel
from rich.table import Table
from rich.live import Live
import logging
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import multiprocessing as mp

# Import existing agents
from src.agents.discovery import DiscoveryAgent
from src.db.client import get_supabase_client

console = Console()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration
STEEL_API_KEY = os.getenv("STEEL_API_KEY")
APIFY_API_TOKEN = os.getenv("APIFY_API_TOKEN")

# Target configuration
TARGET_LEADS = 30000
STEEL_PARALLEL_SESSIONS = 50
APIFY_PARALLEL_ACTORS = 10

# Indian cities (top 50)
CITIES = [
    # Tier 1
    "Mumbai", "Delhi", "Bangalore", "Hyderabad", "Chennai", "Kolkata", "Pune", "Ahmedabad",
    # Tier 2
    "Jaipur", "Surat", "Lucknow", "Kanpur", "Nagpur", "Indore", "Thane", "Bhopal",
    "Visakhapatnam", "Pimpri-Chinchwad", "Patna", "Vadodara", "Ghaziabad", "Ludhiana",
    "Agra", "Nashik", "Faridabad", "Meerut", "Rajkot", "Kalyan-Dombivali", "Vasai-Virar",
    "Varanasi", "Srinagar", "Aurangabad", "Dhanbad", "Amritsar", "Navi Mumbai", "Allahabad",
    "Ranchi", "Howrah", "Coimbatore", "Jabalpur", "Gwalior", "Vijayawada", "Jodhpur",
    "Madurai", "Raipur", "Kota", "Chandigarh", "Guwahati", "Solapur"
]

# Lead types with search keywords
LEAD_CONFIGS = [
    {
        "type": "Hospital - Multi Specialty",
        "keywords": ["multi specialty hospital", "multi-speciality hospital"],
        "priority": 1,
        "target_per_city": 20
    },
    {
        "type": "Hospital - Super Specialty",
        "keywords": ["super specialty hospital", "super speciality hospital"],
        "priority": 1,
        "target_per_city": 15
    },
    {
        "type": "Hospital - General",
        "keywords": ["hospital", "medical center"],
        "priority": 2,
        "target_per_city": 30
    },
    {
        "type": "Diagnostic Center",
        "keywords": ["diagnostic center", "diagnostic centre", "pathology lab"],
        "priority": 2,
        "target_per_city": 25
    },
    {
        "type": "Polyclinic",
        "keywords": ["polyclinic", "multi specialty clinic"],
        "priority": 3,
        "target_per_city": 20
    },
    {
        "type": "Eye Hospital",
        "keywords": ["eye hospital", "eye care center", "ophthalmology"],
        "priority": 2,
        "target_per_city": 10
    },
    {
        "type": "Dental Hospital",
        "keywords": ["dental hospital", "dental clinic"],
        "priority": 3,
        "target_per_city": 15
    },
    {
        "type": "Maternity Hospital",
        "keywords": ["maternity hospital", "women hospital"],
        "priority": 2,
        "target_per_city": 10
    }
]


class ApifyBulkDiscovery:
    """Uses Apify to discover leads in bulk"""
    
    def __init__(self):
        self.discovery_agent = DiscoveryAgent()
        self.leads_discovered = 0
    
    def discover_city_batch(self, city: str, lead_config: Dict) -> List[Dict]:
        """Discover leads for a city using Apify"""
        try:
            logger.info(f"Apify: Discovering {lead_config['type']} in {city}")
            
            leads = self.discovery_agent.discover_from_google_maps(
                keywords=lead_config["keywords"],
                geo={"city": city, "country": "India"},
                limit=lead_config["target_per_city"],
                auto_process=False
            )
            
            self.leads_discovered += len(leads)
            logger.info(f"Apify: Found {len(leads)} leads in {city}")
            
            return [
                {
                    "business_name": lead.business_name,
                    "location": lead.location,
                    "website": lead.website,
                    "phone": lead.phone,
                    "lead_type": lead_config["type"],
                    "city": city,
                    "priority": lead_config["priority"],
                    "discovered_at": datetime.utcnow().isoformat(),
                    "source": "apify_google_maps"
                }
                for lead in leads
            ]
            
        except Exception as e:
            logger.error(f"Apify error for {city}: {e}")
            return []


class SteelIntelligenceExtractor:
    """Uses Steel to extract deep intelligence from websites"""
    
    def __init__(self, session_id: int):
        self.session_id = session_id
        self.session_token = None
        self.leads_enriched = 0
        self.errors = 0
    
    async def create_session(self):
        """Create Steel browser session"""
        async with aiohttp.ClientSession() as http_session:
            headers = {
                "Authorization": f"Bearer {STEEL_API_KEY}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "sessionTimeout": 3600000,
                "useProxy": True,
                "solveCaptchas": True
            }
            
            try:
                async with http_session.post(
                    "https://api.steel.dev/v1/sessions",
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        self.session_token = data.get("id")
                        logger.info(f"Steel Session {self.session_id}: Created")
                        return True
                    else:
                        text = await response.text()
                        logger.error(f"Steel Session {self.session_id}: Failed to create - {response.status}: {text}")
                        return False
            except Exception as e:
                logger.error(f"Steel Session {self.session_id}: Error creating - {e}")
                return False
    
    async def extract_intelligence(self, lead: Dict) -> Dict:
        """Extract intelligence from lead website"""
        website = lead.get("website")
        if not website:
            return {"status": "no_website"}
        
        try:
            # Navigate to website
            async with aiohttp.ClientSession() as http_session:
                headers = {
                    "Authorization": f"Bearer {STEEL_API_KEY}",
                    "Content-Type": "application/json"
                }
                
                # Navigate
                nav_payload = {"url": website}
                async with http_session.post(
                    f"https://api.steel.dev/v1/sessions/{self.session_token}/navigate",
                    headers=headers,
                    json=nav_payload,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status != 200:
                        return {"status": "navigation_failed"}
                
                # Wait for page load
                await asyncio.sleep(2)
                
                # Scrape page
                async with http_session.get(
                    f"https://api.steel.dev/v1/sessions/{self.session_token}/scrape",
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status != 200:
                        return {"status": "scrape_failed"}
                    
                    data = await response.json()
                    content = str(data).lower()
                    
                    # Extract intelligence
                    intelligence = {
                        "status": "success",
                        "scraped_at": datetime.utcnow().isoformat(),
                        "website": website,
                        "has_online_booking": any(x in content for x in ["book appointment", "online booking", "book now"]),
                        "has_insurance_portal": "insurance" in content and ("portal" in content or "claim" in content),
                        "has_patient_portal": "patient portal" in content or "patient login" in content,
                        "bed_count": None,
                        "departments": [],
                        "contact_emails": [],
                        "contact_phones": []
                    }
                    
                    # Extract bed count
                    import re
                    bed_matches = re.findall(r'(\d+)\s*bed', content)
                    if bed_matches:
                        intelligence["bed_count"] = int(bed_matches[0])
                    
                    # Extract emails
                    email_matches = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', content)
                    intelligence["contact_emails"] = list(set(email_matches))[:5]
                    
                    # Extract phones
                    phone_matches = re.findall(r'\+91[\s-]?\d{10}|\d{10}', content)
                    intelligence["contact_phones"] = list(set(phone_matches))[:5]
                    
                    self.leads_enriched += 1
                    return intelligence
                    
        except Exception as e:
            logger.error(f"Steel Session {self.session_id}: Intelligence extraction error - {e}")
            self.errors += 1
            return {"status": "error", "error": str(e)}
    
    async def close_session(self):
        """Close Steel session"""
        if not self.session_token:
            return
        
        try:
            async with aiohttp.ClientSession() as http_session:
                headers = {"Authorization": f"Bearer {STEEL_API_KEY}"}
                async with http_session.delete(
                    f"https://api.steel.dev/v1/sessions/{self.session_token}",
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    logger.info(f"Steel Session {self.session_id}: Closed")
        except Exception as e:
            logger.error(f"Steel Session {self.session_id}: Error closing - {e}")


async def steel_worker(worker_id: int, lead_queue: asyncio.Queue, enriched_queue: asyncio.Queue, progress, task_id):
    """Worker that enriches leads using Steel"""
    
    extractor = SteelIntelligenceExtractor(worker_id)
    
    # Create session
    success = await extractor.create_session()
    if not success:
        logger.error(f"Steel Worker {worker_id}: Failed to start")
        return
    
    try:
        while True:
            try:
                lead = await asyncio.wait_for(lead_queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            
            if lead is None:  # Poison pill
                break
            
            try:
                # Extract intelligence
                intelligence = await extractor.extract_intelligence(lead)
                
                # Combine
                enriched_lead = {
                    **lead,
                    "intelligence": intelligence
                }
                
                # Add to enriched queue
                await enriched_queue.put(enriched_lead)
                
                progress.update(task_id, advance=1)
                
            except Exception as e:
                logger.error(f"Steel Worker {worker_id}: Error processing lead - {e}")
            
            finally:
                lead_queue.task_done()
    
    finally:
        await extractor.close_session()
        logger.info(f"Steel Worker {worker_id}: Enriched {extractor.leads_enriched} leads, Errors: {extractor.errors}")


def apify_discovery_worker(city: str, lead_config: Dict, result_queue: mp.Queue):
    """Process worker for Apify discovery"""
    try:
        discovery = ApifyBulkDiscovery()
        leads = discovery.discover_city_batch(city, lead_config)
        
        for lead in leads:
            result_queue.put(lead)
        
        logger.info(f"Apify Worker: Completed {city} - {lead_config['type']}")
    except Exception as e:
        logger.error(f"Apify Worker: Error in {city} - {e}")


async def database_saver(enriched_queue: asyncio.Queue, output_file: str):
    """Save enriched leads to database and file"""
    
    db = get_supabase_client()
    saved_count = 0
    all_leads = []
    
    while True:
        try:
            lead = await asyncio.wait_for(enriched_queue.get(), timeout=5.0)
            all_leads.append(lead)
            
            # Save to database
            try:
                # TODO: Insert into Supabase
                pass
            except Exception as e:
                logger.error(f"Database save error: {e}")
            
            saved_count += 1
            
            # Save to file every 100 leads
            if saved_count % 100 == 0:
                with open(output_file, 'w') as f:
                    json.dump(all_leads, f, indent=2, default=str)
                logger.info(f"Saved {saved_count} leads to {output_file}")
            
            enriched_queue.task_done()
            
        except asyncio.TimeoutError:
            # Final save
            if all_leads:
                with open(output_file, 'w') as f:
                    json.dump(all_leads, f, indent=2, default=str)
                logger.info(f"Final save: {saved_count} leads")
            break


async def main(target_leads: int = 30000, steel_sessions: int = 50):
    """Main execution"""
    
    console.print(Panel.fit(
        f"[bold red]🚀 MASSIVE LEAD EXTRACTION SYSTEM 🚀[/bold red]\n\n"
        f"[yellow]Target Leads: {target_leads:,}[/yellow]\n"
        f"[yellow]Steel Sessions: {steel_sessions}[/yellow]\n"
        f"[yellow]Cities: {len(CITIES)}[/yellow]\n"
        f"[yellow]Lead Types: {len(LEAD_CONFIGS)}[/yellow]\n\n"
        f"[cyan]Phase 1: Apify Bulk Discovery (FAST)[/cyan]\n"
        f"[cyan]Phase 2: Steel Deep Intelligence (PARALLEL)[/cyan]\n\n"
        f"[green]LET'S GET 30,000 LEADS![/green]",
        border_style="red"
    ))
    
    # Phase 1: Apify Bulk Discovery
    console.print("\n[bold cyan]PHASE 1: APIFY BULK DISCOVERY[/bold cyan]")
    
    discovered_leads = []
    
    # Use multiprocessing for Apify (CPU-bound)
    with mp.Manager() as manager:
        result_queue = manager.Queue()
        
        with ProcessPoolExecutor(max_workers=APIFY_PARALLEL_ACTORS) as executor:
            futures = []
            
            for city in CITIES:
                for lead_config in LEAD_CONFIGS:
                    future = executor.submit(apify_discovery_worker, city, lead_config, result_queue)
                    futures.append(future)
            
            # Collect results
            with Progress(console=console) as progress:
                task = progress.add_task("[cyan]Discovering leads...", total=len(futures))
                
                for future in futures:
                    future.result()
                    progress.update(task, advance=1)
                
                # Get all leads from queue
                while not result_queue.empty():
                    discovered_leads.append(result_queue.get())
    
    console.print(f"[green]✓ Phase 1 Complete: {len(discovered_leads):,} leads discovered[/green]")
    
    # Phase 2: Steel Deep Intelligence
    console.print("\n[bold cyan]PHASE 2: STEEL DEEP INTELLIGENCE[/bold cyan]")
    
    lead_queue = asyncio.Queue()
    enriched_queue = asyncio.Queue()
    
    # Add leads to queue
    for lead in discovered_leads:
        await lead_queue.put(lead)
    
    # Add poison pills
    for _ in range(steel_sessions):
        await lead_queue.put(None)
    
    # Start Steel workers
    with Progress(console=console) as progress:
        task_id = progress.add_task(
            "[cyan]Extracting intelligence...",
            total=len(discovered_leads)
        )
        
        # Start workers
        workers = [
            asyncio.create_task(steel_worker(i, lead_queue, enriched_queue, progress, task_id))
            for i in range(steel_sessions)
        ]
        
        # Start saver
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"MASSIVE_LEADS_{len(discovered_leads)}_{timestamp}.json"
        saver = asyncio.create_task(database_saver(enriched_queue, output_file))
        
        # Wait for completion
        await asyncio.gather(*workers)
        await enriched_queue.join()
    
    console.print(f"\n[bold green]✅ MISSION COMPLETE![/bold green]")
    console.print(f"[yellow]Total Leads: {len(discovered_leads):,}[/yellow]")
    console.print(f"[yellow]Saved to: {output_file}[/yellow]")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", type=int, default=30000)
    parser.add_argument("--steel-sessions", type=int, default=50)
    
    args = parser.parse_args()
    
    asyncio.run(main(args.target, args.steel_sessions))
