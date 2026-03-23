import type {
  AgentHealth,
  Conversation,
  ConversationMessage,
  GovernanceStatus,
  OutreachMessage,
  OutreachStatus,
  ProofArtifact,
  SystemMetrics,
} from "@/lib/zrai/types";

const OUTREACH_SECTION_BREAK = /\n\s*\n/;

function asIsoString(value: unknown): string {
  return typeof value === "string" && value.length > 0
    ? value
    : new Date().toISOString();
}

function parseOutreachBody(body: string) {
  const sections = body
    .split(OUTREACH_SECTION_BREAK)
    .map((section) => section.trim())
    .filter(Boolean);

  return {
    observation: sections[0] || "",
    impact: sections[1] || "",
    offer: sections[2] || "",
    cta: sections[3] || sections.at(-1) || "",
  };
}

function normalizeOutreachStatus(status: unknown): OutreachStatus {
  const value = String(status || "draft").toLowerCase();
  const statusMap: Record<string, OutreachStatus> = {
    pending: "draft",
    approved: "approved",
    sent: "sent",
    rejected: "failed",
    failed: "failed",
    delivered: "delivered",
    opened: "opened",
    clicked: "clicked",
    replied: "replied",
    bounced: "bounced",
    draft: "draft",
  };
  return statusMap[value] || "draft";
}

export function toProofArtifact(
  proof: Record<string, any>,
  proofType = "screenshot"
): ProofArtifact {
  const primaryUrl =
    proof.hero_screenshot_url || proof.cta_screenshot_url || "";
  const extractedText =
    proofType === "extracted_data"
      ? JSON.stringify(proof.extraction_data || {}, null, 2)
      : undefined;

  return {
    id: `${proof.lead_id || "proof"}-${proofType}`,
    lead_id: String(proof.lead_id || ""),
    proof_type: proofType as ProofArtifact["proof_type"],
    url: primaryUrl,
    storage_path: primaryUrl,
    metadata: {
      url: primaryUrl,
      extracted_text: extractedText,
    },
    created_at: asIsoString(proof.generated_at),
  };
}

export function toOutreachMessage(
  message: Record<string, any>,
  fallbackChannel: string
): OutreachMessage {
  const body = String(message.body || "");
  return {
    id: String(message.outreach_id || message.id || ""),
    lead_id: String(message.lead_id || ""),
    channel: (message.channel || fallbackChannel || "email").toLowerCase(),
    subject: message.subject || undefined,
    body,
    structure: parseOutreachBody(body),
    personalization: message.personalization || {},
    status: normalizeOutreachStatus(message.status),
    sent_at: typeof message.sent_at === "string" ? message.sent_at : undefined,
    created_at: asIsoString(message.created_at),
  };
}

export function toConversation(
  conversation: Record<string, any>,
  channel = "email"
): Conversation {
  const transcript = Array.isArray(conversation.transcript)
    ? conversation.transcript
    : [];

  const messages: ConversationMessage[] = transcript.map((item, index) => {
    const role = String(item.role || "prospect").toLowerCase();
    const sender = role === "ai" ? "ai" : "lead";
    return {
      id: `${conversation.conversation_id || "conversation"}-${index}`,
      conversation_id: String(conversation.conversation_id || ""),
      role: sender,
      sender,
      content: String(item.message || ""),
      channel: channel as ConversationMessage["channel"],
      timestamp: asIsoString(item.timestamp),
      created_at: asIsoString(item.timestamp),
      qualification_signals: [],
    };
  });

  return {
    id: String(conversation.conversation_id || ""),
    lead_id: String(conversation.lead_id || ""),
    status: conversation.escalated ? "escalated" : "active",
    messages,
    escalation_reason: conversation.objection_summary || undefined,
    created_at: asIsoString(conversation.created_at),
    updated_at: asIsoString(conversation.updated_at),
  };
}

export function toSystemMetrics(data: GovernanceStatus): SystemMetrics {
  const agentHealthEntries = (data.agent_health || []).map(
    (agent: AgentHealth) => [agent.agent_name, agent]
  );

  return {
    period: "daily",
    reply_rate: 0,
    meeting_rate: 0,
    cost_per_meeting: 0,
    leads_discovered: 0,
    leads_qualified: 0,
    outreach_sent: 0,
    budget: {
      llm_tokens: data.budgets.llm_tokens,
      apify_runs: data.budgets.apify_runs,
      browser_sessions: data.budgets.browser_sessions,
    },
    agent_health: Object.fromEntries(agentHealthEntries),
  };
}
