# AGENTS.md
## Title: Elite Agentic Intelligence Framework for ZRAI Lead OS

**Purpose:** Configure OpenCode agents for peak performance on ZRAI Lead OS autonomous lead intelligence system.

---

## 1. PROJECT OVERVIEW

### 1.1 System Architecture
ZRAI Lead OS is a LangGraph-based multi-agent autonomous system with:
- 9 specialist agents (discovery, enrichment, intent, audit, scoring, outreach, conversation, governance, eval)
- Supabase database (15+ tables)
- MCP tools: Firecrawl (web scraping), Steel (browser automation), Brave (search), Context7 (docs), Perplexity (research)
- Stateful graph orchestration with circuit breakers

### 1.2 Agent Capabilities
- **Discovery Agent**: Bulk ingestion via Apify (Meta Ads, Google Maps)
- **Enrichment Agent**: Contact extraction, tech signal detection
- **Intent Agent**: Revenue leak scoring, intent analysis
- **Audit Agent**: Proof generation via Steel.dev browser automation
- **Scoring Agent**: Weighted scoring with disqualification rules
- **Outreach Agent**: Evidence-backed message generation
- **Conversation Agent**: AI-driven BANT qualification
- **Governance Agent**: RBAC, rate limiting, audit logging
- **Eval Agent**: Offline replay and A/B testing

---

## 2. AGENT BEHAVIORAL ARCHITECTURE

### 2.1 Cognitive Principles

**Principle 1: Multi-Perspective Analysis**
When analyzing code or requirements, always:
- Examine from 3+ architectural perspectives (performance, security, maintainability)
- Consider trade-offs explicitly (time vs. quality, flexibility vs. complexity)
- Document assumptions and validate them with codebase reality
- Ask clarifying questions before proceeding with implementation

**Principle 2: Progressive Refinement**
- Start with high-level solution outline
- Iteratively refine with detailed implementation
- Validate each component against existing patterns
- Only commit changes after full cycle completion

**Principle 3: Context-Efficient Tool Selection**
Before invoking any MCP tool:
1. Check if information exists in current context
2. Evaluate tool cost vs. information value
3. Prefer local tools (file reads, database queries) over external API calls
4. Batch related operations when possible
5. Cache frequently accessed external data

**Principle 4: Self-Verification Loop**
After any significant operation:
1. Review change for consistency with system patterns
2. Check for security implications (secrets exposure, input validation)
3. Verify database schema compliance
4. Test edge cases mentally before suggesting completion
5. Generate rollback plan if high-risk changes

### 2.2 MCP Server Utilization Strategy

**Tier 1: Zero-Cost (Immediate)**
- `read` - File system operations
- Local database queries via SQLite MCP
- Local git operations
- Project structure analysis

**Tier 2: Low-Cost (Fast Response)**
- Brave Search - Quick web searches
- Context7 - Documentation lookup
- Local tools with minimal latency

**Tier 3: Medium-Cost (Structured Data)**
- Firecrawl - Web scraping with schema extraction
- Perplexity - Research and synthesis
- Semgrep - Code analysis with rules

**Tier 4: High-Cost (Complex Operations)**
- Steel - Browser automation (mystery shopping)
- GitHub - Repository operations
- N8N - Workflow automation

**Selection Heuristic:**
```
IF task requires fresh web data:
  Use Firecrawl for scraping
  Use Brave for discovery searches
ELSE IF task requires browsing automation:
  Use Steel for interactive tasks
ELSE IF task requires docs lookup:
  Use Context7 for documentation
ELSE IF task requires code analysis:
  Use Semgrep for static analysis
  Use SQLite for data inspection
```

---

## 3. PROJECT-SPECIFIC INSTRUCTIONS

### 3.1 Code Conventions

**Language:** Python 3.11+
**Type System:** Type hints with `pydantic>=2.0.0`
**Testing Framework:** pytest with hypothesis (property-based tests)
**Orchestration:** LangGraph with stateful graphs

**Style Guidelines:**
- Follow existing patterns in `src/agents/*.py`
- Use base class patterns from `src/agents/base.py`
- Implement proper error handling with circuit breakers
- Add idempotency keys for all external operations
- Log all external actions for audit trail

**File Organization:**
```
src/
  agents/           # Specialist agents (discovery, enrichment, etc.)
  graph/            # LangGraph orchestration
  tools/            # External integrations (Apify, Steel, etc.)
  db/              # Supabase client
  config/           # YAML configuration files
```

### 3.2 Database Schema Awareness

**Critical Tables:**
- `leads` - Canonical lead records
- `lead_state` - Graph orchestration state
- `scoring_results` - Weighted scoring outputs
- `outreach_queue` - Message queue
- `conversations` - AI conversation transcripts
- `audit_log` - Append-only action logs
- `negative_signals` - Opt-outs and angry replies
- `circuit_breakers` - Component failure tracking

**Schema Rules:**
- Always validate against Pydantic models before DB writes
- Use parameterized queries to prevent SQL injection
- Implement proper foreign key relationships
- Use transactions for multi-table operations
- Add indexes for query optimization

### 3.3 Safety & Compliance

**Kill Switches:**
- Check environment variables: `KILL_SWITCH_GLOBAL`, `KILL_SWITCH_DISCOVERY`, etc.
- Respect kill switches before any external API calls
- Graceful shutdown with state persistence

**Rate Limiting:**
- Per-domain: 5 emails/day, 2 DMs/day
- Per-channel: 200 emails/day
- Cool-down periods after bounces (7 days), spam complaints (30 days)
- Always check `circuit_breakers` table before operations

**Do Not Contact (DNC):**
- Check `do_not_contact` table before outreach
- Respect opt-out detection (STOP, UNSUBSCRIBE keywords)
- Honor angry reply flags
- Permanently remove invalid emails

**Budget Controls:**
- Track daily usage in `usage_metrics` table
- Enforce `config/budgets.yaml` limits
- Alert at 80% usage
- Block operations at 100% usage

### 3.4 MCP Tool Integration

**Critical Usage Patterns:**

**Web Scraping (Discovery & Enrichment):**
```
When scraping business data:
  1. Use Apify actors via discovery agent (bulk operations)
  2. Use Firecrawl for targeted page scraping with schema extraction
  3. Extract: business_name, website, phone, email, social_profiles
  4. Validate: email format with email-validator, phone with phonenumbers
  5. Deduplicate: existing leads via database query
```

**Browser Automation (Audit Agent):**
```
When generating proof artifacts:
  1. Use Steel MCP for interactive browsing
  2. Navigate: landing_page_url from lead record
  3. Extract: phone_visibility, form_field_count, booking_link, business_hours
  4. Capture: screenshots of hero section and CTA/form area
  5. Generate: 3 audit_bullets with evidence, fix, and upside estimate
  6. Store: screenshots to object storage, update URLs in database
```

**Research & Documentation:**
```
When researching niches or outreach patterns:
  1. Use Context7 MCP for playbook documentation
  2. Use Perplexity MCP for research synthesis
  3. Use Brave Search for niche keyword research
  4. Extract: niche-specific guidance, industry patterns, objection handling
```

**Code Analysis:**
```
When analyzing codebase:
  1. Use Semgrep MCP for security scans and best practices
  2. Query SQLite MCP for lead lifecycle state inspection
  3. Focus on: input validation, secret management, error handling
  4. Report: vulnerabilities, performance issues, and improvement opportunities
```

---

## 4. AGENT-SPECIFIC CONFIGURATIONS

### 4.1 Primary Agents

**Build Agent (Default - Full Access)**
- **Purpose:** Full development capability with all tools
- **Model:** Use globally configured model
- **Temperature:** 0.3 (balanced creativity)
- **Tools:** All enabled
- **Permissions:**
  - write: allow
  - edit: allow
  - bash: allow
- **Use when:** Implementation, bug fixes, feature development

**Plan Agent (Restricted)**
- **Purpose:** Analysis and planning without changes
- **Model:** Same as Build
- **Temperature:** 0.1 (deterministic)
- **Tools:** Read-only (no write/edit/bash writes)
- **Permissions:**
  - write: ask
  - edit: ask
  - bash: ask
- **Use when:** Requirements analysis, code review, architecture planning

### 4.2 Subagents (Specialized)

**General Agent**
- **Purpose:** Multi-step research and complex queries
- **Trigger:** Auto-invoked for search tasks or manually via `@general`
- **Tools:** All search and query tools
- **Mode:** subagent

**Explore Agent**
- **Purpose:** Fast codebase exploration
- **Trigger:** Auto-invoked for file pattern searches
- **Tools:** Glob, grep, file reads
- **Mode:** subagent

**Custom Agents Configuration:**

```json
{
  "agent": {
    "zrai-lead-scoring": {
      "description": "Specialized agent for lead scoring analysis and optimization",
      "mode": "subagent",
      "model": "anthropic/claude-sonnet-4-20250514",
      "prompt": "{file:.opencode/prompts/lead-scoring.txt}",
      "tools": {
        "write": false,
        "edit": false,
        "bash": false
      },
      "temperature": 0.1,
      "permission": {
        "task": {
          "*": "deny",
          "build": "allow",
          "plan": "allow"
        }
      }
    },
    "zrai-audit-generator": {
      "description": "Generates proof artifacts via Steel browser automation",
      "mode": "subagent",
      "model": "anthropic/claude-sonnet-4-20250514",
      "tools": {
        "write": true,
        "edit": false,
        "bash": false
      },
      "temperature": 0.2,
      "maxSteps": 15
    },
    "zrai-outreach-writer": {
      "description": "Creates evidence-backed outreach messages with proof screenshots",
      "mode": "subagent",
      "model": "anthropic/claude-sonnet-4-20250514",
      "tools": {
        "firecrawl": true,
        "brave-search": true,
        "context7": true
      },
      "permission": {
        "bash": {
          "git*": "allow",
          "test*": "allow"
        }
      }
    }
  }
}
```

---

## 5. REASONING WORKFLOWS

### 5.1 Problem Decomposition

**When analyzing complex requirements:**

1. **Problem Statement Clarification**
   - Rephrase user request in own words
   - Identify ambiguous terms
   - Ask targeted clarifying questions
   - Document assumptions

2. **Component Breakdown**
   - Decompose into atomic subtasks
   - Identify dependencies between tasks
   - Estimate complexity for each component
   - Prioritize based on critical path

3. **Solution Space Exploration**
   - Generate 2-3 alternative approaches
   - Compare approaches on multiple criteria
   - Select optimal approach with rationale
   - Document rejected alternatives and reasons

4. **Implementation Planning**
   - Create step-by-step execution plan
   - Identify verification points for each step
   - Plan rollback strategy for high-risk changes
   - Estimate resource requirements (time, tools, compute)

### 5.2 Multi-Tool Coordination

**When tasks require multiple MCP servers:**

1. **Dependency Analysis**
   ```
   Graph task dependencies:
   Lead Discovery (Apify) → Enrichment (Firecrawl) → Intent Analysis (LLM) → Audit (Steel)

   Parallelization opportunities:
   - Multiple leads can be enriched concurrently
   - Intent scoring can happen in batches
   - Database queries should be batched
   ```

2. **Error Handling Strategy**
   - Circuit breaker activation: log error, skip lead, continue pipeline
   - Retry with exponential backoff: 3 attempts with doubling delays
   - Fallback: If Steel fails, use Firecrawl for static analysis
   - Partial success handling: Save available data, flag incomplete records

3. **Cost Optimization**
   ```
   IF high-tier lead (score > 80):
     Use Steel for full audit (expensive but high value)
   ELSE IF medium-tier lead (50 < score < 80):
     Use Firecrawl for lightweight scraping
   ELSE:
     Minimal processing, defer to batch
   ```

---

## 6. QUALITY ASSURANCE

### 6.1 Code Review Checklist

**Before suggesting any code:**

- [ ] Type hints complete (Pydantic models)
- [ ] Error handling for all external operations
- [ ] Idempotency keys implemented
- [ ] Rate limit checks before API calls
- [ ] Secret redaction in logs
- [ ] Database query parameterization
- [ ] Circuit breaker integration
- [ ] Unit test paths provided
- [ ] Property test coverage for critical functions
- [ ] Documentation for new functions

### 6.2 Testing Guidance

**When implementing features:**

1. **Unit Tests**
   - Test individual functions in isolation
   - Mock external dependencies (Apify, Steel, Firecrawl)
   - Use pytest fixtures for database states
   - Cover happy path and error cases

2. **Property-Based Tests**
   - Use Hypothesis for edge case generation
   - Test invariant properties (e.g., "scoring always 0-100")
   - Test state machine transitions (NEW → STALE → REACTIVATABLE)
   - Test circuit breaker logic
   - Test rate limiting boundaries

3. **Integration Tests**
   - Test end-to-end lead pipeline flow
   - Test MCP server integrations
   - Test database migrations
   - Test agent coordination via LangGraph

### 6.3 Performance Optimization

**When analyzing performance-critical code:**

1. Identify hot paths in pipeline
2. Suggest batching for database operations
3. Recommend caching for frequently accessed data
4. Propose parallelization for independent operations
5. Suggest async operations for I/O-bound tasks

---

## 7. MCP SERVER REFERENCE

### 7.1 Quick Reference

| Tool | Server | Use Case | Cost Tier | Invocation Pattern |
|------|---------|------------|-------------|------------------|
| Search web | brave-search | Low | "use brave-search to find [query]" |
| Scrape page | firecrawl | Medium | "use firecrawl to extract data from [url]" |
| Browse interactively | steel | High | "use steel to navigate and audit [url]" |
| Search docs | context7 | Low | "use context7 to find [topic]" |
| Research synthesis | perplexity | Medium | "use perplexity to research [topic]" |
| Analyze code | semgrep | Low | "use semgrep to scan for [rule]" |
| Query database | sqlite | Zero | "use sqlite to query [table]" |
| GitHub operations | github | Medium | "use github to [action]" |

### 7.2 Tool Selection Decision Tree

```
Task: Need to analyze lead website
├─ Is it static page extraction?
│  └─ YES → Use Firecrawl (faster, cheaper)
├─ Is it interactive browsing needed?
│  └─ YES → Use Steel (full browser automation)
└─ Is it just data lookup?
   └─ YES → Use SQLite (zero cost)

Task: Need to research niche patterns
├─ Looking for documentation?
│  └─ YES → Use Context7
├─ Synthesizing information?
│  └─ YES → Use Perplexity
└─ Finding new information?
   └─ YES → Use Brave Search

Task: Need code analysis
├─ Security scan?
│  └─ YES → Use Semgrep with security rules
├─ Best practices?
│  └─ YES → Use Semgrep with custom rules
└─ Data inspection?
   └─ YES → Use SQLite queries
```

---

## 8. SPECIAL INSTRUCTIONS

### 8.1 MCP Usage

**Critical Rules:**
1. NEVER make parallel external API calls without batching consideration
2. Always check circuit breaker state before expensive operations (Steel, Firecrawl)
3. Use SQLite MCP for all data inspection before new API calls
4. Cache results from MCP servers when idempotency allows
5. Prefer Context7 for playbook lookup over web searches
6. Use Brave Search for discovery, not for known URLs
7. Validate API keys exist before MCP tool invocation
8. Check rate limits in `config/policies.yaml` before operations

### 8.2 Security & Secrets

**Non-negotiable Requirements:**
- Never log or expose API keys
- Use `{env:VAR_NAME}` syntax only
- Add `opencode.json` to `.gitignore`
- Use secret redaction in all logs and error messages
- Validate inputs before database queries (prevent injection)
- Use parameterized queries (never string interpolation)
- Check `do_not_contact` table before all outreach

### 8.3 Error Handling

**MCP Server Failures:**
1. Log error with MCP server name and operation
2. Check `circuit_breakers` table
3. Activate circuit breaker if threshold exceeded
4. Implement fallback strategy (Firecrawl if Steel fails)
5. Continue processing other leads (don't block entire pipeline)
6. Alert via `audit_log` when circuits trip

**Database Failures:**
1. Use Supabase connection pooling
2. Implement transaction retry with exponential backoff
3. Validate schema before writes
4. Check foreign key constraints
5. Log detailed error context for debugging

---

## 9. CONTINUOUS IMPROVEMENT

### 9.1 Self-Reflection Protocol

**After significant operations:**

1. **What went well?**
   - Identify successful patterns
   - Note efficient MCP usage
   - Record effective strategies

2. **What could improve?**
   - Identify bottlenecks or inefficiencies
   - Note areas requiring deeper knowledge
   - Suggest optimization opportunities

3. **Pattern Extraction:**
   - Extract reusable strategies
   - Document successful workflows
   - Create agent-specific guidance

### 9.2 Knowledge Base Updates

**Maintain Playbooks:**
- Outreach templates that converted well
- Objection handling that worked
- Scoring rules with high precision
- Niche-specific insights discovered

**Update Configuration:**
- Adjust rate limits based on deliverability
- Update scoring weights in `config/niches.yaml`
- Refine disqualification rules
- Add new MCP servers as they become available

---

## 10. EXECUTION PROTOCOLS

### 10.1 Agent Invocation

**Manual Invocation:**
```
@zrai-lead-scoring Analyze lead quality for HVAC niche
@zrai-audit-generator Create proof artifacts for high-tier leads
@zrai-outreach-writer Generate outreach for tier A leads with proof
@general Research HVAC contractor lead generation strategies
```

**Automatic Invocation:**
- Build agent automatically invokes General for research tasks
- Build agent automatically invokes Explore for file pattern searches
- Plan agent auto-invokes for analysis requests

### 10.2 Tool Usage

**Pre-Invocation Checklist:**
1. Is information already in context? → Skip MCP call
2. Can local tool suffice? → Use file read/SQLite
3. Is this a batch operation? → Combine requests
4. Does circuit breaker allow this? → Check DB first
5. Is cost justified? → Estimate value before invocation
6. Have alternative approach? → Consider fallback options

---

**Appendix: Agent Capabilities Summary**

| Agent | Access Level | Primary Focus | Temperature | Max Steps |
|-------|-------------|---------------|-------------|------------|
| Build | Full | Implementation | 0.3 | Unbounded |
| Plan | Read-only | Analysis | 0.1 | Unbounded |
| General | Research | Multi-step tasks | 0.5 | 20 |
| Explore | Search | Fast discovery | 0.4 | 10 |
| Lead Scoring | Analysis | Quality assessment | 0.1 | 15 |
| Audit Generator | Write | Proof creation | 0.2 | 15 |
| Outreach Writer | All tools | Message generation | 0.3 | Unbounded |

---

**Last Updated:** January 12, 2026
**Framework Version:** 1.0 - Elite Tier Intelligence
**Compatibility:** OpenCode 1.0+, ZRAI Lead OS v0.85+
