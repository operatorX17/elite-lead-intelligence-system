import assert from "node:assert/strict";
import { createRequire } from "node:module";
import test from "node:test";

test("unlinked clinic-sales threads use backend prospect reasoning before local fallback", async () => {
  process.env.ZRAI_BACKEND_URL = "https://backend.test";
  const require = createRequire(import.meta.url);
  const serverOnlyPath = require.resolve("server-only");
  require.cache[serverOnlyPath] = {
    exports: {},
    filename: serverOnlyPath,
    id: serverOnlyPath,
    loaded: true,
    path: serverOnlyPath,
  } as any;

  const originalFetch = global.fetch;
  const fetchCalls: Array<{ url: string; body: string }> = [];

  global.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
    fetchCalls.push({
      url: String(input),
      body: String(init?.body || ""),
    });

    return new Response(
      JSON.stringify({
        success: true,
        ai_response:
          "Hi, this is ZRAI. Is this for one clinic or multiple branches, and is the goal simple enquiry capture or confirmed booking on WhatsApp?",
        conversation: {
          conversation_id: "prospect_conv_1",
          entities: {
            stage: "ENGAGED",
            lead_channels: ["sales_whatsapp", "clinic_sales", "inbound_whatsapp"],
            pain_points: ["booking_gap", "whatsapp_gap"],
            confidence: 0.66,
          },
        },
      }),
      {
        status: 200,
        headers: {
          "Content-Type": "application/json",
        },
      }
    );
  }) as typeof fetch;

  try {
    const { generateWhatsAppReplyPlan } = await import("@/lib/whatsapp/agent");
    const { createWhatsAppInboundSalesProspectState } = await import(
      "@/lib/whatsapp/state"
    );

    const conversation = {
      id: "conv_backend_sales",
      linkedLeadId: null,
      leadContext: null,
      opsState: {
        niche: "Derm & Aesthetic",
        city: "Bangalore",
      },
      contactName: "Self Test",
      contactPhone: "+918310002656",
      businessPhone: "+16623986774",
      mode: "bot",
      agentState: createWhatsAppInboundSalesProspectState(),
    } as any;

    const plan = await generateWhatsAppReplyPlan({
      conversation,
      messages: [],
      incomingText: "Hi",
    });

    assert.equal(fetchCalls.length, 1);
    assert.match(fetchCalls[0]?.url || "", /\/api\/v1\/conversation\/prospect$/);
    assert.match(fetchCalls[0]?.body || "", /"message":"Hi"/);
    assert.match(plan.replyText, /zrai/i);
    assert.match(plan.replyText, /clinic|branches|booking/i);
    assert.equal(plan.nextState.leadChannels.includes("clinic_sales"), true);
  } finally {
    global.fetch = originalFetch;
  }
});
