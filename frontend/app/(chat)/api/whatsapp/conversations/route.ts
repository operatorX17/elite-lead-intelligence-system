import { z } from "zod";
import { auth } from "@/app/(auth)/auth";
import {
  createWhatsAppConversation,
  listWhatsAppConversations,
  updateWhatsAppConversationLeadLink,
} from "@/lib/db/queries";
import { getWhatsAppPublicConfig } from "@/lib/whatsapp/config";
import { resolveLeadContextForWhatsAppThread } from "@/lib/whatsapp/lead-context";

const createConversationSchema = z.object({
  contactName: z.string().trim().min(1, "Contact name is required"),
  contactPhone: z.string().trim().min(5, "Phone number is required"),
  startInHumanMode: z.boolean().optional(),
});

export async function GET() {
  const session = await auth();

  if (!session?.user) {
    return Response.json({ error: "Unauthorized" }, { status: 401 });
  }

  const conversations = await listWhatsAppConversations();

  return Response.json({
    conversations,
    config: getWhatsAppPublicConfig(),
  });
}

export async function POST(request: Request) {
  const session = await auth();

  if (!session?.user) {
    return Response.json({ error: "Unauthorized" }, { status: 401 });
  }

  const rawBody = await request.json().catch(() => null);
  const payload = createConversationSchema.safeParse(rawBody);

  if (!payload.success) {
    return Response.json(
      {
        error: payload.error.flatten(),
      },
      { status: 400 }
    );
  }

  let conversation = await createWhatsAppConversation({
    contactName: payload.data.contactName,
    contactPhone: payload.data.contactPhone,
    mode: payload.data.startInHumanMode ? "human" : "bot",
    source: "manual",
    assignedOperatorLabel: payload.data.startInHumanMode
      ? session.user.email ?? session.user.name ?? "Human operator"
      : null,
    opsState: {
      commercialStatus: "contacted",
      senderStatus: "not_started",
      owner: session.user.email ?? session.user.name ?? null,
      nextActionAt: payload.data.startInHumanMode
        ? new Date().toISOString()
        : null,
      niche: "Derm & Aesthetic",
      contactChannel: "whatsapp",
    },
  });

  try {
    const resolved = await resolveLeadContextForWhatsAppThread({
      contactPhone: conversation.contactPhone,
      contactName: conversation.contactName,
      userId: session.user.id,
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
    console.warn("[whatsapp:create] Lead linking failed", error);
  }

  return Response.json({
    conversation,
  });
}
