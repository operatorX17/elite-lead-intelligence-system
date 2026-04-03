import assert from "node:assert/strict";
import test from "node:test";

let salesPlaybook: typeof import("@/lib/whatsapp/sales-playbook");
let whatsappState: typeof import("@/lib/whatsapp/state");

test.before(async () => {
  salesPlaybook = await import("@/lib/whatsapp/sales-playbook");
  whatsappState = await import("@/lib/whatsapp/state");
});

test("unknown inbound clinic threads bootstrap into sales mode instead of generic inbox mode", () => {
  const seededState = whatsappState.createWhatsAppInboundSalesProspectState();

  assert.equal(seededState.leadChannels.includes("sales_whatsapp"), true);
  assert.equal(seededState.leadChannels.includes("clinic_sales"), true);

  const conversation = {
    id: "conv_inbound_sales",
    linkedLeadId: null,
    leadContext: null,
    contactName: "Self Test",
    contactPhone: "+918310002656",
    mode: "bot",
  } as any;

  const derived = salesPlaybook.deriveNextWhatsAppAgentState({
    conversation,
    messages: [],
    incomingText: "Whatsapp Patient Booking needed",
    currentState: seededState,
  });

  assert.equal(derived.nextState.painConfirmed, true);
  assert.equal(derived.nextState.leadChannels.includes("sales_whatsapp"), true);
  assert.equal(derived.nextState.painPoints.includes("booking_gap"), true);
  assert.equal(derived.nextState.painPoints.includes("whatsapp_gap"), true);

  const reply = salesPlaybook.buildWhatsAppFallbackReply(
    derived.nextState,
    [],
    null,
    "Whatsapp Patient Booking needed",
    null
  );

  assert.match(reply, /lead capture|confirmed booking|booking/i);
  assert.doesNotMatch(reply, /Tell me the context and what you want help with/i);
});

test("clinic-sales greeting stays in healthcare intake mode for unknown inbound threads", () => {
  const seededState = whatsappState.createWhatsAppInboundSalesProspectState();
  const reply = salesPlaybook.buildWhatsAppFallbackReply(
    seededState,
    [],
    null,
    "hi",
    null
  );

  assert.match(reply, /zrai/i);
  assert.match(reply, /clinic|healthcare|whatsapp/i);
  assert.doesNotMatch(reply, /What are you looking to get sorted right now/i);
});

test("just enquiry is treated as a real workflow answer, not a generic follow-up loop", () => {
  const seededState = whatsappState.createWhatsAppInboundSalesProspectState({
    painPoints: ["booking_gap", "whatsapp_gap"],
    painConfirmed: true,
  } as any);

  const reply = salesPlaybook.buildWhatsAppFallbackReply(
    seededState,
    [],
    null,
    "Just enquiry please!",
    "Got it. Pick the main goal first: enquiry capture only, or full booking inside WhatsApp. If relevant, tell me whether this is for one clinic or several branches."
  );

  assert.match(reply, /one clinic|multiple branches|instagram|website|whatsapp/i);
  assert.doesNotMatch(reply, /What are you looking to get sorted right now/i);
});
