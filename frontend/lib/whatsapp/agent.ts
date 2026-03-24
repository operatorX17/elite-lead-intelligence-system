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
  type WhatsAppLinkedLeadContext,
  type WhatsAppAgentState,
} from "@/lib/whatsapp/state";

const WHATSAPP_FAST_MODEL =
  process.env.WHATSAPP_FAST_MODEL?.trim() || "openai/gpt-4o";

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

function isTemplateLikeReply(reply: string) {
  const normalized = normalizeReplyFingerprint(reply);
  if (!normalized) {
    return true;
  }

  const wordCount = normalized.split(/\s+/).filter(Boolean).length;
  if (wordCount < 7) {
    return true;
  }

  return [
    /^(got it|understood|makes sense)\b/i,
    /\bif you want\b/i,
    /\bi can (show|share) (you|that|them)\b/i,
    /\bfirst place i'?d check\b/i,
    /\bfirst thing i'?d look at\b/i,
    /\bquick check\b/i,
    /\bexact leak\b/i,
  ].some((pattern) => pattern.test(normalized));
}

function buildReplyPrompt({
  conversation,
  incomingText,
  state,
  messages,
  leadContext,
  recentReplies,
}: {
  conversation: WhatsAppConversation;
  incomingText: string;
  state: WhatsAppAgentState;
  messages: WhatsAppMessage[];
  leadContext: WhatsAppLinkedLeadContext | null;
  recentReplies: string[];
}) {
  const transcript = messages
    .slice(-6)
    .map((message) => `${message.authorLabel}: ${message.body}`)
    .join("\n");

  return [
    `Contact: ${conversation.contactName} (${conversation.contactPhone})`,
    `Current stage: ${state.stage}`,
    `Current priority: ${state.priority}`,
    `Memory summary: ${state.summary ?? "none"}`,
    `Next best move: ${state.nextBestMove ?? "none"}`,
    `Requested next step: ${state.requestedNextStep ?? "unknown"}`,
    `Pain points: ${state.painPoints.join(", ") || "none"}`,
    `Objections: ${state.objectionCategories.join(", ") || "none"}`,
    `Last suggested reply: ${state.lastSuggestedReply ?? "none"}`,
    `Recent assistant replies: ${recentReplies.join(" | ") || "none"}`,
    leadContext?.companyName ? `Linked clinic: ${leadContext.companyName}` : null,
    leadContext?.topIssue ? `Top issue: ${leadContext.topIssue}` : null,
    leadContext?.nextBestAction
      ? `Recommended next action: ${leadContext.nextBestAction}`
      : null,
    leadContext?.decisionMakerName
      ? `Decision maker: ${leadContext.decisionMakerName} (${leadContext.decisionMakerRole || "unknown role"})`
      : null,
    `Recent transcript:\n${transcript || "No prior transcript"}`,
    `Latest inbound message: ${incomingText}`,
    "Write the next WhatsApp reply only.",
    "Make it sound like a real operator who knows the thread.",
  ]
    .filter(Boolean)
    .join("\n");
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
  let replyText: string | null = null;

  if (
    process.env.OPENROUTER_API_KEY &&
    !nextState.optOut &&
    !nextState.handoffRecommended
  ) {
    try {
      const generateReply = (system: string) =>
        Promise.race([
          generateText({
            model: getLanguageModel(WHATSAPP_FAST_MODEL || DEFAULT_CHAT_MODEL),
            abortSignal: abortSignal ?? undefined,
            temperature: 0.5,
            maxOutputTokens: 150,
            system,
            prompt: buildReplyPrompt({
              conversation,
              incomingText,
              state: nextState,
              messages,
              leadContext: conversation.leadContext ?? null,
              recentReplies,
            }),
          }),
          new Promise<never>((_, reject) =>
            setTimeout(
              () => reject(new Error("WhatsApp reply generation timed out")),
              WHATSAPP_REPLY_TIMEOUT_MS
            )
          ),
        ]);

      const system = buildWhatsAppSystemPrompt({
        conversation,
        state: nextState,
        messages,
        leadContext: conversation.leadContext ?? null,
      });

      const result = await generateReply(system);
      const normalized = normalizeBotReply(result.text);

      if (
        normalized &&
        !isRepeatedReply(normalized, [nextState.lastSuggestedReply, ...recentReplies]) &&
        !isTemplateLikeReply(normalized)
      ) {
        replyText = normalized;
      } else {
        const strictSystem = [
          system,
          "Hard rule: do not sound templated or canned.",
          "Start from the thread memory and answer with one concrete observation or one concrete question.",
          "Avoid these phrases: got it, understood, makes sense, if you want, I can show you, first place I'd check, quick check.",
        ].join("\n");

        const strictResult = await Promise.race([
          generateText({
            model: getLanguageModel(WHATSAPP_FAST_MODEL || DEFAULT_CHAT_MODEL),
            abortSignal: abortSignal ?? undefined,
            temperature: 0.65,
            maxOutputTokens: 150,
            system: strictSystem,
            prompt: buildReplyPrompt({
              conversation,
              incomingText,
              state: nextState,
              messages,
              leadContext: conversation.leadContext ?? null,
              recentReplies,
            }),
          }),
          new Promise<never>((_, reject) =>
            setTimeout(
              () => reject(new Error("WhatsApp reply regeneration timed out")),
              WHATSAPP_REPLY_TIMEOUT_MS
            )
          ),
        ]);

        const strictNormalized = normalizeBotReply(strictResult.text);
        if (
          strictNormalized &&
          !isRepeatedReply(strictNormalized, [nextState.lastSuggestedReply, ...recentReplies]) &&
          !isTemplateLikeReply(strictNormalized)
        ) {
          replyText = strictNormalized;
        }
      }
    } catch (error) {
      console.error("[whatsapp:agent] Falling back to deterministic reply", error);
    }
  }

  if (!replyText) {
    replyText = buildWhatsAppFallbackReply(
      nextState,
      recentReplies,
      conversation.leadContext ?? null
    );
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
