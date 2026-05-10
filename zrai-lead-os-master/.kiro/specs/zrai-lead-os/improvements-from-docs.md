# ZRAI Lead OS - Improvement Recommendations from Documentation Review

## Overview

This document captures improvement recommendations based on comprehensive review of:
- **LangGraph Documentation** (https://docs.langchain.com/oss/python/langgraph/)
- **Apify Documentation** (https://docs.apify.com/)
- **Firecrawl Documentation** (https://docs.firecrawl.dev/)

## Key Learnings & Recommendations

---

## 1. LangGraph Improvements

### 1.1 State Management Enhancements

**Current Implementation:** Basic `LeadGraphState` with simple state transitions.

**Recommended Improvements:**

1. **Use Annotated Reducers for Message History**
   ```python
   from typing import Annotated
   from langgraph.graph.message import add_messages
   
   class LeadGraphState(TypedDict):
       messages: Annotated[list, add_messages]  # Auto-handles message deduplication
       lead_id: UUID
       # ... other fields
   ```

2. **Implement Multiple Schemas for Input/Output Separation**
   ```python
   class InputState(TypedDict):
       lead_id: UUID
       raw_lead_data: Dict[str, Any]
   
   class OutputState(TypedDict):
       lead: Lead
       scoring: ScoringData
       outreach_messages: List[OutreachMessage]
   
   class OverallState(InputState, OutputState):
       current_stage: str
       enrichment: EnrichmentData
       # ... internal state
   
   builder = StateGraph(OverallState, input_schema=InputState, output_schema=OutputState)
   ```

3. **Use RemainingSteps for Proactive Recursion Handling**
   ```python
   from langgraph.managed import RemainingSteps
   
   class LeadGraphState(TypedDict):
       remaining_steps: RemainingSteps
       # ... other fields
   
   def scoring_node(state: LeadGraphState) -> dict:
       if state["remaining_steps"] <= 2:
           return {"messages": ["Approaching limit, finalizing..."]}
       # Normal processing
   ```

### 1.2 Command-Based Control Flow

**Current Implementation:** Separate conditional edge functions.

**Recommended Improvement:** Use `Command` for combined state updates + routing:

```python
from langgraph.types import Command

def scoring_node(state: LeadGraphState) -> Command:
    # Compute scoring
    scoring_result = compute_scoring(state)
    
    # Combined state update + routing decision
    if scoring_result.lead_tier == "C":
        return Command(
            update={"scoring": scoring_result, "is_disqualified": True},
            goto="end"
        )
    elif scoring_result.lead_tier == "A":
        return Command(
            update={"scoring": scoring_result},
            goto="outreach"
        )
    else:
        return Command(
            update={"scoring": scoring_result},
            goto="outreach"
        )
```

### 1.3 Send for Parallel Processing (Map-Reduce Pattern)

**Current Implementation:** Sequential lead processing.

**Recommended Improvement:** Use `Send` for map-reduce patterns to process multiple leads in parallel:

```python
from langgraph.types import Send
from typing import Annotated
import operator

class BatchLeadState(TypedDict):
    """State for batch lead processing."""
    discovery_query: str
    discovered_leads: list[Lead]
    enriched_leads: Annotated[list[Lead], operator.add]  # Reducer for parallel results
    scored_leads: Annotated[list[Lead], operator.add]

def discovery_to_enrichment(state: BatchLeadState) -> list[Send]:
    """Fan-out: Route each discovered lead to parallel enrichment."""
    return [
        Send("enrichment", {
            "lead": lead,
            "lead_id": lead.lead_id,
            "discovery_query": state["discovery_query"]
        })
        for lead in state["discovered_leads"]
    ]

def enrichment_to_scoring(state: BatchLeadState) -> list[Send]:
    """Fan-out: Route each enriched lead to parallel scoring."""
    return [
        Send("scoring", {
            "lead": lead,
            "enrichment": lead.enrichment
        })
        for lead in state["enriched_leads"]
    ]

# Build graph with parallel processing
builder = StateGraph(BatchLeadState)
builder.add_node("discovery", discovery_node)
builder.add_node("enrichment", enrichment_node)
builder.add_node("scoring", scoring_node)
builder.add_node("aggregate", aggregate_results_node)

builder.add_edge(START, "discovery")
builder.add_conditional_edges("discovery", discovery_to_enrichment, ["enrichment"])
builder.add_conditional_edges("enrichment", enrichment_to_scoring, ["scoring"])
builder.add_edge("scoring", "aggregate")
builder.add_edge("aggregate", END)
```

### 1.4 Node Caching for Expensive Operations

**Recommended Addition:**
```python
from langgraph.cache import cache

@cache
def intent_node(state: LeadGraphState) -> LeadGraphState:
    """Cache LLM-based intent analysis results."""
    # Expensive LLM call - results cached based on input
    return _intent_agent(state)
```

---

## 2. Apify Integration Improvements

### 2.1 Enhanced Google Maps Scraper Configuration

**Current Implementation:** Basic search queries.

**Recommended Improvements based on Apify docs:**

```python
def run_google_maps_scraper(
    self,
    keywords: List[str],
    geo: Dict[str, str],
    limit: int = 100,
) -> List[Dict[str, Any]]:
    input_data = {
        "searchStringsArray": search_queries,
        "maxCrawledPlacesPerSearch": limit // len(keywords),
        "language": "en",
        "includeWebResults": False,
        # NEW: Enhanced options from docs
        "maxReviews": 10,  # Get review snippets for intent analysis
        "maxImages": 0,  # Skip images to save credits
        "includeHistogram": False,
        "includeOpeningHours": True,  # Critical for after-hours analysis
        "includePeopleAlsoSearch": False,
        "additionalInfo": True,  # Get business attributes
        "scrapeDirectories": False,
        "deeperCityScrape": False,
        "oneReviewPerRow": False,
        # Proxy configuration for reliability
        "proxyConfiguration": {
            "useApifyProxy": True,
            "apifyProxyGroups": ["RESIDENTIAL"]
        }
    }
```

### 2.2 Website Content Crawler for Better Enrichment

**Current Implementation:** Basic website crawling.

**Recommended Improvement:** Use `apify/website-content-crawler` with LLM-optimized output:

```python
WEBSITE_CRAWLER_ACTOR = "apify/website-content-crawler"

def crawl_website_for_enrichment(
    self,
    url: str,
    max_pages: int = 10,
) -> Dict[str, Any]:
    input_data = {
        "startUrls": [{"url": url}],
        "maxCrawlPages": max_pages,
        # NEW: Optimized for LLM consumption
        "crawlerType": "playwright:firefox",  # Better JS rendering
        "saveMarkdown": True,  # LLM-ready format
        "saveHtml": False,  # Skip raw HTML
        "removeElementsCssSelector": "nav, header, footer, .cookie-banner, .modal",
        "clickElementsCssSelector": "[data-expand], .show-more",  # Expand content
        "htmlTransformer": "readableText",  # Clean output
        "maxScrollHeightPixels": 5000,  # Load lazy content
        "waitForDynamicContent": 3000,  # Wait for JS
    }
```

### 2.3 Exponential Backoff (Already in Apify SDK)

**Note:** The Apify Python SDK already implements exponential backoff transparently. No code changes needed, but good to document:

```python
# The ApifyClient automatically handles rate limits with exponential backoff
# No manual retry logic needed for Apify calls
```

### 2.4 Async Actor Calls for Better Performance

**Recommended Addition:**
```python
async def run_google_maps_scraper_async(
    self,
    keywords: List[str],
    geo: Dict[str, str],
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """Async version for concurrent discovery."""
    run = await self._client.actor(self.GOOGLE_MAPS_ACTOR).start(
        run_input=input_data,
        wait_for_finish=0,  # Don't wait
    )
    
    # Return run ID for status checking
    return {"run_id": run["id"], "dataset_id": run["defaultDatasetId"]}
```

---

## 3. Firecrawl Integration (New Capability)

### 3.1 Add Firecrawl as Alternative Scraper

**Recommendation:** Add Firecrawl for structured data extraction:

```python
# src/tools/firecrawl.py
from firecrawl import FirecrawlApp

class FirecrawlClient:
    """Firecrawl client for structured web extraction."""
    
    def __init__(self, api_key: Optional[str] = None):
        config = load_config()
        self._api_key = api_key or config.firecrawl.api_key
        self._client = FirecrawlApp(api_key=self._api_key)
    
    def extract_business_info(self, url: str) -> Dict[str, Any]:
        """Extract structured business info using LLM."""
        result = self._client.scrape_url(
            url,
            params={
                "formats": ["json"],
                "jsonOptions": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "business_name": {"type": "string"},
                            "phone": {"type": "string"},
                            "email": {"type": "string"},
                            "booking_url": {"type": "string"},
                            "services": {"type": "array", "items": {"type": "string"}},
                            "business_hours": {"type": "object"},
                            "has_online_booking": {"type": "boolean"},
                            "has_contact_form": {"type": "boolean"},
                        }
                    }
                }
            }
        )
        return result.get("json", {})
    
    def extract_with_actions(self, url: str) -> Dict[str, Any]:
        """Extract data after interacting with page."""
        result = self._client.scrape_url(
            url,
            params={
                "formats": ["markdown", "screenshot"],
                "actions": [
                    {"type": "wait", "milliseconds": 2000},
                    {"type": "scroll", "direction": "down"},
                    {"type": "click", "selector": "[data-booking], .book-now, .schedule"},
                    {"type": "wait", "milliseconds": 1000},
                    {"type": "screenshot", "fullPage": False},
                ]
            }
        )
        return result
```

### 3.2 Firecrawl Agent for Complex Extraction

**Recommendation:** Use Firecrawl Agent for autonomous data gathering:

```python
def discover_with_agent(self, prompt: str, urls: Optional[List[str]] = None) -> Dict[str, Any]:
    """Use Firecrawl Agent for autonomous discovery."""
    result = self._client.agent(
        prompt=prompt,
        urls=urls,
        schema={
            "type": "object",
            "properties": {
                "businesses": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "website": {"type": "string"},
                            "phone": {"type": "string"},
                            "has_booking": {"type": "boolean"},
                            "revenue_leak_indicators": {"type": "array", "items": {"type": "string"}}
                        }
                    }
                }
            }
        }
    )
    return result
```

### 3.3 Batch Scraping for Efficiency

**Recommendation:**
```python
def batch_scrape_websites(self, urls: List[str]) -> List[Dict[str, Any]]:
    """Batch scrape multiple URLs efficiently."""
    result = self._client.batch_scrape_urls(
        urls,
        params={
            "formats": ["markdown"],
            "onlyMainContent": True,
        }
    )
    return result.get("data", [])
```

---

## 4. Architecture Improvements

### 4.1 Hybrid Scraping Strategy

**Recommendation:** Use multiple scrapers based on use case:

```python
class ScraperRouter:
    """Route scraping requests to optimal provider."""
    
    def __init__(self):
        self._apify = ApifyClient()
        self._firecrawl = FirecrawlClient()
    
    def scrape(self, url: str, task_type: str) -> Dict[str, Any]:
        if task_type == "bulk_discovery":
            # Apify for bulk Google Maps/Meta Ads
            return self._apify.run_google_maps_scraper(...)
        elif task_type == "structured_extraction":
            # Firecrawl for LLM-structured extraction
            return self._firecrawl.extract_business_info(url)
        elif task_type == "interactive_audit":
            # Firecrawl with actions for proof generation
            return self._firecrawl.extract_with_actions(url)
        else:
            # Default to Apify website crawler
            return self._apify.crawl_website(url)
```

### 4.2 Caching Layer for Scraped Data

**Recommendation:** Add caching to reduce API costs:

```python
from functools import lru_cache
import hashlib

class CachedScraperRouter(ScraperRouter):
    def __init__(self):
        super().__init__()
        self._cache = {}  # In production, use Redis
    
    def scrape(self, url: str, task_type: str, max_age_hours: int = 24) -> Dict[str, Any]:
        cache_key = hashlib.md5(f"{url}:{task_type}".encode()).hexdigest()
        
        # Check cache
        if cache_key in self._cache:
            cached = self._cache[cache_key]
            if (datetime.utcnow() - cached["timestamp"]).hours < max_age_hours:
                return cached["data"]
        
        # Fetch fresh data
        result = super().scrape(url, task_type)
        
        # Cache result
        self._cache[cache_key] = {
            "data": result,
            "timestamp": datetime.utcnow()
        }
        
        return result
```

---

## 5. New User Stories to Add

### Story 24: Firecrawl Integration
**User Story:** As a system operator, I want to use Firecrawl for structured data extraction, so that I can get LLM-ready business information without complex parsing.

### Story 25: Hybrid Scraping Strategy
**User Story:** As a cost-conscious operator, I want the system to route scraping requests to the optimal provider, so that I minimize costs while maximizing data quality.

### Story 26: LangGraph Command-Based Routing
**User Story:** As a system engineer, I want combined state updates and routing decisions, so that the graph logic is cleaner and more maintainable.

### Story 27: Parallel Lead Processing
**User Story:** As a system operator, I want discovered leads to be processed in parallel, so that the pipeline throughput is maximized.

---

## Implementation Priority

| Priority | Improvement | Effort | Impact |
|----------|-------------|--------|--------|
| P0 | Apify Website Crawler optimization | Low | High |
| P0 | LangGraph Command-based routing | Medium | High |
| P1 | Firecrawl integration | Medium | High |
| P1 | Caching layer | Medium | Medium |
| P2 | Parallel processing with Send | High | High |
| P2 | Multiple state schemas | Medium | Medium |
| P3 | Node caching | Low | Low |

---

## Files to Modify

1. `src/tools/apify.py` - Enhanced scraper configurations
2. `src/tools/firecrawl.py` - New file for Firecrawl client
3. `src/graph/orchestrator.py` - Command-based routing, Send patterns
4. `src/graph/state.py` - Multiple schemas, annotated reducers
5. `src/agents/enrichment.py` - Use optimized website crawler
6. `src/agents/audit.py` - Use Firecrawl for proof generation
7. `config/agents.yaml` - Add Firecrawl configuration

---

## References

- LangGraph Graph API: https://docs.langchain.com/oss/python/langgraph/graph-api
- Apify Website Content Crawler: https://apify.com/apify/website-content-crawler
- Apify Google Maps Scraper: https://apify.com/compass/crawler-google-places
- Firecrawl Scrape: https://docs.firecrawl.dev/features/scrape
- Firecrawl Extract: https://docs.firecrawl.dev/features/extract
- Firecrawl Agent: https://docs.firecrawl.dev/features/agent
