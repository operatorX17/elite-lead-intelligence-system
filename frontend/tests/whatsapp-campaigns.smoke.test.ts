import assert from "node:assert/strict";
import test from "node:test";

process.env.ZRAI_IN_MEMORY_DB = "true";
process.env.WHATSAPP_PROVIDER = "twilio";
process.env.TWILIO_ACCOUNT_SID = "AC_TEST";
process.env.TWILIO_AUTH_TOKEN = "secret";
process.env.TWILIO_WHATSAPP_NUMBER = "+15550001111";
process.env.NEXTAUTH_URL = "https://example.com";

const originalFetch = global.fetch;
global.fetch = async () =>
  new Response(JSON.stringify({ sid: "SM_TEST", status: "queued" }), {
    status: 201,
    headers: { "Content-Type": "application/json" },
  });

let campaignsDb: typeof import("@/lib/db/whatsapp-campaigns");
let campaignRunner: typeof import("@/lib/whatsapp/campaign-runner");

test.before(async () => {
  campaignsDb = await import("@/lib/db/whatsapp-campaigns");
  campaignRunner = await import("@/lib/whatsapp/campaign-runner");
});

test("campaign wave sends approved recipients and marks replies", async () => {
  const campaign = await campaignsDb.createWhatsAppCampaign({
    name: "Wave 1",
    messageStyle: "template",
    templateName: "curiosity_wave_1",
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

test.after(() => {
  global.fetch = originalFetch;
});
