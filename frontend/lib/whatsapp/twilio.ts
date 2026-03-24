import twilio from "twilio";
import { getWhatsAppConfig } from "./config";
import type {
  ParsedInboundWhatsAppMessage,
  ParsedWhatsAppStatusUpdate,
  SendWhatsAppResult,
} from "./meta";

function normalizeWhatsAppAddress(value: string) {
  const trimmed = value.trim();
  if (trimmed.toLowerCase().startsWith("whatsapp:")) {
    return trimmed;
  }
  return `whatsapp:${trimmed}`;
}

function stripWhatsAppPrefix(value: string | null | undefined) {
  return String(value ?? "")
    .replace(/^whatsapp:/i, "")
    .trim();
}

export async function sendTwilioWhatsAppTextMessage({
  to,
  body,
}: {
  to: string;
  body: string;
}): Promise<SendWhatsAppResult> {
  const config = getWhatsAppConfig();
  const sender = config.twilioWhatsAppNumber ?? config.twilioPhoneNumber;

  if (
    config.provider !== "twilio" ||
    !config.twilioAccountSid ||
    !config.twilioAuthToken ||
    !sender
  ) {
    return {
      status: "draft",
      providerMessageId: null,
      error: "Twilio WhatsApp is not configured",
      skipped: true,
    };
  }

  const payload = new URLSearchParams();
  payload.set("To", normalizeWhatsAppAddress(to));
  payload.set("From", normalizeWhatsAppAddress(sender));
  payload.set("Body", body);
  if (config.twilioStatusCallbackUrl) {
    payload.set("StatusCallback", config.twilioStatusCallbackUrl);
  }

  const auth = Buffer.from(
    `${config.twilioAccountSid}:${config.twilioAuthToken}`
  ).toString("base64");

  const response = await fetch(
    `https://api.twilio.com/2010-04-01/Accounts/${config.twilioAccountSid}/Messages.json`,
    {
      method: "POST",
      headers: {
        Authorization: `Basic ${auth}`,
        "Content-Type": "application/x-www-form-urlencoded",
      },
      body: payload,
    }
  );

  const data = await response.json().catch(() => null);
  if (!response.ok) {
    return {
      status: "failed",
      providerMessageId: null,
      error:
        data?.message ??
        data?.detail ??
        data?.error_message ??
        "Twilio API request failed",
    };
  }

  const twilioStatus = String(data?.status ?? "").toLowerCase();
  const status: SendWhatsAppResult["status"] =
    twilioStatus === "queued" || twilioStatus === "accepted"
      ? "sent"
      : twilioStatus === "sent" || twilioStatus === "delivered" || twilioStatus === "read"
        ? "sent"
        : twilioStatus === "failed" || twilioStatus === "undelivered"
          ? "failed"
          : "sent";

  return {
    status,
    providerMessageId: data?.sid ?? null,
    error: data?.error_message ?? null,
  };
}

export function verifyTwilioWebhookSignature({
  requestUrl,
  rawBody,
  signatureHeader,
}: {
  requestUrl: string;
  rawBody: string;
  signatureHeader: string | null;
}) {
  const config = getWhatsAppConfig();

  if (config.provider !== "twilio" || !config.twilioAuthToken) {
    return true;
  }

  if (!signatureHeader) {
    return false;
  }

  const params = Object.fromEntries(new URLSearchParams(rawBody).entries());
  const candidateUrls = Array.from(
    new Set(
      [
        requestUrl,
        requestUrl.split("?")[0],
        config.twilioStatusCallbackUrl,
      ].filter((value): value is string => Boolean(value))
    )
  );

  return candidateUrls.some((candidateUrl) =>
    twilio.validateRequest(
      config.twilioAuthToken as string,
      signatureHeader,
      candidateUrl,
      params
    )
  );
}

function mapTwilioStatus(
  value: string | null | undefined
): ParsedWhatsAppStatusUpdate["status"] | null {
  const normalized = String(value ?? "").toLowerCase();
  if (normalized === "sent" || normalized === "delivered" || normalized === "read") {
    return normalized;
  }
  if (
    normalized === "failed" ||
    normalized === "undelivered" ||
    normalized === "canceled"
  ) {
    return "failed";
  }
  return null;
}

export function parseTwilioWebhookPayload(rawBody: string): {
  messages: ParsedInboundWhatsAppMessage[];
  statuses: ParsedWhatsAppStatusUpdate[];
} {
  const params = new URLSearchParams(rawBody);
  const messages: ParsedInboundWhatsAppMessage[] = [];
  const statuses: ParsedWhatsAppStatusUpdate[] = [];

  const messageSid = params.get("MessageSid");
  const from = stripWhatsAppPrefix(params.get("From"));
  const body = (params.get("Body") ?? "").trim();
  const profileName = params.get("ProfileName")?.trim() || from || "Lead";
  const rawStatus = params.get("MessageStatus") ?? params.get("SmsStatus");
  const status = mapTwilioStatus(rawStatus);

  if (messageSid && status) {
    statuses.push({
      providerMessageId: messageSid,
      status,
    });
  }

  const hasInboundMessage =
    Boolean(messageSid && from) &&
    (body.length > 0 || Number(params.get("NumMedia") ?? "0") > 0) &&
    !status;

  if (hasInboundMessage) {
    messages.push({
      contactPhone: from,
      contactName: profileName,
      body: body || "[media]",
      providerMessageId: messageSid,
      receivedAt: new Date(),
    });
  }

  return { messages, statuses };
}
