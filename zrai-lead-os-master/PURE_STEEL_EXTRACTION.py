#!/usr/bin/env python
"""
PURE STEEL LEAD EXTRACTION - 100% Browser Automation
No Apify. No other tools. Just Steel burning credits.

Strategy:
1. Use Steel to search Google Maps
2. Extract business listings from search results
3. Visit each business website
4. Extract deep intelligence
5. Burn 3000 hours in 3 days

Target: 30,000-40,000 leads with REAL intelligence

Usage:
    python PURE_STEEL_EXTRACTION.py --sessions 50 --target 30000
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
import logging
import re

console = Console()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Steel API configuration
STEEL_API_KEY = os.getenv("STEEL_API_KEY")
STEEL_API_URL = "https://api.steel.dev/v1"

# Configuration
MAX_PARALLEL_SESSIONS = 50
TARGET_LEADS = 30000

# Indian cities (top 100 for maximum coverage)
CITIES = [
    # Tier 1 (8 cities)
    "Mumbai", "Delhi", "Bangalore", "Hyderabad", "Chennai", "Kolkata", "Pune", "Ahmedabad",
    
    # Tier 2 (24 cities)
    "Jaipur", "Surat", "Lucknow", "Kanpur", "Nagpur", "Indore", "Thane", "Bhopal",
    "Visakhapatnam", "Pimpri-Chinchwad", "Patna", "Vadodara", "Ghaziabad", "Ludhiana",
    "Agra", "Nashik", "Faridabad", "Meerut", "Rajkot", "Kalyan-Dombivali", "Vasai-Virar",
    "Varanasi", "Srinagar", "Aurangabad",
    
    # Tier 3 (68 cities - high potential)
    "Dhanbad", "Amritsar", "Navi Mumbai", "Allahabad", "Ranchi", "Howrah", "Coimbatore",
    "Jabalpur", "Gwalior", "Vijayawada", "Jodhpur", "Madurai", "Raipur", "Kota",
    "Chandigarh", "Guwahati", "Solapur", "Hubli-Dharwad", "Mysore", "Tiruchirappalli",
    "Bareilly", "Aligarh", "Moradabad", "Jalandhar", "Bhubaneswar", "Salem", "Warangal",
    "Mira-Bhayandar", "Thiruvananthapuram", "Bhiwandi", "Saharanpur", "Guntur", "Amravati",
    "Bikaner", "Noida", "Jamshedpur", "Bhilai", "Cuttack", "Firozabad", "Kochi",
    "Nellore", "Bhavnagar", "Dehradun", "Durgapur", "Asansol", "Rourkela", "Nanded",
    "Kolhapur", "Ajmer", "Akola", "Gulbarga", "Jamnagar", "Ujjain", "Loni", "Siliguri",
    "Jhansi", "Ulhasnagar", "Jammu", "Sangli-Miraj", "Mangalore", "Erode", "Belgaum",
    "Ambattur", "Tirunelveli", "Malegaon", "Gaya", "Jalgaon", "Udaipur", "Maheshtala"
]

# Lead types with Google Maps search queries
LEAD_TYPES = [
    {
        "name": "Multi-Specialty Hospital",
        "search_query": "multi specialty hospital",
        "priority": 1,
        "target_per_city": 15
    },
    {
        "name": "Super-Specialty Hospital",
        "search_query": "super specialty hospital",
        "priority": 1,
        "target_per_city": 10
    },
    {
        "name": "General Hospital",
        "search_query": "hospital",
        "priority": 2,
        "target_per_city": 20
    },
    {
        "name": "Diagnostic Center",
        "search_query": "diagnostic center",
        "priority": 2,
        "target_per_city": 15
    },
    {
        "name": "Pathology Lab",
        "search_query": "pathology lab",
        "priority": 2,
        "target_per_city": 10
    },
    {
        "name": "Radiology Center",
        "search_query": "radiology center",
        "priority": 2,
        "target_per_city": 8
    },
    {
        "name": "Eye Hospital",
        "search_query": "eye hospital",
        "priority": 2,
        "target_per_city": 8
    },
    {
        "name": "Dental Hospital",
        "search_query": "dental hospital",
        "priority": 3,
        "target_per_city": 10
    },
    {
        "name": "Maternity Hospital",
        "search_query": "maternity hospital",
        "priority": 2,
        "target_per_city": 8
    },
    {
        "name": "Polyclinic",
        "search_query": "polyclinic",
        "priority": 3,
        "target_per_city": 12
    }
]


class SteelBrowser:
    """Manages Steel browser session"""
    
    def __init__(self, session_id: int):
        self.session_id = session_id
        self.session_token = None
        self.leads_found = 0
        self.leads_enriched = 0
        self.errors = 0
        self.start_time = datetime.utcnow()
    
    async def create_session(self) -> bool:
        """Create Steel browser session"""
        async with aiohttp.ClientSession() as http:
            headers = {
                "Authorization": f"Bearer {STEEL_API_KEY}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "sessionTimeout": 3600000,  # 1 hour
                "useProxy": True,
                "solveCaptchas": True
            }
            
            try:
                async with http.post(
                    f"{STEEL_API_URL}/sessions",
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        self.session_token = data.get("id")
                        logger.info(f"Steel-{self.session_id}: Session created")
                        return True
                    else:
                        text = await response.text()
                        logger.error(f"Steel-{self.session_id}: Failed to create session - {response.status}: {text}")
                        return False
            except Exception as e:
                logger.error(f"Steel-{self.session_id}: Error creating session - {e}")
                return False
    
    async def navigate(self, url: str) -> bool:
        """Navigate to URL"""
        async with aiohttp.ClientSession() as http:
            headers = {
                "Authorization": f"Bearer {STEEL_API_KEY}",
                "Content-Type": "application/json"
            }
            
            payload = {"url": url}
            
            try:
                async with http.post(
                    f"{STEEL_API_URL}/sessions/{self.session_token}/navigate",
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    return response.status == 200
            except Exception as e:
                logger.error(f"Steel-{self.session_id}: Navigation error - {e}")
                return False
    
    async def scrape(self) -> Dict:
        """Scrape current page"""
        async with aiohttp.ClientSession() as http:
            headers = {"Authorization": f"Bearer {STEEL_API_KEY}"}
            
            try:
                async with http.get(
                    f"{STEEL_API_URL}/sessions/{self.session_token}/scrape",
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status == 200:
                        return await response.json()
                    return {}
            except Exception as e:
                logger.error(f"Steel-{self.session_id}: Scrape error - {e}")
                return {}
    
    async def screenshot(self) -> bytes:
        """Take screenshot"""
        async with aiohttp.ClientSession() as http:
            headers = {"Authorization": f"Bearer {STEEL_API_KEY}"}
            
            try:
                async with http.get(
                    f"{STEEL_API_URL}/sessions/{self.session_token}/screenshot",
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status == 200:
                        return await response.read()
                    return b""
            except Exception as e:
                logger.error(f"Steel-{self.session_id}: Screenshot error - {e}")
                return b""
    
    async def close(self):
        """Close session"""
        if not self.session_token:
            return
        
        try:
            async with aiohttp.ClientSession() as http:
                headers = {"Authorization": f"Bearer {STEEL_API_KEY}"}
                async with http.delete(
                    f"{STEEL_API_URL}/sessions/{self.session_token}",
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    logger.info(f"Steel-{self.session_id}: Session closed")
        except Exception as e:
            logger.error(f"Steel-{self.session_id}: Error closing - {e}")


class GoogleMapsExtractor:
    """Extracts leads from Google Maps using Steel"""
    
    def __init__(self, browser: SteelBrowser):
        self.browser = browser
    
    async def search_and_extract(self, query: str, city: str, limit: int = 20) -> List[Dict]:
        """Search Google Maps and extract business listings"""
        
        # Build Google Maps search URL
        search_query = f"{query} in {city} India"
        maps_url = f"https://www.google.com/maps/search/{search_query.replace(' ', '+')}"
        
        logger.info(f"Steel-{self.browser.session_id}: Searching '{search_query}'")
        
        # Navigate to Google Maps
        success = await self.browser.navigate(maps_url)
        if not success:
            return []
        
        # Wait for results to load
        await asyncio.sleep(5)
        
        # Scrape page
        data = await self.browser.scrape()
        if not data:
            return []
        
        # Parse HTML to extract business listings
        leads = self._parse_google_maps_results(data, query, city)
        
        logger.info(f"Steel-{self.browser.session_id}: Found {len(leads)} businesses")
        self.browser.leads_found += len(leads)
        
        return leads[:limit]
    
    def _parse_google_maps_results(self, data: Dict, query: str, city: str) -> List[Dict]:
        """Parse Google Maps HTML to extract business info"""
        
        # Get HTML content
        html = str(data.get("content", ""))
        
        # Extract business names (simplified regex - real implementation would be more robust)
        business_names = re.findall(r'aria-label="([^"]+)"', html)
        
        # Extract phone numbers
        phones = re.findall(r'\+91[\s-]?\d{10}|\d{10}', html)
        
        # Extract websites
        websites = re.findall(r'https?://[^\s<>"]+', html)
        
        # Combine into leads
        leads = []
        for i, name in enumerate(business_names[:20]):  # Limit to 20
            lead = {
                "business_name": name,
                "location": city,
                "phone": phones[i] if i < len(phones) else None,
                "website": websites[i] if i < len(websites) else None,
                "lead_type": query,
                "city": city,
                "discovered_at": datetime.utcnow().isoformat(),
                "source": "steel_google_maps"
            }
            leads.append(lead)
        
        return leads


class WebsiteIntelligenceExtractor:
    """Extracts deep intelligence from websites using Steel"""
    
    def __init__(self, browser: SteelBrowser):
        self.browser = browser
    
    async def extract(self, lead: Dict) -> Dict:
        """Extract intelligence from lead website"""
        
        website = lead.get("website")
        if not website:
            return {"status": "no_website"}
        
        logger.info(f"Steel-{self.browser.session_id}: Extracting from {website}")
        
        # Navigate to website
        success = await self.browser.navigate(website)
        if not success:
            return {"status": "navigation_failed"}
        
        # Wait for page load
        await asyncio.sleep(3)
        
        # Scrape page
        data = await self.browser.scrape()
        if not data:
            return {"status": "scrape_failed"}
        
        # Extract intelligence
        content = str(data.get("content", "")).lower()
        
        intelligence = {
            "status": "success",
            "scraped_at": datetime.utcnow().isoformat(),
            "website": website,
            "has_online_booking": self._check_online_booking(content),
            "has_insurance_portal": self._check_insurance_portal(content),
            "has_patient_portal": self._check_patient_portal(content),
            "bed_count": self._extract_bed_count(content),
            "departments": self._extract_departments(content),
            "contact_emails": self._extract_emails(content),
            "contact_phones": self._extract_phones(content),
            "services": self._extract_services(content)
        }
        
        # Take screenshot
        screenshot = await self.browser.screenshot()
        if screenshot:
            # Save screenshot (optional)
            screenshot_path = f"screenshots/{lead['business_name'].replace(' ', '_')}.png"
            # os.makedirs("screenshots", exist_ok=True)
            # with open(screenshot_path, 'wb') as f:
            #     f.write(screenshot)
            intelligence["screenshot"] = screenshot_path
        
        self.browser.leads_enriched += 1
        logger.info(f"Steel-{self.browser.session_id}: Intelligence extracted")
        
        return intelligence
    
    def _check_online_booking(self, content: str) -> bool:
        keywords = ["book appointment", "online booking", "book now", "schedule appointment"]
        return any(kw in content for kw in keywords)
    
    def _check_insurance_portal(self, content: str) -> bool:
        return "insurance" in content and ("portal" in content or "claim" in content)
    
    def _check_patient_portal(self, content: str) -> bool:
        return "patient portal" in content or "patient login" in content
    
    def _extract_bed_count(self, content: str) -> int:
        matches = re.findall(r'(\d+)\s*bed', content)
        return int(matches[0]) if matches else None
    
    def _extract_departments(self, content: str) -> List[str]:
        dept_keywords = ["cardiology", "neurology", "oncology", "orthopedics", "pediatrics", 
                        "gynecology", "radiology", "pathology", "emergency", "icu"]
        return [dept for dept in dept_keywords if dept in content]
    
    def _extract_emails(self, content: str) -> List[str]:
        emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', content)
        return list(set(emails))[:5]
    
    def _extract_phones(self, content: str) -> List[str]:
        phones = re.findall(r'\+91[\s-]?\d{10}|\d{10}', content)
        return list(set(phones))[:5]
    
    def _extract_services(self, content: str) -> List[str]:
        service_keywords = ["surgery", "consultation", "diagnostic", "emergency", "ambulance",
                           "pharmacy", "laboratory", "imaging", "rehabilitation"]
        return [svc for svc in service_keywords if svc in content]


async def worker(worker_id: int, task_queue: asyncio.Queue, result_queue: asyncio.Queue, progress, task_id):
    """Worker that processes tasks using Steel"""
    
    browser = SteelBrowser(worker_id)
    
    # Create session
    success = await browser.create_session()
    if not success:
        logger.error(f"Worker-{worker_id}: Failed to start")
        return
    
    maps_extractor = GoogleMapsExtractor(browser)
    web_extractor = WebsiteIntelligenceExtractor(browser)
    
    try:
        while True:
            try:
                task = await asyncio.wait_for(task_queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            
            if task is None:  # Poison pill
                break
            
            lead_type, city = task
            
            try:
                # Step 1: Search Google Maps and extract leads
                leads = await maps_extractor.search_and_extract(
                    lead_type["search_query"],
                    city,
                    lead_type["target_per_city"]
                )
                
                # Step 2: Extract intelligence from each lead's website
                for lead in leads:
                    intelligence = await web_extractor.extract(lead)
                    
                    # Combine
                    enriched_lead = {
                        **lead,
                        "intelligence": intelligence,
                        "priority": lead_type["priority"]
                    }
                    
                    # Add to results
                    await result_queue.put(enriched_lead)
                    progress.update(task_id, advance=1)
                
            except Exception as e:
                logger.error(f"Worker-{worker_id}: Error processing task - {e}")
                browser.errors += 1
            
            finally:
                task_queue.task_done()
    
    finally:
        await browser.close()
        
        duration = (datetime.utcnow() - browser.start_time).total_seconds()
        logger.info(
            f"Worker-{worker_id}: Found {browser.leads_found} leads, "
            f"Enriched {browser.leads_enriched}, Errors {browser.errors}, "
            f"Duration {duration:.1f}s"
        )


async def saver(result_queue: asyncio.Queue, output_file: str):
    """Save results to file"""
    
    results = []
    
    while True:
        try:
            result = await asyncio.wait_for(result_queue.get(), timeout=10.0)
            results.append(result)
            
            # Save every 50 leads
            if len(results) % 50 == 0:
                with open(output_file, 'w') as f:
                    json.dump(results, f, indent=2, default=str)
                logger.info(f"Saved {len(results)} leads")
            
            result_queue.task_done()
            
        except asyncio.TimeoutError:
            # Final save
            if results:
                with open(output_file, 'w') as f:
                    json.dump(results, f, indent=2, default=str)
                logger.info(f"Final save: {len(results)} leads")
            break


async def main(num_sessions: int = 50, target_leads: int = 30000):
    """Main execution"""
    
    console.print(Panel.fit(
        f"[bold red]🔥 PURE STEEL LEAD EXTRACTION 🔥[/bold red]\n\n"
        f"[yellow]Parallel Sessions: {num_sessions}[/yellow]\n"
        f"[yellow]Target Leads: {target_leads:,}[/yellow]\n"
        f"[yellow]Cities: {len(CITIES)}[/yellow]\n"
        f"[yellow]Lead Types: {len(LEAD_TYPES)}[/yellow]\n\n"
        f"[cyan]100% Steel - No Apify - Pure Browser Automation[/cyan]\n\n"
        f"[green]LET'S BURN 3000 HOURS![/green]",
        border_style="red"
    ))
    
    # Create queues
    task_queue = asyncio.Queue()
    result_queue = asyncio.Queue()
    
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
    
    # Start workers
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=console
    ) as progress:
        
        task_id = progress.add_task(
            "[cyan]Extracting leads with Steel...",
            total=target_leads
        )
        
        # Start workers
        workers = [
            asyncio.create_task(worker(i, task_queue, result_queue, progress, task_id))
            for i in range(num_sessions)
        ]
        
        # Start saver
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"PURE_STEEL_LEADS_{target_leads}_{timestamp}.json"
        saver_task = asyncio.create_task(saver(result_queue, output_file))
        
        # Wait for completion
        await asyncio.gather(*workers)
        await result_queue.join()
    
    console.print(f"\n[bold green]✅ EXTRACTION COMPLETE![/bold green]")
    console.print(f"[yellow]Results saved to: {output_file}[/yellow]")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--sessions", type=int, default=50, help="Parallel Steel sessions")
    parser.add_argument("--target", type=int, default=30000, help="Target leads")
    
    args = parser.parse_args()
    
    console.print(f"\n[bold]Starting Pure Steel Extraction...[/bold]\n")
    
    asyncio.run(main(args.sessions, args.target))
