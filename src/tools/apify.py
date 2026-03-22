"""
Apify client for web scraping operations.
Requirements: 3.1, 3.3, 3.5
Runtime: Uses official apify-client SDK (NOT MCP)
"""

from typing import Dict, Any, List, Optional
import logging
import os
import time
import threading
import math
from contextlib import contextmanager

from apify_client import ApifyClient as ApifySDK

from src.config import load_config


logger = logging.getLogger(__name__)

PROXY_ENV_KEYS = [
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
]


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
    META_ADS_ACTOR = "XtaWFhbtfxyzqrFmd"
    GOOGLE_MAPS_ACTOR = "compass/crawler-google-places"
    GOOGLE_ADS_ACTOR = "N8vqwV9wL9wpIsLDz"
    WEBSITE_CRAWLER_ACTOR = "apify/website-content-crawler"
    CONTACT_SCRAPER_ACTOR = "apify/contact-info-scraper"
    
    def __init__(self, api_token: Optional[str] = None):
        config = load_config()
        self._token = api_token or config.apify.api_token
        self._config = config.apify
        self._proxy_lock = threading.Lock()

        with self._without_broken_local_proxy():
            self._client = ApifySDK(self._token)

    @contextmanager
    def _without_broken_local_proxy(self):
        """
        Temporarily remove the dead localhost:9 proxy injected into this shell.

        The local environment sets HTTP(S)_PROXY/ALL_PROXY to 127.0.0.1:9,
        which causes the Apify SDK to fail before it can reach the real API.
        """
        original_values: Dict[str, Optional[str]] = {}

        with self._proxy_lock:
            try:
                for key in PROXY_ENV_KEYS:
                    value = os.environ.get(key)
                    if value and value.strip().lower() == "http://127.0.0.1:9":
                        original_values[key] = value
                        os.environ.pop(key, None)
                yield
            finally:
                for key, value in original_values.items():
                    os.environ[key] = value
    
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
        
        country_code = (geo or {}).get("country_code") or "ALL"
        search_urls = []
        for keyword in keywords:
            encoded_keyword = keyword.strip().replace(" ", "%20")
            search_urls.append(
                {
                    "url": (
                        "https://www.facebook.com/ads/library/"
                        f"?active_status=all&ad_type=all&country={country_code}"
                        f"&q={encoded_keyword}&search_type=keyword_unordered&media_type=all"
                    )
                }
            )

        input_data = {
            "urls": search_urls,
            "scrapeAdDetails": None,
            "limitPerSource": None,
            "count": limit,
            "scrapePageAds.period": "",
            "scrapePageAds.activeStatus": "all",
            "scrapePageAds.sortBy": "impressions_desc",
            "scrapePageAds.countryCode": country_code,
            "runTag": None,
            "proxy": None,
        }
        
        try:
            with self._without_broken_local_proxy():
                run = self._client.actor(self.META_ADS_ACTOR).call(
                    run_input=input_data,
                    memory_mbytes=self._config.memory_mbytes,
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

    def run_facebook_page_ads_scraper(
        self,
        page_urls: List[str],
        count: int = 100,
        country_code: str = "ALL",
    ) -> List[Dict[str, Any]]:
        """
        Run the Facebook Ads Library actor against concrete page URLs.

        This is the cleanest way to verify whether a known business is actively
        running Facebook ads when we already have its Facebook page URL.
        """
        if not page_urls:
            return []

        logger.info("Running Facebook page ads scraper for %s page(s)", len(page_urls))

        input_data = {
            "urls": [{"url": url} for url in page_urls],
            "scrapeAdDetails": None,
            "limitPerSource": None,
            "count": count,
            "scrapePageAds.period": "",
            "scrapePageAds.activeStatus": "all",
            "scrapePageAds.sortBy": "impressions_desc",
            "scrapePageAds.countryCode": country_code,
            "runTag": None,
            "proxy": None,
        }

        try:
            with self._without_broken_local_proxy():
                run = self._client.actor(self.META_ADS_ACTOR).call(
                    run_input=input_data,
                    memory_mbytes=self._config.memory_mbytes,
                    timeout_secs=self._config.default_timeout_secs,
                )
                dataset = self._client.dataset(run["defaultDatasetId"])
                items = list(dataset.iterate_items())

            logger.info("Facebook page ads scraper returned %s results", len(items))
            return items

        except Exception as e:
            logger.error("Facebook page ads scraper error: %s", e)
            raise
    
    def run_google_maps_scraper(
        self,
        keywords: List[str],
        geo: Dict[str, str],
        limit: int = 100,
        detailed: bool = False,
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
        
        search_count = max(len(search_queries), 1)
        buffered_limit = max(limit * 2, 8)
        per_search_limit = max(4, math.ceil(buffered_limit / search_count))

        input_data = {
            "searchStringsArray": search_queries,
            "maxCrawledPlacesPerSearch": per_search_limit,
            "language": "en",
            "skipClosedPlaces": True,
        }

        if detailed:
            input_data.update({
                "scrapePlaceDetailPage": True,
                "includeHistogram": True,
                "includeOpeningHours": True,
                "includeWebResults": True,
                "includePeopleAlsoSearch": True,
                "maxQuestions": 999,
                "maxImages": 50,
                "scrapeContacts": True,
                "maxReviews": 100,
            })
        else:
            # Discovery should return quickly. Detailed contact/review scraping
            # belongs to enrichment, not the first-pass lead list.
            input_data.update({
                "scrapePlaceDetailPage": True,
                "includeHistogram": False,
                "includeOpeningHours": True,
                "includeWebResults": False,
                "includePeopleAlsoSearch": False,
                "maxQuestions": 0,
                "maxImages": 5,
                "scrapeContacts": False,
                "maxReviews": 10,
            })
        
        try:
            with self._without_broken_local_proxy():
                run = self._client.actor(self.GOOGLE_MAPS_ACTOR).call(
                    run_input=input_data,
                    memory_mbytes=self._config.memory_mbytes,
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

    def run_google_ads_scraper(
        self,
        start_urls: List[str],
        results_limit: Optional[int] = None,
        skip_details: bool = False,
        should_download_assets: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Run the Google Ads Transparency actor.

        Important: this actor needs a selected advertiser URL from the Google
        Ads Transparency Center, not just a company website/domain.
        """
        if not start_urls:
            return []

        logger.info("Running Google Ads scraper for %s advertiser URL(s)", len(start_urls))

        input_data = {
            "startUrls": [{"url": url} for url in start_urls],
            "resultsLimit": results_limit,
            "skipDetails": skip_details,
            "shouldDownloadAssets": should_download_assets,
            "shouldDownloadPreviews": False,
            "ocr": False,
            "proxyConfiguration": {
                "apifyProxyGroups": [],
                "useApifyProxy": True,
            },
        }

        try:
            with self._without_broken_local_proxy():
                run = self._client.actor(self.GOOGLE_ADS_ACTOR).call(
                    run_input=input_data,
                    memory_mbytes=self._config.memory_mbytes,
                    timeout_secs=self._config.default_timeout_secs,
                )
                dataset = self._client.dataset(run["defaultDatasetId"])
                items = list(dataset.iterate_items())

            logger.info("Google Ads scraper returned %s results", len(items))
            return items

        except Exception as e:
            logger.error("Google Ads scraper error: %s", e)
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
            with self._without_broken_local_proxy():
                run = self._client.actor(self.WEBSITE_CRAWLER_ACTOR).call(
                    run_input=input_data,
                    memory_mbytes=self._config.memory_mbytes,
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
            with self._without_broken_local_proxy():
                run = self._client.actor(self.CONTACT_SCRAPER_ACTOR).call(
                    run_input=input_data,
                    memory_mbytes=self._config.memory_mbytes,
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
        with self._without_broken_local_proxy():
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
