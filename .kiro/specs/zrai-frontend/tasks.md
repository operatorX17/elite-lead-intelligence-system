# Implementation Plan: ZRAI Frontend Integration

## Overview

This plan implements the integration between the Vercel Chat SDK frontend and the ZRAI Lead OS Python backend. The implementation follows a bottom-up approach: first the API bridge, then tools, then artifacts, Chat SDK feature customizations, and finally wiring everything together.

**CRITICAL**: This implementation utilizes EVERY feature of the Vercel Chat SDK - no capability is left unused.

## Tasks

- [x] 1. Set up ZRAI infrastructure in Chat SDK
  - [x] 1.1 Create ZRAI types and constants
    - Create `lib/zrai/types.ts` with Lead, Outreach, Proof, Metrics interfaces
    - Create `lib/zrai/constants.ts` with API URLs and configuration
    - Create `lib/zrai/file-handlers.ts` for file upload processing
    - _Requirements: 1.1, 1.4, 24.1, 24.2_
  
  - [x] 1.2 Create ZRAI API client
    - Create `lib/zrai/client.ts` with fetch wrapper for ZRAI endpoints
    - Implement authentication header injection
    - Implement error handling and response parsing
    - _Requirements: 1.2, 1.4, 1.5_

- [x] 2. Implement FastAPI Bridge endpoints
  - [x] 2.1 Create discovery endpoint
    - Create `app/(chat)/api/zrai/discover/route.ts`
    - Implement POST handler that calls ZRAI Discovery Agent
    - Return lead list with run_id
    - _Requirements: 2.1, 2.2, 2.3_
  
  - [x] 2.2 Create enrichment endpoint
    - Create `app/(chat)/api/zrai/enrich/route.ts`
    - Implement POST handler that calls ZRAI Enrichment Agent
    - Return enriched lead data
    - _Requirements: 3.1, 3.2, 3.4_
  
  - [x] 2.3 Create intent endpoint
    - Create `app/(chat)/api/zrai/intent/route.ts`
    - Implement POST handler that calls ZRAI Intent Agent
    - Return intent signals and revenue leak score
    - _Requirements: 4.1, 4.2, 4.3_
  
  - [x] 2.4 Create proof endpoint
    - Create `app/(chat)/api/zrai/proof/route.ts`
    - Implement POST handler that calls ZRAI Audit Agent
    - Return proof artifact URLs
    - _Requirements: 5.1, 5.2_
  
  - [x] 2.5 Create scoring endpoint
    - Create `app/(chat)/api/zrai/score/route.ts`
    - Implement POST handler that calls ZRAI Scoring Agent
    - Return ranked leads with scores
    - _Requirements: 6.1, 6.2, 6.3_
  
  - [x] 2.6 Create outreach endpoint
    - Create `app/(chat)/api/zrai/outreach/route.ts`
    - Implement POST handler for draft and send actions
    - Call ZRAI Outreach Agent
    - _Requirements: 7.1, 7.2, 8.2_
  
  - [x] 2.7 Create conversation endpoint
    - Create `app/(chat)/api/zrai/conversation/route.ts`
    - Implement POST handler that calls ZRAI Conversation Agent
    - Return AI response and conversation state
    - _Requirements: 9.1, 9.2, 9.3_
  
  - [x] 2.8 Create governance endpoint
    - Create `app/(chat)/api/zrai/governance/route.ts`
    - Implement GET handler that returns governance status
    - Include rate limits, budgets, circuit breakers
    - _Requirements: 11.1, 11.2, 11.3, 11.4_
  
  - [x] 2.9 Create A/B test endpoint
    - Create `app/(chat)/api/zrai/ab-test/route.ts`
    - Implement POST handler for test management
    - Call ZRAI Eval Agent
    - _Requirements: 12.1, 12.2_
  
  - [x] 2.10 Create leads data endpoint
    - Create `app/(chat)/api/zrai/leads/route.ts`
    - Implement GET handler for lead data retrieval
    - Support filtering and pagination
    - _Requirements: 13.1, 13.2, 13.3_
  
  - [x] 2.11 Create metrics endpoint
    - Create `app/(chat)/api/zrai/metrics/route.ts`
    - Implement GET handler for system metrics
    - Return aggregated metrics data
    - _Requirements: 18.1, 18.2, 18.3, 18.4_

  - [x] 2.12 Create import endpoint for bulk operations
    - Create `app/(chat)/api/zrai/import/route.ts`
    - Implement POST handler for CSV/file imports
    - Parse and validate uploaded files
    - Return import results with success/failure counts
    - _Requirements: 24.3, 24.4, 34.6_

- [ ] 3. Checkpoint - Verify bridge endpoints
  - Test each endpoint with curl/Postman
  - Ensure authentication works
  - Verify error handling
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Implement ZRAI Tools
  - [x] 4.1 Create discover leads tool
    - Create `lib/ai/tools/zrai/discover-leads.ts`
    - Define input schema (niche, geo, limit)
    - Implement execute function calling bridge
    - Trigger lead-list artifact on success
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_
  
  - [x] 4.2 Create enrich lead tool
    - Create `lib/ai/tools/zrai/enrich-lead.ts`
    - Define input schema (lead_id)
    - Implement execute function calling bridge
    - Trigger lead-card artifact on success
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_
  
  - [x] 4.3 Create analyze intent tool
    - Create `lib/ai/tools/zrai/analyze-intent.ts`
    - Define input schema (lead_id)
    - Implement execute function calling bridge
    - Trigger lead-card artifact with intent data
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_
  
  - [x] 4.4 Create generate proof tool
    - Create `lib/ai/tools/zrai/generate-proof.ts`
    - Define input schema (lead_id, proof_type)
    - Implement execute function calling bridge
    - Trigger proof-viewer artifact on success
    - _Requirements: 5.1, 5.2, 5.3, 5.5_
  
  - [x] 4.5 Create score leads tool
    - Create `lib/ai/tools/zrai/score-leads.ts`
    - Define input schema (filters)
    - Implement execute function calling bridge
    - Trigger scoring-dashboard artifact on success
    - _Requirements: 6.1, 6.2, 6.3, 6.4_
  
  - [x] 4.6 Create draft outreach tool
    - Create `lib/ai/tools/zrai/draft-outreach.ts`
    - Define input schema (lead_id, channel)
    - Implement execute function calling bridge with action='draft'
    - Trigger outreach-draft artifact on success
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6_
  
  - [x] 4.7 Create send outreach tool (approval required)
    - Create `lib/ai/tools/zrai/send-outreach.ts`
    - Set needsApproval: true
    - Define input schema (lead_id, channel, message)
    - Implement execute function calling bridge with action='send'
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6_
  
  - [x] 4.8 Create handle conversation tool
    - Create `lib/ai/tools/zrai/handle-conversation.ts`
    - Define input schema (lead_id, message)
    - Implement execute function calling bridge
    - Trigger conversation-thread artifact on success
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_
  
  - [x] 4.9 Create approve escalation tool (approval required)
    - Create `lib/ai/tools/zrai/approve-escalation.ts`
    - Set needsApproval: true
    - Define input schema (lead_id, reason)
    - Implement execute function calling bridge
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_
  
  - [x] 4.10 Create check governance tool
    - Create `lib/ai/tools/zrai/check-governance.ts`
    - Define input schema (optional filters)
    - Implement execute function calling bridge
    - Trigger metrics-dashboard artifact on success
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5_
  
  - [x] 4.11 Create manage A/B test tool
    - Create `lib/ai/tools/zrai/manage-ab-test.ts`
    - Define input schema (action, test_params)
    - Implement execute function calling bridge
    - Trigger metrics-dashboard artifact for results
    - _Requirements: 12.1, 12.2, 12.3, 12.5_
  
  - [x] 4.12 Create run pipeline tool
    - Create `lib/ai/tools/zrai/run-pipeline.ts`
    - Define input schema (mode, options)
    - Implement execute function calling bridge
    - Return run status
    - _Requirements: 19.1, 19.2, 19.3, 19.4, 19.5_
  
  - [x] 4.13 Create import leads tool
    - Create `lib/ai/tools/zrai/import-leads.ts`
    - Define input schema for file handling
    - Implement CSV parsing and validation
    - Trigger lead-sheet artifact on success
    - _Requirements: 24.3, 24.4, 34.1_
  
  - [x] 4.14 Create analyze screenshot tool
    - Create `lib/ai/tools/zrai/analyze-screenshot.ts`
    - Define input schema for image analysis
    - Implement intent signal detection from screenshots
    - Trigger proof-viewer artifact on success
    - _Requirements: 24.3, 33.1, 33.5_
  
  - [x] 4.15 Create tools index
    - Create `lib/ai/tools/zrai/index.ts`
    - Export all ZRAI tools
    - _Requirements: 1.1_

- [ ] 5. Checkpoint - Verify tools work
  - Test each tool in isolation
  - Verify approval flow for send_outreach and approve_escalation
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Implement ZRAI Artifacts
  - [x] 6.1 Create lead-card artifact
    - Create `artifacts/zrai/lead-card/client.tsx`
    - Create `artifacts/zrai/lead-card/server.ts`
    - Display lead details, score, contacts, intent signals
    - Add quick actions (enrich, score, draft outreach)
    - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5, 13.6_
  
  - [x] 6.2 Create lead-list artifact
    - Create `artifacts/zrai/lead-list/client.tsx`
    - Create `artifacts/zrai/lead-list/server.ts`
    - Display list of leads with summary info
    - Support filtering and sorting
    - _Requirements: 2.4, 6.4_
  
  - [x] 6.3 Create proof-viewer artifact
    - Create `artifacts/zrai/proof-viewer/client.tsx`
    - Create `artifacts/zrai/proof-viewer/server.ts`
    - Display screenshots at full resolution
    - Support zoom, pan, download
    - _Requirements: 14.1, 14.2, 14.3, 14.4, 14.5_
  
  - [x] 6.4 Create scoring-dashboard artifact
    - Create `artifacts/zrai/scoring-dashboard/client.tsx`
    - Create `artifacts/zrai/scoring-dashboard/server.ts`
    - Display ranked leads with score breakdown
    - Support filtering and sorting
    - _Requirements: 15.1, 15.2, 15.3, 15.4, 15.5_
  
  - [x] 6.5 Create outreach-draft artifact
    - Create `artifacts/zrai/outreach-draft/client.tsx`
    - Create `artifacts/zrai/outreach-draft/server.ts`
    - Display message with 4-part structure
    - Support inline editing
    - Add send action triggering approval
    - _Requirements: 16.1, 16.2, 16.3, 16.4, 16.5, 16.6_
  
  - [x] 6.6 Create conversation-thread artifact
    - Create `artifacts/zrai/conversation-thread/client.tsx`
    - Create `artifacts/zrai/conversation-thread/server.ts`
    - Display messages in chronological order
    - Distinguish AI vs human messages
    - Show qualification signals
    - _Requirements: 17.1, 17.2, 17.3, 17.4, 17.5_
  
  - [x] 6.7 Create metrics-dashboard artifact
    - Create `artifacts/zrai/metrics-dashboard/client.tsx`
    - Create `artifacts/zrai/metrics-dashboard/server.ts`
    - Display key metrics with trends
    - Show budget consumption
    - Show agent health status
    - _Requirements: 18.1, 18.2, 18.3, 18.4, 18.5_
  
  - [x] 6.8 Create lead-sheet artifact
    - Create `artifacts/zrai/lead-sheet/client.tsx`
    - Create `artifacts/zrai/lead-sheet/server.ts`
    - Display leads in spreadsheet format
    - Support sorting, filtering, inline editing
    - Support CSV export and bulk actions
    - _Requirements: 34.1, 34.2, 34.3, 34.4, 34.5, 34.6_
  
  - [x] 6.9 Register artifacts
    - Update `lib/artifacts/server.ts` to include ZRAI artifacts
    - Update `components/artifact.tsx` to include ZRAI artifact definitions
    - Update `lib/db/schema.ts` to add ZRAI artifact kinds
    - _Requirements: 13.6, 14.1, 15.1, 16.1, 17.1, 18.1, 34.1_

- [ ] 7. Checkpoint - Verify artifacts render
  - Test each artifact with mock data
  - Verify streaming updates work
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. Customize Chat SDK Features for ZRAI
  - [x] 8.1 Create ZRAI greeting component
    - Create `components/zrai-greeting.tsx`
    - Display "Welcome to ZRAI Lead OS" with branding
    - Show current pipeline stats (leads discovered, outreach sent)
    - Show active alerts (budget warnings, circuit breakers)
    - Add smooth animations on load
    - _Requirements: 31.1, 31.2, 31.3, 31.4, 31.5_
  
  - [x] 8.2 Create ZRAI suggested actions
    - Create `components/zrai-suggested-actions.tsx`
    - Display 4 ZRAI-specific quick actions
    - Include: "Discover leads in [niche]", "Show pipeline dashboard", "Check outreach queue", "Review governance"
    - Wire actions to corresponding tools
    - _Requirements: 25.1, 25.2, 25.3, 25.4, 25.5, 25.6_
  
  - [x] 8.3 Integrate ZRAI greeting into chat
    - Update `components/messages.tsx` to use ZRAI greeting
    - Replace default greeting with ZRAI-branded version
    - _Requirements: 31.1, 31.2_
  
  - [x] 8.4 Integrate ZRAI suggested actions
    - Update `components/multimodal-input.tsx` to use ZRAI suggestions
    - Replace default suggestions with ZRAI-specific actions
    - _Requirements: 25.1, 25.6_

- [x] 9. Implement multimodal input enhancements
  - [x] 9.1 Add file upload handlers for ZRAI
    - Create `lib/zrai/file-handlers.ts`
    - Implement CSV parsing for lead imports
    - Implement image analysis for screenshots
    - Validate file types and sizes
    - _Requirements: 24.1, 24.2, 24.4, 24.6_
  
  - [x] 9.2 Integrate file handlers with multimodal input
    - Update file upload flow to detect ZRAI file types
    - Route CSV files to import tool
    - Route images to analyze-screenshot tool
    - Show upload progress and previews
    - _Requirements: 24.3, 24.5_

- [x] 10. Wire tools into chat route
  - [x] 10.1 Update chat route with ZRAI tools
    - Import all ZRAI tools in `app/(chat)/api/chat/route.ts`
    - Add ZRAI tools to the tools object
    - Update experimental_activeTools to include ZRAI tools
    - _Requirements: 1.1, 20.1_
  
  - [x] 10.2 Update system prompt for ZRAI
    - Update `lib/ai/prompts.ts` with ZRAI context
    - Add ZRAI capabilities description
    - Add workflow guidance
    - Add approval warnings
    - Include geolocation context
    - _Requirements: 20.1, 20.2, 20.3, 20.4, 20.5, 35.2_

- [x] 11. Implement error handling
  - [x] 11.1 Create error utilities
    - Create `lib/zrai/errors.ts` with error classes
    - Implement user-friendly error messages
    - Implement error logging
    - _Requirements: 21.1, 21.2, 21.3, 21.5_
  
  - [x] 11.2 Add error handling to tools
    - Wrap tool execute functions with try-catch
    - Return structured error responses
    - Suggest recovery actions
    - _Requirements: 21.1, 21.2, 21.4_

- [x] 12. Implement real-time updates
  - [x] 12.1 Add streaming to bridge endpoints
    - Implement SSE streaming for long operations
    - Stream partial results as available
    - _Requirements: 22.1, 22.2_
  
  - [x] 12.2 Add progress indicators to tools
    - Show progress during discovery, enrichment, proof generation
    - Update artifacts in real-time
    - _Requirements: 22.1, 22.3_

- [ ] 13. Checkpoint - Full integration test
  - Test complete discovery → outreach flow
  - Test approval flows
  - Test error scenarios
  - Test file uploads (CSV, images)
  - Ensure all tests pass, ask the user if questions arise.

- [x] 14. Add authentication integration
  - [x] 14.1 Integrate with ZRAI auth
    - Pass user session to bridge endpoints
    - Implement RBAC checks
    - _Requirements: 23.1, 23.2, 23.4_
  
  - [x] 14.2 Add audit logging
    - Log all tool invocations with user identity
    - Include action, parameters, result
    - _Requirements: 23.3_

- [x] 15. Implement Chat SDK advanced features
  - [x] 15.1 Configure resumable streams
    - Verify Redis configuration for resumable streams
    - Test stream resumption after disconnection
    - Add reconnection status UI
    - _Requirements: 29.1, 29.2, 29.3, 29.4, 29.5_
  
  - [x] 15.2 Implement vote system integration
    - Ensure vote data is stored correctly
    - Connect vote data to ZRAI Eval Agent for training
    - Prevent duplicate votes
    - _Requirements: 27.1, 27.2, 27.3, 27.4, 27.5_
  
  - [x] 15.3 Configure reasoning model support
    - Verify reasoning models work with ZRAI
    - Display thinking/reasoning process
    - Disable tools and attachments for reasoning models
    - _Requirements: 26.1, 26.2, 26.3, 26.4, 26.5_
  
  - [x] 15.4 Implement visibility controls
    - Default to private for ZRAI chats
    - Add warning before making lead data public
    - Generate shareable links for public chats
    - _Requirements: 30.1, 30.2, 30.3, 30.4, 30.5_
  
  - [x] 15.5 Implement geolocation context
    - Capture geolocation from request headers
    - Include in system prompt for geo-relevant suggestions
    - Use for timezone-aware outreach scheduling
    - _Requirements: 35.1, 35.2, 35.3, 35.4, 35.5_
  
  - [x] 15.6 Implement document versioning for artifacts
    - Track all artifact versions
    - Add version navigation in footer
    - Support diff view between versions
    - Support reverting to previous versions
    - _Requirements: 36.1, 36.2, 36.3, 36.4, 36.5_
  
  - [x] 15.7 Implement toolbar actions for ZRAI artifacts
    - Add contextual toolbar to each ZRAI artifact
    - Lead_Card: Enrich, Score, Draft Outreach
    - Outreach_Draft: Send, Edit, Regenerate
    - Add keyboard shortcuts
    - _Requirements: 37.1, 37.2, 37.3, 37.4, 37.5, 37.6_

- [ ] 16. Final checkpoint
  - Run full E2E test suite
  - Verify all 37 requirements met
  - Test all Chat SDK features are utilized
  - Ensure all tests pass, ask the user if questions arise.

- [x] 17. Property-based tests
  - [x] 17.1 Write property test for tool approval enforcement
    - **Property 1: Tool Approval Enforcement**
    - **Validates: Requirements 8.1, 8.2, 8.3, 10.1, 10.2, 10.3**
  
  - [x] 17.2 Write property test for authentication
    - **Property 2: Bridge Request Authentication**
    - **Validates: Requirements 1.4, 23.1, 23.3**
  
  - [x] 17.3 Write property test for governance enforcement
    - **Property 3: Governance Rule Enforcement**
    - **Validates: Requirements 1.6, 11.2, 11.3, 11.4**
  
  - [x] 17.4 Write property test for error message safety
    - **Property 5: Error Message Safety**
    - **Validates: Requirements 21.1, 21.5**
  
  - [x] 17.5 Write property test for multimodal input validation
    - **Property 11: Multimodal Input Validation**
    - **Validates: Requirements 24.1, 24.2, 24.6**
  
  - [x] 17.6 Write property test for vote uniqueness
    - **Property 13: Vote Uniqueness**
    - **Validates: Requirements 27.2, 27.3**
  
  - [x] 17.7 Write property test for visibility privacy default
    - **Property 15: Visibility Privacy Default**
    - **Validates: Requirements 30.4, 30.5**

## Notes

- All tasks are required for comprehensive implementation
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties
- The FastAPI bridge can be implemented as Next.js API routes initially, then migrated to a separate Python service if needed for performance
- **ALL 18 Chat SDK features are utilized** - see Feature Integration Map in design.md
- Total: 37 requirements, 15 correctness properties, 17 major task groups
