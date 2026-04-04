import type { WhatsAppConversation, WhatsAppMessage } from "@/lib/db/schema";
import {
  DEFAULT_WHATSAPP_AGENT_STATE,
  type WhatsAppOpsState,
  type WhatsAppAgentState,
  type WhatsAppLinkedLeadContext,
} from "@/lib/whatsapp/state";

const OPT_OUT_PATTERNS = [
  /\bstop\b/i,
  /\bunsubscribe\b/i,
  /\bremove me\b/i,
  /\bdo not contact\b/i,
  /\bdon't contact\b/i,
  /\bnot interested\b/i,
];

const HUMAN_HANDOFF_PATTERNS = [
  /\bhuman\b/i,
  /\bperson\b/i,
  /\bfounder\b/i,
  /\bowner\b/i,
  /\bcall me\b/i,
  /\bspeak to someone\b/i,
  /\blive demo\b/i,
  /\bwalkthrough\b/i,
  /\bdemo\b/i,
  /\bhow does it work\b/i,
  /\brun on our number\b/i,
  /\bour number\b/i,
  /\bproposal\b/i,
  /\bsend details\b/i,
  /\bsend info\b/i,
  /\blegal\b/i,
  /\bcompliance\b/i,
  /\bwebhook\b/i,
  /\btwilio\b/i,
  /\bwhatsapp business\b/i,
];

const OBJECTION_PATTERNS: Record<string, RegExp[]> = {
  price: [/\bprice\b/i, /\bcost\b/i, /\bexpensive\b/i, /\bbudget\b/i],
  timing: [/\bnot now\b/i, /\blater\b/i, /\bnext month\b/i, /\bbusy\b/i],
  integration: [/\bintegrat/i, /\bcrm\b/i, /\bcurrent setup\b/i],
  trust: [/\bproof\b/i, /\bcase stud/i, /\bwho else\b/i],
  spam: [/\bspam\b/i, /\bspammy\b/i, /\btoo many messages\b/i],
  safety: [/\bsafe\b/i, /\bcompliance\b/i, /\bdata\b/i],
  brochure: [/\bsend details\b/i, /\bbrochure\b/i, /\bsend info\b/i],
  human_preference: [
    /\bhuman\b/i,
    /\breceptionist\b/i,
    /\bstaff\b/i,
    /\bpatients prefer humans\b/i,
  ],
  roi: [/\bactual patients\b/i, /\bmore bookings\b/i, /\bwill this work\b/i],
};

function normalizeReplyFingerprint(value: string | null | undefined) {
  return String(value ?? "")
    .replace(/\s+/g, " ")
    .trim()
    .toLowerCase();
}

function pickFreshReply(
  candidates: string[],
  recentReplies: Array<string | null | undefined>
) {
  const seen = new Set(
    recentReplies
      .map((reply) => normalizeReplyFingerprint(reply))
      .filter(Boolean)
  );

  for (const candidate of candidates) {
    const fingerprint = normalizeReplyFingerprint(candidate);
    if (!seen.has(fingerprint)) {
      return candidate;
    }
  }

  return candidates[0] ?? "";
}

const PAIN_PATTERNS: Record<string, RegExp[]> = {
  missed_follow_up: [
    /\bmissed\b/i,
    /\bdrop ?off\b/i,
    /\bno follow[- ]?up\b/i,
    /\bfollow[- ]?up\b/i,
  ],
  slow_response: [
    /\bslow\b/i,
    /\blate\b/i,
    /\bdelay\b/i,
    /\bnot replied\b/i,
    /\bfirst reply\b/i,
    /\breply speed\b/i,
    /\bresponse speed\b/i,
  ],
  whatsapp_gap: [/\bwhatsapp\b/i, /\bchat\b/i],
  instagram_gap: [/\binstagram\b/i, /\bdm\b/i],
  booking_gap: [
    /\bbooking\b/i,
    /\bappointment\b/i,
    /\bconsultation\b/i,
    /\bbooking handoff\b/i,
  ],
  no_show: [/\bno[- ]?show\b/i, /\bdrop after booking\b/i],
  staff_dependency: [
    /\bstaff\b/i,
    /\breception\b/i,
    /\bfront desk\b/i,
    /\bhandoff\b/i,
  ],
};

const CHANNEL_PATTERNS: Record<string, RegExp[]> = {
  whatsapp: [/\bwhatsapp\b/i],
  instagram: [/\binstagram\b/i, /\bdm\b/i],
  email: [/\bemail\b/i, /\bmail\b/i],
  website_chat: [/\bwebsite\b/i, /\bsite\b/i, /\bchat\b/i],
  phone: [/\bcall\b/i, /\bphone\b/i],
  google: [/\bgoogle\b/i, /\bmaps\b/i],
  ads: [/\bads\b/i, /\bmeta\b/i, /\bfacebook ads\b/i, /\binstagram ads\b/i],
  referrals: [/\breferral\b/i],
};

const ROLE_PATTERNS: Record<string, RegExp[]> = {
  founder: [/\bfounder\b/i, /\bowner\b/i],
  doctor: [/\bdoctor\b/i, /\bdr\b/i, /\bdermatologist\b/i, /\bdentist\b/i],
  manager: [/\bmanager\b/i, /\badmin\b/i],
  reception: [/\breception\b/i, /\bfront desk\b/i, /\bcoordinator\b/i],
};

function findMatches(text: string, patternMap: Record<string, RegExp[]>) {
  const matches: string[] = [];

  for (const [label, patterns] of Object.entries(patternMap)) {
    if (patterns.some((pattern) => pattern.test(text))) {
      matches.push(label);
    }
  }

  return matches;
}

function inferRequestedNextStep(text: string) {
  if (/\b(call|speak|talk|demo|walkthrough)\b/i.test(text)) {
    return "call";
  }
  if (/\b(proposal|quote|pricing sheet)\b/i.test(text)) {
    return "proposal";
  }
  if (
    /\b(details|brochure|send|info|explain|show me|show that|share it|share them|tell me more|go on|prove it|how does it work|how it works)\b/i.test(
      text
    )
  ) {
    return "details";
  }
  if (/\b(price|pricing|cost)\b/i.test(text)) {
    return "pricing";
  }
  if (/\b(later|next month|after one month)\b/i.test(text)) {
    return "follow_up_later";
  }
  if (/\b(payment|pay|pilot)\b/i.test(text)) {
    return "payment";
  }

  return null;
}

function rankCommercialStatus(value: WhatsAppOpsState["commercialStatus"]) {
  switch (value) {
    case "contacted":
      return 1;
    case "replied":
      return 2;
    case "qualified":
      return 3;
    case "demo_booked":
      return 4;
    case "demo_done":
      return 5;
    case "pilot_won":
      return 6;
    case "onboarding":
      return 7;
    case "live":
      return 8;
    default:
      return 0;
  }
}

function escalateCommercialStatus(
  current: WhatsAppOpsState["commercialStatus"],
  target: WhatsAppOpsState["commercialStatus"]
) {
  return rankCommercialStatus(target) > rankCommercialStatus(current)
    ? target
    : current;
}

function isLightweightGreeting(text: string) {
  return /^\s*(?:hi|hello|hey|yo|hiya|good\s+morning|good\s+afternoon|good\s+evening)(?:\s+[a-z][a-z'_-]*){0,2}[!?.\s]*$/i.test(
    text
  );
}

function isLightweightAcknowledgement(text: string) {
  return /^\s*(?:ok(?:ay)?|alright|all\s+right|got\s+it|cool|fine|fair|right|sure|makes\s+sense|noted|hmm|hm|kk|k)[!?.\s]*$/i.test(
    text
  );
}

function isLightweightAffirmation(text: string) {
  return /^\s*(?:yes|yeah|yep|yup|ya|sure|absolutely|of\s+course|definitely|please\s+do|go\s+ahead)[!?.\s]*$/i.test(
    text
  );
}

function isLowInformationReply(text: string) {
  return /^\s*(?:i\s*(?:do\s*not|don't|dont)\s*know|not\s*sure|unsure|no\s*idea|idk|don't\s*know\s*yet|dont\s*know\s*yet)[!?.\s]*$/i.test(
    text
  );
}

function lastAssistantAskedFocusChoice(reply: string | null | undefined) {
  const normalized = String(reply ?? "");
  return (
    /\b(which|what side|look at|look at first|sort first|looking at first)\b/i.test(
      normalized
    ) && /\b(reply speed|follow-?up|booking handoff|booking flow)\b/i.test(normalized)
  );
}

function lastAssistantAskedRoleChoice(reply: string | null | undefined) {
  return /\bdoctor,\s*manager,\s*or front desk\b/i.test(String(reply ?? ""));
}

function lastAssistantOfferedNextLeak(reply: string | null | undefined) {
  return /\bwant the next (?:one|point) too\b/i.test(String(reply ?? ""));
}

function lastAssistantAskedPracticalStepConfirmation(
  reply: string | null | undefined
) {
  const normalized = String(reply ?? "");
  return (
    /\bdoes that sound like a practical step to focus on\b/i.test(normalized) ||
    /\bfirst change might be\b/i.test(normalized) ||
    /\bif you(?:'|’)re handling it yourself\b/i.test(normalized)
  );
}

function lastAssistantAskedCaptureVsBooking(reply: string | null | undefined) {
  const normalized = String(reply ?? "");
  return (
    /\b(lead capture|collect (?:patient )?details|enquiry)\b/i.test(normalized) &&
    /\b(confirmed booking|confirmed appointment|booking inside whatsapp|booking inside the chat)\b/i.test(
      normalized
    )
  );
}

function isGeneralCapabilityQuestion(text: string) {
  return /\b(what can you do|who are you|who are u|who r u|what is this|what do you do|how can you help|what are you|what's your role|whats your role)\b/i.test(
    text
  );
}

function isOutboundClinicThread(state: WhatsAppAgentState) {
  return state.leadChannels.includes("outbound_whatsapp");
}

function isClinicSalesThread(state: WhatsAppAgentState) {
  return (
    isOutboundClinicThread(state) ||
    state.leadChannels.includes("sales_whatsapp") ||
    state.leadChannels.includes("clinic_sales")
  );
}

function inferRole(text: string) {
  for (const [label, patterns] of Object.entries(ROLE_PATTERNS)) {
    if (patterns.some((pattern) => pattern.test(text))) {
      return label;
    }
  }

  return null;
}

function lastAssistantOfferedProof(messages: WhatsAppMessage[]) {
  const lastAssistantMessage = [...messages]
    .reverse()
    .find(
      (message) =>
        message.direction === "outgoing" &&
        (message.authorType === "bot" || message.authorType === "human")
    );

  if (!lastAssistantMessage) {
    return false;
  }

  return /\b(show|exact leak|leak points|look at first|keep it practical)\b/i.test(
    lastAssistantMessage.body
  );
}

function normalizePainLabel(value: string | null | undefined) {
  return String(value ?? "")
    .replace(/_/g, " ")
    .trim();
}

function lowerCaseFirst(value: string | null | undefined) {
  const normalized = String(value ?? "").trim();
  if (!normalized) {
    return "";
  }

  return normalized.charAt(0).toLowerCase() + normalized.slice(1);
}

function inferPainPointsFromTranscript(
  messages: WhatsAppMessage[],
  incomingText: string
) {
  const transcript = [...messages.slice(-8).map((message) => message.body), incomingText]
    .filter(Boolean)
    .join(" ");

  return findMatches(transcript, PAIN_PATTERNS);
}

function buildGenericProofReply(firstPain: string | null) {
  switch (firstPain) {
    case "booking gap":
      return [
        "I'd start with the booking handoff after the first enquiry. That's usually where the thread loosens.",
        "I'd look at whether the first answer turns into a real next step quickly enough. That is usually the first thing to tighten.",
      ];
    case "slow response":
      return [
        "I'd start with reply speed on the first enquiry. That is usually where warm intent cools fastest.",
        "I'd check whether the first message gets a real answer or just a delay. That is the first thing I see go wrong most often.",
      ];
    case "missed follow up":
      return [
        "I'd start with the second touch. One missed follow-up is often enough to lose the lead.",
        "I'd look at what happens after the first reply. That quiet gap usually costs bookings.",
      ];
    case "whatsapp gap":
      return [
        "I'd start with what happens after the first WhatsApp reply. If the chat does not move to a clear next step, it just drifts.",
        "I'd inspect whether the chat gets a real next step or just more back-and-forth. That is usually where the thread loses momentum.",
      ];
    case "staff dependency":
      return [
        "I'd start with the handoff between doctor and front desk. That is where good intent usually gets delayed.",
        "I'd look at who actually owns the first reply and follow-up. Staff dependency slows the close path.",
      ];
    case "no show":
      return [
        "I'd start with the gap between booking and showing up. Weak reminders usually make that worse.",
        "I'd inspect what happens after a slot gets booked. Weak reconfirmation quietly stacks up no-shows.",
      ];
    default:
      return [
        "I'd start with the first reply window after someone reaches out. That is usually where the thread starts slipping.",
        "I'd check whether the enquiry gets a real next step or just a slow back-and-forth. That is usually the first place to tighten.",
      ];
  }
}
function inferConfidence({
  messages,
  painPoints,
  objectionCategories,
  requestedNextStep,
  handoffRequested,
  optOut,
}: {
  messages: WhatsAppMessage[];
  painPoints: string[];
  objectionCategories: string[];
  requestedNextStep: string | null;
  handoffRequested: boolean;
  optOut: boolean;
}) {
  let confidence = 0.28;

  confidence += Math.min(messages.length * 0.025, 0.18);
  confidence += Math.min(painPoints.length * 0.1, 0.2);
  confidence += Math.min(objectionCategories.length * 0.08, 0.16);

  if (requestedNextStep) {
    confidence += 0.08;
  }
  if (handoffRequested || optOut) {
    confidence += 0.15;
  }

  return Math.max(0.15, Math.min(0.95, confidence));
}

export function classifyInboundLeadMessage(text: string) {
  const normalized = text.trim();

  if (!normalized) {
    return {
      leadChannels: [] as string[],
      objectionCategories: [] as string[],
      painPoints: [] as string[],
      roleHint: null as string | null,
      requestedNextStep: null as string | null,
      paymentInterest: false,
      optOut: false,
      handoffRequested: false,
      escalateToHuman: false,
      isGreeting: false,
      isAcknowledgement: false,
      isAffirmation: false,
    };
  }

  const objectionCategories = findMatches(normalized, OBJECTION_PATTERNS);
  const requestedNextStep = inferRequestedNextStep(normalized);
  const handoffRequested = HUMAN_HANDOFF_PATTERNS.some((pattern) =>
    pattern.test(normalized)
  );
  const optOut = OPT_OUT_PATTERNS.some((pattern) => pattern.test(normalized));

  return {
    leadChannels: findMatches(normalized, CHANNEL_PATTERNS),
    objectionCategories,
    painPoints: findMatches(normalized, PAIN_PATTERNS),
    roleHint: inferRole(normalized),
    requestedNextStep,
    paymentInterest:
      objectionCategories.includes("price") ||
      requestedNextStep === "payment",
    optOut,
    handoffRequested,
    escalateToHuman:
      handoffRequested ||
      objectionCategories.some((label) =>
        ["price", "safety", "integration", "brochure"].includes(label)
      ),
    isGreeting: isLightweightGreeting(normalized),
    isAcknowledgement: isLightweightAcknowledgement(normalized),
    isAffirmation: isLightweightAffirmation(normalized),
  };
}

export function inferSalesStage(state: WhatsAppAgentState) {
  if (state.optOut) {
    return "CLOSED_LOST" as const;
  }
  if (state.handoffRecommended || state.paymentInterest) {
    return "HUMAN_HANDOFF" as const;
  }
  if (state.requestedNextStep === "payment") {
    return "PAYMENT_PUSHED" as const;
  }
  if (state.requestedNextStep === "call") {
    return "DEMO_PUSHED" as const;
  }
  if (state.objectionCategories.length > 0) {
    return "OBJECTION_ACTIVE" as const;
  }
  if (state.painConfirmed && state.requestedNextStep === "details") {
    return "PROOF_SHARED" as const;
  }
  if (state.painConfirmed && state.decisionMakerConfirmed) {
    return "QUALIFIED" as const;
  }
  if (state.painConfirmed) {
    return "PAIN_FOUND" as const;
  }
  if (state.lastIntent) {
    return "ENGAGED" as const;
  }

  return "NEW" as const;
}

export function inferThreadPriority(state: WhatsAppAgentState) {
  if (
    state.optOut ||
    state.stage === "CLOSED_LOST" ||
    state.stage === "CLOSED_WON"
  ) {
    return "low" as const;
  }

  if (
    state.handoffRecommended ||
    state.paymentInterest ||
    state.requestedNextStep === "call" ||
    state.decisionMakerConfirmed
  ) {
    return "high" as const;
  }

  if (state.painConfirmed || state.objectionCategories.length > 0) {
    return "high" as const;
  }

  return state.lastIntent ? ("medium" as const) : ("low" as const);
}

export function inferNextBestMove(state: WhatsAppAgentState) {
  if (isOutboundClinicThread(state) && !state.painConfirmed) {
    return "Keep the clinic in founder-led SDR mode: diagnose enquiry drop-off, quantify WhatsApp volume, then move to a 3-minute demo.";
  }

  if (isClinicSalesThread(state) && !state.painConfirmed) {
    return "Keep this in clinic-sales intake mode: confirm clinic context, clarify booking vs follow-up need, then narrow the real drop-off point.";
  }

  switch (state.stage) {
    case "NEW":
    case "ENGAGED":
      return "Keep it conversational and ask one grounded question.";
    case "PAIN_FOUND":
      return "Validate the gap and offer to show the exact leak.";
    case "QUALIFIED":
      return "Move toward a founder-led 3-minute demo and confirm the paid pilot fit.";
    case "PROOF_SHARED":
      return "Use one proof-led observation and ask for the lightest next step.";
    case "OBJECTION_ACTIVE":
      return "Acknowledge the concern, reframe around leakage, and keep the ask small.";
    case "DEMO_PUSHED":
      return "Lock the 3-minute demo and keep the founder ready to take over.";
    case "PAYMENT_PUSHED":
      return "Prepare the founder handoff for pricing, paid pilot terms, or clinic-owned sender onboarding.";
    case "HUMAN_HANDOFF":
      return "Hand the thread to a human closer with a clean summary.";
    case "CLOSED_LOST":
      return "Close the loop and stop further contact.";
    default:
      return "Keep the next move simple and specific.";
  }
}

export function summarizeConversationState({
  conversation,
  state,
}: {
  conversation: WhatsAppConversation;
  state: WhatsAppAgentState;
}) {
  const summaryParts = [
    `${conversation.contactName} is in ${state.stage.toLowerCase()} stage`,
  ];

  if (isClinicSalesThread(state) && !conversation.linkedLeadId) {
    summaryParts.push(
      isOutboundClinicThread(state)
        ? "outbound clinic SDR thread"
        : "unlinked inbound clinic sales thread"
    );
  }

  if (state.painPoints.length > 0) {
    summaryParts.push(`pain: ${state.painPoints.join(", ")}`);
  }

  if (state.objectionCategories.length > 0) {
    summaryParts.push(`objections: ${state.objectionCategories.join(", ")}`);
  }

  if (state.requestedNextStep) {
    summaryParts.push(`asked about ${state.requestedNextStep}`);
  }

  if (state.handoffRecommended && state.handoffReason) {
    summaryParts.push(`handoff: ${state.handoffReason}`);
  }

  return summaryParts.join(" | ");
}

export function buildHandoffReason(state: WhatsAppAgentState) {
  if (state.optOut) {
    return "Lead opted out";
  }
  if (state.paymentInterest) {
    return "Pricing or paid pilot discussion is active";
  }
  if (state.objectionCategories.includes("safety")) {
    return "Healthcare safety or compliance concern needs careful handling";
  }
  if (state.objectionCategories.includes("integration")) {
    return "Clinic-number onboarding or integration question needs a specific human answer";
  }
  if (state.objectionCategories.includes("price")) {
    return "Pricing discussion should move to a human closer";
  }
  if (state.requestedNextStep === "proposal") {
    return "Proposal request should move to the founder or closer";
  }
  if (state.requestedNextStep === "details") {
    return "Operational details request needs a founder-led answer";
  }
  if (state.requestedNextStep === "call") {
    return "Lead is asking for a demo or live discussion";
  }

  return null;
}

export function deriveWhatsAppOpsStatePatch({
  currentOpsState,
  nextState,
  leadContext,
  shouldRespondWithinMinutes = false,
}: {
  currentOpsState: WhatsAppOpsState;
  nextState: WhatsAppAgentState;
  leadContext?: WhatsAppLinkedLeadContext | null;
  shouldRespondWithinMinutes?: boolean;
}): Partial<WhatsAppOpsState> {
  let commercialStatus = currentOpsState.commercialStatus;

  if (rankCommercialStatus(commercialStatus) < rankCommercialStatus("replied")) {
    commercialStatus = "replied";
  }

  if (
    nextState.painConfirmed &&
    (nextState.decisionMakerConfirmed ||
      Boolean(nextState.requestedNextStep) ||
      nextState.handoffRecommended)
  ) {
    commercialStatus = escalateCommercialStatus(commercialStatus, "qualified");
  }

  return {
    commercialStatus,
    city: currentOpsState.city ?? leadContext?.geo ?? null,
    contactChannel:
      currentOpsState.contactChannel ??
      leadContext?.bestContactChannel ??
      leadContext?.recommendedChannel ??
      "whatsapp",
    nextActionAt: shouldRespondWithinMinutes
      ? new Date(Date.now() + 15 * 60_000).toISOString()
      : currentOpsState.nextActionAt,
  };
}

export function buildWhatsAppFallbackReply(
  state: WhatsAppAgentState,
  recentReplies: Array<string | null | undefined> = [],
  leadContext?: WhatsAppLinkedLeadContext | null,
  incomingText?: string | null,
  latestAssistantReply?: string | null
) {
  const replyHistory = [state.lastSuggestedReply, ...recentReplies];
  const isLinkedLeadThread = Boolean(leadContext?.leadId);
  const isOutboundClinicLeadThread =
    !isLinkedLeadThread && isOutboundClinicThread(state);

  if (isOutboundClinicLeadThread) {
    if (state.optOut) {
      return pickFreshReply(
        [
          "Understood. I'll close the thread from here.",
          "All good. I'll stop the follow-up from here.",
        ],
        replyHistory
      );
    }

    if (state.handoffRecommended || state.requestedNextStep === "call") {
      return pickFreshReply(
        [
          "It’s easier to show than explain — takes 3 minutes. Want a quick walkthrough?",
          "Better to show this properly than drag it over text. Want a quick 3-minute walkthrough?",
        ],
        replyHistory
      );
    }

    if (isLightweightGreeting(incomingText || "")) {
      return pickFreshReply(
        [
          "Quick one - when someone messages the clinic but doesn't finish booking, do they usually come back later or do they mostly disappear?",
          "Quick one - on your side, when a WhatsApp enquiry doesn't finish booking, does it usually recover later or just fade out?",
        ],
        replyHistory
      );
    }

    if (isGeneralCapabilityQuestion(incomingText || "")) {
      return pickFreshReply(
        [
          "I help clinics tighten WhatsApp booking and follow-up. The reason I reached out is that a lot of enquiries cool off before they ever book. Is that happening on your side?",
          "I work on the WhatsApp side for clinics - reply speed, follow-up, and getting chats to a real booking instead of losing them. Is that a live issue on your side?",
        ],
        replyHistory
      );
    }

    if (isLightweightAffirmation(incomingText || "")) {
      return pickFreshReply(
        [
          "Roughly how many WhatsApp enquiries do you get in a normal week?",
          "On a normal week, how many WhatsApp enquiries hit the clinic?",
        ],
        replyHistory
      );
    }

    if (isLightweightAcknowledgement(incomingText || "")) {
      return pickFreshReply(
        [
          "Alright. If you had to guess, how many WhatsApp chats come in most weeks?",
          "All good. Roughly how many enquiries come in through WhatsApp in a normal week?",
        ],
        replyHistory
      );
    }

    if (state.requestedNextStep === "details") {
      return pickFreshReply(
        [
          "Main thing I'd check first is whether the first WhatsApp reply turns into a real next step or just more back-and-forth. If that part is loose, warm intent cools fast.",
          "First thing I'd look at is what happens after the first enquiry lands. If nobody owns the thread quickly, the booking usually drifts.",
        ],
        replyHistory
      );
    }

    if (state.painConfirmed && state.painPoints.length > 0) {
      return pickFreshReply(
        [
          "Useful. Is the bigger issue slow first reply, weak follow-up, or patients dropping before a slot is actually confirmed?",
          "That helps. Is the bigger drag reply speed, follow-up discipline, or chats going quiet before the booking gets locked?",
        ],
        replyHistory
      );
    }

    return pickFreshReply(
      [
        "The main thing I'm trying to understand is whether WhatsApp enquiries are actually turning into booked consults consistently, or whether some cool off before that. What's happening on your side?",
        "From what I see, most clinics don't lose demand - they lose momentum between the first message and the booked slot. Does that show up on your side too?",
      ],
      replyHistory
    );
  }

  if (!isLinkedLeadThread && isClinicSalesThread(state)) {
    if (state.optOut) {
      return pickFreshReply(
        [
          "Understood. I’ll close this from here.",
          "All good. I’ll stop here.",
        ],
        replyHistory
      );
    }

    if (state.handoffRecommended || state.requestedNextStep === "call") {
      return pickFreshReply(
        [
          "Better to keep this clean with a quick walkthrough. Do you want to do that now or later today?",
          "This is easier to show properly than drag over text. Want a quick walkthrough?",
        ],
        replyHistory
      );
    }

    if (isLightweightGreeting(incomingText || "")) {
      return pickFreshReply(
        [
          "Hi, this is ZRAI. Is this for your clinic or healthcare setup? Tell me a little about what you want WhatsApp to handle and I'll guide you from there.",
          "Hi, this is ZRAI. If this is for a clinic, tell me what kind of setup you are looking at on WhatsApp - enquiries, bookings, or follow-up.",
        ],
        replyHistory
      );
    }

    if (isGeneralCapabilityQuestion(incomingText || "")) {
      return pickFreshReply(
        [
          "This line is for clinic-side WhatsApp setup - enquiries, booking flow, and follow-up. Tell me what kind of clinic this is and what you want WhatsApp to handle.",
          "I help clinics set up WhatsApp around enquiries, bookings, and follow-up. Start with the clinic type and the workflow you want to tighten.",
        ],
        replyHistory
      );
    }

    if (isLowInformationReply(incomingText || "")) {
      return pickFreshReply(
        [
          "No issue. Start with two things: what kind of clinic this is, and whether you want WhatsApp mainly for enquiries, bookings, or follow-up.",
          "That's fine. Tell me what type of clinic this is first, then tell me if the main need is enquiry capture, booking, or follow-up on WhatsApp.",
        ],
        replyHistory
      );
    }

    if (state.painConfirmed && state.painPoints.includes("booking_gap")) {
      return pickFreshReply(
        [
          "Understood. Tell me which one you want first: just enquiry capture on WhatsApp, or confirmed bookings inside WhatsApp. Also, is this for one clinic or multiple branches?",
          "Got it. Pick the main goal first: enquiry capture only, or full booking inside WhatsApp. If relevant, tell me whether this is for one clinic or several branches.",
        ],
        replyHistory
      );
    }

    if (
      /\b(enquiry|inquiry|lead capture|capture only|just enquiry|just inquiry|collect (?:patient )?details)\b/i.test(
        incomingText || ""
      )
    ) {
      return pickFreshReply(
        [
          "Got it. So this is more of an enquiry capture flow. Is this for one clinic or multiple branches, and where are patients coming in from now: WhatsApp, Instagram, ads, or website?",
          "Understood. Then the main flow is enquiry capture, not full booking. Tell me if this is one clinic or multiple branches, and what channels are bringing patients in now.",
        ],
        replyHistory
      );
    }

    if (
      state.painConfirmed &&
      (state.painPoints.includes("whatsapp_gap") ||
        state.painPoints.includes("missed_follow_up") ||
        state.painPoints.includes("slow_response"))
    ) {
      return pickFreshReply(
        [
          "Understood. What is actually breaking now: slow first reply, weak follow-up, or patients dropping before the booking gets confirmed?",
          "That helps. Is the bigger issue reply speed, follow-up discipline, or chats going quiet before a slot is locked?",
        ],
        replyHistory
      );
    }

    if (isLightweightAffirmation(incomingText || "")) {
      if (lastAssistantAskedCaptureVsBooking(latestAssistantReply)) {
        return pickFreshReply(
          [
            "Tell me which one you want first: enquiry capture only, or confirmed bookings inside WhatsApp.",
            "Pick one for me: just enquiry capture, or full booking inside WhatsApp.",
          ],
          replyHistory
        );
      }

      return pickFreshReply(
        [
          "Perfect. Start with the clinic type, then tell me whether the main need is enquiries, bookings, or follow-up on WhatsApp.",
          "Alright. Tell me what kind of clinic this is and which workflow matters first - enquiry capture, booking, or follow-up.",
        ],
        replyHistory
      );
    }

    if (isLightweightAcknowledgement(incomingText || "")) {
      return pickFreshReply(
        [
          "Okay. Start with the clinic type and the part you want WhatsApp to handle - enquiries, bookings, or follow-up.",
          "Alright. Tell me what kind of clinic this is and whether the first priority is booking, follow-up, or enquiry capture.",
        ],
        replyHistory
      );
    }

    return pickFreshReply(
      [
        "Tell me a little about the clinic first, then tell me what you want WhatsApp to handle - enquiries, bookings, or follow-up.",
        "Give me two things: the clinic type, and the workflow you want on WhatsApp. I'll take it from there.",
      ],
      replyHistory
    );
  }

  if (!isLinkedLeadThread) {
    if (isLightweightGreeting(incomingText || "")) {
      return pickFreshReply(
        [
          "Hi, this is ZRAI. Is this for a clinic or healthcare business? If yes, tell me what you want WhatsApp to handle.",
          "Hi, this is ZRAI. If this is for a clinic, tell me whether the main need is enquiries, bookings, or follow-up on WhatsApp.",
        ],
        replyHistory
      );
    }

    if (isGeneralCapabilityQuestion(incomingText || "")) {
      return pickFreshReply(
        [
          "This line is for clinic-side WhatsApp setup. Tell me what kind of clinic this is and whether you are looking at enquiries, bookings, or follow-up.",
          "I help clinics tighten their WhatsApp flow. Start with the clinic type and the part you want to improve first.",
        ],
        replyHistory
      );
    }

    if (isLowInformationReply(incomingText || "")) {
      return pickFreshReply(
        [
          "No problem. Start with the clinic type, then tell me if the need is enquiry capture, booking, or follow-up on WhatsApp.",
          "That's okay. Tell me what kind of clinic this is first, and whether WhatsApp needs to handle enquiries, bookings, or follow-up.",
        ],
        replyHistory
      );
    }

    if (isLightweightAffirmation(incomingText || "")) {
      return pickFreshReply(
        [
          "Good. Start with the clinic type, then tell me whether the first need is enquiries, bookings, or follow-up.",
          "Alright. Tell me what kind of clinic this is and which WhatsApp workflow matters first.",
        ],
        replyHistory
      );
    }

    if (isLightweightAcknowledgement(incomingText || "")) {
      return pickFreshReply(
        [
          "Alright. Start with the clinic type, then tell me what you want WhatsApp to handle.",
          "Okay. Tell me if this is for a clinic and whether the first need is enquiry capture, booking, or follow-up.",
        ],
        replyHistory
      );
    }

    return pickFreshReply(
      [
        "Tell me what kind of clinic this is and what you want WhatsApp to handle, and I'll guide it properly from there.",
        "Give me the clinic type and the workflow you want on WhatsApp - enquiries, bookings, or follow-up - and I'll take it from there.",
      ],
      replyHistory
    );
  }

  if (isLightweightGreeting(incomingText || "")) {
    if (state.painConfirmed && state.decisionMakerConfirmed) {
      return pickFreshReply(
        [
          "Good to hear from you. Do you want to look at reply speed, follow-up, or booking handoff first?",
          "Hey. Which side do you want to look at first: first reply, follow-up, or booking handoff?",
        ],
        replyHistory
      );
    }

    if (state.painConfirmed) {
      return pickFreshReply(
        [
          "Hey. Are we looking at reply speed, follow-up, or booking handoff today?",
          "Good to hear from you. Which part feels worth looking at first: replies, follow-up, or bookings?",
        ],
        replyHistory
      );
    }

    return pickFreshReply(
      [
        "Hey. What side do you want to look at first: replies, follow-up, or bookings?",
        "Hi. What do you want to sort first: response speed, follow-up, or booking flow?",
      ],
      replyHistory
    );
  }

  if (isLightweightAcknowledgement(incomingText || "")) {
    if (state.requestedNextStep === "details") {
      return pickFreshReply(
        [
          "Alright. Do you want the next thing I'd tighten, or do you want to stay on the first point for a minute?",
          "Okay. I can give you the next point, or we can unpack the first one properly.",
        ],
        replyHistory
      );
    }

    return pickFreshReply(
      [
        "Alright. Which side do you want to go deeper on: first reply, follow-up, or booking handoff?",
        "Okay. Do you want to look deeper at response speed, follow-up, or booking flow?",
      ],
      replyHistory
    );
  }

  if (isLightweightAffirmation(incomingText || "")) {
    if (lastAssistantAskedFocusChoice(latestAssistantReply)) {
      return pickFreshReply(
        [
          "Which one do you want first: reply speed, follow-up, or booking handoff?",
          "Good. Pick the lane you want to start with: first reply, follow-up, or booking handoff.",
        ],
        replyHistory
      );
    }

    if (lastAssistantAskedRoleChoice(latestAssistantReply)) {
      return pickFreshReply(
        [
          "Which one is it right now: doctor, manager, or front desk?",
          "Tell me who owns it day to day: doctor, manager, or front desk?",
        ],
        replyHistory
      );
    }

    if (lastAssistantOfferedNextLeak(latestAssistantReply)) {
      return pickFreshReply(
        [
          "Second thing I'd tighten is follow-up after the first reply. If nobody keeps control after that first exchange, warm leads drift before a slot gets locked.",
          "Next place I'd look is what happens after the first response. If follow-up is loose there, intent fades before the booking ask lands.",
        ],
        replyHistory
      );
    }

    if (lastAssistantAskedPracticalStepConfirmation(latestAssistantReply)) {
      return pickFreshReply(
        [
          "Good. I would keep it simple: if you cannot reply properly in the moment, send a short holding message straight away and set one follow-up for later the same day.",
          "Good. First fix would be a simple busy-state rule: acknowledge the enquiry fast, then send one proper follow-up at a defined time instead of letting the thread drift.",
        ],
        replyHistory
      );
    }
  }

  if (state.optOut) {
    return pickFreshReply(
      [
        "I'll close this thread and stop the follow-up.",
        "I'll keep you off the follow-up list from here.",
      ],
      replyHistory
    );
  }

  if (state.handoffRecommended) {
    return pickFreshReply(
      [
        "I'm handing this to a human so you get a clean answer.",
        "I'll pass this to a person on our side and keep it clean.",
      ],
      replyHistory
    );
  }

  if (state.requestedNextStep === "details") {
    const topIssue = normalizePainLabel(leadContext?.topIssue);
    const nextBestAction = lowerCaseFirst(leadContext?.nextBestAction);
    const firstPain = normalizePainLabel(state.painPoints[0]);

    if (topIssue && nextBestAction) {
      return pickFreshReply(
        [
          `I'd tighten ${topIssue} first. I'd start by ${nextBestAction}. If useful, I can give you the next thing I'd tighten after that.`,
          `The clearest leak I see is ${topIssue}. First move I'd make is ${nextBestAction}. I can keep going if useful.`,
        ],
        replyHistory
      );
    }

    if (topIssue) {
      return pickFreshReply(
        [
          `I'd start with ${topIssue}. That is usually where warm intent slips first. If useful, I can give you the next point after that.`,
          `The first thing I'd tighten is ${topIssue}. Fix that first and the thread usually gets cleaner. I can keep going if useful.`,
        ],
        replyHistory
      );
    }

    if (firstPain) {
      return pickFreshReply(
        buildGenericProofReply(firstPain).map(
          (reply) => `${reply} If useful, I can give you the next point after that.`
        ),
        replyHistory
      );
    }

    return pickFreshReply(
      [
        "I'd start with the first reply window after someone reaches out. That is usually where the thread starts slipping.",
        "The cleanest place to look is who answers first and how quickly it turns into a real next step.",
        "I'd check whether the enquiry gets a straight answer or just more back-and-forth. That's usually the first thing to tighten.",
      ],
      replyHistory
    );
  }

  if (state.requestedNextStep === "call") {
    return pickFreshReply(
      [
        "A quick 10-minute look will be cleaner than a long text. Today or tomorrow?",
        "Happy to keep it short. Today or tomorrow works better for a quick call?",
      ],
      replyHistory
    );
  }

  if (state.painConfirmed && state.painPoints.length > 0) {
    const focusedPain = normalizePainLabel(
      state.painPoints[state.painPoints.length - 1] ?? state.painPoints[0]
    );

    return pickFreshReply(
      buildGenericProofReply(focusedPain).map(
        (reply) => `${reply} If you want, I can stay on this point or give you the next one.`
      ),
      replyHistory
    );
  }

  if (!state.painConfirmed) {
    return pickFreshReply(
      [
        "I'm trying to narrow where the process is breaking first: first reply, follow-up, or handoff. Which one feels weakest?",
        "The first gap I'd check is response speed, lead handling, or booking ownership. Which one feels roughest today?",
        "I'm narrowing the point that is actually slowing bookings down. What is slipping today?",
      ],
      replyHistory
    );
  }

  if (state.objectionCategories.length > 0) {
    return pickFreshReply(
      [
        "Fair point. I'm not talking about more noise, just the one practical thing worth fixing first. Want the short version?",
        "I can keep it to the one point that matters most and skip the fluff.",
      ],
      replyHistory
    );
  }

  if (!state.decisionMakerConfirmed) {
    return pickFreshReply(
      [
        "Who usually owns bookings and follow-up there: doctor, manager, or front desk?",
        "Quick check, who actually handles this side right now?",
      ],
      replyHistory
    );
  }

  return pickFreshReply(
    [
      "I'd start with the first leak point and keep it practical.",
      "I can keep this tight and point to the main drop-off spot first.",
    ],
    replyHistory
  );
}
export function buildWhatsAppSystemPrompt({
  conversation,
  state,
  messages,
  leadContext,
}: {
  conversation: WhatsAppConversation;
  state: WhatsAppAgentState;
  messages: WhatsAppMessage[];
  leadContext?: {
    companyName?: string | null;
    topIssue?: string | null;
    nextBestAction?: string | null;
    decisionMakerName?: string | null;
    decisionMakerRole?: string | null;
    bestContactChannel?: string | null;
    finalScore?: number | null;
  } | null;
}) {
  const transcript = messages
    .slice(-8)
    .map((message) => `${message.authorLabel}: ${message.body}`)
    .join("\n");

  if (!conversation.linkedLeadId && isOutboundClinicThread(state)) {
    return [
      "You are a human-sounding founder-side WhatsApp SDR messaging Derm and Aesthetic clinics about missed bookings and enquiry drop-off.",
      "This thread started from outbound WhatsApp outreach.",
      "Stay anchored to the outbound angle in the conversation memory.",
      "Do not sound like support, a generic chatbot, or a clinic auditor.",
      "Do not mention AI, automation stack, lead scores, or internal system terms unless asked directly.",
      "Keep replies short, calm, commercially sharp, and human.",
      "Ask one grounded question at a time.",
      "Do not jump into a long pitch.",
      "First diagnose what happens to WhatsApp enquiries that do not finish booking.",
      "Then quantify weekly volume or the main drop-off point.",
      "Only move to a quick demo after the clinic confirms there is a real gap.",
      "If the clinic asks for pricing, proposal, details, compliance, or whether this can run on their number, prepare a clean founder handoff.",
      "If the latest inbound is a greeting, do not lose the outbound frame. Re-open with the same enquiry-drop-off conversation.",
      "If the clinic asks who you are or what you do, explain it plainly in one or two short lines and stay on the booking problem.",
      "If the clinic asks for details, give one concrete operational point instead of promising to show it later.",
      `Current stage: ${state.stage}`,
      `Priority: ${state.priority}`,
      `State summary: ${state.summary ?? "none"}`,
      `Next best move: ${state.nextBestMove ?? "none"}`,
      `Last suggested reply: ${state.lastSuggestedReply ?? "none"}`,
      `Pain points: ${state.painPoints.join(", ") || "not yet confirmed"}`,
      `Objections: ${state.objectionCategories.join(", ") || "none"}`,
      `Requested next step: ${state.requestedNextStep ?? "unknown"}`,
      `Contact: ${conversation.contactName}`,
      `Recent transcript:\n${transcript || "No prior transcript"}`,
    ].join("\n");
  }

  if (!conversation.linkedLeadId && isClinicSalesThread(state)) {
    return [
      "You are a human-sounding clinic sales intake assistant on a WhatsApp sales line.",
      "This is an inbound clinic prospect thread without a resolved lead record yet.",
      "Do not act like a generic support bot.",
      "Assume the contact is exploring clinic-side help with patient booking, follow-up, reminders, or enquiry handling unless the thread proves otherwise.",
      "Never say you are an AI.",
      "Keep replies short, calm, structured, and human.",
      "On the first turn, introduce yourself lightly as ZRAI instead of sounding like an anonymous bot.",
      "Ask one grounded question at a time.",
      "Do not jump into a long pitch.",
      "First confirm whether this is for a clinic, hospital, or healthcare service, then ask for a little context.",
      "After that, clarify the workflow naturally: booking, follow-up, reminders, lead capture, or another clinic-side need.",
      "If they mention booking or WhatsApp patient handling, keep the thread in healthcare-sales mode instead of falling back to generic inbox language.",
      "If they ask for pricing, proposal, sender setup, whether it can run on their number, or operational details, prepare a clean founder handoff.",
      `Current stage: ${state.stage}`,
      `Priority: ${state.priority}`,
      `State summary: ${state.summary ?? "none"}`,
      `Next best move: ${state.nextBestMove ?? "none"}`,
      `Last suggested reply: ${state.lastSuggestedReply ?? "none"}`,
      `Pain points: ${state.painPoints.join(", ") || "not yet confirmed"}`,
      `Objections: ${state.objectionCategories.join(", ") || "none"}`,
      `Requested next step: ${state.requestedNextStep ?? "unknown"}`,
      `Contact: ${conversation.contactName}`,
      `Recent transcript:\n${transcript || "No prior transcript"}`,
    ].join("\n");
  }

  if (!conversation.linkedLeadId) {
    return [
      "You are a human-sounding WhatsApp assistant handling a manual contact thread.",
      "Do not act like a clinic auditor, growth consultant, or lead-scoring bot unless the contact explicitly goes there.",
      "Do not mention leakages, booking gaps, handoffs, revenue loss, or operational diagnosis unless the contact brings that topic up.",
      "Your job is to understand who the person is, what they want, and keep the conversation natural and easy to follow.",
      "Sound calm, direct, and human.",
      "Never say you are an AI.",
      "Keep replies short and clear.",
      "Ask one grounded question at a time.",
      "If the contact asks what you do, answer plainly and stay on their topic.",
      "If the thread is vague, ask for the context instead of inventing a sales angle.",
      `Contact: ${conversation.contactName}`,
      `Recent transcript:\n${transcript || "No prior transcript"}`,
    ].join("\n");
  }

  return [
    "You are a premium WhatsApp sales closer for clinics and medspas.",
    "You sound calm, credible, commercially mature, and human.",
    "Never say you are an AI.",
    "Never use markdown, bullet formatting, or long paragraphs.",
    "Reply in 1-3 short WhatsApp-style chat bubbles worth of text.",
    "If you use more than one bubble, separate them with a blank line.",
    "Do not pitch too early.",
    "Do not explain tech unless asked.",
    "Focus on response speed, follow-up discipline, missed bookings, and operational leakage.",
    "If the lead asks for a human, pricing, pilot details, or seems uncomfortable, keep it short and move to handoff.",
    "Do not invent case studies, guaranteed ROI, or direct founder contact if it is not verified.",
    "Sound like a real operator, not a support bot or assistant.",
    "Do not start every message with 'Got it', 'Makes sense', or 'Understood'.",
    "Do not sound templated, scripted, or like a sales sequence.",
    "Keep the tone composed, direct, slightly sharp, and trustworthy.",
    "Use one concrete question or one concrete observation per reply.",
    "If the latest inbound is just a greeting, do not resume an old proof or call prompt. Re-open naturally and ask what they want to look at now.",
    "If the lead asks to see details, proof, or leak points, actually give the first leak immediately.",
    "Do not say 'I can show you' or 'I can share' when the lead already asked for it. Just show the first point.",
    "Do not offer a consultation, a call, automation, or a system unless the lead asked for that next step.",
    "Prefer grounded operational observations over generic sales language.",
    "Do not repeat your last suggested reply. If a similar reply is already in the recent transcript, vary the wording and ask a different diagnostic question.",
    "Use the conversation memory as your anchor. If the memory is thin, infer the most likely leak from the thread instead of restarting the conversation.",
    `Current stage: ${state.stage}`,
    `Priority: ${state.priority}`,
    `State summary: ${state.summary ?? "none"}`,
    `Next best move: ${state.nextBestMove ?? "none"}`,
    `Last suggested reply: ${state.lastSuggestedReply ?? "none"}`,
    `Pain points: ${state.painPoints.join(", ") || "not yet confirmed"}`,
    `Objections: ${state.objectionCategories.join(", ") || "none"}`,
    `Requested next step: ${state.requestedNextStep ?? "unknown"}`,
    state.requestedNextStep === "details"
      ? "Priority instruction: give the first concrete leak point now, then ask if they want the second one."
      : null,
    `Current mode: ${conversation.mode}`,
    leadContext?.companyName ? `Linked clinic: ${leadContext.companyName}` : null,
    leadContext?.finalScore != null ? `Lead score: ${leadContext.finalScore}` : null,
    leadContext?.topIssue ? `Top issue: ${leadContext.topIssue}` : null,
    leadContext?.nextBestAction
      ? `Recommended next action: ${leadContext.nextBestAction}`
      : null,
    leadContext?.decisionMakerName
      ? `Decision maker: ${leadContext.decisionMakerName} (${leadContext.decisionMakerRole || "unknown role"})`
      : null,
    leadContext?.bestContactChannel
      ? `Best contact channel: ${leadContext.bestContactChannel}`
      : null,
    "If the message is a proof request, answer with the actual first leak instead of promising to show it later.",
    "If the message is a follow-up or check-in, keep the reply human and move the thread forward instead of re-opening the same question.",
    `Recent transcript:\n${transcript || "No prior transcript"}`,
  ]
    .filter(Boolean)
    .join("\n");
}

export function deriveNextWhatsAppAgentState({
  conversation,
  messages,
  incomingText,
  currentState,
}: {
  conversation: WhatsAppConversation;
  messages: WhatsAppMessage[];
  incomingText: string;
  currentState: WhatsAppAgentState;
}) {
  const classification = classifyInboundLeadMessage(incomingText);
  const isUnlinkedConversation =
    !conversation.linkedLeadId && !conversation.leadContext?.leadId;
  const outboundClinicThread = isUnlinkedConversation
    ? isOutboundClinicThread(currentState)
    : false;
  const shouldResetNextStep =
    classification.isGreeting &&
    !classification.requestedNextStep &&
    classification.painPoints.length === 0 &&
    classification.objectionCategories.length === 0 &&
    !classification.roleHint &&
    !classification.handoffRequested &&
    !classification.optOut;
  const shouldFreshStartUnlinkedThread =
    isUnlinkedConversation &&
    !outboundClinicThread &&
    (classification.isGreeting || isGeneralCapabilityQuestion(incomingText)) &&
    !classification.requestedNextStep &&
    !classification.handoffRequested &&
    !classification.optOut;
  const stateSeed: WhatsAppAgentState = shouldFreshStartUnlinkedThread
    ? {
        ...DEFAULT_WHATSAPP_AGENT_STATE,
        lastSuggestedReply: currentState.lastSuggestedReply,
      }
    : currentState;
  const contextualPainPoints =
    isUnlinkedConversation
      ? []
      : stateSeed.painPoints.length > 0 ||
    !(
      stateSeed.painConfirmed ||
      classification.requestedNextStep === "details" ||
      /\b(yes|yeah|yup|ok|okay|sure|show|share|tell me|go on|exactly|correct|true|sometimes)\b/i.test(
        incomingText
      )
    )
      ? []
      : inferPainPointsFromTranscript(messages, incomingText);
  const inferredNextStep =
    classification.requestedNextStep ||
    (lastAssistantOfferedProof(messages) &&
    /\b(yes|yeah|yup|ok|okay|sure|show|share|tell me|go on)\b/i.test(
      incomingText
    )
      ? "details"
      : null);

  const nextState: WhatsAppAgentState = {
    ...stateSeed,
    leadChannels: [
      ...stateSeed.leadChannels,
      ...classification.leadChannels,
    ],
    painPoints: [
      ...stateSeed.painPoints,
      ...classification.painPoints,
      ...contextualPainPoints,
    ],
    objectionCategories: [
      ...stateSeed.objectionCategories,
      ...classification.objectionCategories,
    ],
    requestedNextStep:
      shouldResetNextStep
        ? null
        : inferredNextStep ?? stateSeed.requestedNextStep,
    lastIntent: incomingText.trim() || stateSeed.lastIntent,
    decisionMakerRole:
      stateSeed.decisionMakerRole ?? classification.roleHint ?? null,
    decisionMakerConfirmed:
      stateSeed.decisionMakerConfirmed ||
      Boolean(
        classification.roleHint &&
          ["founder", "doctor", "manager"].includes(classification.roleHint)
      ),
    painConfirmed:
      stateSeed.painConfirmed ||
      classification.painPoints.length > 0 ||
      /\b(yes|yeah|true|correct|exactly|sometimes)\b/i.test(incomingText),
    paymentInterest:
      stateSeed.paymentInterest || classification.paymentInterest,
    optOut: classification.optOut,
    handoffRecommended: false,
    handoffReason: null,
    updatedAt: new Date().toISOString(),
  };

  nextState.confidence = inferConfidence({
    messages,
    painPoints: nextState.painPoints,
    objectionCategories: nextState.objectionCategories,
    requestedNextStep: nextState.requestedNextStep,
    handoffRequested: classification.handoffRequested,
    optOut: nextState.optOut,
  });
  nextState.stage = inferSalesStage(nextState);
  nextState.priority = inferThreadPriority(nextState);
  nextState.nextBestMove = inferNextBestMove(nextState);
  nextState.handoffReason = buildHandoffReason(nextState);
  nextState.handoffRecommended = Boolean(
    classification.escalateToHuman || nextState.handoffReason
  );
  nextState.summary = summarizeConversationState({
    conversation,
    state: nextState,
  });

  return {
    classification,
    nextState,
  };
}
