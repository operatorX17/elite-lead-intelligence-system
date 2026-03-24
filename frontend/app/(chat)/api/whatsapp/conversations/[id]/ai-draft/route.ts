import { auth } from "@/app/(auth)/auth";
import {
  getWhatsAppConversationById,
  getWhatsAppMessagesByConversationId,
  updateWhatsAppConversationAgentState,
  updateWhatsAppConversationLeadLink,
} from "@/lib/db/queries";
import { generateWhatsAppReplyPlan } from "@/lib/whatsapp/agent";
import {
  buildLeadAwareAgentStatePatch,
  requestLeadAwareWhatsAppReply,
  resolveLeadContextForWhatsAppThread,
} from "@/lib/whatsapp/lead-context";

export async function POST(
  _request: Request,
  context: { params: Promise<{ id: string }> }
) {
  const session = await auth();

  if (!session?.user) {
    return Response.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { id } = await context.params;
  let [conversation, messages] = await Promise.all([
    getWhatsAppConversationById({ id }),
    getWhatsAppMessagesByConversationId({ conversationId: id }),
  ]);

  if (!conversation) {
    return Response.json({ error: "Conversation not found" }, { status: 404 });
  }

  const latestInbound =
    [...messages]
      .reverse()
      .find((message) => message.authorType === "contact")?.body ??
    conversation.lastMessagePreview;

  if (!latestInbound?.trim()) {
    return Response.json(
      {
        error: "No recent inbound context available for an AI draft",
      },
      { status: 400 }
    );
  }

  if (!conversation.linkedLeadId) {
    try {
      const resolved = await resolveLeadContextForWhatsAppThread({
        contactPhone: conversation.contactPhone,
        contactName: conversation.contactName,
        userId: session.user.id,
      });
      if (resolved?.leadContext) {
        conversation =
          (await updateWhatsAppConversationLeadLink({
            id: conversation.id,
            linkedLeadId: resolved.leadContext.leadId,
            leadContext: resolved.leadContext,
          })) || conversation;
      }
    } catch (error) {
      console.warn("[whatsapp:ai-draft] Lead linking failed", error);
    }
  }

  let suggestedReply = conversation.agentState.lastSuggestedReply;
  let nextState = conversation.agentState;
  let backendConversationId = conversation.backendConversationId;

  if (conversation.linkedLeadId && !suggestedReply) {
    try {
      const backendReply = await requestLeadAwareWhatsAppReply({
        leadId: conversation.linkedLeadId,
        incomingText: latestInbound,
        userId: session.user.id,
      });
      suggestedReply =
        String(
          typeof backendReply.response === "string"
            ? backendReply.response
            : backendReply.response?.message ||
              backendReply.ai_response ||
            backendReply.conversation?.entities?.last_ai_response ||
            ""
        ).trim() || suggestedReply;
      backendConversationId =
        backendReply.conversation?.conversation_id || backendConversationId;
      nextState = buildLeadAwareAgentStatePatch({
        currentState: conversation.agentState,
        leadContext: conversation.leadContext,
        aiResponse: suggestedReply || "",
        conversation: backendReply.conversation,
        needsEscalation: backendReply.needs_escalation,
        escalationReason: backendReply.escalation_reason || null,
      });
    } catch (error) {
      console.warn("[whatsapp:ai-draft] Backend conversation draft failed", error);
    }
  }

  if (!suggestedReply) {
    const replyPlan = await generateWhatsAppReplyPlan({
      conversation,
      messages,
      incomingText: latestInbound,
    });
    suggestedReply = replyPlan.replyText;
    nextState = replyPlan.nextState;
  }

  const updatedConversation = await updateWhatsAppConversationAgentState({
    id,
    patch: nextState,
  });

  let linkedConversation = updatedConversation;
  if (conversation.linkedLeadId || backendConversationId) {
    linkedConversation =
      (await updateWhatsAppConversationLeadLink({
        id,
        linkedLeadId: conversation.linkedLeadId,
        backendConversationId,
        leadContext: conversation.leadContext,
      })) || updatedConversation;
  }

  return Response.json({
    conversation: linkedConversation,
    suggestedReply,
    stage: linkedConversation.agentState.stage,
    priority: linkedConversation.agentState.priority,
  });
}
