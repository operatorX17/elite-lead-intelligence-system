import type { WhatsAppAgentState } from "@/lib/whatsapp/state";

export const WHATSAPP_CAMPAIGN_STATUSES = [
  "draft",
  "active",
  "paused",
  "completed",
] as const;

export type WhatsAppCampaignStatus =
  (typeof WHATSAPP_CAMPAIGN_STATUSES)[number];

export const WHATSAPP_CAMPAIGN_MESSAGE_STYLES = [
  "template",
  "freeform",
] as const;

export type WhatsAppCampaignMessageStyle =
  (typeof WHATSAPP_CAMPAIGN_MESSAGE_STYLES)[number];

export const WHATSAPP_CAMPAIGN_RECIPIENT_STATUSES = [
  "draft",
  "approved",
  "rejected",
  "sent",
  "replied",
  "failed",
] as const;

export type WhatsAppCampaignRecipientStatus =
  (typeof WHATSAPP_CAMPAIGN_RECIPIENT_STATUSES)[number];

export type WhatsAppCampaignRecipientInput = {
  contactName: string;
  contactPhone: string;
  companyName: string | null;
};

export type WhatsAppCampaignTemplateVariables = Record<string, string>;

export type WhatsAppCampaignPreset = {
  id: string;
  label: string;
  angle: string;
  recommendedFor: string;
  description: string;
  templateName: string;
  messageStyle: WhatsAppCampaignMessageStyle;
  firstMessage: string;
  suggestedFollowUp: string;
  painPoints: string[];
  nextBestMove: string;
  summary: string;
};

export type WhatsAppCampaignRecipientRecord = {
  id: string;
  campaignId: string;
  conversationId: string | null;
  linkedLeadId: string | null;
  contactName: string;
  contactPhone: string;
  companyName: string | null;
  messageBody: string;
  status: WhatsAppCampaignRecipientStatus;
  providerMessageId: string | null;
  approvedByLabel: string | null;
  approvedAt: string | null;
  sentAt: string | null;
  repliedAt: string | null;
  errorText: string | null;
  notes: string | null;
  createdAt: string;
  updatedAt: string;
};

export type WhatsAppCampaignRecord = {
  id: string;
  name: string;
  status: WhatsAppCampaignStatus;
  messageStyle: WhatsAppCampaignMessageStyle;
  templateName: string | null;
  providerTemplateId: string | null;
  providerTemplateVariables: WhatsAppCampaignTemplateVariables | null;
  messageTemplate: string;
  createdByLabel: string;
  dailyLimit: number;
  waveSize: number;
  waveGapMinutes: number;
  nextWaveAt: string | null;
  lastWaveAt: string | null;
  notes: string | null;
  createdAt: string;
  updatedAt: string;
  recipients: WhatsAppCampaignRecipientRecord[];
  counts: {
    total: number;
    draft: number;
    approved: number;
    rejected: number;
    sent: number;
    replied: number;
    failed: number;
  };
};

export const WHATSAPP_CAMPAIGN_PRESETS: WhatsAppCampaignPreset[] = [
  {
    id: "curiosity_wave_1",
    label: "Curiosity opener",
    angle: "missed enquiries disappearing",
    recommendedFor: "first outbound touch",
    description:
      "Research-style opener that gets clinics talking about enquiry drop-off without feeling pitched.",
    templateName: "curiosity_wave_1",
    messageStyle: "template",
    firstMessage:
      "Quick question - when someone messages {{company_name}} but doesn't complete the booking, do they usually come back later or do they mostly disappear?",
    suggestedFollowUp:
      "Roughly how many WhatsApp enquiries do you get in a normal week?",
    painPoints: ["missed_follow_up", "booking_gap", "whatsapp_gap"],
    nextBestMove:
      "If they reply, quantify weekly WhatsApp enquiries, confirm drop-off, then move to a quick demo.",
    summary:
      "Outbound clinic SDR opener focused on WhatsApp enquiries disappearing before the booking is completed.",
  },
  {
    id: "call_only_booking_gap",
    label: "Call-only booking gap",
    angle: "patients pushed back to calling",
    recommendedFor: "clinics still forcing calls to book",
    description:
      "Highlights friction when patients must call instead of booking smoothly on WhatsApp.",
    templateName: "call_only_booking_gap",
    messageStyle: "template",
    firstMessage:
      "Quick one - is booking at {{company_name}} still mostly handled by phone call once someone enquires, or can patients actually get all the way to a confirmed slot on WhatsApp?",
    suggestedFollowUp:
      "When staff are busy, do some of those chats cool off before the call happens?",
    painPoints: ["booking_gap", "staff_dependency", "whatsapp_gap"],
    nextBestMove:
      "If they engage, stay on booking friction, staff handoff, and how many chats stall before a slot is confirmed.",
    summary:
      "Outbound clinic SDR opener focused on call-only booking friction and drop-off before appointment confirmation.",
  },
  {
    id: "follow_up_recovery",
    label: "Follow-up recovery",
    angle: "silent enquiries never re-engaged",
    recommendedFor: "follow-up heavy clinics and medspas",
    description:
      "Starts from the most common revenue loss: people enquire once, then vanish because nobody follows up properly.",
    templateName: "follow_up_recovery",
    messageStyle: "template",
    firstMessage:
      "When someone enquires at {{company_name}} and then goes quiet, does your team usually follow up properly or do most of those chats just fade out?",
    suggestedFollowUp:
      "If even a few of those were recovered each week, would that be meaningful on your side?",
    painPoints: ["missed_follow_up", "slow_response", "whatsapp_gap"],
    nextBestMove:
      "If they reply, quantify follow-up discipline, confirm how many enquiries fade out, then invite a quick walkthrough.",
    summary:
      "Outbound clinic SDR opener focused on silent enquiries that are never followed up and quietly disappear.",
  },
  {
    id: "aesthetic_consult_dropoff",
    label: "Aesthetic consult drop-off",
    angle: "skin and aesthetic consults cooling off",
    recommendedFor: "aesthetic, dermatology, skin clinics",
    description:
      "Aesthetic-specific opener that feels close to the actual consult-booking problem instead of generic automation talk.",
    templateName: "aesthetic_consult_dropoff",
    messageStyle: "template",
    firstMessage:
      "For skin and aesthetic consults at {{company_name}}, are most WhatsApp enquiries actually turning into booked consultations, or are some cooling off before the slot gets confirmed?",
    suggestedFollowUp:
      "Is the bigger issue slow first reply, follow-up, or patients dropping before payment and confirmation?",
    painPoints: ["booking_gap", "slow_response", "missed_follow_up"],
    nextBestMove:
      "If they reply, stay on aesthetic consult conversion, diagnose where the consult drop-off happens, then suggest a 3-minute demo.",
    summary:
      "Outbound clinic SDR opener for aesthetic and dermatology clinics focused on consults cooling off before booking confirmation.",
  },
];

export const DEFAULT_WHATSAPP_CAMPAIGN_PRESET =
  WHATSAPP_CAMPAIGN_PRESETS[0];

function normalizePhone(value: string) {
  return value.replace(/[^\d+]/g, "");
}

export function parseCampaignContactsInput(input: string) {
  const seenPhones = new Set<string>();
  const contacts: WhatsAppCampaignRecipientInput[] = [];

  for (const rawLine of input.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line) {
      continue;
    }

    const parts = line.includes("|")
      ? line.split("|").map((part) => part.trim())
      : line.includes("\t")
        ? line.split("\t").map((part) => part.trim())
        : [line];

    let contactName = "";
    let companyName: string | null = null;
    let phoneCandidate = "";

    if (parts.length >= 3) {
      [contactName, phoneCandidate, companyName] = parts;
    } else if (parts.length === 2) {
      const [first, second] = parts;
      if (/\d/.test(first) && !/\d/.test(second)) {
        phoneCandidate = first;
        contactName = second;
      } else if (!/\d/.test(first) && /\d/.test(second)) {
        contactName = first;
        phoneCandidate = second;
      } else {
        contactName = first;
        phoneCandidate = second;
      }
    } else {
      const match = line.match(/(\+?\d[\d\s()-]{7,}\d)/);
      if (!match) {
        continue;
      }
      phoneCandidate = match[1];
      const remainder = line.replace(match[1], "").trim().replace(/^[,|-]+/, "").trim();
      contactName = remainder || "Lead";
    }

    const normalizedPhone = normalizePhone(phoneCandidate);
    if (normalizedPhone.length < 8 || seenPhones.has(normalizedPhone)) {
      continue;
    }

    seenPhones.add(normalizedPhone);
    contacts.push({
      contactName: contactName || companyName || normalizedPhone,
      contactPhone: normalizedPhone,
      companyName: companyName || null,
    });
  }

  return contacts;
}

function firstNameFromContact(value: string) {
  const firstToken = value.trim().split(/\s+/).filter(Boolean)[0];
  return firstToken || value.trim() || "there";
}

export function getWhatsAppCampaignPresetById(
  presetId: string | null | undefined
) {
  const normalized = String(presetId ?? "").trim().toLowerCase();
  if (!normalized) {
    return null;
  }

  return (
    WHATSAPP_CAMPAIGN_PRESETS.find(
      (preset) =>
        preset.id.toLowerCase() === normalized ||
        preset.templateName.toLowerCase() === normalized
    ) ?? null
  );
}

export function parseCampaignTemplateVariablesInput(
  input: string | null | undefined
): WhatsAppCampaignTemplateVariables | null {
  const raw = String(input ?? "").trim();
  if (!raw) {
    return null;
  }

  try {
    const parsed = JSON.parse(raw) as Record<string, unknown>;
    const normalizedEntries = Object.entries(parsed)
      .map(([key, value]) => [String(key).trim(), String(value ?? "").trim()] as const)
      .filter(([key, value]) => Boolean(key) && Boolean(value));

    if (normalizedEntries.length === 0) {
      return null;
    }

    return Object.fromEntries(normalizedEntries);
  } catch {
    return null;
  }
}

export function stringifyCampaignTemplateVariables(
  value: WhatsAppCampaignTemplateVariables | null | undefined
) {
  if (!value || Object.keys(value).length === 0) {
    return "";
  }

  return JSON.stringify(value, null, 2);
}

export function buildOutreachCampaignStatePatch({
  presetId,
  companyName,
}: {
  presetId: string | null | undefined;
  companyName?: string | null;
}): Partial<WhatsAppAgentState> | null {
  const preset = getWhatsAppCampaignPresetById(presetId);
  if (!preset) {
    return null;
  }

  const clinicLabel = String(companyName ?? "").trim() || "the clinic";
  return {
    stage: "ENGAGED",
    priority: "high",
    confidence: 0.68,
    summary: `${preset.summary} Current clinic: ${clinicLabel}.`,
    painPoints: preset.painPoints,
    leadChannels: ["whatsapp", "outbound_whatsapp"],
    nextBestMove: preset.nextBestMove,
    lastIntent: "outbound_whatsapp",
    requestedNextStep: null,
    updatedAt: new Date().toISOString(),
  };
}

export function renderCampaignTemplateVariables({
  templateVariables,
  contactName,
  contactPhone,
  companyName,
  topIssue,
  decisionMakerName,
  city,
}: {
  templateVariables: WhatsAppCampaignTemplateVariables | null | undefined;
  contactName: string;
  contactPhone?: string | null;
  companyName?: string | null;
  topIssue?: string | null;
  decisionMakerName?: string | null;
  city?: string | null;
}) {
  if (!templateVariables || Object.keys(templateVariables).length === 0) {
    return null;
  }

  const entries = Object.entries(templateVariables)
    .map(([key, value]) => [
      key,
      renderCampaignMessageTemplate({
        template: value,
        contactName,
        contactPhone,
        companyName,
        topIssue,
        decisionMakerName,
        city,
      }).trim(),
    ] as const)
    .filter(([, value]) => Boolean(value));

  if (entries.length === 0) {
    return null;
  }

  return Object.fromEntries(entries);
}

export function renderCampaignMessageTemplate({
  template,
  contactName,
  contactPhone,
  companyName,
  topIssue,
  decisionMakerName,
  city,
}: {
  template: string;
  contactName: string;
  contactPhone?: string | null;
  companyName?: string | null;
  topIssue?: string | null;
  decisionMakerName?: string | null;
  city?: string | null;
}) {
  const replacements: Record<string, string> = {
    first_name: firstNameFromContact(contactName),
    full_name: contactName.trim() || "there",
    phone: String(contactPhone || "").trim(),
    company_name: String(companyName || "").trim(),
    top_issue: String(topIssue || "").trim(),
    decision_maker: String(decisionMakerName || "").trim(),
    city: String(city || "").trim(),
  };

  return template.replace(/\{\{\s*([a-z_]+)\s*\}\}/gi, (_match, key) => {
    const replacement = replacements[String(key).toLowerCase()];
    return replacement || "";
  });
}

export function summarizeCampaignCounts(
  recipients: Array<{ status: WhatsAppCampaignRecipientStatus }>
) {
  const counts = {
    total: recipients.length,
    draft: 0,
    approved: 0,
    rejected: 0,
    sent: 0,
    replied: 0,
    failed: 0,
  };

  for (const recipient of recipients) {
    counts[recipient.status] += 1;
  }

  return counts;
}
