# ZRAI ELITE INFRASTRUCTURE
## Master Documentation v1.0

---

# 🏗️ ARCHITECTURE OVERVIEW

```
┌─────────────────────────────────────────────────────────────────────┐
│                         ORCHESTRATOR                                 │
│                  (Coordinates all agents)                           │
└─────────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│   DISCOVERY   │    │  ENRICHMENT   │    │    SCORING    │
│    AGENT      │    │    AGENT      │    │    AGENT      │
└───────────────┘    └───────────────┘    └───────────────┘
        │                     │                     │
        ▼                     ▼                     ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│   ADS INTEL   │    │   ANALYSIS    │    │   OUTREACH    │
│    AGENT      │    │    AGENT      │    │    AGENT      │
└───────────────┘    └───────────────┘    └───────────────┘
        │                     │                     │
        └─────────────────────┼─────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       TOOL REGISTRY                                  │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐       │
│  │ Apify   │ │Firecrawl│ │Raw HTML │ │OpenRouter│ │ Future  │       │
│  │  Tool   │ │  Tool   │ │  Tool   │ │  Tool   │ │ Tools   │       │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘       │
└─────────────────────────────────────────────────────────────────────┘
```

---

# 📦 CORE COMPONENTS

## 1. Data Models (`Lead`, `TrackingData`, `ScoreData`, etc.)

All data flows through standardized models:

```python
from zrai_infrastructure import Lead, TrackingData, ScoreData

# Create a lead
lead = Lead(
    lead_id="abc123",
    business_name="Test Business",
    category="dental clinic",
    city="Mumbai"
)

# Access nested data
lead.tracking.has_gtm  # bool
lead.scores.final_score  # int
lead.contacts.whatsapp.phone_number  # str
```

## 2. Tool Registry (Plugin Architecture)

All external tools are registered and accessed through `ToolRegistry`:

```python
from zrai_infrastructure import ToolRegistry

# List available tools
tools = ToolRegistry.list_tools()
# ['apify_google_maps', 'firecrawl', 'raw_html', 'openrouter_llm']

# Execute a tool
result = ToolRegistry.execute("raw_html", url="https://example.com")

# Get tool instance
tool = ToolRegistry.get("firecrawl")
```

### Adding New Tools

```python
class MyNewTool:
    name = "my_new_tool"
    description = "Description of what it does"
    
    def execute(self, **kwargs) -> Dict[str, Any]:
        # Implementation
        return {"result": "data"}

# Register
ToolRegistry.register(MyNewTool())
```

## 3. Agents (Specialized Workers)

Each agent has a single responsibility:

| Agent | Purpose | Tools Used |
|-------|---------|------------|
| `DiscoveryAgent` | Find businesses | Apify |
| `EnrichmentAgent` | Extract website data | Firecrawl, Raw HTML |
| `AdsIntelAgent` | Check ad libraries | Apify (FB, Google) |
| `ScoringAgent` | Calculate scores | Internal algorithms |
| `AnalysisAgent` | AI analysis | OpenRouter |
| `OutreachAgent` | Generate content | Templates |

### Creating New Agents

```python
from zrai_infrastructure import BaseAgent, Lead, ToolRegistry

class MyNewAgent(BaseAgent):
    name = "my_new_agent"
    description = "What this agent does"
    
    def process(self, lead: Lead, **kwargs) -> Lead:
        # Use tools
        tool = ToolRegistry.get("some_tool")
        result = tool.execute(...)
        
        # Update lead
        lead.some_field = result["data"]
        
        return lead
```

## 4. Orchestrator (Main Controller)

The `Orchestrator` coordinates all agents:

```python
from zrai_infrastructure import Orchestrator

orchestrator = Orchestrator()

# Run full pipeline
report = orchestrator.run_pipeline(
    niche="dental clinic",
    city="Mumbai",
    target=10,
    enable_ai=True,
    enable_ads_check=False
)
```

---

# 🔌 TOOL REFERENCE

## ApifyTool (Google Maps Discovery)

```python
result = ToolRegistry.execute(
    "apify_google_maps",
    query="dental clinic in Mumbai",
    limit=20
)

# Returns:
{
    "items": [...],  # List of businesses
    "count": 20
}
```

## FirecrawlTool (Website Scraping)

```python
result = ToolRegistry.execute(
    "firecrawl",
    url="https://example.com"
)

# Returns:
{
    "success": True,
    "markdown": "...",  # Website content
    "metadata": {...}
}
```

## RawHTMLTool (Tracking Detection)

```python
result = ToolRegistry.execute(
    "raw_html",
    url="https://example.com",
    timeout=20
)

# Returns:
{
    "success": True,
    "html": "...",  # Full HTML
    "length": 12345
}
```

## OpenRouterTool (AI Analysis)

```python
result = ToolRegistry.execute(
    "openrouter_llm",
    prompt="Analyze this business...",
    system="You are a B2B sales analyst.",
    json_mode=True
)

# Returns:
{
    "success": True,
    "data": {...}  # JSON response
}
```

---

# 📊 SCORING SYSTEM

## Score Components

| Score | Weight | Description |
|-------|--------|-------------|
| `data_quality` | 15% | Completeness of data |
| `reachability` | 15% | Contact methods available |
| `money_signal` | 30% | Budget indicators |
| `opportunity` | 25% | Gap analysis |
| `urgency` | 15% | Time sensitivity |

## Lead Tiers

| Tier | Criteria | Action |
|------|----------|--------|
| `WHALE` | Running ads + high opportunity | Priority outreach |
| `HOT` | Score ≥ 70 | Immediate contact |
| `WARM` | Score ≥ 50 | Nurture sequence |
| `COLD` | Score < 50 | Low priority |

## Budget Tiers

| Tier | Money Signal | Likely Budget |
|------|--------------|---------------|
| `ENTERPRISE` | 80+ | >10L/month |
| `HIGH` | 50-79 | 2-10L/month |
| `MEDIUM` | 25-49 | 50K-2L/month |
| `LOW` | <25 | <50K/month |

---

# 🔍 DETECTION ACCURACY

## What's 100% Accurate

| Signal | Pattern | Confidence |
|--------|---------|------------|
| GTM | `GTM-XXXXX` | 100% |
| GA4 | `G-XXXXXXXXXX` | 100% |
| UA | `UA-XXXXX-X` | 100% |
| FB Pixel ID | `fbq('init', 'ID')` | 100% |
| Google Ads ID | `AW-XXXXX` | 100% |
| WhatsApp Link | `wa.me/number` | 100% |
| WhatsApp Button | Widget patterns | 95% |
| WhatsApp Mention | Text only | 50% |

---

# 🚀 USAGE EXAMPLES

## Basic Run

```bash
python -m zrai_infrastructure --niche "dental clinic" --city "Mumbai" --count 10
```

## With Ad Library Check

```bash
python -m zrai_infrastructure --niche "dental clinic" --city "Mumbai" --check-ads
```

## Without AI (Faster)

```bash
python -m zrai_infrastructure --niche "dental clinic" --city "Mumbai" --no-ai
```

## Programmatic Usage

```python
from zrai_infrastructure import Orchestrator

orch = Orchestrator()
report = orch.run_pipeline(
    niche="diagnostic center",
    city="Bangalore",
    target=20,
    enable_ai=True,
    enable_ads_check=False
)

# Access results
for lead in report["leads"]:
    if lead["tier"] == "WHALE":
        print(f"🐋 {lead['business_name']}: ₹{lead['estimated_revenue_loss']}/mo")
```

---

# 🔧 EXTENDING THE SYSTEM

## Adding a New Tool

1. Create tool class with `name`, `description`, `execute()`:

```python
class SocialMediaTool:
    name = "social_media"
    description = "Fetch social media data"
    
    def execute(self, url: str, **kwargs) -> Dict:
        # Implementation
        return {"followers": 1000}
```

2. Register the tool:

```python
from zrai_infrastructure import ToolRegistry
ToolRegistry.register(SocialMediaTool())
```

3. Use in agents:

```python
class SocialAgent(BaseAgent):
    def process(self, lead: Lead, **kwargs) -> Lead:
        tool = ToolRegistry.get("social_media")
        result = tool.execute(url=lead.website)
        lead.social_followers = result.get("followers", 0)
        return lead
```

## Adding a New Agent

1. Inherit from `BaseAgent`:

```python
from zrai_infrastructure import BaseAgent, Lead

class CustomAgent(BaseAgent):
    name = "custom_agent"
    description = "Custom processing"
    
    def process(self, lead: Lead, **kwargs) -> Lead:
        # Your logic here
        return lead
```

2. Add to Orchestrator:

```python
# In Orchestrator.__init__()
self.custom_agent = CustomAgent()

# In run_pipeline()
lead = self.custom_agent.process(lead)
```

## Adding New Data Fields

1. Add to appropriate dataclass:

```python
@dataclass
class Lead:
    # Existing fields...
    
    # New field
    custom_score: int = 0
```

2. Update `to_dict()` and `from_dict()` if needed.

---

# 📁 FILE STRUCTURE

```
/app/
├── zrai_infrastructure/
│   └── __init__.py          # Main infrastructure code
│
├── docs/
│   ├── CHANGELOG.md         # What changed
│   └── MASTER_DOCS.md       # This file
│
├── output/                   # Generated reports
│   └── {City}_{Niche}_{Timestamp}/
│       ├── report.json
│       ├── leads.json
│       └── ...
│
├── .env                      # API keys
│
└── ELITE_INTELLIGENCE_V5.py  # Standalone version
```

---

# 🔮 FUTURE INTEGRATION POINTS

## WhatsApp Business API

```python
# Future tool structure
class WhatsAppBusinessTool:
    name = "whatsapp_business"
    description = "Send messages and check responses"
    
    def execute(self, phone: str, message: str, **kwargs) -> Dict:
        # Send message
        # Wait for response
        # Return response time
        return {
            "sent": True,
            "response_time_seconds": 45,
            "has_auto_reply": True
        }
```

## Pipeline Automation

```python
# Future orchestrator method
def run_outreach_pipeline(self, leads: List[Lead]):
    for lead in leads:
        if lead.tier == LeadTier.WHALE:
            # Send immediate WhatsApp
            self.whatsapp_agent.send(lead)
        elif lead.tier == LeadTier.HOT:
            # Schedule email
            self.email_agent.schedule(lead, delay_hours=2)
        # etc.
```

## CRM Integration

```python
class CRMTool:
    name = "crm"
    description = "Push leads to CRM"
    
    def execute(self, lead: Lead, crm_type: str = "hubspot", **kwargs):
        # Push to HubSpot, Salesforce, etc.
        pass
```

---

# 🎯 DESIGN PRINCIPLES

1. **Single Responsibility** - Each agent does ONE thing well
2. **Loose Coupling** - Agents communicate via `Lead` objects
3. **Plugin Architecture** - Add tools without changing core
4. **Fail-Safe** - Graceful degradation, never crash
5. **Observable** - Every action is logged
6. **Testable** - Each component can be tested independently
7. **Scalable** - Ready for parallel processing

---

# ✅ CHECKLIST FOR NEW FEATURES

- [ ] Create tool class with `name`, `description`, `execute()`
- [ ] Register tool with `ToolRegistry.register()`
- [ ] Add data fields to appropriate dataclass
- [ ] Create agent if needed (inherit `BaseAgent`)
- [ ] Add agent to `Orchestrator`
- [ ] Update documentation
- [ ] Test independently
- [ ] Test in full pipeline

---

**Built for trillion-dollar scale. 🚀**
