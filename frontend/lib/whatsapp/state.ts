export const WHATSAPP_SALES_STAGES = [
  "NEW",
  "ENGAGED",
  "QUALIFIED",
  "PAIN_FOUND",
  "PROOF_SHARED",
  "OBJECTION_ACTIVE",
  "DEMO_PUSHED",
  "PAYMENT_PUSHED",
  "HUMAN_HANDOFF",
  "FOLLOWUP_PENDING",
  "CLOSED_WON",
  "CLOSED_LOST",
] as const;

export type WhatsAppSalesStage = (typeof WHATSAPP_SALES_STAGES)[number];

export const WHATSAPP_THREAD_PRIORITIES = ["low", "medium", "high"] as const;

export type WhatsAppThreadPriority =
  (typeof WHATSAPP_THREAD_PRIORITIES)[number];

export const WHATSAPP_COMMERCIAL_STATUSES = [
  "contacted",
  "replied",
  "qualified",
  "demo_booked",
  "demo_done",
  "pilot_won",
  "onboarding",
  "live",
] as const;

export type WhatsAppCommercialStatus =
  (typeof WHATSAPP_COMMERCIAL_STATUSES)[number];

export const WHATSAPP_SENDER_STATUSES = [
  "not_started",
  "docs_requested",
  "twilio_ready",
  "whatsapp_ready",
  "webhook_ready",
  "live",
] as const;

export type WhatsAppSenderStatus = (typeof WHATSAPP_SENDER_STATUSES)[number];

export type WhatsAppOnboardingChecklist = {
  hoursCollected: boolean;
  servicesCollected: boolean;
  faqCollected: boolean;
  escalationOwnerCollected: boolean;
  routingChecklistAssigned: boolean;
};

export type WhatsAppOpsState = {
  commercialStatus: WhatsAppCommercialStatus;
  senderStatus: WhatsAppSenderStatus;
  owner: string | null;
  nextActionAt: string | null;
  niche: string | null;
  city: string | null;
  contactChannel: string | null;
  senderOnboardingPossible: boolean | null;
  onboardingChecklist: WhatsAppOnboardingChecklist;
};

export type WhatsAppOpsStatePatch = Omit<
  Partial<WhatsAppOpsState>,
  "onboardingChecklist"
> & {
  onboardingChecklist?: Partial<WhatsAppOnboardingChecklist>;
};

export type WhatsAppLeadContactPoint = {
  name?: string | null;
  role?: string | null;
  phone?: string | null;
  email?: string | null;
  linkedin?: string | null;
  source?: string | null;
  confidence?: number | null;
  reason?: string | null;
  channel?: string | null;
  contactType?: string | null;
  ownerScope?: string | null;
  isDirect?: boolean;
  isPublic?: boolean;
};

export type WhatsAppLeadBranchPhone = {
  name?: string | null;
  phone?: string | null;
  source?: string | null;
};

export type WhatsAppLinkedLeadContext = {
  leadId: string;
  companyName: string;
  domain?: string | null;
  geo?: string | null;
  status?: string | null;
  analysisState?: string | null;
  finalScore?: number | null;
  previewMatchScore?: number | null;
  topIssue?: string | null;
  nextBestAction?: string | null;
  recommendedChannel?: string | null;
  demandScore?: number | null;
  trustScore?: number | null;
  leakScore?: number | null;
  offerFitScore?: number | null;
  contactQualityScore?: number | null;
  decisionMakerName?: string | null;
  decisionMakerRole?: string | null;
  decisionMakerLinkedin?: string | null;
  bestContactPhone?: string | null;
  bestContactEmail?: string | null;
  bestContactLinkedin?: string | null;
  bestContactChannel?: string | null;
  bestContactReason?: string | null;
  likelyContacts?: WhatsAppLeadContactPoint[];
  branchPhones?: WhatsAppLeadBranchPhone[];
  linkedAt?: string | null;
  source?: string | null;
  confidence?: number | null;
};

export type WhatsAppAgentState = {
  stage: WhatsAppSalesStage;
  priority: WhatsAppThreadPriority;
  confidence: number;
  summary: string | null;
  leadChannels: string[];
  painPoints: string[];
  objectionCategories: string[];
  requestedNextStep: string | null;
  lastIntent: string | null;
  nextBestMove: string | null;
  lastSuggestedReply: string | null;
  handoffReason: string | null;
  handoffRecommended: boolean;
  decisionMakerRole: string | null;
  decisionMakerConfirmed: boolean;
  painConfirmed: boolean;
  paymentInterest: boolean;
  optOut: boolean;
  updatedAt: string | null;
};

export const DEFAULT_WHATSAPP_AGENT_STATE: WhatsAppAgentState = {
  stage: "NEW",
  priority: "medium",
  confidence: 0.2,
  summary: null,
  leadChannels: [],
  painPoints: [],
  objectionCategories: [],
  requestedNextStep: null,
  lastIntent: null,
  nextBestMove: null,
  lastSuggestedReply: null,
  handoffReason: null,
  handoffRecommended: false,
  decisionMakerRole: null,
  decisionMakerConfirmed: false,
  painConfirmed: false,
  paymentInterest: false,
  optOut: false,
  updatedAt: null,
};

export const DEFAULT_WHATSAPP_ONBOARDING_CHECKLIST: WhatsAppOnboardingChecklist =
  {
    hoursCollected: false,
    servicesCollected: false,
    faqCollected: false,
    escalationOwnerCollected: false,
    routingChecklistAssigned: false,
  };

export const DEFAULT_WHATSAPP_OPS_STATE: WhatsAppOpsState = {
  commercialStatus: "contacted",
  senderStatus: "not_started",
  owner: null,
  nextActionAt: null,
  niche: null,
  city: null,
  contactChannel: "whatsapp",
  senderOnboardingPossible: null,
  onboardingChecklist: DEFAULT_WHATSAPP_ONBOARDING_CHECKLIST,
};

function dedupeStrings(values: string[] | undefined | null) {
  return Array.from(
    new Set(
      (values ?? [])
        .map((value) => value.trim())
        .filter(Boolean)
    )
  );
}

function normalizeStage(stage: string | null | undefined): WhatsAppSalesStage {
  if (
    stage &&
    WHATSAPP_SALES_STAGES.includes(stage as WhatsAppSalesStage)
  ) {
    return stage as WhatsAppSalesStage;
  }

  return DEFAULT_WHATSAPP_AGENT_STATE.stage;
}

function normalizePriority(
  priority: string | null | undefined
): WhatsAppThreadPriority {
  if (
    priority &&
    WHATSAPP_THREAD_PRIORITIES.includes(priority as WhatsAppThreadPriority)
  ) {
    return priority as WhatsAppThreadPriority;
  }

  return DEFAULT_WHATSAPP_AGENT_STATE.priority;
}

function clampConfidence(value: number | null | undefined) {
  if (!Number.isFinite(value)) {
    return DEFAULT_WHATSAPP_AGENT_STATE.confidence;
  }

  return Math.max(0, Math.min(1, Number(value)));
}

function normalizeText(value: string | null | undefined) {
  const normalized = value?.trim();
  return normalized ? normalized : null;
}

function normalizeCommercialStatus(
  value: string | null | undefined
): WhatsAppCommercialStatus {
  if (
    value &&
    WHATSAPP_COMMERCIAL_STATUSES.includes(value as WhatsAppCommercialStatus)
  ) {
    return value as WhatsAppCommercialStatus;
  }

  return DEFAULT_WHATSAPP_OPS_STATE.commercialStatus;
}

function normalizeSenderStatus(
  value: string | null | undefined
): WhatsAppSenderStatus {
  if (
    value &&
    WHATSAPP_SENDER_STATUSES.includes(value as WhatsAppSenderStatus)
  ) {
    return value as WhatsAppSenderStatus;
  }

  return DEFAULT_WHATSAPP_OPS_STATE.senderStatus;
}

function normalizeNullableBoolean(value: boolean | null | undefined) {
  if (value === true || value === false) {
    return value;
  }

  return null;
}

function normalizeOnboardingChecklist(
  value?: Partial<WhatsAppOnboardingChecklist> | null
): WhatsAppOnboardingChecklist {
  return {
    hoursCollected: Boolean(value?.hoursCollected),
    servicesCollected: Boolean(value?.servicesCollected),
    faqCollected: Boolean(value?.faqCollected),
    escalationOwnerCollected: Boolean(value?.escalationOwnerCollected),
    routingChecklistAssigned: Boolean(value?.routingChecklistAssigned),
  };
}

export function normalizeWhatsAppAgentState(
  value?: Partial<WhatsAppAgentState> | null
): WhatsAppAgentState {
  return {
    stage: normalizeStage(value?.stage),
    priority: normalizePriority(value?.priority),
    confidence: clampConfidence(value?.confidence),
    summary: normalizeText(value?.summary),
    leadChannels: dedupeStrings(value?.leadChannels),
    painPoints: dedupeStrings(value?.painPoints),
    objectionCategories: dedupeStrings(value?.objectionCategories),
    requestedNextStep: normalizeText(value?.requestedNextStep),
    lastIntent: normalizeText(value?.lastIntent),
    nextBestMove: normalizeText(value?.nextBestMove),
    lastSuggestedReply: normalizeText(value?.lastSuggestedReply),
    handoffReason: normalizeText(value?.handoffReason),
    handoffRecommended: Boolean(value?.handoffRecommended),
    decisionMakerRole: normalizeText(value?.decisionMakerRole),
    decisionMakerConfirmed: Boolean(value?.decisionMakerConfirmed),
    painConfirmed: Boolean(value?.painConfirmed),
    paymentInterest: Boolean(value?.paymentInterest),
    optOut: Boolean(value?.optOut),
    updatedAt: normalizeText(value?.updatedAt),
  };
}

export function normalizeWhatsAppOpsState(
  value?: Partial<WhatsAppOpsState> | null
): WhatsAppOpsState {
  return {
    commercialStatus: normalizeCommercialStatus(value?.commercialStatus),
    senderStatus: normalizeSenderStatus(value?.senderStatus),
    owner: normalizeText(value?.owner),
    nextActionAt: normalizeText(value?.nextActionAt),
    niche: normalizeText(value?.niche),
    city: normalizeText(value?.city),
    contactChannel:
      normalizeText(value?.contactChannel) ??
      DEFAULT_WHATSAPP_OPS_STATE.contactChannel,
    senderOnboardingPossible: normalizeNullableBoolean(
      value?.senderOnboardingPossible
    ),
    onboardingChecklist: normalizeOnboardingChecklist(
      value?.onboardingChecklist
    ),
  };
}

export function createWhatsAppAgentState(
  overrides?: Partial<WhatsAppAgentState>
) {
  return normalizeWhatsAppAgentState({
    ...DEFAULT_WHATSAPP_AGENT_STATE,
    ...overrides,
  });
}

export function createWhatsAppOpsState(overrides?: WhatsAppOpsStatePatch) {
  return normalizeWhatsAppOpsState({
    ...DEFAULT_WHATSAPP_OPS_STATE,
    ...overrides,
    onboardingChecklist: {
      ...DEFAULT_WHATSAPP_ONBOARDING_CHECKLIST,
      ...(overrides?.onboardingChecklist ?? {}),
    },
  });
}

export function mergeWhatsAppAgentState(
  current: Partial<WhatsAppAgentState> | null | undefined,
  patch: Partial<WhatsAppAgentState>
) {
  const currentState = normalizeWhatsAppAgentState(current);

  return normalizeWhatsAppAgentState({
    ...currentState,
    ...patch,
    leadChannels: [...currentState.leadChannels, ...(patch.leadChannels ?? [])],
    painPoints: [...currentState.painPoints, ...(patch.painPoints ?? [])],
    objectionCategories: [
      ...currentState.objectionCategories,
      ...(patch.objectionCategories ?? []),
    ],
  });
}

export function mergeWhatsAppOpsState(
  current: Partial<WhatsAppOpsState> | null | undefined,
  patch: WhatsAppOpsStatePatch
) {
  const currentState = normalizeWhatsAppOpsState(current);

  return normalizeWhatsAppOpsState({
    ...currentState,
    ...patch,
    onboardingChecklist: {
      ...currentState.onboardingChecklist,
      ...(patch.onboardingChecklist ?? {}),
    },
  });
}
