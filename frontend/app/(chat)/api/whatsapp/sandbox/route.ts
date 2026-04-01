import { z } from "zod";
import { auth } from "@/app/(auth)/auth";
import {
  appendWhatsAppMessage,
  createWhatsAppConversation,
  getWhatsAppConversationByPhone,
  getWhatsAppMessagesByConversationId,
  updateWhatsAppConversationAgentState,
  updateWhatsAppConversationLeadLink,
  updateWhatsAppConversationOpsState,
} from "@/lib/db/queries";
import {
  buildWhatsAppSandboxAgentState,
  buildWhatsAppSandboxLeadContext,
  buildWhatsAppSandboxOpsState,
} from "@/lib/whatsapp/sandbox";
import { getWhatsAppDefaultSender } from "@/lib/whatsapp/config";

const createSandboxSchema = z.object({
  contactName: z.string().trim().min(1, "Contact name is required"),
  contactPhone: z.string().trim().min(5, "WhatsApp number is required"),
  companyName: z.string().trim().min(1, "Company name is required"),
  geo: z.string().trim().optional(),
  topIssue: z.string().trim().optional(),
  decisionMakerName: z.string().trim().optional(),
  decisionMakerRole: z.string().trim().optional(),
  seedStarterThread: z.boolean().optional().default(true),
});

export async function POST(request: Request) {
  const session = await auth();

  if (!session?.user) {
    return Response.json({ error: "Unauthorized" }, { status: 401 });
  }

  const rawBody = await request.json().catch(() => null);
  const payload = createSandboxSchema.safeParse(rawBody);

  if (!payload.success) {
    return Response.json({ error: payload.error.flatten() }, { status: 400 });
  }

  const {
    contactName,
    contactPhone,
    companyName,
    geo,
    topIssue,
    decisionMakerName,
    decisionMakerRole,
    seedStarterThread,
  } = payload.data;

  const businessPhone = getWhatsAppDefaultSender();
  let conversation =
    (await getWhatsAppConversationByPhone({ contactPhone, businessPhone })) ||
    (await createWhatsAppConversation({
      contactName,
      contactPhone,
      businessPhone,
      mode: "bot",
      source: "manual",
      opsState: buildWhatsAppSandboxOpsState({
        geo,
        owner: session.user.email ?? session.user.name ?? null,
      }),
    }));

  const leadContext = buildWhatsAppSandboxLeadContext({
    contactPhone,
    companyName,
    geo,
    topIssue,
    decisionMakerName,
    decisionMakerRole,
  });

  conversation =
    (await updateWhatsAppConversationLeadLink({
      id: conversation.id,
      linkedLeadId: leadContext.leadId,
      backendConversationId: null,
      leadContext,
    })) || conversation;

  conversation =
    (await updateWhatsAppConversationOpsState({
      id: conversation.id,
      patch: buildWhatsAppSandboxOpsState({
        geo,
        owner: session.user.email ?? session.user.name ?? null,
      }),
    })) || conversation;

  conversation =
    (await updateWhatsAppConversationAgentState({
      id: conversation.id,
      patch: buildWhatsAppSandboxAgentState({
        companyName,
        topIssue,
        decisionMakerRole,
      }),
    })) || conversation;

  if (seedStarterThread) {
    const existingMessages = await getWhatsAppMessagesByConversationId({
      conversationId: conversation.id,
    });

    if (existingMessages.length === 0) {
      await appendWhatsAppMessage({
        conversationId: conversation.id,
        direction: "outgoing",
        authorType: "system",
        authorLabel: "Sandbox",
        body: `Sandbox lead seeded for ${companyName}. This thread is safe to use for manual WhatsApp sales-agent testing.`,
        status: "sent",
      });

      await appendWhatsAppMessage({
        conversationId: conversation.id,
        direction: "incoming",
        authorType: "contact",
        authorLabel: contactName,
        body: `Hi, I run ${companyName}. We get enquiries on WhatsApp and by phone, but I think some people disappear before booking. Can you show me what you would improve first?`,
        status: "received",
      });
    }
  }

  const messages = await getWhatsAppMessagesByConversationId({
    conversationId: conversation.id,
  });

  return Response.json({
    conversation,
    messages,
  });
}
