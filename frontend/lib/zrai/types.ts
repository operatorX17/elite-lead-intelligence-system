/**
 * ZRAI Lead OS - TypeScript Types
 * 
 * Core data models for the ZRAI frontend integration.
 * These types mirror the Python backend models.
 */

// ============================================================================
// Lead Types
// ============================================================================

export type LeadStatus =
  | 'discovered'
  | 'candidate_preview'
  | 'qualified_preview'
  | 'enriched'
  | 'scored'
  | 'outreach_pending'
  | 'outreach_sent'
  | 'replied'
  | 'qualified'
  | 'escalated'
  | 'disqualified';

export type AnalysisState =
  | 'preview'
  | 'analyzing'
  | 'analyzed'
  | 'stale'
  | 'failed';

export type AdsStatus = 'yes' | 'no' | 'not_checked';

export interface Contact {
  id: string;
  lead_id: string;
  name: string;
  title?: string;
  email?: string;
  phone?: string;
  linkedin_url?: string;
  is_primary: boolean;
  created_at: string;
}

export interface IntentSignal {
  id: string;
  lead_id: string;
  signal_type: string;
  signal_value: string;
  confidence: number;
  source: string;
  detected_at: string;
}

export interface SignalFacts {
  phone_visible: boolean;
  phone_numbers: string[];
  booking_detected: boolean;
  booking_target?: string | null;
  contact_form_detected: boolean;
  whatsapp_detected: boolean;
  whatsapp_target?: string | null;
  chat_widget_type?: string | null;
  ads_status: AdsStatus;
  ads_channels: string[];
  ads_last_seen?: string | null;
  reviews_count?: number | null;
  rating?: number | null;
  volume_score_inputs?: Record<string, unknown>;
  services: string[];
  social_profiles: Record<string, string | string[]>;
  multi_clinic?: boolean;
  branch_count?: number;
  branch_names?: string[];
  doctor_count?: number;
  doctor_names?: string[];
  doctor_profiles?: Array<{
    name?: string;
    role?: string;
    clinic?: string;
    experience?: string;
    source?: string;
    score?: number;
    phones?: string[];
    emails?: string[];
    linkedin?: string;
  }>;
  instagram_present?: boolean;
  youtube_present?: boolean;
  testimonials_present?: boolean;
  gallery_present?: boolean;
  content_ready_score?: number;
  booking_flow_quality?: string;
  after_hours_capture?: boolean;
  instant_response_path?: boolean;
  confidence_by_signal?: Record<string, number>;
  decision_maker_name?: string | null;
  decision_maker_linkedin?: string | null;
  decision_maker_role?: string | null;
  decision_maker_source?: string | null;
  decision_maker_confidence?: number | null;
  best_contact_phone?: string | null;
  best_contact_email?: string | null;
  best_contact_linkedin?: string | null;
  best_contact_channel?: string | null;
  best_contact_reason?: string | null;
  decision_maker_candidates?: Array<{
    name?: string;
    role?: string;
    source?: string;
    score?: number;
    linkedin?: string;
    emails?: string[];
    phones?: string[];
    clinic?: string;
  }>;
  branch_contacts?: Array<{
    name?: string;
    phone?: string;
    source?: string;
  }>;
  contact_evidence?: string[];
  top_issue?: string;
  next_best_action?: string;
  recommended_channel?: string | null;
  recommended_message_type?: string | null;
  draft_template_key?: string | null;
  requires_operator_approval?: boolean;
}

export interface AnalysisBundle {
  version: string;
  state: AnalysisState | string;
  updated_at?: string | null;
  qualification?: {
    final_score?: number | null;
    lead_tier?: string | null;
    do_not_contact?: boolean | null;
    do_not_contact_reason?: string | null;
  };
  facts: SignalFacts;
  scores: {
    preview_match_score?: number | null;
    final_score?: number | null;
    lead_tier?: string | null;
    demand_score?: number | null;
    trust_score?: number | null;
    leak_score?: number | null;
    serviceability_score?: number | null;
    offer_fit_score?: number | null;
    total_score?: number | null;
  };
  guidance: {
    site_truth_summary?: string | null;
    why_this_lead?: string | null;
    top_issue?: string | null;
    next_best_action?: string | null;
    recommended_channel?: string | null;
    recommended_message_type?: string | null;
    draft_template_key?: string | null;
    requires_operator_approval?: boolean | null;
  };
  evidence: {
    hero_screenshot_url?: string | null;
    cta_screenshot_url?: string | null;
    proof_mode?: string | null;
    audit_bullets?: Array<Record<string, unknown>>;
  };
  lead: {
    id?: string | null;
    business_name?: string | null;
    website?: string | null;
    category?: string | null;
    location?: string | null;
  };
  agent_context?: {
    business_summary?: string | null;
    conversion_summary?: string | null;
    known_pain_points?: string[];
    trust_markers?: string[];
    decision_maker_name?: string | null;
    decision_maker_linkedin?: string | null;
    decision_maker_role?: string | null;
    decision_maker_source?: string | null;
    decision_maker_confidence?: number | null;
    best_contact_phone?: string | null;
    best_contact_email?: string | null;
    best_contact_linkedin?: string | null;
    best_contact_channel?: string | null;
    best_contact_reason?: string | null;
    decision_maker_candidates?: SignalFacts["decision_maker_candidates"];
    doctor_profiles?: SignalFacts["doctor_profiles"];
    branch_contacts?: SignalFacts["branch_contacts"];
    contact_evidence?: SignalFacts["contact_evidence"];
    recommended_offer?: string | null;
    recommended_channel?: string | null;
    recommended_next_step?: string | null;
  };
}

export interface Lead {
  id: string;
  company_name: string;
  domain: string;
  niche: string;
  geo: string;
  status: LeadStatus;
  score?: number;
  score_kind?: 'preview_match' | 'final_score';
  preview_match_score?: number;
  final_score?: number;
  score_breakdown?: ScoreBreakdown;
  verified_fit?: string;
  source?: string;
  source_label?: string;
  preview_summary?: string;
  contact_paths?: string[];
  analysis_state?: AnalysisState;
  analysis_updated_at?: string;
  signals_version?: string;
  signal_facts?: SignalFacts;
  analysis_bundle?: AnalysisBundle;
  site_truth_summary?: string;
  why_this_lead?: string;
  contacts: Contact[];
  intent_signals: IntentSignal[];
  enrichment_data?: EnrichmentData;
  created_at: string;
  updated_at: string;
}

// ============================================================================
// Enrichment Types
// ============================================================================

export interface EnrichmentData {
  id: string;
  lead_id: string;
  company_size?: string;
  industry?: string;
  revenue_range?: string;
  tech_stack?: string[];
  social_profiles?: Record<string, string>;
  description?: string;
  founded_year?: number;
  employee_count?: number;
  headquarters?: string;
  enriched_at: string;
}

// ============================================================================
// Scoring Types
// ============================================================================

export interface ScoreBreakdown {
  total_score: number;
  demand_score?: number;
  trust_score?: number;
  leak_score?: number;
  serviceability_score?: number;
  offer_fit_score?: number;
  intent_score?: number;
  fit_score?: number;
  engagement_score?: number;
  recency_score?: number;
}

export interface ScoringResult {
  lead_id?: string;
  lead?: Lead;
  leads?: Lead[];
  score_breakdown?: ScoreBreakdown;
  disqualified?: boolean;
  disqualification_reason?: string;
  scored_at: string;
}

// ============================================================================
// Outreach Types
// ============================================================================

export type OutreachChannel = 'email' | 'linkedin' | 'sms' | 'whatsapp';

export type OutreachStatus = 
  | 'draft' 
  | 'approved' 
  | 'sent' 
  | 'delivered' 
  | 'opened'
  | 'clicked'
  | 'replied'
  | 'bounced'
  | 'failed';

export interface OutreachStructure {
  observation: string;
  impact: string;
  offer: string;
  cta: string;
}

export interface OutreachMessage {
  id: string;
  lead_id: string;
  channel: OutreachChannel;
  subject?: string;
  body: string;
  structure: OutreachStructure;
  personalization: Record<string, string>;
  status: OutreachStatus;
  sent_at?: string;
  created_at: string;
}

// ============================================================================
// Proof Types
// ============================================================================

export type ProofType = 'screenshot' | 'recording' | 'extracted_data';

export interface ProofMetadata {
  width?: number;
  height?: number;
  duration?: number;
  extracted_text?: string;
  url?: string;
}

export interface ProofArtifact {
  id: string;
  lead_id: string;
  proof_type: ProofType;
  url: string;
  storage_path: string;
  metadata: ProofMetadata;
  created_at: string;
}

// ============================================================================
// Conversation Types
// ============================================================================

export type ConversationStatus = 
  | 'active' 
  | 'qualified' 
  | 'escalated' 
  | 'closed'
  | 'unresponsive';

export interface ConversationMessage {
  id: string;
  conversation_id: string;
  role: 'ai' | 'human' | 'lead';
  sender: 'ai' | 'human' | 'lead';
  content: string;
  channel: OutreachChannel;
  timestamp: string;
  qualification_signals?: Array<{
    type: 'positive' | 'negative' | 'neutral';
    label: string;
    confidence?: number;
  }>;
  created_at: string;
}

export interface Conversation {
  id: string;
  lead_id: string;
  status: ConversationStatus;
  messages: ConversationMessage[];
  escalation_reason?: string;
  assigned_to?: string;
  created_at: string;
  updated_at: string;
}

// ============================================================================
// Governance Types
// ============================================================================

export type CircuitBreakerState = 'closed' | 'open' | 'half_open';
export type AgentHealthStatus = 'healthy' | 'degraded' | 'down';

export interface BudgetUsage {
  used: number;
  limit: number;
  reset_at?: string;
}

export interface RateLimitStatus {
  channel: OutreachChannel;
  current: number;
  limit: number;
  window: string;
  reset_at: string;
}

export interface AgentHealth {
  agent_name: string;
  status: AgentHealthStatus;
  circuit_breaker: CircuitBreakerState;
  avg_latency_ms: number;
  success_rate: number;
  last_error?: string;
  last_success_at?: string;
}

export interface GovernanceStatus {
  rate_limits: RateLimitStatus[];
  budgets: {
    llm_tokens: BudgetUsage;
    apify_runs: BudgetUsage;
    browser_sessions: BudgetUsage;
  };
  circuit_breakers: Record<string, CircuitBreakerState>;
  agent_health: AgentHealth[];
  kill_switches: Record<string, boolean>;
}

// ============================================================================
// Metrics Types
// ============================================================================

export type MetricsPeriod = 'daily' | 'weekly' | 'monthly';

export interface SystemMetrics {
  period: MetricsPeriod;
  reply_rate: number;
  meeting_rate: number;
  cost_per_meeting: number;
  leads_discovered: number;
  leads_qualified: number;
  outreach_sent: number;
  budget: {
    llm_tokens: BudgetUsage;
    apify_runs: BudgetUsage;
    browser_sessions: BudgetUsage;
  };
  agent_health: Record<string, AgentHealth>;
  trends?: MetricsTrend[];
}

export interface MetricsTrend {
  date: string;
  metric: string;
  value: number;
}

// ============================================================================
// A/B Test Types
// ============================================================================

export type ABTestStatus = 'draft' | 'running' | 'paused' | 'concluded';

export interface ABTestVariant {
  id: string;
  name: string;
  description: string;
  config: Record<string, unknown>;
  sample_size: number;
  conversions: number;
  conversion_rate: number;
}

export interface ABTest {
  id: string;
  name: string;
  description: string;
  status: ABTestStatus;
  variants: ABTestVariant[];
  metric: string;
  winner?: string;
  statistical_significance?: number;
  created_at: string;
  concluded_at?: string;
}

// ============================================================================
// Pipeline Run Types
// ============================================================================

export type RunMode = 'full' | 'dry_run' | 'replay' | 'resume';
export type RunStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';

export interface PipelineRun {
  id: string;
  mode: RunMode;
  status: RunStatus;
  config_snapshot: Record<string, unknown>;
  started_at: string;
  completed_at?: string;
  stats: {
    leads_processed: number;
    leads_succeeded: number;
    leads_failed: number;
    errors: string[];
  };
}

// ============================================================================
// API Response Types
// ============================================================================

export interface ZRAIResponse<T> {
  success: boolean;
  data?: T;
  error?: ZRAIError;
}

export interface ZRAIError {
  code: string;
  message: string;
  details?: Record<string, unknown>;
  retry_after?: number;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
}

// ============================================================================
// Tool Result Types (for Chat SDK integration)
// ============================================================================

export interface ToolResult<T = unknown> {
  success: boolean;
  data?: T;
  error?: string;
  artifactTrigger?: {
    kind: ZRAIArtifactKind;
    data: unknown;
  };
}

export type ZRAIArtifactKind =
  | 'lead-card'
  | 'lead-list'
  | 'proof-viewer'
  | 'scoring-dashboard'
  | 'outreach-draft'
  | 'conversation-thread'
  | 'metrics-dashboard'
  | 'lead-sheet';

// ============================================================================
// File Upload Types
// ============================================================================

export type SupportedImageType = 'image/png' | 'image/jpeg' | 'image/gif' | 'image/webp';
export type SupportedDocumentType = 'application/pdf' | 'text/csv' | 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';

export interface FileUploadResult {
  success: boolean;
  file_id?: string;
  file_type: string;
  file_name: string;
  size_bytes: number;
  error?: string;
}

export interface CSVImportResult {
  success: boolean;
  total_rows: number;
  imported: number;
  failed: number;
  errors: Array<{
    row: number;
    error: string;
  }>;
  leads?: Lead[];
}

export interface ImageAnalysisResult {
  success: boolean;
  intent_signals: IntentSignal[];
  extracted_text?: string;
  confidence: number;
}
