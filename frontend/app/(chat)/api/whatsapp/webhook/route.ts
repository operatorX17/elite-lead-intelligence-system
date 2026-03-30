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
import { markWhatsAppCampaignRecipientReplied } from "@/lib/db/whatsapp-campaigns";
import { generateWhatsAppReplyPlan } from "@/lib/whatsapp/agent";
import {
  resolveLeadContextForWhatsAppThread,
  syncWhatsAppMessageToLeadMemory,
} from "@/lib/whatsapp/lead-context";
import { getWhatsAppConfig } from "@/lib/whatsapp/config";
import {
  parseWhatsAppWebhookPayload,
  sendWhatsAppTextMessage,
  type ParsedInboundWhatsAppMessage,
  verifyWhatsAppWebhookSignature,
} from "@/lib/whatsapp/provider";
import { waitUntil } from "@vercel/functions";

const WHATSAPP_REPLY_BUDGET_MS = 8000;

function splitOutgoingWhatsAppReply(reply: string) {
  return reply
    .split(/\n{2,}/)
    .map((part) => part.trim())
    .filter(Boolean)
    .slice(0, 3);
}

async function processInboundWhatsAppMessage({
  conversationId,
  inboundMessage,
}: {
  conversationId: string;
  inboundMessage: ParsedInboundWhatsAppMessage;
}) {
  const replyAbortController = new AbortController();
  const replyTimeout = setTimeout(
    () => replyAbortController.abort(),
    WHATSAPP_REPLY_BUDGET_MS
  );

  try {
    let latestConversation = await getWhatsAppConversationById({
      id: conversationId,
    });

    if (!latestConversation) {
      return;
    }

    if (!latestConversation.linkedLeadId) {
      try {
        const resolved = await resolveLeadContextForWhatsAppThread({
          contactPhone: latestConversation.contactPhone,
          contactName: latestConversation.contactName,
          abortSignal: replyAbortController.signal,
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

    const replyPlan = await generateWhatsAppReplyPlan({
      conversation: latestConversation,
      messages: conversationMessages,
      incomingText: inboundMessage.body,
      abortSignal: replyAbortController.signal,
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
      return;
    }

    const splitReplyParts = splitOutgoingWhatsAppReply(replyPlan.replyText);
    const outgoingParts =
      splitReplyParts.length > 0 ? splitReplyParts : [replyPlan.replyText];

    for (const body of outgoingParts) {
      const delivery = await sendWhatsAppTextMessage({
        to: latestConversation.contactPhone,
        body,
      });

      await appendWhatsAppMessage({
        conversationId: latestConversation.id,
        direction: "outgoing",
        authorType: "bot",
        authorLabel: "ZRAI Bot",
        body,
        providerMessageId: delivery.providerMessageId,
        status: delivery.status,
        errorText: delivery.error,
      });
    }

    if (latestConversation.linkedLeadId) {
      try {
        const inboundSync = await syncWhatsAppMessageToLeadMemory({
          leadId: latestConversation.linkedLeadId,
          role: "prospect",
          message: inboundMessage.body,
          conversationId: conversationWithState?.backendConversationId,
          abortSignal: replyAbortController.signal,
        });

        const backendConversationId =
          inboundSync.conversation?.conversation_id ||
          conversationWithState?.backendConversationId ||
          null;

        if (backendConversationId) {
          await updateWhatsAppConversationLeadLink({
            id: latestConversation.id,
            linkedLeadId: latestConversation.linkedLeadId,
            backendConversationId,
            leadContext: conversationWithState?.leadContext || latestConversation.leadContext,
          });
        }

        await syncWhatsAppMessageToLeadMemory({
          leadId: latestConversation.linkedLeadId,
          role: "ai",
          message: replyPlan.replyText,
          conversationId: backendConversationId,
          abortSignal: replyAbortController.signal,
        });
      } catch (error) {
        console.error("[whatsapp:webhook] Failed to sync WhatsApp memory", error);
      }
    }
  } catch (error) {
    console.error("[whatsapp:webhook] Background inbound processing failed", error);
  } finally {
    clearTimeout(replyTimeout);
  }
}

export async function GET(request: Request) {
  const config = getWhatsAppConfig();

  if (config.provider === "twilio") {
    return Response.json(
      {
        provider: config.provider,
        webhookReady: config.webhookReady,
      },
      { status: 200 }
    );
  }

  const { searchParams } = new URL(request.url);
  const mode = searchParams.get("hub.mode");
  const challenge = searchParams.get("hub.challenge");
  const verifyToken = searchParams.get("hub.verify_token");

  if (
    mode === "subscribe" &&
    challenge &&
    config.metaVerifyToken &&
    verifyToken === config.metaVerifyToken
  ) {
    return new Response(challenge, { status: 200 });
  }

  return new Response("Verification failed", { status: 403 });
}

export async function POST(request: Request) {
  const rawBody = await request.text();
  const contentType = request.headers.get("content-type") ?? "";

  if (
    !verifyWhatsAppWebhookSignature({
      requestUrl: request.url,
      rawBody,
      signatureHeader:
        request.headers.get("x-twilio-signature") ??
        request.headers.get("x-hub-signature-256"),
    })
  ) {
    return Response.json({ error: "Invalid webhook signature" }, { status: 401 });
  }

  let payload: unknown = {};

  const shouldParseJson =
    contentType.toLowerCase().includes("application/json") ||
    rawBody.trim().startsWith("{") ||
    rawBody.trim().startsWith("[");

  if (shouldParseJson) {
    try {
      payload = rawBody ? JSON.parse(rawBody) : {};
    } catch (_error) {
      return Response.json({ error: "Invalid JSON payload" }, { status: 400 });
    }
  }

  const { messages, statuses } = parseWhatsAppWebhookPayload({
    rawBody,
    parsedJson: payload,
  });

  try {
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
        const conversation = await upsertWhatsAppConversationFromInbound({
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
        await markWhatsAppCampaignRecipientReplied({
          contactPhone: inboundMessage.contactPhone,
          conversationId: conversation.id,
        });
        waitUntil(
          processInboundWhatsAppMessage({
            conversationId: conversation.id,
            inboundMessage,
          }).catch((error) => {
            console.error(
              "[whatsapp:webhook] Background processing promise failed",
              error
            );
          })
        );
      } catch (error) {
        console.error("[whatsapp:webhook] Failed to process inbound message", error);
      }
    }

    return Response.json({ received: true });
  } catch (error) {
    console.error("[whatsapp:webhook] Unexpected webhook failure", error);
    return Response.json({ received: true });
  }
}
