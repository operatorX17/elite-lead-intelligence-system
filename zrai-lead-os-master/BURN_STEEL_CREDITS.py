#!/usr/bin/env python
"""
STEEL CREDIT BURNER - MASSIVE PARALLEL LEAD EXTRACTION
Goal: Burn 3000 hours of Steel credits in 3 days
Target: 30,000-40,000 leads with REAL intelligence

Architecture:
- 50 parallel Steel sessions
- Each session processes 600-800 leads
- Uses Steel SDK directly (not MCP)
- Saves to database in real-time
- Runs 24/7 for 3 days

Usage:
    python BURN_STEEL_CREDITS.py --sessions 50 --target 30000
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
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.panel import Panel
from rich.table import Table
import logging

console = Console()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Steel API configuration
STEEL_API_KEY = os.getenv("STEEL_API_KEY", "ste-qXypWdcQOE3uwlKgpUO3nSKe6SeB5DFmK2Y4FOvT3IXRNcRsNMj5S3bHJuqrimOK9wTDc3uALvqdgVBLLimMXVCqR0EDb2OVOwa")
STEEL_API_URL = "https://api.steel.dev/v1"

# Configuration
MAX_PARALLEL_SESSIONS = 50  # Run 50 browsers in parallel
TARGET_LEADS = 30000
CITIES = [
    "Mumbai", "Delhi", "Bangalore", "Hyderabad", "Chennai",
    "Kolkata", "Pune", "Ahmedabad", "Jaipur", "Surat",
    "Lucknow", "Kanpur", "Nagpur", "Indore", "Thane",
    "Bhopal", "Visakhapatnam", "Pimpri-Chinchwad", "Patna", "Vadodara"
]

# Lead types to search
LEAD_TYPES = [
    {
        "name": "Hospitals",
        "keywords": ["multi specialty hospital", "super specialty hospital", "hospital"],
        "priority": "HIGH"
    },
    {
        "name": "Diagnostic Centers",
        "keywords": ["diagnostic center", "pathology lab", "radiology center"],
        "priority": "MEDIUM"
    },
    {
        "name": "Clinics",
        "keywords": ["multi specialty clinic", "polyclinic", "medical center"],
        "priority": "MEDIUM"
    },
    {
        "name": "Dental Clinics",
        "keywords": ["dental clinic", "dental hospital", "orthodontic center"],
        "priority": "LOW"
    },
    {
        "name": "Eye Hospitals",
        "keywords": ["eye hospital", "eye care center", "ophthalmology"],
        "priority": "MEDIUM"
    }
]


class SteelSession:
    """Manages a single Steel browser session"""
    
    def __init__(self, session_id: int):
        self.session_id = session_id
        self.session_token = None
        self.leads_processed = 0
        self.leads_found = 0
        self.errors = 0
        self.start_time = datetime.utcnow()
    
    async def create_session(self):
        """Create a new Steel browser session"""
        async with aiohttp.ClientSession() as http_session:
            headers = {
                "Authorization": f"Bearer {STEEL_API_KEY}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "sessionTimeout": 3600000,  # 1 hour timeout
                "useProxy": True,
                "solveCaptchas": True
            }
            
            try:
                async with http_session.post(
                    f"{STEEL_API_URL}/sessions",
                    headers=headers,
                    json=payload
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        self.session_token = data.get("id")
                        logger.info(f"Session {self.session_id}: Created Steel session {self.session_token}")
                        return True
                    else:
                        logger.error(f"Session {self.session_id}: Failed to create session: {response.status}")
                        return False
            except Exception as e:
                logger.error(f"Session {self.session_id}: Error creating session: {e}")
                return False
    
    async def navigate(self, url: str):
        """Navigate to URL"""
        async with aiohttp.ClientSession() as http_session:
            headers = {
                "Authorization": f"Bearer {STEEL_API_KEY}",
                "Content-Type": "application/json"
            }
            
            payload = {"url": url}
            
            try:
                async with http_session.post(
                    f"{STEEL_API_URL}/sessions/{self.session_token}/navigate",
                    headers=headers,
                    json=payload
                ) as response:
                    return response.status == 200
            except Exception as e:
                logger.error(f"Session {self.session_id}: Navigation error: {e}")
                return False
    
    async def scrape_page(self):
        """Scrape current page content"""
        async with aiohttp.ClientSession() as http_session:
            headers = {
                "Authorization": f"Bearer {STEEL_API_KEY}"
            }
            
            try:
                async with http_session.get(
                    f"{STEEL_API_URL}/sessions/{self.session_token}/scrape",
                    headers=headers
                ) as response:
                    if response.status == 200:
                        return await response.json()
                    return None
            except Exception as e:
                logger.error(f"Session {self.session_id}: Scrape error: {e}")
                return None
    
    async def close_session(self):
        """Close Steel session"""
        if not self.session_token:
            return
        
        async with aiohttp.ClientSession() as http_session:
            headers = {
                "Authorization": f"Bearer {STEEL_API_KEY}"
            }
            
            try:
                async with http_session.delete(
                    f"{STEEL_API_URL}/sessions/{self.session_token}",
                    headers=headers
                ) as response:
                    logger.info(f"Session {self.session_id}: Closed")
            except Exception as e:
                logger.error(f"Session {self.session_id}: Error closing: {e}")


class LeadExtractor:
    """Extracts leads using Steel browser automation"""
    
    def __init__(self, session: SteelSession):
        self.session = session
    
    async def search_google_maps(self, keyword: str, city: str) -> List[Dict]:
        """Search Google Maps for businesses"""
        query = f"{keyword} in {city} India"
        url = f"https://www.google.com/maps/search/{query.replace(' ', '+')}"
        
        # Navigate to Google Maps
        success = await self.session.navigate(url)
        if not success:
            return []
        
        # Wait for results to load
        await asyncio.sleep(3)
        
        # Scrape results
        data = await self.session.scrape_page()
        if not data:
            return []
        
        # Parse results (simplified - real implementation would parse HTML)
        leads = []
        # TODO: Parse actual Google Maps results from scraped HTML
        
        return leads
    
    async def extract_website_intelligence(self, website: str) -> Dict:
        """Extract intelligence from hospital website"""
        if not website:
            return {}
        
        # Navigate to website
        success = await self.session.navigate(website)
        if not success:
            return {}
        
        # Wait for page load
        await asyncio.sleep(2)
        
        # Scrape page
        data = await self.session.scrape_page()
        if not data:
            return {}
        
        # Extract intelligence
        intelligence = {
            "scraped_at": datetime.utcnow().isoformat(),
            "website": website,
            "has_online_booking": False,
            "has_insurance_portal": False,
            "bed_count": None,
            "departments": [],
            "contact_emails": [],
            "contact_phones": []
        }
        
        # Parse HTML content (simplified)
        content = str(data).lower()
        
        # Check for online booking
        if "book appointment" in content or "online booking" in content:
            intelligence["has_online_booking"] = True
        
        # Check for insurance portal
        if "insurance" in content and ("portal" in content or "claim" in content):
            intelligence["has_insurance_portal"] = True
        
        # Extract bed count
        import re
        bed_matches = re.findall(r'(\d+)\s*bed', content)
        if bed_matches:
            intelligence["bed_count"] = int(bed_matches[0])
        
        return intelligence


async def worker(worker_id: int, task_queue: asyncio.Queue, results_queue: asyncio.Queue, progress: Progress, task_id):
    """Worker that processes leads using Steel"""
    
    session = SteelSession(worker_id)
    extractor = LeadExtractor(session)
    
    # Create Steel session
    success = await session.create_session()
    if not success:
        logger.error(f"Worker {worker_id}: Failed to create session")
        return
    
    try:
        while True:
            # Get task from queue
            try:
                task = await asyncio.wait_for(task_queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            
            if task is None:  # Poison pill
                break
            
            lead_type, city = task
            
            try:
                # Search for leads
                for keyword in lead_type["keywords"]:
                    leads = await extractor.search_google_maps(keyword, city)
                    
                    # Process each lead
                    for lead in leads:
                        # Extract website intelligence
                        intelligence = await extractor.extract_website_intelligence(
                            lead.get("website")
                        )
                        
                        # Combine data
                        result = {
                            **lead,
                            "intelligence": intelligence,
                            "lead_type": lead_type["name"],
                            "city": city,
                            "extracted_at": datetime.utcnow().isoformat()
                        }
                        
                        # Add to results
                        await results_queue.put(result)
                        
                        session.leads_found += 1
                        progress.update(task_id, advance=1)
                
                session.leads_processed += 1
                
            except Exception as e:
                logger.error(f"Worker {worker_id}: Error processing task: {e}")
                session.errors += 1
            
            finally:
                task_queue.task_done()
    
    finally:
        # Close session
        await session.close_session()
        
        # Log stats
        duration = (datetime.utcnow() - session.start_time).total_seconds()
        logger.info(
            f"Worker {worker_id}: Processed {session.leads_processed} tasks, "
            f"Found {session.leads_found} leads, "
            f"Errors: {session.errors}, "
            f"Duration: {duration:.1f}s"
        )


async def save_results(results_queue: asyncio.Queue, output_file: str):
    """Save results to file as they come in"""
    
    results = []
    
    while True:
        try:
            result = await asyncio.wait_for(results_queue.get(), timeout=5.0)
            results.append(result)
            
            # Save every 100 leads
            if len(results) % 100 == 0:
                with open(output_file, 'w') as f:
                    json.dump(results, f, indent=2, default=str)
                logger.info(f"Saved {len(results)} leads to {output_file}")
            
            results_queue.task_done()
            
        except asyncio.TimeoutError:
            # Save final results
            if results:
                with open(output_file, 'w') as f:
                    json.dump(results, f, indent=2, default=str)
                logger.info(f"Final save: {len(results)} leads to {output_file}")
            break


async def main(num_sessions: int = 50, target_leads: int = 30000):
    """Main execution"""
    
    console.print(Panel.fit(
        f"[bold red]🔥 STEEL CREDIT BURNER 🔥[/bold red]\n"
        f"[yellow]Parallel Sessions: {num_sessions}[/yellow]\n"
        f"[yellow]Target Leads: {target_leads:,}[/yellow]\n"
        f"[yellow]Cities: {len(CITIES)}[/yellow]\n"
        f"[yellow]Lead Types: {len(LEAD_TYPES)}[/yellow]\n"
        f"[green]LET'S BURN THOSE CREDITS![/green]",
        border_style="red"
    ))
    
    # Create task queue
    task_queue = asyncio.Queue()
    results_queue = asyncio.Queue()
    
    # Generate tasks
    tasks_generated = 0
    for city in CITIES:
        for lead_type in LEAD_TYPES:
            await task_queue.put((lead_type, city))
            tasks_generated += 1
    
    console.print(f"[green]✓ Generated {tasks_generated} tasks[/green]")
    
    # Add poison pills
    for _ in range(num_sessions):
        await task_queue.put(None)
    
    # Create progress bar
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console
    ) as progress:
        
        task_id = progress.add_task(
            f"[cyan]Extracting leads...",
            total=target_leads
        )
        
        # Start workers
        workers = [
            asyncio.create_task(worker(i, task_queue, results_queue, progress, task_id))
            for i in range(num_sessions)
        ]
        
        # Start result saver
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"STEEL_LEADS_{target_leads}_{timestamp}.json"
        saver = asyncio.create_task(save_results(results_queue, output_file))
        
        # Wait for all workers to complete
        await asyncio.gather(*workers)
        
        # Wait for results to be saved
        await results_queue.join()
        
        console.print(f"\n[bold green]✅ COMPLETE![/bold green]")
        console.print(f"[yellow]Results saved to: {output_file}[/yellow]")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Burn Steel credits to extract massive leads")
    parser.add_argument("--sessions", type=int, default=50, help="Number of parallel sessions")
    parser.add_argument("--target", type=int, default=30000, help="Target number of leads")
    
    args = parser.parse_args()
    
    console.print(f"\n[bold]Starting Steel Credit Burner...[/bold]\n")
    
    # Run async main
    asyncio.run(main(args.sessions, args.target))
