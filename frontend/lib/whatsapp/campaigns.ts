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
