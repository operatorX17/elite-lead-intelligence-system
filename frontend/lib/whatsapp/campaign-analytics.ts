import type { WhatsAppConversation } from "@/lib/db/schema";
import type { WhatsAppCampaignRecord } from "@/lib/whatsapp/campaigns";
import {
  normalizeWhatsAppAgentState,
  normalizeWhatsAppOpsState,
} from "@/lib/whatsapp/state";

export type WhatsAppCampaignAnalytics = {
  overview: {
    campaigns: number;
    activeCampaigns: number;
    readyRecipients: number;
    contactedRecipients: number;
    repliedRecipients: number;
    failedRecipients: number;
    replyRate: number;
    demoReadyThreads: number;
    hotThreads: number;
    qualifiedThreads: number;
    demoBookedThreads: number;
    pilotWonThreads: number;
    liveSenders: number;
  };
  hotThreads: Array<{
    conversationId: string;
    contactName: string;
    contactPhone: string;
    companyName: string | null;
    stage: string;
    priority: string;
    summary: string | null;
    nextBestMove: string | null;
    lastMessageAt: string;
  }>;
  campaignRollup: Array<{
    id: string;
    name: string;
    status: string;
    ready: number;
    contacted: number;
    replied: number;
    replyRate: number;
    nextWaveAt: string | null;
  }>;
};

function isDemoReadyStage(stage: string) {
  return ["DEMO_PUSHED", "PAYMENT_PUSHED", "HUMAN_HANDOFF"].includes(stage);
}

export function computeWhatsAppCampaignAnalytics({
  campaigns,
  conversations,
}: {
  campaigns: WhatsAppCampaignRecord[];
  conversations: WhatsAppConversation[];
}): WhatsAppCampaignAnalytics {
  const activeCampaigns = campaigns.filter(
    (campaign) => campaign.status === "active"
  ).length;
  const readyRecipients = campaigns.reduce(
    (total, campaign) => total + campaign.counts.approved,
    0
  );
  const repliedRecipients = campaigns.reduce(
    (total, campaign) => total + campaign.counts.replied,
    0
  );
  const failedRecipients = campaigns.reduce(
    (total, campaign) => total + campaign.counts.failed,
    0
  );
  const contactedRecipients = campaigns.reduce(
    (total, campaign) =>
      total +
      campaign.recipients.filter((recipient) =>
        ["sent", "replied", "failed"].includes(recipient.status)
      ).length,
    0
  );
  const replyBase = campaigns.reduce(
    (total, campaign) => total + campaign.counts.sent + campaign.counts.replied,
    0
  );
  const replyRate =
    replyBase > 0 ? Math.round((repliedRecipients / replyBase) * 100) : 0;

  const campaignPhones = new Set(
    campaigns.flatMap((campaign) =>
      campaign.recipients.map((recipient) => recipient.contactPhone)
    )
  );

  const hotThreads = conversations
    .filter((conversation) => campaignPhones.has(conversation.contactPhone))
    .map((conversation) => ({
      conversation,
      state: normalizeWhatsAppAgentState(conversation.agentState),
      opsState: normalizeWhatsAppOpsState(conversation.opsState),
    }))
    .filter(
      ({ state }) =>
        state.priority === "high" ||
        isDemoReadyStage(state.stage) ||
        state.requestedNextStep === "call"
    )
    .sort(
      (a, b) =>
        b.conversation.lastMessageAt.getTime() - a.conversation.lastMessageAt.getTime()
    );

  const demoReadyThreads = hotThreads.filter(
    ({ state }) =>
      isDemoReadyStage(state.stage) || state.requestedNextStep === "call"
  ).length;
  const qualifiedThreads = conversations.filter((conversation) => {
    const opsState = normalizeWhatsAppOpsState(conversation.opsState);
    return ["qualified", "demo_booked", "demo_done", "pilot_won", "onboarding", "live"].includes(
      opsState.commercialStatus
    );
  }).length;
  const demoBookedThreads = conversations.filter((conversation) => {
    const opsState = normalizeWhatsAppOpsState(conversation.opsState);
    return ["demo_booked", "demo_done", "pilot_won", "onboarding", "live"].includes(
      opsState.commercialStatus
    );
  }).length;
  const pilotWonThreads = conversations.filter((conversation) => {
    const opsState = normalizeWhatsAppOpsState(conversation.opsState);
    return ["pilot_won", "onboarding", "live"].includes(
      opsState.commercialStatus
    );
  }).length;
  const liveSenders = conversations.filter((conversation) => {
    const opsState = normalizeWhatsAppOpsState(conversation.opsState);
    return opsState.senderStatus === "live";
  }).length;

  return {
    overview: {
      campaigns: campaigns.length,
      activeCampaigns,
      readyRecipients,
      contactedRecipients,
      repliedRecipients,
      failedRecipients,
      replyRate,
      demoReadyThreads,
      hotThreads: hotThreads.length,
      qualifiedThreads,
      demoBookedThreads,
      pilotWonThreads,
      liveSenders,
    },
    hotThreads: hotThreads.slice(0, 8).map(({ conversation, state }) => ({
      conversationId: conversation.id,
      contactName: conversation.contactName,
      contactPhone: conversation.contactPhone,
      companyName: conversation.leadContext?.companyName ?? null,
      stage: state.stage,
      priority: state.priority,
      summary: state.summary,
      nextBestMove: state.nextBestMove,
      lastMessageAt: conversation.lastMessageAt.toISOString(),
    })),
    campaignRollup: campaigns.map((campaign) => {
      const contacted = campaign.recipients.filter((recipient) =>
        ["sent", "replied", "failed"].includes(recipient.status)
      ).length;
      const sentBase = campaign.counts.sent + campaign.counts.replied;

      return {
        id: campaign.id,
        name: campaign.name,
        status: campaign.status,
        ready: campaign.counts.approved,
        contacted,
        replied: campaign.counts.replied,
        replyRate:
          sentBase > 0 ? Math.round((campaign.counts.replied / sentBase) * 100) : 0,
        nextWaveAt: campaign.nextWaveAt,
      };
    }),
  };
}
