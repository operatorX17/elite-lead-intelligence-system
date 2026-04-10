import type {
  WhatsAppConversation,
  WhatsAppMessage,
} from "@/lib/db/schema";
import {
  requestLeadAwareWhatsAppReply,
  requestProspectAwareWhatsAppReply,
} from "@/lib/whatsapp/lead-context";
import {
  normalizeWhatsAppAgentState,
  type WhatsAppAgentState,
} from "@/lib/whatsapp/state";

const WHATSAPP_BACKEND_REPLY_TIMEOUT_MS = 3500;
const WHATSAPP_PROSPECT_BACKEND_REPLY_TIMEOUT_MS = 2200;

function normalizeBotReply(reply: string) {
  return reply
    .replace(/\*\*/g, "")
    .replace(/^[`'"]+|[`'"]+$/g, "")
    .replace(/\r/g, "")
    .replace(/[ \t]+/g, " ")
    .replace(/\n{3,}/g, "\n\n")
    .trim()
    .slice(0, 420);
}

function extractBackendReplyText(
  response:
    | Awaited<ReturnType<typeof requestLeadAwareWhatsAppReply>>
    | Awaited<ReturnType<typeof requestProspectAwareWhatsAppReply>>
) {
  const leadAwareResponse =
    "response" in response ? response.response : undefined;

  if (typeof leadAwareResponse === "string") {
    return leadAwareResponse.trim();
  }

  const responseMessage = leadAwareResponse?.message?.trim();
  if (responseMessage) {
    return responseMessage;
  }

  const aiResponse = response.ai_response?.trim();
  if (aiResponse) {
    return aiResponse;
  }

  const transcriptReply = String(
    response.conversation?.entities?.last_ai_response ?? ""
  ).trim();
  return transcriptReply || null;
}

export type WhatsAppReplyPlan = {
  nextState: WhatsAppAgentState;
  replyText: string;
  shouldSendReply: boolean;
  shouldSwitchToHuman: boolean;
};

function buildRailwayAgentStatePatch({
  currentState,
  replyText,
  needsEscalation,
  escalationReason,
}: {
  currentState: WhatsAppAgentState;
  replyText: string;
  needsEscalation?: boolean | null;
  escalationReason?: string | null;
}) {
  return normalizeWhatsAppAgentState({
    ...currentState,
    lastSuggestedReply: replyText,
    handoffRecommended: Boolean(needsEscalation),
    handoffReason: escalationReason || (needsEscalation ? "Railway escalation requested" : null),
    updatedAt: new Date().toISOString(),
  });
}

export async function generateWhatsAppReplyPlan({
  conversation,
  messages,
  incomingText,
}: {
  conversation: WhatsAppConversation;
  messages: WhatsAppMessage[];
  incomingText: string;
  abortSignal?: AbortSignal | null;
}): Promise<WhatsAppReplyPlan> {
  const currentState = normalizeWhatsAppAgentState(conversation.agentState);
  const backendAbortController = new AbortController();
  const backendTimeoutMs = conversation.linkedLeadId
    ? WHATSAPP_BACKEND_REPLY_TIMEOUT_MS
    : WHATSAPP_PROSPECT_BACKEND_REPLY_TIMEOUT_MS;
  const backendTimeout = setTimeout(
    () => backendAbortController.abort(),
    backendTimeoutMs
  );

  try {
    const backendResponse = conversation.linkedLeadId
      ? await requestLeadAwareWhatsAppReply({
          leadId: conversation.linkedLeadId,
          incomingText,
          abortSignal: backendAbortController.signal,
        })
      : await requestProspectAwareWhatsAppReply({
          conversation,
          messages,
          incomingText,
          currentState,
          abortSignal: backendAbortController.signal,
        });

    const replyText = normalizeBotReply(
      extractBackendReplyText(backendResponse) || ""
    );

    if (!replyText) {
      const emptyReplyState = normalizeWhatsAppAgentState({
        ...currentState,
        handoffRecommended: true,
        handoffReason:
          "Railway conversation service returned no reply for this WhatsApp thread",
        nextBestMove:
          "Switch this thread to human handling or retry from Railway.",
        updatedAt: new Date().toISOString(),
      });

      return {
        nextState: emptyReplyState,
        replyText: "",
        shouldSendReply: false,
        shouldSwitchToHuman: true,
      };
    }

    const finalState = buildRailwayAgentStatePatch({
      currentState,
      replyText,
      needsEscalation: backendResponse.needs_escalation,
      escalationReason: backendResponse.escalation_reason || null,
    });

    return {
      nextState: finalState,
      replyText,
      shouldSendReply: conversation.mode === "bot",
      shouldSwitchToHuman: finalState.handoffRecommended,
    };
  } catch (error) {
    console.warn("[whatsapp:agent] Railway conversation reply failed", error);

    const unavailableState = normalizeWhatsAppAgentState({
      ...currentState,
      handoffRecommended: true,
      handoffReason:
        "Railway conversation service is unavailable for this WhatsApp thread",
      nextBestMove:
        "Keep the thread manual until the Railway sales agent is healthy again.",
      updatedAt: new Date().toISOString(),
    });

    return {
      nextState: unavailableState,
      replyText: "",
      shouldSendReply: false,
      shouldSwitchToHuman: true,
    };
  } finally {
    clearTimeout(backendTimeout);
  }
}
