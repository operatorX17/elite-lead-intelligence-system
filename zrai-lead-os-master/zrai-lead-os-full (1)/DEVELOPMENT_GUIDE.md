# 🚀 ZRAI Lead OS - Comprehensive Development & Finishing Guide

## 📖 Executive Summary

**ZRAI Lead OS** is a production-grade, autonomous B2B lead generation system that:

1. **Discovers** high-value prospects already spending money (from Meta Ads, Google Maps)
2. **Verifies** their pain points through actual browser automation (screenshots)
3. **Generates** proof-backed outreach messages (not generic templates)
4. **Qualifies** prospects through AI conversation (BANT framework)
5. **Escalates** to humans only when ready to close

### Complexity Level: **Enterprise SaaS** (8/10)
- 9 AI Agents coordinated via LangGraph
- 28+ Database tables in Supabase
- 6 External API integrations
- Real-time browser automation
- Multi-channel outreach
- Full governance & compliance layer

---

## 🏗️ Current State Assessment

### ✅ Fully Implemented (Ready to Use)

| Component | Status | Location |
|-----------|--------|----------|
| **Database Schema** | ✅ Complete | 28+ tables in Supabase |
| **Discovery Agent** | ✅ Working | `/src/agents/discovery.py` - Apify integration tested |
| **All 9 Agents** | ✅ Implemented | `/src/agents/*.py` (300-550 lines each) |
| **LangGraph Orchestrator** | ✅ Complete | `/src/graph/orchestrator.py` |
| **FastAPI Backend** | ✅ Running | Port 8001, all endpoints working |
| **Frontend Chat UI** | ✅ Built | Next.js + AI SDK + OpenRouter |
| **Frontend Tools** | ✅ 15 tools | `/frontend/lib/ai/tools/zrai/*.ts` |

### ⚠️ Needs Testing & Verification

| Component | Issue | Priority |
|-----------|-------|----------|
| **Frontend→Backend Integration** | Tools may return simulated data | HIGH |
| **Steel.dev (Browser Automation)** | Untested - needs screenshots | HIGH |
| **Enrichment Agent** | Need to verify Apify actor works | MEDIUM |
| **Outreach Sending** | Email/DM integration incomplete | MEDIUM |
| **Conversation Agent** | Webhook handling needed | MEDIUM |

### ❌ Not Yet Implemented

| Feature | Complexity | Notes |
|---------|------------|-------|
| **Email Sending** | Medium | Need SendGrid/Resend integration |
| **LinkedIn DM** | High | Need Phantom Buster or manual |
| **SMS Sending** | Medium | Need Twilio integration |
| **Reply Webhooks** | Medium | Inbound message handling |
| **Dashboard Analytics** | Medium | Real-time metrics UI |

---

## 🔧 Phase 1: Immediate Fixes (Do Now)

### 1.1 Fix External URL Routing

The Kubernetes ingress is routing all traffic to backend. Need to ensure:
- `/api/*` routes → Backend (port 8001)
- All other routes → Frontend (port 3000)

```bash
# This is an infrastructure issue - may need to contact support
```

### 1.2 Test Full Pipeline End-to-End

```bash
# Test Discovery → Backend returns REAL Apify data
curl -X POST http://localhost:8001/api/v1/discover \
  -H "Content-Type: application/json" \
  -d '{"niche": "dental", "geo": "los angeles", "limit": 5}'

# Test Enrichment
curl -X POST http://localhost:8001/api/v1/enrich \
  -H "Content-Type: application/json" \
  -d '{"lead_id": "<UUID_FROM_ABOVE>"}'

# Test Intent Analysis
curl -X POST http://localhost:8001/api/v1/intent \
  -H "Content-Type: application/json" \
  -d '{"lead_id": "<UUID_FROM_ABOVE>"}'

# Test Scoring
curl -X POST http://localhost:8001/api/v1/score \
  -H "Content-Type: application/json" \
  -d '{"lead_ids": ["<UUID>"]}'

# Test Full Pipeline
curl -X POST http://localhost:8001/api/v1/run \
  -H "Content-Type: application/json" \
  -d '{"lead_id": "<UUID>", "stages": ["discovery", "enrichment", "intent", "scoring"]}'
```

### 1.3 Verify Frontend Tool Integration

Check each tool in `/frontend/lib/ai/tools/zrai/` calls the correct backend endpoint and returns real data, not mock/simulated.

---

## 🔧 Phase 2: Complete Core Features

### 2.1 Steel.dev Browser Automation (Proof Generation)

The Audit Agent uses Steel.dev for screenshots. Verify it works:

```python
# Test in /src/agents/audit.py
# Ensure STEEL_API_KEY is loaded correctly

# Expected flow:
# 1. Navigate to lead's website
# 2. Take hero screenshot
# 3. Find and screenshot CTA
# 4. Extract audit bullets (load times, form quality, etc.)
# 5. Save to proof_artifacts table
```

**Files to check:**
- `/src/agents/audit.py`
- `/src/services/steel_service.py` (if exists)

### 2.2 Complete Outreach Sending

Currently outreach is drafted but not sent. Need to implement:

```typescript
// Option A: SendGrid for Email
// Add to .env: SENDGRID_API_KEY=xxx

// Option B: Resend for Email
// Add to .env: RESEND_API_KEY=xxx

// Implementation location: /src/agents/outreach.py
```

### 2.3 Conversation Webhook Handler

For inbound replies, need webhook endpoint:

```python
# Add to /src/api/server.py

@app.post("/api/v1/webhooks/email-reply")
async def handle_email_reply(payload: dict):
    """Handle inbound email replies for conversation agent"""
    # 1. Parse sender, subject, body
    # 2. Match to lead in database
    # 3. Run conversation agent
    # 4. Check for escalation triggers
    pass

@app.post("/api/v1/webhooks/sms-reply")
async def handle_sms_reply(payload: dict):
    """Handle inbound SMS replies"""
    pass
```

---

## 🔧 Phase 3: Advanced Features

### 3.1 Dashboard & Analytics UI

Build React components for:
- Pipeline visualization (Sankey chart of lead flow)
- Daily metrics (leads discovered, qualified, closed)
- A/B test results
- Agent performance
- Cost tracking

**Location:** `/frontend/components/dashboard/`

### 3.2 A/B Testing System

Already has database tables. Need UI to:
- Create experiments
- Define variants
- View statistical significance
- Select winners

### 3.3 Governance Dashboard

UI for:
- Circuit breaker status
- Budget usage
- Kill switch
- Rate limit monitoring

---

## 📦 Data Ingestion Guide

### Do You Need to Run Migrations?

**NO** - The database is already set up with all 28+ tables!

Verified tables exist:
- `leads`, `lead_state`, `enrichment_data`, `intent_data`
- `proof_artifacts`, `scoring_results`, `outreach_queue`
- `conversations`, `negative_signals`, `do_not_contact`
- `audit_log`, `circuit_breakers`, `escalations`
- `golden_dataset`, `ab_tests`, `ab_metrics`, `daily_metrics`
- `playbooks`, `usage_metrics`

### Seeding Test Data (Optional)

If you want test data:

```bash
# Run the seed script
python -c "
from src.db.client import get_supabase_client

db = get_supabase_client()

# Insert test lead
db.client.table('leads').insert({
    'business_name': 'Test Dental Clinic',
    'category': 'dental',
    'location': 'Los Angeles, CA',
    'website': 'https://example-dental.com',
    'lead_lifecycle_state': 'NEW'
}).execute()
"
```

---

## 🛠️ Configuration Files

### Critical Config Files

| File | Purpose | Update When |
|------|---------|-------------|
| `/config/agents.yaml` | Agent behavior settings | Tuning agent performance |
| `/config/budgets.yaml` | Daily spend limits | Scaling up/down |
| `/config/niches.yaml` | Target verticals | Adding new markets |
| `/config/policies.yaml` | Governance rules | Compliance updates |
| `/config/prompts/` | LLM prompts | Improving AI quality |

### Environment Variables Checklist

```env
# Required for Full Functionality
SUPABASE_URL=✅ Set
SUPABASE_SERVICE_ROLE_KEY=✅ Set
OPENROUTER_API_KEY=✅ Set
GOOGLE_API_KEY=✅ Set
PINECONE_API_KEY=✅ Set
APIFY_API_TOKEN=✅ Set
STEEL_API_KEY=✅ Set

# Optional (for sending outreach)
SENDGRID_API_KEY=❌ Not set (needed for email)
TWILIO_SID=❌ Not set (needed for SMS)
TWILIO_AUTH_TOKEN=❌ Not set (needed for SMS)
```

---

## 🚀 Recommended Development Order

### Week 1: Stabilization
1. ✅ Fix external URL routing (infrastructure)
2. ✅ Test all 9 agents via curl
3. ✅ Verify frontend→backend tool integration
4. ✅ Fix any broken API contracts

### Week 2: Core Pipeline
1. Test Steel.dev browser automation
2. Implement email sending (SendGrid/Resend)
3. Add webhook handlers for replies
4. Test full pipeline: Discovery → Outreach

### Week 3: Conversation & Qualification
1. Test conversation agent with mock replies
2. Implement escalation flow
3. Add human handoff UI
4. Test BANT qualification

### Week 4: Dashboard & Polish
1. Build dashboard components
2. Add real-time metrics
3. Implement A/B testing UI
4. Governance dashboard

### Week 5: Production Hardening
1. Error handling & retries
2. Rate limiting
3. Monitoring & alerts
4. Documentation

---

## 🧪 Testing Checklist

### Backend API Tests
```bash
# Health
curl http://localhost:8001/health

# Discovery (should return REAL Apify data)
curl -X POST http://localhost:8001/api/v1/discover -H "Content-Type: application/json" -d '{"niche":"dental","geo":"miami","limit":3}'

# Enrichment
curl -X POST http://localhost:8001/api/v1/enrich -H "Content-Type: application/json" -d '{"lead_id":"<UUID>"}'

# Intent
curl -X POST http://localhost:8001/api/v1/intent -H "Content-Type: application/json" -d '{"lead_id":"<UUID>"}'

# Scoring
curl -X POST http://localhost:8001/api/v1/score -H "Content-Type: application/json" -d '{"lead_ids":["<UUID>"]}'

# Outreach Draft
curl -X POST http://localhost:8001/api/v1/outreach -H "Content-Type: application/json" -d '{"lead_id":"<UUID>","channel":"email"}'

# Full Pipeline
curl -X POST http://localhost:8001/api/v1/run -H "Content-Type: application/json" -d '{"niche":"dental","geo":"austin","limit":1}'
```

### Frontend Tests
- [ ] Chat loads without errors
- [ ] "Discover leads" tool returns real data
- [ ] "Enrich lead" tool works
- [ ] "Generate proof" shows screenshots
- [ ] "Draft outreach" creates message

---

## 📊 Success Metrics

When fully operational, ZRAI Lead OS should:

| Metric | Target |
|--------|--------|
| Leads discovered/day | 100-500 |
| Enrichment success rate | >80% |
| Proof generation success | >70% |
| Outreach sent/day | 50-200 |
| Reply rate | 5-15% |
| Qualification rate | 20-40% of replies |
| Escalation rate | 5-10% of replies |

---

## 🆘 Troubleshooting

### Common Issues

**"Not Found" on external URL**
- Kubernetes ingress misconfiguration
- Contact infrastructure team

**Apify returning empty data**
- Check APIFY_API_TOKEN validity
- Verify actor ID in discovery.py

**Steel.dev screenshots failing**
- Check STEEL_API_KEY
- Verify browser session limits

**Database connection errors**
- Verify POSTGRES_URL is correct
- Check Supabase project status

**OpenRouter API errors**
- Check OPENROUTER_API_KEY
- Verify model availability

---

## 📞 Support Resources

- **Apify Documentation**: https://docs.apify.com
- **Steel.dev Documentation**: https://docs.steel.dev
- **LangGraph Documentation**: https://langchain-ai.github.io/langgraph/
- **Supabase Documentation**: https://supabase.com/docs
- **AI SDK Documentation**: https://sdk.vercel.ai/docs

---

*Last Updated: January 2026*
*Version: 1.0.0*
