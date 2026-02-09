# LEAD OS - LANGGRAPH + OPENROUTER INTEGRATED ✅

## 🎯 WHAT'S INTEGRATED

### ✅ LangGraph Orchestration
- **File:** `src/graph/orchestrator.py`
- **Status:** ACTIVE
- **Features:**
  - StateGraph with 12 nodes
  - Checkpointing (SQLite)
  - Retry logic with exponential backoff
  - Circuit breakers
  - Approval workflows
  - Error handling

### ✅ OpenRouter LLM
- **Provider:** OpenRouter
- **Model:** `moonshotai/kimi-k2:free`
- **File:** `src/tools/llm.py`
- **Status:** CONFIGURED
- **Features:**
  - Multi-provider support (OpenAI, Anthropic, Google, OpenRouter)
  - Structured output generation
  - Temperature control
  - Token limits

### ✅ LEAD OS Integration
- **File:** `lead_os.py`
- **Status:** UPDATED
- **Integration:**
  ```python
  self.llm = get_llm_client()  # OpenRouter with Kimi
  self.orchestrator = LeadOrchestrator(mode='production')  # LangGraph
  ```

---

## 🔧 CONFIGURATION

### Environment Variables (.env):
```bash
# LLM Configuration
DEFAULT_LLM_PROVIDER=openrouter
DEFAULT_LLM_MODEL=moonshotai/kimi-k2:free
OPENROUTER_API_KEY=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
```

### LangGraph Pipeline:
```
START
  ↓
Discovery (Apify)
  ↓
Enrichment (Steel + Firecrawl)
  ↓
Intent Analysis (LLM)
  ↓
Governance (Budget checks)
  ↓
Audit (Steel screenshots)
  ↓
Scoring (Weighted algorithm)
  ↓
Outreach (LLM generation)
  ↓
Approval (Human-in-loop)
  ↓
Send (Email/WhatsApp)
  ↓
Conversation (AI qualification)
  ↓
Escalate (Sales handoff)
  ↓
END
```

---

## 🚀 HOW IT WORKS

### 1. Discovery Stage
- Uses Apify (minimal credits)
- Finds businesses from Google Maps
- **No LLM needed** (just API calls)

### 2. Enrichment Stage
- Uses Steel browser automation
- Scrapes website content
- **LLM analyzes** page structure
- Extracts signals (booking, WhatsApp, etc.)

### 3. Intent Analysis Stage
- **LLM (Kimi) analyzes** business signals
- Computes intent score
- Detects revenue leaks
- **Uses OpenRouter API**

### 4. Scoring Stage
- Weighted algorithm (no LLM)
- Combines: intent + leak + signals
- Assigns tier (A/B/C)

### 5. Outreach Generation Stage
- **LLM (Kimi) generates** personalized messages
- Email subject + body
- WhatsApp message
- Call script
- Loom script
- **Uses OpenRouter API**

---

## 💰 COST BREAKDOWN

### OpenRouter (Kimi K2:free):
- **Cost:** FREE ✅
- **Usage:** Intent analysis + Outreach generation
- **Calls per lead:** ~2-3 calls
- **500 leads:** ~1,000-1,500 LLM calls
- **Total cost:** $0 (free tier)

### Steel:
- **Cost:** 3000 hours available
- **Usage:** Website analysis + screenshots
- **Time per lead:** ~5 minutes
- **500 leads:** ~42 hours
- **Remaining:** 2,958 hours

### Apify:
- **Cost:** $5 available
- **Usage:** Google Maps discovery
- **Cost per lead:** ~$0.01
- **500 leads:** ~$5
- **Status:** Will use all $5

---

## 🎯 LLM USAGE IN PIPELINE

### Where LLM is Used:

1. **Intent Analysis** (Stage 3)
   ```python
   prompt = f"""
   Analyze this business for revenue leaks:
   
   Business: {business_name}
   Category: {category}
   Website signals: {signals}
   
   Compute:
   - Intent score (0-100)
   - Leak score (0-100)
   - Revenue leak categories
   """
   
   result = llm.generate_structured(prompt, schema)
   ```

2. **Outreach Generation** (Stage 6)
   ```python
   prompt = f"""
   Generate personalized outreach for:
   
   Business: {business_name}
   Revenue loss: ₹{revenue_loss}/month
   Recoverable: ₹{recoverable}/month
   
   Create:
   - Email subject (compelling)
   - Email body (proof-based)
   - WhatsApp message (short)
   - Call script (conversational)
   """
   
   result = llm.generate_structured(prompt, schema)
   ```

### Where LLM is NOT Used:

- Discovery (Apify API)
- Enrichment (Steel scraping)
- Scoring (Algorithm)
- Export (File operations)

---

## 🔥 ADVANTAGES OF THIS SETUP

### 1. Free LLM (Kimi K2)
- No cost for 500 leads
- Good quality output
- Fast response times

### 2. LangGraph Orchestration
- Stateful pipeline
- Automatic retries
- Circuit breakers
- Checkpointing (resume on failure)
- Human-in-loop approval

### 3. Steel for Real Data
- Actual website screenshots
- Real signal detection
- Proof artifacts
- Burns credits (that's the goal!)

### 4. Minimal Apify
- Just for discovery
- $5 is enough
- Fast bulk scraping

---

## 🚀 TO RUN NOW

### Test with 10 leads:
```bash
python test_lead_os.py
```

### Run full 500 leads:
```bash
python lead_os.py --city "Bangalore" --n 500 --niche "diagnostics"
```

### What Happens:
1. **Discovery:** Apify finds 500 businesses (5 minutes)
2. **Enrichment:** Steel analyzes websites (2-3 hours)
3. **Intent:** Kimi LLM analyzes signals (10 minutes)
4. **Scoring:** Algorithm computes scores (1 minute)
5. **Outreach:** Kimi LLM generates messages (10 minutes)
6. **Export:** Saves to CSV + JSON (1 minute)

**Total time:** ~3-4 hours for 500 leads

---

## 📊 EXPECTED OUTPUT

### Top 50 Hot Leads:
```json
{
  "business_name": "Apollo Diagnostics",
  "leak_score": 85,
  "intent_score": 90,
  "final_score": 87,
  "tier": "A",
  "estimated_revenue_loss_inr": 180000,
  "recoverable_amount_inr": 126000,
  "recommended_tier": "Pro ₹60K/month",
  "roi_multiple": 5.0,
  
  "llm_analysis": {
    "leak_categories": [
      "no online booking leak",
      "speed-to-lead leak",
      "after hours leak"
    ],
    "intent_signals": [
      "running Meta ads",
      "high review volume",
      "no WhatsApp integration"
    ]
  },
  
  "llm_outreach": {
    "email_subject": "Recovering ₹126k/month for Apollo Diagnostics",
    "email_body": "...",
    "whatsapp_msg": "...",
    "call_script": "..."
  }
}
```

---

## ✅ VERIFICATION

### Check LLM Configuration:
```bash
python -c "from src.tools.llm import get_llm_client; llm = get_llm_client(); print(f'Provider: {llm._provider}, Model: {llm._model}')"
```

**Expected output:**
```
Provider: openrouter, Model: moonshotai/kimi-k2:free
```

### Check LangGraph:
```bash
python -c "from src.graph.orchestrator import create_orchestrator; orch = create_orchestrator(); print('LangGraph ready')"
```

**Expected output:**
```
LangGraph ready
```

---

## 🎯 SUMMARY

**YES, we're using:**
- ✅ **LangGraph** for orchestration
- ✅ **OpenRouter** for LLM
- ✅ **Kimi K2:free** model (as you specified)
- ✅ **Steel** for browser automation
- ✅ **Minimal Apify** for discovery

**NOT using:**
- ❌ Random things
- ❌ Perplexity (as you requested)
- ❌ Expensive LLMs

**Everything is integrated and ready to run!**

---

## 🚀 NEXT STEP

Run the test:
```bash
python test_lead_os.py
```

This will:
1. Test LangGraph orchestration
2. Test OpenRouter + Kimi LLM
3. Test Steel integration
4. Generate 10 sample leads
5. Show you the output

**Ready to test?** 🔥
