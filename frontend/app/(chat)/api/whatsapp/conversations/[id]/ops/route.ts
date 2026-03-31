import { z } from "zod";
import { auth } from "@/app/(auth)/auth";
import {
  getWhatsAppConversationById,
  updateWhatsAppConversationOpsState,
} from "@/lib/db/queries";
import {
  WHATSAPP_COMMERCIAL_STATUSES,
  WHATSAPP_SENDER_STATUSES,
} from "@/lib/whatsapp/state";

const updateConversationOpsSchema = z.object({
  commercialStatus: z.enum(WHATSAPP_COMMERCIAL_STATUSES).optional(),
  senderStatus: z.enum(WHATSAPP_SENDER_STATUSES).optional(),
  owner: z.string().trim().nullable().optional(),
  nextActionAt: z.string().trim().nullable().optional(),
  niche: z.string().trim().nullable().optional(),
  city: z.string().trim().nullable().optional(),
  contactChannel: z.string().trim().nullable().optional(),
  senderOnboardingPossible: z.boolean().nullable().optional(),
  onboardingChecklist: z
    .object({
      hoursCollected: z.boolean().optional(),
      servicesCollected: z.boolean().optional(),
      faqCollected: z.boolean().optional(),
      escalationOwnerCollected: z.boolean().optional(),
      routingChecklistAssigned: z.boolean().optional(),
    })
    .optional(),
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
  const existingConversation = await getWhatsAppConversationById({ id });

  if (!existingConversation) {
    return Response.json({ error: "Conversation not found" }, { status: 404 });
  }

  const rawBody = await request.json().catch(() => null);
  const payload = updateConversationOpsSchema.safeParse(rawBody);

  if (!payload.success) {
    return Response.json({ error: payload.error.flatten() }, { status: 400 });
  }

  const patch = payload.data;
  const conversation = await updateWhatsAppConversationOpsState({
    id,
    patch,
  });

  return Response.json({ conversation });
}
