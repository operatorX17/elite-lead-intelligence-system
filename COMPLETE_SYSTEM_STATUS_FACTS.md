# ZRAI LEAD OS - COMPLETE SYSTEM STATUS (FACTS ONLY)

**Date:** February 22, 2026  
**Database:** Supabase (CONNECTED ✅)  
**Total Leads:** 293 in database

---

## 1. FULL PIPELINE ARCHITECTURE

```
Discovery → Enrichment → Intent → Audit → Scoring → Outreach → Conversation
```

**What each agent does:**
- **Discovery**: Bulk ingestion via Apify (Meta Ads, Google Maps)
- **Enrichment**: Contact extraction + tech signals + **VOLUME SIGNALS** (NEW)
- **Intent**: Intent scoring + leak scoring + **VOLUME SCORING** (NEW)
- **Audit**: Proof generation via Steel.dev browser automation
- **Scoring**: Weighted scoring (15% volume, 30% intent, 25% leak, 15% reactivation, 10% contact, 5% ads)
- **Outreach**: Evidence-backed message generation with proof screenshots
- **Conversation**: AI-driven BANT qualification

---

## 2. WHAT'S IMPLEMENTED (CODE EXISTS ✅)

### Database Schema
- ✅ `leads` table (293 records)
- ✅ `enrichment_data` table with **16 NEW VOLUME COLUMNS**:
  - `peak_busyness` (0-100)
  - `avg_busyness` (0-100)
  - `busy_hours_count` (hours/week >70% traffic)
  - `avg_visit_duration_min` (minutes)
  - `popular_times_histogram` (JSON)
  - `popular_times_live_text` (string)
  - `people_typically_spend_here` (string)
  - `is_peak_busy` (boolean)
  - `is_above_average` (boolean)
  - `opening_hours` (JSON)
  - `reviews_distribution` (JSON)
  - `questions_and_answers` (JSON)
  - `web_results` (JSON)
  - `table_reservation_links` (JSON)
  - `image_categories` (JSON)
- ✅ `intent_data` table with `volume_score` column
- ✅ `scoring_results` table
- ✅ `proof_artifacts` table
- ✅ `outreach_queue` table
- ✅ `conversations` table
- ✅ Migration `003_add_volume_signals.sql` **RAN SUCCESSFULLY**

### Agent Implementations
- ✅ **Discovery Agent** (`src/agents/discovery.py`)
  - Apify Meta Ads scraper integration
  - Apify Google Maps scraper integration (WITH MAXIMUM SIGNAL EXTRACTION)
  - Auto-process feature (100X upgrade)
  - Deduplication logic
  
- ✅ **Enrichment Agent** (`src/agents/enrichment.py`)
  - Tech signal extraction (booking, CRM, chat, forms)
  - Contact normalization
  - **NEW: `_extract_volume_signals()` method (150 lines)**
  - **NEW: `_parse_duration()` method** ("20 min to 2 hr" → 70 min)
  - Extracts ALL 16 volume signals from Google Maps data
  
- ✅ **Intent Agent** (`src/agents/intent.py`)
  - Intent score calculation (0-100)
  - Leak score calculation (0-100)
  - Reactivation fit calculation (0-100)
  - **NEW: `_calculate_volume_score()` method**
    - Reviews: 0-40 pts (>500 = 40, >200 = 30, >100 = 20, >50 = 10)
    - Peak busyness: 0-30 pts (>90 = 30, >70 = 20, >50 = 10)
    - Busy hours: 0-20 pts (>40 hrs/week = 20, >20 = 10)
    - Visit duration: 0-10 pts (>60 min = 10, >30 = 5)
  - Speed-to-lead risk classification
  - Review mining for pain points
  
- ✅ **Scoring Agent** (`src/agents/scoring.py`)
  - **UPDATED WEIGHTS** (100X ENHANCED):
    - Volume: 15% (NEW)
    - Intent: 30% (reduced from 35%)
    - Leak: 25%
    - Reactivation: 15% (reduced from 20%)
    - Contact Quality: 10%
    - Ad Activity: 5% (reduced from 20%)
    - Business Size: 0% (removed)
  - **UPDATED TIER THRESHOLDS** (realistic):
    - Tier A: ≥55 (was 80)
    - Tier B: ≥35 (was 60)
    - Tier C: <35
  - **REMOVED** "no_ads_history" disqualification rule
  - Disqualification rules: emergency-only, no contact path
  
- ✅ **Audit Agent** (`src/agents/audit.py`)
  - Steel.dev browser automation integration
  - Screenshot capture (hero + CTA)
  - Proof pack generation (3 audit bullets)
  - Score threshold: 70+ triggers audit
  
- ✅ **Outreach Agent** (`src/agents/outreach.py`)
  - LLM-based message generation
  - A/B variant creation
  - Proof screenshot attachment
  - Opt-out compliance

### Tools & Integrations
- ✅ **Apify Client** (`src/tools/apify.py`)
  - **MAXIMUM SIGNAL EXTRACTION CONFIG**:
    - `scrapePlaceDetailPage: True`
    - `includeHistogram: True`
    - `includeOpeningHours: True`
    - `maxQuestions: 999`
    - `maxImages: 50`
    - `scrapeContacts: True`
    - `maxReviews: 100`
  - Meta Ads scraper
  - Google Maps scraper
  - Website crawler
  
- ✅ **Supabase Client** (`src/db/client.py`)
  - HTTP/1.1 patched (fixes Windows socket errors)
  - All CRUD operations for 13 tables
  - Circuit breaker management
  - Usage tracking
  
- ✅ **Steel Client** (`src/tools/steel.py`) - exists but not tested
- ✅ **LLM Client** (`src/tools/llm.py`) - exists but not tested

### Configuration
- ✅ `config/niches.yaml` - Per-niche scoring weights
- ✅ `config/budgets.yaml` - Rate limits and budgets
- ✅ `config/policies.yaml` - DNC rules and compliance
- ✅ `.env` - API keys and secrets

---

## 3. WHAT'S NOT WORKING (UNTESTED ❌)

### Never Run on Real Data
- ❌ **Discovery Agent**: Not run on your 5 hospitals
- ❌ **Enrichment Agent**: No Google Maps data scraped for hospitals
- ❌ **Intent Agent**: No volume scores calculated for hospitals
- ❌ **Scoring Agent**: No real scores with volume for hospitals
- ❌ **Audit Agent**: Steel.dev never tested
- ❌ **Outreach Agent**: Never generated real messages
- ❌ **Conversation Agent**: Never tested

### Missing Real Data
- ❌ **Your 5 Hospitals** (in `ELITE_INTELLIGENCE_Hyderabad_5_hospitals.json`):
  - HKC Hospital
  - Royal Multi Speciality Hospital
  - Sri Chandra Multi Speciality Hospital
  - St Theresa's Multi Specialty Hospital
  - Premier Super Specialty Hospital
  
  **Missing fields:**
  - `reviews_count` / `reviewsCount` (CRITICAL for volume score)
  - `rating` / `review_rating`
  - `popularTimesHistogram` (CRITICAL for peak busyness)
  - `peopleTypicallySpendHere` (for visit duration)
  - `openingHours`
  - `reviewsDistribution`
  - `questionsAndAnswers`
  
  **What they have:**
  - business_name ✅
  - location ✅
  - website ✅ (4 out of 5)
  - phone ✅ (4 out of 5)
  - bed_count (estimated 100)

### Database Status
- ✅ 293 leads in database (from previous runs)
- ❌ None of your 5 hospitals are in the database
- ❌ No enrichment data with volume signals
- ❌ No intent data with volume scores
- ❌ No scoring results with volume weights

---

## 4. THE DATA GAP (ROOT CAUSE)

**Problem:** Your 5 hospitals were manually created, NOT scraped from Google Maps.

**What's missing:**
1. Google Maps scraping never ran for these hospitals
2. No `popularTimesHistogram` data
3. No `reviews_count` data
4. No `rating` data
5. No `peopleTypicallySpendHere` data

**Impact:**
- Volume score = 0 (no data to score)
- Intent score = lower (missing high-ticket signals)
- Final score = lower (missing 15% volume weight)
- No proof of "busy but inefficient" businesses

---

## 5. WHAT NEEDS TO HAPPEN (ACTION PLAN)

### Step 1: Scrape Google Maps Data for 5 Hospitals
```python
from src.agents.discovery import DiscoveryAgent

agent = DiscoveryAgent()

# Scrape each hospital
hospitals = [
    "HKC Hospital Hyderabad",
    "Royal Multi Speciality Hospital Hyderabad",
    "Sri Chandra Multi Speciality Hospital Hyderabad",
    "St Theresa's Multi Specialty Hospital Hyderabad",
    "Premier Super Specialty Hospital Hyderabad"
]

for hospital in hospitals:
    leads = agent.discover_from_google_maps(
        keywords=[hospital],
        geo={"city": "Hyderabad", "state": "Telangana", "country": "India"},
        limit=1,
        auto_process=True  # Runs enrichment + intent + scoring automatically
    )
```

### Step 2: Verify Volume Signals Extracted
```python
from src.db.client import SupabaseClient

client = SupabaseClient()

# Check enrichment data
enrichment = client.get_enrichment_data(lead_id)
print(f"Peak busyness: {enrichment.get('peak_busyness')}")
print(f"Busy hours: {enrichment.get('busy_hours_count')}")
print(f"Visit duration: {enrichment.get('avg_visit_duration_min')}")
```

### Step 3: Verify Volume Scores Calculated
```python
# Check intent data
intent = client.get_intent_data(lead_id)
print(f"Volume score: {intent.get('volume_score')}")
print(f"Intent score: {intent.get('intent_score')}")
print(f"Leak score: {intent.get('leak_score')}")
```

### Step 4: Verify Final Scoring with Volume
```python
# Check scoring results
scoring = client.get_scoring_result(lead_id)
print(f"Final score: {scoring.get('final_score')}")
print(f"Tier: {scoring.get('lead_tier')}")
print(f"Score breakdown: {scoring.get('score_breakdown')}")
```

### Step 5: Generate Complete Analysis
```python
# Run complete analysis script
python show_complete_lead_analysis.py --lead-id <lead_id>
```

---

## 6. MCP TOOLS AVAILABLE

### Semgrep (Code Analysis)
- `semgrep_rule_schema` - Get rule schema
- `get_supported_languages` - List supported languages
- `semgrep_findings` - Fetch findings from Semgrep AppSec Platform
- `semgrep_scan_with_custom_rule` - Scan with custom rule
- `semgrep_scan` - Scan code files
- `get_abstract_syntax_tree` - Get AST for code
- `semgrep_scan_supply_chain` - Supply chain scan

### Context7 (Documentation)
- `resolve_library_id` - Resolve library name to ID
- `query_docs` - Query documentation

### Firecrawl (Web Scraping)
- `firecrawl_scrape` - Scrape single URL
- `firecrawl_map` - Discover URLs on site
- `firecrawl_search` - Web search
- `firecrawl_crawl` - Crawl multiple pages
- `firecrawl_extract` - Extract structured data
- `firecrawl_agent` - Autonomous research agent

### Steel (Browser Automation)
- `steel_navigate` - Navigate to URL
- `steel_search` - Google search
- `steel_click` - Click element
- `steel_type` - Type text
- `steel_scroll_down` - Scroll down
- `steel_scroll_up` - Scroll up
- `steel_go_back` - Go back
- `steel_wait` - Wait for page load
- `steel_save_unmarked_screenshot` - Save screenshot

### N8N (Workflow Automation)
- `n8n_documentation` - Get docs
- `search_nodes` - Search n8n nodes
- `get_node` - Get node info
- `validate_node` - Validate config
- `get_template` - Get template
- `search_templates` - Search templates
- `validate_workflow` - Validate workflow

### Brave Search
- `brave_web_search` - Web search
- `brave_local_search` - Local business search

---

## 7. TECH STACK SUMMARY

### Runtime
- **Language:** Python 3.11+
- **Orchestration:** LangGraph (stateful graphs)
- **Database:** Supabase (PostgreSQL)
- **Type System:** Pydantic v2
- **Testing:** pytest + hypothesis

### External Services
- **Apify:** Web scraping (Meta Ads, Google Maps)
- **Steel.dev:** Browser automation (proof generation)
- **Firecrawl:** Web scraping (MCP)
- **Brave Search:** Web search (MCP)
- **Context7:** Documentation lookup (MCP)
- **Semgrep:** Code analysis (MCP)
- **N8N:** Workflow automation (MCP)

### Agent Architecture
- **9 Specialist Agents:** Discovery, Enrichment, Intent, Audit, Scoring, Outreach, Conversation, Governance, Eval
- **Circuit Breakers:** Failure tracking and recovery
- **Rate Limiting:** Per-domain, per-channel limits
- **Kill Switches:** Global and per-agent emergency stops
- **Idempotency:** All external operations have idempotency keys
- **Audit Logging:** Append-only action logs

---

## 8. WHAT'S WORKING RIGHT NOW (TESTED ✅)

1. ✅ Database connection (Supabase)
2. ✅ Database schema (all 13 tables exist)
3. ✅ Volume signal columns (16 new columns in enrichment_data)
4. ✅ Migration ran successfully
5. ✅ Agent code exists and imports successfully
6. ✅ Configuration loads successfully
7. ✅ Apify client configured with maximum signal extraction
8. ✅ Volume score calculation logic (tested with mock data)
9. ✅ Duration parsing logic (tested: "20 min to 2 hr" → 70 min)
10. ✅ Scoring weights updated (15% volume)
11. ✅ Tier thresholds adjusted (55/35 instead of 80/60)

---

## 9. WHAT'S NOT WORKING (FACTS ❌)

1. ❌ Discovery agent never run on your 5 hospitals
2. ❌ Google Maps data never scraped for hospitals
3. ❌ Enrichment agent never extracted volume signals from real data
4. ❌ Intent agent never calculated volume scores from real data
5. ❌ Scoring agent never scored leads with volume weights
6. ❌ Audit agent (Steel.dev) never tested
7. ❌ Outreach agent never generated real messages
8. ❌ Conversation agent never tested
9. ❌ No review text analysis (no pain point detection)
10. ❌ No proof artifacts generated
11. ❌ No outreach messages queued
12. ❌ No conversations tracked

---

## 10. THE BOTTOM LINE

**CODE STATUS:** 100% implemented ✅  
**DATABASE STATUS:** 100% ready ✅  
**DATA STATUS:** 0% populated ❌  
**TESTING STATUS:** 0% tested with real data ❌

**What you have:**
- Complete agent implementations
- Complete database schema
- Complete volume signal extraction logic
- Complete volume scoring logic
- Complete weighted scoring system
- 293 leads in database (from previous runs)

**What you DON'T have:**
- Google Maps data for your 5 hospitals
- Volume signals extracted for any leads
- Volume scores calculated for any leads
- Final scores with volume weights
- Proof artifacts from Steel.dev
- Outreach messages generated
- Any evidence that the system works end-to-end

**What needs to happen:**
1. Run Apify Google Maps scraper for 5 hospitals
2. Extract volume signals using enrichment agent
3. Calculate volume scores using intent agent
4. Rescore with volume weights using scoring agent
5. Generate proof artifacts using audit agent (optional)
6. Generate outreach messages using outreach agent (optional)
7. Prove the system works with real evidence

**Time estimate:** 30-60 minutes to run full pipeline on 5 hospitals

---

**Last Updated:** February 22, 2026  
**Status:** READY TO RUN - Code complete, data missing
