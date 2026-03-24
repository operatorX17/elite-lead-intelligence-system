import { createHmac, timingSafeEqual } from "node:crypto";
import { getWhatsAppConfig } from "./config";

export type SendWhatsAppResult = {
  status: "draft" | "sent" | "failed";
  providerMessageId: string | null;
  error: string | null;
  skipped?: boolean;
};

export type ParsedInboundWhatsAppMessage = {
  contactPhone: string;
  contactName: string;
  body: string;
  providerMessageId: string | null;
  receivedAt: Date;
};

export type ParsedWhatsAppStatusUpdate = {
  providerMessageId: string;
  status: "sent" | "delivered" | "read" | "failed";
};

type WhatsAppChangeValue = {
  contacts?: Array<{
    profile?: {
      name?: string;
    };
    wa_id?: string;
  }>;
  messages?: Array<{
    from?: string;
    id?: string;
    timestamp?: string;
    type?: string;
    text?: {
      body?: string;
    };
  }>;
  statuses?: Array<{
    id?: string;
    status?: string;
  }>;
};

export async function sendWhatsAppTextMessage({
  to,
  body,
}: {
  to: string;
  body: string;
}): Promise<SendWhatsAppResult> {
  const config = getWhatsAppConfig();

  if (!config.outboundReady || !config.phoneNumberId || !config.accessToken) {
    return {
      status: "draft",
      providerMessageId: null,
      error: "WhatsApp Cloud API is not configured",
      skipped: true,
    };
  }

  const response = await fetch(
    `https://graph.facebook.com/${config.graphApiVersion}/${config.phoneNumberId}/messages`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${config.accessToken}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        messaging_product: "whatsapp",
        to,
        type: "text",
        text: {
          body,
          preview_url: false,
        },
      }),
    }
  );

  const payload = await response.json().catch(() => null);

  if (!response.ok) {
    const errorMessage =
      payload?.error?.message ??
      payload?.message ??
      "WhatsApp API request failed";

    return {
      status: "failed",
      providerMessageId: null,
      error: errorMessage,
    };
  }

  return {
    status: "sent",
    providerMessageId: payload?.messages?.[0]?.id ?? null,
    error: null,
  };
}

export function verifyWhatsAppWebhookSignature({
  rawBody,
  signatureHeader,
}: {
  rawBody: string;
  signatureHeader: string | null;
}) {
  const config = getWhatsAppConfig();

  if (!config.appSecret) {
    return true;
  }

  if (!signatureHeader?.startsWith("sha256=")) {
    return false;
  }

  const expectedSignature = createHmac("sha256", config.appSecret)
    .update(rawBody)
    .digest("hex");

  const expectedBuffer = Buffer.from(expectedSignature, "hex");
  const actualBuffer = Buffer.from(signatureHeader.replace("sha256=", ""), "hex");

  if (expectedBuffer.length !== actualBuffer.length) {
    return false;
  }

  return timingSafeEqual(expectedBuffer, actualBuffer);
}

export function parseWhatsAppWebhookPayload(payload: unknown): {
  messages: ParsedInboundWhatsAppMessage[];
  statuses: ParsedWhatsAppStatusUpdate[];
} {
  const messages: ParsedInboundWhatsAppMessage[] = [];
  const statuses: ParsedWhatsAppStatusUpdate[] = [];

  if (!payload || typeof payload !== "object") {
    return { messages, statuses };
  }

  const entries = Array.isArray((payload as { entry?: unknown }).entry)
    ? ((payload as { entry: Array<{ changes?: Array<{ value?: WhatsAppChangeValue }> }> }).entry)
    : [];

  for (const entry of entries) {
    const changes = Array.isArray(entry.changes) ? entry.changes : [];

    for (const change of changes) {
      const value = change.value;

      if (!value) {
        continue;
      }

      const contact = value.contacts?.[0];
      const contactName = contact?.profile?.name ?? contact?.wa_id ?? "Lead";

      for (const inboundMessage of value.messages ?? []) {
        const rawBody =
          inboundMessage.type === "text"
            ? inboundMessage.text?.body ?? ""
            : `[${inboundMessage.type ?? "message"}]`;

        const body = rawBody.trim();

        if (!body || !inboundMessage.from) {
          continue;
        }

        messages.push({
          contactPhone: inboundMessage.from,
          contactName,
          body,
          providerMessageId: inboundMessage.id ?? null,
          receivedAt: inboundMessage.timestamp
            ? new Date(Number(inboundMessage.timestamp) * 1000)
            : new Date(),
        });
      }

      for (const statusEvent of value.statuses ?? []) {
        if (
          !statusEvent.id ||
          !statusEvent.status ||
          !["sent", "delivered", "read", "failed"].includes(statusEvent.status)
        ) {
          continue;
        }

        statuses.push({
          providerMessageId: statusEvent.id,
          status: statusEvent.status as ParsedWhatsAppStatusUpdate["status"],
        });
      }
    }
  }

  return { messages, statuses };
}
