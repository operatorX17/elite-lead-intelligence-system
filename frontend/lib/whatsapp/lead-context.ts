import "server-only";

import type {
  WhatsAppConversation,
  WhatsAppMessage,
} from "@/lib/db/schema";
import {
  normalizeWhatsAppAgentState,
  normalizeWhatsAppOpsState,
  type WhatsAppAgentState,
  type WhatsAppLeadBranchPhone,
  type WhatsAppLeadContactPoint,
  type WhatsAppLinkedLeadContext,
} from "@/lib/whatsapp/state";
import { ZRAI_BACKEND_URL } from "@/lib/zrai/constants";

type ResolveContactMatch = {
  lead_id: string;
  business_name?: string | null;
  confidence: number;
  reasons?: string[];
  matched_phone?: string | null;
  matched_name?: string | null;
};

type ResolveContactResponse = {
  success: boolean;
  match?: ResolveContactMatch | null;
};

type LeadDetailsResponse = {
  success: boolean;
  lead?: Record<string, any>;
  signal_facts?: Record<string, any>;
  analysis_bundle?: Record<string, any>;
  processed_details?: Record<string, any>;
};

type ZRAIConversationResponse = {
  success: boolean;
  lead_id?: string;
  conversation?: {
    conversation_id?: string | null;
    entities?: Record<string, any>;
  };
  response?: string | { message?: string | null };
  ai_response?: string | null;
  needs_escalation?: boolean;
  escalation_reason?: string | null;
};

type ZRAIProspectConversationResponse = {
  success: boolean;
  conversation?: {
    conversation_id?: string | null;
    entities?: Record<string, any>;
  };
  ai_response?: string | null;
  needs_escalation?: boolean;
  escalation_reason?: string | null;
};

function clampConfidence(value: number | null | undefined) {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return null;
  }
  return Math.max(0, Math.min(1, value));
}

function dedupeStrings(values: Array<string | null | undefined>) {
  const seen = new Set<string>();
  const deduped: string[] = [];
  for (const value of values) {
    const normalized = String(value || "").trim();
    if (!normalized) {
      continue;
    }
    const key = normalized.toLowerCase();
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    deduped.push(normalized);
  }
  return deduped;
}

function buildLikelyContacts(
  signalFacts: Record<string, any>
): WhatsAppLeadContactPoint[] {
  const contactPoints =
    signalFacts.contact_intelligence?.contact_points ??
    signalFacts.contact_points ??
    [];

  return (Array.isArray(contactPoints) ? contactPoints : [])
    .map((contact) => ({
      name: String(contact?.name || "").trim() || null,
      role: String(contact?.role || "").trim() || null,
      phone: String(contact?.phone || "").trim() || null,
      email: String(contact?.email || "").trim() || null,
      linkedin: String(contact?.linkedin || "").trim() || null,
      source: String(contact?.source || "").trim() || null,
      confidence:
        typeof contact?.confidence === "number" ? contact.confidence : null,
      reason: String(contact?.reason || "").trim() || null,
      channel: String(contact?.channel || "").trim() || null,
      contactType: String(contact?.contact_type || "").trim() || null,
      ownerScope: String(contact?.owner_scope || "").trim() || null,
      isDirect: Boolean(contact?.is_direct),
      isPublic: Boolean(contact?.is_public),
    }))
    .filter(
      (contact) =>
        contact.name || contact.phone || contact.email || contact.linkedin
    )
    .slice(0, 6);
}

function buildBranchPhones(
  signalFacts: Record<string, any>
): WhatsAppLeadBranchPhone[] {
  const branchContacts = signalFacts.branch_contacts ?? [];
  return (Array.isArray(branchContacts) ? branchContacts : [])
    .map((branch) => ({
      name: String(branch?.name || "").trim() || null,
      phone: String(branch?.phone || "").trim() || null,
      source: String(branch?.source || "").trim() || null,
    }))
    .filter((branch) => branch.name || branch.phone)
    .slice(0, 8);
}

function buildLeadContextFromLeadPayload(
  payload: LeadDetailsResponse,
  match?: ResolveContactMatch | null
): WhatsAppLinkedLeadContext | null {
  const lead = payload.lead ?? {};
  const signalFacts =
    payload.signal_facts ??
    payload.processed_details?.signal_facts ??
    payload.analysis_bundle?.facts ??
    lead.signal_facts ??
    {};
  const analysisBundle =
    payload.analysis_bundle ??
    payload.processed_details?.analysis_bundle ??
    lead.analysis_bundle ??
    {};
  const scores = analysisBundle.scores ?? {};
  const guidance = analysisBundle.guidance ?? {};
  const agentContext = analysisBundle.agent_context ?? {};
  const contactIntel =
    analysisBundle.contact_intelligence ??
    signalFacts.contact_intelligence ??
    {};

  const leadId = String(
    lead.id || lead.lead_id || analysisBundle.lead?.id || match?.lead_id || ""
  ).trim();
  const companyName = String(
    lead.company_name ||
      lead.business_name ||
      analysisBundle.lead?.business_name ||
      match?.business_name ||
      ""
  ).trim();

  if (!leadId || !companyName) {
    return null;
  }

  return {
    leadId,
    companyName,
    domain: String(
      lead.domain || analysisBundle.lead?.website || lead.website || ""
    ).trim() || null,
    geo: String(lead.geo || analysisBundle.lead?.location || "").trim() || null,
    status: String(lead.status || "").trim() || null,
    analysisState:
      String(
        lead.analysis_state || analysisBundle.state || payload.processed_details?.analysis_state || ""
      ).trim() || null,
    finalScore:
      typeof lead.final_score === "number"
        ? lead.final_score
        : typeof scores.final_score === "number"
          ? scores.final_score
          : null,
    previewMatchScore:
      typeof lead.preview_match_score === "number"
        ? lead.preview_match_score
        : typeof scores.preview_match_score === "number"
          ? scores.preview_match_score
          : null,
    topIssue:
      String(signalFacts.top_issue || guidance.top_issue || "").trim() || null,
    nextBestAction:
      String(
        signalFacts.next_best_action || guidance.next_best_action || ""
      ).trim() || null,
    recommendedChannel:
      String(
        signalFacts.recommended_channel ||
          guidance.recommended_channel ||
          agentContext.recommended_channel ||
          ""
      ).trim() || null,
    demandScore:
      typeof scores.demand_score === "number" ? scores.demand_score : null,
    trustScore:
      typeof scores.trust_score === "number" ? scores.trust_score : null,
    leakScore: typeof scores.leak_score === "number" ? scores.leak_score : null,
    offerFitScore:
      typeof scores.offer_fit_score === "number" ? scores.offer_fit_score : null,
    contactQualityScore:
      typeof contactIntel.contact_quality_score === "number"
        ? contactIntel.contact_quality_score
        : typeof signalFacts.contact_quality_score === "number"
          ? signalFacts.contact_quality_score
          : null,
    decisionMakerName:
      String(
        contactIntel.decision_maker_name ||
          agentContext.decision_maker_name ||
          signalFacts.decision_maker_name ||
          ""
      ).trim() || null,
    decisionMakerRole:
      String(
        contactIntel.decision_maker_role ||
          agentContext.decision_maker_role ||
          signalFacts.decision_maker_role ||
          ""
      ).trim() || null,
    decisionMakerLinkedin:
      String(
        contactIntel.decision_maker_linkedin ||
          agentContext.decision_maker_linkedin ||
          signalFacts.decision_maker_linkedin ||
          ""
      ).trim() || null,
    bestContactPhone:
      String(
        contactIntel.best_contact_phone ||
          agentContext.best_contact_phone ||
          signalFacts.best_contact_phone ||
          ""
      ).trim() || null,
    bestContactEmail:
      String(
        contactIntel.best_contact_email ||
          agentContext.best_contact_email ||
          signalFacts.best_contact_email ||
          ""
      ).trim() || null,
    bestContactLinkedin:
      String(
        contactIntel.best_contact_linkedin ||
          agentContext.best_contact_linkedin ||
          signalFacts.best_contact_linkedin ||
          ""
      ).trim() || null,
    bestContactChannel:
      String(
        contactIntel.best_contact_channel ||
          agentContext.best_contact_channel ||
          signalFacts.best_contact_channel ||
          ""
      ).trim() || null,
    bestContactReason:
      String(
        contactIntel.best_contact_reason ||
          agentContext.best_contact_reason ||
          signalFacts.best_contact_reason ||
          ""
      ).trim() || null,
    likelyContacts: buildLikelyContacts(signalFacts),
    branchPhones: buildBranchPhones(signalFacts),
    linkedAt: new Date().toISOString(),
    source: "lead_intelligence",
    confidence: clampConfidence(match?.confidence ?? null),
  };
}

async function backendJson<T>(
  path: string,
  init?: RequestInit,
  userId?: string | null
): Promise<T> {
  const headers = new Headers(init?.headers || {});
  headers.set("Content-Type", "application/json");
  if (userId) {
    headers.set("X-User-ID", userId);
  }

  const response = await fetch(`${ZRAI_BACKEND_URL}${path}`, {
    ...init,
    headers,
    cache: "no-store",
  });

  const payload = (await response.json().catch(() => ({}))) as T & {
    detail?: string;
    message?: string;
  };

  if (!response.ok) {
    const message =
      (payload as { detail?: string }).detail ||
      (payload as { message?: string }).message ||
      `Backend request failed: ${response.status}`;
    throw new Error(message);
  }

  return payload;
}

export async function resolveLeadForWhatsAppThread({
  contactPhone,
  contactName,
  userId,
  abortSignal,
}: {
  contactPhone: string;
  contactName?: string | null;
  userId?: string | null;
  abortSignal?: AbortSignal | null;
}) {
  if (!String(contactPhone || "").trim()) {
    return null;
  }

  const payload = await backendJson<ResolveContactResponse>(
    "/api/v1/leads/resolve-contact",
    {
      method: "POST",
      signal: abortSignal ?? undefined,
      body: JSON.stringify({
        contact_phone: contactPhone,
        contact_name: contactName || null,
      }),
    },
    userId
  );

  return payload.match ?? null;
}

export async function fetchLinkedLeadContext({
  leadId,
  match,
  userId,
  abortSignal,
}: {
  leadId: string;
  match?: ResolveContactMatch | null;
  userId?: string | null;
  abortSignal?: AbortSignal | null;
}) {
  const payload = await backendJson<LeadDetailsResponse>(
    `/api/v1/leads/${leadId}`,
    { method: "GET", signal: abortSignal ?? undefined },
    userId
  );

  return buildLeadContextFromLeadPayload(payload, match);
}

export async function resolveLeadContextForWhatsAppThread({
  contactPhone,
  contactName,
  userId,
  abortSignal,
}: {
  contactPhone: string;
  contactName?: string | null;
  userId?: string | null;
  abortSignal?: AbortSignal | null;
}) {
  const match = await resolveLeadForWhatsAppThread({
    contactPhone,
    contactName,
    userId,
    abortSignal,
  });

  if (!match?.lead_id) {
    return null;
  }

  const leadContext = await fetchLinkedLeadContext({
    leadId: match.lead_id,
    match,
    userId,
    abortSignal,
  });

  if (!leadContext) {
    return null;
  }

  return {
    match,
    leadContext,
  };
}

export async function requestLeadAwareWhatsAppReply({
  leadId,
  incomingText,
  userId,
  abortSignal,
}: {
  leadId: string;
  incomingText: string;
  userId?: string | null;
  abortSignal?: AbortSignal | null;
}) {
  return backendJson<ZRAIConversationResponse>(
    "/api/v1/conversation",
    {
      method: "POST",
      signal: abortSignal ?? undefined,
      body: JSON.stringify({
        lead_id: leadId,
        message: incomingText,
        channel: "whatsapp",
      }),
    },
    userId
  );
}

function toBackendTranscriptRole(message: WhatsAppMessage) {
  if (message.direction === "incoming") {
    return "prospect";
  }

  return "ai";
}

export async function requestProspectAwareWhatsAppReply({
  conversation,
  messages,
  incomingText,
  currentState,
  userId,
  abortSignal,
}: {
  conversation: Pick<
    WhatsAppConversation,
    | "contactName"
    | "contactPhone"
    | "businessPhone"
    | "leadContext"
    | "opsState"
    | "agentState"
  >;
  messages: WhatsAppMessage[];
  incomingText: string;
  currentState: Partial<WhatsAppAgentState> | null | undefined;
  userId?: string | null;
  abortSignal?: AbortSignal | null;
}) {
  const normalizedState = normalizeWhatsAppAgentState(currentState);
  const normalizedOpsState = normalizeWhatsAppOpsState(conversation.opsState);
  const transcript = messages.slice(-6).map((message) => ({
    role: toBackendTranscriptRole(message),
    message: message.body,
  }));

  return backendJson<ZRAIProspectConversationResponse>(
    "/api/v1/conversation/prospect",
    {
      method: "POST",
      signal: abortSignal ?? undefined,
      body: JSON.stringify({
        message: incomingText,
        channel: "whatsapp",
        contact_name: conversation.contactName || null,
        contact_phone: conversation.contactPhone || null,
        business_phone: conversation.businessPhone || null,
        transcript,
        entities: {
          stage: normalizedState.stage,
          lead_channels: normalizedState.leadChannels,
          pain_points: normalizedState.painPoints,
          objection_categories: normalizedState.objectionCategories,
          requested_next_step: normalizedState.requestedNextStep,
          last_intent: normalizedState.lastIntent,
          handoff_requested: normalizedState.handoffRecommended,
          decision_maker_role: normalizedState.decisionMakerRole,
          decision_maker_confirmed: normalizedState.decisionMakerConfirmed,
          pain_confirmed: normalizedState.painConfirmed,
          payment_interest: normalizedState.paymentInterest,
          opt_out: normalizedState.optOut,
          confidence: normalizedState.confidence,
        },
        lead_context: conversation.leadContext
          ? {
              company_name: conversation.leadContext.companyName,
              top_issue: conversation.leadContext.topIssue,
              next_best_action: conversation.leadContext.nextBestAction,
              decision_maker_name: conversation.leadContext.decisionMakerName,
              decision_maker_role: conversation.leadContext.decisionMakerRole,
              recommended_channel: conversation.leadContext.recommendedChannel,
              final_score: conversation.leadContext.finalScore,
              preview_match_score: conversation.leadContext.previewMatchScore,
              geo: conversation.leadContext.geo,
            }
          : null,
        ops_state: {
          niche: normalizedOpsState.niche,
          city: normalizedOpsState.city,
          owner: normalizedOpsState.owner,
          commercial_status: normalizedOpsState.commercialStatus,
          sender_status: normalizedOpsState.senderStatus,
          contact_channel: normalizedOpsState.contactChannel,
          sender_onboarding_possible:
            normalizedOpsState.senderOnboardingPossible,
        },
      }),
    },
    userId
  );
}

export async function syncWhatsAppMessageToLeadMemory({
  leadId,
  message,
  role,
  conversationId,
  userId,
  abortSignal,
}: {
  leadId: string;
  message: string;
  role: "human" | "prospect" | "ai";
  conversationId?: string | null;
  userId?: string | null;
  abortSignal?: AbortSignal | null;
}) {
  return backendJson<{
    success: boolean;
    conversation?: { conversation_id?: string | null; entities?: Record<string, any> };
  }>(
    "/api/v1/conversation/sync",
    {
      method: "POST",
      signal: abortSignal ?? undefined,
      body: JSON.stringify({
        lead_id: leadId,
        role,
        message,
        channel: "whatsapp",
        conversation_id: conversationId || null,
      }),
    },
    userId
  );
}

export function buildLeadAwareAgentStatePatch({
  currentState,
  leadContext,
  aiResponse,
  conversation,
  needsEscalation,
  escalationReason,
}: {
  currentState: Partial<WhatsAppAgentState> | null | undefined;
  leadContext: WhatsAppLinkedLeadContext | null;
  aiResponse: string;
  conversation?: { entities?: Record<string, any> } | null;
  needsEscalation?: boolean;
  escalationReason?: string | null;
}) {
  const existingState = normalizeWhatsAppAgentState(currentState);
  const entities = conversation?.entities ?? {};
  const painPoints = dedupeStrings([
    ...existingState.painPoints,
    ...((entities.pain_points as string[]) ?? []),
  ]);
  const objectionCategories = dedupeStrings([
    ...existingState.objectionCategories,
    ...((entities.objection_categories as string[]) ?? []),
  ]);
  const leadChannels = dedupeStrings([
    ...existingState.leadChannels,
    leadContext?.recommendedChannel,
    ...((entities.lead_channels as string[]) ?? []),
  ]);
  const stage =
    String(entities.stage || existingState.stage || "ENGAGED").trim() ||
    "ENGAGED";

  let priority = existingState.priority;
  if (
    needsEscalation ||
    Boolean(entities.payment_interest) ||
    Boolean(entities.decision_maker_confirmed) ||
    (leadContext?.finalScore ?? 0) >= 80
  ) {
    priority = "high";
  } else if (painPoints.length > 0 || objectionCategories.length > 0) {
    priority = "medium";
  }

  const confidence = clampConfidence(
    typeof entities.confidence === "number"
      ? entities.confidence
      : Math.max(existingState.confidence, leadContext ? 0.6 : 0.35)
  );

  const summaryParts = [
    leadContext?.companyName
      ? `${leadContext.companyName} thread in ${stage.toLowerCase().replace(/_/g, " ")}`
      : `Thread in ${stage.toLowerCase().replace(/_/g, " ")}`,
  ];
  if (leadContext?.topIssue) {
    summaryParts.push(`top issue: ${leadContext.topIssue}`);
  }
  if (painPoints.length > 0) {
    summaryParts.push(`pain: ${painPoints.join(", ")}`);
  }
  if (objectionCategories.length > 0) {
    summaryParts.push(`objections: ${objectionCategories.join(", ")}`);
  }

  let nextBestMove = existingState.nextBestMove;
  if (needsEscalation) {
    nextBestMove = "Keep the thread warm and hand it to a human closer.";
  } else if (entities.requested_next_step === "call") {
    nextBestMove = "Offer two short time options and move toward a call.";
  } else if (leadContext?.nextBestAction) {
    nextBestMove = leadContext.nextBestAction;
  } else if (painPoints.length > 0) {
    nextBestMove = "Validate the leak calmly and keep the ask small.";
  } else {
    nextBestMove = "Keep the reply short, calm, and diagnostic.";
  }

  return normalizeWhatsAppAgentState({
    ...existingState,
    stage: stage as WhatsAppAgentState["stage"],
    priority,
    confidence: confidence ?? existingState.confidence,
    summary: summaryParts.join(" | "),
    leadChannels,
    painPoints,
    objectionCategories,
    requestedNextStep:
      String(entities.requested_next_step || "").trim() ||
      existingState.requestedNextStep,
    lastIntent: aiResponse || existingState.lastIntent,
    nextBestMove,
    lastSuggestedReply: aiResponse || existingState.lastSuggestedReply,
    handoffReason:
      String(escalationReason || "").trim() || existingState.handoffReason,
    handoffRecommended:
      Boolean(needsEscalation) || existingState.handoffRecommended,
    decisionMakerRole:
      String(
        leadContext?.decisionMakerRole ||
          entities.decision_maker_role ||
          existingState.decisionMakerRole ||
          ""
      ).trim() || null,
    decisionMakerConfirmed:
      Boolean(leadContext?.decisionMakerName) ||
      Boolean(entities.decision_maker_confirmed) ||
      existingState.decisionMakerConfirmed,
    painConfirmed:
      Boolean(entities.pain_confirmed) ||
      painPoints.length > 0 ||
      existingState.painConfirmed,
    paymentInterest:
      Boolean(entities.payment_interest) || existingState.paymentInterest,
    optOut: Boolean(entities.opt_out) || existingState.optOut,
    updatedAt: new Date().toISOString(),
  });
}
