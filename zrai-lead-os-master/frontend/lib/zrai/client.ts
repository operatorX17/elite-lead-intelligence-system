/**
 * ZRAI Lead OS - API Client
 * 
 * Fetch wrapper for communicating with the ZRAI FastAPI bridge endpoints.
 * Handles authentication, error parsing, and response typing.
 */

import {
  API_TIMEOUT_MS,
  LONG_OPERATION_TIMEOUT_MS,
  ZRAI_ENDPOINTS,
  ZRAI_ERROR_CODES,
} from './constants';
import type {
  ABTest,
  Conversation,
  CSVImportResult,
  EnrichmentData,
  GovernanceStatus,
  ImageAnalysisResult,
  IntentSignal,
  Lead,
  OutreachChannel,
  OutreachMessage,
  PaginatedResponse,
  PipelineRun,
  ProofArtifact,
  ProofType,
  RunMode,
  ScoringResult,
  SystemMetrics,
  ZRAIError,
  ZRAIResponse,
} from './types';

// ============================================================================
// Client Configuration
// ============================================================================

interface ZRAIClientConfig {
  baseUrl?: string;
  timeout?: number;
  getAuthToken?: () => Promise<string | null>;
}

let clientConfig: ZRAIClientConfig = {};

/**
 * Configures the ZRAI API client.
 */
export function configureZRAIClient(config: ZRAIClientConfig): void {
  clientConfig = { ...clientConfig, ...config };
}

// ============================================================================
// Request Helpers
// ============================================================================

/**
 * Creates headers for ZRAI API requests.
 */
async function createHeaders(): Promise<HeadersInit> {
  const headers: HeadersInit = {
    'Content-Type': 'application/json',
  };

  if (clientConfig.getAuthToken) {
    const token = await clientConfig.getAuthToken();
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
  }

  return headers;
}

/**
 * Parses error response from the API.
 */
function parseErrorResponse(status: number, data: unknown): ZRAIError {
  if (data && typeof data === 'object' && 'error' in data) {
    return data.error as ZRAIError;
  }

  // Map HTTP status to error codes
  const errorMap: Record<number, { code: string; message: string }> = {
    400: { code: ZRAI_ERROR_CODES.VALIDATION_ERROR, message: 'Invalid request' },
    401: { code: ZRAI_ERROR_CODES.AUTH_ERROR, message: 'Authentication required' },
    403: { code: ZRAI_ERROR_CODES.PERMISSION_ERROR, message: 'Permission denied' },
    404: { code: ZRAI_ERROR_CODES.NOT_FOUND, message: 'Resource not found' },
    429: { code: ZRAI_ERROR_CODES.RATE_LIMIT, message: 'Rate limit exceeded' },
    500: { code: ZRAI_ERROR_CODES.BACKEND_ERROR, message: 'Internal server error' },
    503: { code: ZRAI_ERROR_CODES.SERVICE_UNAVAILABLE, message: 'Service unavailable' },
  };

  return errorMap[status] || { code: ZRAI_ERROR_CODES.BACKEND_ERROR, message: 'Unknown error' };
}

/**
 * Makes a request to the ZRAI API.
 */
async function zraiFetch<T>(
  endpoint: string,
  options: RequestInit = {},
  timeout: number = API_TIMEOUT_MS
): Promise<ZRAIResponse<T>> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeout);

  try {
    const headers = await createHeaders();
    const response = await fetch(endpoint, {
      ...options,
      headers: { ...headers, ...(options.headers || {}) },
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    const data = await response.json();

    if (!response.ok) {
      return {
        success: false,
        error: parseErrorResponse(response.status, data),
      };
    }

    return {
      success: true,
      data: data as T,
    };
  } catch (error) {
    clearTimeout(timeoutId);

    if (error instanceof Error && error.name === 'AbortError') {
      return {
        success: false,
        error: {
          code: ZRAI_ERROR_CODES.TIMEOUT,
          message: 'Request timed out',
        },
      };
    }

    return {
      success: false,
      error: {
        code: ZRAI_ERROR_CODES.BACKEND_ERROR,
        message: error instanceof Error ? error.message : 'Network error',
      },
    };
  }
}

// ============================================================================
// Discovery API
// ============================================================================

export interface DiscoverLeadsParams {
  niche: string;
  geo?: string;
  limit?: number;
}

export interface DiscoverLeadsResponse {
  leads: Lead[];
  count: number;
  run_id: string;
}

/**
 * Discovers leads based on niche and geo.
 */
export async function discoverLeads(
  params: DiscoverLeadsParams
): Promise<ZRAIResponse<DiscoverLeadsResponse>> {
  return zraiFetch<DiscoverLeadsResponse>(
    ZRAI_ENDPOINTS.discover,
    {
      method: 'POST',
      body: JSON.stringify(params),
    },
    LONG_OPERATION_TIMEOUT_MS
  );
}

// ============================================================================
// Enrichment API
// ============================================================================

export interface EnrichLeadParams {
  lead_id: string;
}

export interface EnrichLeadResponse {
  lead: Lead;
  enrichment: EnrichmentData;
}

/**
 * Enriches a lead with additional data.
 */
export async function enrichLead(
  params: EnrichLeadParams
): Promise<ZRAIResponse<EnrichLeadResponse>> {
  return zraiFetch<EnrichLeadResponse>(
    ZRAI_ENDPOINTS.enrich,
    {
      method: 'POST',
      body: JSON.stringify(params),
    },
    LONG_OPERATION_TIMEOUT_MS
  );
}

// ============================================================================
// Intent API
// ============================================================================

export interface AnalyzeIntentParams {
  lead_id: string;
}

export interface AnalyzeIntentResponse {
  lead: Lead;
  intent_signals: IntentSignal[];
  revenue_leak_score: number;
}

/**
 * Analyzes intent signals for a lead.
 */
export async function analyzeIntent(
  params: AnalyzeIntentParams
): Promise<ZRAIResponse<AnalyzeIntentResponse>> {
  return zraiFetch<AnalyzeIntentResponse>(
    ZRAI_ENDPOINTS.intent,
    {
      method: 'POST',
      body: JSON.stringify(params),
    },
    LONG_OPERATION_TIMEOUT_MS
  );
}

// ============================================================================
// Proof API
// ============================================================================

export interface GenerateProofParams {
  lead_id: string;
  proof_type: ProofType;
}

export interface GenerateProofResponse {
  proof: ProofArtifact;
}

/**
 * Generates proof artifacts (screenshots, recordings) for a lead.
 */
export async function generateProof(
  params: GenerateProofParams
): Promise<ZRAIResponse<GenerateProofResponse>> {
  return zraiFetch<GenerateProofResponse>(
    ZRAI_ENDPOINTS.proof,
    {
      method: 'POST',
      body: JSON.stringify(params),
    },
    LONG_OPERATION_TIMEOUT_MS
  );
}

// ============================================================================
// Scoring API
// ============================================================================

export interface ScoreLeadsParams {
  niche?: string;
  geo?: string;
  min_score?: number;
  lead_ids?: string[];
}

export interface ScoreLeadsResponse {
  results: ScoringResult[];
  count: number;
}

/**
 * Scores leads based on intent, fit, and engagement.
 */
export async function scoreLeads(
  params: ScoreLeadsParams = {}
): Promise<ZRAIResponse<ScoreLeadsResponse>> {
  return zraiFetch<ScoreLeadsResponse>(
    ZRAI_ENDPOINTS.score,
    {
      method: 'POST',
      body: JSON.stringify(params),
    },
    LONG_OPERATION_TIMEOUT_MS
  );
}

// ============================================================================
// Outreach API
// ============================================================================

export interface DraftOutreachParams {
  lead_id: string;
  channel: OutreachChannel;
}

export interface SendOutreachParams {
  lead_id: string;
  channel: OutreachChannel;
  message_id: string;
  message?: string; // Optional override
}

export interface OutreachResponse {
  message: OutreachMessage;
  sent?: boolean;
}

/**
 * Drafts an outreach message for a lead.
 */
export async function draftOutreach(
  params: DraftOutreachParams
): Promise<ZRAIResponse<OutreachResponse>> {
  return zraiFetch<OutreachResponse>(ZRAI_ENDPOINTS.outreach, {
    method: 'POST',
    body: JSON.stringify({ ...params, action: 'draft' }),
  });
}

/**
 * Sends an outreach message to a lead.
 */
export async function sendOutreach(
  params: SendOutreachParams
): Promise<ZRAIResponse<OutreachResponse>> {
  return zraiFetch<OutreachResponse>(ZRAI_ENDPOINTS.outreach, {
    method: 'POST',
    body: JSON.stringify({ ...params, action: 'send' }),
  });
}

// ============================================================================
// Conversation API
// ============================================================================

export interface HandleConversationParams {
  lead_id: string;
  message: string;
  channel?: OutreachChannel;
}

export interface HandleConversationResponse {
  conversation: Conversation;
  ai_response: string;
  needs_escalation: boolean;
  escalation_reason?: string;
}

/**
 * Handles a conversation with a lead.
 */
export async function handleConversation(
  params: HandleConversationParams
): Promise<ZRAIResponse<HandleConversationResponse>> {
  return zraiFetch<HandleConversationResponse>(ZRAI_ENDPOINTS.conversation, {
    method: 'POST',
    body: JSON.stringify(params),
  });
}

// ============================================================================
// Escalation API
// ============================================================================

export interface ApproveEscalationParams {
  lead_id: string;
  reason: string;
  assignee?: string;
}

export interface ApproveEscalationResponse {
  conversation: Conversation;
  escalated: boolean;
}

/**
 * Approves escalation of a lead to human handling.
 */
export async function approveEscalation(
  params: ApproveEscalationParams
): Promise<ZRAIResponse<ApproveEscalationResponse>> {
  return zraiFetch<ApproveEscalationResponse>(
    `${ZRAI_ENDPOINTS.conversation}/escalate`,
    {
      method: 'POST',
      body: JSON.stringify(params),
    }
  );
}

// ============================================================================
// Governance API
// ============================================================================

/**
 * Gets current governance status.
 */
export async function getGovernanceStatus(): Promise<ZRAIResponse<GovernanceStatus>> {
  return zraiFetch<GovernanceStatus>(ZRAI_ENDPOINTS.governance, {
    method: 'GET',
  });
}

// ============================================================================
// A/B Test API
// ============================================================================

export interface CreateABTestParams {
  name: string;
  description: string;
  variants: Array<{
    name: string;
    description: string;
    config: Record<string, unknown>;
  }>;
  metric: string;
}

export interface ABTestActionParams {
  test_id: string;
  action: 'start' | 'pause' | 'conclude';
}

/**
 * Creates a new A/B test.
 */
export async function createABTest(
  params: CreateABTestParams
): Promise<ZRAIResponse<ABTest>> {
  return zraiFetch<ABTest>(ZRAI_ENDPOINTS.abTest, {
    method: 'POST',
    body: JSON.stringify({ ...params, action: 'create' }),
  });
}

/**
 * Gets A/B test results.
 */
export async function getABTestResults(testId: string): Promise<ZRAIResponse<ABTest>> {
  return zraiFetch<ABTest>(`${ZRAI_ENDPOINTS.abTest}/${testId}`, {
    method: 'GET',
  });
}

/**
 * Performs an action on an A/B test.
 */
export async function abTestAction(
  params: ABTestActionParams
): Promise<ZRAIResponse<ABTest>> {
  return zraiFetch<ABTest>(ZRAI_ENDPOINTS.abTest, {
    method: 'POST',
    body: JSON.stringify(params),
  });
}

// ============================================================================
// Pipeline Run API
// ============================================================================

export interface RunPipelineParams {
  mode: RunMode;
  config?: Record<string, unknown>;
  run_id?: string; // For replay/resume
  limit?: number; // For dry_run
}

/**
 * Triggers a pipeline run.
 */
export async function runPipeline(
  params: RunPipelineParams
): Promise<ZRAIResponse<PipelineRun>> {
  return zraiFetch<PipelineRun>(
    ZRAI_ENDPOINTS.run,
    {
      method: 'POST',
      body: JSON.stringify(params),
    },
    LONG_OPERATION_TIMEOUT_MS
  );
}

/**
 * Gets pipeline run status.
 */
export async function getPipelineRun(runId: string): Promise<ZRAIResponse<PipelineRun>> {
  return zraiFetch<PipelineRun>(`${ZRAI_ENDPOINTS.run}/${runId}`, {
    method: 'GET',
  });
}

// ============================================================================
// Leads API
// ============================================================================

export interface GetLeadsParams {
  page?: number;
  page_size?: number;
  niche?: string;
  geo?: string;
  status?: string;
  min_score?: number;
  sort_by?: string;
  sort_order?: 'asc' | 'desc';
}

/**
 * Gets paginated list of leads.
 */
export async function getLeads(
  params: GetLeadsParams = {}
): Promise<ZRAIResponse<PaginatedResponse<Lead>>> {
  const searchParams = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined) {
      searchParams.set(key, String(value));
    }
  });

  const url = `${ZRAI_ENDPOINTS.leads}?${searchParams.toString()}`;
  return zraiFetch<PaginatedResponse<Lead>>(url, { method: 'GET' });
}

/**
 * Gets a single lead by ID.
 */
export async function getLead(leadId: string): Promise<ZRAIResponse<Lead>> {
  return zraiFetch<Lead>(`${ZRAI_ENDPOINTS.leads}/${leadId}`, {
    method: 'GET',
  });
}

// ============================================================================
// Metrics API
// ============================================================================

export interface GetMetricsParams {
  period?: 'daily' | 'weekly' | 'monthly';
}

/**
 * Gets system metrics.
 */
export async function getMetrics(
  params: GetMetricsParams = {}
): Promise<ZRAIResponse<SystemMetrics>> {
  const searchParams = new URLSearchParams();
  if (params.period) {
    searchParams.set('period', params.period);
  }

  const url = `${ZRAI_ENDPOINTS.metrics}?${searchParams.toString()}`;
  return zraiFetch<SystemMetrics>(url, { method: 'GET' });
}

// ============================================================================
// Import API
// ============================================================================

export interface ImportLeadsParams {
  leads: Array<Partial<Lead>>;
  source: string;
}

/**
 * Imports leads from CSV or other sources.
 */
export async function importLeads(
  params: ImportLeadsParams
): Promise<ZRAIResponse<CSVImportResult>> {
  return zraiFetch<CSVImportResult>(ZRAI_ENDPOINTS.import, {
    method: 'POST',
    body: JSON.stringify(params),
  });
}

// ============================================================================
// Screenshot Analysis API
// ============================================================================

export interface AnalyzeScreenshotParams {
  image_base64: string;
  mime_type: string;
  context?: string;
}

/**
 * Analyzes a screenshot for intent signals.
 */
export async function analyzeScreenshot(
  params: AnalyzeScreenshotParams
): Promise<ZRAIResponse<ImageAnalysisResult>> {
  return zraiFetch<ImageAnalysisResult>(
    `${ZRAI_ENDPOINTS.intent}/screenshot`,
    {
      method: 'POST',
      body: JSON.stringify(params),
    },
    LONG_OPERATION_TIMEOUT_MS
  );
}
