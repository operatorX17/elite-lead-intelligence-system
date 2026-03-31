import { z } from "zod";
import { auth } from "@/app/(auth)/auth";
import {
  appendWhatsAppMessage,
  getWhatsAppConversationById,
  getWhatsAppMessagesByConversationId,
  updateWhatsAppConversationAgentState,
  updateWhatsAppConversationLeadLink,
} from "@/lib/db/queries";
import {
  resolveLeadContextForWhatsAppThread,
  syncWhatsAppMessageToLeadMemory,
} from "@/lib/whatsapp/lead-context";
import { sendWhatsAppTextMessage } from "@/lib/whatsapp/provider";
import { isWhatsAppSandboxLead } from "@/lib/whatsapp/sandbox";

const sendMessageSchema = z.object({
  body: z.string().trim().min(1, "Message body is required"),
});

export async function GET(
  _request: Request,
  context: { params: Promise<{ id: string }> }
) {
  const session = await auth();

  if (!session?.user) {
    return Response.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { id } = await context.params;
  const [conversation, messages] = await Promise.all([
    getWhatsAppConversationById({ id }),
    getWhatsAppMessagesByConversationId({ conversationId: id }),
  ]);

  if (!conversation) {
    return Response.json({ error: "Conversation not found" }, { status: 404 });
  }

  return Response.json({
    conversation,
    messages,
  });
}

export async function POST(
  request: Request,
  context: { params: Promise<{ id: string }> }
) {
  const session = await auth();

  if (!session?.user) {
    return Response.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { id } = await context.params;
  let conversation = await getWhatsAppConversationById({ id });

  if (!conversation) {
    return Response.json({ error: "Conversation not found" }, { status: 404 });
  }

  const rawBody = await request.json().catch(() => null);
  const payload = sendMessageSchema.safeParse(rawBody);

  if (!payload.success) {
    return Response.json(
      {
        error: payload.error.flatten(),
      },
      { status: 400 }
    );
  }

  const delivery = await sendWhatsAppTextMessage({
    to: conversation.contactPhone,
    body: payload.data.body,
  });

  const message = await appendWhatsAppMessage({
    conversationId: conversation.id,
    direction: "outgoing",
    authorType: "human",
    authorLabel: session.user.email ?? session.user.name ?? "Human operator",
    body: payload.data.body,
    providerMessageId: delivery.providerMessageId,
    status: delivery.status,
    errorText: delivery.error,
  });

  await updateWhatsAppConversationAgentState({
    id: conversation.id,
    patch: {
      handoffRecommended: false,
      handoffReason: null,
      lastSuggestedReply: null,
      nextBestMove: "Wait for the reply, then continue the diagnosis.",
      updatedAt: new Date().toISOString(),
    },
  });

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
      console.warn("[whatsapp:send] Lead linking failed", error);
    }
  }

  if (
    conversation.linkedLeadId &&
    !isWhatsAppSandboxLead({
      linkedLeadId: conversation.linkedLeadId,
      leadContext: conversation.leadContext,
    })
  ) {
    try {
      const syncResult = await syncWhatsAppMessageToLeadMemory({
        leadId: conversation.linkedLeadId,
        message: payload.data.body,
        role: "human",
        conversationId: conversation.backendConversationId,
        userId: session.user.id,
      });

      if (syncResult?.conversation?.conversation_id) {
        conversation =
          (await updateWhatsAppConversationLeadLink({
            id: conversation.id,
            linkedLeadId: conversation.linkedLeadId,
            backendConversationId: syncResult.conversation.conversation_id,
            leadContext: conversation.leadContext,
          })) || conversation;
      }
    } catch (error) {
      console.warn("[whatsapp:send] Backend memory sync failed", error);
    }
  }

  return Response.json({
    message,
    delivery,
    conversation,
  });
}
