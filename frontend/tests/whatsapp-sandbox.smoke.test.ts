import assert from "node:assert/strict";
import test from "node:test";
import {
  buildWhatsAppSandboxAgentState,
  buildWhatsAppSandboxLeadContext,
  isWhatsAppSandboxLead,
} from "@/lib/whatsapp/sandbox";

test("sandbox lead context and agent state stay stable", () => {
  const leadContext = buildWhatsAppSandboxLeadContext({
    contactPhone: "+91 83 1000 2656",
    companyName: "iSkin Bangalore",
    geo: "Bangalore",
    topIssue: "WhatsApp enquiries dropping before booking confirmation",
    decisionMakerName: "Ashren",
    decisionMakerRole: "Founder",
  });

  assert.match(leadContext.leadId, /^sandbox:/);
  assert.equal(leadContext.companyName, "iSkin Bangalore");
  assert.equal(leadContext.source, "sandbox_demo");
  assert.equal(leadContext.bestContactChannel, "whatsapp");

  const state = buildWhatsAppSandboxAgentState({
    companyName: leadContext.companyName,
    topIssue: leadContext.topIssue,
    decisionMakerRole: leadContext.decisionMakerRole,
  });

  assert.equal(state.stage, "ENGAGED");
  assert.equal(state.priority, "high");
  assert.equal(state.decisionMakerRole, "Founder");
  assert.equal(state.leadChannels?.includes("sandbox_demo"), true);

  assert.equal(
    isWhatsAppSandboxLead({
      linkedLeadId: leadContext.leadId,
      leadContext,
    }),
    true
  );
  assert.equal(
    isWhatsAppSandboxLead({
      linkedLeadId: "real-lead-id",
      leadContext: null,
    }),
    false
  );
});
