# ZRAI Lead OS

**Autonomous Lead Intelligence + Outreach Engine**

A production-grade, multi-agent system that autonomously discovers businesses with revenue leaks, verifies pain points through evidence-based analysis, initiates proof-backed conversations, qualifies prospects, and escalates to humans only at the closing moment.

## Architecture

ZRAI Lead OS is built on LangGraph for stateful orchestration with specialist agents:

- **Discovery Agent**: Bulk ingestion via Apify (Meta Ads, Google Maps)
- **Enrichment Agent**: Contact extraction and tech signal detection
- **Intent Agent**: Revenue leak scoring and intent analysis
- **Audit Agent**: Proof generation via Steel.dev browser automation
- **Scoring Agent**: Weighted scoring with disqualification rules
- **Outreach Agent**: Evidence-backed message generation
- **Conversation Agent**: AI-driven qualification (BANT)
- **Governance Agent**: RBAC, rate limiting, audit logging
- **Eval Agent**: Offline replay and A/B testing

## Tech Stack

- **Orchestration**: LangGraph (stateful graph runtime)
- **Database**: Supabase (Postgres)
- **Scraping**: Apify Actors
- **Browser Automation**: Steel.dev
- **LLM**: Gemini/OpenAI/Anthropic (pluggable)
- **Vector Store**: Pinecone (playbook RAG)
- **Object Storage**: S3-compatible

## Quick Start

### 1. Prerequisites

- Python 3.11+
- Supabase account
- API keys: Gemini/OpenAI, Apify, Steel.dev, Pinecone

### 2. Installation

```bash
# Clone repository
git clone <repo-url>
cd zrai-lead-os

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env
```

### 3. Configuration

Edit `.env` with your API keys:

```bash
# Database
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key

# LLM
GOOGLE_API_KEY=your-gemini-key
OPENAI_API_KEY=your-openai-key  # optional
ANTHROPIC_API_KEY=your-anthropic-key  # optional

# Integrations
APIFY_API_TOKEN=your-apify-token
STEEL_API_KEY=your-steel-key
PINECONE_API_KEY=your-pinecone-key

# Storage (optional, uses Supabase by default)
AWS_ACCESS_KEY_ID=your-aws-key
AWS_SECRET_ACCESS_KEY=your-aws-secret
S3_BUCKET_NAME=zrai-artifacts
```

### 4. Database Setup

Run migrations in Supabase SQL Editor:

```bash
# Copy contents of migrations/001_initial_schema.sql
# Paste into Supabase SQL Editor and execute
```

### 5. Pinecone Setup

Create index with these settings:
- **Name**: `zrai-playbooks`
- **Dimensions**: 768
- **Metric**: cosine
- **Cloud**: AWS
- **Region**: us-east-1

Or use the setup script:

```bash
python setup_pinecone_index.py
```

### 6. Verify Setup

```bash
# Check system status
python -m src.cli status

# Test connections
python test_gemini_api.py
python test_apify_connection.py
python test_pinecone_connection.py
```

## Usage

### Daily Run

Process leads through the full pipeline:

```bash
python -m src.cli run_daily --limit 100
```

Options:
- `--config PATH`: Custom config file
- `--limit N`: Process N leads
- `--niche NAME`: Filter by niche

### Dry Run

Simulate without external writes:

```bash
python -m src.cli dry_run --limit 10
```

### Resume Failed

Resume failed executions:

```bash
python -m src.cli resume_failed --since 2026-01-01T00:00:00
```

### Replay Historical Run

Replay for evaluation:

```bash
python -m src.cli replay_run <run_id>
```

### System Status

Check kill switches, circuit breakers, usage:

```bash
python -m src.cli status
```

### A/B Test Status

Check A/B test results:

```bash
python -m src.cli ab_status --test-name outreach_tone_test
```

### Inspect Lead

View lead details and history:

```bash
python -m src.cli inspect <lead_id>
```

## Configuration

All behavior is config-driven via YAML files in `config/`:

### `config/niches.yaml`

Define target niches with keywords, scoring weights, and rules:

```yaml
niches:
  hvac:
    name: "HVAC Services"
    keywords: ["hvac", "air conditioning", "heating"]
    geo_filters: ["US"]
    high_ticket: true
    scoring_weights:
      ad_activity: 0.20
      intent: 0.25
      leak: 0.30
      reactivation: 0.10
      contact_quality: 0.10
      business_size: 0.05
```

### `config/policies.yaml`

Rate limits, disqualification rules, lifecycle settings:

```yaml
rate_limits:
  per_domain:
    email_per_day: 5
    dm_per_day: 2
  cool_downs:
    after_bounce: 7
    after_spam_complaint: 30
```

### `config/agents.yaml`

Agent-specific settings, LLM routing, retry configs:

```yaml
llm:
  default_provider: "gemini"
  routing:
    outreach_generation: "gemini"
    conversation: "gemini"
```

### `config/budgets.yaml`

Daily cost limits and alerts:

```yaml
daily_limits:
  llm:
    tokens: 1000000
    cost_usd: 50.00
  browser:
    sessions: 500
    cost_usd: 25.00
```

## Safety Features

### Kill Switches

Emergency stops via environment variables:

```bash
# Global kill switch
KILL_SWITCH_GLOBAL=true

# Per-module kill switches
KILL_SWITCH_DISCOVERY=false
KILL_SWITCH_AUDIT=false
KILL_SWITCH_OUTREACH=false
```

### Circuit Breakers

Automatic isolation of failing components:
- Opens after N failures
- Routes around failed components
- Auto-recovers after timeout

### Rate Limiting

Multi-level protection:
- Per-domain limits (5 emails/day)
- Per-channel limits (200 emails/day)
- Cool-down periods after negative signals

### Do Not Contact (DNC)

Permanent and temporary blocks:
- Opt-out detection (STOP, UNSUBSCRIBE)
- Angry reply detection
- Bounce handling
- Spam complaint tracking

### Budget Guardrails

Daily limits prevent runaway costs:
- LLM token limits
- Browser session limits
- Scraper run limits
- Automatic alerts at 80% usage

## Development

### Project Structure

```
zrai-lead-os/
├── src/
│   ├── agents/          # Specialist agents
│   ├── config/          # Configuration management
│   ├── db/              # Database client and models
│   ├── graph/           # LangGraph orchestration
│   ├── tools/           # External integrations
│   └── cli.py           # CLI interface
├── config/              # YAML configuration files
├── migrations/          # Database migrations
├── tests/               # Property-based tests
├── .env                 # Environment variables
└── requirements.txt     # Python dependencies
```

### Running Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio hypothesis pytest-cov

# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test
pytest tests/test_scoring.py
```

### Adding a New Agent

1. Create agent file in `src/agents/`
2. Inherit from `BaseAgent`
3. Implement `process(state: LeadGraphState)` method
4. Add node function at bottom
5. Wire into orchestrator in `src/graph/orchestrator.py`
6. Add configuration in `config/agents.yaml`

### Adding a New Niche

1. Add niche definition to `config/niches.yaml`
2. Define keywords and geo filters
3. Set scoring weights
4. Configure disqualification rules
5. Add playbook content for the niche

## Monitoring

### Metrics

Daily metrics tracked:
- Reply rate
- Meeting rate
- Cost per qualified meeting
- False positive rate
- Human override rate

### Audit Logs

All external actions logged:
- Actor (which agent)
- Action (what was done)
- Resource (lead ID, etc.)
- Timestamp
- Result (success/failure)
- Idempotency key

### Execution Traces

Per-lead tracing:
- Node latency
- Tool errors
- Retry count
- LLM tokens and cost
- Success/failure reasons

## Evaluation

### Golden Dataset

Maintain labeled leads for validation:
- Expected scores and tiers
- Known outcomes (replied, meeting, closed)
- Outreach quality labels

### Offline Replay

Test changes before production:

```bash
python -m src.cli replay_run <run_id>
```

Compares:
- Score correlation
- Tier agreement
- Outreach quality delta
- False positive rate delta

### A/B Testing

Test variants in production:
- Automatic traffic splitting
- Guardrail monitoring
- Auto-rollback on degradation

## Troubleshooting

### Common Issues

**"No leads to process"**
- Check lead_lifecycle_state in database
- Verify discovery agent ran successfully
- Check kill switches: `python -m src.cli status`

**"Circuit breaker is OPEN"**
- Check which component failed
- Review error logs in audit_log table
- Reset manually or wait for timeout

**"Budget limit exceeded"**
- Check usage: `python -m src.cli status`
- Increase limits in `config/budgets.yaml`
- Wait for daily reset (midnight UTC)

**"Rate limit reached"**
- Check per-domain/channel limits
- Review negative signals for the lead
- Adjust limits in `config/policies.yaml`

### Debug Mode

Enable verbose logging:

```bash
python -m src.cli run_daily --verbose
```

Or set in environment:

```bash
LOG_LEVEL=DEBUG python -m src.cli run_daily
```

### Inspect Lead State

View full lead details:

```bash
python -m src.cli inspect <lead_id>
```

Shows:
- Lead data
- Processing state
- Scoring results
- Negative signals
- Conversation history

## Production Deployment

### Recommended Setup

1. **Database**: Supabase Pro plan
2. **Compute**: Cloud VM (2 vCPU, 4GB RAM minimum)
3. **Scheduler**: Cron job for daily runs
4. **Monitoring**: Prometheus + Grafana
5. **Alerts**: Email/Slack on budget/errors

### Cron Schedule

```bash
# Daily run at 2 AM
0 2 * * * cd /path/to/zrai-lead-os && python -m src.cli run_daily >> logs/daily.log 2>&1

# Resume failed every 6 hours
0 */6 * * * cd /path/to/zrai-lead-os && python -m src.cli resume_failed --since "6 hours ago" >> logs/resume.log 2>&1
```

### Scaling

For high volume (>10K leads/day):
- Increase `MAX_CONCURRENT_LEADS` in config
- Use connection pooling for database
- Consider separate workers for agents
- Implement queue-based processing

## Security

### Secrets Management

Never commit secrets:
- Use `.env` for local development
- Use secret manager in production (AWS Secrets Manager, etc.)
- Rotate API keys regularly

### Database Security

- Enable Row Level Security (RLS) in Supabase
- Use service role key only in backend
- Restrict network access
- Regular backups

### Compliance

- GDPR: Respect opt-outs, data retention limits
- CAN-SPAM: Include opt-out in emails
- TCPA: Honor DNC list
- Audit logs for compliance verification

## Support

For issues or questions:
1. Check this README
2. Review `.rules` and spec files
3. Inspect logs and audit trail
4. Check system status

## License

[Your License Here]

## Contributing

[Your Contributing Guidelines Here]
