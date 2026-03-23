"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import { Artifact } from "@/components/create-artifact";
import { CopyIcon, RedoIcon, UndoIcon } from "@/components/icons";
import {
  buildLeadScoreNarrative,
  buildRankedContactModel,
  formatLeadForClipboard,
} from "@/lib/zrai/clipboard";
import {
  fetchFounderIntelligence,
  mergeFounderIntelligenceIntoProcessedDetails,
  needsFounderIntelligence,
  type FounderIntelPayload,
} from "@/lib/zrai/founder-intelligence";
import { getZRAILeadByIdEndpoint, ZRAI_ENDPOINTS } from "@/lib/zrai/constants";
import type { AnalysisBundle, Lead, SignalFacts } from "@/lib/zrai/types";

type ProcessedLeadDetails = {
  enrichment?: Record<string, unknown>;
  intent?: Record<string, unknown>;
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
  scoring?: Record<string, unknown>;
  signal_facts?: SignalFacts;
  analysis_bundle?: AnalysisBundle;
  analysis_state?: string;
  analysis_updated_at?: string;
  signals_version?: string;
};

type OutreachDraft = NonNullable<ProcessedLeadDetails["outreach"]>[number];

type LeadCardPayload = {
  lead: Lead | null;
  processed_details?: ProcessedLeadDetails;
};

type LeadCardMetadata = {
  lead: Lead | null;
  loading: boolean;
  processedDetails?: ProcessedLeadDetails | null;
  liveLead?: Lead | null;
  liveProcessedDetails?: ProcessedLeadDetails | null;
};

function getPayloadData<T = any>(payload: any): T {
  return (payload?.data ?? payload) as T;
}

function parseLeadCardPayload(content: string): LeadCardPayload | null {
  if (!content) {
    return null;
  }

  try {
    const parsed = JSON.parse(content);
    if (parsed && typeof parsed === "object" && "lead" in parsed) {
      return parsed as LeadCardPayload;
    }

    return { lead: parsed as Lead };
  } catch {
    return null;
  }
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
  } else {
    insights.push("Booking path detected.");
  }

  if (signalFacts.next_best_action) {
    insights.push(signalFacts.next_best_action);
  }

  return insights.slice(0, 4);
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
  processedDetails: ProcessedLeadDetails | null | undefined
) {
  return processedDetails?.analysis_bundle || lead?.analysis_bundle || null;
}

function getScoreSnapshot(
  lead: Lead | null | undefined,
  processedDetails: ProcessedLeadDetails | null | undefined
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

function normalizeLeadCardContent(
  lead: Lead,
  processedDetails?: ProcessedLeadDetails | null
) {
  return JSON.stringify({
    lead,
    processed_details: processedDetails || null,
  });
}

function LeadStatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    discovered: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400",
    enriched: "bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-400",
    scored: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400",
    outreach_pending: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400",
    qualified: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-400",
  };

  return (
    <span className={`rounded-full px-2 py-1 text-xs font-medium ${colors[status] || colors.discovered}`}>
      {status.replace(/_/g, " ")}
    </span>
  );
}

function LeadCardContent({
  content,
  metadata,
  setMetadata,
}: {
  content: string;
  metadata: LeadCardMetadata;
  setMetadata: (fn: (prev: LeadCardMetadata) => LeadCardMetadata) => void;
}) {
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isRefreshingTruth, setIsRefreshingTruth] = useState(false);
  const [liveLead, setLiveLead] = useState<Lead | null>(null);
  const [liveProcessedDetails, setLiveProcessedDetails] = useState<ProcessedLeadDetails | null>(null);
  const founderIntelCacheRef = useRef<Record<string, FounderIntelPayload>>({});
  const payload = parseLeadCardPayload(content);
  const lead = metadata?.lead || payload?.lead || null;
  const processedDetails = metadata?.processedDetails || payload?.processed_details || null;
  const displayLead = liveLead || metadata?.liveLead || lead;
  const displayProcessedDetails =
    liveProcessedDetails || metadata?.liveProcessedDetails || processedDetails;

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

  useEffect(() => {
    setLiveLead(null);
    setLiveProcessedDetails(null);
    setMetadata((prev: LeadCardMetadata) => ({
      ...prev,
      liveLead: null,
      liveProcessedDetails: null,
    }));
    if (!lead?.id) {
      return;
    }

    let cancelled = false;

    const refreshLead = async () => {
      try {
        const response = await fetch(getZRAILeadByIdEndpoint(lead.id));
        if (!response.ok) {
          return;
        }

        const latest = await response.json();
        const latestData = getPayloadData(latest);
        if (!(latest?.success ?? true) || cancelled) {
          return;
        }

        const nextLiveLead = (latestData?.lead || latestData) as Lead;
        const nextLiveProcessedDetailsRaw =
          latestData?.processed_details
            ? ({
                ...(latestData.processed_details || {}),
                signal_facts: latestData.signal_facts || latestData.processed_details?.signal_facts || null,
                analysis_bundle: latestData.analysis_bundle || latestData.processed_details?.analysis_bundle || null,
                analysis_state: latestData.analysis_state || latestData.processed_details?.analysis_state || null,
                analysis_updated_at:
                  latestData.analysis_updated_at || latestData.processed_details?.analysis_updated_at || null,
                signals_version: latestData.signals_version || latestData.processed_details?.signals_version || null,
              } as ProcessedLeadDetails)
            : null;
        const hydrated = await hydrateFounderIntel(nextLiveLead, nextLiveProcessedDetailsRaw);
        if (cancelled) {
          return;
        }
        setLiveLead(hydrated.lead);
        setLiveProcessedDetails(hydrated.processedDetails);
        setMetadata((prev: LeadCardMetadata) => ({
          ...prev,
          liveLead: hydrated.lead,
          liveProcessedDetails: hydrated.processedDetails,
        }));
      } catch {
        // Embedded artifact payload remains available if refresh fails.
      }
    };

    void refreshLead();

    return () => {
      cancelled = true;
    };
  }, [lead?.id, setMetadata]);

  const proofExtraction = displayProcessedDetails?.proof?.extraction_data as Record<string, unknown> | undefined;
  const outreachSummary = useMemo(
    () => getVisibleOutreachDrafts(displayProcessedDetails?.outreach),
    [displayProcessedDetails?.outreach]
  );
  const signalFacts = displayProcessedDetails?.signal_facts || displayLead?.signal_facts || null;
  const proofFacts = useMemo(
    () => getCanonicalProofFacts(signalFacts, proofExtraction),
    [signalFacts, proofExtraction]
  );
  const proofInsights = useMemo(
    () =>
      getCanonicalProofInsights(
        signalFacts,
        proofExtraction,
        displayProcessedDetails?.proof?.audit_bullets
      ),
    [signalFacts, proofExtraction, displayProcessedDetails?.proof?.audit_bullets]
  );
  const scoreSnapshot = useMemo(
    () => getScoreSnapshot(displayLead, displayProcessedDetails),
    [displayLead, displayProcessedDetails]
  );
  const analysisBundle = useMemo(
    () => getAnalysisBundle(displayLead, displayProcessedDetails),
    [displayLead, displayProcessedDetails]
  );
  const contactIntel = useMemo(
    () => getContactIntelligence(displayLead, displayProcessedDetails, signalFacts, analysisBundle),
    [displayLead, displayProcessedDetails, signalFacts, analysisBundle]
  );
  const scoreNarrative = useMemo(
    () => buildLeadScoreNarrative(displayLead, displayProcessedDetails),
    [displayLead, displayProcessedDetails]
  );

  const refreshLeadTruth = async () => {
    if (!lead?.id) {
      return;
    }

    setIsRefreshingTruth(true);
    try {
      const response = await fetch(getZRAILeadByIdEndpoint(lead.id));
      if (!response.ok) {
        throw new Error(await response.text());
      }

        const latest = await response.json();
        const latestData = getPayloadData(latest);
        if (!(latest?.success ?? true) || !latestData?.lead) {
          throw new Error("Lead truth refresh failed.");
        }

        const latestLead = latestData.lead as Lead;
        const latestProcessedDetailsRaw = latestData.processed_details
          ? ({
              ...(latestData.processed_details || {}),
              signal_facts: latestData.signal_facts || latestData.processed_details?.signal_facts || null,
              analysis_bundle: latestData.analysis_bundle || latestData.processed_details?.analysis_bundle || null,
              analysis_state: latestData.analysis_state || latestData.processed_details?.analysis_state || null,
              analysis_updated_at:
                latestData.analysis_updated_at || latestData.processed_details?.analysis_updated_at || null,
              signals_version: latestData.signals_version || latestData.processed_details?.signals_version || null,
            } as ProcessedLeadDetails)
          : null;
      const hydrated = await hydrateFounderIntel(latestLead, latestProcessedDetailsRaw);
      setMetadata((prev: LeadCardMetadata) => ({
        ...prev,
        lead: hydrated.lead,
        processedDetails: hydrated.processedDetails,
        liveLead: hydrated.lead,
        liveProcessedDetails: hydrated.processedDetails,
      }));
      setLiveLead(hydrated.lead);
      setLiveProcessedDetails(hydrated.processedDetails);
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

      const latest = await response.json();
      const latestData = getPayloadData(latest);
      const latestLead = latestData?.lead as Lead | undefined;
      const nextAnalysisState =
        latestData?.analysis_state ||
        latestData?.processed_details?.analysis_state ||
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

      const latestProcessedDetailsRaw = latestData.processed_details
        ? ({
            ...(latestData.processed_details || {}),
            signal_facts: latestData.signal_facts || latestData.processed_details?.signal_facts || null,
            analysis_bundle: latestData.analysis_bundle || latestData.processed_details?.analysis_bundle || null,
            analysis_state: latestData.analysis_state || latestData.processed_details?.analysis_state || null,
            analysis_updated_at:
              latestData.analysis_updated_at || latestData.processed_details?.analysis_updated_at || null,
            signals_version: latestData.signals_version || latestData.processed_details?.signals_version || null,
          } as ProcessedLeadDetails)
        : null;
      const hydrated = await hydrateFounderIntel(latestLead, latestProcessedDetailsRaw);

      setMetadata((prev: LeadCardMetadata) => ({
        ...prev,
        lead: hydrated.lead,
        processedDetails: hydrated.processedDetails,
      }));
      setLiveLead(hydrated.lead);
      setLiveProcessedDetails(hydrated.processedDetails);
      toast.success("Lead analyzed.");
      return;
    }

    toast.success("Analysis is still running. Use Refresh truth in a moment.");
  };

  const analyzeLead = async () => {
    if (!lead?.id) {
      return;
    }

    setIsAnalyzing(true);
    try {
      const response = await fetch(ZRAI_ENDPOINTS.analyzeLead, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          lead_id: lead.id,
          include_outreach: true,
        }),
      });

      if (!response.ok) {
        throw new Error(await response.text());
      }

      const result = await response.json();
      const resultData = getPayloadData(result);
      const queued =
        resultData?.queued ||
        result?.queued ||
        resultData?.analysis_state === "analyzing" ||
        result?.analysis_state === "analyzing";

      if (queued) {
        const queuedLead = {
          ...lead,
          analysis_state: "analyzing",
        } as Lead;
        const queuedProcessedDetails = {
          ...(metadata?.processedDetails || {}),
          analysis_state: "analyzing",
          analysis_updated_at: resultData?.analysis_updated_at || result?.analysis_updated_at || null,
        } as ProcessedLeadDetails;
        setMetadata((prev: LeadCardMetadata) => ({
          ...prev,
          lead: queuedLead,
          processedDetails: queuedProcessedDetails,
          liveLead: queuedLead,
          liveProcessedDetails: queuedProcessedDetails,
        }));
        setLiveLead(queuedLead);
        setLiveProcessedDetails(queuedProcessedDetails);
        toast.success("Analysis started.");
        await pollLeadAnalysisCompletion(queuedLead.id);
        return;
      }

      if (!(result?.success ?? true) || !resultData?.lead) {
        throw new Error("Lead analysis failed.");
      }

      const nextLead = resultData.lead as Lead;
      const nextProcessedDetailsRaw = {
        ...(resultData?.processed_details || {}),
        signal_facts: resultData?.signal_facts || resultData?.processed_details?.signal_facts || null,
        analysis_bundle: resultData?.analysis_bundle || resultData?.processed_details?.analysis_bundle || null,
        analysis_state: resultData?.analysis_state || resultData?.processed_details?.analysis_state || "analyzed",
        analysis_updated_at:
          resultData?.analysis_updated_at || resultData?.processed_details?.analysis_updated_at || null,
        signals_version: resultData?.signals_version || resultData?.processed_details?.signals_version || null,
      } as ProcessedLeadDetails;
      const hydrated = await hydrateFounderIntel(nextLead, nextProcessedDetailsRaw);

      setMetadata((prev: LeadCardMetadata) => ({
        ...prev,
        lead: hydrated.lead,
        processedDetails: hydrated.processedDetails,
        liveLead: hydrated.lead,
        liveProcessedDetails: hydrated.processedDetails,
      }));
      setLiveLead(hydrated.lead);
      setLiveProcessedDetails(hydrated.processedDetails);
      toast.success("Lead analyzed.");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Lead analysis failed");
    } finally {
      setIsAnalyzing(false);
    }
  };

  if (!displayLead) {
    return (
      <div className="flex h-full items-center justify-center p-8">
        <div className="text-center text-zinc-500">
          <div className="text-lg">No lead data available</div>
          <div className="text-sm">Open a lead artifact from chat history or discover leads first.</div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4 p-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold">{displayLead.company_name}</h2>
          <a
            className="text-sm text-blue-500 hover:underline"
            href={`https://${displayLead.domain}`}
            rel="noopener noreferrer"
            target="_blank"
          >
            {displayLead.domain}
          </a>
          {liveLead || metadata?.liveLead ? (
            <div className="mt-2 inline-flex rounded-full bg-emerald-100 px-2.5 py-1 text-[11px] text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300">
              Live backend state
            </div>
          ) : displayLead.score_kind !== "final_score" ? (
            <div className="mt-2 inline-flex rounded-full bg-amber-100 px-2.5 py-1 text-[11px] text-amber-800 dark:bg-amber-950 dark:text-amber-300">
              Snapshot preview
            </div>
          ) : null}
          <div className="mt-2 text-sm text-zinc-500 dark:text-zinc-400">
            {scoreNarrative.whyThisLead ||
              scoreNarrative.nextBestAction ||
              "Ranked contacts, score context, and proof stay visible below."}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <div className="text-2xl font-bold text-emerald-500">{displayLead.score ?? "-"}</div>
          <LeadStatusBadge status={displayLead.status} />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <div className="text-xs text-zinc-500">Verified fit</div>
          <div className="font-medium">{displayLead.verified_fit || displayLead.niche}</div>
        </div>
        <div>
          <div className="text-xs text-zinc-500">Geography</div>
          <div className="font-medium">{displayLead.geo}</div>
        </div>
        <div>
          <div className="text-xs text-zinc-500">Analysis</div>
          <div className="font-medium">
            {displayLead.analysis_state === "analyzed" || displayLead.score_kind === "final_score"
              ? "Analyzed"
              : "Preview"}
          </div>
        </div>
      </div>

      {!!displayLead.contacts?.length && (
        <div>
          <h3 className="mb-2 text-sm font-semibold text-zinc-700 dark:text-zinc-300">Actual contacts</h3>
          <div className="space-y-2">
            {displayLead.contacts.map((contact, idx) => (
              <div className="rounded-lg border border-zinc-200 p-2 dark:border-zinc-700" key={contact.id || idx}>
                <div className="font-medium">{contact.name}</div>
                {contact.title && <div className="text-sm text-zinc-500">{contact.title}</div>}
                {contact.phone && <div className="text-sm">{contact.phone}</div>}
                {contact.email && (
                  <a className="text-sm text-blue-500 hover:underline" href={`mailto:${contact.email}`}>
                    {contact.email}
                  </a>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {!!displayLead.contact_paths?.length && (
        <div className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-700">
          <div className="text-xs text-zinc-500 uppercase tracking-[0.16em]">Contact paths</div>
          <div className="mt-2 text-sm">{displayLead.contact_paths.join(", ")}</div>
        </div>
      )}

      {signalFacts && (
        <div className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-700">
          <div className="flex items-start justify-between gap-3">
            <div>
              <div className="text-xs text-zinc-500 uppercase tracking-[0.16em]">Decision</div>
              <div className="mt-1 text-lg font-semibold">{getDecisionLabel(scoreSnapshot.finalScore)}</div>
            </div>
            <div className="text-right">
              <div className="text-xs text-zinc-500 uppercase tracking-[0.16em]">Final score</div>
              <div className="mt-1 text-2xl font-bold">{scoreSnapshot.finalScore ?? displayLead.score ?? "-"}</div>
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
              <div className="text-[10px] uppercase tracking-[0.16em] text-zinc-500">Locations</div>
              <div className="mt-1">{formatLocationFact(signalFacts)}</div>
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
        </div>
      )}

      {displayProcessedDetails?.intent && (
        <details className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-700">
          <summary className="cursor-pointer text-xs text-zinc-500 uppercase tracking-[0.16em]">Intent summary</summary>
          <div className="mt-3 rounded-md bg-zinc-100 p-2 text-sm dark:bg-zinc-900">
            {String(displayProcessedDetails.intent.site_truth_summary || "No site truth summary captured.")}
          </div>
          <div className="mt-3 text-sm">
            {String(displayProcessedDetails.intent.why_this_lead || "No intent narrative captured.")}
          </div>
        </details>
      )}

      {displayProcessedDetails?.proof && (
        <details className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-700">
          <summary className="cursor-pointer text-xs text-zinc-500 uppercase tracking-[0.16em]">Proof details</summary>
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
                <div className="rounded-md bg-zinc-100 p-2 dark:bg-zinc-900" key={`${lead?.id || "lead"}-proof-${index}`}>
                  {insight}
                </div>
              ))}
            </div>
          )}
          <div className="mt-3 grid grid-cols-2 gap-2">
            {displayProcessedDetails.proof.hero_screenshot_url && (
              <a href={displayProcessedDetails.proof.hero_screenshot_url} rel="noreferrer" target="_blank">
                <img
                  alt="Hero proof"
                  className="h-24 w-full rounded-md border border-zinc-200 object-cover dark:border-zinc-700"
                  src={displayProcessedDetails.proof.hero_screenshot_url}
                />
              </a>
            )}
            {displayProcessedDetails.proof.cta_screenshot_url && (
              <a href={displayProcessedDetails.proof.cta_screenshot_url} rel="noreferrer" target="_blank">
                <img
                  alt="CTA proof"
                  className="h-24 w-full rounded-md border border-zinc-200 object-cover dark:border-zinc-700"
                  src={displayProcessedDetails.proof.cta_screenshot_url}
                />
              </a>
            )}
          </div>
        </details>
      )}

      {!!outreachSummary.drafts.length && (
        <details className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-700">
          <summary className="cursor-pointer text-xs text-zinc-500 uppercase tracking-[0.16em]">Outreach drafts</summary>
          <div className="mt-2 text-xs text-zinc-500">Showing the latest unique drafts only.</div>
          <div className="mt-3 space-y-2">
            {outreachSummary.drafts.map((draft, index) => (
              <div
                className="rounded-md bg-zinc-100 p-2 text-sm dark:bg-zinc-900"
                key={`${lead?.id ?? "lead"}-draft-${index}`}
              >
                <div className="font-medium">{draft.subject || `${draft.channel || "message"} draft`}</div>
                {draft.body && <div className="mt-1 line-clamp-4 text-zinc-600 dark:text-zinc-300">{draft.body}</div>}
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
        <button
          className="rounded-md border border-zinc-300 px-3 py-2 text-sm transition hover:bg-zinc-100 dark:border-zinc-600 dark:hover:bg-zinc-900"
          onClick={() => {
            navigator.clipboard.writeText(
              formatLeadForClipboard(displayLead, displayProcessedDetails)
            );
            toast.success("Live lead summary copied.");
          }}
          type="button"
        >
          Copy summary
        </button>
        <button
          className="rounded-md bg-emerald-600 px-3 py-2 text-sm text-white transition hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-50"
          disabled={isAnalyzing}
          onClick={() => void analyzeLead()}
          type="button"
        >
          {isAnalyzing ? "Analyzing..." : "Analyze lead"}
        </button>
        <button
          className="rounded-md border border-zinc-300 px-3 py-2 text-sm transition hover:bg-zinc-100 disabled:cursor-not-allowed disabled:opacity-50 dark:border-zinc-600 dark:hover:bg-zinc-900"
          disabled={isRefreshingTruth || isAnalyzing}
          onClick={() => void refreshLeadTruth()}
          type="button"
        >
          {isRefreshingTruth ? "Refreshing..." : "Refresh truth"}
        </button>
      </div>
    </div>
  );
}

export const leadCardArtifact = new Artifact<"lead-card", LeadCardMetadata>({
  kind: "lead-card",
  description: "Display deterministic lead details with processed proof, intent, and outreach.",
  initialize: ({ setMetadata }) => {
    setMetadata({
      lead: null,
      loading: false,
      processedDetails: null,
    });
  },
  onStreamPart: ({ setArtifact, setMetadata, streamPart }) => {
    if ((streamPart as any).type === "data-leadCard") {
      const data = (streamPart as any).data as LeadCardPayload | Lead;
      const payload =
        data && typeof data === "object" && "lead" in data ? (data as LeadCardPayload) : { lead: data as Lead };
      if (!payload.lead) {
        return;
      }
      const lead = payload.lead;
      const processedDetails = payload.processed_details || null;
      setMetadata((prev: LeadCardMetadata) => ({
        ...prev,
        lead,
        loading: false,
        processedDetails,
      }));
      setArtifact((draft) => ({
        ...draft,
        content: normalizeLeadCardContent(lead, processedDetails),
        status: "idle",
      }));
    }
  },
  content: (props) => <LeadCardContent content={props.content} metadata={props.metadata} setMetadata={props.setMetadata} />,
  actions: [
    {
      icon: <UndoIcon size={18} />,
      description: "View Previous version",
      isDisabled: ({ currentVersionIndex }) => currentVersionIndex === 0,
      onClick: ({ handleVersionChange }) => handleVersionChange("prev"),
    },
    {
      icon: <RedoIcon size={18} />,
      description: "View Next version",
      isDisabled: ({ isCurrentVersion }) => isCurrentVersion,
      onClick: ({ handleVersionChange }) => handleVersionChange("next"),
    },
    {
      icon: <CopyIcon size={18} />,
      description: "Copy lead summary",
      onClick: ({ content, metadata }) => {
        const payload = parseLeadCardPayload(content);
        const lead = metadata?.liveLead || metadata?.lead || payload?.lead || null;
        const processedDetails =
          metadata?.liveProcessedDetails ||
          metadata?.processedDetails ||
          payload?.processed_details ||
          null;

        navigator.clipboard.writeText(
          formatLeadForClipboard(lead, processedDetails)
        );
        toast.success("Lead summary copied!");
      },
    },
  ],
  toolbar: [
    {
      icon: <span className="text-xs">EN</span>,
      description: "Enrich lead",
      onClick: async ({ content, metadata, setArtifact, setMetadata }) => {
        const payload = parseLeadCardPayload(content);
        const lead = metadata?.lead || payload?.lead;
        if (!lead?.id) {
          toast.error("No lead loaded.");
          return;
        }

        const response = await fetch(ZRAI_ENDPOINTS.enrich, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ lead_id: lead.id }),
        });

        if (!response.ok) {
          toast.error(await response.text());
          return;
        }

        const result = await response.json();
        const resultData = getPayloadData(result);
        if (!(result?.success ?? true) || !resultData?.lead) {
          toast.error("Enrichment failed.");
          return;
        }

        const nextLead = resultData.lead as Lead;
        const nextProcessedDetails = {
          ...(metadata?.processedDetails || payload?.processed_details || {}),
          enrichment: resultData.enrichment || {},
        } as ProcessedLeadDetails;

        setMetadata((prev: LeadCardMetadata) => ({
          ...prev,
          lead: nextLead,
          processedDetails: nextProcessedDetails,
        }));
        setArtifact((draft) => ({
          ...draft,
          content: normalizeLeadCardContent(nextLead, nextProcessedDetails),
        }));
        toast.success("Lead enriched.");
      },
    },
    {
      icon: <span className="text-xs">SC</span>,
      description: "Score lead",
      onClick: async ({ content, metadata, setArtifact, setMetadata }) => {
        const payload = parseLeadCardPayload(content);
        const lead = metadata?.lead || payload?.lead;
        if (!lead?.id) {
          toast.error("No lead loaded.");
          return;
        }

        const response = await fetch(ZRAI_ENDPOINTS.score, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ lead_ids: [lead.id] }),
        });

        if (!response.ok) {
          toast.error(await response.text());
          return;
        }

        const result = await response.json();
        const scoreResults = Array.isArray(result?.results)
          ? result.results
          : Array.isArray(result?.data?.results)
            ? result.data.results
            : [];
        const scoreResult = scoreResults[0] || null;
        const nextLead = (scoreResult?.lead || lead) as Lead;
        const totalScore =
          scoreResult?.score_breakdown?.total_score ??
          scoreResult?.breakdown?.total_score;
        if (totalScore !== undefined) {
          nextLead.score = totalScore;
          nextLead.score_kind = "final_score";
        }

        const nextProcessedDetails = {
          ...(metadata?.processedDetails || payload?.processed_details || {}),
          scoring: scoreResult?.score_breakdown || scoreResult?.breakdown || {},
        } as ProcessedLeadDetails;

        setMetadata((prev: LeadCardMetadata) => ({
          ...prev,
          lead: nextLead,
          processedDetails: nextProcessedDetails,
        }));
        setArtifact((draft) => ({
          ...draft,
          content: normalizeLeadCardContent(nextLead, nextProcessedDetails),
        }));
        toast.success("Lead scored.");
      },
    },
    {
      icon: <span className="text-xs">DR</span>,
      description: "Draft outreach",
      onClick: async ({ content, metadata, setArtifact, setMetadata }) => {
        const payload = parseLeadCardPayload(content);
        const lead = metadata?.lead || payload?.lead;
        if (!lead?.id) {
          toast.error("No lead loaded.");
          return;
        }

        const response = await fetch(ZRAI_ENDPOINTS.outreach, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            lead_id: lead.id,
            channel: "email",
            action: "draft",
          }),
        });

        if (!response.ok) {
          toast.error(await response.text());
          return;
        }

        const result = await response.json();
        const resultData = getPayloadData(result);
        const nextLead = (resultData?.lead || lead) as Lead;
        const nextProcessedDetails = {
          ...(metadata?.processedDetails || payload?.processed_details || {}),
          outreach: resultData?.outreach || (resultData?.message ? [resultData.message] : []),
        } as ProcessedLeadDetails;

        setMetadata((prev: LeadCardMetadata) => ({
          ...prev,
          lead: nextLead,
          processedDetails: nextProcessedDetails,
        }));
        setArtifact((draft) => ({
          ...draft,
          content: normalizeLeadCardContent(nextLead, nextProcessedDetails),
        }));
        toast.success("Draft outreach refreshed.");
      },
    },
    {
      icon: <span className="text-xs">AN</span>,
      description: "Analyze lead",
      onClick: async ({ content, metadata, setArtifact, setMetadata }) => {
        const payload = parseLeadCardPayload(content);
        const lead = metadata?.lead || payload?.lead;
        if (!lead?.id) {
          toast.error("No lead loaded.");
          return;
        }

        const response = await fetch(ZRAI_ENDPOINTS.analyzeLead, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            lead_id: lead.id,
            include_outreach: true,
          }),
        });

        if (!response.ok) {
          toast.error(await response.text());
          return;
        }

        const result = await response.json();
        const resultData = getPayloadData(result);
        const queued =
          resultData?.queued ||
          result?.queued ||
          resultData?.analysis_state === "analyzing" ||
          result?.analysis_state === "analyzing";

        if (queued) {
          const queuedLead = {
            ...lead,
            analysis_state: "analyzing",
          } as Lead;
          const queuedProcessedDetails = {
            ...(metadata?.processedDetails || payload?.processed_details || {}),
            analysis_state: "analyzing",
            analysis_updated_at: resultData?.analysis_updated_at || result?.analysis_updated_at || null,
          } as ProcessedLeadDetails;

          setMetadata((prev: LeadCardMetadata) => ({
            ...prev,
            lead: queuedLead,
            processedDetails: queuedProcessedDetails,
          }));
          setArtifact((draft) => ({
            ...draft,
            content: normalizeLeadCardContent(queuedLead, queuedProcessedDetails),
          }));
          toast.success("Analysis started.");

          for (let attempt = 0; attempt < 45; attempt += 1) {
            await new Promise((resolve) => setTimeout(resolve, 4000));
            const latestResponse = await fetch(getZRAILeadByIdEndpoint(lead.id));
            if (!latestResponse.ok) {
              continue;
            }

            const latest = await latestResponse.json();
            const latestData = getPayloadData(latest);
            const latestLead = latestData?.lead as Lead | undefined;
            const nextAnalysisState =
              latestData?.analysis_state ||
              latestData?.processed_details?.analysis_state ||
              latestLead?.analysis_state;

            if (!latestLead || !nextAnalysisState) {
              continue;
            }

            if (nextAnalysisState === "failed") {
              toast.error("Lead analysis failed in the backend.");
              return;
            }

            if (nextAnalysisState !== "analyzed") {
              continue;
            }

            const latestProcessedDetails = {
              ...(latestData?.processed_details || {}),
              signal_facts: latestData?.signal_facts || latestData?.processed_details?.signal_facts || null,
              analysis_bundle: latestData?.analysis_bundle || latestData?.processed_details?.analysis_bundle || null,
              analysis_state: latestData?.analysis_state || latestData?.processed_details?.analysis_state || "analyzed",
              analysis_updated_at:
                latestData?.analysis_updated_at || latestData?.processed_details?.analysis_updated_at || null,
              signals_version: latestData?.signals_version || latestData?.processed_details?.signals_version || null,
            } as ProcessedLeadDetails;

            setMetadata((prev: LeadCardMetadata) => ({
              ...prev,
              lead: latestLead,
              processedDetails: latestProcessedDetails,
            }));
            setArtifact((draft) => ({
              ...draft,
              content: normalizeLeadCardContent(latestLead, latestProcessedDetails),
            }));
            toast.success("Lead analyzed.");
            return;
          }

          toast.success("Analysis is still running. Use Refresh truth in a moment.");
          return;
        }

        if (!(result?.success ?? true) || !resultData?.lead) {
          toast.error("Lead analysis failed.");
          return;
        }

        const nextLead = resultData.lead as Lead;
        const nextProcessedDetails = {
          ...(resultData?.processed_details || {}),
          signal_facts: resultData?.signal_facts || resultData?.processed_details?.signal_facts || null,
          analysis_bundle: resultData?.analysis_bundle || resultData?.processed_details?.analysis_bundle || null,
          analysis_state: resultData?.analysis_state || resultData?.processed_details?.analysis_state || "analyzed",
          analysis_updated_at:
            resultData?.analysis_updated_at || resultData?.processed_details?.analysis_updated_at || null,
          signals_version: resultData?.signals_version || resultData?.processed_details?.signals_version || null,
        } as ProcessedLeadDetails;

        setMetadata((prev: LeadCardMetadata) => ({
          ...prev,
          lead: nextLead,
          processedDetails: nextProcessedDetails,
        }));
        setArtifact((draft) => ({
          ...draft,
          content: normalizeLeadCardContent(nextLead, nextProcessedDetails),
        }));
        toast.success("Lead analyzed.");
      },
    },
  ],
});

