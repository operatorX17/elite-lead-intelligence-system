export type WhatsAppProvider = "twilio" | "meta" | "none";

export type WhatsAppPublicConfig = {
  provider: WhatsAppProvider;
  providerLabel: string;
  businessNumber: string | null;
  outboundReady: boolean;
  webhookReady: boolean;
  twilioConfigured: boolean;
  metaConfigured: boolean;
};

export type WhatsAppServerConfig = WhatsAppPublicConfig & {
  twilioAccountSid: string | null;
  twilioAuthToken: string | null;
  twilioPhoneNumber: string | null;
  twilioWhatsAppNumber: string | null;
  twilioStatusCallbackUrl: string | null;
  metaGraphApiVersion: string;
  metaPhoneNumberId: string | null;
  metaAccessToken: string | null;
  metaVerifyToken: string | null;
  metaAppSecret: string | null;
};

function normalizeUrl(value: string | null) {
  return value ? value.replace(/\/+$/, "") : null;
}

function cleanEnvValue(value: string | null | undefined) {
  if (!value) {
    return null;
  }

  return value
    .trim()
    .replace(/^"|"$/g, "")
    .replace(/\\r\\n/g, "")
    .replace(/\\n/g, "")
    .trim();
}

function buildPublicBaseUrl() {
  const directUrl = normalizeUrl(cleanEnvValue(process.env.NEXTAUTH_URL));
  if (directUrl) {
    return directUrl;
  }

  const appUrl = normalizeUrl(cleanEnvValue(process.env.APP_URL));
  if (appUrl) {
    return appUrl;
  }

  const vercelUrl = normalizeUrl(cleanEnvValue(process.env.VERCEL_URL));
  if (vercelUrl) {
    return vercelUrl.startsWith("http") ? vercelUrl : `https://${vercelUrl}`;
  }

  return null;
}

export function getWhatsAppConfig(): WhatsAppServerConfig {
  const twilioAccountSid = cleanEnvValue(process.env.TWILIO_ACCOUNT_SID);
  const twilioAuthToken = cleanEnvValue(process.env.TWILIO_AUTH_TOKEN);
  const twilioPhoneNumber = cleanEnvValue(process.env.TWILIO_PHONE_NUMBER);
  const twilioWhatsAppNumber = cleanEnvValue(process.env.TWILIO_WHATSAPP_NUMBER);

  const metaPhoneNumberId = cleanEnvValue(process.env.WHATSAPP_PHONE_NUMBER_ID);
  const metaAccessToken = cleanEnvValue(process.env.WHATSAPP_ACCESS_TOKEN);
  const metaVerifyToken = cleanEnvValue(
    process.env.WHATSAPP_WEBHOOK_VERIFY_TOKEN
  );
  const metaAppSecret = cleanEnvValue(process.env.WHATSAPP_APP_SECRET);

  const twilioSender = twilioWhatsAppNumber ?? twilioPhoneNumber ?? null;
  const businessNumber =
    cleanEnvValue(process.env.WHATSAPP_DISPLAY_NUMBER) ??
    cleanEnvValue(process.env.WHATSAPP_NUMBER) ??
    twilioSender ??
    null;

  const twilioConfigured = Boolean(twilioAccountSid && twilioAuthToken && twilioSender);
  const metaConfigured = Boolean(metaPhoneNumberId && metaAccessToken);

  const explicitProvider = (cleanEnvValue(process.env.WHATSAPP_PROVIDER) ?? "")
    .toLowerCase();

  let provider: WhatsAppProvider = "none";
  if (explicitProvider === "twilio" || explicitProvider === "meta") {
    provider = explicitProvider;
  } else if (twilioConfigured) {
    provider = "twilio";
  } else if (metaConfigured) {
    provider = "meta";
  }

  const publicBaseUrl = buildPublicBaseUrl();

  return {
    provider,
    providerLabel:
      provider === "twilio"
        ? "Twilio"
        : provider === "meta"
          ? "Meta Cloud API"
          : "WhatsApp",
    businessNumber,
    outboundReady:
      provider === "twilio"
        ? twilioConfigured
        : provider === "meta"
          ? metaConfigured
          : false,
    webhookReady:
      provider === "twilio"
        ? Boolean(twilioConfigured && publicBaseUrl)
        : provider === "meta"
          ? Boolean(metaConfigured && metaVerifyToken && metaAppSecret)
          : false,
    twilioConfigured,
    metaConfigured,
    twilioAccountSid,
    twilioAuthToken,
    twilioPhoneNumber,
    twilioWhatsAppNumber,
    twilioStatusCallbackUrl: publicBaseUrl
      ? `${publicBaseUrl}/api/whatsapp/webhook`
      : null,
    metaGraphApiVersion:
      cleanEnvValue(process.env.WHATSAPP_GRAPH_API_VERSION) ?? "v23.0",
    metaPhoneNumberId,
    metaAccessToken,
    metaVerifyToken,
    metaAppSecret,
  };
}

export function getWhatsAppPublicConfig(): WhatsAppPublicConfig {
  const {
    provider,
    providerLabel,
    businessNumber,
    outboundReady,
    webhookReady,
    twilioConfigured,
    metaConfigured,
  } = getWhatsAppConfig();

  return {
    provider,
    providerLabel,
    businessNumber,
    outboundReady,
    webhookReady,
    twilioConfigured,
    metaConfigured,
  };
}
