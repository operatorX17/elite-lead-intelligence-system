import {
  appendWhatsAppMessage,
  getWhatsAppConversationById,
  getWhatsAppMessagesByConversationId,
  updateWhatsAppConversationAgentState,
  updateWhatsAppConversationLeadLink,
  updateWhatsAppConversationMode,
  updateWhatsAppConversationStatus,
  updateWhatsAppMessageStatusByProviderId,
  upsertWhatsAppConversationFromInbound,
} from "@/lib/db/queries";
import { generateWhatsAppReplyPlan } from "@/lib/whatsapp/agent";
import {
  buildLeadAwareAgentStatePatch,
  requestLeadAwareWhatsAppReply,
  resolveLeadContextForWhatsAppThread,
} from "@/lib/whatsapp/lead-context";
import { getWhatsAppConfig } from "@/lib/whatsapp/config";
import {
  parseWhatsAppWebhookPayload,
  sendWhatsAppTextMessage,
  verifyWhatsAppWebhookSignature,
} from "@/lib/whatsapp/meta";

export async function GET(request: Request) {
  const config = getWhatsAppConfig();
  const { searchParams } = new URL(request.url);
  const mode = searchParams.get("hub.mode");
  const challenge = searchParams.get("hub.challenge");
  const verifyToken = searchParams.get("hub.verify_token");

  if (
    mode === "subscribe" &&
    challenge &&
    config.verifyToken &&
    verifyToken === config.verifyToken
  ) {
    return new Response(challenge, { status: 200 });
  }

  return new Response("Verification failed", { status: 403 });
}

export async function POST(request: Request) {
  const rawBody = await request.text();

  if (
    !verifyWhatsAppWebhookSignature({
      rawBody,
      signatureHeader: request.headers.get("x-hub-signature-256"),
    })
  ) {
    return Response.json({ error: "Invalid webhook signature" }, { status: 401 });
  }

  let payload: unknown = {};

  try {
    payload = rawBody ? JSON.parse(rawBody) : {};
  } catch (_error) {
    return Response.json({ error: "Invalid JSON payload" }, { status: 400 });
  }
  const { messages, statuses } = parseWhatsAppWebhookPayload(payload);

  for (const statusEvent of statuses) {
    try {
      await updateWhatsAppMessageStatusByProviderId({
        providerMessageId: statusEvent.providerMessageId,
        status: statusEvent.status,
      });
    } catch (error) {
      console.error("[whatsapp:webhook] Failed to process status event", error);
    }
  }

  for (const inboundMessage of messages) {
    try {
      let conversation = await upsertWhatsAppConversationFromInbound({
        contactName: inboundMessage.contactName,
        contactPhone: inboundMessage.contactPhone,
        body: inboundMessage.body,
        receivedAt: inboundMessage.receivedAt,
      });

      await appendWhatsAppMessage({
        conversationId: conversation.id,
        direction: "incoming",
        authorType: "contact",
        authorLabel: conversation.contactName,
        body: inboundMessage.body,
        providerMessageId: inboundMessage.providerMessageId,
        status: "received",
        createdAt: inboundMessage.receivedAt,
      });

      let latestConversation = await getWhatsAppConversationById({
        id: conversation.id,
      });

      if (!latestConversation) {
        continue;
      }

      if (!latestConversation.linkedLeadId) {
        try {
          const resolved = await resolveLeadContextForWhatsAppThread({
            contactPhone: latestConversation.contactPhone,
            contactName: latestConversation.contactName,
          });
          if (resolved?.leadContext) {
            latestConversation =
              (await updateWhatsAppConversationLeadLink({
                id: latestConversation.id,
                linkedLeadId: resolved.leadContext.leadId,
                leadContext: resolved.leadContext,
              })) || latestConversation;
          }
        } catch (error) {
          console.error("[whatsapp:webhook] Lead linking failed", error);
        }
      }

      const conversationMessages = await getWhatsAppMessagesByConversationId({
        conversationId: latestConversation.id,
      });

      if (latestConversation.linkedLeadId) {
        try {
          const backendReply = await requestLeadAwareWhatsAppReply({
            leadId: latestConversation.linkedLeadId,
            incomingText: inboundMessage.body,
          });

          const aiResponse =
            String(backendReply.response?.message || "").trim() || "";
          const nextState = buildLeadAwareAgentStatePatch({
            currentState: latestConversation.agentState,
            leadContext: latestConversation.leadContext,
            aiResponse,
            conversation: backendReply.conversation,
            needsEscalation: backendReply.needs_escalation,
            escalationReason: backendReply.escalation_reason || null,
          });

          let conversationWithState = await updateWhatsAppConversationAgentState({
            id: latestConversation.id,
            patch: nextState,
          });

          if (
            latestConversation.linkedLeadId &&
            backendReply.conversation?.conversation_id
          ) {
            conversationWithState =
              (await updateWhatsAppConversationLeadLink({
                id: latestConversation.id,
                linkedLeadId: latestConversation.linkedLeadId,
                backendConversationId:
                  backendReply.conversation.conversation_id,
                leadContext: latestConversation.leadContext,
              })) || conversationWithState;
          }

          if (nextState.optOut) {
            await updateWhatsAppConversationStatus({
              id: latestConversation.id,
              status: "closed",
            });
            continue;
          }

          if (backendReply.needs_escalation) {
            await updateWhatsAppConversationMode({
              id: latestConversation.id,
              mode: "human",
              assignedOperatorLabel: latestConversation.assignedOperatorLabel,
            });
          }

          const shouldSendReply =
            latestConversation.mode === "bot" &&
            !backendReply.needs_escalation &&
            Boolean(aiResponse);

          if (!shouldSendReply) {
            continue;
          }

          const delivery = await sendWhatsAppTextMessage({
            to: latestConversation.contactPhone,
            body: aiResponse,
          });

          await appendWhatsAppMessage({
            conversationId: latestConversation.id,
            direction: "outgoing",
            authorType: "bot",
            authorLabel: "ZRAI Bot",
            body: aiResponse,
            providerMessageId: delivery.providerMessageId,
            status: delivery.status,
            errorText: delivery.error,
          });

          if (conversationWithState?.linkedLeadId) {
            try {
              await updateWhatsAppConversationLeadLink({
                id: latestConversation.id,
                linkedLeadId: conversationWithState.linkedLeadId,
                backendConversationId:
                  backendReply.conversation?.conversation_id ||
                  conversationWithState.backendConversationId,
                leadContext: conversationWithState.leadContext,
              });
            } catch (error) {
              console.error("[whatsapp:webhook] Failed to persist backend conversation id", error);
            }
          }

          continue;
        } catch (error) {
          console.error("[whatsapp:webhook] Lead-aware reply failed, falling back", error);
        }
      }

      const replyPlan = await generateWhatsAppReplyPlan({
        conversation: latestConversation,
        messages: conversationMessages,
        incomingText: inboundMessage.body,
      });

      const conversationWithState = await updateWhatsAppConversationAgentState({
        id: latestConversation.id,
        patch: replyPlan.nextState,
      });

      if (replyPlan.nextState.optOut) {
        await updateWhatsAppConversationStatus({
          id: latestConversation.id,
          status: "closed",
        });
      }

      if (replyPlan.shouldSwitchToHuman) {
        await updateWhatsAppConversationMode({
          id: latestConversation.id,
          mode: "human",
          assignedOperatorLabel: latestConversation.assignedOperatorLabel,
        });
      }

      if (!replyPlan.shouldSendReply) {
        continue;
      }

      const delivery = await sendWhatsAppTextMessage({
        to: latestConversation.contactPhone,
        body: replyPlan.replyText,
      });

      await appendWhatsAppMessage({
        conversationId: latestConversation.id,
        direction: "outgoing",
        authorType: "bot",
        authorLabel: "ZRAI Bot",
        body: replyPlan.replyText,
        providerMessageId: delivery.providerMessageId,
        status: delivery.status,
        errorText: delivery.error,
      });

      if (conversationWithState?.mode === "human") {
        await updateWhatsAppConversationAgentState({
          id: latestConversation.id,
          patch: {
            lastSuggestedReply: replyPlan.replyText,
          },
        });
      }
    } catch (error) {
      console.error("[whatsapp:webhook] Failed to process inbound message", error);
    }
  }

  return Response.json({ received: true });
}
