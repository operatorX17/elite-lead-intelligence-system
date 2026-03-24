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
  buildLeadAwareAgentStatePatch,
  requestLeadAwareWhatsAppReply,
} from "@/lib/whatsapp/lead-context";
import {
  normalizeWhatsAppAgentState,
  type WhatsAppLinkedLeadContext,
  type WhatsAppAgentState,
} from "@/lib/whatsapp/state";

const WHATSAPP_FAST_MODEL =
  process.env.WHATSAPP_FAST_MODEL?.trim() || "openai/gpt-4o";
const WHATSAPP_BACKEND_REPLY_TIMEOUT_MS = 6000;

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
  if (wordCount < 5) {
    return true;
  }

  // Only reject obvious canned lines. Useful short operator replies should pass.
  return [
    /^(got it|understood|makes sense)(?:[.!]?\s*)?$/i,
    /^i(?:'|’)m looking at where bookings leak most(?:[.!]?\s*)?$/i,
    /^the first gap i(?:'|’)d check is\b/i,
    /^i(?:'|’)d start with the first few minutes after someone reaches out\b/i,
    /^i(?:'|’)d start with reply speed after the first enquiry\b/i,
  ].some((pattern) => pattern.test(normalized));
}

function extractBackendReplyText(
  response: Awaited<ReturnType<typeof requestLeadAwareWhatsAppReply>>
) {
  if (typeof response.response === "string") {
    return response.response.trim();
  }

  const responseMessage = response.response?.message?.trim();
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
  let effectiveNextState = nextState;

  if (conversation.linkedLeadId) {
    const backendAbortController = new AbortController();
    const backendTimeout = setTimeout(
      () => backendAbortController.abort(),
      WHATSAPP_BACKEND_REPLY_TIMEOUT_MS
    );

    try {
      const backendResponse = await requestLeadAwareWhatsAppReply({
        leadId: conversation.linkedLeadId,
        incomingText,
        abortSignal: backendAbortController.signal,
      });

      const backendReply = normalizeBotReply(
        extractBackendReplyText(backendResponse) || ""
      );

      if (
        backendReply &&
        !isRepeatedReply(backendReply, [nextState.lastSuggestedReply, ...recentReplies]) &&
        !isTemplateLikeReply(backendReply)
      ) {
        replyText = backendReply;
        effectiveNextState = buildLeadAwareAgentStatePatch({
          currentState,
          leadContext: conversation.leadContext ?? null,
          aiResponse: backendReply,
          conversation: backendResponse.conversation ?? null,
          needsEscalation: backendResponse.needs_escalation,
          escalationReason: backendResponse.escalation_reason || null,
        });
      }
    } catch (error) {
      console.warn("[whatsapp:agent] Backend conversation reply failed", error);
    } finally {
      clearTimeout(backendTimeout);
    }
  }

  if (
    !replyText &&
    process.env.OPENROUTER_API_KEY &&
    !effectiveNextState.optOut &&
    !effectiveNextState.handoffRecommended
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
              state: effectiveNextState,
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
        state: effectiveNextState,
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
              state: effectiveNextState,
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
      effectiveNextState,
      recentReplies,
      conversation.leadContext ?? null,
      incomingText
    );
  }

  const finalState = normalizeWhatsAppAgentState({
    ...effectiveNextState,
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
