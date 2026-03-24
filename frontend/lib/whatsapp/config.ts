export type WhatsAppPublicConfig = {
  businessNumber: string | null;
  phoneNumberIdConfigured: boolean;
  accessTokenConfigured: boolean;
  verifyTokenConfigured: boolean;
  appSecretConfigured: boolean;
  outboundReady: boolean;
};

type WhatsAppServerConfig = WhatsAppPublicConfig & {
  graphApiVersion: string;
  phoneNumberId: string | null;
  accessToken: string | null;
  verifyToken: string | null;
  appSecret: string | null;
};

export function getWhatsAppConfig(): WhatsAppServerConfig {
  const phoneNumberId = process.env.WHATSAPP_PHONE_NUMBER_ID ?? null;
  const accessToken = process.env.WHATSAPP_ACCESS_TOKEN ?? null;
  const verifyToken = process.env.WHATSAPP_WEBHOOK_VERIFY_TOKEN ?? null;
  const appSecret = process.env.WHATSAPP_APP_SECRET ?? null;
  const businessNumber =
    process.env.WHATSAPP_DISPLAY_NUMBER ?? process.env.WHATSAPP_NUMBER ?? null;

  return {
    graphApiVersion: process.env.WHATSAPP_GRAPH_API_VERSION ?? "v23.0",
    businessNumber,
    phoneNumberId,
    accessToken,
    verifyToken,
    appSecret,
    phoneNumberIdConfigured: Boolean(phoneNumberId),
    accessTokenConfigured: Boolean(accessToken),
    verifyTokenConfigured: Boolean(verifyToken),
    appSecretConfigured: Boolean(appSecret),
    outboundReady: Boolean(phoneNumberId && accessToken),
  };
}

export function getWhatsAppPublicConfig(): WhatsAppPublicConfig {
  const {
    businessNumber,
    phoneNumberIdConfigured,
    accessTokenConfigured,
    verifyTokenConfigured,
    appSecretConfigured,
    outboundReady,
  } = getWhatsAppConfig();

  return {
    businessNumber,
    phoneNumberIdConfigured,
    accessTokenConfigured,
    verifyTokenConfigured,
    appSecretConfigured,
    outboundReady,
  };
}
