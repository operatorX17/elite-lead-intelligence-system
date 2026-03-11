# ZRAI Lead OS Runbook

## Overview

This runbook documents the daily operations, monitoring, debugging, and recovery procedures for ZRAI Lead OS.

## Daily Operations

### Running the Daily Pipeline

```bash
# Standard daily run
python -m src.cli run_daily --config config/

# With specific niche
python -m src.cli run_daily --config config/ --niche dental

# With lead limit
python -m src.cli run_daily --config config/ --limit 100
```

### Dry Run (No Side Effects)

```bash
# Test without sending outreach or making external calls
python -m src.cli dry_run --config config/ --limit 10
```

### Replay a Previous Run

```bash
# Replay with same inputs for debugging
python -m src.cli replay_run --run_id <run_id>
```

### Resume Failed Leads

```bash
# Resume leads that failed since a timestamp
python -m src.cli resume_failed --since "2024-01-01T00:00:00Z"
```

## Monitoring

### Key Metrics to Watch

| Metric | Target | Alert Threshold |
|--------|--------|-----------------|
| reply_rate | >5% | <2% |
| meeting_rate | >2% | <0.5% |
| cost_per_qualified_meeting | <$50 | >$100 |
| false_positive_rate | <10% | >20% |
| human_override_rate | <5% | >15% |

### Budget Monitoring

Check daily usage against limits:
- LLM tokens: `daily_llm_token_limit`
- Browser sessions: `daily_browser_session_limit`
- Scraper runs: `daily_scraper_run_limit`

### Circuit Breaker Status

Monitor circuit breaker states in `circuit_breakers` table:
- CLOSED: Normal operation
- OPEN: Service unavailable, routing around
- HALF_OPEN: Testing recovery

## Debugging

### Common Issues

#### 1. High Error Rate in Discovery

**Symptoms**: Many leads failing at discovery stage

**Check**:
```sql
SELECT error_message, COUNT(*) 
FROM audit_log 
WHERE action = 'discovery_process' AND result = 'failure'
AND timestamp > NOW() - INTERVAL '1 day'
GROUP BY error_message;
```

**Solutions**:
- Check Apify API status
- Verify API token is valid
- Check rate limits

#### 2. Steel.dev Timeouts

**Symptoms**: Audit agent timing out

**Check**:
```sql
SELECT * FROM circuit_breakers WHERE node_name = 'audit';
```

**Solutions**:
- Increase timeout in config
- Check Steel.dev service status
- Reduce concurrent sessions

#### 3. Budget Exceeded

**Symptoms**: Operations blocked with "budget_exceeded"

**Check**:
```sql
SELECT * FROM usage_metrics WHERE date = CURRENT_DATE;
```

**Solutions**:
- Wait for daily reset
- Increase limits in config
- Investigate unexpected usage

### Log Analysis

```bash
# View recent errors
grep "ERROR" logs/zrai.log | tail -100

# View specific lead processing
grep "<lead_id>" logs/zrai.log
```

## Recovery Procedures

### Rollback a Bad Deployment

1. Stop current execution:
   ```bash
   # Set global kill switch
   export ZRAI_GLOBAL_KILL=true
   ```

2. Rollback to previous version:
   ```bash
   git checkout <previous_tag>
   pip install -r requirements.txt
   ```

3. Resume with previous config:
   ```bash
   python -m src.cli resume_failed --since "<deployment_time>"
   ```

### Reset Circuit Breaker

```sql
UPDATE circuit_breakers 
SET state = 'CLOSED', failure_count = 0 
WHERE node_name = '<node_name>';
```

### Clear Stuck Leads

```sql
-- Find stuck leads
SELECT lead_id, current_stage, last_error 
FROM lead_state 
WHERE is_complete = false 
AND updated_at < NOW() - INTERVAL '1 hour';

-- Reset for retry
UPDATE lead_state 
SET retry_count = 0, last_error = NULL 
WHERE lead_id = '<lead_id>';
```

## Emergency Procedures

### Global Shutdown

```bash
# Immediate stop
export ZRAI_GLOBAL_KILL=true

# Or via config
# Set kill_switches.global_kill = true in config/agents.yaml
```

### Module-Specific Shutdown

```yaml
# In config/agents.yaml
kill_switches:
  discovery_kill: true  # Stop discovery
  audit_kill: true      # Stop Steel.dev calls
  outreach_kill: true   # Stop sending messages
```

### Data Recovery

1. Check audit log for last successful operations
2. Identify affected leads
3. Use replay_run to reprocess

## Maintenance

### Weekly Tasks

- Review metrics dashboard
- Check for stale leads
- Review negative signals
- Update playbooks if needed

### Monthly Tasks

- Review and update scoring weights
- Analyze A/B test results
- Update golden dataset
- Review budget allocations

## Contact

For escalations:
- On-call: Check PagerDuty
- Slack: #zrai-ops
