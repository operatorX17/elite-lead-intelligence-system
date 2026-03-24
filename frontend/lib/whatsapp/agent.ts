import { generateText } from "ai";
import { DEFAULT_CHAT_MODEL } from "@/lib/ai/models";
import { getLanguageModel } from "@/lib/ai/providers";
import type {
  WhatsAppConversation,
  WhatsAppMessage,
} from "@/lib/db/schema";
import {
  buildWhatsAppFallbackReply,
  buildWhatsAppSystemPrompt,
  classifyInboundLeadMessage,
  deriveNextWhatsAppAgentState,
} from "@/lib/whatsapp/sales-playbook";
import {
  normalizeWhatsAppAgentState,
  type WhatsAppAgentState,
} from "@/lib/whatsapp/state";

const WHATSAPP_FAST_MODEL =
  process.env.WHATSAPP_FAST_MODEL?.trim() || "openai/gpt-4o-mini";

function normalizeBotReply(reply: string) {
  return reply
    .replace(/\*\*/g, "")
    .replace(/^[`'"]+|[`'"]+$/g, "")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 420);
}

function normalizeReplyFingerprint(value: string | null | undefined) {
  return String(value ?? "")
    .replace(/\s+/g, " ")
    .trim()
    .toLowerCase();
}

function getRecentAssistantReplies(messages: WhatsAppMessage[]) {
  return messages
    .filter(
      (message) =>
        message.direction === "outgoing" &&
        (message.authorType === "bot" || message.authorType === "human")
    )
    .slice(-4)
    .map((message) => message.body)
    .filter(Boolean);
}

function isRepeatedReply(
  reply: string,
  recentReplies: Array<string | null | undefined>
) {
  const fingerprint = normalizeReplyFingerprint(reply);
  if (!fingerprint) {
    return true;
  }

  return recentReplies.some(
    (recentReply) => normalizeReplyFingerprint(recentReply) === fingerprint
  );
}

export type WhatsAppReplyPlan = {
  classification: ReturnType<typeof classifyInboundLeadMessage>;
  nextState: WhatsAppAgentState;
  replyText: string;
  shouldSendReply: boolean;
  shouldSwitchToHuman: boolean;
};

export { classifyInboundLeadMessage };

const WHATSAPP_REPLY_TIMEOUT_MS = 4500;

export async function generateWhatsAppReplyPlan({
  conversation,
  messages,
  incomingText,
  abortSignal,
}: {
  conversation: WhatsAppConversation;
  messages: WhatsAppMessage[];
  incomingText: string;
  abortSignal?: AbortSignal | null;
}): Promise<WhatsAppReplyPlan> {
  const currentState = normalizeWhatsAppAgentState(conversation.agentState);
  const { classification, nextState } = deriveNextWhatsAppAgentState({
    conversation,
    messages,
    incomingText,
    currentState,
  });

  const recentReplies = getRecentAssistantReplies(messages);
  let replyText = buildWhatsAppFallbackReply(nextState, recentReplies);

  if (
    process.env.OPENROUTER_API_KEY &&
    !nextState.optOut &&
    !nextState.handoffRecommended
  ) {
    try {
      const result = await Promise.race([
        generateText({
          model: getLanguageModel(WHATSAPP_FAST_MODEL || DEFAULT_CHAT_MODEL),
          abortSignal: abortSignal ?? undefined,
          temperature: 0.35,
          maxOutputTokens: 120,
          system: buildWhatsAppSystemPrompt({
            conversation,
            state: nextState,
            messages,
            leadContext: conversation.leadContext ?? null,
          }),
          prompt: [
            `Contact: ${conversation.contactName} (${conversation.contactPhone})`,
            `Latest inbound message: ${incomingText}`,
            "Reply text:",
          ].join("\n"),
        }),
        new Promise<never>((_, reject) =>
          setTimeout(
            () => reject(new Error("WhatsApp reply generation timed out")),
            WHATSAPP_REPLY_TIMEOUT_MS
          )
        ),
      ]);

      const normalized = normalizeBotReply(result.text);
      if (normalized && !isRepeatedReply(normalized, [nextState.lastSuggestedReply, ...recentReplies])) {
        replyText = normalized;
      }
    } catch (error) {
      console.error("[whatsapp:agent] Falling back to deterministic reply", error);
    }
  }

  const finalState = normalizeWhatsAppAgentState({
    ...nextState,
    lastSuggestedReply: replyText,
  });

  const shouldSwitchToHuman = finalState.handoffRecommended;
  const shouldSendReply = conversation.mode === "bot";

  return {
    classification,
    nextState: finalState,
    replyText,
    shouldSendReply,
    shouldSwitchToHuman,
  };
}
