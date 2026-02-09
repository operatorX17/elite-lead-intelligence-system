# Requirements Document: ZRAI Frontend Integration

## Introduction

This document defines the requirements for integrating the ZRAI Lead OS backend (Python/LangGraph) with the Vercel Chat SDK frontend. The goal is to provide a powerful chat-based interface where users can control all 9 ZRAI agents, view lead data through custom artifacts, and approve sensitive operations like outreach sending.

**CRITICAL**: This spec utilizes EVERY feature of the Vercel Chat SDK - no capability is left unused.

## Glossary

- **Chat_SDK**: Vercel's open-source Next.js template for building AI chatbot applications
- **ZRAI_Backend**: The Python LangGraph-based lead intelligence system with 9 agents
- **Tool**: A function the AI can invoke to perform actions (discover leads, send outreach, etc.)
- **Artifact**: A workspace-like UI component for displaying complex data (lead cards, dashboards)
- **Tool_Approval**: Human-in-the-loop pattern requiring user confirmation before execution
- **FastAPI_Bridge**: API layer connecting Chat SDK to ZRAI Python backend
- **Lead**: A business entity being prospected
- **Outreach**: Communication sent to a lead (email, LinkedIn, SMS)
- **Proof_Artifact**: Screenshot or recording from Steel.dev audit
- **Resumable_Stream**: Redis-backed stream that survives disconnections
- **Reasoning_Model**: AI model with extended thinking capabilities (Claude 3.7 Sonnet, Grok Code)
- **Multimodal_Input**: Chat input supporting text, images, and file attachments
- **Vote_System**: User feedback mechanism for upvoting/downvoting AI responses

---

## Requirements

### Requirement 1: FastAPI Bridge API

**User Story:** As a frontend developer, I want a FastAPI bridge that connects Chat SDK tools to the ZRAI Python backend, so that chat commands trigger real agent actions.

#### Acceptance Criteria

1. THE FastAPI_Bridge SHALL expose REST endpoints for each ZRAI agent operation
2. WHEN a Chat SDK tool calls the bridge, THE FastAPI_Bridge SHALL invoke the corresponding LangGraph node
3. THE FastAPI_Bridge SHALL stream responses back using Server-Sent Events (SSE)
4. THE FastAPI_Bridge SHALL authenticate requests using API keys or JWT tokens
5. IF a bridge request fails, THEN THE FastAPI_Bridge SHALL return structured error responses with error codes
6. THE FastAPI_Bridge SHALL respect all ZRAI governance rules (rate limits, circuit breakers, budgets)

---

### Requirement 2: Lead Discovery Tool

**User Story:** As a user, I want to discover leads through chat commands, so that I can find prospects without using the CLI.

#### Acceptance Criteria

1. WHEN a user requests lead discovery, THE Discovery_Tool SHALL accept niche, geo, and limit parameters
2. THE Discovery_Tool SHALL call the ZRAI Discovery Agent via FastAPI bridge
3. WHEN discovery completes, THE Discovery_Tool SHALL return a summary of leads found
4. THE Discovery_Tool SHALL trigger the Lead_List_Artifact to display results
5. IF discovery fails, THEN THE Discovery_Tool SHALL return a user-friendly error message

---

### Requirement 3: Lead Enrichment Tool

**User Story:** As a user, I want to enrich lead data through chat, so that I can get contact information and context.

#### Acceptance Criteria

1. WHEN a user requests enrichment for a lead, THE Enrichment_Tool SHALL accept lead_id as parameter
2. THE Enrichment_Tool SHALL call the ZRAI Enrichment Agent via FastAPI bridge
3. WHEN enrichment completes, THE Enrichment_Tool SHALL update the Lead_Card_Artifact with new data
4. THE Enrichment_Tool SHALL return enriched contact details (email, phone, LinkedIn)
5. IF enrichment fails, THEN THE Enrichment_Tool SHALL indicate which data could not be found

---

### Requirement 4: Intent Analysis Tool

**User Story:** As a user, I want to analyze lead intent through chat, so that I can understand their revenue leak signals.

#### Acceptance Criteria

1. WHEN a user requests intent analysis, THE Intent_Tool SHALL accept lead_id as parameter
2. THE Intent_Tool SHALL call the ZRAI Intent Agent via FastAPI bridge
3. WHEN analysis completes, THE Intent_Tool SHALL return intent signals and revenue leak score
4. THE Intent_Tool SHALL trigger the Intent_Signals_Artifact to visualize findings
5. IF no intent signals found, THEN THE Intent_Tool SHALL indicate the lead has low intent

---

### Requirement 5: Proof Generation Tool

**User Story:** As a user, I want to generate proof artifacts through chat, so that I can see screenshots of lead websites.

#### Acceptance Criteria

1. WHEN a user requests proof generation, THE Proof_Tool SHALL accept lead_id and proof_type parameters
2. THE Proof_Tool SHALL call the ZRAI Audit Agent (Steel.dev) via FastAPI bridge
3. WHEN proof generation completes, THE Proof_Tool SHALL trigger the Proof_Viewer_Artifact
4. THE Proof_Viewer_Artifact SHALL display screenshots, recordings, or extracted data
5. IF proof generation fails, THEN THE Proof_Tool SHALL indicate the failure reason (site blocked, timeout, etc.)

---

### Requirement 6: Lead Scoring Tool

**User Story:** As a user, I want to score leads through chat, so that I can prioritize my outreach.

#### Acceptance Criteria

1. WHEN a user requests lead scoring, THE Scoring_Tool SHALL accept optional filters (niche, min_score)
2. THE Scoring_Tool SHALL call the ZRAI Scoring Agent via FastAPI bridge
3. WHEN scoring completes, THE Scoring_Tool SHALL return ranked leads with scores
4. THE Scoring_Tool SHALL trigger the Scoring_Dashboard_Artifact to visualize rankings
5. THE Scoring_Dashboard_Artifact SHALL show score breakdown by category (intent, fit, engagement)

---

### Requirement 7: Outreach Drafting Tool

**User Story:** As a user, I want to draft outreach messages through chat, so that I can review before sending.

#### Acceptance Criteria

1. WHEN a user requests outreach drafting, THE Draft_Outreach_Tool SHALL accept lead_id and channel parameters
2. THE Draft_Outreach_Tool SHALL call the ZRAI Outreach Agent via FastAPI bridge
3. WHEN drafting completes, THE Draft_Outreach_Tool SHALL trigger the Outreach_Draft_Artifact
4. THE Outreach_Draft_Artifact SHALL display the message with edit capabilities
5. THE Outreach_Draft_Artifact SHALL show the 4-part structure (Observation, Impact, Offer, CTA)
6. THE Draft_Outreach_Tool SHALL NOT send the message - only draft it

---

### Requirement 8: Outreach Sending Tool (Approval Required)

**User Story:** As a user, I want to approve outreach before it's sent, so that I maintain control over communications.

#### Acceptance Criteria

1. THE Send_Outreach_Tool SHALL have needsApproval set to true
2. WHEN a user approves sending, THE Send_Outreach_Tool SHALL call the ZRAI Outreach Agent send function
3. WHEN a user denies sending, THE Send_Outreach_Tool SHALL cancel the operation and log the denial
4. THE Send_Outreach_Tool SHALL display the full message content in the approval UI
5. THE Send_Outreach_Tool SHALL show the recipient, channel, and any warnings
6. IF sending fails, THEN THE Send_Outreach_Tool SHALL return the error and not retry automatically

---

### Requirement 9: Conversation Handling Tool

**User Story:** As a user, I want to handle lead conversations through chat, so that I can qualify responses.

#### Acceptance Criteria

1. WHEN a user requests conversation handling, THE Conversation_Tool SHALL accept lead_id and message parameters
2. THE Conversation_Tool SHALL call the ZRAI Conversation Agent via FastAPI bridge
3. WHEN handling completes, THE Conversation_Tool SHALL return the AI-generated response
4. THE Conversation_Tool SHALL trigger the Conversation_Thread_Artifact to show history
5. IF escalation is needed, THEN THE Conversation_Tool SHALL indicate human handoff is required

---

### Requirement 10: Escalation Approval Tool (Approval Required)

**User Story:** As a user, I want to approve escalations before they happen, so that I control when leads go to humans.

#### Acceptance Criteria

1. THE Escalation_Tool SHALL have needsApproval set to true
2. WHEN escalation is triggered, THE Escalation_Tool SHALL display the lead context and reason
3. WHEN a user approves escalation, THE Escalation_Tool SHALL create the escalation record
4. WHEN a user denies escalation, THE Escalation_Tool SHALL keep the lead in AI handling
5. THE Escalation_Tool SHALL show the recommended human assignee if available

---

### Requirement 11: Governance Status Tool

**User Story:** As a user, I want to check governance status through chat, so that I can monitor rate limits and budgets.

#### Acceptance Criteria

1. WHEN a user requests governance status, THE Governance_Tool SHALL return current limits and usage
2. THE Governance_Tool SHALL show rate limit status per channel (email, LinkedIn, SMS)
3. THE Governance_Tool SHALL show budget consumption (LLM tokens, Apify runs, browser sessions)
4. THE Governance_Tool SHALL show circuit breaker states for each agent
5. THE Governance_Tool SHALL trigger the Metrics_Dashboard_Artifact for visualization

---

### Requirement 12: A/B Test Management Tool

**User Story:** As a user, I want to manage A/B tests through chat, so that I can optimize outreach performance.

#### Acceptance Criteria

1. WHEN a user requests A/B test creation, THE AB_Test_Tool SHALL accept test parameters (variants, metrics)
2. THE AB_Test_Tool SHALL call the ZRAI Eval Agent via FastAPI bridge
3. WHEN viewing results, THE AB_Test_Tool SHALL trigger the AB_Results_Artifact
4. THE AB_Results_Artifact SHALL show variant performance with statistical significance
5. THE AB_Test_Tool SHALL support starting, pausing, and concluding tests

---

### Requirement 13: Lead Card Artifact

**User Story:** As a user, I want to see lead details in a rich card format, so that I can quickly understand a lead.

#### Acceptance Criteria

1. THE Lead_Card_Artifact SHALL display lead name, company, and contact info
2. THE Lead_Card_Artifact SHALL show the current lead score and status
3. THE Lead_Card_Artifact SHALL display intent signals and revenue leak indicators
4. THE Lead_Card_Artifact SHALL show outreach history and conversation summary
5. THE Lead_Card_Artifact SHALL provide quick actions (enrich, score, draft outreach)
6. THE Lead_Card_Artifact SHALL update in real-time when data changes

---

### Requirement 14: Proof Viewer Artifact

**User Story:** As a user, I want to view proof artifacts in a dedicated viewer, so that I can see screenshots and recordings.

#### Acceptance Criteria

1. THE Proof_Viewer_Artifact SHALL display Steel.dev screenshots at full resolution
2. THE Proof_Viewer_Artifact SHALL support multiple proof types (screenshot, recording, extracted_data)
3. THE Proof_Viewer_Artifact SHALL show proof metadata (timestamp, URL, proof_type)
4. THE Proof_Viewer_Artifact SHALL allow zooming and panning on images
5. THE Proof_Viewer_Artifact SHALL provide download capability for proof files

---

### Requirement 15: Scoring Dashboard Artifact

**User Story:** As a user, I want to see lead scores in a dashboard, so that I can prioritize my pipeline.

#### Acceptance Criteria

1. THE Scoring_Dashboard_Artifact SHALL display leads ranked by total score
2. THE Scoring_Dashboard_Artifact SHALL show score breakdown (intent, fit, engagement, recency)
3. THE Scoring_Dashboard_Artifact SHALL support filtering by niche, geo, and score range
4. THE Scoring_Dashboard_Artifact SHALL highlight disqualified leads with reasons
5. THE Scoring_Dashboard_Artifact SHALL provide sorting by any score component

---

### Requirement 16: Outreach Draft Artifact

**User Story:** As a user, I want to edit outreach drafts in a dedicated editor, so that I can refine messages before sending.

#### Acceptance Criteria

1. THE Outreach_Draft_Artifact SHALL display the message with syntax highlighting
2. THE Outreach_Draft_Artifact SHALL show the 4-part structure sections clearly
3. THE Outreach_Draft_Artifact SHALL allow inline editing of the message
4. THE Outreach_Draft_Artifact SHALL show character/word count and channel limits
5. THE Outreach_Draft_Artifact SHALL provide a "Send" action that triggers approval flow
6. THE Outreach_Draft_Artifact SHALL show personalization variables highlighted

---

### Requirement 17: Conversation Thread Artifact

**User Story:** As a user, I want to see conversation history in a thread view, so that I can follow lead interactions.

#### Acceptance Criteria

1. THE Conversation_Thread_Artifact SHALL display messages in chronological order
2. THE Conversation_Thread_Artifact SHALL distinguish between AI and human messages
3. THE Conversation_Thread_Artifact SHALL show message timestamps and channels
4. THE Conversation_Thread_Artifact SHALL highlight qualification signals in messages
5. THE Conversation_Thread_Artifact SHALL show the current conversation status (active, qualified, escalated)

---

### Requirement 18: Metrics Dashboard Artifact

**User Story:** As a user, I want to see system metrics in a dashboard, so that I can monitor performance.

#### Acceptance Criteria

1. THE Metrics_Dashboard_Artifact SHALL display key metrics (reply_rate, meeting_rate, cost_per_meeting)
2. THE Metrics_Dashboard_Artifact SHALL show daily/weekly/monthly trends
3. THE Metrics_Dashboard_Artifact SHALL display budget consumption with alerts
4. THE Metrics_Dashboard_Artifact SHALL show agent performance (latency, success rate)
5. THE Metrics_Dashboard_Artifact SHALL highlight anomalies and warnings

---

### Requirement 19: Run Management Tool

**User Story:** As a user, I want to manage pipeline runs through chat, so that I can control execution.

#### Acceptance Criteria

1. WHEN a user requests a daily run, THE Run_Tool SHALL trigger the ZRAI pipeline
2. THE Run_Tool SHALL support dry_run mode that doesn't perform external writes
3. THE Run_Tool SHALL support replay_run for specific run_ids
4. THE Run_Tool SHALL support resume_failed for recovering from errors
5. THE Run_Tool SHALL return run status with success/failure counts

---

### Requirement 20: System Prompt Integration

**User Story:** As a user, I want the AI to understand ZRAI context, so that it can help me effectively.

#### Acceptance Criteria

1. THE System_Prompt SHALL include ZRAI capabilities and available tools
2. THE System_Prompt SHALL explain the lead pipeline stages
3. THE System_Prompt SHALL guide users on common workflows
4. THE System_Prompt SHALL warn about approval-required actions
5. THE System_Prompt SHALL reference governance rules and limits

---

### Requirement 21: Error Handling and Recovery

**User Story:** As a user, I want clear error messages and recovery options, so that I can handle failures gracefully.

#### Acceptance Criteria

1. WHEN a tool fails, THE System SHALL display a user-friendly error message
2. THE System SHALL suggest recovery actions when possible
3. THE System SHALL log errors to the audit system
4. IF a circuit breaker is open, THEN THE System SHALL indicate when to retry
5. THE System SHALL not expose internal error details to users

---

### Requirement 22: Real-time Updates

**User Story:** As a user, I want real-time updates on long-running operations, so that I know progress.

#### Acceptance Criteria

1. WHEN a long operation starts, THE System SHALL show a progress indicator
2. THE System SHALL stream partial results as they become available
3. THE System SHALL update artifacts in real-time during operations
4. IF an operation is cancelled, THEN THE System SHALL stop gracefully
5. THE System SHALL show estimated time remaining when possible

---

### Requirement 23: Authentication and Authorization

**User Story:** As a user, I want secure access to ZRAI features, so that my data is protected.

#### Acceptance Criteria

1. THE System SHALL require authentication before accessing ZRAI tools
2. THE System SHALL enforce RBAC rules from the ZRAI Governance Agent
3. THE System SHALL audit all tool invocations with user identity
4. THE System SHALL respect user permissions for sensitive operations
5. IF a user lacks permission, THEN THE System SHALL deny the action with explanation

---

## Chat SDK Feature Utilization Requirements

### Requirement 24: Multimodal Input Support

**User Story:** As a user, I want to upload images and files in chat, so that I can share lead screenshots, documents, and data with the AI.

#### Acceptance Criteria

1. THE System SHALL support image uploads (PNG, JPG, GIF, WebP)
2. THE System SHALL support document uploads (PDF, CSV, Excel)
3. WHEN a user uploads a lead screenshot, THE System SHALL analyze it for intent signals
4. WHEN a user uploads a CSV, THE System SHALL parse it for bulk lead import
5. THE System SHALL display upload progress and preview attachments
6. THE System SHALL validate file types and sizes before upload

---

### Requirement 25: ZRAI Suggested Actions

**User Story:** As a user, I want ZRAI-specific quick actions when starting a chat, so that I can quickly access common workflows.

#### Acceptance Criteria

1. THE Suggested_Actions SHALL display 4 ZRAI-specific actions on empty chat
2. THE Suggested_Actions SHALL include "Discover leads in [niche]"
3. THE Suggested_Actions SHALL include "Show my pipeline dashboard"
4. THE Suggested_Actions SHALL include "Check today's outreach queue"
5. THE Suggested_Actions SHALL include "Review governance status"
6. WHEN a user clicks a suggested action, THE System SHALL execute the corresponding tool

---

### Requirement 26: Reasoning Model Support

**User Story:** As a user, I want to use reasoning models for complex lead analysis, so that I get deeper insights.

#### Acceptance Criteria

1. THE Model_Selector SHALL include reasoning models (Claude 3.7 Sonnet Thinking, Grok Code)
2. WHEN a reasoning model is selected, THE System SHALL display thinking/reasoning process
3. THE System SHALL show reasoning in a collapsible component
4. WHEN a reasoning model is selected, THE System SHALL disable file attachments (model limitation)
5. THE System SHALL use reasoning models for complex scoring and intent analysis

---

### Requirement 27: Vote/Feedback System

**User Story:** As a user, I want to upvote/downvote AI responses, so that the system can learn from my feedback.

#### Acceptance Criteria

1. THE System SHALL display upvote/downvote buttons on AI responses
2. WHEN a user votes, THE System SHALL store the vote in the database
3. THE System SHALL prevent duplicate votes on the same message
4. THE Vote_Data SHALL be used for ZRAI Eval Agent training data
5. THE System SHALL show visual feedback when a vote is recorded

---

### Requirement 28: Message Edit Capability

**User Story:** As a user, I want to edit my messages, so that I can correct mistakes without starting over.

#### Acceptance Criteria

1. THE System SHALL display an edit button on user messages (on hover)
2. WHEN a user edits a message, THE System SHALL regenerate the AI response
3. THE System SHALL preserve message history for audit purposes
4. THE Edit_UI SHALL show inline editing with save/cancel options

---

### Requirement 29: Resumable Streams

**User Story:** As a user, I want my chat to resume after disconnection, so that I don't lose progress on long operations.

#### Acceptance Criteria

1. THE System SHALL use Redis-backed resumable streams
2. WHEN a user reconnects, THE System SHALL resume from the last checkpoint
3. THE System SHALL handle network interruptions gracefully
4. THE System SHALL show reconnection status to the user
5. Long-running ZRAI operations (discovery, enrichment) SHALL be resumable

---

### Requirement 30: Chat Visibility Control

**User Story:** As a user, I want to control chat visibility, so that I can share or keep private my lead research.

#### Acceptance Criteria

1. THE System SHALL support private and public chat visibility
2. THE Visibility_Selector SHALL be accessible from the chat header
3. WHEN a chat is public, THE System SHALL generate a shareable link
4. THE System SHALL default to private visibility for ZRAI chats
5. THE System SHALL warn before making a chat with sensitive lead data public

---

### Requirement 31: ZRAI Greeting Component

**User Story:** As a user, I want a ZRAI-branded greeting when starting a new chat, so that I know I'm in the lead intelligence system.

#### Acceptance Criteria

1. THE Greeting SHALL display "Welcome to ZRAI Lead OS"
2. THE Greeting SHALL show a brief description of capabilities
3. THE Greeting SHALL display current pipeline stats (leads discovered, outreach sent)
4. THE Greeting SHALL show any active alerts (budget warnings, circuit breakers)
5. THE Greeting SHALL animate smoothly on load

---

### Requirement 32: Code Execution for Data Analysis

**User Story:** As a user, I want to run Python code for custom lead analysis, so that I can perform advanced data operations.

#### Acceptance Criteria

1. THE System SHALL support Python code execution via Pyodide (WASM)
2. THE Code_Artifact SHALL execute lead analysis scripts
3. THE System SHALL support matplotlib for lead data visualization
4. THE Console SHALL display code output and errors
5. THE System SHALL sandbox code execution for security
6. THE System SHALL provide ZRAI data access helpers in the code environment

---

### Requirement 33: Image Artifact for Proof Display

**User Story:** As a user, I want to view and edit proof screenshots in an image artifact, so that I can annotate and highlight key findings.

#### Acceptance Criteria

1. THE Image_Artifact SHALL display Steel.dev screenshots
2. THE Image_Artifact SHALL support zoom and pan
3. THE Image_Artifact SHALL support basic annotations (highlight, arrow, text)
4. THE Image_Artifact SHALL support downloading the image
5. THE Image_Artifact SHALL show image metadata (URL, timestamp, dimensions)

---

### Requirement 34: Sheet Artifact for Lead Data

**User Story:** As a user, I want to view and edit lead data in a spreadsheet format, so that I can work with bulk data efficiently.

#### Acceptance Criteria

1. THE Sheet_Artifact SHALL display lead lists in spreadsheet format
2. THE Sheet_Artifact SHALL support sorting and filtering
3. THE Sheet_Artifact SHALL support inline editing of lead data
4. THE Sheet_Artifact SHALL support CSV export
5. THE Sheet_Artifact SHALL highlight scored leads with color coding
6. THE Sheet_Artifact SHALL support bulk actions (enrich all, score all)

---

### Requirement 35: Geolocation Context

**User Story:** As a user, I want the AI to know my location context, so that it can suggest relevant local leads and geo-specific strategies.

#### Acceptance Criteria

1. THE System SHALL capture user geolocation from request headers
2. THE System_Prompt SHALL include user location context
3. WHEN discovering leads, THE System SHALL suggest geo-relevant niches
4. THE System SHALL respect user privacy and allow location opt-out
5. THE Geolocation SHALL be used for timezone-aware outreach scheduling

---

### Requirement 36: Document Versioning

**User Story:** As a user, I want to see version history of artifacts, so that I can track changes and revert if needed.

#### Acceptance Criteria

1. THE System SHALL track all artifact versions
2. THE Version_Footer SHALL show version count and navigation
3. THE System SHALL support viewing previous versions
4. THE System SHALL support diff view between versions
5. THE System SHALL allow reverting to previous versions

---

### Requirement 37: Toolbar Actions for Artifacts

**User Story:** As a user, I want quick toolbar actions on artifacts, so that I can perform common operations efficiently.

#### Acceptance Criteria

1. EACH Artifact SHALL have a contextual toolbar
2. THE Toolbar SHALL appear on hover/focus
3. THE Toolbar SHALL include artifact-specific actions
4. FOR Lead_Card_Artifact, THE Toolbar SHALL include "Enrich", "Score", "Draft Outreach"
5. FOR Outreach_Draft_Artifact, THE Toolbar SHALL include "Send", "Edit", "Regenerate"
6. THE Toolbar SHALL support keyboard shortcuts
