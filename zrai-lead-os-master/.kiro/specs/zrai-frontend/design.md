# Design Document: ZRAI Frontend Integration

## Overview

This design document describes the architecture for integrating the ZRAI Lead OS Python backend with the Vercel Chat SDK frontend. The integration enables users to control all 9 ZRAI agents through a conversational interface, view data through custom artifacts, and approve sensitive operations before execution.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Vercel Chat SDK (Next.js)                        │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                        Chat Interface                            │    │
│  │  - useChat hook with streaming                                   │    │
│  │  - Tool approval UI (Deny/Allow buttons)                         │    │
│  │  - Message history                                               │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                      ZRAI Tools (lib/ai/tools/)                  │    │
│  │  - discover_leads, enrich_lead, analyze_intent                   │    │
│  │  - generate_proof, score_leads, draft_outreach                   │    │
│  │  - send_outreach (needsApproval), handle_conversation            │    │
│  │  - approve_escalation (needsApproval), check_governance          │    │
│  │  - manage_ab_test, run_pipeline                                  │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                    ZRAI Artifacts (artifacts/)                   │    │
│  │  - lead-card, proof-viewer, scoring-dashboard                    │    │
│  │  - outreach-draft, conversation-thread, metrics-dashboard        │    │
│  └─────────────────────────────────────────────────────────────────┘    │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │ HTTP/SSE
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      FastAPI Bridge (api/zrai/)                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  POST /api/zrai/discover     - Trigger discovery                 │    │
│  │  POST /api/zrai/enrich       - Enrich lead                       │    │
│  │  POST /api/zrai/intent       - Analyze intent                    │    │
│  │  POST /api/zrai/proof        - Generate proof                    │    │
│  │  POST /api/zrai/score        - Score leads                       │    │
│  │  POST /api/zrai/outreach     - Draft/send outreach               │    │
│  │  POST /api/zrai/conversation - Handle conversation               │    │
│  │  GET  /api/zrai/governance   - Get governance status             │    │
│  │  POST /api/zrai/ab-test      - Manage A/B tests                  │    │
│  │  POST /api/zrai/run          - Trigger pipeline runs             │    │
│  │  GET  /api/zrai/leads        - Get lead data                     │    │
│  │  GET  /api/zrai/metrics      - Get metrics                       │    │
│  └─────────────────────────────────────────────────────────────────┘    │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │ Python SDK calls
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    ZRAI Lead OS (Python/LangGraph)                       │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  Discovery → Enrichment → Intent → Audit → Scoring               │    │
│  │  → Outreach → Conversation → Governance → Eval                   │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  Supabase (PostgreSQL) | Pinecone (RAG) | Apify | Steel.dev     │    │
│  └─────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────┘
```

## Components and Interfaces

### 1. ZRAI Tools

Tools are defined in `frontend/lib/ai/tools/zrai/` and registered in the chat route.

#### Tool Interface
```typescript
interface ZRAIToolConfig {
  name: string;
  description: string;
  inputSchema: z.ZodSchema;
  needsApproval?: boolean;
  execute: (input: any, context: ToolContext) => Promise<ToolResult>;
}

interface ToolContext {
  session: Session;
  dataStream: UIMessageStreamWriter;
  bridgeUrl: string;
}

interface ToolResult {
  success: boolean;
  data?: any;
  error?: string;
  artifactTrigger?: {
    kind: ArtifactKind;
    data: any;
  };
}
```

#### Tool Definitions

| Tool | Description | Approval | Artifact |
|------|-------------|----------|----------|
| `discoverLeads` | Find leads by niche/geo | No | lead-list |
| `enrichLead` | Get contact info | No | lead-card |
| `analyzeIntent` | Detect revenue leaks | No | lead-card |
| `generateProof` | Take screenshots | No | proof-viewer |
| `scoreLeads` | Rank leads | No | scoring-dashboard |
| `draftOutreach` | Create message | No | outreach-draft |
| `sendOutreach` | Send message | **Yes** | - |
| `handleConversation` | Process reply | No | conversation-thread |
| `approveEscalation` | Escalate to human | **Yes** | - |
| `checkGovernance` | Get limits/status | No | metrics-dashboard |
| `manageABTest` | Create/view tests | No | metrics-dashboard |
| `runPipeline` | Trigger runs | No | - |

### 2. ZRAI Artifacts

Artifacts are defined in `frontend/artifacts/zrai/` with client and server components.

#### Artifact Interface
```typescript
interface ZRAIArtifact<K extends string, M = any> {
  kind: K;
  description: string;
  initialize?: (props: InitProps) => Promise<void>;
  onStreamPart?: (props: StreamProps<M>) => void;
  content: (props: ContentProps<M>) => React.ReactNode;
  actions?: ArtifactAction[];
  toolbar?: ToolbarAction[];
}
```

#### Artifact Definitions

| Artifact | Purpose | Data Source |
|----------|---------|-------------|
| `lead-card` | Display single lead | `/api/zrai/leads/:id` |
| `lead-list` | Display lead list | `/api/zrai/leads` |
| `proof-viewer` | Show screenshots | `/api/zrai/proof/:id` |
| `scoring-dashboard` | Lead rankings | `/api/zrai/score` |
| `outreach-draft` | Edit messages | Tool response |
| `conversation-thread` | Message history | `/api/zrai/conversations/:id` |
| `metrics-dashboard` | System metrics | `/api/zrai/metrics` |

### 3. FastAPI Bridge

The bridge is implemented as Next.js API routes that call the Python backend.

#### Bridge Endpoints

```typescript
// POST /api/zrai/discover
interface DiscoverRequest {
  niche: string;
  geo?: string;
  limit?: number;
}

interface DiscoverResponse {
  success: boolean;
  leads: Lead[];
  count: number;
  run_id: string;
}

// POST /api/zrai/enrich
interface EnrichRequest {
  lead_id: string;
}

interface EnrichResponse {
  success: boolean;
  lead: Lead;
  enrichment: EnrichmentData;
}

// POST /api/zrai/outreach
interface OutreachRequest {
  lead_id: string;
  channel: 'email' | 'linkedin' | 'sms';
  action: 'draft' | 'send';
  message?: string; // For send action
}

interface OutreachResponse {
  success: boolean;
  message: OutreachMessage;
  sent?: boolean;
}
```

## Data Models

### Lead Model
```typescript
interface Lead {
  id: string;
  company_name: string;
  domain: string;
  niche: string;
  geo: string;
  status: LeadStatus;
  score?: number;
  contacts: Contact[];
  intent_signals: IntentSignal[];
  created_at: string;
  updated_at: string;
}

type LeadStatus = 
  | 'discovered'
  | 'enriched'
  | 'scored'
  | 'outreach_pending'
  | 'outreach_sent'
  | 'replied'
  | 'qualified'
  | 'escalated'
  | 'disqualified';
```

### Outreach Message Model
```typescript
interface OutreachMessage {
  id: string;
  lead_id: string;
  channel: 'email' | 'linkedin' | 'sms';
  subject?: string;
  body: string;
  structure: {
    observation: string;
    impact: string;
    offer: string;
    cta: string;
  };
  personalization: Record<string, string>;
  status: 'draft' | 'approved' | 'sent' | 'delivered' | 'failed';
  created_at: string;
}
```

### Proof Artifact Model
```typescript
interface ProofArtifact {
  id: string;
  lead_id: string;
  proof_type: 'screenshot' | 'recording' | 'extracted_data';
  url: string;
  storage_path: string;
  metadata: {
    width?: number;
    height?: number;
    duration?: number;
    extracted_text?: string;
  };
  created_at: string;
}
```

### Metrics Model
```typescript
interface SystemMetrics {
  period: 'daily' | 'weekly' | 'monthly';
  reply_rate: number;
  meeting_rate: number;
  cost_per_meeting: number;
  leads_discovered: number;
  leads_qualified: number;
  outreach_sent: number;
  budget: {
    llm_tokens: { used: number; limit: number };
    apify_runs: { used: number; limit: number };
    browser_sessions: { used: number; limit: number };
  };
  agent_health: Record<string, AgentHealth>;
}

interface AgentHealth {
  status: 'healthy' | 'degraded' | 'down';
  circuit_breaker: 'closed' | 'open' | 'half_open';
  avg_latency_ms: number;
  success_rate: number;
  last_error?: string;
}
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do.*

### Property 1: Tool Approval Enforcement
*For any* tool with `needsApproval: true`, the tool SHALL NOT execute until the user explicitly approves, and denial SHALL prevent execution entirely.
**Validates: Requirements 8.1, 8.2, 8.3, 10.1, 10.2, 10.3**

### Property 2: Bridge Request Authentication
*For any* request to the FastAPI bridge, the request SHALL include valid authentication, and unauthenticated requests SHALL be rejected with 401.
**Validates: Requirements 1.4, 23.1, 23.3**

### Property 3: Governance Rule Enforcement
*For any* tool invocation, the system SHALL check governance rules (rate limits, budgets, circuit breakers) before execution, and violations SHALL prevent execution.
**Validates: Requirements 1.6, 11.2, 11.3, 11.4**

### Property 4: Artifact Data Consistency
*For any* artifact displaying lead data, the data SHALL match the current state in the database, and updates SHALL be reflected within 5 seconds.
**Validates: Requirements 13.6, 22.3**

### Property 5: Error Message Safety
*For any* error returned to the user, the error message SHALL NOT expose internal system details, stack traces, or sensitive data.
**Validates: Requirements 21.1, 21.5**

### Property 6: Outreach Structure Compliance
*For any* outreach message generated, the message SHALL contain all 4 required parts (Observation, Impact, Offer, CTA) and SHALL include opt-out for email.
**Validates: Requirements 7.5, 16.2**

### Property 7: Audit Trail Completeness
*For any* tool invocation, the system SHALL create an audit log entry with user identity, action, parameters, and result.
**Validates: Requirements 23.3, 21.3**

### Property 8: Streaming Response Integrity
*For any* streaming response from the bridge, partial results SHALL be valid JSON and the final result SHALL be complete.
**Validates: Requirements 1.3, 22.2**

### Property 9: Tool Result Artifact Trigger
*For any* tool that specifies an artifact trigger, the artifact SHALL be displayed after successful tool execution.
**Validates: Requirements 2.4, 3.3, 4.4, 5.3, 6.4**

### Property 10: Approval UI Information Display
*For any* tool requiring approval, the approval UI SHALL display all relevant information (message content, recipient, warnings) before user decision.
**Validates: Requirements 8.4, 8.5, 10.2**

### Property 11: Multimodal Input Validation
*For any* file upload, the system SHALL validate file type and size before processing, and invalid files SHALL be rejected with clear error messages.
**Validates: Requirements 24.1, 24.2, 24.6**

### Property 12: Reasoning Model Tool Restriction
*For any* reasoning model selection, tools and file attachments SHALL be disabled, and the reasoning process SHALL be displayed.
**Validates: Requirements 26.2, 26.4**

### Property 13: Vote Uniqueness
*For any* message, a user SHALL only be able to cast one vote (up or down), and duplicate votes SHALL be prevented.
**Validates: Requirements 27.2, 27.3**

### Property 14: Stream Resumability
*For any* network disconnection during a long-running operation, the stream SHALL be resumable from the last checkpoint within 5 minutes.
**Validates: Requirements 29.1, 29.2, 29.5**

### Property 15: Visibility Privacy Default
*For any* new ZRAI chat, the default visibility SHALL be private, and public visibility SHALL require explicit user action.
**Validates: Requirements 30.4, 30.5**

## Error Handling

### Error Categories

| Category | HTTP Code | User Message | Recovery |
|----------|-----------|--------------|----------|
| `auth_error` | 401 | "Please sign in to continue" | Redirect to login |
| `permission_error` | 403 | "You don't have permission for this action" | Contact admin |
| `not_found` | 404 | "The requested resource was not found" | Check ID |
| `rate_limit` | 429 | "Rate limit exceeded. Try again in X minutes" | Wait and retry |
| `budget_exceeded` | 402 | "Daily budget exceeded for X" | Wait for reset |
| `circuit_open` | 503 | "Service temporarily unavailable" | Retry later |
| `validation_error` | 400 | "Invalid input: {details}" | Fix input |
| `backend_error` | 500 | "Something went wrong. Please try again" | Retry |

### Error Response Format
```typescript
interface ErrorResponse {
  success: false;
  error: {
    code: string;
    message: string;
    details?: Record<string, any>;
    retry_after?: number; // seconds
  };
}
```

## Testing Strategy

### Unit Tests
- Tool input validation
- Artifact rendering with mock data
- Error handling paths
- Authentication checks

### Integration Tests
- Tool → Bridge → Backend flow
- Artifact data loading
- Streaming response handling
- Approval flow completion

### Property-Based Tests
- Tool approval enforcement (Property 1)
- Authentication on all endpoints (Property 2)
- Governance rule checking (Property 3)
- Error message safety (Property 5)

### E2E Tests (Playwright)
- Complete discovery → outreach flow
- Approval flow (approve and deny)
- Artifact interactions
- Error recovery scenarios

## File Structure

```
frontend/
├── lib/ai/tools/zrai/
│   ├── index.ts                 # Export all ZRAI tools
│   ├── discover-leads.ts
│   ├── enrich-lead.ts
│   ├── analyze-intent.ts
│   ├── generate-proof.ts
│   ├── score-leads.ts
│   ├── draft-outreach.ts
│   ├── send-outreach.ts         # needsApproval: true
│   ├── handle-conversation.ts
│   ├── approve-escalation.ts    # needsApproval: true
│   ├── check-governance.ts
│   ├── manage-ab-test.ts
│   ├── run-pipeline.ts
│   ├── import-leads.ts          # For CSV/file uploads
│   └── analyze-screenshot.ts    # For image analysis
├── artifacts/zrai/
│   ├── lead-card/
│   │   ├── client.tsx
│   │   └── server.ts
│   ├── lead-list/
│   │   ├── client.tsx
│   │   └── server.ts
│   ├── proof-viewer/
│   │   ├── client.tsx
│   │   └── server.ts
│   ├── scoring-dashboard/
│   │   ├── client.tsx
│   │   └── server.ts
│   ├── outreach-draft/
│   │   ├── client.tsx
│   │   └── server.ts
│   ├── conversation-thread/
│   │   ├── client.tsx
│   │   └── server.ts
│   ├── metrics-dashboard/
│   │   ├── client.tsx
│   │   └── server.ts
│   └── lead-sheet/              # NEW: Spreadsheet artifact
│       ├── client.tsx
│       └── server.ts
├── app/(chat)/api/zrai/
│   ├── discover/route.ts
│   ├── enrich/route.ts
│   ├── intent/route.ts
│   ├── proof/route.ts
│   ├── score/route.ts
│   ├── outreach/route.ts
│   ├── conversation/route.ts
│   ├── governance/route.ts
│   ├── ab-test/route.ts
│   ├── run/route.ts
│   ├── leads/route.ts
│   ├── metrics/route.ts
│   └── import/route.ts          # NEW: Bulk import endpoint
├── components/
│   ├── zrai-greeting.tsx        # NEW: Custom ZRAI greeting
│   └── zrai-suggested-actions.tsx # NEW: ZRAI-specific suggestions
└── lib/zrai/
    ├── client.ts                # ZRAI API client
    ├── types.ts                 # TypeScript types
    ├── constants.ts             # Configuration
    └── file-handlers.ts         # NEW: File upload handlers
```

## Chat SDK Feature Integration Map

| Chat SDK Feature | ZRAI Integration | Implementation |
|-----------------|------------------|----------------|
| Model Selector | All models available, reasoning for complex analysis | `multimodal-input.tsx` |
| File Attachments | Lead screenshots, CSV imports, documents | `multimodal-input.tsx` + `import-leads.ts` |
| Suggested Actions | ZRAI-specific quick actions | `zrai-suggested-actions.tsx` |
| Visibility Selector | Private by default, shareable reports | `visibility-selector.tsx` |
| Chat History | Full lead research history | `sidebar-history.tsx` |
| Resumable Streams | Long-running discovery/enrichment | Redis + `resumable-stream` |
| Tool Approval | send_outreach, approve_escalation | `needsApproval: true` |
| Artifacts | 8 ZRAI artifacts + existing 4 | `artifacts/zrai/` |
| Reasoning Models | Complex scoring, intent analysis | `message-reasoning.tsx` |
| Vote System | Training data for Eval Agent | `message-actions.tsx` |
| Code Execution | Custom lead analysis scripts | `code/client.tsx` + Pyodide |
| Message Edit | Correct lead queries | `message-editor.tsx` |
| Greeting | ZRAI-branded welcome | `zrai-greeting.tsx` |
| Image Artifact | Proof screenshots with annotations | `image/client.tsx` |
| Sheet Artifact | Bulk lead data management | `lead-sheet/client.tsx` |
| Geolocation | Geo-relevant lead suggestions | `geolocation(request)` |
| Document Versioning | Artifact history | `version-footer.tsx` |
| Toolbar | Quick artifact actions | `toolbar.tsx` |
