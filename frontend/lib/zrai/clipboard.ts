import type {
  AnalysisBundle,
  ConversationMessage,
  Lead,
  OutreachMessage,
  ProofArtifact,
  ScoringResult,
  SignalFacts,
} from "@/lib/zrai/types";
import { sanitizeDecisionMakerName } from "@/lib/zrai/people";

type LeadProcessedDetails = {
  intent?: Record<string, unknown>;
  proof?: {
    audit_bullets?: Array<Record<string, string>>;
    extraction_data?: Record<string, unknown>;
  };
  outreach?: Array<{
    subject?: string;
    body?: string;
    channel?: string;
    status?: string;
  }>;
  signal_facts?: SignalFacts | null;
  analysis_bundle?: AnalysisBundle | null;
};

function formatValue(value: unknown) {
  if (value == null || value === "") {
    return "Unknown";
  }

  if (typeof value === "boolean") {
    return value ? "Yes" : "No";
  }

  return String(value);
}

function joinNonEmpty(values: Array<string | null | undefined>) {
  return values.map((value) => value?.trim()).filter(Boolean).join(", ");
}

function getSignalFacts(
  lead: Lead | null | undefined,
  processedDetails?: LeadProcessedDetails | null
) {
  return (
    processedDetails?.signal_facts ||
    lead?.signal_facts ||
    getAnalysisBundle(lead, processedDetails)?.facts ||
    null
  );
}

function getAnalysisBundle(
  lead: Lead | null | undefined,
  processedDetails?: LeadProcessedDetails | null
) {
  return processedDetails?.analysis_bundle || lead?.analysis_bundle || null;
}

function getGuidance(
  lead: Lead | null | undefined,
  processedDetails?: LeadProcessedDetails | null
) {
  return getAnalysisBundle(lead, processedDetails)?.guidance || {};
}

function getAgentContext(
  lead: Lead | null | undefined,
  processedDetails?: LeadProcessedDetails | null
) {
  return getAnalysisBundle(lead, processedDetails)?.agent_context || {};
}

function getFinalScore(
  lead: Lead | null | undefined,
  processedDetails?: LeadProcessedDetails | null
) {
  const scores = getAnalysisBundle(lead, processedDetails)?.scores || {};
  return (
    lead?.final_score ??
    lead?.score ??
    (scores.final_score as number | undefined) ??
    (scores.total_score as number | undefined) ??
    null
  );
}

function getContactLines(
  lead: Lead | null | undefined,
  signalFacts: SignalFacts | null,
  processedDetails?: LeadProcessedDetails | null
) {
  const agentContext = getAgentContext(lead, processedDetails);
  const directPhones = (signalFacts?.phone_numbers || [])
    .map((phone) => `Phone: ${phone}`);
  const contactPhones = (lead?.contacts || [])
    .map((contact) => contact.phone)
    .filter(Boolean)
    .map((phone) => `Phone: ${phone}`);
  const contactEmails = (lead?.contacts || [])
    .map((contact) => contact.email)
    .filter(Boolean)
    .map((email) => `Email: ${email}`);
  const bestPhone = signalFacts?.best_contact_phone || agentContext.best_contact_phone;
  const bestEmail = signalFacts?.best_contact_email || agentContext.best_contact_email;
  const linkedin = signalFacts?.decision_maker_linkedin || agentContext.decision_maker_linkedin;

  return Array.from(
    new Set([
      ...(bestPhone ? [`Best phone: ${bestPhone}`] : []),
      ...(bestEmail ? [`Best email: ${bestEmail}`] : []),
      ...(linkedin ? [`LinkedIn: ${linkedin}`] : []),
      ...directPhones,
      ...contactPhones,
      ...contactEmails,
    ])
  );
}

function getProofInsights(
  lead: Lead | null | undefined,
  processedDetails?: LeadProcessedDetails | null
) {
  const auditBullets =
    processedDetails?.proof?.audit_bullets ||
    getAnalysisBundle(lead, processedDetails)?.evidence?.audit_bullets ||
    [];

  return auditBullets
    .map((bullet) => bullet.evidence || bullet.specific || bullet.estimate || "")
    .map((line) => String(line).trim())
    .filter(Boolean)
    .slice(0, 3);
}

function getOutreachSummary(processedDetails?: LeadProcessedDetails | null) {
  const latestDraft = [...(processedDetails?.outreach || [])]
    .reverse()
    .find((draft) => (draft.body || "").trim().length > 0);

  if (!latestDraft) {
    return null;
  }

  return joinNonEmpty([
    latestDraft.channel ? `Channel: ${latestDraft.channel}` : null,
    latestDraft.subject ? `Subject: ${latestDraft.subject}` : null,
  ]);
}

function formatOutreachMessageForClipboard(message: OutreachMessage | null | undefined) {
  if (!message) {
    return "No outreach draft available.";
  }

  const sections = [
    `${String(message.channel || "message").toUpperCase()} outreach draft`,
    message.subject ? `Subject: ${message.subject}` : null,
    message.body?.trim() ? `Body:\n${message.body.trim()}` : null,
    message.structure?.observation
      ? `Observation:\n${message.structure.observation}`
      : null,
    message.structure?.impact ? `Impact:\n${message.structure.impact}` : null,
    message.structure?.offer ? `Offer:\n${message.structure.offer}` : null,
    message.structure?.cta ? `CTA:\n${message.structure.cta}` : null,
  ].filter(Boolean);

  return sections.join("\n\n");
}

function formatProofArtifactForClipboard(proof: ProofArtifact | null | undefined) {
  if (!proof) {
    return "No proof artifact available.";
  }

  const lines = [
    "Proof artifact",
    proof.proof_type ? `Type: ${proof.proof_type}` : null,
    proof.url ? `URL: ${proof.url}` : null,
    proof.metadata?.extracted_text
      ? `Extracted text:\n${proof.metadata.extracted_text}`
      : null,
    proof.created_at
      ? `Captured: ${new Date(proof.created_at).toLocaleString()}`
      : null,
  ].filter(Boolean);

  return lines.join("\n\n");
}

function scoreValue(result: ScoringResult) {
  return result.score_breakdown?.total_score ?? result.lead?.score ?? 0;
}

function formatScoringDashboardForClipboard(results: ScoringResult[]) {
  if (!results.length) {
    return "No scoring results available.";
  }

  return [...results]
    .sort((a, b) => scoreValue(b) - scoreValue(a))
    .map((result, index) => {
      const lead = result.lead;
      if (!lead) {
        return null;
      }

      return [
        `${index + 1}. ${lead.company_name}`,
        lead.geo ? `   Location: ${lead.geo}` : null,
        `   Score: ${scoreValue(result)}`,
        result.disqualified
          ? `   Disqualified: ${result.disqualification_reason || "No reason provided"}`
          : null,
      ]
        .filter(Boolean)
        .join("\n");
    })
    .filter(Boolean)
    .join("\n\n");
}

function formatConversationForClipboard(messages: ConversationMessage[]) {
  if (!messages.length) {
    return "No conversation available.";
  }

  return messages
    .map((message) => {
      const timestamp = message.timestamp
        ? new Date(message.timestamp).toLocaleString()
        : "Unknown time";

      return `[${message.sender} | ${message.channel} | ${timestamp}]\n${message.content}`;
    })
    .join("\n\n");
}

function formatLeadSheetForClipboard(leads: Lead[]) {
  if (!leads.length) {
    return "No leads available.";
  }

  return leads
    .map((lead, index) =>
      [
        `${index + 1}. ${lead.company_name}`,
        lead.domain ? `   Website: ${lead.domain}` : null,
        lead.geo ? `   Location: ${lead.geo}` : null,
        lead.score != null ? `   Score: ${lead.score}` : null,
        lead.status ? `   Status: ${lead.status}` : null,
      ]
        .filter(Boolean)
        .join("\n")
    )
    .join("\n\n");
}

export function formatLeadForClipboard(
  lead: Lead | null | undefined,
  processedDetails?: LeadProcessedDetails | null
) {
  if (!lead) {
    return "No lead selected.";
  }

  const signalFacts = getSignalFacts(lead, processedDetails);
  const guidance = getGuidance(lead, processedDetails);
  const agentContext = getAgentContext(lead, processedDetails);
  const contactLines = getContactLines(lead, signalFacts, processedDetails);
  const proofInsights = getProofInsights(lead, processedDetails);
  const outreachSummary = getOutreachSummary(processedDetails);
  const finalScore = getFinalScore(lead, processedDetails);
  const decisionMakerName = sanitizeDecisionMakerName(
    signalFacts?.decision_maker_name || agentContext.decision_maker_name || null
  );
  const decisionMakerRole = decisionMakerName
    ? signalFacts?.decision_maker_role || agentContext.decision_maker_role || null
    : null;
  const bestContactChannel =
    signalFacts?.best_contact_channel || agentContext.best_contact_channel || null;
  const bestContactReason =
    signalFacts?.best_contact_reason || agentContext.best_contact_reason || null;
  const recommendedOffer = agentContext.recommended_offer || null;
  const likelyContacts = signalFacts?.decision_maker_candidates || agentContext.decision_maker_candidates || [];
  const branchContacts = signalFacts?.branch_contacts || agentContext.branch_contacts || [];
  const topIssue = signalFacts?.top_issue || guidance.top_issue || null;
  const nextBestAction =
    signalFacts?.next_best_action || guidance.next_best_action || null;

  const summaryLines = [
    lead.company_name || "Unknown lead",
    lead.domain ? `Website: ${lead.domain}` : null,
    lead.geo ? `Location: ${lead.geo}` : null,
    lead.verified_fit ? `Fit: ${lead.verified_fit}` : null,
    `Stage: ${formatValue(lead.analysis_state || lead.status || "preview")}`,
    `Score: ${formatValue(finalScore)}`,
    topIssue ? `Top issue: ${topIssue}` : null,
    nextBestAction ? `Next best action: ${nextBestAction}` : null,
    recommendedOffer ? `Recommended offer: ${recommendedOffer}` : null,
    signalFacts
      ? `Signals: Phone ${formatValue(signalFacts.phone_visible)}, Booking ${formatValue(signalFacts.booking_detected)}, WhatsApp ${formatValue(signalFacts.whatsapp_detected)}, Ads ${formatValue(signalFacts.ads_status || "not_checked")}`
      : null,
    signalFacts?.reviews_count != null
      ? `Reviews: ${signalFacts.reviews_count}${signalFacts.rating ? ` (${signalFacts.rating} rating)` : ""}`
      : null,
    signalFacts?.doctor_names?.length
      ? `Doctors: ${signalFacts.doctor_names.join(", ")}`
      : signalFacts?.doctor_count
        ? `Doctors: ${signalFacts.doctor_count}`
        : null,
    signalFacts?.branch_names?.length
      ? `Locations: ${signalFacts.branch_names.join(", ")}`
      : signalFacts?.branch_count
        ? `Locations: ${signalFacts.branch_count}`
        : null,
    lead.contact_paths?.length
      ? `Contact paths: ${lead.contact_paths.join(", ")}`
      : null,
    decisionMakerName ? `Decision maker: ${decisionMakerName}` : null,
    decisionMakerRole ? `Decision-maker role: ${decisionMakerRole}` : null,
    bestContactChannel ? `Best channel: ${bestContactChannel}` : null,
  ].filter(Boolean);

  const sections = [summaryLines.join("\n")];

  if (contactLines.length) {
    sections.push(`Contacts\n${contactLines.join("\n")}`);
  }

  if (likelyContacts.length) {
    sections.push(
      `Likely contacts\n${likelyContacts
        .slice(0, 4)
        .map((candidate) =>
          joinNonEmpty([
            String(candidate.name || "Unknown contact"),
            candidate.role ? `role: ${candidate.role}` : null,
            candidate.clinic ? `clinic: ${candidate.clinic}` : null,
            candidate.linkedin ? `linkedin: ${candidate.linkedin}` : null,
            candidate.phones?.length ? `phones: ${candidate.phones.join(", ")}` : null,
            candidate.emails?.length ? `emails: ${candidate.emails.join(", ")}` : null,
          ])
        )
        .join("\n")}`
    );
  }

  if (branchContacts.length) {
    sections.push(
      `Branch phones\n${branchContacts
        .slice(0, 4)
        .map((contact) => joinNonEmpty([String(contact.name || "Clinic branch"), contact.phone || null]))
        .join("\n")}`
    );
  }

  if (bestContactReason) {
    sections.push(`Contact strategy\n${bestContactReason}`);
  }

  if (proofInsights.length) {
    sections.push(`Proof\n${proofInsights.map((line) => `- ${line}`).join("\n")}`);
  }

  const siteTruthSummary =
    processedDetails?.intent?.site_truth_summary || guidance.site_truth_summary || null;
  const whyThisLead =
    processedDetails?.intent?.why_this_lead || guidance.why_this_lead || null;

  if (siteTruthSummary || whyThisLead) {
    const intentLines = [
      siteTruthSummary
        ? `Site truth: ${String(siteTruthSummary)}`
        : null,
      whyThisLead
        ? `Why this lead: ${String(whyThisLead)}`
        : null,
    ].filter(Boolean);

    if (intentLines.length) {
      sections.push(`Intent\n${intentLines.join("\n")}`);
    }
  }

  if (outreachSummary) {
    sections.push(`Latest outreach\n${outreachSummary}`);
  }

  return sections.join("\n\n");
}

export function formatLeadListForClipboard(
  leads: Lead[],
  processedDetails?: Record<string, LeadProcessedDetails>,
  selectedLeadId?: string | null
) {
  const selectedLead = selectedLeadId
    ? leads.find((lead) => lead.id === selectedLeadId)
    : null;

  if (selectedLead) {
    return formatLeadForClipboard(
      selectedLead,
      selectedLead.id ? processedDetails?.[selectedLead.id] : null
    );
  }

  if (!leads.length) {
    return "No leads available.";
  }

  return leads
    .map((lead, index) => {
      const signalFacts = getSignalFacts(
        lead,
        lead.id ? processedDetails?.[lead.id] : null
      );
      const score = getFinalScore(
        lead,
        lead.id ? processedDetails?.[lead.id] : null
      );

      return [
        `${index + 1}. ${lead.company_name}`,
        lead.domain ? `   Website: ${lead.domain}` : null,
        lead.geo ? `   Location: ${lead.geo}` : null,
        `   Score: ${formatValue(score)} (${lead.score_kind === "final_score" || lead.analysis_state === "analyzed" ? "Final" : "Preview"})`,
        lead.verified_fit ? `   Fit: ${lead.verified_fit}` : null,
        signalFacts?.top_issue ? `   Top issue: ${signalFacts.top_issue}` : null,
        signalFacts?.next_best_action
          ? `   Next action: ${signalFacts.next_best_action}`
          : null,
      ]
        .filter(Boolean)
        .join("\n");
    })
    .join("\n\n");
}

export function formatArtifactPayloadForClipboard(kind: string, data: unknown) {
  if (!data || typeof data !== "object") {
    return typeof data === "string" ? data : "";
  }

  const payload = data as Record<string, unknown>;

  switch (kind) {
    case "lead-card":
      return formatLeadForClipboard(
        (payload.lead as Lead | null | undefined) || null,
        (payload.processed_details as LeadProcessedDetails | null | undefined) ||
          null
      );
    case "lead-list":
      return formatLeadListForClipboard(
        Array.isArray(payload.leads) ? (payload.leads as Lead[]) : [],
        ((payload.processedDetails ||
          payload.processed_details) as Record<string, LeadProcessedDetails>) ||
          {},
        null
      );
    case "outreach-draft":
      return formatOutreachMessageForClipboard(
        payload as unknown as OutreachMessage
      );
    case "scoring-dashboard":
      return formatScoringDashboardForClipboard(
        Array.isArray(payload.results) ? (payload.results as ScoringResult[]) : []
      );
    case "conversation-thread":
      return formatConversationForClipboard(
        Array.isArray(payload.messages)
          ? (payload.messages as ConversationMessage[])
          : []
      );
    case "proof-viewer":
      return formatProofArtifactForClipboard(
        payload as unknown as ProofArtifact
      );
    case "lead-sheet":
      return formatLeadSheetForClipboard(
        Array.isArray(payload) ? (payload as Lead[]) : []
      );
    default:
      return "";
  }
}
