import "server-only";

import {
  countWhatsAppCampaignRecipientsSentToday,
  getWhatsAppCampaignById,
  updateWhatsAppCampaign,
  updateWhatsAppCampaignRecipient,
} from "@/lib/db/whatsapp-campaigns";
import {
  appendWhatsAppMessage,
  createWhatsAppConversation,
  getWhatsAppConversationByPhone,
  updateWhatsAppConversationLeadLink,
} from "@/lib/db/queries";
import {
  resolveLeadContextForWhatsAppThread,
  syncWhatsAppMessageToLeadMemory,
} from "@/lib/whatsapp/lead-context";
import { renderCampaignMessageTemplate } from "@/lib/whatsapp/campaigns";
import { sendWhatsAppTextMessage } from "@/lib/whatsapp/provider";

function nextDaySameTime(now: Date) {
  const next = new Date(now);
  next.setDate(next.getDate() + 1);
  return next;
}

export async function runWhatsAppCampaignWave({
  campaignId,
  operatorLabel,
  userId,
}: {
  campaignId: string;
  operatorLabel: string;
  userId?: string | null;
}) {
  let campaign = await getWhatsAppCampaignById({ id: campaignId });
  if (!campaign) {
    return { error: "Campaign not found", status: 404 as const };
  }

  const now = new Date();
  if (campaign.status === "paused") {
    return {
      error: "Campaign is paused. Resume it before sending.",
      status: 400 as const,
    };
  }

  if (campaign.nextWaveAt && new Date(campaign.nextWaveAt).getTime() > now.getTime()) {
    return {
      error: "Next wave is not due yet",
      nextWaveAt: campaign.nextWaveAt,
      status: 400 as const,
    };
  }

  const sentToday = await countWhatsAppCampaignRecipientsSentToday({
    campaignId,
    now,
  });
  const remainingDaily = Math.max(0, campaign.dailyLimit - sentToday);

  if (remainingDaily <= 0) {
    const nextWaveAt = nextDaySameTime(now).toISOString();
    campaign =
      (await updateWhatsAppCampaign({
        id: campaignId,
        patch: {
          status: "active",
          nextWaveAt,
          lastWaveAt: now.toISOString(),
        },
      })) || campaign;

    return {
      campaign,
      sentCount: 0,
      blockedReason: "daily_limit_reached",
      status: 200 as const,
    };
  }

  const approvedRecipients = campaign.recipients.filter(
    (recipient) => recipient.status === "approved"
  );
  const sendBatch = approvedRecipients.slice(
    0,
    Math.min(remainingDaily, campaign.waveSize)
  );

  if (sendBatch.length === 0) {
    const nextStatus =
      campaign.recipients.some((recipient) => recipient.status === "replied") ||
      campaign.recipients.some((recipient) => recipient.status === "sent")
        ? "completed"
        : campaign.status;
    campaign =
      (await updateWhatsAppCampaign({
        id: campaignId,
        patch: {
          status: nextStatus,
        },
      })) || campaign;
    return { campaign, sentCount: 0, status: 200 as const };
  }

  const results: Array<{
    recipientId: string;
    status: "sent" | "failed";
    error: string | null;
  }> = [];

  for (const recipient of sendBatch) {
    let conversation =
      (await getWhatsAppConversationByPhone({
        contactPhone: recipient.contactPhone,
      })) ||
      (await createWhatsAppConversation({
        contactName: recipient.contactName,
        contactPhone: recipient.contactPhone,
        mode: "bot",
        source: "manual",
      }));

    if (!conversation.linkedLeadId) {
      try {
        const resolved = await resolveLeadContextForWhatsAppThread({
          contactPhone: conversation.contactPhone,
          contactName: conversation.contactName,
          userId: userId ?? null,
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
        console.warn("[whatsapp:campaign-run] Lead linking failed", error);
      }
    }

    const outgoingBody = renderCampaignMessageTemplate({
      template: recipient.messageBody,
      contactName: recipient.contactName,
      contactPhone: recipient.contactPhone,
      companyName: recipient.companyName ?? conversation.leadContext?.companyName ?? null,
      topIssue: conversation.leadContext?.topIssue ?? null,
      decisionMakerName: conversation.leadContext?.decisionMakerName ?? null,
      city: conversation.leadContext?.geo ?? null,
    }).trim();

    const delivery = await sendWhatsAppTextMessage({
      to: recipient.contactPhone,
      body: outgoingBody,
    });

    await appendWhatsAppMessage({
      conversationId: conversation.id,
      direction: "outgoing",
      authorType: "human",
      authorLabel: operatorLabel,
      body: outgoingBody,
      providerMessageId: delivery.providerMessageId,
      status: delivery.status,
      errorText: delivery.error,
    });

    const nextStatus =
      delivery.status === "failed" || delivery.status === "draft"
        ? "failed"
        : "sent";

    if (conversation.linkedLeadId && nextStatus === "sent") {
      try {
        await syncWhatsAppMessageToLeadMemory({
          leadId: conversation.linkedLeadId,
          message: outgoingBody,
          role: "human",
          conversationId: conversation.backendConversationId,
          userId: userId ?? null,
        });
      } catch (error) {
        console.warn("[whatsapp:campaign-run] Backend sync failed", error);
      }
    }

    await updateWhatsAppCampaignRecipient({
      campaignId,
      recipientId: recipient.id,
      patch: {
        conversationId: conversation.id,
        linkedLeadId: conversation.linkedLeadId,
        messageBody: outgoingBody,
        status: nextStatus,
        providerMessageId: delivery.providerMessageId,
        sentAt: nextStatus === "sent" ? now.toISOString() : undefined,
        errorText: delivery.error,
      },
    });

    results.push({
      recipientId: recipient.id,
      status: nextStatus,
      error: delivery.error,
    });
  }

  campaign = (await getWhatsAppCampaignById({ id: campaignId })) || campaign;
  const remainingApproved = campaign.recipients.filter(
    (recipient) => recipient.status === "approved"
  ).length;

  const nextWaveAt =
    remainingApproved > 0
      ? new Date(now.getTime() + campaign.waveGapMinutes * 60_000).toISOString()
      : null;

  campaign =
    (await updateWhatsAppCampaign({
      id: campaignId,
      patch: {
        status: remainingApproved > 0 ? "active" : "completed",
        lastWaveAt: now.toISOString(),
        nextWaveAt:
          remainingApproved > 0 && remainingDaily - sendBatch.length > 0
            ? nextWaveAt
            : remainingApproved > 0
              ? nextDaySameTime(now).toISOString()
              : null,
      },
    })) || campaign;

  return {
    campaign,
    sentCount: results.filter((result) => result.status === "sent").length,
    results,
    status: 200 as const,
  };
}
