import { getWhatsAppConfig } from "./config";
import {
  parseWhatsAppWebhookPayload as parseMetaWebhookPayload,
  sendWhatsAppTextMessage as sendMetaWhatsAppTextMessage,
  verifyWhatsAppWebhookSignature as verifyMetaWebhookSignature,
  type ParsedInboundWhatsAppMessage,
  type ParsedWhatsAppStatusUpdate,
  type SendWhatsAppResult,
} from "./meta";
import {
  parseTwilioWebhookPayload,
  sendTwilioWhatsAppTextMessage,
  verifyTwilioWebhookSignature,
} from "./twilio";

export type {
  ParsedInboundWhatsAppMessage,
  ParsedWhatsAppStatusUpdate,
  SendWhatsAppResult,
};

export async function sendWhatsAppTextMessage(input: {
  to: string;
  body: string;
  from?: string | null;
  contentSid?: string | null;
  contentVariables?: Record<string, string> | null;
}): Promise<SendWhatsAppResult> {
  const config = getWhatsAppConfig();

  if (config.provider === "twilio") {
    return sendTwilioWhatsAppTextMessage(input);
  }

  return sendMetaWhatsAppTextMessage(input);
}

export function verifyWhatsAppWebhookSignature(input: {
  requestUrl: string;
  rawBody: string;
  signatureHeader: string | null;
}) {
  const config = getWhatsAppConfig();

  if (config.provider === "twilio") {
    return verifyTwilioWebhookSignature(input);
  }

  return verifyMetaWebhookSignature({
    rawBody: input.rawBody,
    signatureHeader: input.signatureHeader,
  });
}

export function parseWhatsAppWebhookPayload(input: {
  rawBody: string;
  parsedJson: unknown;
}): {
  messages: ParsedInboundWhatsAppMessage[];
  statuses: ParsedWhatsAppStatusUpdate[];
} {
  const config = getWhatsAppConfig();

  if (config.provider === "twilio") {
    return parseTwilioWebhookPayload(input.rawBody);
  }

  return parseMetaWebhookPayload(input.parsedJson);
}
