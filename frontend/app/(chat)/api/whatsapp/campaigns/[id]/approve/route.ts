import { z } from "zod";
import { auth } from "@/app/(auth)/auth";
import { approveWhatsAppCampaignRecipients } from "@/lib/db/whatsapp-campaigns";

const approveSchema = z.object({
  recipientIds: z.array(z.string().uuid()).optional(),
});

export async function POST(
  request: Request,
  context: { params: Promise<{ id: string }> }
) {
  const session = await auth();
  if (!session?.user) {
    return Response.json({ error: "Unauthorized" }, { status: 401 });
  }

  const rawBody = await request.json().catch(() => ({}));
  const payload = approveSchema.safeParse(rawBody);
  if (!payload.success) {
    return Response.json({ error: payload.error.flatten() }, { status: 400 });
  }

  const { id } = await context.params;
  const campaign = await approveWhatsAppCampaignRecipients({
    campaignId: id,
    approvedByLabel:
      session.user.email ?? session.user.name ?? "Human operator",
    recipientIds: payload.data.recipientIds,
  });

  if (!campaign) {
    return Response.json({ error: "Campaign not found" }, { status: 404 });
  }

  return Response.json({ campaign });
}
