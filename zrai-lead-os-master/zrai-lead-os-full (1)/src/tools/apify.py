"""
Apify client for web scraping operations.
Requirements: 3.1, 3.3, 3.5
Runtime: Uses official apify-client SDK (NOT MCP)
"""

from typing import Dict, Any, List, Optional
import logging
import time

from apify_client import ApifyClient as ApifySDK

from src.config import load_config


logger = logging.getLogger(__name__)


class ApifyClient:
    """
    Apify client wrapper for ZRAI Lead OS.
    
    Requirements:
    - 3.1: Use Apify Actors to scrape Meta Ads Library
    - 3.3: Use Apify Actors to scrape Google Maps listings
    - 3.5: Crawl contact pages for emails, phones, booking links
    
    Runtime Architecture (Rule 3):
    - Uses official apify-client SDK
    - NOT MCP at runtime
    """
    
    # Actor IDs for different scrapers
    META_ADS_ACTOR = "apify/facebook-ads-scraper"
    GOOGLE_MAPS_ACTOR = "compass/crawler-google-places"
    WEBSITE_CRAWLER_ACTOR = "apify/website-content-crawler"
    CONTACT_SCRAPER_ACTOR = "apify/contact-info-scraper"
    
    def __init__(self, api_token: Optional[str] = None):
        config = load_config()
        self._token = api_token or config.apify.api_token
        self._client = ApifySDK(self._token)
        self._config = config.apify
    
    def run_meta_ads_scraper(
        self,
        keywords: List[str],
        geo: Optional[Dict[str, str]] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Run Meta Ads Library scraper.
        Requirements: 3.1, 3.2
        """
        logger.info(f"Running Meta Ads scraper for keywords: {keywords}")
        
        input_data = {
            "searchTerms": keywords,
            "maxItems": limit,
            "adType": "all",
            "mediaType": "all",
        }
        
        if geo:
            if geo.get("country"):
                input_data["country"] = geo["country"]
        
        try:
            run = self._client.actor(self.META_ADS_ACTOR).call(
                run_input=input_data,
                timeout_secs=self._config.default_timeout_secs,
            )
            
            # Get results from dataset
            dataset = self._client.dataset(run["defaultDatasetId"])
            items = list(dataset.iterate_items())
            
            logger.info(f"Meta Ads scraper returned {len(items)} results")
            return items
            
        except Exception as e:
            logger.error(f"Meta Ads scraper error: {e}")
            raise
    
    def run_google_maps_scraper(
        self,
        keywords: List[str],
        geo: Dict[str, str],
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Run Google Maps scraper.
        Requirements: 3.3, 3.4
        """
        logger.info(f"Running Google Maps scraper for keywords: {keywords}")
        
        # Build search queries
        search_queries = []
        location = []
        if geo.get("city"):
            location.append(geo["city"])
        if geo.get("state"):
            location.append(geo["state"])
        if geo.get("country"):
            location.append(geo["country"])
        
        location_str = ", ".join(location) if location else ""
        
        for keyword in keywords:
            query = f"{keyword} {location_str}".strip()
            search_queries.append(query)
        
        input_data = {
            "searchStringsArray": search_queries,
            "maxCrawledPlacesPerSearch": limit // len(keywords) if keywords else limit,
            "language": "en",
            "includeWebResults": False,
        }
        
        try:
            run = self._client.actor(self.GOOGLE_MAPS_ACTOR).call(
                run_input=input_data,
                timeout_secs=self._config.default_timeout_secs,
            )
            
            # Get results from dataset
            dataset = self._client.dataset(run["defaultDatasetId"])
            items = list(dataset.iterate_items())
            
            logger.info(f"Google Maps scraper returned {len(items)} results")
            return items
            
        except Exception as e:
            logger.error(f"Google Maps scraper error: {e}")
            raise
    
    def crawl_website(
        self,
        url: str,
        max_pages: int = 10,
    ) -> Dict[str, Any]:
        """
        Crawl a website for contact information.
        Requirements: 3.5
        """
        logger.info(f"Crawling website: {url}")
        
        input_data = {
            "startUrls": [{"url": url}],
            "maxCrawlPages": max_pages,
            "crawlerType": "cheerio",
        }
        
        try:
            run = self._client.actor(self.WEBSITE_CRAWLER_ACTOR).call(
                run_input=input_data,
                timeout_secs=self._config.default_timeout_secs,
            )
            
            # Get results from dataset
            dataset = self._client.dataset(run["defaultDatasetId"])
            items = list(dataset.iterate_items())
            
            # Aggregate results
            result = {
                "url": url,
                "pages_crawled": len(items),
                "emails": [],
                "phones": [],
                "social_links": {},
            }
            
            for item in items:
                # Extract emails
                if item.get("emails"):
                    result["emails"].extend(item["emails"])
                
                # Extract phones
                if item.get("phones"):
                    result["phones"].extend(item["phones"])
                
                # Extract social links
                if item.get("socialLinks"):
                    for platform, link in item["socialLinks"].items():
                        if link:
                            result["social_links"][platform] = link
            
            # Deduplicate
            result["emails"] = list(set(result["emails"]))
            result["phones"] = list(set(result["phones"]))
            
            logger.info(f"Website crawl found {len(result['emails'])} emails, {len(result['phones'])} phones")
            return result
            
        except Exception as e:
            logger.error(f"Website crawler error: {e}")
            raise
    
    def extract_contact_info(self, url: str) -> Dict[str, Any]:
        """
        Extract contact information from a URL.
        Requirements: 3.5
        """
        logger.info(f"Extracting contact info from: {url}")
        
        input_data = {
            "startUrls": [{"url": url}],
            "maxRequestsPerCrawl": 5,
        }
        
        try:
            run = self._client.actor(self.CONTACT_SCRAPER_ACTOR).call(
                run_input=input_data,
                timeout_secs=self._config.default_timeout_secs,
            )
            
            # Get results from dataset
            dataset = self._client.dataset(run["defaultDatasetId"])
            items = list(dataset.iterate_items())
            
            if items:
                return items[0]
            return {}
            
        except Exception as e:
            logger.error(f"Contact info extraction error: {e}")
            raise
    
    def get_run_status(self, run_id: str) -> Dict[str, Any]:
        """Get status of an Apify run."""
        run = self._client.run(run_id).get()
        return {
            "id": run["id"],
            "status": run["status"],
            "started_at": run.get("startedAt"),
            "finished_at": run.get("finishedAt"),
        }
    
    def wait_for_run(self, run_id: str, timeout_secs: int = 300) -> Dict[str, Any]:
        """Wait for an Apify run to complete."""
        start_time = time.time()
        
        while time.time() - start_time < timeout_secs:
            status = self.get_run_status(run_id)
            
            if status["status"] in ["SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"]:
                return status
            
            time.sleep(5)
        
        raise TimeoutError(f"Run {run_id} did not complete within {timeout_secs} seconds")
