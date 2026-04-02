import "server-only";

import {
  countRecentOutgoingWhatsAppMessagesForContact,
  countRecentOutgoingWhatsAppMessagesGlobal,
  findRecentDuplicateOutgoingWhatsAppMessage,
  getLatestIncomingWhatsAppMessageAt,
  getWhatsAppConversationById,
  getWhatsAppConversationByPhone,
} from "@/lib/db/queries";

const MAX_MESSAGES_PER_USER_PER_HOUR = 3;
const MAX_GLOBAL_OUTBOUND_PER_MINUTE = 20;
const FREEFORM_WINDOW_MS = 24 * 60 * 60 * 1000;
const DUPLICATE_WINDOW_MS = 10 * 60 * 1000;
const RUNTIME_KILL_SWITCH_MS = 15 * 60 * 1000;

type RuntimeWhatsAppPolicyState = {
  killSwitchUntil: number | null;
  lastReason: string | null;
};

const runtimeState = globalThis as typeof globalThis & {
  __zraiWhatsAppPolicyState?: RuntimeWhatsAppPolicyState;
};

function getRuntimePolicyState() {
  if (!runtimeState.__zraiWhatsAppPolicyState) {
    runtimeState.__zraiWhatsAppPolicyState = {
      killSwitchUntil: null,
      lastReason: null,
    };
  }

  return runtimeState.__zraiWhatsAppPolicyState;
}

function normalizeBody(body: string) {
  return body.trim().replace(/\s+/g, " ");
}

function isManualKillSwitchEnabled() {
  const value = String(process.env.WHATSAPP_OUTBOUND_KILL_SWITCH ?? "").trim();
  return ["1", "true", "yes", "on"].includes(value.toLowerCase());
}

function tripRuntimeKillSwitch(reason: string) {
  const state = getRuntimePolicyState();
  state.killSwitchUntil = Date.now() + RUNTIME_KILL_SWITCH_MS;
  state.lastReason = reason;
}

function getRuntimeKillSwitchBlockReason() {
  const state = getRuntimePolicyState();
  if (!state.killSwitchUntil) {
    return null;
  }

  if (Date.now() >= state.killSwitchUntil) {
    state.killSwitchUntil = null;
    state.lastReason = null;
    return null;
  }

  return state.lastReason ?? "runtime_kill_switch_active";
}

export type GuardedWhatsAppMessageStyle = "freeform" | "template";

export type GuardedWhatsAppMessageDecision =
  | {
      allowed: true;
      conversationId: string;
      contactPhone: string;
      businessPhone: string | null;
    }
  | {
      allowed: false;
      reason:
        | "manual_kill_switch_active"
        | "runtime_kill_switch_active"
        | "conversation_not_found"
        | "message_body_required"
        | "duplicate_recently_sent"
        | "per_user_hour_limit"
        | "global_minute_limit"
        | "customer_service_window_closed";
      detail: string;
      status: number;
    };

export async function guardWhatsAppOutboundMessage(input: {
  conversationId?: string | null;
  contactPhone?: string | null;
  businessPhone?: string | null;
  body: string;
  messageStyle: GuardedWhatsAppMessageStyle;
}): Promise<GuardedWhatsAppMessageDecision> {
  const normalizedBody = normalizeBody(input.body);

  if (!normalizedBody) {
    return {
      allowed: false,
      reason: "message_body_required",
      detail: "Message body is required",
      status: 400,
    };
  }

  if (isManualKillSwitchEnabled()) {
    return {
      allowed: false,
      reason: "manual_kill_switch_active",
      detail: "WhatsApp outbound kill switch is enabled",
      status: 503,
    };
  }

  const runtimeKillReason = getRuntimeKillSwitchBlockReason();
  if (runtimeKillReason) {
    return {
      allowed: false,
      reason: "runtime_kill_switch_active",
      detail: `WhatsApp outbound runtime kill switch is active (${runtimeKillReason})`,
      status: 503,
    };
  }

  const conversation =
    (input.conversationId
      ? await getWhatsAppConversationById({ id: input.conversationId })
      : null) ||
    (input.contactPhone
      ? await getWhatsAppConversationByPhone({
          contactPhone: input.contactPhone,
          businessPhone: input.businessPhone,
        })
      : null);

  if (!conversation) {
    return {
      allowed: false,
      reason: "conversation_not_found",
      detail: "WhatsApp conversation not found for outbound policy check",
      status: 404,
    };
  }

  const now = new Date();
  const globalMessagesInLastMinute = await countRecentOutgoingWhatsAppMessagesGlobal({
    since: new Date(now.getTime() - 60_000),
  });

  if (globalMessagesInLastMinute >= MAX_GLOBAL_OUTBOUND_PER_MINUTE) {
    tripRuntimeKillSwitch("global_minute_limit");
    return {
      allowed: false,
      reason: "global_minute_limit",
      detail: "Global outbound rate limit reached",
      status: 429,
    };
  }

  const messagesForContactInLastHour =
    await countRecentOutgoingWhatsAppMessagesForContact({
      contactPhone: conversation.contactPhone,
      since: new Date(now.getTime() - 60 * 60_000),
    });

  if (messagesForContactInLastHour >= MAX_MESSAGES_PER_USER_PER_HOUR) {
    return {
      allowed: false,
      reason: "per_user_hour_limit",
      detail: "This contact already received the hourly message limit",
      status: 429,
    };
  }

  const recentDuplicate = await findRecentDuplicateOutgoingWhatsAppMessage({
    conversationId: conversation.id,
    body: normalizedBody,
    since: new Date(now.getTime() - DUPLICATE_WINDOW_MS),
  });

  if (recentDuplicate) {
    return {
      allowed: false,
      reason: "duplicate_recently_sent",
      detail: "Duplicate WhatsApp message blocked in short interval",
      status: 409,
    };
  }

  if (input.messageStyle === "freeform") {
    const latestInboundAt = await getLatestIncomingWhatsAppMessageAt({
      conversationId: conversation.id,
    });

    if (!latestInboundAt || now.getTime() - latestInboundAt.getTime() > FREEFORM_WINDOW_MS) {
      return {
        allowed: false,
        reason: "customer_service_window_closed",
        detail:
          "Free-form WhatsApp messages are only allowed inside the 24-hour customer service window",
        status: 409,
      };
    }
  }

  return {
    allowed: true,
    conversationId: conversation.id,
    contactPhone: conversation.contactPhone,
    businessPhone: conversation.businessPhone || null,
  };
}
