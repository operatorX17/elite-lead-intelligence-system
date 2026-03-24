import type { WhatsAppConversation, WhatsAppMessage } from "@/lib/db/schema";
import type {
  WhatsAppAgentState,
  WhatsAppLinkedLeadContext,
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
  missed_follow_up: [/\bmissed\b/i, /\bdrop ?off\b/i, /\bno follow[- ]?up\b/i],
  slow_response: [/\bslow\b/i, /\blate\b/i, /\bdelay\b/i, /\bnot replied\b/i],
  whatsapp_gap: [/\bwhatsapp\b/i, /\bchat\b/i],
  instagram_gap: [/\binstagram\b/i, /\bdm\b/i],
  booking_gap: [/\bbooking\b/i, /\bappointment\b/i, /\bconsultation\b/i],
  no_show: [/\bno[- ]?show\b/i, /\bdrop after booking\b/i],
  staff_dependency: [/\bstaff\b/i, /\breception\b/i, /\bfront desk\b/i],
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
  if (
    /\b(details|brochure|send|info|explain|show me|show that|share it|share them|tell me more|go on|prove it)\b/i.test(
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
        ["price", "safety", "integration"].includes(label)
      ),
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
  switch (state.stage) {
    case "NEW":
    case "ENGAGED":
      return "Keep it conversational and ask one grounded question.";
    case "PAIN_FOUND":
      return "Validate the gap and offer to show the exact leak.";
    case "QUALIFIED":
      return "Move toward a short call or audit review.";
    case "PROOF_SHARED":
      return "Use one proof-led observation and ask for the lightest next step.";
    case "OBJECTION_ACTIVE":
      return "Acknowledge the concern, reframe around leakage, and keep the ask small.";
    case "DEMO_PUSHED":
      return "Offer a short call with two concrete time options.";
    case "PAYMENT_PUSHED":
      return "Prepare a careful human handoff for pricing or pilot details.";
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
    return "Payment or pilot discussion is active";
  }
  if (state.objectionCategories.includes("safety")) {
    return "Healthcare safety or compliance concern needs careful handling";
  }
  if (state.objectionCategories.includes("integration")) {
    return "Integration question needs a specific human answer";
  }
  if (state.objectionCategories.includes("price")) {
    return "Pricing discussion should move to a human closer";
  }
  if (state.requestedNextStep === "call") {
    return "Lead is asking for a live discussion";
  }

  return null;
}

export function buildWhatsAppFallbackReply(
  state: WhatsAppAgentState,
  recentReplies: Array<string | null | undefined> = [],
  leadContext?: WhatsAppLinkedLeadContext | null
) {
  const replyHistory = [state.lastSuggestedReply, ...recentReplies];

  if (state.optOut) {
    return pickFreshReply(
      [
        "Understood. I'll close the loop here and won't continue the follow-up.",
        "Understood. I'll stop the follow-up here and keep you off the list.",
      ],
      replyHistory
    );
  }

  if (state.handoffRecommended) {
    return pickFreshReply(
      [
        "Makes sense. I'll have a human from our team take this over so you get a clean answer.",
        "Got it. I'll pass this to a human so you get a clear answer without the back-and-forth.",
      ],
      replyHistory
    );
  }

  if (!state.painConfirmed) {
    return pickFreshReply(
      [
        "Got it. Where is the bigger leak right now: enquiries, call pickup, or bookings?",
        "Understood. Which part is slipping more: getting leads, converting them, or following up fast enough?",
        "I am checking the bottleneck that is costing bookings. What feels weakest today?",
      ],
      replyHistory
    );
  }

  if (state.objectionCategories.length > 0) {
    return pickFreshReply(
      [
        "Fair point. I am not talking about more noise, just the exact gap I am seeing. Should I keep it to one practical observation?",
        "Makes sense. I can keep it to the one leak that matters most if you'd like.",
      ],
      replyHistory
    );
  }

  if (!state.decisionMakerConfirmed) {
    return pickFreshReply(
      [
        "Makes sense. Who usually looks after this side for you right now: doctor, manager, or front desk?",
        "Quick check: who usually handles bookings and follow-up there?",
      ],
      replyHistory
    );
  }

  if (state.requestedNextStep === "call") {
    return pickFreshReply(
      [
        "Makes sense. A quick 10-minute look will be cleaner than a long text. Would this evening or tomorrow afternoon be easier?",
        "Happy to keep it short. Would today or tomorrow work better for a quick call?",
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
          `First thing I'd tighten is ${topIssue}. I'd start by ${nextBestAction}. If you want, I'll show you the second leak after that.`,
          `The clearest leak I see is ${topIssue}. First move I'd make is ${nextBestAction}. Want the next one too?`,
        ],
        replyHistory
      );
    }

    if (topIssue) {
      return pickFreshReply(
        [
          `First thing I'd look at is ${topIssue}. That is usually where warm intent slips. Want the second leak too?`,
          `The first leak is ${topIssue}. Fix that first and the thread usually gets cleaner. Want the next one?`,
        ],
        replyHistory
      );
    }

    if (firstPain) {
      return pickFreshReply(
        [
          `First leak I'd check is ${firstPain}. That usually costs replies before the team even gets a proper shot. Want the next one too?`,
          `I'd start with ${firstPain}. Clean that up first, then look at the second drop-off point. Want me to keep going?`,
        ],
        replyHistory
      );
    }
  }

  return pickFreshReply(
    [
      "Understood. If you're open, I can show you the exact leak points I'd look at first and keep it very practical.",
      "If helpful, I can start with the one thing most likely causing drop-off and keep it tight.",
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

  return [
    "You are a premium WhatsApp sales closer for clinics and medspas.",
    "You sound calm, credible, commercially mature, and human.",
    "Never say you are an AI.",
    "Never use markdown, bullet formatting, or long paragraphs.",
    "Reply in 1-3 short WhatsApp-style chat bubbles worth of text.",
    "Do not pitch too early.",
    "Do not explain tech unless asked.",
    "Focus on response speed, follow-up discipline, missed bookings, and operational leakage.",
    "If the lead asks for a human, pricing, pilot details, or seems uncomfortable, keep it short and move to handoff.",
    "Do not invent case studies, guaranteed ROI, or direct founder contact if it is not verified.",
    "Sound like a real operator, not a support bot or assistant.",
    "Do not start every message with 'Got it', 'Makes sense', or 'Understood'.",
    "Keep the tone composed, direct, slightly sharp, and trustworthy.",
    "Use one concrete question or one concrete observation per reply.",
    "Do not repeat your last suggested reply. If a similar reply is already in the recent transcript, vary the wording and ask a different diagnostic question.",
    `Current stage: ${state.stage}`,
    `Priority: ${state.priority}`,
    `Pain points: ${state.painPoints.join(", ") || "not yet confirmed"}`,
    `Objections: ${state.objectionCategories.join(", ") || "none"}`,
    `Requested next step: ${state.requestedNextStep ?? "unknown"}`,
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
  const inferredNextStep =
    classification.requestedNextStep ||
    (lastAssistantOfferedProof(messages) &&
    /\b(yes|yeah|yup|ok|okay|sure|show|share|tell me|go on)\b/i.test(
      incomingText
    )
      ? "details"
      : null);

  const nextState: WhatsAppAgentState = {
    ...currentState,
    leadChannels: [
      ...currentState.leadChannels,
      ...classification.leadChannels,
    ],
    painPoints: [...currentState.painPoints, ...classification.painPoints],
    objectionCategories: [
      ...currentState.objectionCategories,
      ...classification.objectionCategories,
    ],
    requestedNextStep:
      inferredNextStep ?? currentState.requestedNextStep,
    lastIntent: incomingText.trim() || currentState.lastIntent,
    decisionMakerRole:
      currentState.decisionMakerRole ?? classification.roleHint ?? null,
    decisionMakerConfirmed:
      currentState.decisionMakerConfirmed ||
      Boolean(
        classification.roleHint &&
          ["founder", "doctor", "manager"].includes(classification.roleHint)
      ),
    painConfirmed:
      currentState.painConfirmed ||
      classification.painPoints.length > 0 ||
      /\b(yes|yeah|true|correct|exactly|sometimes)\b/i.test(incomingText),
    paymentInterest:
      currentState.paymentInterest || classification.paymentInterest,
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
