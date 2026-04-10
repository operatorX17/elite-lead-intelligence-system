import "server-only";

import { ZRAI_BACKEND_ENDPOINTS } from "@/lib/zrai/constants";

function normalizeBody(body: string) {
  return body.trim().replace(/\s+/g, " ");
}

export type GuardedWhatsAppMessageStyle = "freeform" | "template";
export type GuardedWhatsAppAutomationKind = "manual" | "bot_reply" | "campaign";

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
        | "customer_service_window_closed"
        | "campaign_opt_in_required"
        | "automation_disclosure_required"
        | "automation_impersonation_risk";
      detail: string;
      status: number;
    };

export async function guardWhatsAppOutboundMessage(input: {
  conversationId?: string | null;
  contactPhone?: string | null;
  businessPhone?: string | null;
  body: string;
  messageStyle: GuardedWhatsAppMessageStyle;
  automationKind?: GuardedWhatsAppAutomationKind;
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

  try {
    const response = await fetch(ZRAI_BACKEND_ENDPOINTS.whatsappPolicyGuard, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        conversation_id: input.conversationId,
        contact_phone: input.contactPhone,
        business_phone: input.businessPhone,
        body: normalizedBody,
        message_style: input.messageStyle,
        automation_kind: input.automationKind ?? "manual",
      }),
    });

    const payload = (await response.json()) as GuardedWhatsAppMessageDecision;
    if (payload && "allowed" in payload) {
      return payload;
    }
  } catch (error) {
    console.error("[whatsapp:policy] Railway policy guard failed", error);
  }

  return {
    allowed: false,
    reason: "runtime_kill_switch_active",
    detail:
      "Railway WhatsApp policy guard is unavailable; outbound message blocked",
    status: 503,
  };
}
