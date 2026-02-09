# Requirements Document: ZRAI Lead OS

## Introduction

ZRAI Lead OS (Autonomous Lead Intelligence + Outreach Engine) is a production-grade, multi-agent system designed to autonomously discover businesses with revenue leaks, verify pain points through evidence-based analysis, initiate proof-backed conversations, qualify prospects, and escalate to humans only at the closing moment. The system operates as a stateful graph orchestration engine with specialist agents, designed for daily execution, safe scaling, and continuous improvement through feedback loops.

## Glossary

- **Lead_OS**: The complete ZRAI Lead Intelligence and Outreach System
- **Graph_Orchestrator**: The state-machine runtime that manages multi-agent workflow execution
- **Discovery_Agent**: Agent responsible for bulk ingestion of business data via Apify
- **Enrichment_Agent**: Agent that extracts contact information and business context
- **Intent_Agent**: Agent that computes intent and revenue leak scores
- **Audit_Agent**: Agent that generates proof artifacts via Steel.dev browser automation
- **Scoring_Agent**: Agent that applies weighted scoring and disqualification rules
- **Outreach_Agent**: Agent that generates evidence-backed outreach messages
- **Conversation_Agent**: AI agent that handles qualification conversations
- **Governance_Layer**: Control system for RBAC, rate limits, audit logs, and compliance
- **Eval_Harness**: Offline replay and A/B testing system for quality validation
- **Canonical_Lead**: Normalized lead record with standardized schema
- **Proof_Pack**: Collection of screenshots and audit bullets showing revenue leak evidence
- **Lead_Tier**: Classification (A/B/C) determining outreach priority and approach
- **Steel_Task**: Browser automation task executed via Steel.dev
- **Apify_Actor**: Scraping/extraction service for bulk data collection
- **Idempotency_Key**: Unique identifier ensuring operations execute exactly once
- **Circuit_Breaker**: Safety mechanism that disables failing components
- **Kill_Switch**: Emergency control to halt system or module execution
- **Playbook**: Versioned knowledge artifact containing niche-specific guidance

## Requirements

### Requirement 1: Graph-Based Orchestration Runtime

**User Story:** As a system operator, I want a stateful graph orchestration engine, so that the multi-agent workflow can handle failures gracefully, retry intelligently, and scale across many leads concurrently.

#### Acceptance Criteria

1. WHEN the Graph_Orchestrator initializes, THE Lead_OS SHALL load the workflow graph definition with explicit nodes and state transitions
2. WHEN processing a lead, THE Graph_Orchestrator SHALL persist lead state including lead_id, current_stage, last_node, last_error, retry_count, next_run_at, and locks
3. WHEN a node fails, THE Graph_Orchestrator SHALL implement exponential backoff retry logic with configurable max attempts
4. WHEN a component repeatedly fails, THE Graph_Orchestrator SHALL activate circuit breakers to isolate failures and continue pipeline execution
5. WHEN executing external writes, THE Graph_Orchestrator SHALL use idempotency keys to prevent duplicate operations
6. WHEN the system receives a kill switch signal, THE Graph_Orchestrator SHALL halt execution gracefully and persist current state
7. WHEN processing multiple leads, THE Graph_Orchestrator SHALL support concurrent execution with configurable parallelism limits
8. WHEN a lead reaches a terminal state, THE Graph_Orchestrator SHALL mark completion and archive execution trace

### Requirement 2: CLI and Execution Modes

**User Story:** As a system operator, I want multiple execution modes via CLI, so that I can run daily operations, replay historical runs, resume failed executions, and test changes safely.

#### Acceptance Criteria

1. WHEN the operator runs `run_daily --config <path>`, THE Lead_OS SHALL execute the full pipeline using the specified configuration
2. WHEN the operator runs `replay_run --run_id <id>`, THE Lead_OS SHALL replay a historical execution with the same inputs and configuration
3. WHEN the operator runs `resume_failed --since <timestamp>`, THE Lead_OS SHALL identify and resume all failed lead executions since the specified time
4. WHEN the operator runs `dry_run --limit N`, THE Lead_OS SHALL simulate execution for N leads without performing external writes
5. WHEN any CLI command completes, THE Lead_OS SHALL output execution summary with success/failure counts and error details

### Requirement 3: Business Discovery via Bulk Ingestion

**User Story:** As a lead generation system, I want to discover businesses already spending money on ads and listings, so that I can target active spenders with verified intent signals.

#### Acceptance Criteria

1. WHEN the Discovery_Agent executes, THE Lead_OS SHALL use Apify Actors to scrape Meta Ads Library for advertisers matching niche keywords
2. WHEN scraping Meta Ads Library, THE Discovery_Agent SHALL extract business_name, website_url, cta_type, ad_start_date, ad_active_status, and creative_count
3. WHEN the Discovery_Agent executes, THE Lead_OS SHALL use Apify Actors to scrape Google Maps listings for service businesses matching geo and keyword filters
4. WHEN scraping Google Maps, THE Discovery_Agent SHALL extract business_name, category, location, phone, website, and review_count
5. WHEN the Discovery_Agent extracts websites, THE Lead_OS SHALL crawl contact pages to find email addresses, phone numbers, and booking links
6. WHEN the Discovery_Agent extracts social profiles, THE Lead_OS SHALL capture Facebook and Instagram page URLs
7. WHEN raw data is collected, THE Discovery_Agent SHALL create a Canonical_Lead record with normalized schema
8. WHEN creating Canonical_Lead records, THE Discovery_Agent SHALL store lead_id, business_name, category, location, geo_tags, website, landing_page_url, phone, emails_found, facebook_page, instagram, ads_active, ad_start_date, ad_last_seen, cta_type, lead_form_detected, created_at, and updated_at

### Requirement 4: Contact and Context Enrichment

**User Story:** As a lead qualification system, I want to enrich raw leads with decision-maker contacts and technical context, so that outreach can be personalized and targeted effectively.

#### Acceptance Criteria

1. WHEN the Enrichment_Agent processes a lead, THE Lead_OS SHALL extract technology signals including booking_provider, crm_hint, chat_widget, and form_tool
2. WHEN the Enrichment_Agent processes a lead, THE Lead_OS SHALL extract decision-maker hints from owner names, team pages, and LinkedIn profiles
3. WHEN the Enrichment_Agent extracts contacts, THE Lead_OS SHALL normalize phone and email formats and validate email domains
4. WHEN the Enrichment_Agent completes processing, THE Lead_OS SHALL compute enrichment_confidence score from 0 to 1
5. WHEN the Enrichment_Agent completes processing, THE Lead_OS SHALL compute contact_quality_score from 0 to 100
6. WHEN duplicate contacts are detected, THE Enrichment_Agent SHALL deduplicate and merge records

### Requirement 5: Intent and Revenue Leak Detection

**User Story:** As a targeting system, I want to infer which businesses are likely leaking revenue, so that outreach focuses on prospects with verified pain points and high conversion potential.

#### Acceptance Criteria

1. WHEN the Intent_Agent processes a lead, THE Lead_OS SHALL compute intent_score from 0 to 100 based on CTA type, ad activity, and high-ticket patterns
2. WHEN the Intent_Agent processes a lead, THE Lead_OS SHALL compute leak_score from 0 to 100 based on call-only CTAs, missing booking systems, after-hours gaps, and form friction
3. WHEN the Intent_Agent processes a lead, THE Lead_OS SHALL compute reactivation_fit from 0 to 100 based on consideration cycle length and follow-up failure indicators
4. WHEN the Intent_Agent computes scores, THE Lead_OS SHALL generate a plain-English explanation in the why_this_lead field
5. WHEN the Intent_Agent processes a lead, THE Lead_OS SHALL classify speed_to_lead_risk as LOW, MED, or HIGH
6. WHEN the Intent_Agent has access to reviews, THE Lead_OS SHALL mine reviews for phrases indicating missed responses and store evidence snippets with source pointers

### Requirement 6: Precision Audit and Proof Generation

**User Story:** As an outreach system, I want to generate proof artifacts showing specific revenue leaks, so that messages are evidence-backed and credible rather than generic claims.

#### Acceptance Criteria

1. WHEN a lead exceeds the configured score threshold, THE Audit_Agent SHALL trigger a Steel_Task for that lead
2. WHEN the Audit_Agent executes a Steel_Task, THE Lead_OS SHALL open the landing_page_url in a real browser
3. WHEN the browser loads, THE Audit_Agent SHALL interact like a human by scrolling, clicking CTAs, opening forms, revealing phone numbers, and opening booking widgets
4. WHEN the Audit_Agent interacts with the page, THE Lead_OS SHALL extract phone_visibility, form_field_count, booking_link, business_hours, and after_hours_capture capability
5. WHEN the Audit_Agent completes extraction, THE Lead_OS SHALL capture screenshots of the hero section and CTA/form/phone section
6. WHEN screenshots are captured, THE Audit_Agent SHALL save artifacts to object storage and link URLs in the database
7. WHEN the Audit_Agent completes processing, THE Lead_OS SHALL generate a Proof_Pack containing three audit_bullets with leak evidence, specific fix, and conservative upside estimate

### Requirement 7: Weighted Scoring and Disqualification

**User Story:** As a filtering system, I want to apply weighted scoring with ruthless disqualification rules, so that only high-quality prospects receive outreach and spam behavior is prevented.

#### Acceptance Criteria

1. WHEN the Scoring_Agent processes a lead, THE Lead_OS SHALL compute final_score using weighted formula: w1×ad_activity + w2×intent + w3×leak + w4×reactivation + w5×contact_quality + w6×business_size
2. WHEN the Scoring_Agent applies weights, THE Lead_OS SHALL load per-niche weight configuration from the config file
3. WHEN the Scoring_Agent evaluates a lead, THE Lead_OS SHALL apply do_not_contact rules for too_small businesses, owner-only indicators, no_ads_history, emergency-only services, toxic_review_patterns, and missing_valid_contact_path
4. WHEN disqualification rules trigger, THE Scoring_Agent SHALL record the do_not_contact_reason
5. WHEN the Scoring_Agent completes evaluation, THE Lead_OS SHALL assign lead_tier as A (Pitch now), B (Soft pitch), or C (Skip)
6. WHEN a lead is assigned tier C, THE Scoring_Agent SHALL exclude it from outreach queues

### Requirement 8: Proof-Based Outreach Generation

**User Story:** As an outreach system, I want to generate evidence-backed messages with specific observations and conservative impact framing, so that recipients see value rather than spam.

#### Acceptance Criteria

1. WHEN the Outreach_Agent generates a message, THE Lead_OS SHALL include proof screenshots from the Proof_Pack
2. WHEN the Outreach_Agent generates a message, THE Lead_OS SHALL include audit_bullets showing evidence, impact, and offer
3. WHEN the Outreach_Agent generates a message, THE Lead_OS SHALL follow the required structure: observation (evidence), impact (money/loss framing), offer (done-for-you), and single CTA
4. WHEN the Outreach_Agent generates an email, THE Lead_OS SHALL include an opt-out line
5. WHEN the Outreach_Agent generates messages, THE Lead_OS SHALL create A/B variants for testing
6. WHEN the Outreach_Agent prepares messages, THE Lead_OS SHALL create channel-ready payloads for email, DM, and website forms
7. WHEN the Outreach_Agent completes generation, THE Lead_OS SHALL queue messages for human approval by default
8. WHEN auto-send is enabled for A-tier leads, THE Outreach_Agent SHALL send messages automatically only for tier A

### Requirement 9: AI Conversation and Qualification

**User Story:** As a qualification system, I want an AI agent to handle initial conversations and qualify prospects, so that humans only engage when budget, authority, and timeline are confirmed.

#### Acceptance Criteria

1. WHEN the Conversation_Agent receives a reply, THE Lead_OS SHALL engage in qualification dialogue following strict escalation policy
2. WHEN the Conversation_Agent qualifies a prospect, THE Lead_OS SHALL confirm budget, authority, and timeline before escalation
3. WHEN the Conversation_Agent completes a conversation, THE Lead_OS SHALL store the full conversation transcript
4. WHEN the Conversation_Agent extracts information, THE Lead_OS SHALL capture budget_range, role, timeline, and objections as structured entities
5. WHEN the Conversation_Agent identifies objections, THE Lead_OS SHALL generate an objection_summary and suggested_close_angle
6. WHEN the Conversation_Agent reaches pricing negotiation, THE Lead_OS SHALL enforce hard stop rules preventing negotiation beyond configured ranges
7. WHEN the Conversation_Agent makes claims, THE Lead_OS SHALL enforce hard stop rules preventing unverifiable claims

### Requirement 10: Human Escalation and Handoff

**User Story:** As a sales operator, I want qualified conversations escalated to me with full context, so that I can close deals efficiently without repeating discovery work.

#### Acceptance Criteria

1. WHEN the Conversation_Agent confirms qualification criteria, THE Lead_OS SHALL escalate the lead to human review
2. WHEN escalating a lead, THE Lead_OS SHALL provide conversation transcript, extracted entities, objection summary, and suggested close angle
3. WHEN escalating a lead, THE Lead_OS SHALL include the original Proof_Pack and audit bullets
4. WHEN a human accepts escalation, THE Lead_OS SHALL mark the lead as human_owned and prevent further AI interaction

### Requirement 11: Role-Based Access Control

**User Story:** As a security system, I want role-based access control for all agents and actions, so that components can only perform authorized operations.

#### Acceptance Criteria

1. WHEN an agent attempts an action, THE Governance_Layer SHALL verify the agent has permission for that action
2. WHEN the Governance_Layer loads, THE Lead_OS SHALL define which agents can send messages, run Steel tasks, and write to the database
3. WHEN an unauthorized action is attempted, THE Governance_Layer SHALL block the action and log the violation

### Requirement 12: Rate Limiting and Cool-Down

**User Story:** As a compliance system, I want rate limits and cool-down periods enforced across channels and domains, so that the system never exhibits spam behavior.

#### Acceptance Criteria

1. WHEN the Governance_Layer enforces limits, THE Lead_OS SHALL apply per-domain, per-channel, and per-day caps from configuration
2. WHEN negative signals are detected, THE Governance_Layer SHALL activate cool-down periods for affected domains or channels
3. WHEN bounces, spam complaints, or angry replies are detected, THE Governance_Layer SHALL record negative signals and adjust rate limits

### Requirement 13: Audit Logging and Compliance

**User Story:** As a compliance system, I want append-only audit logs for all external actions, so that every operation is traceable and auditable.

#### Acceptance Criteria

1. WHEN any external write occurs, THE Governance_Layer SHALL log the action with actor, timestamp, payload_hash, and idempotency_key
2. WHEN the Governance_Layer stores audit logs, THE Lead_OS SHALL use append-only storage preventing modification or deletion
3. WHEN processing leads, THE Governance_Layer SHALL store region, consent_hints, and enforce policy gates via configuration
4. WHEN handling secrets, THE Governance_Layer SHALL load from environment variables or secret manager and never log secret values

### Requirement 14: Observability and Tracing

**User Story:** As a system operator, I want detailed tracing and metrics for every lead, so that I can diagnose issues, measure performance, and optimize the system.

#### Acceptance Criteria

1. WHEN a lead flows through the graph, THE Lead_OS SHALL trace node_latency, tool_errors, retry_count, llm_tokens, llm_cost, and success_failure_reasons
2. WHEN the Lead_OS completes daily execution, THE Lead_OS SHALL compute metrics including reply_rate, meeting_rate, cost_per_qualified_meeting, false_positive_rate, and human_override_rate
3. WHEN metrics are computed, THE Lead_OS SHALL store them in a time-series format for trend analysis

### Requirement 15: Evaluation and Offline Replay

**User Story:** As a system engineer, I want offline replay and A/B testing capabilities, so that I can validate changes before production deployment and avoid regressions.

#### Acceptance Criteria

1. WHEN the Eval_Harness initializes, THE Lead_OS SHALL load a golden dataset with labeled leads, known outcomes, and known good outreach examples
2. WHEN running offline replay, THE Eval_Harness SHALL execute new scoring or prompt versions on historical leads and compare metrics to baseline
3. WHEN running online A/B tests, THE Eval_Harness SHALL split traffic between variants with configured guardrails
4. WHEN A/B test metrics degrade below threshold, THE Eval_Harness SHALL trigger automatic rollback to the previous version

### Requirement 16: Knowledge and Playbook Management

**User Story:** As a system operator, I want versioned playbooks for outreach examples, objection handling, and niche-specific guidance, so that the system maintains consistency and improves over time.

#### Acceptance Criteria

1. WHEN agents need guidance, THE Lead_OS SHALL retrieve relevant playbook snippets by niche, tier, and channel
2. WHEN playbooks are updated, THE Lead_OS SHALL version them and tie versions to run_id for reproducibility
3. WHEN storing playbooks, THE Lead_OS SHALL include outreach_examples, objection_handling, compliance_rules, and niche_notes

### Requirement 17: Configuration-Driven Architecture

**User Story:** As a system operator, I want all niche-specific logic, scoring weights, and policies defined in configuration files, so that I can adapt the system without code changes.

#### Acceptance Criteria

1. WHEN the Lead_OS initializes, THE Lead_OS SHALL load all niche keywords, geo filters, scoring weights, rate limits, and disqualification rules from configuration files
2. WHEN configuration changes, THE Lead_OS SHALL reload without requiring code deployment
3. WHEN configuration is invalid, THE Lead_OS SHALL fail fast with clear validation errors

### Requirement 18: Database Schema and Migrations

**User Story:** As a system engineer, I want well-defined database schemas with migration support, so that data is structured consistently and schema evolution is managed safely.

#### Acceptance Criteria

1. WHEN the Lead_OS initializes, THE Lead_OS SHALL apply pending database migrations automatically
2. WHEN storing Canonical_Lead records, THE Lead_OS SHALL enforce the defined schema with all required fields
3. WHEN storing execution state, THE Lead_OS SHALL use a separate state table with lead_id, current_stage, last_node, last_error, retry_count, next_run_at, and locks

### Requirement 19: Secrets Management

**User Story:** As a security system, I want secure secrets management for API keys and credentials, so that sensitive data is never exposed in logs or code.

#### Acceptance Criteria

1. WHEN the Lead_OS loads secrets, THE Lead_OS SHALL read from environment variables or a secret manager service
2. WHEN logging operations, THE Lead_OS SHALL never include secret values in log output
3. WHEN secrets are missing, THE Lead_OS SHALL fail fast with clear error messages

### Requirement 20: Error Handling and Resilience

**User Story:** As a production system, I want comprehensive error handling with retries, backoff, and graceful degradation, so that transient failures don't cause data loss or system crashes.

#### Acceptance Criteria

1. WHEN an external API call fails, THE Lead_OS SHALL retry with exponential backoff up to the configured maximum attempts
2. WHEN a component fails repeatedly, THE Lead_OS SHALL activate circuit breakers and route around the failing component
3. WHEN unrecoverable errors occur, THE Lead_OS SHALL log the error, persist lead state, and continue processing other leads
4. WHEN the system encounters rate limits, THE Lead_OS SHALL back off and reschedule affected operations

### Requirement 21: Lead Lifecycle and Aging Management

**User Story:** As a lead management system, I want to track lead contact history and lifecycle state, so that I can avoid annoying prospects, optimize retry timing, and increase conversions through smart reactivation.

#### Acceptance Criteria

1. WHEN a lead is first created, THE Lead_OS SHALL set lead_lifecycle_state to NEW
2. WHEN a lead is contacted, THE Lead_OS SHALL record last_contacted_at timestamp
3. WHEN a lead does not respond within the configured timeframe, THE Lead_OS SHALL transition lead_lifecycle_state to STALE
4. WHEN a stale lead meets reactivation criteria, THE Lead_OS SHALL transition lead_lifecycle_state to REACTIVATABLE
5. WHEN determining contact eligibility, THE Lead_OS SHALL calculate days_since_last_contact and compare against configured minimum_wait_days
6. WHEN a lead is in STALE state, THE Lead_OS SHALL not contact the lead until the reactivation window opens
7. WHEN a lead responds positively, THE Lead_OS SHALL transition lead_lifecycle_state to ENGAGED
8. WHEN a lead is qualified, THE Lead_OS SHALL transition lead_lifecycle_state to QUALIFIED
9. WHEN a lead is closed, THE Lead_OS SHALL transition lead_lifecycle_state to CLOSED_WON or CLOSED_LOST

### Requirement 22: Negative Memory and Reputation Protection

**User Story:** As a compliance and reputation system, I want to remember and respect negative signals, so that the system protects sender reputation, maintains compliance, and remains usable long-term.

#### Acceptance Criteria

1. WHEN a prospect replies with opt-out language, THE Lead_OS SHALL parse the reply and detect opt-out intent
2. WHEN opt-out intent is detected, THE Lead_OS SHALL add the lead to the do_not_contact list with reason OPT_OUT
3. WHEN a prospect replies with angry or negative language, THE Lead_OS SHALL classify the reply as negative_signal
4. WHEN a negative_signal is detected, THE Lead_OS SHALL record the signal with timestamp, channel, and sentiment_score
5. WHEN a lead has negative_signal records, THE Lead_OS SHALL activate cool-down period preventing further contact
6. WHEN a domain accumulates multiple negative signals, THE Lead_OS SHALL reduce outreach volume to similar leads from that domain
7. WHEN an email bounces, THE Lead_OS SHALL record the bounce type (hard/soft) and remove invalid emails from future campaigns
8. WHEN spam complaints are detected, THE Lead_OS SHALL immediately halt outreach to that lead and flag the domain for review
9. WHEN a lead is on the do_not_contact list, THE Lead_OS SHALL block all outreach attempts regardless of score or tier

### Requirement 23: Cost Guardrails and Budget Controls

**User Story:** As a system operator, I want daily cost limits and usage guardrails, so that misconfigured agents cannot cause runaway spending or resource exhaustion.

#### Acceptance Criteria

1. WHEN the Lead_OS initializes, THE Lead_OS SHALL load daily budget limits for llm_tokens, browser_sessions, and scraper_runs from configuration
2. WHEN an agent requests LLM usage, THE Lead_OS SHALL check current daily token usage against the configured limit
3. WHEN daily LLM token limit is reached, THE Lead_OS SHALL block further LLM calls and log a budget_exceeded event
4. WHEN an agent requests a browser session, THE Lead_OS SHALL check current daily session count against the configured limit
5. WHEN daily browser session limit is reached, THE Lead_OS SHALL block further Steel tasks and log a budget_exceeded event
6. WHEN an agent requests a scraper run, THE Lead_OS SHALL check current daily scraper usage against the configured limit
7. WHEN daily scraper limit is reached, THE Lead_OS SHALL block further Apify calls and log a budget_exceeded event
8. WHEN any budget limit is reached, THE Lead_OS SHALL send an alert notification to the operator
9. WHEN the daily reset time occurs, THE Lead_OS SHALL reset all usage counters to zero
