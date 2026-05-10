/**
 * ZRAI Lead OS - Constants and Configuration
 * 
 * Centralized configuration for the ZRAI frontend integration.
 */

// ============================================================================
// API Configuration
// ============================================================================

/**
 * Base URL for the ZRAI FastAPI bridge endpoints.
 * In production, this should be the same origin (Next.js API routes).
 * For development with separate Python backend, set ZRAI_API_URL env var.
 */
export const ZRAI_API_BASE_URL = process.env.ZRAI_API_URL || '/api/zrai';

/**
 * Python backend URL for direct calls (if needed).
 * Used when bypassing Next.js API routes.
 */
export const ZRAI_BACKEND_URL = process.env.ZRAI_BACKEND_URL || 'http://localhost:8000';

/**
 * API endpoints for ZRAI operations.
 */
export const ZRAI_ENDPOINTS = {
  // Discovery
  discover: `${ZRAI_API_BASE_URL}/discover`,
  
  // Enrichment
  enrich: `${ZRAI_API_BASE_URL}/enrich`,
  
  // Intent Analysis
  intent: `${ZRAI_API_BASE_URL}/intent`,
  
  // Proof Generation
  proof: `${ZRAI_API_BASE_URL}/proof`,
  
  // Scoring
  score: `${ZRAI_API_BASE_URL}/score`,
  
  // Outreach
  outreach: `${ZRAI_API_BASE_URL}/outreach`,
  
  // Conversation
  conversation: `${ZRAI_API_BASE_URL}/conversation`,
  
  // Governance
  governance: `${ZRAI_API_BASE_URL}/governance`,
  
  // A/B Testing
  abTest: `${ZRAI_API_BASE_URL}/ab-test`,
  
  // Pipeline Runs
  run: `${ZRAI_API_BASE_URL}/run`,
  
  // Lead Data
  leads: `${ZRAI_API_BASE_URL}/leads`,
  
  // Metrics
  metrics: `${ZRAI_API_BASE_URL}/metrics`,
  
  // Import
  import: `${ZRAI_API_BASE_URL}/import`,
} as const;

// ============================================================================
// Default Values
// ============================================================================

/**
 * Default pagination settings.
 */
export const DEFAULT_PAGE_SIZE = 20;
export const MAX_PAGE_SIZE = 100;

/**
 * Default discovery settings.
 */
export const DEFAULT_DISCOVERY_LIMIT = 50;
export const MAX_DISCOVERY_LIMIT = 200;

/**
 * Default timeout for API requests (in milliseconds).
 */
export const API_TIMEOUT_MS = 30000;

/**
 * Long operation timeout (discovery, enrichment, proof generation).
 */
export const LONG_OPERATION_TIMEOUT_MS = 120000;

// ============================================================================
// Supported Niches
// ============================================================================

/**
 * Supported niches for lead discovery.
 * These should match the config/niches.yaml in the backend.
 */
export const SUPPORTED_NICHES = [
  'saas',
  'ecommerce',
  'agency',
  'fintech',
  'healthtech',
  'edtech',
  'real_estate',
  'legal',
  'consulting',
  'manufacturing',
] as const;

export type SupportedNiche = typeof SUPPORTED_NICHES[number];

// ============================================================================
// Supported Geos
// ============================================================================

/**
 * Supported geographic regions for lead discovery.
 */
export const SUPPORTED_GEOS = [
  'us',
  'uk',
  'eu',
  'canada',
  'australia',
  'global',
] as const;

export type SupportedGeo = typeof SUPPORTED_GEOS[number];

// ============================================================================
// Outreach Configuration
// ============================================================================

/**
 * Channel-specific character limits.
 */
export const OUTREACH_LIMITS = {
  email: {
    subject_max: 100,
    body_max: 5000,
  },
  linkedin: {
    connection_note_max: 300,
    message_max: 2000,
  },
  sms: {
    message_max: 160,
  },
} as const;

/**
 * Required outreach structure parts.
 */
export const OUTREACH_STRUCTURE_PARTS = [
  'observation',
  'impact',
  'offer',
  'cta',
] as const;

// ============================================================================
// File Upload Configuration
// ============================================================================

/**
 * Supported image MIME types.
 */
export const SUPPORTED_IMAGE_TYPES = [
  'image/png',
  'image/jpeg',
  'image/gif',
  'image/webp',
] as const;

/**
 * Supported document MIME types.
 */
export const SUPPORTED_DOCUMENT_TYPES = [
  'application/pdf',
  'text/csv',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
] as const;

/**
 * Maximum file sizes (in bytes).
 */
export const MAX_FILE_SIZES = {
  image: 10 * 1024 * 1024, // 10MB
  document: 50 * 1024 * 1024, // 50MB
  csv: 10 * 1024 * 1024, // 10MB
} as const;

// ============================================================================
// Error Codes
// ============================================================================

/**
 * ZRAI-specific error codes.
 */
export const ZRAI_ERROR_CODES = {
  // Authentication
  AUTH_ERROR: 'auth_error',
  PERMISSION_ERROR: 'permission_error',
  
  // Resource errors
  NOT_FOUND: 'not_found',
  ALREADY_EXISTS: 'already_exists',
  
  // Rate limiting
  RATE_LIMIT: 'rate_limit',
  BUDGET_EXCEEDED: 'budget_exceeded',
  
  // Service errors
  CIRCUIT_OPEN: 'circuit_open',
  SERVICE_UNAVAILABLE: 'service_unavailable',
  
  // Validation
  VALIDATION_ERROR: 'validation_error',
  INVALID_INPUT: 'invalid_input',
  
  // Backend errors
  BACKEND_ERROR: 'backend_error',
  TIMEOUT: 'timeout',
  
  // Governance
  GOVERNANCE_VIOLATION: 'governance_violation',
  DO_NOT_CONTACT: 'do_not_contact',
} as const;

export type ZRAIErrorCode = typeof ZRAI_ERROR_CODES[keyof typeof ZRAI_ERROR_CODES];

// ============================================================================
// UI Configuration
// ============================================================================

/**
 * Score thresholds for visual indicators.
 */
export const SCORE_THRESHOLDS = {
  high: 80,
  medium: 50,
  low: 0,
} as const;

/**
 * Status colors for leads.
 */
export const LEAD_STATUS_COLORS: Record<string, string> = {
  discovered: 'bg-gray-100 text-gray-800',
  enriched: 'bg-blue-100 text-blue-800',
  scored: 'bg-purple-100 text-purple-800',
  outreach_pending: 'bg-yellow-100 text-yellow-800',
  outreach_sent: 'bg-orange-100 text-orange-800',
  replied: 'bg-green-100 text-green-800',
  qualified: 'bg-emerald-100 text-emerald-800',
  escalated: 'bg-red-100 text-red-800',
  disqualified: 'bg-gray-200 text-gray-500',
} as const;

/**
 * Agent health status colors.
 */
export const AGENT_HEALTH_COLORS: Record<string, string> = {
  healthy: 'text-green-500',
  degraded: 'text-yellow-500',
  down: 'text-red-500',
} as const;

/**
 * Circuit breaker state colors.
 */
export const CIRCUIT_BREAKER_COLORS: Record<string, string> = {
  closed: 'text-green-500',
  half_open: 'text-yellow-500',
  open: 'text-red-500',
} as const;

// ============================================================================
// Suggested Actions
// ============================================================================

/**
 * ZRAI-specific suggested actions for the chat interface.
 */
export const ZRAI_SUGGESTED_ACTIONS = [
  {
    title: 'Discover leads',
    label: 'in SaaS niche',
    action: 'Discover 20 leads in the SaaS niche in the US',
  },
  {
    title: 'Show pipeline',
    label: 'dashboard',
    action: 'Show me the current pipeline dashboard with lead scores',
  },
  {
    title: 'Check outreach',
    label: 'queue',
    action: "What's in today's outreach queue?",
  },
  {
    title: 'Review governance',
    label: 'status',
    action: 'Show me the current governance status including rate limits and budgets',
  },
] as const;

// ============================================================================
// Greeting Configuration
// ============================================================================

/**
 * ZRAI greeting message configuration.
 */
export const ZRAI_GREETING = {
  title: 'Welcome to ZRAI Lead OS',
  subtitle: 'Your AI-powered lead intelligence system',
  description: 'I can help you discover, enrich, score, and engage with leads. Ask me to find prospects, analyze intent signals, draft outreach, or check your pipeline status.',
} as const;
