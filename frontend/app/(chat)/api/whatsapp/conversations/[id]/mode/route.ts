import { z } from "zod";
import { auth } from "@/app/(auth)/auth";
import {
  appendWhatsAppMessage,
  getWhatsAppConversationById,
  updateWhatsAppConversationAgentState,
  updateWhatsAppConversationMode,
} from "@/lib/db/queries";

const modeSchema = z.object({
  mode: z.enum(["bot", "human"]),
});

export async function PATCH(
  request: Request,
  context: { params: Promise<{ id: string }> }
) {
  const session = await auth();

  if (!session?.user) {
    return Response.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { id } = await context.params;
  const conversation = await getWhatsAppConversationById({ id });

  if (!conversation) {
    return Response.json({ error: "Conversation not found" }, { status: 404 });
  }

  const rawBody = await request.json().catch(() => null);
  const payload = modeSchema.safeParse(rawBody);

  if (!payload.success) {
    return Response.json(
      {
        error: payload.error.flatten(),
      },
      { status: 400 }
    );
  }

  const nextMode = payload.data.mode;
  const updatedConversation = await updateWhatsAppConversationMode({
    id,
    mode: nextMode,
    assignedOperatorLabel:
      nextMode === "human"
        ? session.user.email ?? session.user.name ?? "Human operator"
        : null,
  });

  await appendWhatsAppMessage({
    conversationId: id,
    direction: "outgoing",
    authorType: "system",
    authorLabel: "System",
    body:
      nextMode === "human"
        ? "Human takeover enabled for this conversation."
        : "Bot replies re-enabled for this conversation.",
    status: "sent",
  });

  await updateWhatsAppConversationAgentState({
    id,
    patch: {
      handoffRecommended: nextMode === "human",
      handoffReason:
        nextMode === "human"
          ? "Operator switched this thread into human takeover mode"
          : null,
      nextBestMove:
        nextMode === "human"
          ? "Reply as a human and keep the thread calm and specific."
          : "Bot replies can resume on the next inbound message.",
      updatedAt: new Date().toISOString(),
    },
  });

  return Response.json({
    conversation: updatedConversation,
  });
}
