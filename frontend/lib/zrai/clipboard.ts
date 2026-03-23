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

type RankedContactEntry = {
  rank: number;
  name: string;
  role?: string | null;
  clinic?: string | null;
  phone?: string | null;
  email?: string | null;
  linkedin?: string | null;
  source?: string | null;
  score?: number | null;
  reason?: string | null;
  channel?: string | null;
  kind?: "primary" | "alternate" | "actual" | "branch";
  isPrimary?: boolean;
};

type RankedContactModel = {
  topContact: RankedContactEntry | null;
  alternateContacts: RankedContactEntry[];
  contactEvidence: string[];
  bestContactReason: string | null;
  recommendedOffer: string | null;
  decisionMakerName: string | null;
  decisionMakerRole: string | null;
  decisionMakerSource: string | null;
  decisionMakerConfidence: number | null;
  decisionMakerLinkedin: string | null;
  bestContactPhone: string | null;
  bestContactEmail: string | null;
  bestContactChannel: string | null;
};

type LeadScoreNarrative = {
  whyThisLead: string | null;
  trustSummary: string | null;
  leakSummary: string | null;
  offerFitSummary: string | null;
  nextBestAction: string | null;
  recommendedOffer: string | null;
  recommendedChannel: string | null;
  topIssue: string | null;
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

function getContactFingerprint(contact: Partial<RankedContactEntry>) {
  return [
    contact.name,
    contact.role,
    contact.clinic,
    contact.phone,
    contact.email,
    contact.linkedin,
  ]
    .map((value) => String(value || "").trim().toLowerCase())
    .join("|");
}

function addRankedContact(
  entries: RankedContactEntry[],
  seen: Set<string>,
  contact: Omit<RankedContactEntry, "rank">,
  kind: RankedContactEntry["kind"],
  rankHint: number
) {
  const fingerprint = getContactFingerprint(contact);
  if (!fingerprint.replace(/\|/g, "").trim() || seen.has(fingerprint)) {
    return;
  }

  seen.add(fingerprint);
  entries.push({
    rank: rankHint,
    kind,
    ...contact,
  });
}

function formatRankedContact(contact: RankedContactEntry) {
  return [
    `${contact.rank}. ${contact.name}`,
    contact.role ? `role: ${contact.role}` : null,
    contact.clinic ? `clinic: ${contact.clinic}` : null,
    contact.phone ? `phone: ${contact.phone}` : null,
    contact.email ? `email: ${contact.email}` : null,
    contact.linkedin ? `linkedin: ${contact.linkedin}` : null,
    contact.channel ? `channel: ${contact.channel}` : null,
    contact.source ? `source: ${contact.source}` : null,
    contact.score != null ? `score: ${contact.score}` : null,
    contact.reason ? `reason: ${contact.reason}` : null,
  ]
    .filter(Boolean)
    .join(" | ");
}

export function buildLeadScoreNarrative(
  lead: Lead | null | undefined,
  processedDetails?: LeadProcessedDetails | null
): LeadScoreNarrative {
  const signalFacts = getSignalFacts(lead, processedDetails);
  const guidance = getGuidance(lead, processedDetails);
  const agentContext = getAgentContext(lead, processedDetails);
  const trustMarkers = agentContext.trust_markers || [];
  const whyThisLead =
    typeof processedDetails?.intent?.why_this_lead === "string"
      ? processedDetails.intent.why_this_lead
      : guidance.why_this_lead || null;
  const recommendedOffer = agentContext.recommended_offer || null;
  const recommendedChannel =
    signalFacts?.recommended_channel ||
    guidance.recommended_channel ||
    agentContext.recommended_channel ||
    null;
  const nextBestAction =
    signalFacts?.next_best_action ||
    guidance.next_best_action ||
    agentContext.recommended_next_step ||
    null;
  const topIssue = signalFacts?.top_issue || guidance.top_issue || null;
  const trustSignals = trustMarkers.length
    ? `Trust signals: ${trustMarkers.slice(0, 4).join(", ")}`
    : joinNonEmpty([
        signalFacts?.reviews_count != null ? `${signalFacts.reviews_count} reviews` : null,
        signalFacts?.rating != null ? `${signalFacts.rating} rating` : null,
        signalFacts?.branch_count ? `${signalFacts.branch_count} locations` : null,
        signalFacts?.doctor_count ? `${signalFacts.doctor_count} doctors` : null,
        signalFacts?.content_ready_score != null
          ? `content readiness ${signalFacts.content_ready_score}/100`
          : null,
      ]);
  const trustSummary =
    trustSignals ||
    "Trust score is a weighted 25% component of the final score and reflects reviews, rating, doctors, locations, social proof, and content readiness.";
  const leakDrivers = [
    signalFacts && !signalFacts.phone_visible ? "phone not prominent" : null,
    signalFacts && !signalFacts.whatsapp_detected ? "missing WhatsApp capture" : null,
    signalFacts
      ? signalFacts.booking_detected
        ? signalFacts.booking_flow_quality === "weak"
          ? "weak booking flow"
          : null
        : "missing booking path"
      : null,
    signalFacts && signalFacts.contact_form_detected === false ? "no contact form" : null,
    signalFacts && !signalFacts.after_hours_capture ? "after-hours gap" : null,
    signalFacts && !signalFacts.instant_response_path ? "no instant-response path" : null,
  ].filter(Boolean);
  const leakSummary =
    leakDrivers.length > 0
      ? `Leak drivers: ${leakDrivers.join(", ")}`
      : "Leak score reflects capture-path gaps such as phone, booking, WhatsApp, forms, after-hours, and instant-response coverage.";
  const offerFitDrivers = [
    signalFacts?.multi_clinic ? "multi-clinic setup" : null,
    signalFacts?.services?.length ? `${signalFacts.services.length} services` : null,
    signalFacts?.content_ready_score != null
      ? `content readiness ${signalFacts.content_ready_score}/100`
      : null,
    signalFacts?.booking_flow_quality && signalFacts.booking_flow_quality !== "strong"
      ? `booking flow ${signalFacts.booking_flow_quality}`
      : null,
    signalFacts?.whatsapp_detected ? null : "no WhatsApp capture",
    Object.keys(signalFacts?.social_profiles || {}).length
      ? "social footprint present"
      : null,
  ].filter(Boolean);
  const offerFitSummary =
    recommendedOffer || offerFitDrivers.length
      ? joinNonEmpty([
          recommendedOffer ? `Offer fit: ${recommendedOffer}` : null,
          offerFitDrivers.length ? `Signals: ${offerFitDrivers.join(", ")}` : null,
        ])
      : "Offer fit reflects multi-location, services, content readiness, booking friction, WhatsApp presence, and social footprint.";

  return {
    whyThisLead,
    trustSummary,
    leakSummary,
    offerFitSummary,
    nextBestAction,
    recommendedOffer,
    recommendedChannel,
    topIssue,
  };
}

export function buildRankedContactModel(
  lead: Lead | null | undefined,
  processedDetails?: LeadProcessedDetails | null
): RankedContactModel {
  const signalFacts = getSignalFacts(lead, processedDetails);
  const agentContext = getAgentContext(lead, processedDetails);
  const decisionMakerName = sanitizeDecisionMakerName(
    signalFacts?.decision_maker_name || agentContext.decision_maker_name || null
  );
  const decisionMakerLinkedin =
    signalFacts?.decision_maker_linkedin ||
    signalFacts?.best_contact_linkedin ||
    agentContext.decision_maker_linkedin ||
    agentContext.best_contact_linkedin ||
    null;
  const decisionMakerRole = decisionMakerName
    ? signalFacts?.decision_maker_role || agentContext.decision_maker_role || null
    : null;
  const decisionMakerSource = decisionMakerName
    ? signalFacts?.decision_maker_source || agentContext.decision_maker_source || null
    : null;
  const decisionMakerConfidence = decisionMakerName
    ? signalFacts?.decision_maker_confidence ?? agentContext.decision_maker_confidence ?? null
    : null;
  const bestContactPhone = signalFacts?.best_contact_phone || agentContext.best_contact_phone || null;
  const bestContactEmail = signalFacts?.best_contact_email || agentContext.best_contact_email || null;
  const bestContactChannel =
    signalFacts?.best_contact_channel || agentContext.best_contact_channel || null;
  const bestContactReason =
    signalFacts?.best_contact_reason || agentContext.best_contact_reason || null;
  const recommendedOffer = agentContext.recommended_offer || null;
  const contactEvidence = signalFacts?.contact_evidence || agentContext.contact_evidence || [];
  const rawCandidates =
    signalFacts?.decision_maker_candidates || agentContext.decision_maker_candidates || [];
  const candidates = [...rawCandidates].sort((a, b) => (b.score || 0) - (a.score || 0));
  const branchContacts = signalFacts?.branch_contacts || agentContext.branch_contacts || [];

  const topContact: Omit<RankedContactEntry, "rank"> | null =
    decisionMakerName || decisionMakerLinkedin || bestContactPhone || bestContactEmail
      ? {
          name: decisionMakerName || "Best contact",
          role: decisionMakerRole || bestContactChannel || null,
          clinic: null,
          phone: bestContactPhone || null,
          email: bestContactEmail || null,
          linkedin: decisionMakerLinkedin || null,
          source: decisionMakerSource || bestContactReason || "best contact",
          score: decisionMakerConfidence,
          reason: bestContactReason || null,
          channel: bestContactChannel || null,
          isPrimary: true,
        }
      : null;

  const rankedContacts: RankedContactEntry[] = [];
  const seen = new Set<string>();
  let rank = 1;

  if (topContact) {
    addRankedContact(rankedContacts, seen, topContact, "primary", rank);
    rank += 1;
  } else if (lead?.contacts?.length) {
    const primaryContact =
      lead.contacts.find((contact) => contact.is_primary) || lead.contacts[0];
    if (primaryContact) {
      addRankedContact(
        rankedContacts,
        seen,
        {
          name: primaryContact.name || "Primary contact",
          role: primaryContact.title || null,
          clinic: null,
          phone: primaryContact.phone || null,
          email: primaryContact.email || null,
          linkedin: primaryContact.linkedin_url || null,
          source: "actual lead contact",
          score: null,
          reason: null,
          channel: null,
          isPrimary: true,
        },
        "actual",
        rank
      );
      rank += 1;
    }
  }

  for (const contact of lead?.contacts || []) {
    addRankedContact(
      rankedContacts,
      seen,
      {
        name: contact.name || "Contact",
        role: contact.title || null,
        clinic: null,
        phone: contact.phone || null,
        email: contact.email || null,
        linkedin: contact.linkedin_url || null,
        source: contact.is_primary ? "actual lead contact" : "actual lead contact",
        score: null,
        reason: null,
        channel: null,
        isPrimary: contact.is_primary,
      },
      "actual",
      rank
    );
    rank += 1;
  }

  for (const candidate of candidates) {
    addRankedContact(
      rankedContacts,
      seen,
      {
        name: candidate.name || "Unknown contact",
        role: candidate.role || null,
        clinic: candidate.clinic || null,
        phone: candidate.phones?.[0] || null,
        email: candidate.emails?.[0] || null,
        linkedin: candidate.linkedin || null,
        source: candidate.source || "decision-maker candidate",
        score: candidate.score ?? null,
        reason: null,
        channel: null,
        isPrimary: false,
      },
      "alternate",
      rank
    );
    rank += 1;
  }

  for (const contact of branchContacts) {
    addRankedContact(
      rankedContacts,
      seen,
      {
        name: contact.name || "Clinic branch",
        role: "branch contact",
        clinic: null,
        phone: contact.phone || null,
        email: null,
        linkedin: null,
        source: contact.source || "branch phone",
        score: null,
        reason: null,
        channel: null,
        isPrimary: false,
      },
      "branch",
      rank
    );
    rank += 1;
  }

  const topContactEntry = rankedContacts[0] || null;
  const alternateContacts = rankedContacts.slice(1);

  return {
    topContact: topContactEntry,
    alternateContacts,
    contactEvidence: contactEvidence.map((item) => String(item).trim()).filter(Boolean),
    bestContactReason,
    recommendedOffer,
    decisionMakerName,
    decisionMakerRole,
    decisionMakerSource,
    decisionMakerConfidence,
    decisionMakerLinkedin,
    bestContactPhone,
    bestContactEmail,
    bestContactChannel,
  };
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
  const scoreNarrative = buildLeadScoreNarrative(lead, processedDetails);
  const contactModel = buildRankedContactModel(lead, processedDetails);
  const proofInsights = getProofInsights(lead, processedDetails);
  const outreachSummary = getOutreachSummary(processedDetails);
  const finalScore = getFinalScore(lead, processedDetails);
  const topIssue = scoreNarrative.topIssue || signalFacts?.top_issue || guidance.top_issue || null;
  const nextBestAction = scoreNarrative.nextBestAction || null;

  const summaryLines = [
    lead.company_name || "Unknown lead",
    lead.domain ? `Website: ${lead.domain}` : null,
    lead.geo ? `Location: ${lead.geo}` : null,
    lead.verified_fit ? `Fit: ${lead.verified_fit}` : null,
    `Stage: ${formatValue(lead.analysis_state || lead.status || "preview")}`,
    `Score: ${formatValue(finalScore)}`,
    topIssue ? `Top issue: ${topIssue}` : null,
    nextBestAction ? `Next best action: ${nextBestAction}` : null,
    scoreNarrative.recommendedOffer ? `Recommended offer: ${scoreNarrative.recommendedOffer}` : null,
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
    scoreNarrative.recommendedOffer ? `Recommended offer: ${scoreNarrative.recommendedOffer}` : null,
    scoreNarrative.recommendedChannel ? `Preferred channel: ${scoreNarrative.recommendedChannel}` : null,
  ].filter(Boolean);

  const sections = [summaryLines.join("\n")];

  if (
    scoreNarrative.whyThisLead ||
    scoreNarrative.trustSummary ||
    scoreNarrative.leakSummary ||
    scoreNarrative.offerFitSummary ||
    scoreNarrative.nextBestAction
  ) {
    const scoreContextLines = [
      scoreNarrative.whyThisLead ? `Why this lead: ${scoreNarrative.whyThisLead}` : null,
      scoreNarrative.trustSummary ? `Trust: ${scoreNarrative.trustSummary}` : null,
      scoreNarrative.leakSummary ? `Leak: ${scoreNarrative.leakSummary}` : null,
      scoreNarrative.offerFitSummary ? `Offer fit: ${scoreNarrative.offerFitSummary}` : null,
      scoreNarrative.nextBestAction ? `Next best action: ${scoreNarrative.nextBestAction}` : null,
    ].filter(Boolean);

    if (scoreContextLines.length) {
      sections.push(`Score context\n${scoreContextLines.join("\n")}`);
    }
  }

  if (contactModel.topContact) {
    sections.push(`Top contact\n${formatRankedContact(contactModel.topContact)}`);
  }

  if (contactModel.alternateContacts.length) {
    sections.push(
      `Alternate contacts\n${contactModel.alternateContacts
        .map((contact) => formatRankedContact(contact))
        .join("\n")}`
    );
  }

  if (contactModel.contactEvidence.length) {
    sections.push(`Contact evidence\n${contactModel.contactEvidence.slice(0, 6).join(" | ")}`);
  }

  if (contactModel.bestContactReason) {
    sections.push(`Contact strategy\n${contactModel.bestContactReason}`);
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
      const scoreNarrative = buildLeadScoreNarrative(
        lead,
        lead.id ? processedDetails?.[lead.id] : null
      );
      const contactModel = buildRankedContactModel(
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
        contactModel.topContact ? `   Top contact: ${contactModel.topContact.name}${contactModel.topContact.role ? ` (${contactModel.topContact.role})` : ""}` : null,
        scoreNarrative.whyThisLead ? `   Why pursue: ${scoreNarrative.whyThisLead}` : null,
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
