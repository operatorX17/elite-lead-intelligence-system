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

let queries: typeof import("@/lib/db/queries");
let policy: typeof import("@/lib/whatsapp/policy");

test.before(async () => {
  queries = await import("@/lib/db/queries");
  policy = await import("@/lib/whatsapp/policy");
});

test.beforeEach(() => {
  delete (globalThis as Record<string, unknown>).__zraiWhatsAppPolicyState;
});

test("freeform outbound is blocked outside the 24-hour service window", async () => {
  const conversation = await queries.createWhatsAppConversation({
    contactName: "Clinic Owner",
    contactPhone: "+9198310002656",
    businessPhone: "+15550001111",
  });

  const decision = await policy.guardWhatsAppOutboundMessage({
    conversationId: conversation.id,
    body: "Quick question.",
    messageStyle: "freeform",
  });

  assert.equal(decision.allowed, false);
  if (decision.allowed) {
    throw new Error("Expected freeform send to be blocked");
  }
  assert.equal(decision.reason, "customer_service_window_closed");
});

test("duplicate and hourly limits block repeated outbound sends", async () => {
  const now = new Date();
  const conversation = await queries.createWhatsAppConversation({
    contactName: "Clinic Owner",
    contactPhone: "+919900000001",
    businessPhone: "+15550001111",
  });

  await queries.appendWhatsAppMessage({
    conversationId: conversation.id,
    direction: "incoming",
    authorType: "contact",
    authorLabel: "Clinic Owner",
    body: "Hi",
    status: "received",
    createdAt: now,
  });

  await queries.appendWhatsAppMessage({
    conversationId: conversation.id,
    direction: "outgoing",
    authorType: "bot",
    authorLabel: "Bot",
    body: "Same body",
    status: "sent",
    createdAt: new Date(now.getTime() - 2 * 60_000),
  });

  let decision = await policy.guardWhatsAppOutboundMessage({
    conversationId: conversation.id,
    body: "Same body",
    messageStyle: "freeform",
  });
  assert.equal(decision.allowed, false);
  if (decision.allowed) {
    throw new Error("Expected duplicate send to be blocked");
  }
  assert.equal(decision.reason, "duplicate_recently_sent");

  await queries.appendWhatsAppMessage({
    conversationId: conversation.id,
    direction: "outgoing",
    authorType: "bot",
    authorLabel: "Bot",
    body: "Body two",
    status: "sent",
    createdAt: new Date(now.getTime() - 10 * 60_000),
  });
  await queries.appendWhatsAppMessage({
    conversationId: conversation.id,
    direction: "outgoing",
    authorType: "bot",
    authorLabel: "Bot",
    body: "Body three",
    status: "sent",
    createdAt: new Date(now.getTime() - 20 * 60_000),
  });

  decision = await policy.guardWhatsAppOutboundMessage({
    conversationId: conversation.id,
    body: "Body four",
    messageStyle: "freeform",
  });
  assert.equal(decision.allowed, false);
  if (decision.allowed) {
    throw new Error("Expected hourly limit to be blocked");
  }
  assert.equal(decision.reason, "per_user_hour_limit");
});
