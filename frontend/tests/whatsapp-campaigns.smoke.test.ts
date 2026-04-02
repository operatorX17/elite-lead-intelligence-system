import assert from "node:assert/strict";
import Module from "node:module";
import test from "node:test";

process.env.ZRAI_IN_MEMORY_DB = "true";
process.env.WHATSAPP_PROVIDER = "twilio";
process.env.TWILIO_ACCOUNT_SID = "AC_TEST";
process.env.TWILIO_AUTH_TOKEN = "secret";
process.env.TWILIO_WHATSAPP_NUMBER = "+15550001111";
process.env.NEXTAUTH_URL = "https://example.com";

const require = Module.createRequire(import.meta.url);
const serverOnlyPath = require.resolve("server-only");
require.cache[serverOnlyPath] = {
  exports: {},
} as NodeJS.Module;

const originalFetch = global.fetch;
const fetchCalls: Array<{ url: string; init?: RequestInit }> = [];
global.fetch = async (input, init) => {
  fetchCalls.push({
    url: String(input),
    init,
  });

  return new Response(JSON.stringify({ sid: "SM_TEST", status: "queued" }), {
    status: 201,
    headers: { "Content-Type": "application/json" },
  });
};

let campaignsDb: typeof import("@/lib/db/whatsapp-campaigns");
let campaignRunner: typeof import("@/lib/whatsapp/campaign-runner");
let campaignPresets: typeof import("@/lib/whatsapp/campaigns");
let salesPlaybook: typeof import("@/lib/whatsapp/sales-playbook");
let whatsappState: typeof import("@/lib/whatsapp/state");

test.before(async () => {
  campaignsDb = await import("@/lib/db/whatsapp-campaigns");
  campaignRunner = await import("@/lib/whatsapp/campaign-runner");
  campaignPresets = await import("@/lib/whatsapp/campaigns");
  salesPlaybook = await import("@/lib/whatsapp/sales-playbook");
  whatsappState = await import("@/lib/whatsapp/state");
});

test("campaign wave sends approved recipients and marks replies", async () => {
  const campaign = await campaignsDb.createWhatsAppCampaign({
    name: "Wave 1",
    messageStyle: "template",
    templateName: "curiosity_wave_1",
    providerTemplateId: "HX_TEST_TEMPLATE",
    providerTemplateVariables: {
      "1": "{{company_name}}",
      "2": "{{first_name}}",
    },
    messageTemplate: "Hi {{first_name}} from {{company_name}}",
    createdByLabel: "Operator",
    dailyLimit: 20,
    waveSize: 5,
    waveGapMinutes: 30,
    recipients: [
      {
        contactName: "Sai Prakash",
        contactPhone: "+9198310002656",
        companyName: "iSkin",
      },
      {
        contactName: "Ashren",
        contactPhone: "+919999999999",
        companyName: "Aesthetic Edge",
      },
    ],
  });

  await campaignsDb.approveWhatsAppCampaignRecipients({
    campaignId: campaign.id,
    approvedByLabel: "Operator",
  });

  const runResult = await campaignRunner.runWhatsAppCampaignWave({
    campaignId: campaign.id,
    operatorLabel: "Operator",
    userId: null,
  });

  assert.equal("error" in runResult, false);
  if ("error" in runResult) {
    throw new Error(runResult.error);
  }

  assert.equal(runResult.sentCount, 2);
  const twilioCalls = fetchCalls.filter((call) =>
    call.url.includes("api.twilio.com")
  );
  assert.equal(twilioCalls.length, 2);
  const firstBody = String(twilioCalls[0]?.init?.body ?? "");
  assert.match(firstBody, /ContentSid=HX_TEST_TEMPLATE/);
  assert.match(firstBody, /ContentVariables=/);
  assert.match(firstBody, /MessagingServiceSid|From=/);

  const reloadedCampaign = await campaignsDb.getWhatsAppCampaignById({
    id: campaign.id,
  });

  assert.ok(reloadedCampaign);
  assert.equal(reloadedCampaign?.counts.sent, 2);

  const targetRecipient = reloadedCampaign?.recipients.find(
    (recipient) => recipient.contactPhone === "+9198310002656"
  );
  assert.ok(targetRecipient?.conversationId);

  await campaignsDb.markWhatsAppCampaignRecipientReplied({
    contactPhone: "+9198310002656",
    conversationId: targetRecipient?.conversationId ?? null,
  });

  const repliedCampaign = await campaignsDb.getWhatsAppCampaignById({
    id: campaign.id,
  });
  assert.equal(repliedCampaign?.counts.replied, 1);
  assert.equal(
    repliedCampaign?.recipients.find(
      (recipient) => recipient.contactPhone === "+9198310002656"
    )?.status,
    "replied"
  );
});

test("outbound preset keeps unlinked clinic replies in SDR mode", () => {
  const outboundPatch = campaignPresets.buildOutreachCampaignStatePatch({
    presetId: "curiosity_wave_1",
    companyName: "iSkin",
  });

  assert.ok(outboundPatch);
  assert.equal(
    outboundPatch?.leadChannels?.includes("outbound_whatsapp"),
    true
  );

  const seededState = whatsappState.createWhatsAppAgentState(outboundPatch ?? {});
  const greetingReply = salesPlaybook.buildWhatsAppFallbackReply(
    seededState,
    [],
    null,
    "hi",
    null
  );

  assert.match(greetingReply, /Quick one/i);
  assert.match(greetingReply, /booking|enquiry/i);

  const conversation = {
    id: "conv_test",
    linkedLeadId: null,
    leadContext: null,
    contactName: "Clinic Owner",
    contactPhone: "+919900000000",
    mode: "bot",
  } as any;

  const systemPrompt = salesPlaybook.buildWhatsAppSystemPrompt({
    conversation,
    state: seededState,
    messages: [],
    leadContext: null,
  });

  assert.match(systemPrompt, /outbound WhatsApp outreach/i);

  const derived = salesPlaybook.deriveNextWhatsAppAgentState({
    conversation,
    messages: [],
    incomingText: "hi",
    currentState: seededState,
  });

  assert.equal(
    derived.nextState.leadChannels.includes("outbound_whatsapp"),
    true
  );

  const followUpReply = salesPlaybook.buildWhatsAppFallbackReply(
    derived.nextState,
    [],
    null,
    "yes",
    greetingReply
  );

  assert.match(followUpReply, /WhatsApp enquiries|normal week|most weeks/i);
});

test.after(() => {
  global.fetch = originalFetch;
});
