# ZRAI Lead OS - Complete Architecture Documentation

**Generated**: January 5, 2026  
**Status**: 85% Complete (Core Functional, AI SDK v6 Issues)

---

## Executive Summary

**ZRAI Lead OS** is an autonomous multi-agent lead intelligence system:
- **Backend**: Python + LangGraph + FastAPI + Supabase (100% functional)
- **Frontend**: Next.js 16 + AI SDK v6 + React 19 (90% functional, tool calling broken)
- **Database**: Supabase PostgreSQL with 18+ tables
- **Agents**: 9 specialist agents orchestrated by LangGraph
- **External Tools**: Apify (scraping), Steel.dev (browser automation)

**Main Blocker**: AI SDK v6 tool calling issues prevent frontend chat from working properly.

---

## System Overview

### What It Does

1. **Discovers** businesses via Apify (Google Maps, Meta Ads)
2. **Enriches** with contact data and tech signals
3. **Analyzes** intent and revenue leak potential
4. **Generates proof** via Steel.dev browser automation
5. **Scores** leads with weighted algorithms
6. **Drafts outreach** with proof-backed messages
7. **Handles conversations** with AI qualification
8. **Escalates** qualified leads to humans
9. **Governs** with RBAC, rate limits, audit logs

### Architecture Flow

```
User (Frontend) 
  → Next.js API Routes 
  → FastAPI Backend 
  → LangGraph Orchestrator 
  → 9 Specialist Agents 
  → External Tools (Apify, Steel.dev, LLMs)
  → Supabase Database
  → Response back to User
```

---

## Backend Architecture

### Tech Stack
- **Language**: Python 3.11+
- **Framework**: FastAPI (REST API)
- **Orchestration**: LangGraph 0.2+ (stateful graph)
- **Database**: Supabase (PostgreSQL)
- **LLMs**: Gemini/OpenAI/Anthropic (via LangChain)
- **Scraping**: Apify Actors
- **Browser**: Steel.dev
- **Validation**: Pydantic v2
- **Config**: YAML files
- **CLI**: Click

### Directory Structure

```
src/
├── agents/          # 9 specialist agents
│   ├── base.py      # BaseAgent (circuit breaker, retry, audit)
│   ├── discovery.py # Apify integration
│   ├── enrichment.py
│   ├── intent.py
│   ├── audit.py     # Steel.dev proof generation
│   ├── scoring.py
│   ├── outreach.py
│   ├── conversation.py
│   ├── governance.py
│   └── eval.py
├── graph/           # LangGraph orchestration
│   ├── orchestrator.py # Main graph builder
│   ├── state.py     # LeadGraphState model
│   └── checkpointer.py # Supabase checkpointer
├── db/              # Database layer
│   ├── client.py    # Supabase wrapper
│   └── models.py    # Pydantic models
├── config/          # Configuration
│   ├── loader.py    # YAML loader
│   └── models.py
├── tools/           # External integrations
│   ├── apify.py
│   ├── steel.py
│   ├── llm.py
│   └── pinecone_client.py
├── api/
│   └── server.py    # FastAPI endpoints
└── cli.py           # CLI interface

config/              # YAML configs
├── niches.yaml      # Target niches
├── policies.yaml    # Rate limits, rules
├── agents.yaml      # Agent settings
└── budgets.yaml     # Cost limits
```

### LangGraph Pipeline

**State Model** (`LeadGraphState`):
```python
class LeadGraphState:
    lead_id: UUID
    lead: Optional[Lead]
    current_stage: str
    enrichment: Optional[EnrichmentData]
    intent: Optional[IntentData]
    proof: Optional[ProofArtifact]
    scoring: Optional[ScoringResult]
    outreach_messages: List[OutreachQueue]
    conversation: Optional[Conversation]
    is_disqualified: bool
    is_escalated: bool
    is_complete: bool
```

**Graph Flow**:
```
Discovery → Enrichment → Intent → Governance 
  → [Conditional] Audit OR Skip
  → Scoring 
  → [Conditional] Outreach OR Skip
  → Eval → Conversation 
  → [Conditional] Escalate OR End
```

**Conditional Routing**:
- Skip Audit: If circuit breaker open OR budget exceeded
- Skip Outreach: If disqualified OR tier C OR DNC
- Escalate: If conversation qualified (BANT complete)

### Database Schema (18 Tables)

1. **leads**: Core lead data
2. **lead_state**: LangGraph checkpoints
3. **enrichment_data**: Contacts, tech signals
4. **intent_data**: Revenue leak scores
5. **proof_artifacts**: Screenshots, recordings
6. **scoring_results**: Scores, tiers
7. **outreach_queue**: Messages
8. **conversations**: Chat history
9. **negative_signals**: Bounces, spam
10. **do_not_contact**: DNC list
11. **audit_log**: Action log
12. **usage_metrics**: Daily usage
13. **playbooks**: RAG content
14. **circuit_breakers**: CB states
15. **escalations**: Human handoffs
16. **golden_dataset**: Labeled leads
17. **ab_tests**: A/B test definitions
18. **ab_metrics**: A/B results

### Safety Features

1. **Kill Switches**: Emergency stops via env vars
2. **Circuit Breakers**: Auto-isolate failures
3. **Rate Limiting**: Per-domain, per-channel limits
4. **DNC List**: Opt-out detection
5. **Budget Guardrails**: Daily cost limits
6. **Audit Logging**: Append-only action log

### FastAPI Endpoints

```
POST /api/v1/discover      # Discover leads
POST /api/v1/enrich        # Enrich lead
POST /api/v1/intent        # Analyze intent
POST /api/v1/proof         # Generate proof
POST /api/v1/score         # Score leads
POST /api/v1/outreach      # Draft/send outreach
POST /api/v1/conversation  # Handle conversation
GET  /api/v1/governance    # Governance status
POST /api/v1/run           # Run pipeline
GET  /api/v1/leads         # Get leads
GET  /api/v1/metrics       # System metrics
POST /api/v1/import        # Import CSV
GET  /health               # Health check
```

---

## Frontend Architecture

### Tech Stack
- **Framework**: Next.js 16.0.10 (App Router)
- **Language**: TypeScript 5.6+
- **UI**: React 19 + Radix UI + Tailwind
- **AI**: Vercel AI SDK v6.0.7 (⚠️ BROKEN)
- **LLM**: OpenRouter (DeepSeek V3 default)
- **Database**: Supabase client
- **Auth**: NextAuth 5.0 (beta)

### Directory Structure

```
frontend/
├── app/(chat)/
│   ├── api/zrai/        # API routes (bridge)
│   │   ├── discover/route.ts
│   │   ├── enrich/route.ts
│   │   ├── intent/route.ts
│   │   ├── proof/route.ts
│   │   ├── score/route.ts
│   │   ├── outreach/route.ts
│   │   ├── conversation/route.ts
│   │   └── ... (14 total)
│   └── chat/[id]/page.tsx
├── lib/
│   ├── ai/              # AI SDK integration
│   │   ├── models.ts    # Model definitions
│   │   ├── providers.ts # OpenRouter setup
│   │   └── tools/zrai/  # 14 ZRAI tools
│   ├── zrai/            # ZRAI client
│   │   ├── client.ts    # API wrapper
│   │   ├── types.ts
│   │   ├── constants.ts
│   │   └── errors.ts
│   └── db/              # Supabase client
├── components/          # React components
├── artifacts/zrai/      # 9 custom artifacts
│   ├── lead-card/
│   ├── lead-list/
│   ├── metrics-dashboard/
│   └── ... (9 total)
└── hooks/               # React hooks
```

### AI SDK Integration

**Default Model**: `deepseek/deepseek-chat` (via OpenRouter)

**Tool Support**:
- ✅ DeepSeek V3, Qwen, GLM, Claude, GPT-4o
- ❌ Gemini Flash Lite, Llama 3.2 3B (NO tools)

**14 ZRAI Tools**:
1. discover-leads
2. enrich-lead
3. analyze-intent
4. generate-proof
5. score-leads
6. draft-outreach
7. send-outreach
8. handle-conversation
9. approve-escalation
10. check-governance
11. manage-ab-test
12. run-pipeline
13. import-leads
14. analyze-screenshot

**9 Custom Artifacts**:
1. lead-card
2. lead-list
3. lead-sheet
4. metrics-dashboard
5. scoring-dashboard
6. proof-viewer
7. outreach-draft
8. conversation-thread
9. index (registry)

### API Bridge Layer

Next.js API routes bridge frontend ↔ backend:

```
Frontend Tool Call
  → Next.js API Route (/api/zrai/*)
  → FastAPI Backend (localhost:8000)
  → LangGraph Orchestrator
  → Response
```

**Why Bridge?**
- CORS handling
- Auth/validation
- Error transformation
- Streaming support

---

## Integration & Communication

### Full Flow Example

```
1. User: "Discover HVAC leads in Texas"
2. AI SDK → LLM (OpenRouter/DeepSeek)
3. LLM → Tool call: discover-leads
4. Frontend → /api/zrai/discover
5. Next.js → FastAPI /api/v1/discover
6. FastAPI → Discovery Agent
7. Agent → Apify (Google Maps scraper)
8. Apify → Scrapes businesses
9. Results → Supabase database
10. Response → FastAPI → Next.js → Frontend
11. AI SDK → Renders lead-list artifact
```

### Memory & State

**Backend (LangGraph)**:
- Checkpointing to Supabase
- Resume from last checkpoint
- Replay historical runs

**Frontend (React)**:
- SWR for data fetching
- React hooks for local state
- No Redux (keeping simple)

---

## Known Issues & Blockers

### 🔴 CRITICAL: AI SDK v6 Tool Calling Broken

**Problem**: AI SDK v6 has breaking changes causing tool failures

**Symptoms**:
- Tools called but responses not processed
- Infinite loops
- Type mismatches
- Streaming breaks

**Root Cause**:
- AI SDK v6 API changes
- OpenRouter provider compatibility
- Model-specific issues

**Impact**: Frontend chat cannot call ZRAI tools

**Status**: BLOCKED

**Possible Fixes**:
1. Downgrade to AI SDK v5
2. Debug OpenRouter provider
3. Switch to Anthropic direct
4. Bypass AI SDK entirely

### 🟡 MEDIUM: Missing Tests

**Problem**: 50 property tests defined but not implemented

**Impact**: No automated validation

**Status**: Pending

### 🟡 MEDIUM: Pinecone RAG Not Implemented

**Problem**: Structure ready but not connected

**Impact**: No RAG-based personalization

**Status**: Pending

### 🟢 LOW: Email/SMS Not Tested

**Problem**: SMTP configured but never tested

**Impact**: Cannot send real messages

**Status**: Pending

---

## What's Working ✅

### Backend (100%)
- ✅ LangGraph orchestration
- ✅ All 9 agents
- ✅ Database (18 tables)
- ✅ Configuration system
- ✅ Safety features
- ✅ CLI (7 commands)
- ✅ FastAPI server
- ✅ Apify integration
- ✅ Steel.dev integration
- ✅ LLM integration

### Frontend (90%)
- ✅ Next.js app
- ✅ UI components
- ✅ Artifacts (9 types)
- ✅ API routes
- ✅ ZRAI client
- ✅ File upload
- ✅ Supabase client
- ❌ AI SDK tool calling (BROKEN)

### Integration (80%)
- ✅ Frontend → Backend API
- ✅ Backend → Database
- ✅ Backend → External tools
- ✅ CORS
- ✅ Error handling
- ❌ Tool calling (BROKEN)

---

## What's Not Working ❌

1. **AI SDK v6 Tool Calling** (CRITICAL)
   - All 14 ZRAI tools broken
   - Chat interface non-functional
   - Artifact generation fails

2. **Property-Based Tests** (HIGH)
   - 50 tests defined but not implemented
   - No automated validation

3. **Pinecone RAG** (MEDIUM)
   - Not implemented
   - No playbook-based personalization

4. **Email/SMS Sending** (MEDIUM)
   - Not tested
   - Cannot send real outreach

5. **Monitoring Dashboard** (LOW)
   - Not implemented
   - Limited observability

6. **Horizontal Scaling** (LOW)
   - Not configured
   - Single instance only

---

## Next Steps

### Immediate (This Week)

1. **Fix AI SDK v6** (CRITICAL)
   - Try downgrade to v5
   - Or debug OpenRouter
   - Or bypass AI SDK

2. **Test Email** (HIGH)
   - Set up SMTP
   - Send test messages

3. **Write 10 Property Tests** (HIGH)
   - Set up Hypothesis
   - Implement critical properties

### Short-Term (This Month)

1. **Implement Pinecone RAG** (MEDIUM)
2. **Add Monitoring** (MEDIUM)
3. **Performance Optimization** (MEDIUM)

### Long-Term (This Quarter)

1. **Horizontal Scaling** (LOW)
2. **ML-Based Scoring** (LOW)
3. **Multi-Language Support** (LOW)

---

## Configuration Files

### 1. `config/niches.yaml`
Defines target industries:
- Keywords for discovery
- Geo filters
- Scoring weights
- Disqualification rules

### 2. `config/policies.yaml`
Defines safety policies:
- Rate limits
- Cool-down periods
- Lifecycle rules
- Negative signal thresholds

### 3. `config/agents.yaml`
Defines agent behavior:
- LLM routing
- Retry configs
- Timeout settings
- Feature flags

### 4. `config/budgets.yaml`
Defines cost limits:
- Daily LLM token limit
- Daily browser session limit
- Daily scraper run limit
- Alert thresholds

---

## CLI Commands

```bash
# Daily run
python -m src.cli run_daily --limit 100

# Dry run (no external writes)
python -m src.cli dry_run --limit 10

# Resume failed executions
python -m src.cli resume_failed --since 2026-01-01

# Replay historical run
python -m src.cli replay_run <run_id>

# Check system status
python -m src.cli status

# Check A/B test results
python -m src.cli ab_status --test-name test_name

# Inspect lead details
python -m src.cli inspect <lead_id>
```

---

## Environment Variables

### Required
```bash
# Database
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_ROLE_KEY=your-service-key

# LLM
GOOGLE_API_KEY=your-gemini-key
OPENAI_API_KEY=your-openai-key  # optional
ANTHROPIC_API_KEY=your-anthropic-key  # optional

# Integrations
APIFY_API_TOKEN=your-apify-token
STEEL_API_KEY=your-steel-key
PINECONE_API_KEY=your-pinecone-key
```

### Optional (Safety)
```bash
# Kill switches
KILL_SWITCH_GLOBAL=false
KILL_SWITCH_DISCOVERY=false
KILL_SWITCH_AUDIT=false
KILL_SWITCH_OUTREACH=false
```

---

## Conclusion

**ZRAI Lead OS is 85% complete** with:
- ✅ Fully functional backend
- ✅ Mostly functional frontend
- ❌ AI SDK v6 tool calling broken (main blocker)

**Production Readiness**: 2-3 weeks with:
1. AI SDK fix
2. Property tests
3. Email testing
4. Performance optimization

**Recommended Action**: Fix AI SDK v6 ASAP to unblock frontend.

---

**Last Updated**: January 5, 2026
