# Design Document: ZRAI Lead OS

## Overview

ZRAI Lead OS is a production-grade, multi-agent system built on LangGraph for stateful orchestration. The system discovers businesses with revenue leaks, generates proof-based outreach, qualifies prospects through AI conversations, and escalates only qualified leads to humans. The architecture is designed for modularity, zero-downtime updates, and production safety.

### Core Design Principles

1. **Config-Driven Everything**: No hard-coded niches, weights, or policies
2. **Stateful Graph Orchestration**: LangGraph with persistent checkpointers for resumable execution
3. **Modular Agents**: Independent specialist agents with clear boundaries
4. **Production Safety**: Retries, circuit breakers, idempotency, kill switches, audit logs
5. **Zero-Downtime Updates**: Hot-swappable nodes, versioned playbooks, config reloads
6. **Evidence-Based Outreach**: Every message backed by proof artifacts
7. **Reputation Protection**: Negative memory, opt-out enforcement, rate limiting
8. **Cost Control**: Daily budget guardrails for LLM, browser, and scraper usage

### Technology Stack

- **Orchestration**: LangGraph (stateful graph runtime with checkpointers)
- **Database**: Supabase (Postgres) - excellent for this scale, real-time subscriptions, built-in auth
- **Scraping**: Apify Actors (Meta Ads Library, Google Maps, website crawling)
- **Browser Automation**: Steel.dev (proof screenshots, interaction testing)
- **LLM**: Pluggable (OpenAI/Anthropic/Gemini) with model routing config
- **Object Storage**: S3-compatible (screenshots, artifacts)
- **Vector Store**: Pinecone (playbook retrieval, RAG)
- **Observability**: Structured logging + metrics (Prometheus/Grafana optional)

### Why This Stack

**Supabase/Postgres**: Fast enough for this workload (thousands of leads/day, not millions). Real-time features useful for dashboard. Mature, reliable, easy migrations.

**LangGraph**: Purpose-built for stateful multi-agent workflows. Checkpointers enable resume-anywhere. Subgraphs enable modularity. Production-proven.

**Apify**: Best-in-class for bulk scraping. Handles rate limits, proxies, anti-bot. Pay-per-use.

**Steel.dev**: Real browser automation for proof generation. Handles JavaScript, captures screenshots, interacts like humans.


## Architecture

### High-Level System Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        CONFIG LAYER                              │
│  ├─ niches.yaml (keywords, geo, weights)                        │
│  ├─ policies.yaml (rate limits, do_not_contact rules)           │
│  ├─ agents.yaml (LLM models, prompts, permissions)              │
│  └─ infrastructure.yaml (API keys, database, storage)           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   GRAPH ORCHESTRATOR (LangGraph)                 │
│  ├─ State Machine (nodes + edges + conditional routing)         │
│  ├─ Checkpointer (Supabase - resume anywhere)                   │
│  ├─ Parallelism Controller (concurrent lead processing)         │
│  ├─ Circuit Breakers (isolate failures)                         │
│  ├─ Kill Switches (global + per-module)                         │
│  └─ Idempotency Manager (prevent duplicate operations)          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      SPECIALIST AGENTS                           │
│  ├─ Discovery Agent (Apify bulk ingestion)                      │
│  ├─ Enrichment Agent (contact + context extraction)             │
│  ├─ Intent Agent (scoring + leak detection)                     │
│  ├─ Audit Agent (Steel.dev proof generation)                    │
│  ├─ Scoring Agent (weighted scoring + disqualification)         │
│  ├─ Outreach Agent (evidence-backed message generation)         │
│  ├─ Conversation Agent (AI qualification)                       │
│  ├─ Governance Agent (RBAC + rate limits + audit)               │
│  └─ Eval Agent (offline replay + A/B testing)                   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                         TOOL LAYER                               │
│  ├─ Apify Cloud (scraping actors)                               │
│  ├─ Steel.dev (browser automation)                              │
│  ├─ LLM Providers (OpenAI/Anthropic/Gemini)                     │
│  ├─ Supabase (database + real-time)                             │
│  ├─ S3 (object storage)                                          │
│  ├─ Pinecone (vector store for playbooks)                       │
│  └─ Email/SMS APIs (outreach channels)                          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      DATA LAYER                                  │
│  ├─ leads (canonical lead records)                              │
│  ├─ lead_state (orchestrator state + checkpoints)               │
│  ├─ enrichment_data (tech signals, contacts)                    │
│  ├─ scores (intent, leak, reactivation)                         │
│  ├─ proof_artifacts (screenshots, audit bullets)                │
│  ├─ outreach_queue (messages pending approval/send)             │
│  ├─ conversations (transcripts, entities)                       │
│  ├─ negative_signals (opt-outs, angry replies, bounces)         │
│  ├─ audit_log (append-only action log)                          │
│  ├─ usage_metrics (daily token/session/scraper counts)          │
│  └─ playbooks (versioned knowledge artifacts)                   │
└─────────────────────────────────────────────────────────────────┘
```

### Graph Flow (LangGraph State Machine)

```
START
  │
  ▼
[Discovery] ──────────────────┐
  │                            │
  ▼                            │
[Enrichment] ─────────────────┤
  │                            │
  ▼                            │
[Intent Detection] ───────────┤
  │                            │
  ▼                            │
[Scoring] ────────────────────┤
  │         │                  │
  │         ▼                  │
  │    [Disqualified] ────────┤
  │                            │
  ▼                            │
[Audit (Steel)] ──────────────┤ (Circuit Breaker)
  │                            │
  ▼                            │
[Outreach Generation] ────────┤
  │                            │
  ▼                            │
[Approval Queue] ─────────────┤
  │         │                  │
  │         ▼                  │
  │    [Human Review] ────────┤
  │                            │
  ▼                            │
[Send Outreach] ──────────────┤
  │                            │
  ▼                            │
[Conversation] ───────────────┤
  │         │                  │
  │         ▼                  │
  │    [Not Qualified] ───────┤
  │                            │
  ▼                            │
[Escalation] ─────────────────┤
  │                            │
  ▼                            │
[Human Close] ────────────────┤
  │                            │
  ▼                            ▼
END                      [Retry/Resume]
```


## Components and Interfaces

### 1. Graph Orchestrator

**Purpose**: Stateful workflow engine managing multi-agent execution with fault tolerance.

**Key Responsibilities**:
- Load and execute graph definition from config
- Persist lead state at each node transition
- Handle retries with exponential backoff
- Activate circuit breakers on repeated failures
- Enforce idempotency for external writes
- Support concurrent lead processing
- Provide CLI commands (run_daily, replay_run, resume_failed, dry_run)

**State Schema**:
```typescript
interface LeadState {
  lead_id: string;
  current_stage: string;
  last_node: string;
  last_error: string | null;
  retry_count: number;
  next_run_at: timestamp;
  locks: string[];
  metadata: Record<string, any>;
}
```

**Checkpointer Integration**:
- Uses Supabase as checkpoint store
- Saves state after each node execution
- Enables resume from any point on failure
- Supports parallel execution with row-level locking

**Circuit Breaker Logic**:
```typescript
interface CircuitBreaker {
  node_name: string;
  failure_count: number;
  failure_threshold: number;
  timeout_seconds: number;
  state: 'CLOSED' | 'OPEN' | 'HALF_OPEN';
  last_failure_at: timestamp;
}
```

### 2. Discovery Agent

**Purpose**: Bulk ingestion of business data from multiple sources.

**Inputs**:
- niche_keywords: string[]
- geo: { city?, state?, country }
- languages: string[]
- platform_toggles: { meta_ads, google_maps, websites, social }

**Apify Actors Used**:
- `apify/meta-ads-library-scraper`
- `apify/google-maps-scraper`
- `apify/website-content-crawler`
- `apify/facebook-pages-scraper`

**Output Schema** (Canonical Lead):
```typescript
interface CanonicalLead {
  lead_id: string;
  business_name: string;
  category: string;
  location: string;
  geo_tags: string[];
  website: string | null;
  landing_page_url: string | null;
  phone: string | null;
  emails_found: string[];
  facebook_page: string | null;
  instagram: string | null;
  ads_active: boolean;
  ad_start_date: timestamp | null;
  ad_last_seen: timestamp | null;
  cta_type: 'CALL' | 'FORM' | 'BOOK' | 'OTHER' | null;
  lead_form_detected: boolean;
  created_at: timestamp;
  updated_at: timestamp;
}
```

**Deduplication Strategy**:
- Hash business_name + location + website
- Check for existing leads before insert
- Merge data if duplicate found (prefer newer ad data)

### 3. Enrichment Agent

**Purpose**: Extract contact information and technical context.

**Inputs**: CanonicalLead

**Enrichment Tasks**:
1. Tech signal extraction (booking provider, CRM, chat widget, form tool)
2. Decision-maker extraction (owner name, team page, LinkedIn)
3. Contact normalization (phone format, email validation)
4. Domain validation (MX records, disposable email detection)

**Output Schema**:
```typescript
interface EnrichmentData {
  lead_id: string;
  enrichment_confidence: number; // 0-1
  booking_provider: string | null;
  crm_hint: string | null;
  chat_widget: string | null;
  form_tool: string | null;
  decision_maker_name: string | null;
  decision_maker_linkedin: string | null;
  contact_quality_score: number; // 0-100
  normalized_phone: string | null;
  validated_emails: string[];
}
```

**Contact Quality Scoring**:
```
score = 0
if has_validated_email: score += 40
if has_normalized_phone: score += 30
if has_decision_maker: score += 20
if has_linkedin: score += 10
```

### 4. Intent Agent

**Purpose**: Compute intent and revenue leak scores.

**Inputs**: CanonicalLead + EnrichmentData

**Scoring Algorithms**:

**Intent Score** (0-100):
```
intent_score = 0
if ads_active: intent_score += 30
if cta_type == 'CALL': intent_score += 20
if high_ticket_category: intent_score += 25
if multiple_ad_creatives: intent_score += 15
if recent_ad_start (< 30 days): intent_score += 10
```

**Leak Score** (0-100):
```
leak_score = 0
if cta_type == 'CALL' and no_booking_system: leak_score += 30
if no_chat_widget: leak_score += 15
if after_hours_gap: leak_score += 25
if form_friction (>5 fields): leak_score += 20
if slow_website (>3s load): leak_score += 10
```

**Reactivation Fit** (0-100):
```
reactivation_fit = 0
if long_consideration_cycle: reactivation_fit += 40
if follow_up_failure_cues: reactivation_fit += 30
if high_ticket: reactivation_fit += 20
if seasonal_business: reactivation_fit += 10
```

**Speed-to-Lead Risk**:
```
if cta_type == 'CALL' and no_after_hours: risk = 'HIGH'
elif form_only and no_auto_response: risk = 'MED'
else: risk = 'LOW'
```

**Review Mining**:
- Extract reviews from Google Maps data
- Search for phrases: "no response", "never called back", "hard to reach", "couldn't get through"
- Store evidence snippets with source URLs

**Output Schema**:
```typescript
interface IntentData {
  lead_id: string;
  intent_score: number;
  leak_score: number;
  reactivation_fit: number;
  why_this_lead: string;
  speed_to_lead_risk: 'LOW' | 'MED' | 'HIGH';
  review_evidence: Array<{
    snippet: string;
    source_url: string;
    sentiment: 'negative' | 'neutral';
  }>;
}
```


### 5. Audit Agent (Steel.dev)

**Purpose**: Generate proof artifacts through browser automation.

**Trigger Conditions**:
- Lead score > configured threshold (e.g., 70)
- OR lead_tier == 'A'
- AND daily_steel_budget not exceeded

**Steel Task Workflow**:
1. Launch browser session
2. Navigate to landing_page_url
3. Wait for page load (timeout: 10s)
4. Scroll to reveal content
5. Click CTA buttons to reveal forms/phone
6. Extract visible elements
7. Capture screenshots
8. Save to S3 and link in DB

**Extraction Logic**:
```typescript
interface AuditExtraction {
  phone_visibility: 'above_fold' | 'below_fold' | 'hidden' | 'none';
  form_field_count: number;
  booking_link: string | null;
  business_hours: string | null;
  after_hours_capture: boolean;
  cta_buttons: string[];
  load_time_ms: number;
}
```

**Screenshot Capture**:
- Hero section (viewport screenshot)
- CTA/form/phone section (element screenshot)
- Save as PNG to S3: `s3://zrai-artifacts/{lead_id}/hero.png`

**Proof Pack Generation**:
```typescript
interface ProofPack {
  lead_id: string;
  hero_screenshot_url: string;
  cta_screenshot_url: string;
  audit_bullets: [
    {
      type: 'leak';
      evidence: string; // "Phone number hidden below fold"
    },
    {
      type: 'fix';
      specific: string; // "Move phone to hero section"
    },
    {
      type: 'upside';
      estimate: string; // "Recover 15-20% of missed calls"
    }
  ];
  generated_at: timestamp;
}
```

**Circuit Breaker for Steel**:
- If Steel fails 3 times in 5 minutes, open circuit
- Route leads around Audit node
- Continue pipeline without proof artifacts
- Alert operator

### 6. Scoring Agent

**Purpose**: Apply weighted scoring and disqualification rules.

**Weighted Scoring Formula**:
```
final_score = 
  w1 * ad_activity_score +
  w2 * intent_score +
  w3 * leak_score +
  w4 * reactivation_fit +
  w5 * contact_quality_score +
  w6 * business_size_score
```

**Default Weights** (configurable per niche):
```yaml
weights:
  ad_activity: 0.20
  intent: 0.25
  leak: 0.30
  reactivation: 0.10
  contact_quality: 0.10
  business_size: 0.05
```

**Disqualification Rules**:
```typescript
interface DisqualificationRule {
  rule_name: string;
  condition: (lead: Lead) => boolean;
  reason: string;
}

const DO_NOT_CONTACT_RULES = [
  {
    rule_name: 'too_small',
    condition: (lead) => lead.employee_count < 2,
    reason: 'Owner-only business'
  },
  {
    rule_name: 'no_ads_history',
    condition: (lead) => !lead.ads_active && !lead.ad_start_date,
    reason: 'No advertising spend detected'
  },
  {
    rule_name: 'emergency_only',
    condition: (lead) => lead.category.includes('emergency'),
    reason: 'Emergency-only service'
  },
  {
    rule_name: 'toxic_reviews',
    condition: (lead) => lead.review_sentiment_avg < -0.5,
    reason: 'Toxic review pattern'
  },
  {
    rule_name: 'no_contact_path',
    condition: (lead) => !lead.phone && lead.validated_emails.length === 0,
    reason: 'No valid contact method'
  }
];
```

**Lead Tier Assignment**:
```
if final_score >= 80: tier = 'A' (Pitch now)
elif final_score >= 60: tier = 'B' (Soft pitch)
else: tier = 'C' (Skip)
```

**Output Schema**:
```typescript
interface ScoringResult {
  lead_id: string;
  final_score: number;
  score_breakdown: {
    ad_activity: number;
    intent: number;
    leak: number;
    reactivation: number;
    contact_quality: number;
    business_size: number;
  };
  lead_tier: 'A' | 'B' | 'C';
  do_not_contact: boolean;
  do_not_contact_reason: string | null;
}
```

### 7. Outreach Agent

**Purpose**: Generate evidence-backed outreach messages.

**Inputs**:
- ProofPack
- ScoringResult
- EnrichmentData
- Niche config (tone, offer)

**Message Structure** (enforced):
1. **Observation** (evidence from proof pack)
2. **Impact** (conservative money/loss framing)
3. **Offer** (done-for-you solution)
4. **CTA** (single action: book call / reply YES)

**Template Example**:
```
Hi {{decision_maker_name}},

I was reviewing {{business_name}}'s lead capture and noticed your phone number 
is hidden below the fold on your landing page [screenshot attached].

Based on similar {{category}} businesses, this typically means 15-20% of 
interested callers give up before finding your number—especially after hours.

We help businesses like yours recover this lost revenue by optimizing lead 
capture without changing your ad spend.

Worth a 15-minute conversation? Reply YES and I'll send a calendar link.

[Opt-out: Reply STOP to unsubscribe]
```

**A/B Variant Generation**:
- Generate 2 variants per lead
- Vary: opening line, impact framing, CTA wording
- Track performance in eval harness

**Channel Payloads**:
```typescript
interface OutreachPayload {
  lead_id: string;
  channel: 'email' | 'dm' | 'form';
  variant: 'A' | 'B';
  subject: string;
  body: string;
  attachments: string[]; // S3 URLs
  personalization: {
    decision_maker_name: string;
    business_name: string;
    category: string;
    evidence: string;
  };
  requires_approval: boolean;
}
```

**Approval Queue**:
- By default, all messages queued for human review
- If `auto_send_tier_a: true` in config, tier A messages auto-send
- Store in `outreach_queue` table with status: 'pending' | 'approved' | 'sent' | 'rejected'


### 8. Conversation Agent

**Purpose**: AI-driven qualification conversations with strict escalation policy.

**Qualification Framework** (BANT):
- **Budget**: Confirmed budget range or willingness to invest
- **Authority**: Decision-maker or can influence decision
- **Need**: Pain point acknowledged
- **Timeline**: Timeframe for implementation

**Conversation Flow**:
```
1. Acknowledge reply
2. Ask discovery questions
3. Confirm pain point
4. Extract BANT criteria
5. If qualified → escalate
6. If not qualified → nurture or disqualify
```

**Discovery Questions** (examples):
- "How do you currently handle missed calls?"
- "What percentage of leads do you think get contacted within 5 minutes?"
- "Do you have a system for following up on leads that didn't respond?"

**Hard Stop Rules**:
```typescript
const CONVERSATION_GUARDRAILS = {
  no_pricing_negotiation: true,
  max_price_range: { min: 500, max: 5000 },
  no_unverifiable_claims: true,
  no_guarantees: true,
  escalate_on_objection: ['price', 'competitor', 'timing']
};
```

**Entity Extraction**:
```typescript
interface ConversationEntities {
  budget_range: { min: number, max: number } | null;
  role: string | null;
  timeline: string | null;
  objections: string[];
  pain_confirmed: boolean;
  interest_level: 'high' | 'medium' | 'low';
}
```

**Escalation Criteria**:
```
if (
  pain_confirmed &&
  budget_range !== null &&
  (role === 'owner' || role === 'decision_maker') &&
  timeline !== null
) {
  escalate_to_human();
}
```

**Output Schema**:
```typescript
interface ConversationRecord {
  lead_id: string;
  conversation_id: string;
  transcript: Array<{
    role: 'ai' | 'prospect';
    message: string;
    timestamp: timestamp;
  }>;
  entities: ConversationEntities;
  objection_summary: string | null;
  suggested_close_angle: string | null;
  escalated: boolean;
  escalated_at: timestamp | null;
}
```

### 9. Governance Agent

**Purpose**: Enforce RBAC, rate limits, audit logging, and compliance.

**RBAC Matrix**:
```yaml
permissions:
  discovery_agent:
    - read_config
    - write_leads
    - call_apify
  
  enrichment_agent:
    - read_leads
    - write_enrichment
    - call_external_apis
  
  audit_agent:
    - read_leads
    - write_proof_artifacts
    - call_steel
    - write_s3
  
  outreach_agent:
    - read_leads
    - read_proof_artifacts
    - write_outreach_queue
    - call_llm
  
  conversation_agent:
    - read_outreach_queue
    - write_conversations
    - call_llm
    - send_messages (conditional)
  
  governance_agent:
    - read_all
    - write_audit_log
    - enforce_rate_limits
    - manage_kill_switches
```

**Rate Limit Configuration**:
```yaml
rate_limits:
  per_domain:
    max_emails_per_day: 5
    max_dms_per_day: 2
  
  per_channel:
    email:
      max_per_hour: 50
      max_per_day: 200
    dm:
      max_per_hour: 20
      max_per_day: 50
  
  cool_down:
    after_bounce: 7_days
    after_spam_complaint: 30_days
    after_angry_reply: 14_days
```

**Audit Log Schema**:
```typescript
interface AuditLogEntry {
  log_id: string;
  actor: string; // agent name
  action: string; // 'send_email', 'write_db', 'call_api'
  resource: string; // lead_id, email, etc.
  timestamp: timestamp;
  payload_hash: string;
  idempotency_key: string;
  result: 'success' | 'failure';
  error_message: string | null;
}
```

**Compliance Enforcement**:
```typescript
interface ComplianceCheck {
  lead_id: string;
  region: string; // 'US', 'EU', 'CA'
  consent_required: boolean;
  consent_obtained: boolean;
  opt_out_honored: boolean;
  data_retention_days: number;
}
```

### 10. Eval Agent

**Purpose**: Offline replay and A/B testing for quality validation.

**Golden Dataset Structure**:
```typescript
interface GoldenDatasetEntry {
  lead_id: string;
  input_data: CanonicalLead;
  expected_score: number;
  expected_tier: 'A' | 'B' | 'C';
  expected_outreach_quality: 'good' | 'bad';
  known_outcome: 'replied' | 'meeting' | 'closed' | 'no_response';
  notes: string;
}
```

**Offline Replay**:
1. Load golden dataset
2. Run new scoring/prompt version on historical leads
3. Compare metrics to baseline
4. Generate diff report

**Metrics Comparison**:
```typescript
interface ReplayMetrics {
  baseline_version: string;
  new_version: string;
  score_correlation: number; // Pearson correlation
  tier_agreement: number; // % agreement
  outreach_quality_delta: number; // quality score change
  false_positive_rate_delta: number;
}
```

**A/B Testing Framework**:
```yaml
ab_test:
  name: "outreach_variant_test"
  variants:
    - name: "control"
      weight: 0.5
      config: "outreach_v1.yaml"
    
    - name: "treatment"
      weight: 0.5
      config: "outreach_v2.yaml"
  
  metrics:
    - reply_rate
    - meeting_rate
    - negative_signal_rate
  
  guardrails:
    min_reply_rate: 0.05
    max_negative_signal_rate: 0.02
  
  rollback_trigger:
    metric: "negative_signal_rate"
    threshold: 0.03
```


## Data Models

### Database Schema (Supabase/Postgres)

#### leads table
```sql
CREATE TABLE leads (
  lead_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  business_name TEXT NOT NULL,
  category TEXT,
  location TEXT,
  geo_tags TEXT[],
  website TEXT,
  landing_page_url TEXT,
  phone TEXT,
  emails_found TEXT[],
  facebook_page TEXT,
  instagram TEXT,
  ads_active BOOLEAN DEFAULT false,
  ad_start_date TIMESTAMP,
  ad_last_seen TIMESTAMP,
  cta_type TEXT CHECK (cta_type IN ('CALL', 'FORM', 'BOOK', 'OTHER')),
  lead_form_detected BOOLEAN DEFAULT false,
  lead_lifecycle_state TEXT DEFAULT 'NEW' CHECK (lead_lifecycle_state IN 
    ('NEW', 'STALE', 'REACTIVATABLE', 'ENGAGED', 'QUALIFIED', 'CLOSED_WON', 'CLOSED_LOST')),
  last_contacted_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW(),
  
  -- Indexes
  INDEX idx_leads_lifecycle (lead_lifecycle_state),
  INDEX idx_leads_last_contacted (last_contacted_at),
  INDEX idx_leads_category (category),
  INDEX idx_leads_geo (geo_tags) USING GIN
);
```

#### lead_state table (LangGraph checkpointer)
```sql
CREATE TABLE lead_state (
  lead_id UUID PRIMARY KEY REFERENCES leads(lead_id),
  current_stage TEXT NOT NULL,
  last_node TEXT NOT NULL,
  last_error TEXT,
  retry_count INTEGER DEFAULT 0,
  next_run_at TIMESTAMP,
  locks TEXT[],
  metadata JSONB,
  updated_at TIMESTAMP DEFAULT NOW(),
  
  INDEX idx_lead_state_next_run (next_run_at),
  INDEX idx_lead_state_stage (current_stage)
);
```

#### enrichment_data table
```sql
CREATE TABLE enrichment_data (
  lead_id UUID PRIMARY KEY REFERENCES leads(lead_id),
  enrichment_confidence DECIMAL(3,2) CHECK (enrichment_confidence BETWEEN 0 AND 1),
  booking_provider TEXT,
  crm_hint TEXT,
  chat_widget TEXT,
  form_tool TEXT,
  decision_maker_name TEXT,
  decision_maker_linkedin TEXT,
  contact_quality_score INTEGER CHECK (contact_quality_score BETWEEN 0 AND 100),
  normalized_phone TEXT,
  validated_emails TEXT[],
  created_at TIMESTAMP DEFAULT NOW()
);
```

#### intent_data table
```sql
CREATE TABLE intent_data (
  lead_id UUID PRIMARY KEY REFERENCES leads(lead_id),
  intent_score INTEGER CHECK (intent_score BETWEEN 0 AND 100),
  leak_score INTEGER CHECK (leak_score BETWEEN 0 AND 100),
  reactivation_fit INTEGER CHECK (reactivation_fit BETWEEN 0 AND 100),
  why_this_lead TEXT,
  speed_to_lead_risk TEXT CHECK (speed_to_lead_risk IN ('LOW', 'MED', 'HIGH')),
  review_evidence JSONB,
  created_at TIMESTAMP DEFAULT NOW()
);
```

#### proof_artifacts table
```sql
CREATE TABLE proof_artifacts (
  lead_id UUID PRIMARY KEY REFERENCES leads(lead_id),
  hero_screenshot_url TEXT,
  cta_screenshot_url TEXT,
  audit_bullets JSONB,
  extraction_data JSONB,
  generated_at TIMESTAMP DEFAULT NOW()
);
```

#### scoring_results table
```sql
CREATE TABLE scoring_results (
  lead_id UUID PRIMARY KEY REFERENCES leads(lead_id),
  final_score INTEGER CHECK (final_score BETWEEN 0 AND 100),
  score_breakdown JSONB,
  lead_tier TEXT CHECK (lead_tier IN ('A', 'B', 'C')),
  do_not_contact BOOLEAN DEFAULT false,
  do_not_contact_reason TEXT,
  created_at TIMESTAMP DEFAULT NOW(),
  
  INDEX idx_scoring_tier (lead_tier),
  INDEX idx_scoring_score (final_score DESC)
);
```

#### outreach_queue table
```sql
CREATE TABLE outreach_queue (
  outreach_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  lead_id UUID REFERENCES leads(lead_id),
  channel TEXT CHECK (channel IN ('email', 'dm', 'form')),
  variant TEXT CHECK (variant IN ('A', 'B')),
  subject TEXT,
  body TEXT,
  attachments TEXT[],
  personalization JSONB,
  status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'sent', 'rejected')),
  requires_approval BOOLEAN DEFAULT true,
  sent_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT NOW(),
  
  INDEX idx_outreach_status (status),
  INDEX idx_outreach_lead (lead_id)
);
```

#### conversations table
```sql
CREATE TABLE conversations (
  conversation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  lead_id UUID REFERENCES leads(lead_id),
  transcript JSONB,
  entities JSONB,
  objection_summary TEXT,
  suggested_close_angle TEXT,
  escalated BOOLEAN DEFAULT false,
  escalated_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW(),
  
  INDEX idx_conversations_lead (lead_id),
  INDEX idx_conversations_escalated (escalated)
);
```

#### negative_signals table
```sql
CREATE TABLE negative_signals (
  signal_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  lead_id UUID REFERENCES leads(lead_id),
  signal_type TEXT CHECK (signal_type IN ('opt_out', 'angry_reply', 'bounce', 'spam_complaint')),
  channel TEXT,
  sentiment_score DECIMAL(3,2),
  message_content TEXT,
  created_at TIMESTAMP DEFAULT NOW(),
  
  INDEX idx_negative_signals_lead (lead_id),
  INDEX idx_negative_signals_type (signal_type)
);
```

#### do_not_contact table
```sql
CREATE TABLE do_not_contact (
  lead_id UUID PRIMARY KEY REFERENCES leads(lead_id),
  reason TEXT NOT NULL,
  added_at TIMESTAMP DEFAULT NOW(),
  expires_at TIMESTAMP,
  
  INDEX idx_dnc_expires (expires_at)
);
```

#### audit_log table
```sql
CREATE TABLE audit_log (
  log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  actor TEXT NOT NULL,
  action TEXT NOT NULL,
  resource TEXT,
  timestamp TIMESTAMP DEFAULT NOW(),
  payload_hash TEXT,
  idempotency_key TEXT UNIQUE,
  result TEXT CHECK (result IN ('success', 'failure')),
  error_message TEXT,
  
  INDEX idx_audit_timestamp (timestamp DESC),
  INDEX idx_audit_actor (actor),
  INDEX idx_audit_idempotency (idempotency_key)
);
```

#### usage_metrics table
```sql
CREATE TABLE usage_metrics (
  metric_date DATE PRIMARY KEY,
  llm_tokens_used BIGINT DEFAULT 0,
  browser_sessions_used INTEGER DEFAULT 0,
  scraper_runs_used INTEGER DEFAULT 0,
  llm_cost_usd DECIMAL(10,2) DEFAULT 0,
  browser_cost_usd DECIMAL(10,2) DEFAULT 0,
  scraper_cost_usd DECIMAL(10,2) DEFAULT 0,
  updated_at TIMESTAMP DEFAULT NOW()
);
```

#### playbooks table
```sql
CREATE TABLE playbooks (
  playbook_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  version TEXT NOT NULL,
  niche TEXT,
  tier TEXT,
  channel TEXT,
  content TEXT,
  embedding VECTOR(1536), -- for Pinecone/pgvector
  created_at TIMESTAMP DEFAULT NOW(),
  
  UNIQUE (name, version),
  INDEX idx_playbooks_niche (niche),
  INDEX idx_playbooks_version (version)
);
```

#### circuit_breakers table
```sql
CREATE TABLE circuit_breakers (
  node_name TEXT PRIMARY KEY,
  failure_count INTEGER DEFAULT 0,
  failure_threshold INTEGER DEFAULT 3,
  timeout_seconds INTEGER DEFAULT 300,
  state TEXT DEFAULT 'CLOSED' CHECK (state IN ('CLOSED', 'OPEN', 'HALF_OPEN')),
  last_failure_at TIMESTAMP,
  updated_at TIMESTAMP DEFAULT NOW()
);
```


## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: State Persistence Completeness

*For any* lead being processed through the graph, persisting the lead state should result in all required fields (lead_id, current_stage, last_node, last_error, retry_count, next_run_at, locks) being stored and retrievable.

**Validates: Requirements 1.2, 1.8, 20.3**

### Property 2: Exponential Backoff Retry Pattern

*For any* node failure, the retry delays should follow an exponential backoff pattern where each subsequent retry delay is exponentially larger than the previous delay, up to the configured maximum attempts.

**Validates: Requirements 1.3, 20.1**

### Property 3: Circuit Breaker Activation

*For any* component that fails repeatedly (exceeding the failure threshold), the circuit breaker should transition to OPEN state and subsequent requests should be routed around the failing component.

**Validates: Requirements 1.4, 20.2**

### Property 4: Idempotency Guarantee

*For any* external write operation, executing it multiple times with the same idempotency key should produce the same final state as executing it once (no duplicate side effects).

**Validates: Requirements 1.5**

### Property 5: Concurrent Execution Limits

*For any* batch of leads being processed, the number of concurrently executing leads should never exceed the configured parallelism limit.

**Validates: Requirements 1.7**

### Property 6: Replay Determinism

*For any* historical execution, replaying it with the same inputs and configuration should produce equivalent results (same scores, same decisions, same outcomes).

**Validates: Requirements 2.2**

### Property 7: Failed Execution Resumption

*For any* timestamp, running resume_failed should identify all leads that failed after that timestamp and resume them from their last successful checkpoint.

**Validates: Requirements 2.3**

### Property 8: Dry Run Side Effect Prevention

*For any* dry run execution, no external writes (database inserts, API calls, emails sent) should occur, and all operations should be simulated only.

**Validates: Requirements 2.4**

### Property 9: CLI Output Completeness

*For any* CLI command execution, the output should include a summary with success count, failure count, and error details for all failures.

**Validates: Requirements 2.5**

### Property 10: Canonical Lead Schema Compliance

*For any* raw data collected by the Discovery Agent, the resulting Canonical_Lead record should conform to the defined schema with all required fields populated (lead_id, business_name, created_at, updated_at).

**Validates: Requirements 3.7, 3.8, 18.2**

### Property 11: Extraction Field Completeness

*For any* data source (Meta Ads, Google Maps, websites), all fields specified for that source should be extracted and stored in the corresponding data structure.

**Validates: Requirements 3.2, 3.4, 6.4**

### Property 12: Contact Normalization Consistency

*For any* extracted contact (phone or email), the normalized format should be consistent (same input always produces same normalized output) and valid according to format rules.

**Validates: Requirements 4.3**

### Property 13: Score Range Validity

*For any* computed score (intent_score, leak_score, reactivation_fit, enrichment_confidence, contact_quality_score, final_score), the value should be within the defined valid range (0-1 for confidence, 0-100 for others).

**Validates: Requirements 4.4, 4.5, 5.1, 5.2, 5.3**

### Property 14: Risk Classification Validity

*For any* lead processed by the Intent Agent, the speed_to_lead_risk classification should be one of the valid values: LOW, MED, or HIGH.

**Validates: Requirements 5.5**

### Property 15: Lead Tier Assignment Validity

*For any* lead processed by the Scoring Agent, the lead_tier should be one of the valid values: A, B, or C.

**Validates: Requirements 7.5**

### Property 16: Tier C Exclusion

*For any* lead assigned tier C, it should not appear in any outreach queue.

**Validates: Requirements 7.6**

### Property 17: Disqualification Reason Recording

*For any* lead that triggers a do_not_contact rule, the do_not_contact_reason field should be populated with a non-empty explanation.

**Validates: Requirements 7.4**

### Property 18: Weighted Scoring Formula Correctness

*For any* lead with computed component scores, the final_score should equal the weighted sum: w1×ad_activity + w2×intent + w3×leak + w4×reactivation + w5×contact_quality + w6×business_size.

**Validates: Requirements 7.1**

### Property 19: Proof Pack Structure Completeness

*For any* completed audit, the generated Proof_Pack should contain exactly 3 audit_bullets, each with type (leak/fix/upside) and corresponding content fields.

**Validates: Requirements 6.7**

### Property 20: Screenshot Artifact Round Trip

*For any* captured screenshot, saving it to object storage and then retrieving it via the stored URL should return the same image data.

**Validates: Requirements 6.6**

### Property 21: Outreach Message Structure Compliance

*For any* generated outreach message, it should contain all required sections in order: observation (evidence), impact (money/loss framing), offer (done-for-you), and single CTA.

**Validates: Requirements 8.3**

### Property 22: Email Opt-Out Inclusion

*For any* outreach message with channel='email', the message body should contain an opt-out line.

**Validates: Requirements 8.4**

### Property 23: A/B Variant Generation

*For any* lead requiring outreach, exactly 2 message variants (A and B) should be generated.

**Validates: Requirements 8.5**

### Property 24: Approval Queue Default Behavior

*For any* generated outreach message where auto_send is not enabled for that tier, the message should be added to the outreach_queue with status='pending' and requires_approval=true.

**Validates: Requirements 8.7**

### Property 25: BANT Qualification Completeness

*For any* lead escalated to human review, the conversation record should have all BANT criteria confirmed (budget_range not null, authority confirmed, need/pain_confirmed=true, timeline not null).

**Validates: Requirements 9.2, 10.1**

### Property 26: Conversation Transcript Persistence

*For any* completed conversation, the full transcript should be stored with all messages, roles, and timestamps.

**Validates: Requirements 9.3**

### Property 27: Escalation Context Completeness

*For any* escalated lead, the escalation package should include conversation transcript, extracted entities, objection summary, suggested close angle, and the original Proof_Pack.

**Validates: Requirements 10.2, 10.3**

### Property 28: Human Ownership Transfer

*For any* lead where a human accepts escalation, the lead should be marked as human_owned=true and no further AI conversation attempts should occur.

**Validates: Requirements 10.4**

### Property 29: Permission Verification

*For any* action attempted by an agent, the Governance Layer should verify that the agent has the required permission before allowing the action to proceed.

**Validates: Requirements 11.1**

### Property 30: Unauthorized Action Blocking

*For any* action attempted without proper permission, the action should be blocked and an audit log entry should be created with result='failure' and error_message indicating permission denial.

**Validates: Requirements 11.3**

### Property 31: Rate Limit Enforcement

*For any* outreach attempt, if the rate limit (per-domain, per-channel, or per-day) has been reached, the attempt should be blocked and rescheduled.

**Validates: Requirements 12.1**

### Property 32: Negative Signal Cool-Down Activation

*For any* detected negative signal (opt-out, angry reply, bounce, spam complaint), a cool-down period should be activated preventing further contact to that lead or domain.

**Validates: Requirements 12.2, 22.5, 22.6**

### Property 33: Negative Signal Recording Completeness

*For any* detected negative signal, a record should be created with all required fields: lead_id, signal_type, channel, timestamp, and sentiment_score (if applicable).

**Validates: Requirements 22.4, 22.7, 22.8**

### Property 34: Audit Log Completeness

*For any* external write operation, an audit log entry should be created with all required fields: actor, action, resource, timestamp, payload_hash, idempotency_key, and result.

**Validates: Requirements 13.1**

### Property 35: Audit Log Immutability

*For any* audit log entry, once written, it should never be modified or deleted (append-only guarantee).

**Validates: Requirements 13.2**

### Property 36: Secret Redaction

*For any* log entry, secret values (API keys, passwords, tokens) should never appear in the log output.

**Validates: Requirements 13.4, 19.2**

### Property 37: Execution Trace Completeness

*For any* lead flowing through the graph, the execution trace should include all required metrics: node_latency, tool_errors, retry_count, llm_tokens, llm_cost, and success_failure_reasons.

**Validates: Requirements 14.1**

### Property 38: Daily Metrics Computation

*For any* completed daily execution, all required metrics should be computed and stored: reply_rate, meeting_rate, cost_per_qualified_meeting, false_positive_rate, and human_override_rate.

**Validates: Requirements 14.2**

### Property 39: Playbook Retrieval Relevance

*For any* agent request for guidance, the retrieved playbook snippets should match the specified filters (niche, tier, channel).

**Validates: Requirements 16.1**

### Property 40: Playbook Versioning

*For any* playbook update, a new version should be created with a unique version identifier and linked to the run_id for reproducibility.

**Validates: Requirements 16.2**

### Property 41: Configuration Hot Reload

*For any* configuration file change, the system should reload the configuration without requiring a restart or code deployment.

**Validates: Requirements 17.2**

### Property 42: Configuration Validation

*For any* invalid configuration (missing required fields, invalid values, type mismatches), the system should fail fast with a clear validation error message.

**Validates: Requirements 17.3, 19.3**

### Property 43: Lead Lifecycle State Machine Validity

*For any* lead state transition, the transition should be valid according to the state machine: NEW → STALE → REACTIVATABLE → ENGAGED → QUALIFIED → CLOSED_WON/CLOSED_LOST.

**Validates: Requirements 21.1, 21.3, 21.4, 21.7, 21.8, 21.9**

### Property 44: Contact Timestamp Recording

*For any* contact event (email sent, DM sent, form submitted), the last_contacted_at timestamp should be updated to the current time.

**Validates: Requirements 21.2**

### Property 45: Stale Lead Contact Prevention

*For any* lead in STALE state, no outreach attempts should occur until the lead transitions to REACTIVATABLE state.

**Validates: Requirements 21.6**

### Property 46: Contact Eligibility Calculation

*For any* lead, the days_since_last_contact should be calculated as the difference between current time and last_contacted_at, and contact should only be allowed if days_since_last_contact >= minimum_wait_days.

**Validates: Requirements 21.5**

### Property 47: Opt-Out Detection and Enforcement

*For any* reply containing opt-out language (STOP, UNSUBSCRIBE, etc.), the lead should be added to the do_not_contact list and all future outreach attempts should be blocked.

**Validates: Requirements 22.1, 22.2, 22.9**

### Property 48: Budget Limit Enforcement

*For any* resource request (LLM tokens, browser sessions, scraper runs), if the daily limit has been reached, the request should be blocked and a budget_exceeded event should be logged.

**Validates: Requirements 23.2, 23.3, 23.4, 23.5, 23.6, 23.7**

### Property 49: Budget Alert Notification

*For any* budget limit reached event, an alert notification should be sent to the operator.

**Validates: Requirements 23.8**

### Property 50: Daily Usage Counter Reset

*For any* daily reset time occurrence, all usage counters (llm_tokens_used, browser_sessions_used, scraper_runs_used) should be reset to zero.

**Validates: Requirements 23.9**


## Error Handling

### Error Classification

**Transient Errors** (retry with backoff):
- Network timeouts
- API rate limits
- Temporary service unavailability
- Database connection failures

**Permanent Errors** (fail fast, no retry):
- Invalid configuration
- Missing secrets
- Schema validation failures
- Permission denied

**Partial Failures** (isolate and continue):
- Single lead processing failure
- Circuit breaker activation
- Optional component failure (e.g., Steel.dev)

### Retry Strategy

**Exponential Backoff Formula**:
```
delay = base_delay * (2 ^ retry_count) + random_jitter
max_delay = min(delay, max_backoff_seconds)
```

**Default Configuration**:
```yaml
retry_config:
  base_delay_ms: 1000
  max_attempts: 3
  max_backoff_seconds: 60
  jitter_range_ms: [0, 1000]
```

**Per-Component Overrides**:
```yaml
component_retry:
  apify:
    max_attempts: 5
    base_delay_ms: 2000
  steel:
    max_attempts: 2
    base_delay_ms: 5000
  llm:
    max_attempts: 3
    base_delay_ms: 1000
```

### Circuit Breaker Pattern

**States**:
- **CLOSED**: Normal operation, requests pass through
- **OPEN**: Component failing, requests routed around
- **HALF_OPEN**: Testing if component recovered

**Transition Logic**:
```
CLOSED → OPEN: failure_count >= failure_threshold
OPEN → HALF_OPEN: timeout_seconds elapsed since last_failure
HALF_OPEN → CLOSED: successful request
HALF_OPEN → OPEN: failed request
```

**Configuration**:
```yaml
circuit_breakers:
  steel_audit:
    failure_threshold: 3
    timeout_seconds: 300
    half_open_max_requests: 1
  
  apify_discovery:
    failure_threshold: 5
    timeout_seconds: 600
    half_open_max_requests: 3
```

### Graceful Degradation

**Steel.dev Failure**:
- Circuit breaker opens
- Leads continue through pipeline without proof artifacts
- Outreach messages generated without screenshots
- Alert sent to operator

**LLM Failure**:
- Retry with exponential backoff
- If all retries fail, use fallback template-based generation
- Mark outreach as "requires_human_review"

**Apify Failure**:
- Retry with longer backoff
- If persistent, pause discovery for that source
- Continue with other sources
- Alert sent to operator

### Error Logging

**Structured Error Format**:
```typescript
interface ErrorLog {
  error_id: string;
  timestamp: timestamp;
  component: string;
  error_type: 'transient' | 'permanent' | 'partial';
  error_code: string;
  error_message: string;
  stack_trace: string;
  context: {
    lead_id?: string;
    node_name?: string;
    retry_count?: number;
  };
  resolution: 'retried' | 'failed' | 'degraded';
}
```

### Kill Switch Implementation

**Global Kill Switch**:
- Environment variable: `KILL_SWITCH_ENABLED=true`
- Checked at start of each graph execution
- Gracefully completes current leads, prevents new starts

**Per-Module Kill Switches**:
```yaml
kill_switches:
  discovery: false
  enrichment: false
  audit: false
  outreach: false
  conversation: false
```

**Activation**:
- Update config file or environment variable
- System detects change within 60 seconds
- Affected modules stop accepting new work
- In-flight work completes gracefully


## Testing Strategy

### Dual Testing Approach

The system requires both **unit tests** and **property-based tests** for comprehensive coverage. These are complementary:

- **Unit tests**: Verify specific examples, edge cases, and error conditions
- **Property tests**: Verify universal properties across all inputs

Together, they provide comprehensive coverage where unit tests catch concrete bugs and property tests verify general correctness.

### Property-Based Testing

**Framework**: Use `hypothesis` (Python) or `fast-check` (TypeScript/JavaScript) depending on implementation language.

**Configuration**: Each property test must run minimum **100 iterations** to ensure adequate randomization coverage.

**Test Tagging**: Each property test must include a comment referencing the design property:
```python
# Feature: zrai-lead-os, Property 1: State Persistence Completeness
def test_state_persistence_completeness(lead_state):
    ...
```

**Property Test Structure**:
```python
from hypothesis import given, strategies as st

# Feature: zrai-lead-os, Property 13: Score Range Validity
@given(
    intent_score=st.integers(min_value=0, max_value=100),
    leak_score=st.integers(min_value=0, max_value=100),
    # ... other scores
)
def test_score_range_validity(intent_score, leak_score, ...):
    """For any computed score, the value should be within the defined valid range."""
    lead = generate_lead_with_scores(intent_score, leak_score, ...)
    
    assert 0 <= lead.intent_score <= 100
    assert 0 <= lead.leak_score <= 100
    # ... other assertions
```

### Unit Testing

**Focus Areas**:
1. **Specific Examples**: Concrete test cases demonstrating correct behavior
2. **Edge Cases**: Empty inputs, boundary values, null handling
3. **Error Conditions**: Invalid inputs, missing data, constraint violations
4. **Integration Points**: Component boundaries, API contracts

**Example Unit Tests**:
```python
def test_canonical_lead_creation_with_minimal_data():
    """Test lead creation with only required fields."""
    raw_data = {
        'business_name': 'Test Business',
        'location': 'San Francisco, CA'
    }
    lead = create_canonical_lead(raw_data)
    
    assert lead.business_name == 'Test Business'
    assert lead.location == 'San Francisco, CA'
    assert lead.lead_id is not None
    assert lead.created_at is not None

def test_disqualification_rule_too_small():
    """Test that owner-only businesses are disqualified."""
    lead = create_lead(employee_count=1)
    result = apply_disqualification_rules(lead)
    
    assert result.do_not_contact == True
    assert result.do_not_contact_reason == 'Owner-only business'

def test_opt_out_detection_stop_keyword():
    """Test opt-out detection for STOP keyword."""
    reply = "STOP sending me emails"
    result = detect_opt_out(reply)
    
    assert result.opt_out_detected == True
    assert result.opt_out_keyword == 'STOP'
```

### Integration Testing

**Apify Integration**:
- Mock Apify responses for deterministic testing
- Test error handling (rate limits, timeouts)
- Verify data transformation from Apify format to Canonical Lead

**Steel.dev Integration**:
- Use Steel.dev test mode or mock browser
- Test screenshot capture and storage
- Verify extraction logic with sample HTML

**Database Integration**:
- Use test database with migrations applied
- Test CRUD operations for all tables
- Verify foreign key constraints and indexes

**LLM Integration**:
- Mock LLM responses for deterministic testing
- Test prompt construction
- Verify response parsing and entity extraction

### Test Data Generators

**Lead Generator**:
```python
def generate_random_lead():
    """Generate a random lead for property testing."""
    return CanonicalLead(
        lead_id=uuid4(),
        business_name=fake.company(),
        category=random.choice(CATEGORIES),
        location=fake.city() + ', ' + fake.state_abbr(),
        geo_tags=[fake.state_abbr()],
        website=fake.url(),
        phone=fake.phone_number(),
        emails_found=[fake.email()],
        ads_active=random.choice([True, False]),
        cta_type=random.choice(['CALL', 'FORM', 'BOOK', 'OTHER']),
        # ... other fields
    )
```

**Conversation Generator**:
```python
def generate_random_conversation():
    """Generate a random conversation for property testing."""
    return Conversation(
        conversation_id=uuid4(),
        lead_id=uuid4(),
        transcript=[
            {'role': 'ai', 'message': fake.sentence(), 'timestamp': fake.date_time()},
            {'role': 'prospect', 'message': fake.sentence(), 'timestamp': fake.date_time()},
        ],
        entities={
            'budget_range': {'min': random.randint(500, 2000), 'max': random.randint(2000, 10000)},
            'role': random.choice(['owner', 'manager', 'decision_maker']),
            'timeline': random.choice(['immediate', '1-2 weeks', '1 month']),
        },
        # ... other fields
    )
```

### Offline Replay Testing

**Golden Dataset**:
- 100+ labeled leads with known outcomes
- Diverse scenarios: high-score, low-score, edge cases
- Known good outreach examples
- Known bad outreach examples

**Replay Process**:
1. Load golden dataset
2. Run current version on dataset
3. Compare scores, tiers, and outreach quality to baseline
4. Generate diff report
5. Flag regressions

**Metrics to Track**:
- Score correlation (Pearson r)
- Tier agreement percentage
- Outreach quality delta
- False positive rate delta

### A/B Testing Framework

**Test Configuration**:
```yaml
ab_test:
  name: "outreach_tone_test"
  variants:
    - name: "control"
      weight: 0.5
      config:
        tone: "professional"
        evidence_emphasis: "high"
    
    - name: "treatment"
      weight: 0.5
      config:
        tone: "casual"
        evidence_emphasis: "medium"
  
  metrics:
    primary: "reply_rate"
    secondary: ["meeting_rate", "negative_signal_rate"]
  
  guardrails:
    min_reply_rate: 0.05
    max_negative_signal_rate: 0.02
  
  sample_size: 200
  duration_days: 7
```

**Automatic Rollback**:
- Monitor metrics in real-time
- If negative_signal_rate > 0.03, rollback to control
- If reply_rate < 0.05, rollback to control
- Alert operator on rollback

### Test Coverage Goals

**Minimum Coverage**:
- Unit tests: 80% code coverage
- Property tests: All 50 correctness properties implemented
- Integration tests: All external integrations covered
- End-to-end tests: Happy path + critical failure scenarios

**Critical Paths** (must have 100% coverage):
- Opt-out detection and enforcement
- Budget limit enforcement
- Idempotency key handling
- Circuit breaker activation
- Audit log creation

### Continuous Testing

**Pre-Commit**:
- Run unit tests
- Run linting and type checking
- Run fast property tests (10 iterations)

**CI Pipeline**:
- Run full unit test suite
- Run full property test suite (100 iterations)
- Run integration tests
- Run offline replay on golden dataset
- Generate coverage report

**Nightly**:
- Run extended property tests (1000 iterations)
- Run performance benchmarks
- Run security scans
- Generate quality metrics report

