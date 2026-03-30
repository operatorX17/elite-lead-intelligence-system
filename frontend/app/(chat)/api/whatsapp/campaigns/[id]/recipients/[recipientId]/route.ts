import { z } from "zod";
import { auth } from "@/app/(auth)/auth";
import {
  getWhatsAppCampaignById,
  updateWhatsAppCampaignRecipient,
} from "@/lib/db/whatsapp-campaigns";

const updateRecipientSchema = z.object({
  contactName: z.string().trim().min(1).optional(),
  companyName: z.string().trim().nullable().optional(),
  messageBody: z.string().trim().min(1).optional(),
  status: z.enum(["draft", "approved", "rejected", "sent", "replied", "failed"]).optional(),
  notes: z.string().trim().nullable().optional(),
});

export async function PATCH(
  request: Request,
  context: { params: Promise<{ id: string; recipientId: string }> }
) {
  const session = await auth();
  if (!session?.user) {
    return Response.json({ error: "Unauthorized" }, { status: 401 });
  }

  const rawBody = await request.json().catch(() => null);
  const payload = updateRecipientSchema.safeParse(rawBody);
  if (!payload.success) {
    return Response.json({ error: payload.error.flatten() }, { status: 400 });
  }

  const { id, recipientId } = await context.params;
  const existingCampaign = await getWhatsAppCampaignById({ id });
  if (!existingCampaign) {
    return Response.json({ error: "Campaign not found" }, { status: 404 });
  }

  const patch = {
    ...payload.data,
    approvedByLabel:
      payload.data.status === "approved"
        ? session.user.email ?? session.user.name ?? "Human operator"
        : undefined,
    approvedAt:
      payload.data.status === "approved" ? new Date().toISOString() : undefined,
  };

  const recipient = await updateWhatsAppCampaignRecipient({
    campaignId: id,
    recipientId,
    patch,
  });

  if (!recipient) {
    return Response.json({ error: "Recipient not found" }, { status: 404 });
  }

  return Response.json({ recipient });
}
