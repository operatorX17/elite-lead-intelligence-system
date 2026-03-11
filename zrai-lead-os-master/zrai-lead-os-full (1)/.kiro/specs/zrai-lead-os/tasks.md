# Implementation Plan: ZRAI Lead OS

## Overview

This implementation plan breaks down the ZRAI Lead OS system into discrete, incremental tasks. The system will be built using Python with LangGraph for orchestration, Supabase for database, Apify for scraping, Steel.dev for browser automation, and pluggable LLM providers. Each task builds on previous work, with property-based tests integrated throughout to validate correctness.

## Tasks

- [x] 1. Project Setup and Infrastructure
  - Initialize Python project with poetry/pip
  - Set up directory structure (src/, tests/, config/, migrations/)
  - Configure environment variables and secrets management
  - Set up Supabase project and connection
  - Create .env.example template
  - _Requirements: 17.1, 19.1_

- [x] 2. Database Schema and Migrations
  - [x] 2.1 Create database migration system
    - Set up Alembic for database migrations
    - Create initial migration structure
    - _Requirements: 18.1_
  
  - [x] 2.2 Implement core tables
    - Create leads table with all fields and indexes
    - Create lead_state table for LangGraph checkpointer
    - Create enrichment_data table
    - Create intent_data table
    - _Requirements: 3.8, 18.2_
  
  - [x] 2.3 Implement scoring and proof tables
    - Create proof_artifacts table
    - Create scoring_results table
    - Create outreach_queue table
    - _Requirements: 6.7, 7.5_
  
  - [x] 2.4 Implement conversation and governance tables
    - Create conversations table
    - Create negative_signals table
    - Create do_not_contact table
    - Create audit_log table
    - _Requirements: 9.3, 13.1, 22.4_
  
  - [x] 2.5 Implement operational tables
    - Create usage_metrics table
    - Create playbooks table
    - Create circuit_breakers table
    - _Requirements: 14.2, 16.2, 20.2_

- [x] 3. Configuration System
  - [x] 3.1 Implement config loader
    - Create YAML config parser
    - Implement config validation with Pydantic models
    - Support environment variable overrides
    - _Requirements: 17.1, 17.3_
  
  - [x] 3.2 Write property test for config validation
    - **Property 42: Configuration Validation**
    - **Validates: Requirements 17.3, 19.3**
    - **File: tests/test_property_config.py**
  
  - [x] 3.3 Implement hot reload mechanism
    - Watch config files for changes
    - Reload without restart
    - _Requirements: 17.2_
  
  - [x] 3.4 Write property test for hot reload
    - **Property 41: Configuration Hot Reload**
    - **Validates: Requirements 17.2**
    - **File: tests/test_property_config.py**

- [x] 4. LangGraph Orchestrator Core
  - [x] 4.1 Implement state model
    - Define LeadState Pydantic model
    - Implement state serialization/deserialization
    - _Requirements: 1.2_
  
  - [x] 4.2 Write property test for state persistence
    - **Property 1: State Persistence Completeness**
    - **Validates: Requirements 1.2, 1.8, 20.3**
    - **File: tests/test_property_state.py**
  
  - [x] 4.3 Implement Supabase checkpointer
    - Create custom LangGraph checkpointer using lead_state table
    - Implement save/load checkpoint methods
    - _Requirements: 1.2_
  
  - [x] 4.4 Define graph nodes and edges
    - Create node functions for each agent
    - Define conditional routing logic
    - Implement graph builder
    - _Requirements: 1.1_
  
  - [x] 4.5 Implement retry logic with exponential backoff
    - Create retry decorator with backoff
    - Configure per-component retry settings
    - _Requirements: 1.3, 20.1_
  
  - [x] 4.6 Write property test for exponential backoff
    - **Property 2: Exponential Backoff Retry Pattern**
    - **Validates: Requirements 1.3, 20.1**
    - **File: tests/test_property_state.py**

- [x] 5. Circuit Breaker System
  - [x] 5.1 Implement circuit breaker class
    - Create CircuitBreaker with CLOSED/OPEN/HALF_OPEN states
    - Implement state transition logic
    - Store state in circuit_breakers table
    - _Requirements: 1.4, 20.2_
  
  - [x] 5.2 Write property test for circuit breaker activation
    - **Property 3: Circuit Breaker Activation**
    - **Validates: Requirements 1.4, 20.2**
    - **File: tests/test_property_circuit_breaker.py**
  
  - [x] 5.3 Integrate circuit breakers with graph nodes
    - Wrap Steel.dev calls with circuit breaker
    - Wrap Apify calls with circuit breaker
    - Implement routing around open circuits
    - _Requirements: 1.4_

- [x] 6. Idempotency and Concurrency Control
  - [x] 6.1 Implement idempotency key manager
    - Generate idempotency keys for external writes
    - Check for duplicate operations
    - Store keys in audit_log
    - _Requirements: 1.5_
  
  - [x] 6.2 Write property test for idempotency
    - **Property 4: Idempotency Guarantee**
    - **Validates: Requirements 1.5**
    - **File: tests/test_property_idempotency.py**
  
  - [x] 6.3 Implement parallelism controller
    - Limit concurrent lead processing
    - Use semaphore or queue-based approach
    - _Requirements: 1.7_
  
  - [x] 6.4 Write property test for concurrency limits
    - **Property 5: Concurrent Execution Limits**
    - **Validates: Requirements 1.7**
    - **File: tests/test_property_idempotency.py**

- [x] 7. CLI Interface
  - [x] 7.1 Implement CLI framework
    - Use Click or Typer for CLI
    - Create command structure
    - _Requirements: 2.1_
  
  - [x] 7.2 Implement run_daily command
    - Load config
    - Execute full pipeline
    - Output execution summary
    - _Requirements: 2.1, 2.5_
  
  - [x] 7.3 Implement replay_run command
    - Load historical run by run_id
    - Replay with same inputs
    - _Requirements: 2.2_
  
  - [x] 7.4 Write property test for replay determinism
    - **Property 6: Replay Determinism**
    - **Validates: Requirements 2.2**
    - **File: tests/test_property_cli.py**
  
  - [x] 7.5 Implement resume_failed command
    - Query failed leads since timestamp
    - Resume from last checkpoint
    - _Requirements: 2.3_
  
  - [x] 7.6 Write property test for failed execution resumption
    - **Property 7: Failed Execution Resumption**
    - **Validates: Requirements 2.3**
    - **File: tests/test_property_cli.py**
  
  - [x] 7.7 Implement dry_run command
    - Simulate execution without side effects
    - Mock external writes
    - _Requirements: 2.4_
  
  - [x] 7.8 Write property test for dry run side effect prevention
    - **Property 8: Dry Run Side Effect Prevention**
    - **Validates: Requirements 2.4**
    - **File: tests/test_property_cli.py**

- [ ] 8. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 9. Discovery Agent (Apify Integration)
  - [x] 9.1 Implement Apify client wrapper
    - Create Apify API client
    - Implement actor execution methods
    - Handle rate limits and errors
    - _Requirements: 3.1, 3.3_
  
  - [x] 9.2 Implement Meta Ads Library scraper
    - Call apify/meta-ads-library-scraper
    - Parse and extract required fields
    - _Requirements: 3.1, 3.2_
  
  - [x] 9.3 Write property test for Meta Ads extraction completeness
    - **Property 11: Extraction Field Completeness (Meta Ads)**
    - **Validates: Requirements 3.2**
    - **File: tests/test_property_discovery.py**
  
  - [x] 9.4 Implement Google Maps scraper
    - Call apify/google-maps-scraper
    - Parse and extract required fields
    - _Requirements: 3.3, 3.4_
  
  - [x] 9.5 Write property test for Google Maps extraction completeness
    - **Property 11: Extraction Field Completeness (Google Maps)**
    - **Validates: Requirements 3.4**
    - **File: tests/test_property_discovery.py**
  
  - [x] 9.6 Implement website crawler
    - Call apify/website-content-crawler
    - Extract contact information
    - _Requirements: 3.5_
  
  - [x] 9.7 Implement Canonical Lead creation
    - Transform raw data to Canonical Lead schema
    - Validate all required fields
    - Deduplicate leads
    - _Requirements: 3.7, 3.8_
  
  - [x] 9.8 Write property test for canonical lead schema compliance
    - **Property 10: Canonical Lead Schema Compliance**
    - **Validates: Requirements 3.7, 3.8, 18.2**
    - **File: tests/test_property_discovery.py**

- [x] 10. Enrichment Agent
  - [x] 10.1 Implement tech signal extraction
    - Detect booking providers (Calendly, Acuity, etc.)
    - Detect CRM hints (HubSpot, Salesforce, etc.)
    - Detect chat widgets (Intercom, Drift, etc.)
    - _Requirements: 4.1_
  
  - [x] 10.2 Implement decision-maker extraction
    - Parse team pages for names
    - Extract LinkedIn profiles
    - _Requirements: 4.2_
  
  - [x] 10.3 Implement contact normalization
    - Normalize phone numbers (libphonenumber)
    - Validate email domains (DNS MX records)
    - _Requirements: 4.3_
  
  - [x] 10.4 Write property test for contact normalization consistency
    - **Property 12: Contact Normalization Consistency**
    - **Validates: Requirements 4.3**
    - **File: tests/test_property_enrichment.py**
  
  - [x] 10.5 Implement enrichment scoring
    - Compute enrichment_confidence
    - Compute contact_quality_score
    - _Requirements: 4.4, 4.5_
  
  - [x] 10.6 Write property test for score range validity
    - **Property 13: Score Range Validity**
    - **Validates: Requirements 4.4, 4.5, 5.1, 5.2, 5.3**
    - **File: tests/test_property_enrichment.py**
  
  - [x] 10.7 Implement deduplication logic
    - Detect duplicate contacts
    - Merge records
    - _Requirements: 4.6_

- [x] 11. Intent Agent
  - [x] 11.1 Implement intent scoring algorithm
    - Score based on CTA type, ad activity, high-ticket patterns
    - _Requirements: 5.1_
  
  - [x] 11.2 Implement leak scoring algorithm
    - Score based on call-only CTAs, missing booking, after-hours gaps
    - _Requirements: 5.2_
  
  - [x] 11.3 Implement reactivation fit scoring
    - Score based on consideration cycle and follow-up failure
    - _Requirements: 5.3_
  
  - [x] 11.4 Implement speed-to-lead risk classification
    - Classify as LOW/MED/HIGH
    - _Requirements: 5.5_
  
  - [x] 11.5 Write property test for risk classification validity
    - **Property 14: Risk Classification Validity**
    - **Validates: Requirements 5.5**
    - **File: tests/test_property_enrichment.py**
  
  - [x] 11.6 Implement review mining
    - Extract negative phrases from reviews
    - Store evidence snippets
    - _Requirements: 5.6_
  
  - [x] 11.7 Implement why_this_lead explanation generator
    - Generate plain-English explanation
    - _Requirements: 5.4_

- [ ] 12. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 13. Audit Agent (Steel.dev Integration)
  - [x] 13.1 Implement Steel.dev client wrapper
    - Create Steel API client
    - Implement browser session management
    - _Requirements: 6.2_
  
  - [x] 13.2 Implement page interaction logic
    - Navigate to landing page
    - Scroll, click CTAs, open forms
    - _Requirements: 6.3_
  
  - [x] 13.3 Implement extraction logic
    - Extract phone visibility, form fields, booking links
    - _Requirements: 6.4_
  
  - [x] 13.4 Write property test for extraction completeness
    - **Property 11: Extraction Field Completeness (Audit)**
    - **Validates: Requirements 6.4**
    - **File: tests/test_property_audit.py**
  
  - [x] 13.5 Implement screenshot capture
    - Capture hero section
    - Capture CTA/form/phone section
    - _Requirements: 6.5_
  
  - [x] 13.6 Implement S3 storage integration
    - Upload screenshots to S3
    - Store URLs in database
    - _Requirements: 6.6_
  
  - [x] 13.7 Write property test for screenshot artifact round trip
    - **Property 20: Screenshot Artifact Round Trip**
    - **Validates: Requirements 6.6**
    - **File: tests/test_property_audit.py**
  
  - [x] 13.8 Implement Proof Pack generation
    - Generate 3 audit bullets (leak, fix, upside)
    - _Requirements: 6.7_
  
  - [x] 13.9 Write property test for proof pack structure
    - **Property 19: Proof Pack Structure Completeness**
    - **Validates: Requirements 6.7**
    - **File: tests/test_property_audit.py**

- [x] 14. Scoring Agent
  - [x] 14.1 Implement weighted scoring formula
    - Load weights from config
    - Compute final_score
    - _Requirements: 7.1, 7.2_
  
  - [x] 14.2 Write property test for weighted scoring correctness
    - **Property 18: Weighted Scoring Formula Correctness**
    - **Validates: Requirements 7.1**
    - **File: tests/test_property_scoring.py**
  
  - [x] 14.3 Implement disqualification rules
    - Apply all do_not_contact rules
    - Record reasons
    - _Requirements: 7.3, 7.4_
  
  - [x] 14.4 Write property test for disqualification reason recording
    - **Property 17: Disqualification Reason Recording**
    - **Validates: Requirements 7.4**
    - **File: tests/test_property_scoring.py**
  
  - [x] 14.5 Implement lead tier assignment
    - Assign A/B/C based on score thresholds
    - _Requirements: 7.5_
  
  - [x] 14.6 Write property test for tier assignment validity
    - **Property 15: Lead Tier Assignment Validity**
    - **Validates: Requirements 7.5**
    - **File: tests/test_property_scoring.py**
  
  - [x] 14.7 Implement tier C exclusion logic
    - Exclude tier C from outreach queues
    - _Requirements: 7.6_
  
  - [x] 14.8 Write property test for tier C exclusion
    - **Property 16: Tier C Exclusion**
    - **Validates: Requirements 7.6**
    - **File: tests/test_property_scoring.py**

- [x] 15. Outreach Agent
  - [x] 15.1 Implement LLM client wrapper
    - Support OpenAI, Anthropic, Gemini
    - Implement model routing
    - _Requirements: 8.1_
  
  - [x] 15.2 Implement message structure generator
    - Generate observation, impact, offer, CTA sections
    - _Requirements: 8.3_
  
  - [x] 15.3 Write property test for message structure compliance
    - **Property 21: Outreach Message Structure Compliance**
    - **Validates: Requirements 8.3**
    - **File: tests/test_property_outreach.py**
  
  - [x] 15.4 Implement opt-out line insertion
    - Add opt-out line to all emails
    - _Requirements: 8.4_
  
  - [x] 15.5 Write property test for email opt-out inclusion
    - **Property 22: Email Opt-Out Inclusion**
    - **Validates: Requirements 8.4**
    - **File: tests/test_property_outreach.py**
  
  - [x] 15.6 Implement A/B variant generation
    - Generate 2 variants per lead
    - _Requirements: 8.5_
  
  - [x] 15.7 Write property test for A/B variant generation
    - **Property 23: A/B Variant Generation**
    - **Validates: Requirements 8.5**
    - **File: tests/test_property_outreach.py**
  
  - [x] 15.8 Implement channel payload creation
    - Create email, DM, form payloads
    - _Requirements: 8.6_
  
  - [x] 15.9 Implement approval queue logic
    - Queue messages for approval by default
    - Support auto-send for tier A
    - _Requirements: 8.7, 8.8_
  
  - [x] 15.10 Write property test for approval queue default behavior
    - **Property 24: Approval Queue Default Behavior**
    - **Validates: Requirements 8.7**
    - **File: tests/test_property_outreach.py**

- [ ] 16. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 17. Conversation Agent
  - [x] 17.1 Implement conversation state machine
    - Track conversation flow
    - Manage BANT criteria collection
    - _Requirements: 9.1, 9.2_
  
  - [x] 17.2 Implement discovery question generator
    - Generate contextual questions
    - _Requirements: 9.1_
  
  - [x] 17.3 Implement entity extraction
    - Extract budget_range, role, timeline, objections
    - _Requirements: 9.4_
  
  - [x] 17.4 Implement escalation criteria checker
    - Verify BANT completeness
    - _Requirements: 9.2_
  
  - [x] 17.5 Write property test for BANT qualification completeness
    - **Property 25: BANT Qualification Completeness**
    - **Validates: Requirements 9.2, 10.1**
    - **File: tests/test_property_conversation.py**
  
  - [x] 17.6 Implement conversation transcript storage
    - Store full transcript with timestamps
    - _Requirements: 9.3_
  
  - [x] 17.7 Write property test for conversation transcript persistence
    - **Property 26: Conversation Transcript Persistence**
    - **Validates: Requirements 9.3**
    - **File: tests/test_property_conversation.py**
  
  - [x] 17.8 Implement objection handling
    - Generate objection summary
    - Generate suggested close angle
    - _Requirements: 9.5_
  
  - [x] 17.9 Implement hard stop rules
    - Prevent pricing negotiation beyond ranges
    - Prevent unverifiable claims
    - _Requirements: 9.6, 9.7_

- [x] 18. Escalation System
  - [x] 18.1 Implement escalation package builder
    - Collect transcript, entities, objections, proof pack
    - _Requirements: 10.2, 10.3_
  
  - [x] 18.2 Write property test for escalation context completeness
    - **Property 27: Escalation Context Completeness**
    - **Validates: Requirements 10.2, 10.3**
    - **File: tests/test_property_conversation.py**
  
  - [x] 18.3 Implement human ownership transfer
    - Mark lead as human_owned
    - Prevent further AI interaction
    - _Requirements: 10.4_
  
  - [x] 18.4 Write property test for human ownership transfer
    - **Property 28: Human Ownership Transfer**
    - **Validates: Requirements 10.4**
    - **File: tests/test_property_conversation.py**

- [x] 19. Governance Layer
  - [x] 19.1 Implement RBAC system
    - Define agent permissions
    - Verify permissions before actions
    - _Requirements: 11.1, 11.2_
  
  - [x] 19.2 Write property test for permission verification
    - **Property 29: Permission Verification**
    - **Validates: Requirements 11.1**
    - **File: tests/test_property_governance.py**
  
  - [x] 19.3 Write property test for unauthorized action blocking
    - **Property 30: Unauthorized Action Blocking**
    - **Validates: Requirements 11.3**
    - **File: tests/test_property_governance.py**
  
  - [x] 19.4 Implement rate limiter
    - Enforce per-domain, per-channel, per-day caps
    - _Requirements: 12.1_
  
  - [x] 19.5 Write property test for rate limit enforcement
    - **Property 31: Rate Limit Enforcement**
    - **Validates: Requirements 12.1**
    - **File: tests/test_property_governance.py**
  
  - [x] 19.6 Implement negative signal detector
    - Detect opt-outs, angry replies, bounces, spam complaints
    - _Requirements: 22.1, 22.3_
  
  - [x] 19.7 Implement cool-down manager
    - Activate cool-downs on negative signals
    - _Requirements: 12.2, 22.5, 22.6_
  
  - [x] 19.8 Write property test for negative signal cool-down activation
    - **Property 32: Negative Signal Cool-Down Activation**
    - **Validates: Requirements 12.2, 22.5, 22.6**
    - **File: tests/test_property_governance.py**
  
  - [x] 19.9 Write property test for negative signal recording completeness
    - **Property 33: Negative Signal Recording Completeness**
    - **Validates: Requirements 22.4, 22.7, 22.8**
    - **File: tests/test_property_governance.py**
  
  - [x] 19.10 Implement audit logger
    - Log all external writes
    - Ensure append-only storage
    - _Requirements: 13.1, 13.2_
  
  - [x] 19.11 Write property test for audit log completeness
    - **Property 34: Audit Log Completeness**
    - **Validates: Requirements 13.1**
    - **File: tests/test_property_governance.py**
  
  - [x] 19.12 Write property test for audit log immutability
    - **Property 35: Audit Log Immutability**
    - **Validates: Requirements 13.2**
    - **File: tests/test_property_governance.py**
  
  - [x] 19.13 Implement secret redaction
    - Redact secrets from logs
    - _Requirements: 13.4, 19.2_
  
  - [x] 19.14 Write property test for secret redaction
    - **Property 36: Secret Redaction**
    - **Validates: Requirements 13.4, 19.2**
    - **File: tests/test_property_governance.py**

- [x] 20. Lead Lifecycle Management
  - [x] 20.1 Implement lifecycle state machine
    - Define valid state transitions
    - _Requirements: 21.1, 21.3, 21.4, 21.7, 21.8, 21.9_
  
  - [x] 20.2 Write property test for lifecycle state machine validity
    - **Property 43: Lead Lifecycle State Machine Validity**
    - **Validates: Requirements 21.1, 21.3, 21.4, 21.7, 21.8, 21.9**
    - **File: tests/test_property_lifecycle.py**
  
  - [x] 20.3 Implement contact timestamp recording
    - Update last_contacted_at on contact events
    - _Requirements: 21.2_
  
  - [x] 20.4 Write property test for contact timestamp recording
    - **Property 44: Contact Timestamp Recording**
    - **Validates: Requirements 21.2**
    - **File: tests/test_property_lifecycle.py**
  
  - [x] 20.5 Implement contact eligibility calculator
    - Calculate days_since_last_contact
    - Compare against minimum_wait_days
    - _Requirements: 21.5_
  
  - [x] 20.6 Write property test for contact eligibility calculation
    - **Property 46: Contact Eligibility Calculation**
    - **Validates: Requirements 21.5**
    - **File: tests/test_property_lifecycle.py**
  
  - [x] 20.7 Implement stale lead contact prevention
    - Block contact for STALE leads
    - _Requirements: 21.6_
  
  - [x] 20.8 Write property test for stale lead contact prevention
    - **Property 45: Stale Lead Contact Prevention**
    - **Validates: Requirements 21.6**
    - **File: tests/test_property_lifecycle.py**

- [x] 21. Opt-Out and DNC Management
  - [x] 21.1 Implement opt-out detector
    - Parse replies for opt-out keywords
    - _Requirements: 22.1_
  
  - [x] 21.2 Implement DNC list manager
    - Add leads to do_not_contact table
    - Enforce DNC blocking
    - _Requirements: 22.2, 22.9_
  
  - [x] 21.3 Write property test for opt-out detection and enforcement
    - **Property 47: Opt-Out Detection and Enforcement**
    - **Validates: Requirements 22.1, 22.2, 22.9**
    - **File: tests/test_property_lifecycle.py**

- [x] 22. Budget Control System
  - [x] 22.1 Implement usage tracker
    - Track LLM tokens, browser sessions, scraper runs
    - Store in usage_metrics table
    - _Requirements: 23.2, 23.4, 23.6_
  
  - [x] 22.2 Implement budget limit enforcer
    - Check usage against limits
    - Block requests when limit reached
    - _Requirements: 23.3, 23.5, 23.7_
  
  - [x] 22.3 Write property test for budget limit enforcement
    - **Property 48: Budget Limit Enforcement**
    - **Validates: Requirements 23.2, 23.3, 23.4, 23.5, 23.6, 23.7**
    - **File: tests/test_property_budget.py**
  
  - [x] 22.4 Implement budget alert system
    - Send alerts when limits reached
    - _Requirements: 23.8_
  
  - [x] 22.5 Write property test for budget alert notification
    - **Property 49: Budget Alert Notification**
    - **Validates: Requirements 23.8**
    - **File: tests/test_property_budget.py**
  
  - [x] 22.6 Implement daily counter reset
    - Reset counters at configured time
    - _Requirements: 23.9_
  
  - [x] 22.7 Write property test for daily usage counter reset
    - **Property 50: Daily Usage Counter Reset**
    - **Validates: Requirements 23.9**
    - **File: tests/test_property_budget.py**

- [ ] 23. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 24. Observability and Metrics
  - [x] 24.1 Implement execution tracer
    - Trace node latency, errors, retries, costs
    - _Requirements: 14.1_
  
  - [x] 24.2 Write property test for execution trace completeness
    - **Property 37: Execution Trace Completeness**
    - **Validates: Requirements 14.1**
    - **File: tests/test_property_observability.py**
  
  - [x] 24.3 Implement metrics calculator
    - Compute reply_rate, meeting_rate, cost_per_qualified_meeting, etc.
    - _Requirements: 14.2_
  
  - [x] 24.4 Write property test for daily metrics computation
    - **Property 38: Daily Metrics Computation**
    - **Validates: Requirements 14.2**
    - **File: tests/test_property_observability.py**
  
  - [x] 24.5 Implement time-series storage
    - Store metrics with timestamps
    - _Requirements: 14.3_

- [x] 25. Playbook System
  - [x] 25.1 Implement playbook storage
    - Store playbooks with versioning
    - _Requirements: 16.2, 16.3_
  
  - [x] 25.2 Implement playbook retrieval
    - Retrieve by niche, tier, channel
    - _Requirements: 16.1_
  
  - [x] 25.3 Write property test for playbook retrieval relevance
    - **Property 39: Playbook Retrieval Relevance**
    - **Validates: Requirements 16.1**
    - **File: tests/test_property_observability.py**
  
  - [x] 25.4 Write property test for playbook versioning
    - **Property 40: Playbook Versioning**
    - **Validates: Requirements 16.2**
    - **File: tests/test_property_observability.py**
  
  - [x] 25.5 Implement Pinecone integration for RAG
    - Store playbook embeddings
    - Implement semantic search
    - _Requirements: 16.1_

- [x] 26. Eval Harness
  - [x] 26.1 Create golden dataset
    - Collect 100+ labeled leads
    - Include known outcomes
    - _Requirements: 15.1_
  
  - [x] 26.2 Implement offline replay
    - Run new versions on historical data
    - Compare metrics to baseline
    - _Requirements: 15.2_
  
  - [x] 26.3 Write property test for offline replay consistency
    - **Property 6: Replay Determinism (extended)**
    - **Validates: Requirements 15.2**
    - **File: tests/test_property_observability.py**
  
  - [x] 26.4 Implement A/B testing framework
    - Split traffic between variants
    - Track metrics
    - _Requirements: 15.3_
  
  - [x] 26.5 Write property test for A/B traffic splitting
    - **Property 6: Replay Determinism (extended)**
    - **Validates: Requirements 15.3**
    - **File: tests/test_property_observability.py**
  
  - [x] 26.6 Implement automatic rollback
    - Monitor metrics
    - Rollback on degradation
    - _Requirements: 15.4_

- [x] 27. Kill Switch System
  - [x] 27.1 Implement global kill switch
    - Check environment variable
    - Gracefully halt execution
    - _Requirements: 1.6_
  
  - [x] 27.2 Implement per-module kill switches
    - Load from config
    - Disable specific modules
    - _Requirements: 1.6_

- [x] 28. Integration and Wiring
  - [x] 28.1 Wire all agents into LangGraph
    - Connect all nodes
    - Configure conditional routing
    - _Requirements: 1.1_
  
  - [x] 28.2 Implement end-to-end pipeline
    - Test full flow from discovery to escalation
    - _Requirements: 2.1_
  
  - [x] 28.3 Create example configuration files
    - Create niches.yaml example
    - Create policies.yaml example
    - Create agents.yaml example
    - _Requirements: 17.1_
  
  - [x] 28.4 Write README and runbook
    - Document daily run process
    - Document monitoring and debugging
    - Document replay and rollback
    - **File: README.md, docs/RUNBOOK.md**
    - _Requirements: All_

- [x] 29. Final Checkpoint - Ensure all tests pass
  - All property tests written in tests/ directory
  - Run with: `pytest tests/ -v`

## Notes

- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties
- Unit tests validate specific examples and edge cases
- Implementation language: Python with LangGraph, Supabase, Apify, Steel.dev
- All property-based tests are required for comprehensive correctness validation
