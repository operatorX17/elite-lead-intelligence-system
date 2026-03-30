import postgres from "postgres";
import {
  type WhatsAppCampaignMessageStyle,
  type WhatsAppCampaignRecipientInput,
  type WhatsAppCampaignRecipientRecord,
  type WhatsAppCampaignRecipientStatus,
  type WhatsAppCampaignRecord,
  type WhatsAppCampaignStatus,
  type WhatsAppCampaignTemplateVariables,
  renderCampaignMessageTemplate,
  summarizeCampaignCounts,
} from "@/lib/whatsapp/campaigns";
import { generateUUID } from "../utils";

const client = postgres(process.env.POSTGRES_URL!);

type CampaignMemoryStore = {
  campaigns: Map<string, WhatsAppCampaignRecord>;
  recipients: Map<string, WhatsAppCampaignRecipientRecord>;
};

const globalCampaignStore = globalThis as typeof globalThis & {
  __zraiWhatsAppCampaignStore?: CampaignMemoryStore;
  __zraiWhatsAppCampaignMemoryOnly?: boolean;
  __zraiWhatsAppCampaignTablesReady?: boolean;
};

function isMemoryDbEnabled() {
  return (
    process.env.ZRAI_IN_MEMORY_DB === "true" ||
    globalCampaignStore.__zraiWhatsAppCampaignMemoryOnly === true
  );
}

function enableRuntimeMemoryDb() {
  globalCampaignStore.__zraiWhatsAppCampaignMemoryOnly = true;
}

let memoryStore = globalCampaignStore.__zraiWhatsAppCampaignStore;
if (!memoryStore) {
  memoryStore = {
    campaigns: new Map<string, WhatsAppCampaignRecord>(),
    recipients: new Map<string, WhatsAppCampaignRecipientRecord>(),
  };
  globalCampaignStore.__zraiWhatsAppCampaignStore = memoryStore;
}
const campaignMemoryStore = memoryStore as CampaignMemoryStore;

function toIsoString(value: Date | string | null | undefined) {
  if (!value) {
    return null;
  }
  return (value instanceof Date ? value : new Date(value)).toISOString();
}

function toDate(value: Date | string | null | undefined) {
  return value ? new Date(value) : null;
}

async function ensureCampaignTables() {
  if (isMemoryDbEnabled() || globalCampaignStore.__zraiWhatsAppCampaignTablesReady) {
    return;
  }

  try {
    await client.unsafe(`
      CREATE TABLE IF NOT EXISTS "WhatsAppCampaign" (
        "id" uuid PRIMARY KEY,
        "createdAt" timestamp NOT NULL,
        "updatedAt" timestamp NOT NULL,
        "name" text NOT NULL,
        "status" varchar(24) NOT NULL,
        "messageStyle" varchar(24) NOT NULL,
        "templateName" text,
        "providerTemplateId" text,
        "providerTemplateVariables" jsonb,
        "messageTemplate" text NOT NULL,
        "createdByLabel" text NOT NULL,
        "dailyLimit" integer NOT NULL DEFAULT 20,
        "waveSize" integer NOT NULL DEFAULT 10,
        "waveGapMinutes" integer NOT NULL DEFAULT 30,
        "nextWaveAt" timestamp NULL,
        "lastWaveAt" timestamp NULL,
        "notes" text NULL
      );

      CREATE TABLE IF NOT EXISTS "WhatsAppCampaignRecipient" (
        "id" uuid PRIMARY KEY,
        "campaignId" uuid NOT NULL REFERENCES "WhatsAppCampaign"("id") ON DELETE CASCADE,
        "conversationId" uuid NULL,
        "linkedLeadId" text NULL,
        "contactName" text NOT NULL,
        "contactPhone" varchar(32) NOT NULL,
        "companyName" text NULL,
        "messageBody" text NOT NULL,
        "status" varchar(24) NOT NULL,
        "providerMessageId" text NULL,
        "approvedByLabel" text NULL,
        "approvedAt" timestamp NULL,
        "sentAt" timestamp NULL,
        "repliedAt" timestamp NULL,
        "errorText" text NULL,
        "notes" text NULL,
        "createdAt" timestamp NOT NULL,
        "updatedAt" timestamp NOT NULL
      );

      CREATE INDEX IF NOT EXISTS "whatsapp_campaign_updated_idx"
      ON "WhatsAppCampaign" ("updatedAt" DESC);

      CREATE INDEX IF NOT EXISTS "whatsapp_campaign_recipient_campaign_idx"
      ON "WhatsAppCampaignRecipient" ("campaignId");

      CREATE INDEX IF NOT EXISTS "whatsapp_campaign_recipient_phone_idx"
      ON "WhatsAppCampaignRecipient" ("contactPhone");
    `);

    await client.unsafe(`
      ALTER TABLE "WhatsAppCampaign"
      ADD COLUMN IF NOT EXISTS "providerTemplateId" text;

      ALTER TABLE "WhatsAppCampaign"
      ADD COLUMN IF NOT EXISTS "providerTemplateVariables" jsonb;
    `);

    globalCampaignStore.__zraiWhatsAppCampaignTablesReady = true;
  } catch (_error) {
    enableRuntimeMemoryDb();
  }
}

function hydrateCampaign(record: any): Omit<WhatsAppCampaignRecord, "recipients" | "counts"> {
  return {
    id: String(record.id),
    name: String(record.name),
    status: record.status as WhatsAppCampaignStatus,
    messageStyle: record.messageStyle as WhatsAppCampaignMessageStyle,
    templateName: record.templateName ?? null,
    providerTemplateId: record.providerTemplateId ?? null,
    providerTemplateVariables:
      (record.providerTemplateVariables as WhatsAppCampaignTemplateVariables | null) ?? null,
    messageTemplate: String(record.messageTemplate),
    createdByLabel: String(record.createdByLabel),
    dailyLimit: Number(record.dailyLimit ?? 20),
    waveSize: Number(record.waveSize ?? 10),
    waveGapMinutes: Number(record.waveGapMinutes ?? 30),
    nextWaveAt: toIsoString(record.nextWaveAt),
    lastWaveAt: toIsoString(record.lastWaveAt),
    notes: record.notes ?? null,
    createdAt: new Date(record.createdAt).toISOString(),
    updatedAt: new Date(record.updatedAt).toISOString(),
  };
}

function hydrateRecipient(record: any): WhatsAppCampaignRecipientRecord {
  return {
    id: String(record.id),
    campaignId: String(record.campaignId),
    conversationId: record.conversationId ?? null,
    linkedLeadId: record.linkedLeadId ?? null,
    contactName: String(record.contactName),
    contactPhone: String(record.contactPhone),
    companyName: record.companyName ?? null,
    messageBody: String(record.messageBody),
    status: record.status as WhatsAppCampaignRecipientStatus,
    providerMessageId: record.providerMessageId ?? null,
    approvedByLabel: record.approvedByLabel ?? null,
    approvedAt: toIsoString(record.approvedAt),
    sentAt: toIsoString(record.sentAt),
    repliedAt: toIsoString(record.repliedAt),
    errorText: record.errorText ?? null,
    notes: record.notes ?? null,
    createdAt: new Date(record.createdAt).toISOString(),
    updatedAt: new Date(record.updatedAt).toISOString(),
  };
}

function joinCampaignsWithRecipients({
  campaigns,
  recipients,
}: {
  campaigns: Array<Omit<WhatsAppCampaignRecord, "recipients" | "counts">>;
  recipients: WhatsAppCampaignRecipientRecord[];
}) {
  const recipientsByCampaign = new Map<string, WhatsAppCampaignRecipientRecord[]>();
  for (const recipient of recipients) {
    const bucket = recipientsByCampaign.get(recipient.campaignId) ?? [];
    bucket.push(recipient);
    recipientsByCampaign.set(recipient.campaignId, bucket);
  }

  return campaigns.map((campaign) => {
    const campaignRecipients = (recipientsByCampaign.get(campaign.id) ?? []).sort(
      (a, b) => new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime()
    );
    return {
      ...campaign,
      recipients: campaignRecipients,
      counts: summarizeCampaignCounts(campaignRecipients),
    } satisfies WhatsAppCampaignRecord;
  });
}

export async function listWhatsAppCampaigns() {
  if (isMemoryDbEnabled()) {
    return joinCampaignsWithRecipients({
      campaigns: Array.from(campaignMemoryStore.campaigns.values()).sort(
        (a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime()
      ),
      recipients: Array.from(campaignMemoryStore.recipients.values()),
    });
  }

  await ensureCampaignTables();
  if (isMemoryDbEnabled()) {
    return listWhatsAppCampaigns();
  }

  try {
    const [campaignRows, recipientRows] = await Promise.all([
      client<any[]>`SELECT * FROM "WhatsAppCampaign" ORDER BY "updatedAt" DESC`,
      client<any[]>`SELECT * FROM "WhatsAppCampaignRecipient" ORDER BY "createdAt" ASC`,
    ]);

    return joinCampaignsWithRecipients({
      campaigns: campaignRows.map(hydrateCampaign),
      recipients: recipientRows.map(hydrateRecipient),
    });
  } catch (_error) {
    enableRuntimeMemoryDb();
    return listWhatsAppCampaigns();
  }
}

export async function getWhatsAppCampaignById({ id }: { id: string }) {
  const campaigns = await listWhatsAppCampaigns();
  return campaigns.find((campaign) => campaign.id === id) ?? null;
}

export async function createWhatsAppCampaign({
  name,
  messageStyle,
  templateName,
  providerTemplateId,
  providerTemplateVariables,
  messageTemplate,
  createdByLabel,
  dailyLimit,
  waveSize,
  waveGapMinutes,
  notes,
  recipients,
}: {
  name: string;
  messageStyle: WhatsAppCampaignMessageStyle;
  templateName?: string | null;
  providerTemplateId?: string | null;
  providerTemplateVariables?: WhatsAppCampaignTemplateVariables | null;
  messageTemplate: string;
  createdByLabel: string;
  dailyLimit: number;
  waveSize: number;
  waveGapMinutes: number;
  notes?: string | null;
  recipients: Array<
    WhatsAppCampaignRecipientInput & {
      linkedLeadId?: string | null;
      conversationId?: string | null;
      renderedBody?: string | null;
    }
  >;
}) {
  const now = new Date();
  const campaignId = generateUUID();
  const campaignBase = {
    id: campaignId,
    name: name.trim(),
    status: "draft" as WhatsAppCampaignStatus,
    messageStyle,
    templateName: templateName?.trim() || null,
    providerTemplateId: providerTemplateId?.trim() || null,
    providerTemplateVariables:
      providerTemplateVariables && Object.keys(providerTemplateVariables).length > 0
        ? providerTemplateVariables
        : null,
    messageTemplate: messageTemplate.trim(),
    createdByLabel: createdByLabel.trim(),
    dailyLimit,
    waveSize,
    waveGapMinutes,
    nextWaveAt: null,
    lastWaveAt: null,
    notes: notes?.trim() || null,
    createdAt: now.toISOString(),
    updatedAt: now.toISOString(),
  };

  const recipientRecords: WhatsAppCampaignRecipientRecord[] = recipients.map(
    (recipient) => ({
      id: generateUUID(),
      campaignId,
      conversationId: recipient.conversationId ?? null,
      linkedLeadId: recipient.linkedLeadId ?? null,
      contactName: recipient.contactName.trim() || recipient.contactPhone,
      contactPhone: recipient.contactPhone.trim(),
      companyName: recipient.companyName?.trim() || null,
      messageBody:
        recipient.renderedBody?.trim() ||
        renderCampaignMessageTemplate({
          template: messageTemplate,
          contactName: recipient.contactName,
          contactPhone: recipient.contactPhone,
          companyName: recipient.companyName ?? null,
        }).trim(),
      status: "draft",
      providerMessageId: null,
      approvedByLabel: null,
      approvedAt: null,
      sentAt: null,
      repliedAt: null,
      errorText: null,
      notes: null,
      createdAt: now.toISOString(),
      updatedAt: now.toISOString(),
    })
  );

  const campaignRecord: WhatsAppCampaignRecord = {
    ...campaignBase,
    recipients: recipientRecords,
    counts: summarizeCampaignCounts(recipientRecords),
  };

  if (isMemoryDbEnabled()) {
    campaignMemoryStore.campaigns.set(campaignId, campaignRecord);
    for (const recipient of recipientRecords) {
      campaignMemoryStore.recipients.set(recipient.id, recipient);
    }
    return campaignRecord;
  }

  await ensureCampaignTables();
  if (isMemoryDbEnabled()) {
    return createWhatsAppCampaign({
      name,
      messageStyle,
      templateName,
      messageTemplate,
      createdByLabel,
      dailyLimit,
      waveSize,
      waveGapMinutes,
      notes,
      recipients,
    });
  }

  try {
    await client.begin(async (tx) => {
      await tx`
        INSERT INTO "WhatsAppCampaign"
          ("id", "createdAt", "updatedAt", "name", "status", "messageStyle", "templateName", "providerTemplateId", "providerTemplateVariables", "messageTemplate", "createdByLabel", "dailyLimit", "waveSize", "waveGapMinutes", "nextWaveAt", "lastWaveAt", "notes")
        VALUES
          (${campaignBase.id}::uuid, ${now}, ${now}, ${campaignBase.name}, ${campaignBase.status}, ${campaignBase.messageStyle}, ${campaignBase.templateName}, ${campaignBase.providerTemplateId}, ${campaignBase.providerTemplateVariables ? JSON.stringify(campaignBase.providerTemplateVariables) : null}::jsonb, ${campaignBase.messageTemplate}, ${campaignBase.createdByLabel}, ${campaignBase.dailyLimit}, ${campaignBase.waveSize}, ${campaignBase.waveGapMinutes}, ${null}, ${null}, ${campaignBase.notes})
      `;

      for (const recipient of recipientRecords) {
        await tx`
          INSERT INTO "WhatsAppCampaignRecipient"
            ("id", "campaignId", "conversationId", "linkedLeadId", "contactName", "contactPhone", "companyName", "messageBody", "status", "providerMessageId", "approvedByLabel", "approvedAt", "sentAt", "repliedAt", "errorText", "notes", "createdAt", "updatedAt")
          VALUES
            (${recipient.id}::uuid, ${campaignId}::uuid, ${recipient.conversationId}::uuid, ${recipient.linkedLeadId}, ${recipient.contactName}, ${recipient.contactPhone}, ${recipient.companyName}, ${recipient.messageBody}, ${recipient.status}, ${recipient.providerMessageId}, ${recipient.approvedByLabel}, ${null}, ${null}, ${null}, ${recipient.errorText}, ${recipient.notes}, ${now}, ${now})
        `;
      }
    });

    return campaignRecord;
  } catch (_error) {
    enableRuntimeMemoryDb();
    return createWhatsAppCampaign({
      name,
      messageStyle,
      templateName,
      providerTemplateId,
      providerTemplateVariables,
      messageTemplate,
      createdByLabel,
      dailyLimit,
      waveSize,
      waveGapMinutes,
      notes,
      recipients,
    });
  }
}

export async function updateWhatsAppCampaign({
  id,
  patch,
}: {
  id: string;
  patch: Partial<
    Pick<
      WhatsAppCampaignRecord,
      | "status"
      | "messageTemplate"
      | "templateName"
      | "providerTemplateId"
      | "providerTemplateVariables"
      | "notes"
      | "nextWaveAt"
      | "lastWaveAt"
      | "dailyLimit"
      | "waveSize"
      | "waveGapMinutes"
    >
  >;
}) {
  const currentCampaign = await getWhatsAppCampaignById({ id });
  if (!currentCampaign) {
    return null;
  }

  const nextCampaign: WhatsAppCampaignRecord = {
    ...currentCampaign,
    ...patch,
    nextWaveAt: patch.nextWaveAt === undefined ? currentCampaign.nextWaveAt : toIsoString(patch.nextWaveAt),
    lastWaveAt: patch.lastWaveAt === undefined ? currentCampaign.lastWaveAt : toIsoString(patch.lastWaveAt),
    updatedAt: new Date().toISOString(),
  };

  if (isMemoryDbEnabled()) {
    campaignMemoryStore.campaigns.set(id, nextCampaign);
    return nextCampaign;
  }

  await ensureCampaignTables();
  if (isMemoryDbEnabled()) {
    return updateWhatsAppCampaign({ id, patch });
  }

  try {
    await client`
      UPDATE "WhatsAppCampaign"
      SET
        "updatedAt" = ${new Date()},
        "status" = ${nextCampaign.status},
        "messageTemplate" = ${nextCampaign.messageTemplate},
        "templateName" = ${nextCampaign.templateName},
        "providerTemplateId" = ${nextCampaign.providerTemplateId},
        "providerTemplateVariables" = ${nextCampaign.providerTemplateVariables ? JSON.stringify(nextCampaign.providerTemplateVariables) : null}::jsonb,
        "notes" = ${nextCampaign.notes},
        "nextWaveAt" = ${toDate(nextCampaign.nextWaveAt)},
        "lastWaveAt" = ${toDate(nextCampaign.lastWaveAt)},
        "dailyLimit" = ${nextCampaign.dailyLimit},
        "waveSize" = ${nextCampaign.waveSize},
        "waveGapMinutes" = ${nextCampaign.waveGapMinutes}
      WHERE "id" = ${id}::uuid
    `;
    return nextCampaign;
  } catch (_error) {
    enableRuntimeMemoryDb();
    return updateWhatsAppCampaign({ id, patch });
  }
}

export async function updateWhatsAppCampaignRecipient({
  campaignId,
  recipientId,
  patch,
}: {
  campaignId: string;
  recipientId: string;
  patch: Partial<
    Pick<
      WhatsAppCampaignRecipientRecord,
      | "contactName"
      | "companyName"
      | "messageBody"
      | "status"
      | "approvedByLabel"
      | "approvedAt"
      | "sentAt"
      | "repliedAt"
      | "providerMessageId"
      | "errorText"
      | "notes"
      | "conversationId"
      | "linkedLeadId"
    >
  >;
}) {
  const currentCampaign = await getWhatsAppCampaignById({ id: campaignId });
  if (!currentCampaign) {
    return null;
  }

  const currentRecipient = currentCampaign.recipients.find(
    (recipient) => recipient.id === recipientId
  );
  if (!currentRecipient) {
    return null;
  }

  const nextRecipient: WhatsAppCampaignRecipientRecord = {
    ...currentRecipient,
    ...patch,
    approvedAt:
      patch.approvedAt === undefined ? currentRecipient.approvedAt : toIsoString(patch.approvedAt),
    sentAt: patch.sentAt === undefined ? currentRecipient.sentAt : toIsoString(patch.sentAt),
    repliedAt:
      patch.repliedAt === undefined ? currentRecipient.repliedAt : toIsoString(patch.repliedAt),
    updatedAt: new Date().toISOString(),
  };

  if (isMemoryDbEnabled()) {
    campaignMemoryStore.recipients.set(recipientId, nextRecipient);
    const nextCampaign: WhatsAppCampaignRecord = {
      ...currentCampaign,
      recipients: currentCampaign.recipients.map((recipient) =>
        recipient.id === recipientId ? nextRecipient : recipient
      ),
      counts: summarizeCampaignCounts(
        currentCampaign.recipients.map((recipient) =>
          recipient.id === recipientId ? nextRecipient : recipient
        )
      ),
      updatedAt: new Date().toISOString(),
    };
    campaignMemoryStore.campaigns.set(campaignId, nextCampaign);
    return nextRecipient;
  }

  await ensureCampaignTables();
  if (isMemoryDbEnabled()) {
    return updateWhatsAppCampaignRecipient({ campaignId, recipientId, patch });
  }

  try {
    await client.begin(async (tx) => {
      await tx`
        UPDATE "WhatsAppCampaignRecipient"
        SET
          "contactName" = ${nextRecipient.contactName},
          "companyName" = ${nextRecipient.companyName},
          "messageBody" = ${nextRecipient.messageBody},
          "status" = ${nextRecipient.status},
          "approvedByLabel" = ${nextRecipient.approvedByLabel},
          "approvedAt" = ${toDate(nextRecipient.approvedAt)},
          "sentAt" = ${toDate(nextRecipient.sentAt)},
          "repliedAt" = ${toDate(nextRecipient.repliedAt)},
          "providerMessageId" = ${nextRecipient.providerMessageId},
          "errorText" = ${nextRecipient.errorText},
          "notes" = ${nextRecipient.notes},
          "conversationId" = ${nextRecipient.conversationId}::uuid,
          "linkedLeadId" = ${nextRecipient.linkedLeadId},
          "updatedAt" = ${new Date()}
        WHERE "id" = ${recipientId}::uuid
      `;

      await tx`
        UPDATE "WhatsAppCampaign"
        SET "updatedAt" = ${new Date()}
        WHERE "id" = ${campaignId}::uuid
      `;
    });

    return nextRecipient;
  } catch (_error) {
    enableRuntimeMemoryDb();
    return updateWhatsAppCampaignRecipient({ campaignId, recipientId, patch });
  }
}

export async function approveWhatsAppCampaignRecipients({
  campaignId,
  approvedByLabel,
  recipientIds,
}: {
  campaignId: string;
  approvedByLabel: string;
  recipientIds?: string[];
}) {
  const campaign = await getWhatsAppCampaignById({ id: campaignId });
  if (!campaign) {
    return null;
  }

  const targetIds = new Set(
    (recipientIds?.length ? recipientIds : campaign.recipients.map((recipient) => recipient.id))
      .map((value) => value.trim())
      .filter(Boolean)
  );

  const approvedAt = new Date().toISOString();
  for (const recipient of campaign.recipients) {
    if (!targetIds.has(recipient.id) || recipient.status === "rejected") {
      continue;
    }

    await updateWhatsAppCampaignRecipient({
      campaignId,
      recipientId: recipient.id,
      patch: {
        status: "approved",
        approvedByLabel,
        approvedAt,
      },
    });
  }

  return updateWhatsAppCampaign({
    id: campaignId,
    patch: {
      status: "active",
      nextWaveAt: new Date().toISOString(),
    },
  });
}

export async function countWhatsAppCampaignRecipientsSentToday({
  campaignId,
  now = new Date(),
}: {
  campaignId: string;
  now?: Date;
}) {
  const startOfDay = new Date(now);
  startOfDay.setHours(0, 0, 0, 0);

  const campaign = await getWhatsAppCampaignById({ id: campaignId });
  if (!campaign) {
    return 0;
  }

  return campaign.recipients.filter((recipient) => {
    if (!recipient.sentAt) {
      return false;
    }
    return new Date(recipient.sentAt).getTime() >= startOfDay.getTime();
  }).length;
}

export async function markWhatsAppCampaignRecipientReplied({
  contactPhone,
  conversationId,
}: {
  contactPhone: string;
  conversationId?: string | null;
}) {
  const campaigns = await listWhatsAppCampaigns();
  const targetRecipient = campaigns
    .flatMap((campaign) => campaign.recipients)
    .filter(
      (recipient) =>
        recipient.contactPhone === contactPhone &&
        (recipient.status === "sent" || recipient.status === "approved")
    )
    .sort((a, b) => {
      const aTime = new Date(a.sentAt || a.updatedAt).getTime();
      const bTime = new Date(b.sentAt || b.updatedAt).getTime();
      return bTime - aTime;
    })
    .find(
      (recipient) => recipient.contactPhone === contactPhone
    );

  if (!targetRecipient) {
    return null;
  }

  return updateWhatsAppCampaignRecipient({
    campaignId: targetRecipient.campaignId,
    recipientId: targetRecipient.id,
    patch: {
      status: "replied",
      conversationId: conversationId ?? targetRecipient.conversationId,
      repliedAt: new Date().toISOString(),
    },
  });
}
