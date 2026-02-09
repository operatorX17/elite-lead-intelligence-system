# EMERGENT.SH GUIDE - ZRAI Lead OS

**IMPORTANT: Build, don't document. Less README, more code.**

## Current Status

### What Works
- **Python Backend**: FastAPI server at `localhost:8000` with all 9 agents initialized
- **Database**: Supabase PostgreSQL with 28 tables (leads, contacts, outreach, etc.)
- **Discovery Agent**: Apify integration working - tested and saved 5 real leads
- **Frontend Chat**: Next.js + OpenRouter AI responding to messages
- **Authentication**: Supabase auth working

### What's Broken
- **Frontend tools return SIMULATED data** - not calling real backend
- Tools in `frontend/lib/ai/tools/zrai/*.ts` call `/api/zrai/*` routes
- Routes proxy to `http://localhost:8000/api/v1/*` but responses aren't being used properly
- AI shows fake company names like "CloudTech Solutions" instead of real Apify data

## Architecture

```
User Chat → OpenRouter AI → Tools → Next.js API Routes → Python FastAPI → LangGraph Agents
                                         ↓
                                    Supabase DB
```

## The 9 Agents (in `src/agents/`)

| Agent | File | Status | What It Does |
|-------|------|--------|--------------|
| Discovery | `discovery.py` | ✅ Working | Apify scraping (Google Maps, Meta Ads) |
| Enrichment | `enrichment.py` | ⚠️ Needs testing | Extract contacts, tech stack |
| Intent | `intent.py` | ⚠️ Needs testing | Compute intent/leak scores |
| Audit | `audit.py` | ⚠️ Needs testing | Steel.dev browser screenshots |
| Scoring | `scoring.py` | ⚠️ Needs testing | Weighted lead scoring |
| Outreach | `outreach.py` | ⚠️ Needs testing | Generate proof-backed messages |
| Conversation | `conversation.py` | ⚠️ Needs testing | AI qualification dialogue |
| Governance | `governance.py` | ⚠️ Needs testing | Rate limits, budgets, RBAC |
| Eval | `eval.py` | ⚠️ Needs testing | A/B testing, offline replay |

## Priority Tasks

### 1. Fix Frontend-Backend Integration (CRITICAL)
The tools call the backend but don't use the real data in responses.

Files to fix:
- `frontend/lib/ai/tools/zrai/discover-leads.ts` - Returns mock data
- `frontend/app/(chat)/api/zrai/discover/route.ts` - Proxy route
- All other tools in `frontend/lib/ai/tools/zrai/`

The tool calls `/api/zrai/discover` which proxies to `http://localhost:8000/api/v1/discover`. The backend returns real leads but the AI shows fake ones.

### 2. Test All Agent Endpoints
Each agent has a FastAPI endpoint in `src/api/server.py`:
- POST `/api/v1/discover` - ✅ Tested
- POST `/api/v1/enrich` - ❌ Untested
- POST `/api/v1/intent` - ❌ Untested
- POST `/api/v1/proof` - ❌ Untested
- POST `/api/v1/score` - ❌ Untested
- POST `/api/v1/outreach` - ❌ Untested
- POST `/api/v1/conversation` - ❌ Untested
- GET `/api/v1/governance` - ❌ Untested

### 3. Complete LangGraph Pipeline
The orchestrator in `src/graph/orchestrator.py` should chain agents:
```
Discovery → Enrichment → Intent → Audit → Scoring → Outreach → Conversation
```

### 4. Implement Missing Features
- **Social DM sending** - LinkedIn, Instagram outreach
- **Email sending** - SMTP integration
- **Steel.dev screenshots** - Browser automation for proof
- **A/B testing** - Eval agent for variant testing
- **Kill switches** - Emergency stop controls

## Credentials (in `.env`)

Copy `.env.example` to `.env` and fill in your API keys:
```
SUPABASE_URL=your_supabase_url
POSTGRES_URL=your_postgres_connection_string
OPENROUTER_API_KEY=your_openrouter_key
GOOGLE_API_KEY=your_google_key
PINECONE_API_KEY=your_pinecone_key
APIFY_API_TOKEN=your_apify_token
STEEL_API_KEY=your_steel_key
```

## How to Run

```bash
# Backend (Python)
cd /path/to/project
uvicorn src.api.server:app --host 0.0.0.0 --port 8000

# Frontend (Next.js)
cd frontend
pnpm install
pnpm dev
```

## Key Files

### Backend
- `src/api/server.py` - FastAPI endpoints
- `src/graph/orchestrator.py` - LangGraph pipeline
- `src/agents/*.py` - Individual agents
- `src/tools/apify.py` - Apify scraping
- `src/tools/steel.py` - Browser automation
- `src/db/client.py` - Supabase client

### Frontend
- `frontend/lib/ai/tools/zrai/*.ts` - AI tools (NEED FIXING)
- `frontend/app/(chat)/api/zrai/*.ts` - API routes
- `frontend/lib/ai/openrouter.ts` - OpenRouter config
- `frontend/artifacts/zrai/*.tsx` - UI components

### Config
- `config/agents.yaml` - Agent settings
- `config/budgets.yaml` - Rate limits
- `config/niches.yaml` - Niche keywords
- `config/policies.yaml` - Governance rules

## Database Tables (Supabase)

Main tables:
- `leads` - Lead records
- `contacts` - Contact info
- `enrichments` - Enrichment data
- `intent_signals` - Intent scores
- `proofs` - Screenshots/evidence
- `outreach_messages` - Drafted messages
- `conversations` - Chat transcripts
- `usage_metrics` - Budget tracking

## What Success Looks Like

1. User says "Find 10 SaaS leads in US"
2. AI calls discover tool → Backend calls Apify → Real leads saved to DB
3. AI shows REAL company names from Apify, not fake ones
4. User can enrich, score, draft outreach for those leads
5. Full pipeline: discover → enrich → score → draft → send

## Don't Do

- Don't write more documentation
- Don't create README files
- Don't add comments explaining obvious code
- Don't refactor working code
- Don't add tests unless asked

## Do

- Fix the frontend-backend integration
- Test each agent endpoint
- Make the pipeline work end-to-end
- Ship working features
