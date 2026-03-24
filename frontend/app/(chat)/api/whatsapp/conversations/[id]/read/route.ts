import { auth } from "@/app/(auth)/auth";
import {
  getWhatsAppConversationById,
  markWhatsAppConversationRead,
} from "@/lib/db/queries";

export async function POST(
  _request: Request,
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

  const updatedConversation = await markWhatsAppConversationRead({ id });

  return Response.json({
    conversation: updatedConversation,
  });
}
