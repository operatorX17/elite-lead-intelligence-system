"use client";

/**
 * ZRAI Lead List Artifact - Client Component
 *
 * Displays a list of leads with filtering and sorting.
 */

import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Artifact } from "@/components/create-artifact";
import { CopyIcon, RedoIcon, UndoIcon } from "@/components/icons";
import { useArtifact } from "@/hooks/use-artifact";
import {
  buildLeadScoreNarrative,
  buildRankedContactModel,
  formatLeadForClipboard,
  formatLeadListForClipboard,
} from "@/lib/zrai/clipboard";
import {
  fetchFounderIntelligence,
  mergeFounderIntelligenceIntoProcessedDetails,
  needsFounderIntelligence,
  type FounderIntelPayload,
} from "@/lib/zrai/founder-intelligence";
import { ensurePersistedLead, isUuidLeadId } from "@/lib/zrai/lead-resolution";
import type { AnalysisBundle, Lead, SignalFacts } from "@/lib/zrai/types";
import { getZRAILeadByIdEndpoint, ZRAI_ENDPOINTS } from "@/lib/zrai/constants";

type LeadListMetadata = {
  leads: Lead[];
  loading: boolean;
  sortBy: string;
  sortOrder: "asc" | "desc";
  filter: string;
  selectedLeadId?: string | null;
  processedDetails?: Record<string, ProcessedLeadDetails>;
  liveSelectedLead?: Lead | null;
  liveSelectedLeadDetails?: ProcessedLeadDetails | null;
};

type LeadListPayload = {
  filter?: string;
  leads?: Lead[];
  processedDetails?: Record<string, ProcessedLeadDetails>;
  processed_details?: Record<string, ProcessedLeadDetails>;
  selectedLeadId?: string | null;
  sortBy?: string;
  sortOrder?: "asc" | "desc";
};

type ProcessedLeadDetails = {
  enrichment?: Record<string, unknown>;
  intent?: Record<string, unknown>;
  scoring?: Record<string, unknown>;
  proof?: {
    hero_screenshot_url?: string;
    cta_screenshot_url?: string;
    audit_bullets?: Array<Record<string, string>>;
    extraction_data?: Record<string, unknown>;
  };
  outreach?: Array<{
    subject?: string;
    body?: string;
    channel?: string;
    status?: string;
  }>;
  signal_facts?: SignalFacts;
  analysis_bundle?: AnalysisBundle;
  analysis_state?: string;
  analysis_updated_at?: string;
  signals_version?: string;
};

type OutreachDraft = NonNullable<ProcessedLeadDetails["outreach"]>[number];

type ProcessedLeadResponseItem = {
  success: boolean;
  lead_id: string;
  error?: string;
  lead?: Lead;
  enrichment?: Record<string, unknown>;
  intent?: Record<string, unknown>;
  proof?: ProcessedLeadDetails["proof"];
  outreach?: ProcessedLeadDetails["outreach"];
  scoring?: ProcessedLeadDetails["scoring"];
  signal_facts?: SignalFacts;
  analysis_bundle?: AnalysisBundle;
  analysis_state?: string;
  analysis_updated_at?: string;
  signals_version?: string;
};

function getScoreResults(payload: any) {
  if (Array.isArray(payload?.results)) {
    return payload.results;
  }
  if (Array.isArray(payload?.data?.results)) {
    return payload.data.results;
  }
  return [];
}

function getPayloadData<T = any>(payload: any): T {
  return (payload?.data ?? payload) as T;
}

function getLeadSource(lead: Lead) {
  return (
    lead.source_label ||
    lead.intent_signals?.find((signal) => signal.signal_type === "discovery_source")
      ?.signal_value ||
    "Unknown"
  );
}

function getLeadFit(lead: Lead) {
  return lead.verified_fit || lead.niche || "Candidate";
}

function getLeadSummary(lead: Lead) {
  return (
    lead.preview_summary ||
    lead.intent_signals?.find((signal) => signal.signal_type === "summary")
      ?.signal_value ||
    ""
  );
}

function getScoreLabel(lead: Lead) {
  if (lead.analysis_state === "analyzed" || lead.score_kind === "final_score") {
    return "Final";
  }
  return "Preview";
}

function getAnalysisLabel(lead: Lead) {
  return lead.analysis_state === "analyzed" || lead.score_kind === "final_score"
    ? "Analyzed"
    : "Preview";
}

function getResolvedAnalysisState(
  lead: Lead | null | undefined,
  processedDetails: ProcessedLeadDetails | null | undefined
) {
  return (
    processedDetails?.analysis_state ||
    lead?.analysis_state ||
    (lead?.score_kind === "final_score" ? "analyzed" : null)
  );
}

function isTerminalAnalysisState(
  lead: Lead | null | undefined,
  processedDetails: ProcessedLeadDetails | null | undefined
) {
  const state = getResolvedAnalysisState(lead, processedDetails);
  return state === "analyzed" || state === "failed";
}

function getStatusHelp(status: Lead["status"]) {
  switch (status) {
    case "qualified_preview":
      return "Discovery found a likely good lead, but the full chain has not been run yet.";
    case "candidate_preview":
      return "Discovery found a possible lead, but confidence is still weaker and needs validation.";
    case "enriched":
      return "The lead was enriched and contact data was pulled, but outreach is not drafted yet.";
    case "outreach_pending":
      return "The full chain ran and draft outreach is ready for review.";
    case "qualified":
      return "The lead is treated as high quality and ready for operator action.";
    default:
      return "Current pipeline stage for this lead.";
  }
}

function formatContactPath(path: string | undefined) {
  if (!path) {
    return "unknown";
  }

  return String(path)
    .replace(/_/g, " ")
    .replace(/\bcta\b/i, "CTA")
    .replace(/\bwhatsapp\b/i, "WhatsApp")
    .replace(/\bbooking\b/i, "booking link");
}

function formatLeadStatus(status: Lead["status"] | string | undefined) {
  if (!status) {
    return "unknown";
  }

  return String(status).replace(/_/g, " ");
}

function formatBooleanFact(value: unknown, truthyLabel: string, falsyLabel: string) {
  return value ? truthyLabel : falsyLabel;
}

function getWhatsAppFact(extractionData: Record<string, unknown> | undefined) {
  const hasWhatsApp =
    extractionData?.chat_widget === "whatsapp" || Boolean(extractionData?.whatsapp_target);
  return {
    hasWhatsApp,
    target: extractionData?.whatsapp_target
      ? String(extractionData.whatsapp_target)
      : "not extracted",
  };
}

function getSignalFacts(
  lead: Lead | null | undefined,
  processedDetails: ProcessedLeadDetails | undefined
): SignalFacts | null {
  return (
    processedDetails?.signal_facts ||
    lead?.signal_facts ||
    null
  );
}

function getCanonicalProofFacts(
  signalFacts: SignalFacts | null,
  extractionData: Record<string, unknown> | undefined
) {
  const extractedPhoneNumbers = Array.isArray(extractionData?.phone_numbers)
    ? extractionData.phone_numbers.map((value) => String(value))
    : [];
  const phoneNumbers = signalFacts?.phone_numbers?.length
    ? signalFacts.phone_numbers
    : extractedPhoneNumbers;

  return {
    phoneVisible:
      signalFacts?.phone_visible ??
      (["hero", "visible", "above_fold", "below_fold"].includes(
        String(extractionData?.phone_visibility || "")
      ) || phoneNumbers.length > 0),
    phoneNumbers,
    bookingDetected: signalFacts?.booking_detected ?? Boolean(extractionData?.booking_link),
    bookingTarget:
      signalFacts?.booking_target ||
      (extractionData?.booking_link ? String(extractionData.booking_link) : null),
    whatsappDetected:
      signalFacts?.whatsapp_detected ??
      (extractionData?.chat_widget === "whatsapp" || Boolean(extractionData?.whatsapp_target)),
    whatsappTarget:
      signalFacts?.whatsapp_target ||
      (extractionData?.whatsapp_target ? String(extractionData.whatsapp_target) : null),
    chatWidgetType:
      signalFacts?.chat_widget_type ||
      (extractionData?.chat_widget ? String(extractionData.chat_widget) : null),
    bookingFlowQuality:
      signalFacts?.booking_flow_quality ||
      ((signalFacts?.booking_detected ?? Boolean(extractionData?.booking_link)) ? "basic" : "none"),
  };
}

function getCanonicalProofInsights(
  signalFacts: SignalFacts | null,
  extractionData: Record<string, unknown> | undefined,
  fallbackBullets: Array<Record<string, string>> | undefined
) {
  if (!signalFacts) {
    return (fallbackBullets || [])
      .map((bullet) => bullet.evidence || bullet.specific || bullet.estimate || "")
      .filter(Boolean);
  }

  const facts = getCanonicalProofFacts(signalFacts, extractionData);
  const insights: string[] = [];

  insights.push(
    facts.phoneVisible
      ? "Phone contact is available on-site."
      : "Phone is not visibly promoted on the landing page."
  );

  if (!facts.whatsappDetected) {
    insights.push("WhatsApp capture path is missing.");
  } else if (!facts.whatsappTarget) {
    insights.push("WhatsApp is present, but the exact target was not cleanly extracted.");
  } else {
    insights.push(`WhatsApp path detected: ${facts.whatsappTarget}`);
  }

  if (!facts.bookingDetected) {
    insights.push("Booking path was not detected.");
  } else if (facts.bookingFlowQuality === "weak") {
    insights.push("Booking exists, but the flow quality still looks weak.");
  } else {
    insights.push("Booking path detected.");
  }

  if (signalFacts.next_best_action) {
    insights.push(signalFacts.next_best_action);
  }

  return insights.slice(0, 4);
}

function formatLocationFact(signalFacts: SignalFacts) {
  const branchCount = signalFacts.branch_count || signalFacts.branch_names?.length || 0;
  if (signalFacts.multi_clinic || branchCount > 1) {
    return `${branchCount || 2}+`;
  }
  if (branchCount === 1) {
    return "Single";
  }
  return "Single / unknown";
}

function formatAdsStatus(adsStatus: SignalFacts["ads_status"] | undefined) {
  if (adsStatus === "yes") {
    return "Yes";
  }
  if (adsStatus === "no") {
    return "No";
  }
  return "Not checked";
}

function getTopIssue(signalFacts: SignalFacts | null) {
  if (!signalFacts) {
    return "No analyzed truth yet";
  }
  if (signalFacts.top_issue) {
    return signalFacts.top_issue;
  }
  if (!signalFacts.phone_visible) {
    return "Phone is not prominent";
  }
  if (!signalFacts.whatsapp_detected) {
    return "WhatsApp capture is missing";
  }
  if (!signalFacts.booking_detected || signalFacts.booking_flow_quality === "weak") {
    return "Booking flow is weak";
  }
  if (!signalFacts.after_hours_capture) {
    return "No after-hours capture";
  }
  return "Conversion optimization opportunity";
}

function getNextBestAction(signalFacts: SignalFacts | null) {
  if (!signalFacts) {
    return "Analyze this lead";
  }
  if (signalFacts.next_best_action) {
    return signalFacts.next_best_action;
  }
  if (!signalFacts.phone_visible) {
    return "Make phone visible in header and hero";
  }
  if (!signalFacts.whatsapp_detected) {
    return "Add WhatsApp entry path and autoresponse";
  }
  if (!signalFacts.booking_detected || signalFacts.booking_flow_quality === "weak") {
    return "Fix booking flow and confirmation path";
  }
  if (!signalFacts.instant_response_path) {
    return "Add instant response automation";
  }
  return "Pitch AI conversion plumbing upgrade";
}

function getVisibleOutreachDrafts(outreach: ProcessedLeadDetails["outreach"] | undefined) {
  if (!outreach?.length) {
    return { drafts: [] as OutreachDraft[], hiddenCount: 0 };
  }

  const seen = new Set<string>();
  const uniqueDrafts: OutreachDraft[] = [];

  for (const draft of [...outreach].reverse()) {
    const signature = JSON.stringify({
      channel: draft.channel || "",
      subject: (draft.subject || "").trim(),
      body: (draft.body || "").replace(/\s+/g, " ").trim(),
    });

    if (seen.has(signature)) {
      continue;
    }

    seen.add(signature);
    uniqueDrafts.push(draft);
  }

  return {
    drafts: uniqueDrafts.slice(0, 2),
    hiddenCount: Math.max(uniqueDrafts.length - 2, 0),
  };
}

function getAnalysisBundle(
  lead: Lead | null | undefined,
  processedDetails: ProcessedLeadDetails | undefined
) {
  return processedDetails?.analysis_bundle || lead?.analysis_bundle || null;
}

function hydrateLeadFromStoredAnalysis(
  lead: Lead | null | undefined,
  processedDetails: ProcessedLeadDetails | null | undefined
) {
  if (!lead) {
    return null;
  }

  if (processedDetails?.analysis_state !== "analyzed") {
    return lead;
  }

  const analysisBundle = getAnalysisBundle(lead, processedDetails || undefined);
  const scoring = (processedDetails?.scoring || {}) as Record<string, unknown>;
  const scores = analysisBundle?.scores || {};
  const scoreBreakdown = (scoring.score_breakdown || scoring.breakdown || {}) as Record<string, unknown>;
  const finalScore =
    lead.final_score ??
    lead.score ??
    (scores.final_score as number | undefined) ??
    (scores.total_score as number | undefined) ??
    (scoreBreakdown.total_score as number | undefined) ??
    null;

  return {
    ...lead,
    score: finalScore ?? lead.score,
    final_score: finalScore ?? lead.final_score,
    score_kind: "final_score" as const,
    analysis_state: "analyzed" as const,
    analysis_updated_at: processedDetails.analysis_updated_at || lead.analysis_updated_at,
    signals_version: processedDetails.signals_version || lead.signals_version,
    signal_facts: processedDetails.signal_facts || lead.signal_facts,
  };
}

function getScoreSnapshot(
  lead: Lead | null | undefined,
  processedDetails: ProcessedLeadDetails | undefined
) {
  const analysisBundle = getAnalysisBundle(lead, processedDetails);
  const scoring = (processedDetails?.scoring || {}) as Record<string, unknown>;
  const scoreBreakdown = (scoring.score_breakdown || scoring.breakdown || {}) as Record<string, unknown>;
  const scores = analysisBundle?.scores || {};
  const finalScore =
    lead?.final_score ??
    lead?.score ??
    (scores.final_score as number | undefined) ??
    (scores.total_score as number | undefined) ??
    (scoreBreakdown.total_score as number | undefined) ??
    null;

  return {
    finalScore,
    demand: (scores.demand_score as number | undefined) ?? (scoreBreakdown.demand_score as number | undefined) ?? null,
    trust: (scores.trust_score as number | undefined) ?? (scoreBreakdown.trust_score as number | undefined) ?? null,
    leak: (scores.leak_score as number | undefined) ?? (scoreBreakdown.leak_score as number | undefined) ?? null,
    serviceability:
      (scores.serviceability_score as number | undefined) ??
      (scoreBreakdown.serviceability_score as number | undefined) ??
      null,
    offerFit:
      (scores.offer_fit_score as number | undefined) ??
      (scoreBreakdown.offer_fit_score as number | undefined) ??
      null,
  };
}

function formatBestContactChannel(value: string | null | undefined) {
  if (!value) {
    return "-";
  }

  return String(value)
    .replace(/_/g, " ")
    .replace(/\bwhatsapp\b/i, "WhatsApp")
    .replace(/\blinkedin\b/i, "LinkedIn");
}

function getContactIntelligence(
  lead: Lead | null,
  processedDetails: ProcessedLeadDetails | null | undefined,
  signalFacts: SignalFacts | null,
  analysisBundle: AnalysisBundle | null
) {
  const rankedContacts = buildRankedContactModel(lead, processedDetails || null);
  const scoreNarrative = buildLeadScoreNarrative(lead, processedDetails || null);
  const topContact = rankedContacts.topContact;
  const doctorNames = signalFacts?.doctor_names || [];
  const decisionMakerCandidates =
    signalFacts?.decision_maker_candidates || analysisBundle?.agent_context?.decision_maker_candidates || [];
  const branchContacts = signalFacts?.branch_contacts || analysisBundle?.agent_context?.branch_contacts || [];

  return {
    ...rankedContacts,
    scoreNarrative,
    decisionMakerName: rankedContacts.decisionMakerName,
    decisionMakerLinkedin:
      rankedContacts.decisionMakerLinkedin || topContact?.linkedin || null,
    decisionMakerRole:
      rankedContacts.decisionMakerRole || topContact?.role || null,
    decisionMakerSource:
      rankedContacts.decisionMakerSource || topContact?.source || null,
    decisionMakerConfidence:
      rankedContacts.decisionMakerConfidence ?? topContact?.score ?? null,
    bestContactPhone:
      rankedContacts.bestContactPhone || topContact?.phone || null,
    bestContactEmail:
      rankedContacts.bestContactEmail || topContact?.email || null,
    bestContactChannel:
      rankedContacts.bestContactChannel || topContact?.channel || null,
    bestContactReason:
      rankedContacts.bestContactReason || topContact?.reason || null,
    recommendedOffer: rankedContacts.recommendedOffer,
    doctorNames,
    decisionMakerCandidates,
    branchContacts,
    hasAny: Boolean(
      rankedContacts.topContact ||
        rankedContacts.alternateContacts.length ||
        rankedContacts.contactEvidence.length ||
        rankedContacts.bestContactReason ||
        scoreNarrative.whyThisLead ||
        scoreNarrative.trustSummary ||
        scoreNarrative.leakSummary ||
        scoreNarrative.offerFitSummary ||
        doctorNames.length
    ),
  };
}

function getDecisionLabel(finalScore: number | null | undefined) {
  if (finalScore == null) {
    return "Needs analysis";
  }
  if (finalScore >= 75) {
    return "High-priority";
  }
  if (finalScore >= 60) {
    return "Worth pursuing";
  }
  if (finalScore >= 45) {
    return "Conditional";
  }
  return "Low priority";
}

function getLeadRowPriority(lead: Lead) {
  let score = 0;
  if (lead.score_kind === "final_score") {
    score += 10;
  }
  if (lead.analysis_state === "analyzed") {
    score += 8;
  } else if (lead.analysis_state === "analyzing") {
    score += 2;
  }
  if ((lead.contacts?.length || 0) > 0) {
    score += 3;
  }
  if (lead.source && lead.source !== "Unknown") {
    score += 1;
  }
  if (lead.score != null) {
    score += 1;
  }
  return score;
}

function mergeLeadRows(existing: Lead[], incoming: Lead[]) {
  const byIdentity = new Map<string, Lead>();

  const upsert = (lead: Lead) => {
    if (!lead?.id || !lead?.company_name) {
      return;
    }

    const keys = [lead.id];
    if (lead.domain) {
      keys.push(`domain:${lead.domain.toLowerCase()}`);
    }

    const existingLead = keys
      .map((key) => byIdentity.get(key))
      .find(Boolean);
    const nextLead =
      existingLead && getLeadRowPriority(existingLead) > getLeadRowPriority(lead)
        ? { ...lead, ...existingLead }
        : { ...existingLead, ...lead };

    for (const key of keys) {
      byIdentity.set(key, nextLead as Lead);
    }
  };

  for (const lead of existing) {
    upsert(lead);
  }

  for (const lead of incoming) {
    if (!lead?.id || !lead?.company_name) {
      continue;
    }
    upsert(lead);
  }

  const deduped = new Map<string, Lead>();
  for (const lead of byIdentity.values()) {
    deduped.set(lead.id, lead);
  }
  return Array.from(deduped.values());
}

function sanitizeLeadRows(leads: Lead[]) {
  return leads.filter((lead) => Boolean(lead?.id && lead?.company_name));
}

function getNormalizedLeadIdentity(lead: Lead | null | undefined) {
  if (!lead) {
    return {
      domain: "",
      company: "",
    };
  }

  return {
    domain: String(lead.domain || "").trim().toLowerCase(),
    company: String(lead.company_name || "").trim().toLowerCase(),
  };
}

function resolveSelectedLeadId(
  selectedLeadId: string | null | undefined,
  mergedLeads: Lead[],
  candidateLeads: Lead[]
) {
  if (!selectedLeadId) {
    return null;
  }

  if (mergedLeads.some((lead) => lead.id === selectedLeadId)) {
    return selectedLeadId;
  }

  const sourceLead = candidateLeads.find((lead) => lead.id === selectedLeadId);
  if (!sourceLead) {
    return null;
  }

  const identity = getNormalizedLeadIdentity(sourceLead);

  const remappedLead = mergedLeads.find((lead) => {
    const candidateIdentity = getNormalizedLeadIdentity(lead);

    if (identity.domain && candidateIdentity.domain === identity.domain) {
      return true;
    }

    if (identity.company && candidateIdentity.company === identity.company) {
      return true;
    }

    return false;
  });

  return remappedLead?.id || null;
}

function replaceLeadRow(existing: Lead[], previousLeadId: string, incoming: Lead) {
  const normalizedDomain = incoming.domain?.toLowerCase() || "";
  const filtered = existing.filter(
    (lead) =>
      lead.id !== previousLeadId &&
      lead.id !== incoming.id &&
      (!normalizedDomain || lead.domain?.toLowerCase() !== normalizedDomain)
  );
  return sanitizeLeadRows([...filtered, incoming]);
}

function replaceProcessedLeadDetails(
  existing: Record<string, ProcessedLeadDetails> | undefined,
  previousLeadId: string,
  nextLeadId: string
) {
  const current = { ...(existing || {}) };
  const previousDetails = current[previousLeadId];
  if (previousLeadId !== nextLeadId) {
    delete current[previousLeadId];
  }
  if (previousDetails) {
    current[nextLeadId] = {
      ...(current[nextLeadId] || {}),
      ...previousDetails,
    };
  }
  return current;
}

function serializeLeadListPayload(
  leads: Lead[],
  metadata?: Pick<
    LeadListMetadata,
    "filter" | "processedDetails" | "selectedLeadId" | "sortBy" | "sortOrder"
  >
) {
  return JSON.stringify({
    filter: metadata?.filter || "",
    leads,
    processedDetails: metadata?.processedDetails || {},
    selectedLeadId: metadata?.selectedLeadId || null,
    sortBy: metadata?.sortBy || "score",
    sortOrder: metadata?.sortOrder || "desc",
  });
}

function getStableLeadKey(lead: Lead, index: number) {
  return `${lead.id || lead.company_name || "lead"}-${index}`;
}

function getStableContactKey(leadId: string, contact: Lead["contacts"][number], index: number) {
  return (
    contact.id ||
    `${leadId}-${contact.email || contact.phone || contact.name || "contact"}-${index}`
  );
}

function filterLeads(leads: Lead[], filter: string) {
  if (!filter) {
    return leads;
  }

  const normalizedFilter = filter.toLowerCase();

  return leads.filter(
    (lead) =>
      lead.company_name.toLowerCase().includes(normalizedFilter) ||
      lead.domain.toLowerCase().includes(normalizedFilter) ||
      lead.niche.toLowerCase().includes(normalizedFilter) ||
      getLeadSource(lead).toLowerCase().includes(normalizedFilter) ||
      getLeadFit(lead).toLowerCase().includes(normalizedFilter)
  );
}

function sortLeads(
  leads: Lead[],
  sortBy: string,
  sortOrder: "asc" | "desc"
) {
  return [...leads].sort((a, b) => {
    if (sortBy === "score") {
      const aFinal = a.score_kind === "final_score" ? 1 : 0;
      const bFinal = b.score_kind === "final_score" ? 1 : 0;

      if (aFinal !== bFinal) {
        return sortOrder === "asc" ? aFinal - bFinal : bFinal - aFinal;
      }

      const aScore = a.score ?? -1;
      const bScore = b.score ?? -1;
      if (aScore !== bScore) {
        return sortOrder === "asc" ? aScore - bScore : bScore - aScore;
      }

      const aName = (a.company_name || "").toLowerCase();
      const bName = (b.company_name || "").toLowerCase();
      if (aName !== bName) {
        return aName.localeCompare(bName);
      }

      return (a.id || "").localeCompare(b.id || "");
    }

    let aVal: unknown = a[sortBy as keyof Lead];
    let bVal: unknown = b[sortBy as keyof Lead];

    if (typeof aVal === "string") {
      aVal = aVal.toLowerCase();
    }
    if (typeof bVal === "string") {
      bVal = bVal.toLowerCase();
    }

    if (aVal == null && bVal == null) {
      return 0;
    }
    if (aVal == null) {
      return sortOrder === "asc" ? -1 : 1;
    }
    if (bVal == null) {
      return sortOrder === "asc" ? 1 : -1;
    }
    if (aVal < bVal) {
      return sortOrder === "asc" ? -1 : 1;
    }
    if (aVal > bVal) {
      return sortOrder === "asc" ? 1 : -1;
    }
    const aName = (a.company_name || "").toLowerCase();
    const bName = (b.company_name || "").toLowerCase();
    if (aName !== bName) {
      return aName.localeCompare(bName);
    }
    return (a.id || "").localeCompare(b.id || "");
  });
}

function LeadRow({ lead, onClick }: { lead: Lead; onClick: () => void }) {
  const scoreColor =
    (lead.score || 0) >= 80
      ? "text-green-600"
      : (lead.score || 0) >= 60
        ? "text-yellow-600"
        : "text-red-600";

  return (
    <tr
      className="cursor-pointer border-zinc-200 border-b hover:bg-zinc-50 dark:border-zinc-700 dark:hover:bg-zinc-800"
      onClick={onClick}
    >
      <td className="p-3">
        <div className="font-medium">{lead.company_name}</div>
        <div className="text-xs text-zinc-500">{lead.domain}</div>
        {getLeadSummary(lead) && (
          <div className="mt-1 text-xs text-zinc-500">
            {getLeadSummary(lead)}
          </div>
        )}
      </td>
      <td className="p-3 text-sm">{getLeadFit(lead)}</td>
      <td className="p-3 text-sm text-zinc-500">{getLeadSource(lead)}</td>
      <td className="p-3 text-sm">{lead.geo}</td>
      <td className={`p-3 font-bold text-sm ${scoreColor}`}>
        <div>{lead.score ?? "-"}</div>
        <div className="text-[10px] uppercase tracking-[0.18em] text-zinc-500">
          {getScoreLabel(lead)}
        </div>
      </td>
      <td className="p-3">
        <span className="rounded-full bg-zinc-100 px-2 py-1 text-xs dark:bg-zinc-800">
          {formatLeadStatus(lead.status)}
        </span>
        <div className="mt-1 text-[10px] uppercase tracking-[0.18em] text-zinc-500">
          {getAnalysisLabel(lead)}
        </div>
      </td>
      <td className="p-3 text-sm text-zinc-500">
        {lead.contacts?.length || 0}
      </td>
    </tr>
  );
}

function parseLeads(content: string): Lead[] {
  return parseLeadListPayload(content).leads;
}

function parseLeadListPayload(content: string): {
  filter: string;
  leads: Lead[];
  processedDetails: Record<string, ProcessedLeadDetails>;
  selectedLeadId: string | null;
  sortBy: string;
  sortOrder: "asc" | "desc";
} {
  if (!content) {
    return {
      filter: "",
      leads: [],
      processedDetails: {},
      selectedLeadId: null,
      sortBy: "score",
      sortOrder: "desc",
    };
  }

  try {
    const parsed = JSON.parse(content) as Lead[] | LeadListPayload;
    const payload = Array.isArray(parsed) ? ({ leads: parsed } satisfies LeadListPayload) : parsed;

    return {
      filter: payload.filter || "",
      leads: sanitizeLeadRows(payload.leads || []),
      processedDetails: payload.processedDetails || payload.processed_details || {},
      selectedLeadId: payload.selectedLeadId || null,
      sortBy: payload.sortBy || "score",
      sortOrder: payload.sortOrder === "asc" ? "asc" : "desc",
    };
  } catch {
    return {
      filter: "",
      leads: [],
      processedDetails: {},
      selectedLeadId: null,
      sortBy: "score",
      sortOrder: "desc",
    };
  }
}

function LeadListContent({
  content,
  metadata,
  setMetadata,
}: {
  content: string;
  metadata: LeadListMetadata;
  setMetadata: (fn: (prev: LeadListMetadata) => LeadListMetadata) => void;
}) {
  const [selectedLead, setSelectedLead] = useState<Lead | null>(null);
  const [selectedLeadLive, setSelectedLeadLive] = useState<Lead | null>(null);
  const [selectedLeadLiveDetails, setSelectedLeadLiveDetails] =
    useState<ProcessedLeadDetails | null>(null);
  const [processingIds, setProcessingIds] = useState<string[]>([]);
  const [isRefreshingTruth, setIsRefreshingTruth] = useState(false);
  const processControllersRef = useRef<Record<string, AbortController>>({});
  const founderIntelCacheRef = useRef<Record<string, FounderIntelPayload>>({});
  const leadsRef = useRef<Lead[]>([]);
  const processedDetailsRef = useRef<Record<string, ProcessedLeadDetails>>({});
  const selectedLeadIdRef = useRef<string | null>(null);
  const persistTimeoutRef = useRef<number | null>(null);
  const { artifact, setArtifact } = useArtifact();

  const contentPayload = parseLeadListPayload(content);
  const contentLeads = contentPayload.leads;
  const metadataLeads = sanitizeLeadRows(metadata?.leads || []);
  const mergedProcessedDetails = {
    ...(contentPayload.processedDetails || {}),
    ...(metadata?.processedDetails || {}),
  };
  const mergedRawLeads = sanitizeLeadRows(
    mergeLeadRows(contentLeads, metadataLeads)
  );
  const leads = sanitizeLeadRows(
    mergedRawLeads.map(
      (lead) =>
        hydrateLeadFromStoredAnalysis(lead, mergedProcessedDetails?.[lead.id] || null) || lead
    )
  );
  const processedDetails = mergedProcessedDetails;

  const filter = metadata?.filter || contentPayload.filter || "";
  const filteredLeads = filterLeads(leads, filter);

  const sortBy = metadata?.sortBy || contentPayload.sortBy || "score";
  const sortOrder = metadata?.sortOrder || contentPayload.sortOrder || "desc";
  const sortedLeads = sortLeads(filteredLeads, sortBy, sortOrder);
  const persistedSelectedLeadId =
    resolveSelectedLeadId(
      metadata?.selectedLeadId || contentPayload.selectedLeadId || null,
      leads,
      [...metadataLeads, ...contentLeads]
    ) || null;

  const queueLeadListDocumentSave = (nextContent: string) => {
    if (!artifact?.documentId || artifact.documentId === "init") {
      return;
    }

    if (persistTimeoutRef.current) {
      window.clearTimeout(persistTimeoutRef.current);
    }

    persistTimeoutRef.current = window.setTimeout(() => {
      void fetch(`/api/document?id=${artifact.documentId}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          title: artifact.title || "Lead List",
          content: nextContent,
          kind: artifact.kind || "lead-list",
        }),
      }).catch(() => {});
    }, 350);
  };

  useEffect(() => {
    leadsRef.current = leads;
  }, [leads]);

  useEffect(() => {
    processedDetailsRef.current = processedDetails || {};
  }, [processedDetails]);

  useEffect(() => {
    selectedLeadIdRef.current = persistedSelectedLeadId;
  }, [persistedSelectedLeadId]);

  const persistLeadListContent = ({
    nextFilter,
    nextLeads,
    nextProcessedDetails,
    nextSelectedLeadId,
    nextSortBy,
    nextSortOrder,
  }: {
    nextFilter?: string;
    nextLeads?: Lead[];
    nextProcessedDetails?: Record<string, ProcessedLeadDetails>;
    nextSelectedLeadId?: string | null;
    nextSortBy?: string;
    nextSortOrder?: "asc" | "desc";
  }) => {
    const nextContent = serializeLeadListPayload(nextLeads || leads, {
      filter: nextFilter ?? filter,
      processedDetails: nextProcessedDetails ?? processedDetails ?? {},
      selectedLeadId:
        nextSelectedLeadId !== undefined ? nextSelectedLeadId : persistedSelectedLeadId,
      sortBy: nextSortBy ?? sortBy,
      sortOrder: nextSortOrder ?? sortOrder,
    });

    setArtifact((draft) => ({
      ...draft,
      content: nextContent,
    }));
    queueLeadListDocumentSave(nextContent);
  };

  useEffect(() => {
    const nextContent = serializeLeadListPayload(leads, {
      filter,
      processedDetails: processedDetails || {},
      selectedLeadId: persistedSelectedLeadId,
      sortBy,
      sortOrder,
    });

    if (nextContent === content) {
      return;
    }

    setArtifact((draft) => ({
      ...draft,
      content: nextContent,
    }));
    queueLeadListDocumentSave(nextContent);
  }, [
    artifact.documentId,
    artifact.kind,
    artifact.title,
    content,
    filter,
    leads,
    persistedSelectedLeadId,
    processedDetails,
    setArtifact,
    sortBy,
    sortOrder,
  ]);

  useEffect(() => {
    return () => {
      if (persistTimeoutRef.current) {
        window.clearTimeout(persistTimeoutRef.current);
      }
    };
  }, []);

  const hydrateFounderIntel = async (
    baseLead: Lead,
    baseProcessedDetails: ProcessedLeadDetails | null | undefined
  ) => {
    if (!baseLead?.id || !needsFounderIntelligence(baseLead, baseProcessedDetails)) {
      return {
        lead: baseLead,
        processedDetails: baseProcessedDetails || null,
      };
    }

    try {
      const cachedFounderIntel = founderIntelCacheRef.current[baseLead.id];
      const founderIntel =
        cachedFounderIntel || (await fetchFounderIntelligence(baseLead));

      if (!cachedFounderIntel && Object.keys(founderIntel || {}).length > 0) {
        founderIntelCacheRef.current[baseLead.id] = founderIntel;
      }

      if (!founderIntel || Object.keys(founderIntel).length === 0) {
        return {
          lead: baseLead,
          processedDetails: baseProcessedDetails || null,
        };
      }

      const nextProcessedDetails = mergeFounderIntelligenceIntoProcessedDetails(
        baseProcessedDetails || null,
        founderIntel
      ) as ProcessedLeadDetails;

      return {
        lead: {
          ...baseLead,
          signal_facts: nextProcessedDetails?.signal_facts || baseLead.signal_facts,
        } as Lead,
        processedDetails: nextProcessedDetails,
      };
    } catch {
      return {
        lead: baseLead,
        processedDetails: baseProcessedDetails || null,
      };
    }
  };

  const syncLeadListState = ({
    nextLeads,
    nextProcessedDetails,
    nextSelectedLeadId,
  }: {
    nextLeads: Lead[];
    nextProcessedDetails?: Record<string, ProcessedLeadDetails>;
    nextSelectedLeadId?: string | null;
  }) => {
    setMetadata((prev: LeadListMetadata) => {
      const updated = {
        ...prev,
        leads: nextLeads,
        processedDetails: nextProcessedDetails ?? prev.processedDetails ?? {},
        selectedLeadId:
          nextSelectedLeadId !== undefined
            ? nextSelectedLeadId
            : prev.selectedLeadId ?? contentPayload.selectedLeadId ?? null,
      };

      persistLeadListContent({
        nextFilter: updated.filter,
        nextLeads: updated.leads,
        nextProcessedDetails: updated.processedDetails,
        nextSelectedLeadId: updated.selectedLeadId ?? null,
        nextSortBy: updated.sortBy,
        nextSortOrder: updated.sortOrder,
      });

      return updated;
    });
  };

  useEffect(() => {
    if (!persistedSelectedLeadId) {
      if (selectedLead) {
        setSelectedLead(null);
        setSelectedLeadLive(null);
        setSelectedLeadLiveDetails(null);
      }
      return;
    }

    if (selectedLead?.id === persistedSelectedLeadId) {
      return;
    }

    const rehydratedLead = leads.find((lead) => lead.id === persistedSelectedLeadId);
    if (!rehydratedLead) {
      return;
    }

    setSelectedLead(rehydratedLead);
    setSelectedLeadLive(null);
    setSelectedLeadLiveDetails(null);
  }, [persistedSelectedLeadId, leads, selectedLead]);

  useEffect(() => {
    if (!selectedLead) {
      setSelectedLeadLive(null);
      setSelectedLeadLiveDetails(null);
      return;
    }

    const hasSelectedLead = leads.some((lead) => lead.id === selectedLead.id);
    if (!hasSelectedLead) {
      setSelectedLead(null);
      setSelectedLeadLive(null);
      setSelectedLeadLiveDetails(null);
    }
  }, [leads, selectedLead]);

  if (leads.length === 0) {
    return (
      <div className="flex h-full items-center justify-center p-8">
        <div className="text-center text-zinc-500">
          <div className="text-lg">No leads found</div>
          <div className="text-sm">Use the discover tool to find leads</div>
        </div>
      </div>
    );
  }

  const handleSort = (column: string) => {
    const nextSortOrder =
      sortBy === column && sortOrder === "desc" ? "asc" : "desc";
    setMetadata((prev: LeadListMetadata) => ({
      ...prev,
      sortBy: column,
      sortOrder: nextSortOrder,
    }));
    persistLeadListContent({
      nextSortBy: column,
      nextSortOrder,
    });
  };

  const clearProcessing = (leadIds: string[]) => {
    for (const leadId of leadIds) {
      delete processControllersRef.current[leadId];
    }
    setProcessingIds((prev) => prev.filter((id) => !leadIds.includes(id)));
  };

  const remapProcessingIds = (mappings: Array<{ from: string; to: string }>) => {
    const validMappings = mappings.filter(
      ({ from, to }) => Boolean(from) && Boolean(to) && from !== to
    );
    if (!validMappings.length) {
      return;
    }

    for (const { from, to } of validMappings) {
      const controller = processControllersRef.current[from];
      if (controller && !processControllersRef.current[to]) {
        processControllersRef.current[to] = controller;
      }
      delete processControllersRef.current[from];
    }

    setProcessingIds((prev) => {
      const remapped = prev.map((id) => {
        const mapping = validMappings.find(({ from }) => from === id);
        return mapping?.to || id;
      });
      return Array.from(new Set(remapped));
    });
  };

  const stopProcessing = (leadIds?: string[]) => {
    const idsToStop = leadIds?.length ? leadIds : Object.keys(processControllersRef.current);
    const controllers = Array.from(
      new Set(
        idsToStop
          .map((leadId) => processControllersRef.current[leadId])
          .filter((controller): controller is AbortController => Boolean(controller))
      )
    );

    for (const controller of controllers) {
      controller.abort();
    }

    clearProcessing(idsToStop);
    toast.success(
      idsToStop.length === 1
        ? "Stopped the running lead process."
        : "Stopped all running lead processes."
    );
  };

  const processLeads = async (
    leadIds: string[],
    options?: {
      includeOutreach?: boolean;
      successMessage?: string;
      emptyMessage?: string;
    }
  ) => {
    if (leadIds.length === 0) {
      return;
    }

    const freshLeadIds = leadIds.filter((leadId) => !processingIds.includes(leadId));
    if (freshLeadIds.length === 0) {
      return;
    }

    const controller = new AbortController();
    for (const leadId of freshLeadIds) {
      processControllersRef.current[leadId] = controller;
    }

    setProcessingIds((prev) => Array.from(new Set([...prev, ...freshLeadIds])));

    let activeLeadIds = [...freshLeadIds];
    let workingLeadRows = leadsRef.current;
    let workingProcessedDetails = processedDetailsRef.current;
    let workingSelectedLeadId = selectedLeadIdRef.current;

    try {
      const persistedLeadMap = new Map<string, Lead>();
      let nextLeadRows = workingLeadRows;
      let nextProcessedDetails = workingProcessedDetails;
      let nextSelectedLeadId = workingSelectedLeadId;

      for (const leadId of freshLeadIds) {
        const rawLead = workingLeadRows.find((candidate) => candidate.id === leadId);
        if (!rawLead) {
          continue;
        }

        if (isUuidLeadId(rawLead.id)) {
          persistedLeadMap.set(leadId, rawLead);
          continue;
        }

        const importedLead = await ensurePersistedLead(rawLead);
        persistedLeadMap.set(leadId, importedLead);
        nextLeadRows = replaceLeadRow(nextLeadRows, rawLead.id, importedLead);
        nextProcessedDetails = replaceProcessedLeadDetails(
          nextProcessedDetails,
          rawLead.id,
          importedLead.id
        );
        if (nextSelectedLeadId === rawLead.id) {
          nextSelectedLeadId = importedLead.id;
        }
      }

      if (
        nextLeadRows !== workingLeadRows ||
        nextProcessedDetails !== workingProcessedDetails ||
        nextSelectedLeadId !== workingSelectedLeadId
      ) {
        syncLeadListState({
          nextLeads: nextLeadRows,
          nextProcessedDetails,
          nextSelectedLeadId,
        });
      }

      workingLeadRows = nextLeadRows;
      workingProcessedDetails = nextProcessedDetails;
      workingSelectedLeadId = nextSelectedLeadId ?? null;

      const remappedLeadIds = freshLeadIds.map(
        (leadId) => persistedLeadMap.get(leadId)?.id || leadId
      );
      remapProcessingIds(
        freshLeadIds.map((leadId, index) => ({
          from: leadId,
          to: remappedLeadIds[index],
        }))
      );
      activeLeadIds = remappedLeadIds;

      const response = await fetch(ZRAI_ENDPOINTS.processLeads, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        signal: controller.signal,
        body: JSON.stringify({
          lead_ids: activeLeadIds,
          include_outreach: options?.includeOutreach ?? true,
        }),
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(errorText || "Processing selected leads failed");
      }

        const payload = getPayloadData((await response.json()) as {
          processed?: ProcessedLeadResponseItem[];
        });
        const processedLeads = (payload.processed || [])
          .filter((item: ProcessedLeadResponseItem) => item.success && item.lead)
          .map((item: ProcessedLeadResponseItem) => item.lead as Lead);
        const processedDetailEntries = (payload.processed || [])
          .filter((item: ProcessedLeadResponseItem) => item.success && item.lead)
          .map((item: ProcessedLeadResponseItem) => [
          item.lead!.id,
          {
            enrichment: item.enrichment || {},
            intent: item.intent || {},
            proof: item.proof || {},
            outreach: item.outreach || [],
            scoring: item.scoring || {},
            signal_facts: item.signal_facts,
            analysis_bundle: item.analysis_bundle,
            analysis_state: item.analysis_state,
            analysis_updated_at: item.analysis_updated_at,
            signals_version: item.signals_version,
          } satisfies ProcessedLeadDetails,
        ] as const);

      if (processedLeads.length === 0) {
        toast.error(options?.emptyMessage || "No leads were processed successfully.");
        return;
      }

      const mergedLeads = mergeLeadRows(workingLeadRows, processedLeads);
      const mergedDetails = {
        ...workingProcessedDetails,
        ...Object.fromEntries(processedDetailEntries),
      };
      syncLeadListState({
        nextLeads: mergedLeads,
        nextProcessedDetails: mergedDetails,
        nextSelectedLeadId: workingSelectedLeadId,
      });

      if (selectedLead) {
        const updatedLead = mergedLeads.find((lead) => lead.id === selectedLead.id);
        if (updatedLead) {
          setSelectedLead(updatedLead);
          setSelectedLeadLive(updatedLead);
          const updatedDetails = mergedDetails[updatedLead.id];
          if (updatedDetails) {
            setSelectedLeadLiveDetails(updatedDetails);
          }
        }
      }

      toast.success(
        options?.successMessage ||
          `Processed ${processedLeads.length} lead${processedLeads.length === 1 ? "" : "s"} through enrich, intent, proof, and outreach.`
      );
      } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") {
        toast.success("Lead processing stopped.");
        return;
      }
      toast.error(error instanceof Error ? error.message : "Lead processing failed");
    } finally {
      clearProcessing(activeLeadIds);
    }
  };

  useEffect(() => {
    if (!processingIds.length) {
      return;
    }

    const completedIds = processingIds.filter((leadId) => {
      const rowLead =
        leads.find((candidate) => candidate.id === leadId) ||
        (selectedLead?.id === leadId ? selectedLead : null) ||
        (selectedLeadLive?.id === leadId ? selectedLeadLive : null) ||
        (metadata?.liveSelectedLead?.id === leadId ? metadata.liveSelectedLead : null);
      const rowDetails =
        processedDetails?.[leadId] ||
        (selectedLeadLive?.id === leadId ? selectedLeadLiveDetails : null) ||
        (metadata?.liveSelectedLead?.id === leadId ? metadata.liveSelectedLeadDetails : null);

      return isTerminalAnalysisState(rowLead, rowDetails);
    });

    if (completedIds.length) {
      clearProcessing(completedIds);
    }
  }, [
    processingIds,
    leads,
    processedDetails,
    selectedLead,
    selectedLeadLive,
    selectedLeadLiveDetails,
    metadata?.liveSelectedLead,
    metadata?.liveSelectedLeadDetails,
  ]);

  const refreshSelectedLeadTruth = async () => {
    if (!selectedLead?.id) {
      return;
    }

    setIsRefreshingTruth(true);
    try {
      const response = await fetch(getZRAILeadByIdEndpoint(selectedLead.id));
      if (!response.ok) {
        throw new Error(await response.text());
      }

        const payload = await response.json();
        const payloadData = getPayloadData(payload);
        if (!(payload?.success ?? true) || !payloadData?.lead) {
          throw new Error("Lead truth refresh failed.");
        }

        const latestLead = payloadData.lead as Lead;
        const latestProcessedDetailsRaw = payloadData.processed_details
          ? ({
              ...(payloadData.processed_details || {}),
              signal_facts: payloadData.signal_facts || payloadData.processed_details?.signal_facts || null,
              analysis_bundle: payloadData.analysis_bundle || payloadData.processed_details?.analysis_bundle || null,
              analysis_state: payloadData.analysis_state || payloadData.processed_details?.analysis_state || null,
              analysis_updated_at:
                payloadData.analysis_updated_at || payloadData.processed_details?.analysis_updated_at || null,
              signals_version: payloadData.signals_version || payloadData.processed_details?.signals_version || null,
            } as ProcessedLeadDetails)
          : null;
      const hydrated = await hydrateFounderIntel(latestLead, latestProcessedDetailsRaw);
      const baseLeads = leadsRef.current;
      const baseProcessedDetails = processedDetailsRef.current;
      const mergedLeads = mergeLeadRows(baseLeads, [hydrated.lead]);
      syncLeadListState({
        nextLeads: mergedLeads,
        nextProcessedDetails: hydrated.processedDetails
          ? {
              ...baseProcessedDetails,
              [selectedLead.id]: hydrated.processedDetails,
            }
          : baseProcessedDetails,
        nextSelectedLeadId: selectedLead.id,
      });
      setSelectedLead(mergedLeads.find((lead) => lead.id === selectedLead.id) || hydrated.lead);
      setSelectedLeadLive(hydrated.lead);
      setSelectedLeadLiveDetails(hydrated.processedDetails);
      setMetadata((prev: LeadListMetadata) => ({
        ...prev,
        liveSelectedLead: hydrated.lead,
        liveSelectedLeadDetails: hydrated.processedDetails,
      }));
      toast.success("Lead truth refreshed.");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Lead truth refresh failed");
    } finally {
      setIsRefreshingTruth(false);
    }
  };

  const pollLeadAnalysisCompletion = async (leadId: string) => {
    for (let attempt = 0; attempt < 45; attempt += 1) {
      await new Promise((resolve) => setTimeout(resolve, 4000));

      const response = await fetch(getZRAILeadByIdEndpoint(leadId));
      if (!response.ok) {
        continue;
      }

      const payload = await response.json();
      const payloadData = getPayloadData(payload);
      const latestLead = payloadData?.lead as Lead | undefined;
      const nextAnalysisState =
        payloadData?.analysis_state ||
        payloadData?.processed_details?.analysis_state ||
        latestLead?.analysis_state;

      if (!latestLead || !nextAnalysisState) {
        continue;
      }

      if (nextAnalysisState === "failed") {
        throw new Error("Lead analysis failed in the backend.");
      }

      if (nextAnalysisState !== "analyzed") {
        continue;
      }

      const latestProcessedDetailsRaw = payloadData.processed_details
        ? ({
            ...(payloadData.processed_details || {}),
            signal_facts: payloadData.signal_facts || payloadData.processed_details?.signal_facts || null,
            analysis_bundle: payloadData.analysis_bundle || payloadData.processed_details?.analysis_bundle || null,
            analysis_state: payloadData.analysis_state || payloadData.processed_details?.analysis_state || null,
            analysis_updated_at:
              payloadData.analysis_updated_at || payloadData.processed_details?.analysis_updated_at || null,
            signals_version: payloadData.signals_version || payloadData.processed_details?.signals_version || null,
          } as ProcessedLeadDetails)
        : null;
      const hydrated = await hydrateFounderIntel(latestLead, latestProcessedDetailsRaw);

      const baseLeads = leadsRef.current;
      const baseProcessedDetails = processedDetailsRef.current;
      const mergedLeads = mergeLeadRows(baseLeads, [hydrated.lead]);
      syncLeadListState({
        nextLeads: mergedLeads,
        nextProcessedDetails: hydrated.processedDetails
          ? {
              ...baseProcessedDetails,
              [leadId]: hydrated.processedDetails,
            }
          : baseProcessedDetails,
        nextSelectedLeadId: leadId,
      });
      setSelectedLead(mergedLeads.find((lead) => lead.id === leadId) || hydrated.lead);
      setSelectedLeadLive(hydrated.lead);
      setSelectedLeadLiveDetails(hydrated.processedDetails);
      setMetadata((prev: LeadListMetadata) => ({
        ...prev,
        liveSelectedLead: hydrated.lead,
        liveSelectedLeadDetails: hydrated.processedDetails,
      }));
      clearProcessing([leadId]);
      toast.success("Lead analyzed.");
      return;
    }

    clearProcessing([leadId]);
    toast.success("Analysis is still running. Use Refresh truth in a moment.");
  };

  const analyzeSelectedLead = async () => {
    if (!selectedLead?.id) {
      return;
    }

    try {
      let workingLeadRows = leadsRef.current;
      let workingProcessedDetails = processedDetailsRef.current;
      const resolvedLead = isUuidLeadId(selectedLead.id)
        ? selectedLead
        : await ensurePersistedLead(selectedLead);
      const effectiveLead =
        resolvedLead.id === selectedLead.id
          ? selectedLead
          : ({
              ...resolvedLead,
              analysis_state: selectedLead.analysis_state,
              score_kind: selectedLead.score_kind,
              preview_summary: selectedLead.preview_summary,
              source: resolvedLead.source || selectedLead.source,
              source_label: resolvedLead.source_label || selectedLead.source_label,
            } as Lead);

      if (effectiveLead.id !== selectedLead.id) {
        const nextLeadRows = replaceLeadRow(workingLeadRows, selectedLead.id, effectiveLead);
        const nextProcessedDetails = replaceProcessedLeadDetails(
          workingProcessedDetails,
          selectedLead.id,
          effectiveLead.id
        );
        syncLeadListState({
          nextLeads: nextLeadRows,
          nextProcessedDetails,
          nextSelectedLeadId: effectiveLead.id,
        });
        setSelectedLead(effectiveLead);
        setSelectedLeadLive(effectiveLead);
        setSelectedLeadLiveDetails(nextProcessedDetails[effectiveLead.id] || null);
        workingLeadRows = nextLeadRows;
        workingProcessedDetails = nextProcessedDetails;
      }

      const controller = new AbortController();
      processControllersRef.current[effectiveLead.id] = controller;
      setProcessingIds((prev) => Array.from(new Set([...prev, effectiveLead.id])));

      const response = await fetch(ZRAI_ENDPOINTS.analyzeLead, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        signal: controller.signal,
        body: JSON.stringify({
          lead_id: effectiveLead.id,
          include_outreach: false,
          lead: effectiveLead,
        }),
      });

      if (!response.ok) {
        throw new Error(await response.text());
      }

      const payload = await response.json();
      const payloadData = getPayloadData(payload);
      const queued =
        payloadData?.queued ||
        payload?.queued ||
        payloadData?.analysis_state === "analyzing" ||
        payload?.analysis_state === "analyzing";

      if (queued) {
        const queuedLead = {
          ...effectiveLead,
          analysis_state: "analyzing",
        } as Lead;
        const mergedQueuedLeads = mergeLeadRows(workingLeadRows, [queuedLead]);
        const mergedQueuedDetails = {
          ...workingProcessedDetails,
          [queuedLead.id]: {
            ...(workingProcessedDetails?.[queuedLead.id] || {}),
            analysis_state: "analyzing",
            analysis_updated_at: payloadData?.analysis_updated_at || payload?.analysis_updated_at || null,
          } as ProcessedLeadDetails,
        };
        syncLeadListState({
          nextLeads: mergedQueuedLeads,
          nextProcessedDetails: mergedQueuedDetails,
          nextSelectedLeadId: queuedLead.id,
        });
        setSelectedLead(mergedQueuedLeads.find((lead) => lead.id === queuedLead.id) || queuedLead);
        setSelectedLeadLive(queuedLead);
        setSelectedLeadLiveDetails(mergedQueuedDetails[queuedLead.id] || null);
        toast.success("Analysis started.");
        await pollLeadAnalysisCompletion(queuedLead.id);
        return;
      }

      if (!(payload?.success ?? true) || !payloadData?.lead) {
        throw new Error("Lead analysis failed.");
      }

      const analyzedLead = payloadData.lead as Lead;
      const analyzedProcessedDetailsRaw = {
        ...(payloadData.processed_details || {}),
        signal_facts: payloadData.signal_facts || payloadData.processed_details?.signal_facts || null,
        analysis_bundle: payloadData.analysis_bundle || payloadData.processed_details?.analysis_bundle || null,
        analysis_state: payloadData.analysis_state || payloadData.processed_details?.analysis_state || "analyzed",
        analysis_updated_at:
          payloadData.analysis_updated_at || payloadData.processed_details?.analysis_updated_at || null,
        signals_version: payloadData.signals_version || payloadData.processed_details?.signals_version || null,
      } as ProcessedLeadDetails;
      const hydrated = await hydrateFounderIntel(analyzedLead, analyzedProcessedDetailsRaw);

      const mergedLeads = mergeLeadRows(workingLeadRows, [hydrated.lead]);
      const mergedDetails = {
        ...workingProcessedDetails,
        [analyzedLead.id]: hydrated.processedDetails || analyzedProcessedDetailsRaw,
      };
      syncLeadListState({
        nextLeads: mergedLeads,
        nextProcessedDetails: mergedDetails,
        nextSelectedLeadId: analyzedLead.id,
      });
      setSelectedLead(mergedLeads.find((lead) => lead.id === analyzedLead.id) || hydrated.lead);
      setSelectedLeadLive(hydrated.lead);
      setSelectedLeadLiveDetails(hydrated.processedDetails);
      toast.success("Lead analyzed.");
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") {
        toast.success("Lead analysis stopped.");
      } else {
        toast.error(error instanceof Error ? error.message : "Lead analysis failed");
      }
      } finally {
      const currentLeadId = isUuidLeadId(selectedLead.id)
        ? selectedLead.id
        : selectedLeadLive?.id || metadata?.liveSelectedLead?.id || selectedLead.id;
      clearProcessing([currentLeadId]);
      }
  };

  const inspectorLead =
    hydrateLeadFromStoredAnalysis(selectedLeadLive, selectedLeadLiveDetails) ||
    hydrateLeadFromStoredAnalysis(metadata?.liveSelectedLead, metadata?.liveSelectedLeadDetails || null) ||
    hydrateLeadFromStoredAnalysis(
      selectedLead,
      selectedLead ? processedDetails[selectedLead.id] : undefined
    ) ||
    selectedLead;
  const selectedLeadDetails =
    selectedLeadLiveDetails ||
    metadata?.liveSelectedLeadDetails ||
    (inspectorLead ? processedDetails[inspectorLead.id] : undefined);
  const selectedLeadEffectiveState = getResolvedAnalysisState(inspectorLead, selectedLeadDetails);
  const isSelectedLeadProcessing = selectedLead
    ? processingIds.includes(inspectorLead?.id || selectedLead.id) &&
      selectedLeadEffectiveState !== "analyzed" &&
      selectedLeadEffectiveState !== "failed"
    : false;
  const analysisBundle = getAnalysisBundle(inspectorLead, selectedLeadDetails);
  const signalFacts = getSignalFacts(inspectorLead, selectedLeadDetails);
  const contactIntel = getContactIntelligence(
    inspectorLead,
    selectedLeadDetails,
    signalFacts,
    analysisBundle
  );
  const scoreNarrative = buildLeadScoreNarrative(inspectorLead, selectedLeadDetails);
  const proofExtraction = selectedLeadDetails?.proof?.extraction_data as Record<string, unknown> | undefined;
  const proofFacts = getCanonicalProofFacts(signalFacts, proofExtraction);
  const proofInsights = getCanonicalProofInsights(
    signalFacts,
    proofExtraction,
    selectedLeadDetails?.proof?.audit_bullets
  );
  const outreachSummary = getVisibleOutreachDrafts(selectedLeadDetails?.outreach);
  const scoreSnapshot = getScoreSnapshot(inspectorLead, selectedLeadDetails);
  const hasFinalRows = leads.some((lead) => lead.score_kind === "final_score");
  const hasPreviewRows = leads.some((lead) => lead.score_kind !== "final_score");
  const avgScoreLabel = hasFinalRows && hasPreviewRows
    ? "Avg visible score"
    : hasFinalRows
      ? "Avg final"
      : "Avg match";

  return (
    <div className="flex h-full min-h-0 flex-row">
      <div className="flex min-h-0 min-w-0 flex-1 flex-col">
        <div className="border-zinc-200 border-b p-3 dark:border-zinc-700">
            <input
              className="w-full rounded-md border border-zinc-300 bg-transparent px-3 py-2 text-sm dark:border-zinc-600"
              onChange={(event) => {
                const nextFilter = event.target.value;
                setMetadata((prev: LeadListMetadata) => ({
                  ...prev,
                  filter: nextFilter,
                }));
                persistLeadListContent({
                  nextFilter,
                });
              }}
              placeholder="Filter leads..."
              type="text"
              value={filter}
            />
        </div>

        <div className="flex gap-4 border-zinc-200 border-b bg-zinc-50 p-3 text-sm dark:border-zinc-700 dark:bg-zinc-800">
          <span>Total: {leads.length}</span>
          <span>Filtered: {filteredLeads.length}</span>
          <span>
            {avgScoreLabel}:{" "}
            {Math.round(
              leads.reduce((sum, lead) => sum + (lead.score || 0), 0) /
                leads.length
            ) || 0}
          </span>
          <div className="ml-auto flex items-center gap-2">
            <button
              className="rounded-md bg-emerald-600 px-3 py-2 text-xs text-white transition hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-50"
              disabled={!sortedLeads.length || !!processingIds.length}
              onClick={() =>
                void processLeads(
                  sortedLeads.map((lead) => lead.id),
                  {
                    includeOutreach: false,
                    successMessage: `Analyzed ${sortedLeads.length} visible lead${sortedLeads.length === 1 ? "" : "s"}.`,
                    emptyMessage: "No visible leads were analyzed successfully.",
                  }
                )
              }
              type="button"
            >
              Analyze visible
            </button>
            {!!processingIds.length && (
              <button
                className="rounded-md border border-red-500/50 px-3 py-2 text-xs text-red-300 transition hover:bg-red-500/10"
                onClick={() => stopProcessing()}
                type="button"
              >
                Stop all
              </button>
            )}
          </div>
        </div>

        <div className="min-h-0 flex-1 overflow-auto">
          <table className="w-full">
            <thead className="sticky top-0 bg-zinc-100 dark:bg-zinc-900">
              <tr>
                <th
                  className="cursor-pointer p-3 text-left font-medium text-sm"
                  onClick={() => handleSort("company_name")}
                >
                  Company{" "}
                  {sortBy === "company_name" &&
                    (sortOrder === "asc" ? "^" : "v")}
                </th>
                <th
                  className="cursor-pointer p-3 text-left font-medium text-sm"
                  onClick={() => handleSort("niche")}
                >
                  Verified fit{" "}
                  {sortBy === "niche" && (sortOrder === "asc" ? "^" : "v")}
                </th>
                <th className="p-3 text-left font-medium text-sm">Source</th>
                <th
                  className="cursor-pointer p-3 text-left font-medium text-sm"
                  onClick={() => handleSort("geo")}
                >
                  Geo {sortBy === "geo" && (sortOrder === "asc" ? "^" : "v")}
                </th>
                <th
                  className="cursor-pointer p-3 text-left font-medium text-sm"
                  onClick={() => handleSort("score")}
                >
                  Match / score{" "}
                  {sortBy === "score" && (sortOrder === "asc" ? "^" : "v")}
                </th>
                <th
                  className="cursor-pointer p-3 text-left font-medium text-sm"
                  onClick={() => handleSort("status")}
                >
                  Status{" "}
                  {sortBy === "status" && (sortOrder === "asc" ? "^" : "v")}
                </th>
                <th className="p-3 text-left font-medium text-sm">Contacts</th>
              </tr>
            </thead>
            <tbody>
              {sortedLeads.map((lead, index) => (
                <LeadRow
                  key={getStableLeadKey(lead, index)}
                  lead={lead}
                  onClick={() => {
                    setSelectedLead(lead);
                    setSelectedLeadLive(null);
                    setSelectedLeadLiveDetails(null);
                    setMetadata((prev: LeadListMetadata) => ({
                      ...prev,
                      selectedLeadId: lead.id,
                      liveSelectedLead: null,
                      liveSelectedLeadDetails: null,
                    }));
                    persistLeadListContent({
                      nextSelectedLeadId: lead.id,
                    });
                  }}
                />
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {inspectorLead && (
        <aside className="w-[320px] shrink-0 border-zinc-200 border-l bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-800">
          <div className="flex items-center justify-between border-zinc-200 border-b px-4 py-3 dark:border-zinc-700">
            <div className="font-medium text-sm text-zinc-500 uppercase tracking-[0.18em]">
              Lead inspector
            </div>
            <button
              className="text-blue-500 text-sm hover:underline"
              onClick={() => {
                setSelectedLead(null);
                setSelectedLeadLive(null);
                setSelectedLeadLiveDetails(null);
                setMetadata((prev: LeadListMetadata) => ({
                  ...prev,
                  selectedLeadId: null,
                  liveSelectedLead: null,
                  liveSelectedLeadDetails: null,
                }));
                persistLeadListContent({
                  nextSelectedLeadId: null,
                });
              }}
              type="button"
            >
              Close
            </button>
          </div>
          <div className="space-y-4 p-4">
            <div>
              <div className="font-bold text-lg">
                {inspectorLead.company_name}
              </div>
              <div className="break-all text-sm text-zinc-500">
                {inspectorLead.domain}
              </div>
              {selectedLeadEffectiveState === "analyzed" && (
                <div className="mt-2 inline-flex rounded-full bg-emerald-100 px-2.5 py-1 text-[11px] text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300">
                  Saved analysis
                </div>
              )}
              {selectedLeadEffectiveState !== "analyzed" && (selectedLeadLive || metadata?.liveSelectedLead) && (
                <div className="mt-2 inline-flex rounded-full bg-emerald-100 px-2.5 py-1 text-[11px] text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300">
                  Live backend state
                </div>
              )}
              {selectedLeadEffectiveState !== "analyzed" &&
                !selectedLeadLive &&
                !metadata?.liveSelectedLead &&
                inspectorLead.score_kind !== "final_score" && (
                <div className="mt-2 inline-flex rounded-full bg-amber-100 px-2.5 py-1 text-[11px] text-amber-800 dark:bg-amber-950 dark:text-amber-300">
                  Snapshot preview
                </div>
              )}
              {selectedLeadEffectiveState !== "analyzed" &&
                (selectedLeadLive || metadata?.liveSelectedLead) &&
                selectedLead &&
                (() => {
                  const latestLead = selectedLeadLive || metadata?.liveSelectedLead;
                  return latestLead
                    ? selectedLead.score !== latestLead.score ||
                        selectedLead.score_kind !== latestLead.score_kind ||
                        selectedLead.analysis_state !== latestLead.analysis_state
                    : false;
                })() && (
                  <div className="mt-2 text-xs text-zinc-500">
                    Inspector is showing fresher backend truth. Use <span className="font-medium">Refresh truth</span> to sync the row.
                  </div>
                )}
              {getLeadSummary(inspectorLead) && (
                <div className="mt-2 text-sm text-zinc-500">
                  {getLeadSummary(inspectorLead)}
                </div>
              )}
              <div className="mt-2 text-sm text-zinc-500">
                {scoreNarrative.whyThisLead ||
                  scoreNarrative.nextBestAction ||
                  "Ranked contacts, score context, and proof stay visible below."}
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-700">
                <div className="text-xs text-zinc-500 uppercase tracking-[0.16em]">
                  Verified fit
                </div>
                <div className="mt-1">{getLeadFit(inspectorLead)}</div>
              </div>
              <div className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-700">
                <div className="text-xs text-zinc-500 uppercase tracking-[0.16em]">
                  Source
                </div>
                <div className="mt-1">{getLeadSource(inspectorLead)}</div>
              </div>
              <div className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-700">
                <div className="text-xs text-zinc-500 uppercase tracking-[0.16em]">
                  Geo
                </div>
                <div className="mt-1">{inspectorLead.geo}</div>
              </div>
              <div className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-700">
                <div className="text-xs text-zinc-500 uppercase tracking-[0.16em]">
                  {getScoreLabel(inspectorLead)}
                </div>
                <div className="mt-1">{inspectorLead.score ?? "-"}</div>
              </div>
              <div className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-700">
                <div className="text-xs text-zinc-500 uppercase tracking-[0.16em]">
                  Analysis
                </div>
                <div className="mt-1">{getAnalysisLabel(inspectorLead)}</div>
              </div>
              <div className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-700">
                <div className="text-xs text-zinc-500 uppercase tracking-[0.16em]">
                  Contacts
                </div>
                <div className="mt-1">{inspectorLead.contacts?.length || 0}</div>
              </div>
            </div>
            {signalFacts && (
              <div className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-700">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="text-xs text-zinc-500 uppercase tracking-[0.16em]">
                      Decision
                    </div>
                    <div className="mt-1 text-lg font-semibold">
                      {getDecisionLabel(scoreSnapshot.finalScore)}
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-xs text-zinc-500 uppercase tracking-[0.16em]">
                      Final score
                    </div>
                    <div className="mt-1 text-2xl font-bold">
                      {scoreSnapshot.finalScore ?? inspectorLead.score ?? "-"}
                    </div>
                  </div>
                </div>
                <div className="mt-3 grid grid-cols-2 gap-2 text-sm">
                  <div className="rounded-md bg-zinc-100 p-2 dark:bg-zinc-900">
                    <div className="text-[10px] uppercase tracking-[0.16em] text-zinc-500">Demand</div>
                    <div className="mt-1">{scoreSnapshot.demand ?? "-"}</div>
                  </div>
                  <div className="rounded-md bg-zinc-100 p-2 dark:bg-zinc-900">
                    <div className="text-[10px] uppercase tracking-[0.16em] text-zinc-500">Trust</div>
                    <div className="mt-1">{scoreSnapshot.trust ?? "-"}</div>
                  </div>
                  <div className="rounded-md bg-zinc-100 p-2 dark:bg-zinc-900">
                    <div className="text-[10px] uppercase tracking-[0.16em] text-zinc-500">Leak</div>
                    <div className="mt-1">{scoreSnapshot.leak ?? "-"}</div>
                  </div>
                  <div className="rounded-md bg-zinc-100 p-2 dark:bg-zinc-900">
                    <div className="text-[10px] uppercase tracking-[0.16em] text-zinc-500">Offer fit</div>
                    <div className="mt-1">{scoreSnapshot.offerFit ?? "-"}</div>
                  </div>
                </div>
                <div className="mt-3 rounded-md bg-zinc-100 p-2 text-sm dark:bg-zinc-900">
                  <div className="text-[10px] uppercase tracking-[0.16em] text-zinc-500">Score context</div>
                  <div className="mt-2 space-y-1">
                    <div>
                      <span className="font-medium">Why pursue:</span>{" "}
                      {scoreNarrative.whyThisLead || "No intent narrative captured yet."}
                    </div>
                    <div>
                      <span className="font-medium">Trust:</span> {scoreNarrative.trustSummary}
                    </div>
                    <div>
                      <span className="font-medium">Leak:</span> {scoreNarrative.leakSummary}
                    </div>
                    <div>
                      <span className="font-medium">Offer fit:</span> {scoreNarrative.offerFitSummary}
                    </div>
                    {scoreNarrative.nextBestAction && (
                      <div>
                        <span className="font-medium">Next action:</span> {scoreNarrative.nextBestAction}
                      </div>
                    )}
                  </div>
                </div>
                <div className="mt-3 space-y-2 text-sm">
                  <div className="rounded-md bg-zinc-100 p-2 dark:bg-zinc-900">
                    <span className="font-medium">Top issue:</span> {getTopIssue(signalFacts)}
                  </div>
                  <div className="rounded-md bg-zinc-100 p-2 dark:bg-zinc-900">
                    <span className="font-medium">Next best action:</span> {getNextBestAction(signalFacts)}
                  </div>
                </div>
                {contactIntel.hasAny && (
                  <div className="mt-3 space-y-2 text-sm">
                    <div className="rounded-md bg-zinc-100 p-2 dark:bg-zinc-900">
                      <span className="font-medium">Decision maker:</span>{" "}
                      {contactIntel.decisionMakerName || "Likely doctor/owner contact not confirmed yet"}
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                      <div className="rounded-md bg-zinc-100 p-2 dark:bg-zinc-900">
                        <div className="text-[10px] uppercase tracking-[0.16em] text-zinc-500">Role</div>
                        <div className="mt-1">{contactIntel.decisionMakerRole || "primary contact"}</div>
                      </div>
                      <div className="rounded-md bg-zinc-100 p-2 dark:bg-zinc-900">
                        <div className="text-[10px] uppercase tracking-[0.16em] text-zinc-500">Best channel</div>
                        <div className="mt-1">{formatBestContactChannel(contactIntel.bestContactChannel)}</div>
                      </div>
                      <div className="rounded-md bg-zinc-100 p-2 dark:bg-zinc-900">
                        <div className="text-[10px] uppercase tracking-[0.16em] text-zinc-500">Best phone</div>
                        <div className="mt-1 break-all">{contactIntel.bestContactPhone || "-"}</div>
                      </div>
                      <div className="rounded-md bg-zinc-100 p-2 dark:bg-zinc-900">
                        <div className="text-[10px] uppercase tracking-[0.16em] text-zinc-500">Best email</div>
                        <div className="mt-1 break-all">{contactIntel.bestContactEmail || "-"}</div>
                      </div>
                    </div>
                    {(contactIntel.decisionMakerSource || contactIntel.decisionMakerConfidence != null) && (
                      <div className="rounded-md bg-zinc-100 p-2 dark:bg-zinc-900">
                        <div className="text-[10px] uppercase tracking-[0.16em] text-zinc-500">Contact confidence</div>
                        <div className="mt-1 text-xs text-zinc-600 dark:text-zinc-400">
                          {[
                            contactIntel.decisionMakerSource ? `Source: ${contactIntel.decisionMakerSource}` : null,
                            contactIntel.decisionMakerConfidence != null
                              ? `Confidence: ${
                                  contactIntel.decisionMakerConfidence <= 1
                                    ? `${Math.round(contactIntel.decisionMakerConfidence * 100)}%`
                                    : `${Math.round(contactIntel.decisionMakerConfidence)}/100`
                                }`
                              : null,
                          ]
                            .filter(Boolean)
                            .join(" | ")}
                        </div>
                      </div>
                    )}
                    {contactIntel.decisionMakerLinkedin && (
                      <div className="rounded-md bg-zinc-100 p-2 dark:bg-zinc-900">
                        <div className="text-[10px] uppercase tracking-[0.16em] text-zinc-500">LinkedIn</div>
                        <a
                          className="mt-1 block break-all text-blue-500 hover:underline"
                          href={contactIntel.decisionMakerLinkedin}
                          rel="noreferrer"
                          target="_blank"
                        >
                          {contactIntel.decisionMakerLinkedin}
                        </a>
                      </div>
                    )}
                    {!!contactIntel.decisionMakerCandidates.length && (
                      <div className="rounded-md bg-zinc-100 p-2 dark:bg-zinc-900">
                        <div className="text-[10px] uppercase tracking-[0.16em] text-zinc-500">Likely contacts</div>
                        <div className="mt-2 space-y-1 text-xs">
                          {contactIntel.decisionMakerCandidates.slice(0, 6).map((candidate, index) => (
                            <div key={`candidate-${index}`} className="rounded border border-zinc-200 px-2 py-1 dark:border-zinc-800">
                              <div className="font-medium">{String(candidate.name || "Unknown contact")}</div>
                              <div className="text-zinc-500 dark:text-zinc-400">
                                {[candidate.role, candidate.clinic, candidate.source].filter(Boolean).join(" | ") || "decision-maker candidate"}
                              </div>
                              {!!candidate.phones?.length && (
                                <div className="mt-1 text-zinc-600 dark:text-zinc-300">
                                  {candidate.phones.slice(0, 2).join(" | ")}
                                </div>
                              )}
                              {!!candidate.emails?.length && (
                                <div className="mt-1 break-all text-zinc-600 dark:text-zinc-300">
                                  {candidate.emails.slice(0, 2).join(" | ")}
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                    {!!contactIntel.branchContacts.length && (
                      <div className="rounded-md bg-zinc-100 p-2 dark:bg-zinc-900">
                        <div className="text-[10px] uppercase tracking-[0.16em] text-zinc-500">Branch phones</div>
                        <div className="mt-2 space-y-1 text-xs">
                          {contactIntel.branchContacts.slice(0, 6).map((contact, index) => (
                            <div key={`branch-contact-${index}`} className="rounded border border-zinc-200 px-2 py-1 dark:border-zinc-800">
                              <div className="font-medium">{String(contact.name || "Clinic branch")}</div>
                              <div className="text-zinc-500 dark:text-zinc-400">{String(contact.phone || "-")}</div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                    {(contactIntel.bestContactReason || contactIntel.recommendedOffer || contactIntel.decisionMakerSource) && (
                      <div className="rounded-md bg-zinc-100 p-2 text-zinc-600 dark:bg-zinc-900 dark:text-zinc-400">
                        {contactIntel.bestContactReason || contactIntel.recommendedOffer || contactIntel.decisionMakerSource}
                      </div>
                    )}
                    {!!contactIntel.contactEvidence.length && (
                      <div className="rounded-md bg-zinc-100 p-2 text-zinc-600 dark:bg-zinc-900 dark:text-zinc-400">
                        {contactIntel.contactEvidence.join(" | ")}
                      </div>
                    )}
                  </div>
                )}
                <div className="mt-3 grid grid-cols-2 gap-2 text-sm">
                  <div className="rounded-md bg-zinc-100 p-2 dark:bg-zinc-900">
                    <div className="text-[10px] uppercase tracking-[0.16em] text-zinc-500">Phone</div>
                    <div className="mt-1">{signalFacts.phone_visible ? "Yes" : "No"}</div>
                  </div>
                  <div className="rounded-md bg-zinc-100 p-2 dark:bg-zinc-900">
                    <div className="text-[10px] uppercase tracking-[0.16em] text-zinc-500">Booking</div>
                    <div className="mt-1">{signalFacts.booking_detected ? "Yes" : "No"}</div>
                  </div>
                  <div className="rounded-md bg-zinc-100 p-2 dark:bg-zinc-900">
                    <div className="text-[10px] uppercase tracking-[0.16em] text-zinc-500">WhatsApp</div>
                    <div className="mt-1">{signalFacts.whatsapp_detected ? "Yes" : "No"}</div>
                  </div>
                  <div className="rounded-md bg-zinc-100 p-2 dark:bg-zinc-900">
                    <div className="text-[10px] uppercase tracking-[0.16em] text-zinc-500">Reviews</div>
                    <div className="mt-1">{signalFacts.reviews_count ?? "-"}</div>
                  </div>
                  <div className="rounded-md bg-zinc-100 p-2 dark:bg-zinc-900">
                    <div className="text-[10px] uppercase tracking-[0.16em] text-zinc-500">Doctors</div>
                    <div className="mt-1">{signalFacts.doctor_count ?? 0}</div>
                    {!!contactIntel.doctorNames.length && (
                      <div className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
                        {contactIntel.doctorNames.slice(0, 4).join(", ")}
                      </div>
                    )}
                  </div>
                  <div className="rounded-md bg-zinc-100 p-2 dark:bg-zinc-900">
                    <div className="text-[10px] uppercase tracking-[0.16em] text-zinc-500">Locations</div>
                    <div className="mt-1">{formatLocationFact(signalFacts)}</div>
                  </div>
                </div>
              </div>
            )}
            <div className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-700">
              <div className="text-xs text-zinc-500 uppercase tracking-[0.16em]">
                Status
              </div>
              <div className="mt-2 inline-flex rounded-full bg-zinc-200 px-2.5 py-1 text-xs dark:bg-zinc-700">
                {formatLeadStatus(inspectorLead.status)}
              </div>
              <div className="mt-2 text-sm text-zinc-500">
                {getStatusHelp(inspectorLead.status)}
              </div>
            </div>
            {!!inspectorLead.contacts?.length && (
              <div className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-700">
                <div className="text-xs text-zinc-500 uppercase tracking-[0.16em]">
                  Actual contacts
                </div>
                <div className="mt-2 space-y-2 text-sm">
                  {inspectorLead.contacts.map((contact, index) => (
                    <div
                      key={getStableContactKey(inspectorLead.id, contact, index)}
                      className="rounded-md bg-zinc-100 p-2 dark:bg-zinc-900"
                    >
                      <div className="font-medium">{contact.name}</div>
                      {contact.title && <div className="text-zinc-500">{contact.title}</div>}
                      {contact.phone && <div>{contact.phone}</div>}
                      {contact.email && <div>{contact.email}</div>}
                    </div>
                  ))}
                </div>
              </div>
            )}
            {!!inspectorLead.contact_paths?.length && (
              <div className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-700">
                <div className="text-xs text-zinc-500 uppercase tracking-[0.16em]">
                  Contact paths
                </div>
                <div className="mt-2 text-sm">
                  {inspectorLead.contact_paths.map(formatContactPath).join(", ")}
                </div>
                <div className="mt-2 text-sm text-zinc-500">
                  These are only the paths actually detected on this site, not a generic list.
                </div>
              </div>
            )}
            {selectedLeadDetails?.intent && (
              <details className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-700">
                <summary className="cursor-pointer text-xs text-zinc-500 uppercase tracking-[0.16em]">
                  Intent summary
                </summary>
                {Boolean(selectedLeadDetails.intent.site_truth_summary) && (
                  <div className="mb-2 mt-3 rounded-md bg-zinc-100 p-2 text-sm dark:bg-zinc-900">
                    {String(selectedLeadDetails.intent.site_truth_summary)}
                  </div>
                )}
                <div className="mt-2 text-sm">
                  {(selectedLeadDetails.intent.why_this_lead as string) || "No intent summary captured."}
                </div>
              </details>
            )}
            {selectedLeadDetails?.proof && (
              <details className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-700">
                <summary className="cursor-pointer text-xs text-zinc-500 uppercase tracking-[0.16em]">
                  Proof details
                </summary>
                <div className="mt-3 grid grid-cols-2 gap-2 text-sm">
                  <div className="rounded-md bg-zinc-100 p-2 dark:bg-zinc-900">
                    <div className="text-[10px] uppercase tracking-[0.16em] text-zinc-500">Booking target</div>
                    <div className="mt-1 break-all">{proofFacts.bookingTarget || "not detected"}</div>
                  </div>
                  <div className="rounded-md bg-zinc-100 p-2 dark:bg-zinc-900">
                    <div className="text-[10px] uppercase tracking-[0.16em] text-zinc-500">WhatsApp target</div>
                    <div className="mt-1 break-all">{proofFacts.whatsappTarget || "not extracted"}</div>
                  </div>
                </div>
                {!!proofInsights.length && (
                  <div className="mt-3 space-y-2 text-sm">
                    {proofInsights.map((insight, index) => (
                      <div key={`${selectedLead?.id ?? "selected"}-proof-${index}`} className="rounded-md bg-zinc-100 p-2 dark:bg-zinc-900">
                        {insight}
                      </div>
                    ))}
                  </div>
                )}
                <div className="mt-3 grid grid-cols-2 gap-2">
                  {selectedLeadDetails.proof.hero_screenshot_url && (
                    <a
                      className="overflow-hidden rounded-md border border-zinc-200 dark:border-zinc-700"
                      href={selectedLeadDetails.proof.hero_screenshot_url}
                      rel="noreferrer"
                      target="_blank"
                    >
                      <img
                        alt="Hero proof"
                        className="h-24 w-full object-cover"
                        src={selectedLeadDetails.proof.hero_screenshot_url}
                      />
                    </a>
                  )}
                  {selectedLeadDetails.proof.cta_screenshot_url && (
                    <a
                      className="overflow-hidden rounded-md border border-zinc-200 dark:border-zinc-700"
                      href={selectedLeadDetails.proof.cta_screenshot_url}
                      rel="noreferrer"
                      target="_blank"
                    >
                      <img
                        alt="CTA proof"
                        className="h-24 w-full object-cover"
                        src={selectedLeadDetails.proof.cta_screenshot_url}
                      />
                    </a>
                  )}
                </div>
              </details>
            )}
            {!!outreachSummary.drafts.length && (
              <details className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-700">
                <summary className="cursor-pointer text-xs text-zinc-500 uppercase tracking-[0.16em]">
                  Outreach drafts
                </summary>
                <div className="mt-2 text-xs text-zinc-500">
                  Showing the latest unique drafts only.
                </div>
                <div className="mt-3 space-y-2 text-sm">
                  {outreachSummary.drafts.map((message, index) => (
                    <div key={`${selectedLead?.id ?? "selected"}-outreach-${index}`} className="rounded-md bg-zinc-100 p-2 dark:bg-zinc-900">
                      <div className="font-medium">
                        {message.subject || `${message.channel || "message"} draft`}
                      </div>
                      {message.body && (
                        <div className="mt-1 line-clamp-4 text-zinc-600 dark:text-zinc-300">
                          {message.body}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
                {!!outreachSummary.hiddenCount && (
                  <div className="mt-2 text-xs text-zinc-500">
                    {outreachSummary.hiddenCount} older duplicate draft
                    {outreachSummary.hiddenCount === 1 ? "" : "s"} hidden.
                  </div>
                )}
              </details>
            )}
            <div className="flex flex-wrap gap-2">
              {isSelectedLeadProcessing ? (
                <button
                  className="rounded-md bg-red-600 px-3 py-2 text-sm text-white transition hover:bg-red-500"
                  onClick={() => {
                    if (!selectedLead?.id) {
                      return;
                    }
                    stopProcessing([selectedLead.id]);
                  }}
                  type="button"
                >
                  Stop analyze
                </button>
              ) : (
                <button
                  className="rounded-md bg-emerald-600 px-3 py-2 text-sm text-white transition hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-50"
                  disabled={isSelectedLeadProcessing}
                  onClick={() => void analyzeSelectedLead()}
                  type="button"
                >
                  Analyze lead
                </button>
              )}
              <button
                className="rounded-md border border-zinc-300 px-3 py-2 text-sm transition hover:bg-zinc-100 dark:border-zinc-600 dark:hover:bg-zinc-900"
                disabled={!inspectorLead}
                onClick={() => {
                  navigator.clipboard.writeText(
                    formatLeadForClipboard(inspectorLead, selectedLeadDetails || null)
                  );
                  toast.success("Live lead summary copied.");
                }}
                type="button"
              >
                Copy summary
              </button>
              <button
                className="rounded-md border border-zinc-300 px-3 py-2 text-sm transition hover:bg-zinc-100 disabled:cursor-not-allowed disabled:opacity-50 dark:border-zinc-600 dark:hover:bg-zinc-900"
                disabled={isRefreshingTruth || isSelectedLeadProcessing}
                onClick={() => void refreshSelectedLeadTruth()}
                type="button"
              >
                {isRefreshingTruth ? "Refreshing..." : "Refresh truth"}
              </button>
              {!!processingIds.length && !isSelectedLeadProcessing && (
                <button
                  className="rounded-md border border-red-500/50 px-3 py-2 text-sm text-red-300 transition hover:bg-red-500/10"
                  onClick={() => stopProcessing()}
                  type="button"
                >
                  Stop all
                </button>
              )}
            </div>
            {isSelectedLeadProcessing && (
              <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-3 text-sm text-emerald-200">
                Running fast lead analysis for this lead: enrichment, intent fit, scoring, and backend truth sync. Click{" "}
                Stop analyze to cancel it.
              </div>
            )}
          </div>
        </aside>
      )}
    </div>
  );
}

export const leadListArtifact = new Artifact<"lead-list", LeadListMetadata>({
  kind: "lead-list",
  description:
    "Display a list of leads with filtering and sorting capabilities",
  initialize: ({ setMetadata }) => {
    setMetadata((prev: Partial<LeadListMetadata> | null) => ({
      leads: prev?.leads ?? [],
      loading: prev?.loading ?? false,
      sortBy: prev?.sortBy ?? "score",
      sortOrder: prev?.sortOrder ?? "desc",
      filter: prev?.filter ?? "",
      selectedLeadId: prev?.selectedLeadId ?? null,
      processedDetails: prev?.processedDetails ?? {},
    }));
  },
  onStreamPart: ({ streamPart, setArtifact, setMetadata }) => {
    if ((streamPart as any).type === "data-leadList") {
      const data = (streamPart as any).data as Lead[] | LeadListPayload;
      const payload = Array.isArray(data) ? ({ leads: data } satisfies LeadListPayload) : data;
      const leads = sanitizeLeadRows(payload.leads || []);
      const processedDetails = payload.processedDetails || payload.processed_details || {};
      setMetadata((prev: LeadListMetadata) => ({
        ...prev,
        filter: payload.filter || prev.filter || "",
        leads,
        loading: false,
        processedDetails:
          Object.keys(processedDetails).length > 0
            ? processedDetails
            : (prev.processedDetails || {}),
        selectedLeadId: payload.selectedLeadId || prev.selectedLeadId || null,
        sortBy: payload.sortBy || prev.sortBy || "score",
        sortOrder: payload.sortOrder || prev.sortOrder || "desc",
      }));
      setArtifact((draft) => ({
        ...draft,
        content: serializeLeadListPayload(leads, {
          filter: payload.filter || "",
          processedDetails,
          selectedLeadId: payload.selectedLeadId || null,
          sortBy: payload.sortBy || "score",
          sortOrder: payload.sortOrder || "desc",
        }),
        status: "idle",
      }));
    }
  },
  content: (props) => (
    <LeadListContent
      content={props.content}
      metadata={props.metadata}
      setMetadata={props.setMetadata}
    />
  ),
  actions: [
    {
      icon: <UndoIcon size={18} />,
      description: "View Previous version",
      onClick: ({ handleVersionChange }) => handleVersionChange("prev"),
      isDisabled: ({ currentVersionIndex }) => currentVersionIndex === 0,
    },
    {
      icon: <RedoIcon size={18} />,
      description: "View Next version",
      onClick: ({ handleVersionChange }) => handleVersionChange("next"),
      isDisabled: ({ isCurrentVersion }) => isCurrentVersion,
    },
    {
      icon: <CopyIcon size={18} />,
      description: "Copy lead summary",
      onClick: ({ content, metadata }) => {
        try {
          if (metadata?.liveSelectedLead) {
            navigator.clipboard.writeText(
              formatLeadForClipboard(
                metadata.liveSelectedLead,
                metadata.liveSelectedLeadDetails || null
              )
            );
            toast.success("Live lead summary copied!");
            return;
          }
          const parsed = JSON.parse(content);
          const leads = Array.isArray(parsed) ? parsed : parsed.leads || [];
          const readable = formatLeadListForClipboard(
            leads,
            metadata?.processedDetails ||
              parsed.processedDetails ||
              parsed.processed_details ||
              {},
            metadata?.selectedLeadId || null
          );
          navigator.clipboard.writeText(readable);
          toast.success(
            metadata?.selectedLeadId ? "Lead inspector copied!" : "Lead list copied!"
          );
        } catch {
          navigator.clipboard.writeText(content);
          toast.success("Copied!");
        }
      },
    },
    {
      icon: <span className="font-semibold text-[10px]">AI</span>,
      label: "Analyze visible",
      description: "Run analysis truth, scoring, and proof for all visible leads",
      onClick: async ({ content, metadata, setMetadata }) => {
        try {
          const parsed = JSON.parse(content);
          const contentLeads = (Array.isArray(parsed) ? parsed : parsed.leads || []) as Lead[];
          const leads = metadata?.leads?.length ? metadata.leads : contentLeads;
          const filteredLeads = filterLeads(leads, metadata?.filter || "");
          const sortedLeads = sortLeads(
            filteredLeads,
            metadata?.sortBy || "score",
            metadata?.sortOrder || "desc"
          );
          const visibleLeads = sortedLeads;
          if (visibleLeads.length === 0) {
            toast.error("No leads available to process.");
            return;
          }
          const persistedTopLeads = await Promise.all(
            visibleLeads.map((lead) =>
              isUuidLeadId(lead.id) ? Promise.resolve(lead) : ensurePersistedLead(lead)
            )
          );
          const replacedLeadRows = visibleLeads.reduce((nextLeads, lead, index) => {
            const importedLead = persistedTopLeads[index];
            return importedLead.id === lead.id
              ? nextLeads
              : replaceLeadRow(nextLeads, lead.id, importedLead);
          }, leads);
          const replacedProcessedDetails = visibleLeads.reduce(
            (nextDetails, lead, index) =>
              persistedTopLeads[index].id === lead.id
                ? nextDetails
                : replaceProcessedLeadDetails(nextDetails, lead.id, persistedTopLeads[index].id),
            metadata?.processedDetails || {}
          );
          if (replacedLeadRows !== leads || replacedProcessedDetails !== (metadata?.processedDetails || {})) {
            setMetadata((prev: LeadListMetadata) => ({
              ...prev,
              leads: replacedLeadRows,
              processedDetails: replacedProcessedDetails,
            }));
          }
          const response = await fetch(ZRAI_ENDPOINTS.processLeads, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify({
              lead_ids: persistedTopLeads.map((lead) => lead.id),
              include_outreach: false,
            }),
          });
          if (!response.ok) {
            throw new Error(await response.text());
          }
          const payload = getPayloadData((await response.json()) as {
            processed?: ProcessedLeadResponseItem[];
          });
          const processedLeads = (payload.processed || [])
            .filter((item: ProcessedLeadResponseItem) => item.success && item.lead)
            .map((item: ProcessedLeadResponseItem) => item.lead as Lead);
          const processedDetailEntries = (payload.processed || [])
            .filter((item: ProcessedLeadResponseItem) => item.success && item.lead)
            .map((item: ProcessedLeadResponseItem) => [
              item.lead!.id,
              {
                enrichment: item.enrichment || {},
                intent: item.intent || {},
                proof: item.proof || {},
                outreach: item.outreach || [],
                scoring: item.scoring || {},
                signal_facts: item.signal_facts,
                analysis_bundle: item.analysis_bundle,
                analysis_state: item.analysis_state,
                analysis_updated_at: item.analysis_updated_at,
                signals_version: item.signals_version,
              } satisfies ProcessedLeadDetails,
            ] as const);
          if (processedLeads.length === 0) {
            toast.error("No leads were processed successfully.");
            return;
          }
          setMetadata((prev: LeadListMetadata) => {
            const nextLeads = mergeLeadRows(prev.leads, processedLeads);
            const nextProcessedDetails = {
              ...(prev.processedDetails || {}),
              ...Object.fromEntries(processedDetailEntries),
            };
            return {
              ...prev,
              leads: nextLeads,
              processedDetails: nextProcessedDetails,
            };
          });
          toast.success(
            `Analyzed ${processedLeads.length} visible lead${processedLeads.length === 1 ? "" : "s"}.`
          );
        } catch (error) {
          toast.error(error instanceof Error ? error.message : "Processing failed");
        }
      },
    },
  ],
  toolbar: [
    {
      icon: <span className="font-semibold text-[10px]">EN</span>,
      description: "Enrich all leads",
      onClick: async ({ content, metadata, setArtifact, setMetadata }) => {
        try {
          const parsed = JSON.parse(content || "{}");
          const contentLeads = (Array.isArray(parsed) ? parsed : parsed.leads || []) as Lead[];
          const visibleLeads = sortLeads(
            filterLeads(metadata?.leads?.length ? metadata.leads : contentLeads, metadata?.filter || ""),
            metadata?.sortBy || "score",
            metadata?.sortOrder || "desc"
          );

          if (!visibleLeads.length) {
            toast.error("No visible leads to enrich.");
            return;
          }

          const enrichedLeads: Lead[] = [];
          for (const rawLead of visibleLeads) {
            const lead = isUuidLeadId(rawLead.id) ? rawLead : await ensurePersistedLead(rawLead);
            const response = await fetch(ZRAI_ENDPOINTS.enrich, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ lead_id: lead.id }),
            });

            if (!response.ok) {
              continue;
            }

            const payload = await response.json();
            const payloadData = getPayloadData(payload);
            if ((payload?.success ?? true) && payloadData?.lead) {
              enrichedLeads.push(payloadData.lead as Lead);
            }
          }

          if (!enrichedLeads.length) {
            toast.error("No leads were enriched successfully.");
            return;
          }

          setMetadata((prev: LeadListMetadata) => {
            const nextLeads = mergeLeadRows(prev.leads, enrichedLeads);
            setArtifact((draft) => ({
              ...draft,
              content: serializeLeadListPayload(nextLeads, {
                filter: prev.filter,
                processedDetails: prev.processedDetails,
                sortBy: prev.sortBy,
                sortOrder: prev.sortOrder,
              }),
            }));
            return {
              ...prev,
              leads: nextLeads,
            };
          });

          toast.success(`Enriched ${enrichedLeads.length} lead${enrichedLeads.length === 1 ? "" : "s"}.`);
        } catch (error) {
          toast.error(error instanceof Error ? error.message : "Enrichment failed");
        }
      },
    },
    {
      icon: <span className="font-semibold text-[10px]">SC</span>,
      description: "Score all leads",
      onClick: async ({ content, metadata, setArtifact, setMetadata }) => {
        try {
          const parsed = JSON.parse(content || "{}");
          const contentLeads = (Array.isArray(parsed) ? parsed : parsed.leads || []) as Lead[];
          const visibleLeads = sortLeads(
            filterLeads(metadata?.leads?.length ? metadata.leads : contentLeads, metadata?.filter || ""),
            metadata?.sortBy || "score",
            metadata?.sortOrder || "desc"
          );

          if (!visibleLeads.length) {
            toast.error("No visible leads to score.");
            return;
          }

          const response = await fetch(ZRAI_ENDPOINTS.score, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              lead_ids: await Promise.all(
                visibleLeads.map(async (lead) =>
                  isUuidLeadId(lead.id) ? lead.id : (await ensurePersistedLead(lead)).id
                )
              ),
            }),
          });

          if (!response.ok) {
            throw new Error(await response.text());
          }

          const payload = await response.json();
          const scoredResults = getScoreResults(payload);
          const scoredLeads = scoredResults
            .map((result: { lead?: Lead; score_breakdown?: { total_score?: number }; breakdown?: { total_score?: number } }) =>
              result.lead
                ? {
                    ...result.lead,
                    score:
                      result.score_breakdown?.total_score ??
                      result.breakdown?.total_score ??
                      result.lead.score,
                    score_kind: "final_score" as const,
                    analysis_state: "analyzed" as const,
                  }
                : null
            )
            .filter(Boolean) as Lead[];

          if (!scoredLeads.length) {
            toast.error("Scoring did not return any leads.");
            return;
          }

          setMetadata((prev: LeadListMetadata) => {
            const nextLeads = mergeLeadRows(prev.leads, scoredLeads);
            setArtifact((draft) => ({
              ...draft,
              content: serializeLeadListPayload(nextLeads, {
                filter: prev.filter,
                processedDetails: prev.processedDetails,
                sortBy: prev.sortBy,
                sortOrder: prev.sortOrder,
              }),
            }));
            return {
              ...prev,
              leads: nextLeads,
            };
          });

          toast.success(`Scored ${scoredLeads.length} lead${scoredLeads.length === 1 ? "" : "s"}.`);
        } catch (error) {
          toast.error(error instanceof Error ? error.message : "Scoring failed");
        }
      },
    },
  ],
});


