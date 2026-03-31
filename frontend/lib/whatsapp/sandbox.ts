import type {
  WhatsAppAgentState,
  WhatsAppLinkedLeadContext,
  WhatsAppOpsState,
} from "@/lib/whatsapp/state";

function normalizePhoneDigits(value: string) {
  return value.replace(/[^\d]/g, "");
}

export function buildWhatsAppSandboxLeadContext({
  contactPhone,
  companyName,
  geo,
  topIssue,
  decisionMakerName,
  decisionMakerRole,
}: {
  contactPhone: string;
  companyName: string;
  geo?: string | null;
  topIssue?: string | null;
  decisionMakerName?: string | null;
  decisionMakerRole?: string | null;
}): WhatsAppLinkedLeadContext {
  const normalizedPhone = normalizePhoneDigits(contactPhone);
  const cleanCompanyName = companyName.trim() || "Sandbox Clinic";
  const cleanGeo = String(geo ?? "").trim() || "Bangalore";
  const cleanTopIssue =
    String(topIssue ?? "").trim() ||
    "WhatsApp enquiries dropping before booking confirmation";
  const cleanDecisionMakerName = String(decisionMakerName ?? "").trim() || null;
  const cleanDecisionMakerRole =
    String(decisionMakerRole ?? "").trim() || "Clinic owner";

  return {
    leadId: `sandbox:${normalizedPhone || "lead"}`,
    companyName: cleanCompanyName,
    geo: cleanGeo,
    status: "sandbox",
    analysisState: "sandbox_seeded",
    finalScore: 88,
    previewMatchScore: 84,
    topIssue: cleanTopIssue,
    nextBestAction:
      "Diagnose the booking gap clearly, show the WhatsApp concierge flow, and move to a demo.",
    recommendedChannel: "whatsapp",
    demandScore: 78,
    trustScore: 71,
    leakScore: 86,
    offerFitScore: 90,
    contactQualityScore: 83,
    decisionMakerName: cleanDecisionMakerName,
    decisionMakerRole: cleanDecisionMakerRole,
    bestContactPhone: contactPhone.trim(),
    bestContactChannel: "whatsapp",
    bestContactReason:
      "Sandbox lead seeded for manual WhatsApp sales-agent testing.",
    likelyContacts: [
      {
        name: cleanDecisionMakerName || cleanCompanyName,
        role: cleanDecisionMakerRole,
        phone: contactPhone.trim(),
        source: "sandbox_seed",
        confidence: 1,
        channel: "whatsapp",
        contactType: "decision-maker",
        ownerScope: "demo",
        isDirect: true,
        isPublic: false,
      },
    ],
    linkedAt: new Date().toISOString(),
    source: "sandbox_demo",
    confidence: 1,
  };
}

export function buildWhatsAppSandboxAgentState({
  companyName,
  topIssue,
  decisionMakerRole,
}: {
  companyName: string;
  topIssue?: string | null;
  decisionMakerRole?: string | null;
}): Partial<WhatsAppAgentState> {
  const cleanCompanyName = companyName.trim() || "the clinic";
  const cleanTopIssue =
    String(topIssue ?? "").trim() ||
    "WhatsApp enquiries dropping before booking confirmation";

  return {
    stage: "ENGAGED",
    priority: "high",
    confidence: 0.82,
    summary: `Sandbox lead seeded for ${cleanCompanyName}. Keep the conversation human, diagnose the booking gap, and guide toward a demo.`,
    leadChannels: ["whatsapp", "sandbox_demo"],
    painPoints: ["booking_gap", "slow_response", "missed_follow_up"],
    requestedNextStep: "diagnose",
    lastIntent: "sandbox_test",
    nextBestMove:
      "Ask one clean diagnostic question about current enquiry handling, then move to proof and demo.",
    handoffRecommended: false,
    decisionMakerRole: String(decisionMakerRole ?? "").trim() || "clinic owner",
    decisionMakerConfirmed: Boolean(decisionMakerRole),
    painConfirmed: false,
    paymentInterest: false,
    optOut: false,
    updatedAt: new Date().toISOString(),
  };
}

export function buildWhatsAppSandboxOpsState({
  geo,
  owner,
}: {
  geo?: string | null;
  owner?: string | null;
}): Partial<WhatsAppOpsState> {
  return {
    commercialStatus: "qualified",
    senderStatus: "docs_requested",
    owner: String(owner ?? "").trim() || null,
    nextActionAt: new Date(Date.now() + 15 * 60_000).toISOString(),
    niche: "Derm & Aesthetic",
    city: String(geo ?? "").trim() || "Bangalore",
    contactChannel: "whatsapp",
    senderOnboardingPossible: true,
    onboardingChecklist: {
      hoursCollected: false,
      servicesCollected: false,
      faqCollected: false,
      escalationOwnerCollected: false,
      routingChecklistAssigned: false,
    },
  };
}

export function isWhatsAppSandboxLead(input: {
  linkedLeadId?: string | null;
  leadContext?: WhatsAppLinkedLeadContext | null;
}) {
  return (
    String(input.linkedLeadId ?? "").startsWith("sandbox:") ||
    input.leadContext?.source === "sandbox_demo"
  );
}
